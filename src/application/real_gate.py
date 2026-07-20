from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class RealBatchGate:
    key_valid: bool = False
    truck_permission: bool = False
    geocode_available: bool = False
    distance_unit_validated: bool = False
    vehicle_parameter_acceptable: bool = False
    error_handling_verified: bool = False
    cache_isolation_verified: bool = False
    validated_at: str = ""
    support_ticket_reference: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "RealBatchGate":
        source = Path(path)
        if not source.exists():
            return cls()
        payload = json.loads(source.read_text(encoding="utf-8"))
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: payload[key] for key in allowed if key in payload})

    def failures(self) -> list[str]:
        checks = (
            (self.key_valid, "Key 有效性未确认"),
            (self.truck_permission, "专业货车路径规划权限未确认"),
            (self.geocode_available, "地理编码接口未确认"),
            (self.distance_unit_validated, "三条线路距离单位未确认"),
            (self.vehicle_parameter_acceptable, "车辆参数歧义尚无可接受结论"),
            (self.error_handling_verified, "正式错误处理未验收"),
            (self.cache_isolation_verified, "real/mock 缓存隔离未验收"),
        )
        return [message for passed, message in checks if not passed]

    def ensure_ready(self) -> None:
        failures = self.failures()
        if failures:
            raise RuntimeError("真实批量计算门未通过：" + "；".join(failures) + "。")
