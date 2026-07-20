from __future__ import annotations

from src.utils.text import normalized_text


TARGET_QUOTE = "非线路报价"


def normalize_quote(value: object) -> str:
    return normalized_text(value, remove_all_space=True)


def is_target_quote(value: object) -> bool:
    return normalize_quote(value) == TARGET_QUOTE

