from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from src.domain.models import GeocodeResult
from src.utils.text import normalized_text, stable_hash

from .errors import AmapApiError, AmapErrorKind
from .http_client import AmapHttpClient


GEOCODE_ENDPOINT = "https://restapi.amap.com/v3/geocode/geo"
GEOCODE_API_VERSION = "amap-geocode-v3-contract-2026-02-02"
LOW_PRECISION_BLOCKED_LEVELS = {"国家", "省", "市"}
HIGH_PRECISION_LEVELS = {"门牌号", "门址", "兴趣点", "道路", "道路交叉口"}

_PROVINCE_CITY = re.compile(
    r"(?:北京市|上海市|天津市|重庆市|[^省自治区]{2,12}(?:省|自治区).{0,20}?(?:市|自治州|地区|盟))"
)


def _text(value: object) -> str:
    if value in (None, []):
        return ""
    if isinstance(value, list):
        return "/".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def _coordinate(value: object, name: str) -> float:
    text = _text(value).strip()
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail=f"{name} 坐标无效") from None
    lower, upper = (Decimal("-180"), Decimal("180")) if name == "经度" else (Decimal("-90"), Decimal("90"))
    if not number.is_finite() or number < lower or number > upper:
        raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail=f"{name} 超出有效范围")
    return round(float(number), 6)


def address_has_explicit_province_city(address: str) -> bool:
    return bool(_PROVINCE_CITY.search(address))


class RealGeocoder:
    def __init__(
        self,
        http: AmapHttpClient,
        *,
        cleaner_version: str = "address-cleaner-v1",
        mode: str = "driving_real",
    ) -> None:
        self.http = http
        self.mode = mode
        self.cleaner_version = cleaner_version
        self.cache_contract = f"{mode}:{GEOCODE_API_VERSION}:{cleaner_version}"

    def cache_key_for(self, cleaned_address: str, city_hint: str = "") -> str:
        return stable_hash(
            "geocode",
            self.mode,
            GEOCODE_API_VERSION,
            self.cleaner_version,
            normalized_text(cleaned_address),
            normalized_text(city_hint, remove_all_space=True),
        )

    def _query(self, address: str, city: str = "") -> dict[str, Any] | None:
        params: dict[str, object] = {"address": address, "output": "JSON"}
        if city:
            params["city"] = city
        payload = self.http.request(GEOCODE_ENDPOINT, params, operation="geocode")
        geocodes = payload.get("geocodes")
        if geocodes is None:
            raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail="地理编码缺少 geocodes 字段")
        if not isinstance(geocodes, list):
            raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail="geocodes 不是列表")
        return geocodes[0] if geocodes and isinstance(geocodes[0], dict) else None

    def geocode(self, cleaned_address: str, city_hint: str = "") -> GeocodeResult:
        address = normalized_text(cleaned_address)
        city = normalized_text(city_hint, remove_all_space=True)
        if not address:
            raise AmapApiError(AmapErrorKind.NO_GEOCODE_RESULT, detail="详细地址为空")
        first_city = "" if address_has_explicit_province_city(address) else city
        item = self._query(address, first_city)
        if item is None and city and not first_city:
            item = self._query(address, city)
        if item is None:
            raise AmapApiError(AmapErrorKind.NO_GEOCODE_RESULT)
        location = _text(item.get("location"))
        parts = [part.strip() for part in location.split(",")]
        if len(parts) != 2:
            raise AmapApiError(AmapErrorKind.RESPONSE_SCHEMA, detail="location 不是经度,纬度")
        longitude = _coordinate(parts[0], "经度")
        latitude = _coordinate(parts[1], "纬度")
        province = _text(item.get("province"))
        result_city = _text(item.get("city"))
        district = _text(item.get("district"))
        street = _text(item.get("street"))
        number = _text(item.get("number"))
        level = _text(item.get("level"))
        formatted = _text(item.get("formatted_address")) or "".join(
            value for value in (province, result_city, district, street, number) if value
        ) or address
        summary = stable_hash(
            "geocode-response",
            province,
            result_city,
            district,
            street,
            number,
            _text(item.get("adcode")),
            level,
            f"{longitude:.6f},{latitude:.6f}",
        )
        return GeocodeResult(
            cache_key=self.cache_key_for(address, city),
            cleaned_address=address,
            city_hint=city,
            longitude=longitude,
            latitude=latitude,
            level=level,
            formatted_address=formatted,
            mode=self.mode,
            province=province,
            city=result_city,
            district=district,
            street=street,
            number=number,
            adcode=_text(item.get("adcode")),
            api_version=GEOCODE_API_VERSION,
            queried_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            cleaner_version=self.cleaner_version,
            response_summary=summary,
            route_eligible=level not in LOW_PRECISION_BLOCKED_LEVELS,
            low_precision=bool(level and level not in HIGH_PRECISION_LEVELS),
        )
