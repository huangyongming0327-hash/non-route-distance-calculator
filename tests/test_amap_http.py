from __future__ import annotations

import json

import pytest

from src.amap.errors import AmapApiError, AmapErrorKind
from src.amap.http_client import AmapHttpClient, RealApiAuditLogger, TransportResponse


class SequenceTransport:
    def __init__(self, *items):
        self.items = list(items)
        self.calls = []

    def get(self, endpoint, params, **timeouts):
        self.calls.append((endpoint, dict(params), timeouts))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def response(payload, status=200):
    return TransportResponse(status, payload, json.dumps(payload, ensure_ascii=False))


def test_empty_key_never_calls_transport():
    transport = SequenceTransport(response({"status": "1"}))
    client = AmapHttpClient(lambda: "", transport=transport, max_attempts=1)
    with pytest.raises(AmapApiError) as caught:
        client.request("https://restapi.amap.com/test", {}, operation="geocode")
    assert caught.value.kind == AmapErrorKind.EMPTY_KEY
    assert transport.calls == []


def test_permission_error_is_operation_specific_and_not_retried():
    transport = SequenceTransport(response({"status": "0", "infocode": "10012", "info": "DENIED"}))
    client = AmapHttpClient(lambda: "SECRET", transport=transport, max_attempts=3, sleeper=lambda _: None)
    with pytest.raises(AmapApiError) as caught:
        client.request("https://restapi.amap.com/v5/direction/driving", {}, operation="driving")
    assert caught.value.kind == AmapErrorKind.PERMISSION
    assert caught.value.technical_code == "10012"
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("code", "kind"),
    [("10001", AmapErrorKind.INVALID_KEY), ("10003", AmapErrorKind.DAILY_QUOTA), ("10020", AmapErrorKind.QPS_LIMIT)],
)
def test_official_error_code_mapping(code, kind):
    transport = SequenceTransport(response({"status": "0", "infocode": code, "info": "ERROR"}))
    client = AmapHttpClient(lambda: "SECRET", transport=transport, max_attempts=1)
    with pytest.raises(AmapApiError) as caught:
        client.request("https://restapi.amap.com/test", {}, operation="geocode")
    assert caught.value.kind == kind


def test_retryable_network_and_server_errors_are_bounded():
    network = AmapApiError(AmapErrorKind.NETWORK, retryable=True)
    transport = SequenceTransport(network, response({}, status=500), response({"status": "1"}))
    client = AmapHttpClient(lambda: "SECRET", transport=transport, max_attempts=3, sleeper=lambda _: None)
    assert client.request("https://restapi.amap.com/test", {}, operation="geocode") == {"status": "1"}
    assert client.actual_calls == 3


def test_audit_log_removes_key_url_and_phone(tmp_path):
    payload = {"status": "1", "formatted_address": "联系人13800138000"}
    transport = SequenceTransport(response(payload))
    client = AmapHttpClient(
        lambda: "TOP-SECRET-KEY",
        transport=transport,
        audit_logger=RealApiAuditLogger(tmp_path),
        max_attempts=1,
    )
    client.request(
        "https://restapi.amap.com/v3/geocode/geo",
        {"address": "电话13800138000", "output": "JSON"},
        operation="geocode",
    )
    text = next(tmp_path.glob("*.json")).read_text(encoding="utf-8")
    assert "TOP-SECRET-KEY" not in text
    assert '"key"' not in text.lower()
    assert "13800138000" not in text
    assert "<手机号已脱敏>" in text
