from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from src.domain.models import CleanedAddress
from src.utils.text import normalized_text, redact_address, scalar_text


CLEANER_VERSION = "address-cleaner-v1"
MOBILE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
LANDLINE_RE = re.compile(r"(?<!\d)0\d{2,3}[-－ ]?\d{7,8}(?!\d)")
CONTACT_RE = re.compile(r"(?:联系人|收货人)\s*[:：]?\s*[\u4e00-\u9fff·]{2,5}")
PHONE_LABEL_RE = re.compile(r"(?:联系电话|手机号码|手机号|电话)\s*[:：]?")
MULTI_SEPARATOR_RE = re.compile(r"[\r\n;；/／|｜]+")
LOCATION_EVIDENCE_RE = re.compile(r"(?:省|市|自治州|区|县).*(?:路|街|道|巷|号|园|仓|厂|村|镇|楼|栋)")


def clean_address(value: object) -> CleanedAddress:
    raw = scalar_text(value)
    text = unicodedata.normalize("NFKC", raw)
    removed: list[str] = []
    for label, pattern in (("mobile", MOBILE_RE), ("landline", LANDLINE_RE), ("contact", CONTACT_RE)):
        if pattern.search(text):
            removed.append(label)
            text = pattern.sub(" ", text)
    text = PHONE_LABEL_RE.sub(" ", text)
    text = normalized_text(text)
    text = re.sub(r"\s*([,，;；])\s*", r"\1", text)
    text = re.sub(r"([,，;；]){2,}", r"\1", text).strip(" ,，;；")
    return CleanedAddress(
        raw_address=raw,
        cleaned_address=text,
        redacted_log_address=redact_address(text),
        cleaner_version=CLEANER_VERSION,
        removed_tokens=tuple(removed),
    )


def canonical_city(value: object) -> str:
    text = normalized_text(value, remove_all_space=True)
    for suffix in ("自治州", "地区", "市", "盟"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def city_tokens(value: object, city_catalog: Iterable[str]) -> list[str]:
    text = normalized_text(value, remove_all_space=True)
    candidates = sorted({canonical_city(item) for item in city_catalog if canonical_city(item)}, key=len, reverse=True)
    found: list[str] = []
    cursor = text
    for candidate in candidates:
        if candidate in cursor and candidate not in found:
            found.append(candidate)
            cursor = cursor.replace(candidate, " ")
    return found


def looks_like_multiple_destinations(city: object, address: object, city_catalog: Iterable[str]) -> bool:
    city_found = city_tokens(city, city_catalog)
    if len(city_found) >= 2:
        return True
    raw = scalar_text(address)
    fragments = [normalized_text(item) for item in MULTI_SEPARATOR_RE.split(raw) if normalized_text(item)]
    if len(fragments) < 2:
        return False
    strong_fragments = [item for item in fragments if LOCATION_EVIDENCE_RE.search(item)]
    if len(strong_fragments) < 2:
        return False
    explicit_cities = {token for fragment in strong_fragments for token in city_tokens(fragment, city_catalog)}
    return len(explicit_cities) >= 2


def detect_city_conflict(city: object, address: object, city_catalog: Iterable[str]) -> tuple[bool, list[str]]:
    expected = canonical_city(city)
    if not expected:
        return False, []
    explicit = city_tokens(address, city_catalog)
    if not explicit:
        fallback = re.findall(r"(?:省|自治区|特别行政区)([\u4e00-\u9fff]{2,8})市", normalized_text(address, remove_all_space=True))
        explicit = [canonical_city(item) for item in fallback]
    # 地址同时出现“苏州市常熟市”一类上级市和县级市时，只要期望城市
    # 本身明确出现，就视为行政层级描述而不是冲突。
    if expected in explicit:
        return False, []
    conflicts = [item for item in explicit if item != expected and expected not in item and item not in expected]
    return bool(conflicts), conflicts
