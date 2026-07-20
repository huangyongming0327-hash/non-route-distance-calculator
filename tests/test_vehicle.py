from __future__ import annotations

import pytest

from src.validation.vehicle import VehicleMapper, normalize_vehicle


@pytest.mark.parametrize(
    ("value", "normalized"),
    [
        (4.2, "4.2"),
        ("4.20", "4.2"),
        ("４．２米", "4.2"),
        ("4.2m", "4.2"),
        (6.8, "6.8"),
        ("7.6 米", "7.6"),
        (9.6, "9.6"),
        (13, "13"),
        ("13.0m", "13"),
        ("4.2吨", "4.2吨"),
    ],
)
def test_vehicle_normalization(value, normalized):
    assert normalize_vehicle(value) == normalized


@pytest.mark.parametrize(
    ("value", "size", "label"),
    [
        (4.2, 2, "轻型货车"),
        ("4.2米", 2, "轻型货车"),
        (6.8, 3, "中型货车"),
        (7.6, 3, "中型货车"),
        (9.6, 4, "重型货车"),
        (13, 4, "重型货车"),
    ],
)
def test_vehicle_mapping(value, size, label):
    result = VehicleMapper().map(value)
    assert result is not None
    assert result.size == size
    assert result.label == label
    assert result.mapping_version == "vehicle-map-v1"


@pytest.mark.parametrize("value", ["4.2吨", "5.2", "厢式货车", None, ""])
def test_unknown_vehicle_is_not_guessed(value):
    assert VehicleMapper().map(value) is None
