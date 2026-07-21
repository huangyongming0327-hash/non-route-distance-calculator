from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.addressing.service import TRUSTED_STATUSES
from src.amap.driving_clients import DRIVING_MODE
from src.cache.sqlite_cache import SCHEMA_VERSION, CacheRepository
from src.domain.models import ConfirmedAddress, GeocodeResult, RouteResult


TRANSFER_FORMAT = "non-route-distance-portable-transfer"
TRANSFER_VERSION = 1


@dataclass(frozen=True)
class TransferSummary:
    imported: int = 0
    skipped: int = 0
    geocodes: int = 0
    routes: int = 0


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_json_write(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def _read_transfer(path: str | Path, expected_kind: str) -> dict[str, Any]:
    source = Path(path).resolve()
    if source.stat().st_size > 250 * 1024 * 1024:
        raise ValueError("迁移文件超过 250 MB，已拒绝导入。")
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("迁移文件顶层必须是 JSON 对象。")
    if payload.get("format") != TRANSFER_FORMAT:
        raise ValueError("不是本工具生成的迁移文件。")
    if payload.get("format_version") != TRANSFER_VERSION:
        raise ValueError("迁移文件版本不受支持。")
    if payload.get("kind") != expected_kind:
        raise ValueError("迁移文件类型与当前导入操作不匹配。")
    return payload


def export_trusted_addresses(repository: CacheRepository, path: str | Path) -> Path:
    records = [
        asdict(record)
        for record in repository.list_addresses()
        if record.confirmation_status in TRUSTED_STATUSES
    ]
    return _atomic_json_write(
        path,
        {
            "format": TRANSFER_FORMAT,
            "format_version": TRANSFER_VERSION,
            "kind": "trusted_addresses",
            "cache_schema_version": SCHEMA_VERSION,
            "exported_at": _timestamp(),
            "record_count": len(records),
            "records": records,
        },
    )


def import_trusted_addresses(
    repository: CacheRepository, path: str | Path
) -> TransferSummary:
    payload = _read_transfer(path, "trusted_addresses")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("迁移文件缺少可信地址记录。")
    imported = skipped = 0
    for raw in records:
        if not isinstance(raw, dict):
            raise ValueError("可信地址记录格式无效。")
        record = ConfirmedAddress(**raw)
        if record.confirmation_status not in TRUSTED_STATUSES:
            skipped += 1
            continue
        if repository.get_address(record.address_id) == record:
            skipped += 1
            continue
        repository.put_address(record)
        imported += 1
    return TransferSummary(imported=imported, skipped=skipped)


def export_driving_cache(repository: CacheRepository, path: str | Path) -> Path:
    geocodes = repository.list_geocode_entries(mode=DRIVING_MODE)
    routes = repository.list_route_entries(mode=DRIVING_MODE)
    return _atomic_json_write(
        path,
        {
            "format": TRANSFER_FORMAT,
            "format_version": TRANSFER_VERSION,
            "kind": "driving_cache",
            "cache_schema_version": SCHEMA_VERSION,
            "mode": DRIVING_MODE,
            "exported_at": _timestamp(),
            "geocode_count": len(geocodes),
            "route_count": len(routes),
            "geocodes": geocodes,
            "routes": routes,
        },
    )


def import_driving_cache(
    repository: CacheRepository, path: str | Path
) -> TransferSummary:
    payload = _read_transfer(path, "driving_cache")
    if payload.get("mode") != DRIVING_MODE:
        raise ValueError("迁移文件不是普通驾车正式缓存。")
    geocodes = payload.get("geocodes")
    routes = payload.get("routes")
    if not isinstance(geocodes, list) or not isinstance(routes, list):
        raise ValueError("迁移文件缺少地理编码或路线记录。")
    geocode_count = route_count = skipped = 0
    for entry in geocodes:
        if not isinstance(entry, dict) or not isinstance(entry.get("result"), dict):
            raise ValueError("地理编码缓存记录格式无效。")
        result = GeocodeResult(**entry["result"])
        if result.mode != DRIVING_MODE:
            raise ValueError("地理编码缓存模式不匹配。")
        if repository.get_geocode(result.cache_key, expected_mode=DRIVING_MODE):
            skipped += 1
            continue
        repository.put_geocode(result, str(entry.get("cleaned_address_hash", "")))
        geocode_count += 1
    for entry in routes:
        if not isinstance(entry, dict) or not isinstance(entry.get("result"), dict):
            raise ValueError("路线缓存记录格式无效。")
        result = RouteResult(**entry["result"])
        if result.mode != DRIVING_MODE:
            raise ValueError("路线缓存模式不匹配。")
        if repository.get_route(result.cache_key, expected_mode=DRIVING_MODE):
            skipped += 1
            continue
        repository.put_route(
            result,
            str(entry.get("origin_key", "")),
            str(entry.get("destination_key", "")),
            entry.get("vehicle_size"),
            str(entry.get("origin_address_id", "")),
            str(entry.get("destination_address_id", "")),
            str(entry.get("origin_geocode_version", "")),
            str(entry.get("destination_geocode_version", "")),
        )
        route_count += 1
    return TransferSummary(
        imported=geocode_count + route_count,
        skipped=skipped,
        geocodes=geocode_count,
        routes=route_count,
    )
