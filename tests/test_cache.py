from __future__ import annotations

import sqlite3

from src.amap.mock_clients import MockGeocoder, MockRoutePlanner
from src.cache.sqlite_cache import CacheRepository
from src.domain.models import RowOutcome


def test_schema_and_wal(tmp_path):
    with CacheRepository(tmp_path / "cache.db") as cache:
        assert cache.journal_mode == "wal"
        counts = cache.counts()
        assert set(counts) == {"geocode_cache", "route_cache", "tasks", "row_results", "schema_meta"}
        assert counts["schema_meta"] == 3


def test_geocode_cache_roundtrip(tmp_path):
    result = MockGeocoder().geocode("A路", "广州")
    with CacheRepository(tmp_path / "cache.db") as cache:
        cache.put_geocode(result, "HASH")
        assert cache.get_geocode(result.cache_key) == result


def test_route_cache_roundtrip(tmp_path):
    geocoder = MockGeocoder()
    origin = geocoder.geocode("A", "广州")
    destination = geocoder.geocode("B", "深圳")
    route = MockRoutePlanner().route(origin, destination)
    with CacheRepository(tmp_path / "cache.db") as cache:
        cache.put_route(route, origin.cache_key, destination.cache_key, 0)
        assert cache.get_route(route.cache_key) == route


def test_route_schema_has_no_excel_row(tmp_path):
    path = tmp_path / "cache.db"
    with CacheRepository(path):
        pass
    connection = sqlite3.connect(path)
    columns = [row[1] for row in connection.execute("PRAGMA table_info(route_cache)")]
    connection.close()
    assert "excel_row" not in columns


def test_row_result_incremental_digest(tmp_path):
    outcome = RowOutcome(8, 100.0, "模拟测试", "模拟", "ABC")
    with CacheRepository(tmp_path / "cache.db") as cache:
        cache.create_task("task", "SHA", {}, "mock")
        cache.save_row_outcome("task", outcome)
        assert cache.load_row_outcome("task", 8, "ABC") == outcome
        assert cache.load_row_outcome("task", 8, "CHANGED") is None


def test_route_cache_insert_is_idempotent(tmp_path):
    geocoder = MockGeocoder()
    origin = geocoder.geocode("A", "广州")
    destination = geocoder.geocode("B", "深圳")
    route = MockRoutePlanner().route(origin, destination)
    with CacheRepository(tmp_path / "cache.db") as cache:
        cache.put_route(route, origin.cache_key, destination.cache_key, 0)
        cache.put_route(route, origin.cache_key, destination.cache_key, 0)
        assert cache.counts()["route_cache"] == 1


def test_driving_route_cache_can_store_without_vehicle_size(tmp_path):
    geocoder = MockGeocoder()
    origin = geocoder.geocode("A", "广州")
    destination = geocoder.geocode("B", "深圳")
    route = MockRoutePlanner().route(origin, destination)
    with CacheRepository(tmp_path / "driving_real.sqlite") as cache:
        cache.put_route(route, origin.cache_key, destination.cache_key)
        assert cache.get_route(route.cache_key) == route


def test_clear_route_cache_is_mode_scoped(tmp_path):
    geocoder = MockGeocoder()
    origin = geocoder.geocode("A", "广州")
    destination = geocoder.geocode("B", "深圳")
    route = MockRoutePlanner().route(origin, destination)
    with CacheRepository(tmp_path / "cache.db") as cache:
        cache.put_route(route, origin.cache_key, destination.cache_key, 0)
        assert cache.clear_route_cache(mode="driving_real") == 0
        assert cache.counts()["route_cache"] == 1
        assert cache.clear_route_cache(mode="mock") == 1
