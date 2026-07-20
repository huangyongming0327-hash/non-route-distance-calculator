from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TaskMode(StrEnum):
    MOCK = "mock"
    DRIVING_REAL = "driving_real"
    LOCAL_VALIDATION = "local_validation"


class OfficeEngine(StrEnum):
    EXCEL = "excel"
    WPS = "wps"


class TaskState(StrEnum):
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AddressConfirmationStatus(StrEnum):
    UNCONFIRMED = "未确认"
    SYSTEM_TRUSTED = "系统高可信"
    MANUALLY_CONFIRMED = "人工确认"
    CORRECTED_AND_CONFIRMED = "人工修正后确认"
    INVALID = "地址无效"
    NEEDS_FURTHER_REVIEW = "待进一步核实"


class AddressRiskLevel(StrEnum):
    TRUSTED = "高可信"
    REVIEW = "建议人工复核"
    BLOCKED = "不允许自动算路"


@dataclass(frozen=True)
class FieldMapping:
    quote_type: int
    origin_city: int
    origin_address: int
    destination_city: int
    destination_address: int
    vehicle: int | None = None

    def as_dict(self) -> dict[str, int | None]:
        return asdict(self)


@dataclass(frozen=True)
class WorkbookSelection:
    path: str
    sheet_name: str
    header_row: int
    fields: FieldMapping


@dataclass(frozen=True)
class RowInput:
    excel_row: int
    quote_type: Any
    origin_city: Any
    origin_address: Any
    destination_city: Any
    destination_address: Any
    vehicle: Any


@dataclass(frozen=True)
class CleanedAddress:
    raw_address: str
    cleaned_address: str
    redacted_log_address: str
    cleaner_version: str
    removed_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class VehicleProfile:
    original: str
    normalized: str
    label: str
    size: int
    mapping_version: str


@dataclass(frozen=True)
class GeocodeResult:
    cache_key: str
    cleaned_address: str
    city_hint: str
    longitude: float
    latitude: float
    level: str
    formatted_address: str
    mode: str = "mock"
    province: str = ""
    city: str = ""
    district: str = ""
    street: str = ""
    number: str = ""
    adcode: str = ""
    api_version: str = ""
    queried_at: str = ""
    cleaner_version: str = ""
    response_summary: str = ""
    route_eligible: bool = True
    low_precision: bool = False
    address_id: str = ""
    geocode_version: str = ""
    confirmation_status: str = ""
    data_source: str = ""


@dataclass(frozen=True)
class ConfirmedAddress:
    address_id: str
    original_city: str
    original_address: str
    cleaned_address: str
    query_address: str
    formatted_address: str
    province: str
    city: str
    district: str
    street: str
    number: str
    level: str
    longitude: float | None
    latitude: float | None
    confirmation_status: str
    confirmed_by: str = ""
    confirmed_at: str = ""
    data_source: str = ""
    cleaner_version: str = ""
    geocode_contract_version: str = ""
    address_hash: str = ""
    geocode_version: str = ""
    city_conflict: bool = False
    risk_level: str = AddressRiskLevel.REVIEW.value
    risk_reason: str = ""
    confirmation_note: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class AddressUsage:
    address_id: str
    purposes: tuple[str, ...]
    excel_rows: tuple[int, ...]
    order_count: int
    route_count: int


@dataclass(frozen=True)
class RouteResult:
    cache_key: str
    distance_km: float | None
    mode: str = "mock"
    raw_distance: int | None = None
    path_count: int = 0
    restriction: str = ""
    api_contract_version: str = ""
    queried_at: str = ""


@dataclass
class RowOutcome:
    excel_row: int
    distance_km: float | None
    status: str
    explanation: str
    input_digest: str
    cache_reused: bool = False
    warning_fields: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResultColumns:
    distance: int
    status: int
    explanation: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class ProgressSnapshot:
    stage: str
    scanned: int
    target_total: int
    processed: int
    succeeded: int
    warning: int
    failed: int
    cache_hits: int
    current_row: int | None = None


@dataclass
class RunSummary:
    task_id: str
    state: str
    source_path: str
    output_path: str | None
    target_total: int
    processed: int
    distance_count: int
    warning_count: int
    cache_hits: int
    stopped: bool = False
    error: str | None = None
    actual_http_calls: int = 0
    unique_route_count: int = 0
    multi_destination_count: int = 0
    city_conflict_count: int = 0
