from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable

from src.cache.sqlite_cache import CacheRepository
from src.domain.models import (
    AddressConfirmationStatus,
    AddressRiskLevel,
    AddressUsage,
    ConfirmedAddress,
    GeocodeResult,
    RowInput,
)
from src.utils.text import normalized_text, stable_hash
from src.validation.address import (
    CLEANER_VERSION,
    canonical_city,
    clean_address,
    detect_city_conflict,
    looks_like_multiple_destinations,
)
from src.validation.precision import assess_geocode
from src.validation.quote import is_target_quote


TRUSTED_STATUSES = {
    AddressConfirmationStatus.SYSTEM_TRUSTED.value,
    AddressConfirmationStatus.MANUALLY_CONFIRMED.value,
    AddressConfirmationStatus.CORRECTED_AND_CONFIRMED.value,
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def address_id_for(original_city: object, original_address: object) -> str:
    cleaned = clean_address(original_address).cleaned_address
    city = canonical_city(original_city)
    return stable_hash("confirmed-address-v1", city, cleaned)


def address_hash_for(original_city: object, cleaned_address: str) -> str:
    return stable_hash("address-hash-v1", canonical_city(original_city), cleaned_address)


def geocode_version_for(query_address: str, geocode: GeocodeResult) -> str:
    return stable_hash(
        "confirmed-geocode-v1",
        normalized_text(query_address),
        geocode.api_version,
        geocode.formatted_address,
        geocode.province,
        geocode.city,
        geocode.district,
        geocode.street,
        geocode.number,
        geocode.level,
        f"{geocode.longitude:.6f},{geocode.latitude:.6f}",
    )


@dataclass(frozen=True)
class AddressResolution:
    record: ConfirmedAddress
    geocode: GeocodeResult | None
    confirmed_reused: bool = False
    geocode_cache_reused: bool = False


class AddressBookService:
    def __init__(self, repository: CacheRepository, *, geocoder=None) -> None:
        self.repository = repository
        self.geocoder = geocoder

    @staticmethod
    def _to_geocode(record: ConfirmedAddress) -> GeocodeResult | None:
        if record.longitude is None or record.latitude is None or not record.geocode_version:
            return None
        route_allowed = (
            record.confirmation_status != AddressConfirmationStatus.INVALID.value
            and record.risk_level != AddressRiskLevel.BLOCKED.value
        )
        return GeocodeResult(
            cache_key=record.geocode_version,
            cleaned_address=record.query_address or record.cleaned_address,
            city_hint=record.original_city,
            longitude=record.longitude,
            latitude=record.latitude,
            level=record.level,
            formatted_address=record.formatted_address,
            mode="driving_real",
            province=record.province,
            city=record.city,
            district=record.district,
            street=record.street,
            number=record.number,
            api_version=record.geocode_contract_version,
            cleaner_version=record.cleaner_version,
            route_eligible=route_allowed,
            low_precision=record.risk_level != AddressRiskLevel.TRUSTED.value,
            address_id=record.address_id,
            geocode_version=record.geocode_version,
            confirmation_status=record.confirmation_status,
            data_source="可信地址库复用" if record.confirmation_status in TRUSTED_STATUSES else record.data_source,
        )

    def _placeholder(
        self,
        original_city: object,
        original_address: object,
        *,
        city_conflict: bool,
        multi_destination: bool = False,
    ) -> ConfirmedAddress:
        cleaned = clean_address(original_address)
        timestamp = _now()
        blocked = multi_destination or not cleaned.cleaned_address
        return ConfirmedAddress(
            address_id=address_id_for(original_city, original_address),
            original_city=normalized_text(original_city),
            original_address=cleaned.raw_address,
            cleaned_address=cleaned.cleaned_address,
            query_address=cleaned.cleaned_address,
            formatted_address="",
            province="",
            city="",
            district="",
            street="",
            number="",
            level="",
            longitude=None,
            latitude=None,
            confirmation_status=(
                AddressConfirmationStatus.NEEDS_FURTHER_REVIEW.value
                if blocked else AddressConfirmationStatus.UNCONFIRMED.value
            ),
            data_source="Excel 唯一地址提取",
            cleaner_version=cleaned.cleaner_version,
            geocode_contract_version=getattr(self.geocoder, "cache_contract", ""),
            address_hash=address_hash_for(original_city, cleaned.cleaned_address),
            geocode_version="",
            city_conflict=city_conflict,
            risk_level=(
                AddressRiskLevel.BLOCKED.value if blocked else AddressRiskLevel.REVIEW.value
            ),
            risk_reason=(
                "检测到多目的地，必须拆分后再定位"
                if multi_destination else "尚未取得地理编码结果"
            ),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def observe_geocode(
        self,
        original_city: object,
        original_address: object,
        geocode: GeocodeResult,
        *,
        city_conflict: bool,
        data_source: str,
        confirm_corrected: bool = False,
    ) -> ConfirmedAddress:
        address_id = address_id_for(original_city, original_address)
        old = self.repository.get_address(address_id)
        cleaned = clean_address(original_address)
        query_address = (
            old.query_address if old and old.query_address else geocode.cleaned_address or cleaned.cleaned_address
        )
        assessment = assess_geocode(cleaned.cleaned_address, geocode, city_conflict=city_conflict)
        version = geocode_version_for(query_address, geocode)
        if confirm_corrected:
            status = AddressConfirmationStatus.CORRECTED_AND_CONFIRMED.value
        elif old and old.geocode_version == version and old.confirmation_status in TRUSTED_STATUSES | {
            AddressConfirmationStatus.INVALID.value,
        }:
            status = old.confirmation_status
        elif assessment.risk_level == AddressRiskLevel.TRUSTED.value:
            status = AddressConfirmationStatus.SYSTEM_TRUSTED.value
        elif assessment.risk_level == AddressRiskLevel.BLOCKED.value:
            status = AddressConfirmationStatus.NEEDS_FURTHER_REVIEW.value
        else:
            status = AddressConfirmationStatus.UNCONFIRMED.value
        timestamp = _now()
        if old and status == old.confirmation_status:
            confirmed_by = old.confirmed_by
            confirmed_at = old.confirmed_at
        elif status == AddressConfirmationStatus.SYSTEM_TRUSTED.value:
            confirmed_by = "系统"
            confirmed_at = timestamp
        elif confirm_corrected:
            confirmed_by = old.confirmed_by if old else ""
            confirmed_at = timestamp
        else:
            confirmed_by = ""
            confirmed_at = ""
        record = ConfirmedAddress(
            address_id=address_id,
            original_city=normalized_text(original_city),
            original_address=cleaned.raw_address,
            cleaned_address=cleaned.cleaned_address,
            query_address=query_address,
            formatted_address=geocode.formatted_address,
            province=geocode.province,
            city=geocode.city,
            district=geocode.district,
            street=geocode.street,
            number=geocode.number,
            level=geocode.level,
            longitude=geocode.longitude,
            latitude=geocode.latitude,
            confirmation_status=status,
            confirmed_by=confirmed_by,
            confirmed_at=confirmed_at,
            data_source=data_source,
            cleaner_version=geocode.cleaner_version or cleaned.cleaner_version,
            geocode_contract_version=geocode.api_version or getattr(self.geocoder, "cache_contract", ""),
            address_hash=address_hash_for(original_city, cleaned.cleaned_address),
            geocode_version=version,
            city_conflict=city_conflict,
            risk_level=assessment.risk_level,
            risk_reason=assessment.reason,
            confirmation_note=(old.confirmation_note if old and status == old.confirmation_status else ""),
            created_at=old.created_at if old else timestamp,
            updated_at=timestamp,
        )
        self.repository.put_address(record)
        return record

    def resolve(
        self,
        original_city: object,
        original_address: object,
        *,
        city_conflict: bool,
    ) -> AddressResolution:
        address_id = address_id_for(original_city, original_address)
        current = self.repository.get_address(address_id)
        if current:
            geocode = self._to_geocode(current)
            if geocode or current.confirmation_status == AddressConfirmationStatus.INVALID.value:
                return AddressResolution(
                    current,
                    geocode,
                    confirmed_reused=current.confirmation_status in TRUSTED_STATUSES,
                    geocode_cache_reused=True,
                )
        if self.geocoder is None:
            placeholder = current or self._placeholder(
                original_city, original_address, city_conflict=city_conflict
            )
            if not current:
                self.repository.put_address(placeholder)
            return AddressResolution(placeholder, None)

        cleaned = clean_address(original_address)
        query_address = current.query_address if current and current.query_address else cleaned.cleaned_address
        normalized_city = normalized_text(original_city, remove_all_space=True)
        cache_key = self.geocoder.cache_key_for(query_address, normalized_city)
        mode = str(getattr(self.geocoder, "mode", ""))
        geocode = self.repository.get_geocode(cache_key, expected_mode=mode)
        cache_hit = geocode is not None
        if geocode is None:
            geocode = self.geocoder.geocode(query_address, normalized_city)
            self.repository.put_geocode(geocode, stable_hash(query_address))
        record = self.observe_geocode(
            original_city,
            original_address,
            geocode,
            city_conflict=city_conflict,
            data_source="高德地理编码缓存" if cache_hit else "高德地理编码实时查询",
        )
        return AddressResolution(record, self._to_geocode(record), geocode_cache_reused=cache_hit)

    def save_query_address(self, address_id: str, query_address: str) -> ConfirmedAddress:
        current = self.repository.get_address(address_id)
        if not current:
            raise KeyError(f"地址ID不存在：{address_id}")
        query = clean_address(query_address).cleaned_address
        if not query:
            raise ValueError("用于查询的修正地址不能为空。")
        if query == current.query_address:
            return current
        timestamp = _now()
        changed = replace(
            current,
            query_address=query,
            formatted_address="",
            province="", city="", district="", street="", number="", level="",
            longitude=None, latitude=None,
            confirmation_status=AddressConfirmationStatus.UNCONFIRMED.value,
            confirmed_by="", confirmed_at="",
            data_source="用户修正查询地址",
            geocode_version="",
            risk_level=AddressRiskLevel.REVIEW.value,
            risk_reason="修正查询地址已保存，等待重新解析",
            updated_at=timestamp,
        )
        self.repository.put_address(changed)
        return changed

    def reparse(self, address_id: str, *, confirm_corrected: bool = False) -> ConfirmedAddress:
        if self.geocoder is None:
            raise RuntimeError("重新解析需要可用的高德地理编码客户端。")
        current = self.repository.get_address(address_id)
        if not current:
            raise KeyError(f"地址ID不存在：{address_id}")
        geocode = self.geocoder.geocode(current.query_address, current.original_city)
        self.repository.put_geocode(geocode, stable_hash(current.query_address))
        return self.observe_geocode(
            current.original_city,
            current.original_address,
            geocode,
            city_conflict=current.city_conflict,
            data_source="用户触发重新解析",
            confirm_corrected=confirm_corrected,
        )

    def confirm(self, address_id: str, *, confirmed_by: str = "", note: str = "") -> ConfirmedAddress:
        current = self.repository.get_address(address_id)
        if not current:
            raise KeyError(f"地址ID不存在：{address_id}")
        if not self._to_geocode(current):
            raise ValueError("当前地址没有可确认的有效坐标，请先重新解析。")
        corrected = current.query_address != current.cleaned_address
        status = (
            AddressConfirmationStatus.CORRECTED_AND_CONFIRMED.value
            if corrected else AddressConfirmationStatus.MANUALLY_CONFIRMED.value
        )
        updated = replace(
            current,
            confirmation_status=status,
            confirmed_by=confirmed_by,
            confirmed_at=_now(),
            confirmation_note=note,
            risk_level=AddressRiskLevel.TRUSTED.value,
            risk_reason="用户已确认该标准地址与坐标可用于算路",
            updated_at=_now(),
        )
        self.repository.put_address(updated)
        return updated

    def mark_invalid(self, address_id: str, *, note: str = "") -> ConfirmedAddress:
        current = self.repository.get_address(address_id)
        if not current:
            raise KeyError(f"地址ID不存在：{address_id}")
        updated = replace(
            current,
            confirmation_status=AddressConfirmationStatus.INVALID.value,
            confirmed_at=_now(),
            confirmation_note=note,
            risk_level=AddressRiskLevel.BLOCKED.value,
            risk_reason="用户标记地址无效",
            updated_at=_now(),
        )
        self.repository.put_address(updated)
        self.repository.invalidate_routes_for_address(address_id)
        return updated

    def update_coordinates(
        self,
        address_id: str,
        longitude: float,
        latitude: float,
        *,
        confirmed_by: str = "",
        note: str = "",
    ) -> ConfirmedAddress:
        current = self.repository.get_address(address_id)
        if not current:
            raise KeyError(f"地址ID不存在：{address_id}")
        base = self._to_geocode(current)
        if base is None:
            base = GeocodeResult(
                "", current.query_address, current.original_city, longitude, latitude,
                current.level or "人工坐标", current.formatted_address or current.query_address,
                mode="driving_real", province=current.province, city=current.city,
                district=current.district, street=current.street, number=current.number,
                api_version=current.geocode_contract_version, cleaner_version=current.cleaner_version,
            )
        changed_geo = replace(base, longitude=float(longitude), latitude=float(latitude))
        version = geocode_version_for(current.query_address, changed_geo)
        updated = replace(
            current,
            longitude=float(longitude), latitude=float(latitude), geocode_version=version,
            confirmation_status=AddressConfirmationStatus.CORRECTED_AND_CONFIRMED.value,
            confirmed_by=confirmed_by, confirmed_at=_now(), confirmation_note=note,
            data_source="用户修正坐标", risk_level=AddressRiskLevel.TRUSTED.value,
            risk_reason="用户已修正并确认坐标", updated_at=_now(),
        )
        self.repository.put_address(updated)
        return updated

    def batch_confirm_high_trust(self) -> int:
        count = 0
        for current in self.repository.list_addresses():
            if (
                current.risk_level == AddressRiskLevel.TRUSTED.value
                and current.confirmation_status == AddressConfirmationStatus.UNCONFIRMED.value
                and current.geocode_version
                and not current.city_conflict
            ):
                self.repository.put_address(replace(
                    current,
                    confirmation_status=AddressConfirmationStatus.SYSTEM_TRUSTED.value,
                    confirmed_at=_now(),
                    data_source="系统高可信批量确认",
                    updated_at=_now(),
                ))
                count += 1
        return count

    def sync_rows(
        self,
        rows: Iterable[RowInput],
        city_catalog: Iterable[str],
        *,
        parse_missing: bool = False,
    ) -> tuple[list[ConfirmedAddress], dict[str, AddressUsage]]:
        target_rows = [row for row in rows if is_target_quote(row.quote_type)]
        usage: dict[str, dict[str, object]] = {}
        route_pairs: set[tuple[str, str]] = set()
        for row in target_rows:
            origin_id = address_id_for(row.origin_city, row.origin_address)
            destination_id = address_id_for(row.destination_city, row.destination_address)
            route_pairs.add((origin_id, destination_id))
            for purpose, city, address, address_id in (
                ("发货", row.origin_city, row.origin_address, origin_id),
                ("目的", row.destination_city, row.destination_address, destination_id),
            ):
                item = usage.setdefault(address_id, {
                    "purposes": set(), "rows": set(), "city": city, "address": address,
                })
                item["purposes"].add(purpose)  # type: ignore[union-attr]
                item["rows"].add(row.excel_row)  # type: ignore[union-attr]

        for address_id, item in usage.items():
            city = item["city"]
            address = item["address"]
            city_conflict, _ = detect_city_conflict(city, clean_address(address).cleaned_address, city_catalog)
            multi = looks_like_multiple_destinations(city, address, city_catalog)
            existing = self.repository.get_address(address_id)
            if (
                existing
                and existing.confirmation_status == AddressConfirmationStatus.SYSTEM_TRUSTED.value
                and not existing.confirmed_at
            ):
                existing = replace(
                    existing,
                    confirmed_by=existing.confirmed_by or "系统",
                    confirmed_at=_now(),
                    updated_at=_now(),
                )
                self.repository.put_address(existing)
            if existing and (
                existing.geocode_version or multi or not parse_missing
            ):
                continue
            placeholder = self._placeholder(
                city, address, city_conflict=city_conflict, multi_destination=multi
            )
            if not multi and self.geocoder is not None:
                cleaned = placeholder.cleaned_address
                key = self.geocoder.cache_key_for(cleaned, normalized_text(city, remove_all_space=True))
                cached = self.repository.get_geocode(key, expected_mode=str(getattr(self.geocoder, "mode", "")))
                if cached:
                    self.observe_geocode(
                        city, address, cached, city_conflict=city_conflict,
                        data_source="TASK-004R 高德地理编码缓存迁移",
                    )
                    continue
                if parse_missing:
                    try:
                        fresh = self.geocoder.geocode(
                            cleaned, normalized_text(city, remove_all_space=True)
                        )
                        self.repository.put_geocode(fresh, stable_hash(cleaned))
                        self.observe_geocode(
                            city, address, fresh, city_conflict=city_conflict,
                            data_source="TASK-005A 唯一地址实时解析",
                        )
                        continue
                    except Exception as exc:
                        placeholder = replace(
                            placeholder,
                            risk_level=AddressRiskLevel.BLOCKED.value,
                            confirmation_status=AddressConfirmationStatus.NEEDS_FURTHER_REVIEW.value,
                            risk_reason=f"地理编码失败：{exc}",
                        )
            self.repository.put_address(placeholder)

        addresses = [self.repository.get_address(address_id) for address_id in usage]
        address_list = [item for item in addresses if item is not None]
        usage_result: dict[str, AddressUsage] = {}
        for address_id, item in usage.items():
            related_routes = {
                pair for pair in route_pairs if address_id in pair
            }
            rows_for_address = tuple(sorted(item["rows"]))  # type: ignore[arg-type]
            usage_result[address_id] = AddressUsage(
                address_id=address_id,
                purposes=tuple(sorted(item["purposes"])),  # type: ignore[arg-type]
                excel_rows=rows_for_address,
                order_count=len(rows_for_address),
                route_count=len(related_routes),
            )
        return address_list, usage_result
