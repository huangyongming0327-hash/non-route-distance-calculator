from __future__ import annotations

import hashlib

from src.domain.models import GeocodeResult, RouteResult
from src.utils.text import stable_hash


MOCK_VERSION = "mock-api-v1"


def _fraction(seed: str, start: int, length: int = 8) -> float:
    return int(seed[start : start + length], 16) / float(16 ** length - 1)


class MockGeocoder:
    """确定性模拟地理编码；相同规范化输入始终返回相同坐标。"""

    mode = "mock"
    cache_contract = MOCK_VERSION

    def cache_key_for(self, cleaned_address: str, city_hint: str = "") -> str:
        return stable_hash("geocode", self.mode, MOCK_VERSION, cleaned_address, city_hint)

    def geocode(self, cleaned_address: str, city_hint: str = "") -> GeocodeResult:
        cache_key = self.cache_key_for(cleaned_address, city_hint)
        seed = hashlib.sha256(cache_key.encode("ascii")).hexdigest()
        longitude = round(73.5 + _fraction(seed, 0) * 60.0, 6)
        latitude = round(18.0 + _fraction(seed, 8) * 35.5, 6)
        return GeocodeResult(
            cache_key=cache_key,
            cleaned_address=cleaned_address,
            city_hint=city_hint,
            longitude=longitude,
            latitude=latitude,
            level="模拟门牌号",
            formatted_address=cleaned_address,
            mode=self.mode,
        )


class MockRoutePlanner:
    """确定性模拟路线；只用于隐藏的开发测试模式。"""

    mode = "mock"
    cache_contract = MOCK_VERSION

    def cache_key_for(self, origin: GeocodeResult, destination: GeocodeResult) -> str:
        return stable_hash(
            "route", self.mode, MOCK_VERSION, origin.cache_key, destination.cache_key
        )

    def route(self, origin: GeocodeResult, destination: GeocodeResult) -> RouteResult:
        cache_key = self.cache_key_for(origin, destination)
        raw = int(hashlib.sha256(cache_key.encode("ascii")).hexdigest()[:12], 16)
        distance_km = round(15.0 + (raw % 19850) / 10.0, 1)
        return RouteResult(cache_key=cache_key, distance_km=distance_km, mode=self.mode)
