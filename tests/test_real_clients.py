from __future__ import annotations

import json

import pytest

from src.amap.distance import meters_to_kilometers, parse_nonnegative_meters
from src.amap.driving_clients import (
    DRIVING_API_VERSION,
    DRIVING_ENDPOINT,
    DRIVING_MODE,
    RealDrivingRouter,
    test_connection as run_connection_test,
)
from src.amap.errors import AmapApiError, AmapErrorKind
from src.amap.http_client import AmapHttpClient, TransportResponse
from src.amap.real_clients import RealGeocoder
from src.domain.models import GeocodeResult


class SequenceTransport:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, endpoint, params, **timeouts):
        self.calls.append((endpoint, dict(params)))
        payload = self.payloads.pop(0)
        return TransportResponse(200, payload, json.dumps(payload, ensure_ascii=False))


def http(*payloads):
    transport = SequenceTransport(*payloads)
    return AmapHttpClient(lambda: "SECRET", transport=transport, max_attempts=1), transport


def geocode_payload(*, level="门牌号", location="114.054000,22.543000"):
    return {
        "status": "1",
        "count": "1",
        "geocodes": [{
            "formatted_address": "广东省深圳市龙华区观宝路3号",
            "province": "广东省",
            "city": "深圳市",
            "district": "龙华区",
            "street": "观宝路",
            "number": "3号",
            "adcode": "440309",
            "level": level,
            "location": location,
        }],
    }


def route_payload(*distances: str):
    values = distances or ("12345",)
    return {
        "status": "1",
        "route": {
            "paths": [
                {"distance": value, "restriction": "0", "steps": []}
                for value in values
            ]
        },
    }


def geo(key, lon, lat, formatted=None):
    return GeocodeResult(
        cache_key=key,
        cleaned_address=key,
        city_hint="",
        longitude=lon,
        latitude=lat,
        level="门牌号",
        formatted_address=formatted or key,
        mode=DRIVING_MODE,
        cleaner_version="address-cleaner-v1",
    )


def test_detailed_address_with_province_city_does_not_force_city():
    client, transport = http(geocode_payload())
    result = RealGeocoder(client).geocode("广东省深圳市龙华区观宝路3号", "广州")
    assert "city" not in transport.calls[0][1]
    assert result.city == "深圳市"
    assert result.route_eligible is True
    assert result.mode == DRIVING_MODE


def test_address_without_administration_uses_city_hint():
    client, transport = http(geocode_payload())
    RealGeocoder(client).geocode("观宝路3号", "深圳")
    assert transport.calls[0][1]["city"] == "深圳"


def test_explicit_address_retries_with_city_only_after_no_result():
    empty = {"status": "1", "count": "0", "geocodes": []}
    client, transport = http(empty, geocode_payload())
    RealGeocoder(client).geocode("广东省深圳市龙华区观宝路3号", "深圳")
    assert "city" not in transport.calls[0][1]
    assert transport.calls[1][1]["city"] == "深圳"


@pytest.mark.parametrize("level", ["国家", "省", "市"])
def test_city_or_coarser_result_is_not_route_eligible(level):
    client, _ = http(geocode_payload(level=level))
    assert RealGeocoder(client).geocode("深圳市", "深圳").route_eligible is False


@pytest.mark.parametrize("level", ["区县", "乡镇", "村庄"])
def test_eligible_but_low_precision_is_marked(level):
    client, _ = http(geocode_payload(level=level))
    result = RealGeocoder(client).geocode("深圳市龙华区", "深圳")
    assert result.route_eligible is True
    assert result.low_precision is True


def test_amap_door_address_alias_is_high_precision():
    client, _ = http(geocode_payload(level="门址"))
    result = RealGeocoder(client).geocode("深圳市龙华区观宝路3号", "深圳")
    assert result.route_eligible is True
    assert result.low_precision is False


def test_geocode_missing_and_invalid_location_are_distinguished():
    client, _ = http({"status": "1", "count": "0", "geocodes": []})
    with pytest.raises(AmapApiError) as no_result:
        RealGeocoder(client).geocode("未知地址", "")
    assert no_result.value.kind == AmapErrorKind.NO_GEOCODE_RESULT
    bad, _ = http(geocode_payload(location="bad"))
    with pytest.raises(AmapApiError) as schema:
        RealGeocoder(bad).geocode("观宝路3号", "深圳")
    assert schema.value.kind == AmapErrorKind.RESPONSE_SCHEMA


def test_v5_driving_request_contract_and_first_route():
    client, transport = http(route_payload("12345", "99999"))
    result = RealDrivingRouter(client).route(
        geo("A", 116.1, 39.1), geo("B", 116.2, 39.2)
    )
    endpoint, params = transport.calls[0]
    assert endpoint == DRIVING_ENDPOINT
    assert params == {
        "origin": "116.100000,39.100000",
        "destination": "116.200000,39.200000",
        "strategy": 32,
        "cartype": 0,
        "ferry": 1,
        "alternative_route": 1,
        "output": "json",
        "key": "SECRET",
    }
    assert result.raw_distance == 12345
    assert result.distance_km == 12.3
    assert result.path_count == 2
    assert result.api_contract_version == DRIVING_API_VERSION


@pytest.mark.parametrize(
    ("meters", "kilometers"),
    [(0, 0.0), (1, 0.0), (49, 0.0), (50, 0.1), (1249, 1.2), (1250, 1.3), (12345, 12.3)],
)
def test_distance_meter_to_kilometer_round_half_up(meters, kilometers):
    assert meters_to_kilometers(meters) == kilometers


@pytest.mark.parametrize("value", [None, "", "-1", -1, "NaN", "Infinity", "1.2"])
def test_invalid_raw_distance_is_rejected(value):
    with pytest.raises(AmapApiError):
        parse_nonnegative_meters(value)


@pytest.mark.parametrize("payload", [
    {"status": "1"},
    {"status": "1", "route": {}},
    {"status": "1", "route": {"paths": []}},
])
def test_missing_route_or_paths_is_rejected(payload):
    client, _ = http(payload)
    with pytest.raises(AmapApiError):
        RealDrivingRouter(client).route(geo("A", 116.1, 39.1), geo("B", 116.2, 39.2))


def test_route_cache_key_is_stable_and_contains_no_vehicle_dimension():
    router, _ = http()
    planner = RealDrivingRouter(router)
    origin = geo("A", 116.1, 39.1, "起点标准地址")
    destination = geo("B", 116.2, 39.2, "终点标准地址")
    first = planner.cache_key_for(origin, destination)
    second = planner.cache_key_for(origin, destination)
    assert first == second
    assert len(first) == 64


def test_connection_uses_exactly_two_successful_calls():
    client, transport = http(geocode_payload(), route_payload("10000"))
    result = run_connection_test(client)
    assert result.key_valid and result.geocode_available and result.driving_available
    assert result.actual_calls == 2
    assert len(transport.calls) == 2
    assert transport.calls[1][0] == DRIVING_ENDPOINT
    assert result.message == "Key、地理编码和普通驾车路径规划均可用。"
