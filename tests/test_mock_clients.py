from __future__ import annotations

from src.amap.mock_clients import MockGeocoder, MockRoutePlanner


def test_geocoder_is_deterministic():
    client = MockGeocoder()
    assert client.geocode("深圳市宝安区A路", "深圳") == client.geocode("深圳市宝安区A路", "深圳")


def test_geocoder_changes_for_different_input():
    client = MockGeocoder()
    assert client.geocode("A路", "深圳").cache_key != client.geocode("B路", "深圳").cache_key


def test_mock_coordinates_are_in_china_envelope():
    result = MockGeocoder().geocode("测试地址", "广州")
    assert 73.5 <= result.longitude <= 133.5
    assert 18 <= result.latitude <= 53.5


def test_route_is_deterministic_and_one_decimal():
    geocoder = MockGeocoder()
    origin = geocoder.geocode("A", "广州")
    destination = geocoder.geocode("B", "深圳")
    first = MockRoutePlanner().route(origin, destination)
    second = MockRoutePlanner().route(origin, destination)
    assert first == second
    assert first.distance_km == round(first.distance_km, 1)


def test_route_key_does_not_include_vehicle_or_row():
    geocoder = MockGeocoder()
    origin = geocoder.geocode("A", "广州")
    destination = geocoder.geocode("B", "深圳")
    route = MockRoutePlanner().route(origin, destination)
    assert route == MockRoutePlanner().route(origin, destination)
    assert "248" not in route.cache_key
