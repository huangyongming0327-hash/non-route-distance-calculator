from __future__ import annotations

import pytest

from src.validation.quote import is_target_quote, normalize_quote


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("非线路报价", True),
        (" 非线路报价 ", True),
        ("非　线路　报价", True),
        ("非\u00a0线路报价", True),
        ("非\u200b线路报价", True),
        ("非线路报\ufeff价", True),
        ("线路报价", False),
        ("非线路报价测试", False),
        ("报价非线路", False),
        (None, False),
        (0, False),
        ("", False),
    ],
)
def test_exact_quote_normalization(value, expected):
    assert is_target_quote(value) is expected


def test_quote_fullwidth_normalization():
    assert normalize_quote("非线路报价") == "非线路报价"
