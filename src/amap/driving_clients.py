from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.domain.models import GeocodeResult, RouteResult
from src.utils.text import stable_hash

from .distance import DRIVING_DISTANCE_UNIT_VERSION, meters_to_kilometers, parse_nonnegative_meters
from .errors import AmapApiError, AmapErrorKind
from .http_client import AmapHttpClient
from .real_clients import RealGeocoder


DRIVING_ENDPOINT = "https://restapi.amap.com/v5/direction/driving"
DRIVING_API_VERSION = "amap-driving-v5-contract-2026-06-17"
DRIVING_ALGORITHM_VERSION = "task-004r-driving-v1"
DRIVING_MODE = "driving_real"


def _first_path(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    route = payload.get("route")
    if not isinstance(route, dict):
        raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail="驾车响应缺少 route")
    paths = route.get("paths")
    if paths in (None, [], {}):
        raise AmapApiError(AmapErrorKind.NO_ROUTE_RESULT)
    if isinstance(paths, dict):
        paths = [paths]
    if not isinstance(paths, list) or not paths or not isinstance(paths[0], dict):
        raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail="route.paths 结构异常")
    return paths[0], len(paths)


class RealDrivingRouter:
    mode = DRIVING_MODE

    def __init__(self, http: AmapHttpClient, *, cleaner_version: str = "address-cleaner-v1") -> None:
        self.http = http
        self.cleaner_version = cleaner_version
        self.cache_contract = ":".join(
            (
                DRIVING_MODE,
                DRIVING_API_VERSION,
                DRIVING_DISTANCE_UNIT_VERSION,
                cleaner_version,
                DRIVING_ALGORITHM_VERSION,
                "strategy=32",
                "cartype=0",
                "ferry=1",
                "alternative_route=1",
            )
        )

    def cache_key_for(self, origin: GeocodeResult, destination: GeocodeResult) -> str:
        return stable_hash(
            "route",
            DRIVING_MODE,
            f"{origin.longitude:.6f},{origin.latitude:.6f}",
            f"{destination.longitude:.6f},{destination.latitude:.6f}",
            stable_hash(origin.formatted_address),
            stable_hash(destination.formatted_address),
            origin.geocode_version or origin.cache_key,
            destination.geocode_version or destination.cache_key,
            32,
            0,
            1,
            1,
            DRIVING_API_VERSION,
            origin.cleaner_version or self.cleaner_version,
            destination.cleaner_version or self.cleaner_version,
            DRIVING_ALGORITHM_VERSION,
        )

    def legacy_cache_key_for(self, origin: GeocodeResult, destination: GeocodeResult) -> str:
        """TASK-004R 旧键，仅用于一次性迁移到带地理编码版本引用的新缓存。"""
        return stable_hash(
            "route",
            DRIVING_MODE,
            f"{origin.longitude:.6f},{origin.latitude:.6f}",
            f"{destination.longitude:.6f},{destination.latitude:.6f}",
            stable_hash(origin.formatted_address),
            stable_hash(destination.formatted_address),
            32,
            0,
            1,
            1,
            DRIVING_API_VERSION,
            origin.cleaner_version or self.cleaner_version,
            destination.cleaner_version or self.cleaner_version,
            DRIVING_ALGORITHM_VERSION,
        )

    def route(self, origin: GeocodeResult, destination: GeocodeResult) -> RouteResult:
        if not origin.route_eligible or not destination.route_eligible:
            raise AmapApiError(AmapErrorKind.LOW_GEOCODE_PRECISION)
        params: dict[str, object] = {
            "origin": f"{origin.longitude:.6f},{origin.latitude:.6f}",
            "destination": f"{destination.longitude:.6f},{destination.latitude:.6f}",
            "strategy": 32,
            "cartype": 0,
            "ferry": 1,
            "alternative_route": 1,
            "output": "json",
        }
        payload = self.http.request(DRIVING_ENDPOINT, params, operation="driving")
        path, path_count = _first_path(payload)
        raw_distance = parse_nonnegative_meters(path.get("distance"))
        return RouteResult(
            cache_key=self.cache_key_for(origin, destination),
            distance_km=meters_to_kilometers(raw_distance),
            mode=self.mode,
            raw_distance=raw_distance,
            path_count=path_count,
            restriction=str(path.get("restriction", "")),
            api_contract_version=DRIVING_API_VERSION,
            queried_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )


@dataclass(frozen=True)
class ConnectionTestResult:
    key_valid: bool
    geocode_available: bool
    driving_available: bool
    actual_calls: int
    message: str


def test_connection(http: AmapHttpClient) -> ConnectionTestResult:
    """显式用户动作：最多 2 个成功请求，验证地理编码和普通驾车 v5。"""
    before = http.actual_calls
    RealGeocoder(http, mode=DRIVING_MODE).geocode("北京市朝阳区阜通东大街6号", "北京")
    origin = GeocodeResult(
        "connection-origin", "", "", 116.481008, 39.989625, "门牌号", "测试起点", DRIVING_MODE
    )
    destination = GeocodeResult(
        "connection-destination", "", "", 116.414217, 40.061741, "门牌号", "测试终点", DRIVING_MODE
    )
    RealDrivingRouter(http).route(origin, destination)
    return ConnectionTestResult(
        True,
        True,
        True,
        http.actual_calls - before,
        "Key、地理编码和普通驾车路径规划均可用。",
    )
