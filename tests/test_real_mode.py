from __future__ import annotations

import json

import pytest

from src.amap.driving_clients import DRIVING_MODE, RealDrivingRouter
from src.amap.http_client import AmapHttpClient, TransportResponse
from src.amap.real_clients import RealGeocoder
from src.application.processor import BusinessProcessor, DRIVING_NOTICE, MOCK_WARNING
from src.cache.sqlite_cache import CacheRepository
from src.domain.models import RowInput, TaskMode


class SequenceTransport:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, endpoint, params, **timeouts):
        self.calls.append((endpoint, dict(params)))
        payload = self.payloads.pop(0)
        return TransportResponse(200, payload, json.dumps(payload, ensure_ascii=False))


def geocode_payload(address, city, *, location, level="门牌号"):
    return {"status": "1", "count": "1", "geocodes": [{
        "formatted_address": address,
        "province": "广东省",
        "city": city,
        "district": "测试区",
        "street": "测试路",
        "number": "1号",
        "adcode": "440000",
        "level": level,
        "location": location,
    }]}


def route_payload(distance="10000"):
    return {"status": "1", "route": {"paths": [{
        "distance": distance, "restriction": "0", "steps": []
    }]}}


def make_clients(*payloads):
    transport = SequenceTransport(*payloads)
    http = AmapHttpClient(lambda: "SECRET", transport=transport, max_attempts=1)
    return transport, {
        "geocoder": RealGeocoder(http, mode=DRIVING_MODE),
        "router": RealDrivingRouter(http),
    }


def test_driving_service_cache_is_checked_before_http_and_has_required_notice(tmp_path):
    transport, clients = make_clients(
        geocode_payload("广东省广州市测试区A路1号", "广州市", location="113.1,23.1"),
        geocode_payload("广东省深圳市测试区B路1号", "深圳市", location="114.1,22.1"),
        route_payload(),
    )
    rows = [
        RowInput(2, "非线路报价", "广州", "广东省广州市测试区A路1号", "深圳", "广东省深圳市测试区B路1号", 4.2),
        RowInput(3, "非线路报价", "广州", "广东省广州市测试区A路1号", "深圳", "广东省深圳市测试区B路1号", "未知车型"),
    ]
    with CacheRepository(tmp_path / "driving_real.sqlite") as cache:
        cache.create_task("task", "SHA", {}, DRIVING_MODE)
        outcomes = BusinessProcessor(cache, **clients).process(
            rows,
            task_id="task",
            mode=TaskMode.DRIVING_REAL,
            city_catalog=["广州", "深圳"],
            force_all=True,
        )
        assert len(transport.calls) == 3
        assert outcomes[0].status == "查询成功—普通驾车参考"
        assert outcomes[1].status == "缓存复用—普通驾车参考"
        assert outcomes[0].distance_km == outcomes[1].distance_km == 10.0
        assert outcomes[1].cache_reused is True
        assert all(DRIVING_NOTICE in item.explanation for item in outcomes)
        assert all(MOCK_WARNING not in item.explanation for item in outcomes)
        assert all("货车可通行" not in item.explanation for item in outcomes)
        assert cache.counts()["geocode_cache"] == 2
        assert cache.counts()["route_cache"] == 1


def test_driving_mode_rejects_mock_clients(tmp_path):
    with CacheRepository(tmp_path / "cache.db") as cache:
        with pytest.raises(RuntimeError, match="driving_real"):
            BusinessProcessor(cache).process_row(
                RowInput(2, "非线路报价", "广州", "A路", "深圳", "B路", 4.2),
                TaskMode.DRIVING_REAL,
                ["广州", "深圳"],
            )


def test_driving_city_conflict_uses_detailed_address_and_marks_warning(tmp_path):
    transport, clients = make_clients(
        geocode_payload("广东省深圳市龙华区观宝路3号", "深圳市", location="114.0,22.0"),
        geocode_payload("广东省深圳市测试区B路1号", "深圳市", location="114.1,22.1"),
        route_payload(),
    )
    with CacheRepository(tmp_path / "driving_real.sqlite") as cache:
        outcome = BusinessProcessor(cache, **clients).process_row(
            RowInput(8, "非线路报价", "广州", "广东省深圳市龙华区观宝路3号", "深圳", "广东省深圳市测试区B路1号", 4.2),
            TaskMode.DRIVING_REAL,
            ["广州", "深圳"],
        )
    assert outcome.status == "查询成功—地址冲突待确认"
    assert outcome.distance_km == 10.0
    assert {"origin_city", "origin_address", "status", "explanation"} <= set(outcome.warning_fields)
    assert "city" not in transport.calls[0][1]
    assert DRIVING_NOTICE in outcome.explanation


def test_district_only_result_blocks_route(tmp_path):
    _, clients = make_clients(
        geocode_payload("广东省广州市测试区", "广州市", location="113.1,23.1", level="区县"),
        geocode_payload("广东省深圳市测试区B路1号", "深圳市", location="114.1,22.1"),
        route_payload(),
    )
    with CacheRepository(tmp_path / "driving_real.sqlite") as cache:
        outcome = BusinessProcessor(cache, **clients).process_row(
            RowInput(2, "非线路报价", "广州", "广东省广州市测试区", "深圳", "广东省深圳市测试区B路1号", None),
            TaskMode.DRIVING_REAL,
            ["广州", "深圳"],
        )
    assert outcome.status == "地址风险过高—未计算"
    assert outcome.distance_km is None
    assert len(clients["router"].http.transport.calls) == 1


def test_vehicle_change_does_not_change_input_digest(tmp_path):
    _, clients = make_clients()
    with CacheRepository(tmp_path / "driving_real.sqlite") as cache:
        processor = BusinessProcessor(cache, **clients)
        common = (2, "非线路报价", "广州", "A路", "深圳", "B路")
        assert processor.input_digest(RowInput(*common, None), TaskMode.DRIVING_REAL) == processor.input_digest(
            RowInput(*common, "任意未知车型"), TaskMode.DRIVING_REAL
        )


def test_force_refresh_calls_route_once_per_unique_pair(tmp_path):
    transport, clients = make_clients(
        geocode_payload("广东省广州市A路", "广州市", location="113.1,23.1"),
        geocode_payload("广东省深圳市B路", "深圳市", location="114.1,22.1"),
        route_payload("11000"),
    )
    rows = [
        RowInput(2, "非线路报价", "广州", "广东省广州市A路", "深圳", "广东省深圳市B路", None),
        RowInput(3, "非线路报价", "广州", "广东省广州市A路", "深圳", "广东省深圳市B路", 9.6),
    ]
    with CacheRepository(tmp_path / "driving_real.sqlite") as cache:
        cache.create_task("task", "SHA", {}, DRIVING_MODE)
        outcomes = BusinessProcessor(cache, **clients).process(
            rows,
            task_id="task",
            mode=TaskMode.DRIVING_REAL,
            city_catalog=["广州", "深圳"],
            force_all=True,
            force_route_refresh=True,
        )
    assert len(transport.calls) == 3
    assert outcomes[1].cache_reused is True
