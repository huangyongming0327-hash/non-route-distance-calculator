from __future__ import annotations

from dataclasses import dataclass
import re

from src.domain.models import AddressRiskLevel, GeocodeResult
from src.utils.text import normalized_text


BLOCKED_LEVELS = {"国家", "省", "市"}
DOOR_LEVELS = {"门牌号", "门址"}
POI_LEVELS = {"兴趣点", "商务住宅", "餐饮服务", "公司企业"}
ROAD_LEVELS = {"道路", "道路交叉口", "交叉口"}
REVIEW_LEVELS = {"街道", "乡镇", "村庄", "村", "开发区", "热点商圈"}
RESIDENTIAL_LEVELS = {"住宅区"}

_ADMIN_UNIT_RE = re.compile(r"([\u4e00-\u9fff]{2,12}?)(自治区|街道|省|市|区|县|镇|乡)")
_ROAD_RE = re.compile(r"([A-Za-z0-9\u4e00-\u9fff]{2,14}(?:大道|公路|路|街|巷|道))")
_NUMBER_RE = re.compile(r"([A-Za-z0-9一二三四五六七八九十百千-]{1,12}号)")
_POI_SUFFIXES = (
    "物流园", "工业园", "科技园", "科创园", "产业园", "仓储中心", "有限公司",
    "公司", "工厂", "云仓", "仓库", "库房", "园区", "基地",
)


@dataclass(frozen=True)
class PrecisionAssessment:
    risk_level: str
    reason: str
    canonical_level: str
    core_name_matched: bool
    administrative_conflict: bool

    @property
    def route_allowed(self) -> bool:
        return self.risk_level != AddressRiskLevel.BLOCKED.value


def canonical_geocode_level(level: object) -> str:
    text = normalized_text(level, remove_all_space=True)
    if text == "门址":
        return "门牌号"
    if text == "交叉口":
        return "道路交叉口"
    return text or "未知"


def coordinates_valid(longitude: float | None, latitude: float | None) -> bool:
    if longitude is None or latitude is None:
        return False
    # 本工具只处理中国境内高德结果；全球合法但明显不在中国的坐标也应阻止算路。
    return 73.0 <= longitude <= 136.0 and 3.0 <= latitude <= 54.0


def _compact(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]", "", normalized_text(value)).lower()


def _terms(text: str) -> set[str]:
    compact = _compact(text)
    terms = set(_ROAD_RE.findall(compact)) | set(_NUMBER_RE.findall(compact))
    for suffix in _POI_SUFFIXES:
        cursor = 0
        while True:
            end = compact.find(suffix, cursor)
            if end < 0:
                break
            suffix_end = end + len(suffix)
            for length in (2, 3, 4, 6, 8, 10):
                start = max(0, end - length)
                terms.add(compact[start:suffix_end])
            cursor = suffix_end
    return {item for item in terms if len(item) >= 2}


def _core_match(raw: str, formatted: str, geocode: GeocodeResult) -> bool:
    raw_compact = _compact(raw)
    formatted_compact = _compact(formatted)
    common = _terms(raw) & _terms(formatted)
    if common:
        return True
    street = _compact(geocode.street)
    number = _compact(geocode.number)
    if street and street in raw_compact and street in formatted_compact:
        return True
    if number and number in raw_compact and number in formatted_compact:
        return True
    formatted_core = formatted_compact
    for component in (
        geocode.province, geocode.city, geocode.district, geocode.street, geocode.number
    ):
        token = _compact(component)
        if token:
            formatted_core = formatted_core.replace(token, "")
    if len(formatted_core) >= 2 and formatted_core in raw_compact:
        return True
    # 避免行政区名称本身造成“名称匹配”的假阳性，要求至少 5 个连续字符。
    shorter, longer = sorted((raw_compact, formatted_compact), key=len)
    return len(shorter) >= 5 and shorter in longer


def _administrative_conflict(raw: str, formatted: str) -> bool:
    def units(value: str, suffixes: set[str]) -> set[str]:
        return {
            name + suffix
            for name, suffix in _ADMIN_UNIT_RE.findall(_compact(value))
            if suffix in suffixes
        }

    raw_districts = units(raw, {"区", "县"})
    formatted_districts = units(formatted, {"区", "县"})
    if raw_districts and formatted_districts and raw_districts.isdisjoint(formatted_districts):
        return True
    raw_towns = units(raw, {"街道", "镇", "乡"})
    formatted_towns = units(formatted, {"街道", "镇", "乡"})
    return bool(raw_towns and formatted_towns and raw_towns.isdisjoint(formatted_towns))


def assess_geocode(
    raw_address: str,
    geocode: GeocodeResult,
    *,
    city_conflict: bool = False,
) -> PrecisionAssessment:
    level = canonical_geocode_level(geocode.level)
    formatted = geocode.formatted_address
    core_match = _core_match(raw_address, formatted, geocode)
    admin_conflict = _administrative_conflict(raw_address, formatted)

    if not coordinates_valid(geocode.longitude, geocode.latitude):
        return PrecisionAssessment(
            AddressRiskLevel.BLOCKED.value, "坐标缺失、越界或明显不在中国境内", level,
            core_match, admin_conflict,
        )
    if level in BLOCKED_LEVELS:
        return PrecisionAssessment(
            AddressRiskLevel.BLOCKED.value, f"高德仅定位到{level}级", level,
            core_match, admin_conflict,
        )
    if level == "区县":
        return PrecisionAssessment(
            AddressRiskLevel.BLOCKED.value,
            "仅定位到区县，未匹配到道路、园区、企业或兴趣点",
            level, core_match, admin_conflict,
        )
    if admin_conflict:
        risk = (
            AddressRiskLevel.REVIEW.value
            if level in DOOR_LEVELS | POI_LEVELS and core_match
            else AddressRiskLevel.BLOCKED.value
        )
        return PrecisionAssessment(risk, "原始地址与高德标准地址的区县不一致", level, core_match, True)
    if city_conflict:
        return PrecisionAssessment(
            AddressRiskLevel.REVIEW.value, "Excel 城市与详细地址指向城市不一致", level,
            core_match, False,
        )
    if level in DOOR_LEVELS:
        if core_match:
            return PrecisionAssessment(
                AddressRiskLevel.TRUSTED.value, "门牌号/门址级且道路、门牌或核心名称匹配", level,
                True, False,
            )
        return PrecisionAssessment(
            AddressRiskLevel.REVIEW.value, "虽为门牌号/门址级，但原始地址与标准地址核心名称不足", level,
            False, False,
        )
    if level in POI_LEVELS:
        if core_match:
            return PrecisionAssessment(
                AddressRiskLevel.TRUSTED.value, "兴趣点/企业级且核心名称匹配", level, True, False,
            )
        return PrecisionAssessment(
            AddressRiskLevel.REVIEW.value, "兴趣点级但核心企业、园区或仓库名称匹配不足", level,
            False, False,
        )
    if level in ROAD_LEVELS:
        if core_match:
            return PrecisionAssessment(
                AddressRiskLevel.TRUSTED.value, "道路级且道路或核心名称匹配", level, True, False,
            )
        return PrecisionAssessment(
            AddressRiskLevel.REVIEW.value, "道路级但缺少原始企业、园区或仓库名称", level,
            False, False,
        )
    if level in RESIDENTIAL_LEVELS:
        if core_match:
            return PrecisionAssessment(
                AddressRiskLevel.TRUSTED.value, "住宅区级但明确园区/企业名称匹配", level, True, False,
            )
        return PrecisionAssessment(
            AddressRiskLevel.REVIEW.value, "住宅区名称匹配不充分", level, False, False,
        )
    if level in REVIEW_LEVELS:
        return PrecisionAssessment(
            AddressRiskLevel.REVIEW.value, f"仅定位到{level}级，需确认具体园区或仓库", level,
            core_match, False,
        )
    if level == "未知" and core_match:
        return PrecisionAssessment(
            AddressRiskLevel.REVIEW.value, "高德层级未知，但标准地址仍包含道路或核心名称", level,
            True, False,
        )
    return PrecisionAssessment(
        AddressRiskLevel.BLOCKED.value, f"定位层级“{level}”无法提供足够算路证据", level,
        core_match, False,
    )
