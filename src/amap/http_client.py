from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import http.client
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import time
from typing import Any, Callable, Protocol
from urllib.parse import urlencode, urlsplit
import uuid

from .errors import AmapApiError, AmapErrorKind, error_from_amap


_PHONE = re.compile(r"(?<!\d)(?:1[3-9]\d{9}|0\d{2,3}[- ]?\d{7,8})(?!\d)")
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _redact_text(value: str) -> str:
    return _PHONE.sub("<手机号已脱敏>", value)


def sanitize_for_audit(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): sanitize_for_audit(item)
            for key, item in value.items()
            if str(key).lower() not in {"key", "sig"}
        }
    if isinstance(value, list):
        return [sanitize_for_audit(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_audit(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    payload: dict[str, Any] | None
    raw_text: str


class HttpTransport(Protocol):
    def get(
        self,
        endpoint: str,
        params: dict[str, object],
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> TransportResponse: ...


class StandardLibraryTransport:
    def get(
        self,
        endpoint: str,
        params: dict[str, object],
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> TransportResponse:
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("真实高德接口只允许 HTTPS 地址。")
        query = urlencode(params)
        path = parsed.path + (f"?{query}" if query else "")
        connection = http.client.HTTPSConnection(parsed.hostname, parsed.port, timeout=connect_timeout)
        try:
            try:
                connection.connect()
            except socket.gaierror as exc:
                raise AmapApiError(AmapErrorKind.DNS, detail=str(exc), retryable=True) from None
            except (TimeoutError, socket.timeout) as exc:
                raise AmapApiError(AmapErrorKind.CONNECT_TIMEOUT, detail=str(exc), retryable=True) from None
            except OSError as exc:
                raise AmapApiError(AmapErrorKind.NETWORK, detail=str(exc), retryable=True) from None
            try:
                if connection.sock:
                    connection.sock.settimeout(read_timeout)
                connection.request("GET", path, headers={"Accept": "application/json", "User-Agent": "NonRouteDistance/0.5"})
                response = connection.getresponse()
                data = response.read(_MAX_RESPONSE_BYTES + 1)
            except (TimeoutError, socket.timeout) as exc:
                raise AmapApiError(AmapErrorKind.READ_TIMEOUT, detail=str(exc), retryable=True) from None
            except OSError as exc:
                raise AmapApiError(AmapErrorKind.NETWORK, detail=str(exc), retryable=True) from None
            if len(data) > _MAX_RESPONSE_BYTES:
                raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail="响应体超过 8 MiB 安全上限")
            text = data.decode("utf-8", errors="replace")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            return TransportResponse(response.status, payload if isinstance(payload, dict) else None, text)
        finally:
            connection.close()


class RealApiAuditLogger:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def write(self, record: dict[str, Any]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f")
        target = self.directory / f"{timestamp}_{uuid.uuid4().hex[:8]}.json"
        safe_record = sanitize_for_audit(record)
        handle, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=self.directory)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(safe_record, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return target


class AmapHttpClient:
    def __init__(
        self,
        key_provider: object,
        *,
        transport: HttpTransport | None = None,
        audit_logger: RealApiAuditLogger | None = None,
        max_attempts: int = 3,
        connect_timeout: float = 5.0,
        read_timeout: float = 15.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("HTTP 重试次数必须在 1 到 3 次之间。")
        self.key_provider = key_provider
        self.transport = transport or StandardLibraryTransport()
        self.audit_logger = audit_logger
        self.max_attempts = max_attempts
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.sleeper = sleeper
        self.actual_calls = 0

    def _get_key(self) -> str:
        provider = self.key_provider
        if callable(provider):
            value = provider()
        elif hasattr(provider, "get_key"):
            value = provider.get_key()
        else:
            value = None
        key = str(value or "").strip()
        if not key:
            raise AmapApiError(AmapErrorKind.EMPTY_KEY)
        return key

    def _audit(
        self,
        *,
        endpoint: str,
        params: dict[str, object],
        operation: str,
        attempt: int,
        response: TransportResponse | None = None,
        error: AmapApiError | None = None,
    ) -> None:
        if not self.audit_logger:
            return
        record: dict[str, Any] = {
            "queried_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "operation": operation,
            "endpoint": endpoint,
            "params": {key: value for key, value in params.items() if key.lower() not in {"key", "sig"}},
            "attempt": attempt,
        }
        if response is not None:
            record["http_status"] = response.status_code
            record["response"] = response.payload if response.payload is not None else response.raw_text[:2000]
        if error is not None:
            record["error"] = {
                "kind": error.kind.value,
                "technical_code": error.technical_code,
                "detail": error.detail,
            }
        self.audit_logger.write(record)

    @staticmethod
    def _response_error(payload: dict[str, Any], operation: str) -> AmapApiError | None:
        status = str(payload.get("status", ""))
        errcode = str(payload.get("errcode", ""))
        if status == "0":
            code = str(payload.get("infocode") or payload.get("errcode") or "")
            return error_from_amap(code, str(payload.get("info") or payload.get("errmsg") or ""), operation)
        if errcode and errcode != "0":
            return error_from_amap(errcode, str(payload.get("errmsg") or payload.get("errdetail") or ""), operation)
        return None

    def request(self, endpoint: str, params: dict[str, object], *, operation: str) -> dict[str, Any]:
        request_params = dict(params)
        request_params["key"] = self._get_key()
        last_error: AmapApiError | None = None
        for attempt in range(1, self.max_attempts + 1):
            response: TransportResponse | None = None
            try:
                self.actual_calls += 1
                response = self.transport.get(
                    endpoint,
                    request_params,
                    connect_timeout=self.connect_timeout,
                    read_timeout=self.read_timeout,
                )
                if response.status_code == 429:
                    raise AmapApiError(
                        AmapErrorKind.QPS_LIMIT,
                        technical_code="HTTP_429",
                        retryable=True,
                    )
                if response.status_code >= 500:
                    raise AmapApiError(
                        AmapErrorKind.SERVER,
                        technical_code=f"HTTP_{response.status_code}",
                        retryable=True,
                    )
                if response.status_code >= 400:
                    raise AmapApiError(
                        AmapErrorKind.PERMISSION,
                        technical_code=f"HTTP_{response.status_code}",
                    )
                if response.payload is None:
                    raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail="响应不是 JSON 对象")
                api_error = self._response_error(response.payload, operation)
                if api_error:
                    raise api_error
                self._audit(
                    endpoint=endpoint,
                    params=request_params,
                    operation=operation,
                    attempt=attempt,
                    response=response,
                )
                return response.payload
            except AmapApiError as exc:
                last_error = exc
                self._audit(
                    endpoint=endpoint,
                    params=request_params,
                    operation=operation,
                    attempt=attempt,
                    response=response,
                    error=exc,
                )
                if not exc.retryable or attempt >= self.max_attempts:
                    raise
                self.sleeper(0.25 * (2 ** (attempt - 1)))
        assert last_error is not None
        raise last_error
