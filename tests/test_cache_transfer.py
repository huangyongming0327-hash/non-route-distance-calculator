from __future__ import annotations

import json

import pytest

from src.amap.driving_clients import DRIVING_MODE
from src.cache.sqlite_cache import CacheRepository
from src.cache.transfer import (
    export_driving_cache,
    export_trusted_addresses,
    import_driving_cache,
    import_trusted_addresses,
)
from src.domain.models import ConfirmedAddress, GeocodeResult, RouteResult


def _trusted_address() -> ConfirmedAddress:
    return ConfirmedAddress(
        address_id="address-1",
        original_city="广州市",
        original_address="测试路1号",
        cleaned_address="测试路1号",
        query_address="测试路1号",
        formatted_address="广东省广州市测试区测试路1号",
        province="广东省",
        city="广州市",
        district="测试区",
        street="测试路",
        number="1号",
        level="门牌号",
        longitude=113.1,
        latitude=23.1,
        confirmation_status="人工确认",
        confirmed_by="测试",
        confirmed_at="2026-07-21T12:00:00+08:00",
        data_source="测试",
        cleaner_version="address-cleaner-v1",
        geocode_contract_version="geocode-v3",
        address_hash="hash",
        geocode_version="geo-version",
        city_conflict=False,
        risk_level="高可信",
        risk_reason="测试",
        confirmation_note="测试",
        created_at="2026-07-21T12:00:00+08:00",
        updated_at="2026-07-21T12:00:00+08:00",
    )


def test_trusted_address_transfer_roundtrip(tmp_path):
    transfer = tmp_path / "可信地址库 备份.json"
    source_path = tmp_path / "source.sqlite"
    target_path = tmp_path / "target.sqlite"
    record = _trusted_address()
    with CacheRepository(source_path) as source:
        source.put_address(record)
        export_trusted_addresses(source, transfer)
    assert "测试路1号" in transfer.read_text(encoding="utf-8")
    with CacheRepository(target_path) as target:
        summary = import_trusted_addresses(target, transfer)
        assert summary.imported == 1
        assert target.get_address(record.address_id) == record
        repeated = import_trusted_addresses(target, transfer)
        assert repeated.skipped == 1


def test_driving_cache_transfer_excludes_task_history(tmp_path):
    transfer = tmp_path / "普通驾车缓存.json"
    source_path = tmp_path / "source.sqlite"
    target_path = tmp_path / "target.sqlite"
    geocode = GeocodeResult(
        "geo-1", "测试路", "广州", 113.1, 23.1, "门牌号", "广州市测试路",
        mode=DRIVING_MODE, api_version="v3",
    )
    route = RouteResult(
        "route-1", 12.3, mode=DRIVING_MODE, raw_distance=12300,
        path_count=1, api_contract_version="v5",
    )
    with CacheRepository(source_path) as source:
        source.put_geocode(geocode, "hash")
        source.put_route(route, geocode.cache_key, "geo-2")
        source.create_task("private-task", "sha", {"path": "private.xlsx"}, DRIVING_MODE)
        export_driving_cache(source, transfer)
    payload = json.loads(transfer.read_text(encoding="utf-8"))
    assert "private-task" not in transfer.read_text(encoding="utf-8")
    assert payload["geocode_count"] == 1
    assert payload["route_count"] == 1
    with CacheRepository(target_path) as target:
        summary = import_driving_cache(target, transfer)
        assert (summary.geocodes, summary.routes) == (1, 1)
        assert target.get_geocode("geo-1", expected_mode=DRIVING_MODE) == geocode
        assert target.get_route("route-1", expected_mode=DRIVING_MODE) == route


def test_transfer_rejects_wrong_kind(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(
        json.dumps({
            "format": "non-route-distance-portable-transfer",
            "format_version": 1,
            "kind": "driving_cache",
        }),
        encoding="utf-8",
    )
    with CacheRepository(tmp_path / "target.sqlite") as target:
        with pytest.raises(ValueError, match="类型"):
            import_trusted_addresses(target, path)
