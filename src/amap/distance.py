from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .errors import AmapApiError, AmapErrorKind


DRIVING_DISTANCE_UNIT_VERSION = "amap-driving-v5-distance-meter-v1"


def parse_nonnegative_meters(value: object, field_name: str = "route.paths.distance") -> int:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise AmapApiError(
            AmapErrorKind.RESPONSE_SCHEMA, detail=f"{field_name} 不是有效数字"
        ) from None
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise AmapApiError(
            AmapErrorKind.RESPONSE_SCHEMA, detail=f"{field_name} 不是非负整数米值"
        )
    return int(number)


def meters_to_kilometers(meters: object) -> float:
    """高德 v5 驾车原始米数的唯一公里换算入口。"""
    raw = parse_nonnegative_meters(meters)
    value = (Decimal(raw) / Decimal(1000)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return float(value)
