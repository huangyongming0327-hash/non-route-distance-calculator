from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.domain.models import VehicleProfile
from src.utils.text import normalized_text, scalar_text


DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[1] / "config" / "vehicle_mappings.json"


def normalize_vehicle(value: object) -> str:
    text = normalized_text(value, remove_all_space=True).lower()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(?:米|m)?", text)
    if not match:
        return text
    try:
        return format(Decimal(match.group(1)).normalize(), "f")
    except InvalidOperation:
        return text


class VehicleMapper:
    def __init__(self, path: str | Path = DEFAULT_MAPPING_PATH) -> None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.version = str(payload["version"])
        self._items: dict[str, dict[str, object]] = {}
        for item in payload["mappings"]:
            for alias in item["aliases"]:
                self._items[normalize_vehicle(alias)] = item

    def map(self, value: object) -> VehicleProfile | None:
        normalized = normalize_vehicle(value)
        item = self._items.get(normalized)
        if item is None:
            return None
        return VehicleProfile(
            original=scalar_text(value),
            normalized=normalized,
            label=str(item["label"]),
            size=int(item["size"]),
            mapping_version=self.version,
        )

