from __future__ import annotations

from typing import Protocol

from .models import GeocodeResult, RouteResult


class Geocoder(Protocol):
    mode: str

    def cache_key_for(self, cleaned_address: str, city_hint: str = "") -> str: ...

    def geocode(self, cleaned_address: str, city_hint: str = "") -> GeocodeResult: ...


class RoutePlanner(Protocol):
    mode: str

    def cache_key_for(self, origin: GeocodeResult, destination: GeocodeResult) -> str: ...

    def route(self, origin: GeocodeResult, destination: GeocodeResult) -> RouteResult: ...
