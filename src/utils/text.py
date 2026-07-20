from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any


INVISIBLE_RE = re.compile(r"[\s\u00a0\u1680\u180e\u2000-\u200d\u2028\u2029\u202f\u205f\u2060\u3000\ufeff]+")


def scalar_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        try:
            return format(Decimal(str(value)).normalize(), "f")
        except InvalidOperation:
            return str(value)
    return str(value)


def normalized_text(value: Any, *, remove_all_space: bool = False) -> str:
    text = unicodedata.normalize("NFKC", scalar_text(value))
    if remove_all_space:
        return INVISIBLE_RE.sub("", text)
    return INVISIBLE_RE.sub(" ", text).strip()


def stable_hash(*parts: Any) -> str:
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()


def redact_address(address: str) -> str:
    if not address:
        return "(空白地址)"
    digest = hashlib.sha256(address.encode("utf-8")).hexdigest()[:12].upper()
    return f"地址摘要#{digest}"

