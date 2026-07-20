from __future__ import annotations

import pytest

from src.validation.address import (
    CLEANER_VERSION,
    canonical_city,
    clean_address,
    detect_city_conflict,
    looks_like_multiple_destinations,
)


@pytest.mark.parametrize(
    ("raw", "contains", "not_contains"),
    [
        (" 广东省深圳市宝安区  ", "广东省深圳市宝安区", "  "),
        ("广东省\n深圳市\t宝安区", "广东省 深圳市 宝安区", "\n"),
        ("仓库 联系人：张三 13800138000", "仓库", "张三"),
        ("仓库 收货人 李四 电话:0755-12345678", "仓库", "0755"),
        ("工业园A栋3号", "工业园A栋3号", "不存在"),
        ("杭州鸿达纺织有限公司库房号:B库1号门", "有限公司", "不存在"),
        ("雷桥路2号元气森林", "雷桥路2号元气森林", "不存在"),
        ("\u3000江苏省苏州市\u00a0", "江苏省苏州市", "\u3000"),
    ],
)
def test_address_cleaning(raw, contains, not_contains):
    result = clean_address(raw)
    assert contains in result.cleaned_address
    assert not_contains not in result.cleaned_address
    assert result.cleaner_version == CLEANER_VERSION
    assert result.raw_address == raw
    assert result.redacted_log_address.startswith("地址摘要#")


def test_mobile_removal_does_not_remove_door_number():
    result = clean_address("科技园18号门，电话13800138000")
    assert "18号门" in result.cleaned_address
    assert "13800138000" not in result.cleaned_address


def test_landline_requires_area_code():
    result = clean_address("仓库12345678号")
    assert "12345678号" in result.cleaned_address


@pytest.mark.parametrize(
    ("value", "expected"),
    [("广州市", "广州"), ("阿坝自治州", "阿坝"), ("北京", "北京"), (None, "")],
)
def test_canonical_city(value, expected):
    assert canonical_city(value) == expected


CATALOG = ["广州", "深圳", "苏州", "常熟", "北京", "杭州", "佛山", "贵阳"]


@pytest.mark.parametrize(
    ("city", "address", "expected"),
    [
        ("广州深圳", "广东省广州市A园/广东省深圳市B园", True),
        ("广州", "广东省广州市白云区A路1号/广东省深圳市宝安区B路2号", True),
        ("广州", "广东省广州市白云区A路与B路交叉口", False),
        ("常熟", "江苏省苏州市常熟市A路1号", False),
        ("深圳", "深圳市宝安区A路1号", False),
    ],
)
def test_multi_destination_detection(city, address, expected):
    assert looks_like_multiple_destinations(city, address, CATALOG) is expected


@pytest.mark.parametrize(
    ("city", "address", "expected"),
    [
        ("广州", "广东省深圳市龙华区观宝路3号", True),
        ("杭州", "北京市海淀区皂甲村支路", True),
        ("常熟", "江苏省苏州市常熟市A路1号", False),
        ("广州", "广东省广州市白云区A路1号", False),
        ("广州", "A路1号", False),
    ],
)
def test_city_conflict(city, address, expected):
    conflict, _ = detect_city_conflict(city, address, CATALOG)
    assert conflict is expected
