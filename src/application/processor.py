from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, replace
import time
from typing import Any

from src.amap.errors import AmapApiError, AmapErrorKind
from src.amap.mock_clients import MockGeocoder, MockRoutePlanner
from src.addressing.service import AddressBookService, TRUSTED_STATUSES, address_id_for
from src.cache.sqlite_cache import CacheRepository
from src.domain.models import (
    AddressConfirmationStatus,
    AddressRiskLevel,
    ProgressSnapshot,
    RowInput,
    RowOutcome,
    TaskMode,
)
from src.utils.text import normalized_text, stable_hash
from src.validation.address import clean_address, detect_city_conflict, looks_like_multiple_destinations
from src.validation.quote import is_target_quote


MOCK_WARNING = "【模拟数据，不可用于正式业务】"
MULTI_DESTINATION_TEXT = "检测到多个目的地，第一版不自动判断行驶顺序，请拆分为单独线路后重新计算。"
DRIVING_NOTICE = (
    "高德普通小汽车驾车推荐路线；strategy=32；不使用轮渡。"
    "本距离不考虑货车限高、限宽、限重、禁行及车牌限制，仅作为非线路报价运距参考。"
)


class BusinessProcessor:
    def __init__(self, repository: CacheRepository, *, geocoder=None, router=None) -> None:
        self.repository = repository
        self.geocoder = geocoder or MockGeocoder()
        self.router = router or MockRoutePlanner()
        self._refreshed_route_keys: set[str] = set()

    def input_digest(self, row: RowInput, mode: TaskMode) -> str:
        origin = clean_address(row.origin_address)
        destination = clean_address(row.destination_address)
        address_versions: list[str] = []
        if mode == TaskMode.DRIVING_REAL:
            for city, address in (
                (row.origin_city, row.origin_address),
                (row.destination_city, row.destination_address),
            ):
                record = self.repository.get_address(address_id_for(city, address))
                address_versions.extend((
                    record.geocode_version if record else "",
                    record.confirmation_status if record else "",
                    record.query_address if record else "",
                ))
        return stable_hash(
            normalized_text(row.quote_type, remove_all_space=True),
            normalized_text(row.origin_city, remove_all_space=True),
            origin.cleaned_address,
            normalized_text(row.destination_city, remove_all_space=True),
            destination.cleaned_address,
            mode.value,
            getattr(self.geocoder, "cache_contract", type(self.geocoder).__name__),
            getattr(self.router, "cache_contract", type(self.router).__name__),
            *address_versions,
        )

    def _geocode(self, cleaned: str, city: str):
        normalized_city = normalized_text(city, remove_all_space=True)
        cache_key = self.geocoder.cache_key_for(cleaned, normalized_city)
        mode = str(getattr(self.geocoder, "mode", ""))
        cached = self.repository.get_geocode(cache_key, expected_mode=mode)
        if cached:
            return cached, True
        candidate = self.geocoder.geocode(cleaned, normalized_city)
        if candidate.cache_key != cache_key or candidate.mode != mode:
            raise RuntimeError("地理编码客户端返回的缓存身份与请求不一致。")
        self.repository.put_geocode(candidate, stable_hash(cleaned))
        return candidate, False

    def _route(self, origin, destination, *, force_refresh: bool):
        cache_key = self.router.cache_key_for(origin, destination)
        mode = str(getattr(self.router, "mode", ""))
        already_refreshed = cache_key in self._refreshed_route_keys
        if not force_refresh or already_refreshed:
            cached = self.repository.get_route(cache_key, expected_mode=mode)
            if cached:
                return cached, True
            legacy_key_for = getattr(self.router, "legacy_cache_key_for", None)
            if callable(legacy_key_for):
                legacy_key = legacy_key_for(origin, destination)
                legacy = self.repository.get_route(legacy_key, expected_mode=mode)
                if legacy:
                    migrated = replace(legacy, cache_key=cache_key)
                    self.repository.put_route(
                        migrated,
                        origin.cache_key,
                        destination.cache_key,
                        vehicle_size=None,
                        origin_address_id=origin.address_id,
                        destination_address_id=destination.address_id,
                        origin_geocode_version=origin.geocode_version,
                        destination_geocode_version=destination.geocode_version,
                    )
                    return migrated, True
        candidate = self.router.route(origin, destination)
        if candidate.cache_key != cache_key or candidate.mode != mode:
            raise RuntimeError("路线客户端返回的缓存身份与请求不一致。")
        self.repository.put_route(
            candidate,
            origin.cache_key,
            destination.cache_key,
            vehicle_size=0 if mode == "mock" else None,
            origin_address_id=getattr(origin, "address_id", ""),
            destination_address_id=getattr(destination, "address_id", ""),
            origin_geocode_version=getattr(origin, "geocode_version", ""),
            destination_geocode_version=getattr(destination, "geocode_version", ""),
        )
        if force_refresh:
            self._refreshed_route_keys.add(cache_key)
        return candidate, False

    @staticmethod
    def _prefix(mode: TaskMode) -> str:
        return MOCK_WARNING if mode == TaskMode.MOCK else ""

    @staticmethod
    def _api_error_outcome(
        row: RowInput,
        input_digest: str,
        audit: dict[str, Any],
        error: AmapApiError,
        warning_fields: list[str],
        *,
        geocode_stage: bool = False,
    ) -> RowOutcome:
        audit["api_error_kind"] = error.kind.value
        if geocode_stage and error.kind == AmapErrorKind.NO_GEOCODE_RESULT:
            status = "详细地址定位失败"
        elif geocode_stage and error.kind == AmapErrorKind.RESPONSE_SCHEMA:
            status = "地址解析失败"
        else:
            status = error.status
        return RowOutcome(
            row.excel_row,
            None,
            status,
            error.user_message,
            input_digest,
            warning_fields=warning_fields + ["status", "explanation"],
            audit=audit,
        )

    def process_row(
        self,
        row: RowInput,
        mode: TaskMode,
        city_catalog: Iterable[str],
        *,
        force_route_refresh: bool = False,
    ) -> RowOutcome:
        if mode == TaskMode.DRIVING_REAL and (
            getattr(self.geocoder, "mode", None) != "driving_real"
            or getattr(self.router, "mode", None) != "driving_real"
        ):
            raise RuntimeError("普通驾车正式模式必须显式注入 driving_real 客户端。")

        origin_multi = looks_like_multiple_destinations(row.origin_city, row.origin_address, city_catalog)
        destination_multi = looks_like_multiple_destinations(row.destination_city, row.destination_address, city_catalog)
        origin = clean_address(row.origin_address)
        destination = clean_address(row.destination_address)
        origin_conflict, origin_conflicts = detect_city_conflict(row.origin_city, origin.cleaned_address, city_catalog)
        destination_conflict, destination_conflicts = detect_city_conflict(
            row.destination_city, destination.cleaned_address, city_catalog
        )
        input_digest = self.input_digest(row, mode)
        audit: dict[str, Any] = {
            "origin": asdict(origin),
            "destination": asdict(destination),
            "origin_conflicts": origin_conflicts,
            "destination_conflicts": destination_conflicts,
            "mode": mode.value,
        }

        if origin_multi or destination_multi:
            fields = ["origin_city", "origin_address"] if origin_multi else []
            if destination_multi:
                fields += ["destination_city", "destination_address"]
            return RowOutcome(
                row.excel_row,
                None,
                "多目的地待确认",
                self._prefix(mode) + MULTI_DESTINATION_TEXT,
                input_digest,
                warning_fields=fields + ["status", "explanation"],
                audit=audit,
            )

        blank_fields: list[str] = []
        if not origin.cleaned_address:
            blank_fields.append("origin_address")
        if not destination.cleaned_address:
            blank_fields.append("destination_address")
        if blank_fields:
            names = "、".join("发货地址" if field == "origin_address" else "目的地址" for field in blank_fields)
            return RowOutcome(
                row.excel_row,
                None,
                "地址为空",
                f"{self._prefix(mode)}{names}为空，未计算距离。",
                input_digest,
                warning_fields=blank_fields + ["status", "explanation"],
                audit=audit,
            )

        warning_fields: list[str] = []
        conflict_warning_fields: list[str] = []
        conflict_messages: list[str] = []
        if origin_conflict:
            conflict_warning_fields += ["origin_city", "origin_address"]
            conflict_messages.append(
                f"发货城市冲突：表中城市“{row.origin_city}”，详细地址指向“{'/'.join(origin_conflicts)}”"
            )
        if destination_conflict:
            conflict_warning_fields += ["destination_city", "destination_address"]
            conflict_messages.append(
                f"目的城市冲突：表中城市“{row.destination_city}”，详细地址指向“{'/'.join(destination_conflicts)}”"
            )

        if mode == TaskMode.LOCAL_VALIDATION:
            if conflict_messages:
                return RowOutcome(
                    row.excel_row,
                    None,
                    "本地校验—地址冲突待确认",
                    "仅本地校验，未调用地理编码或驾车路线。" + "；".join(conflict_messages) + "。",
                    input_digest,
                    warning_fields=conflict_warning_fields + ["status", "explanation"],
                    audit=audit,
                )
            return RowOutcome(
                row.excel_row,
                None,
                "本地校验通过",
                "仅本地校验，未调用地理编码或驾车路线，未生成距离。",
                input_digest,
                audit=audit,
            )

        try:
            if mode == TaskMode.DRIVING_REAL:
                address_book = AddressBookService(self.repository, geocoder=self.geocoder)
                origin_resolution = address_book.resolve(
                    row.origin_city, row.origin_address, city_conflict=origin_conflict
                )
                origin_geo = origin_resolution.geocode
                origin_geo_hit = origin_resolution.geocode_cache_reused
            else:
                origin_resolution = None
                origin_geo, origin_geo_hit = self._geocode(origin.cleaned_address, row.origin_city)
        except AmapApiError as exc:
            return self._api_error_outcome(
                row, input_digest, audit, exc, ["origin_address"], geocode_stage=True
            )
        if mode == TaskMode.DRIVING_REAL and origin_resolution is not None:
            origin_record = origin_resolution.record
            if origin_record.confirmation_status == AddressConfirmationStatus.INVALID.value:
                return RowOutcome(
                    row.excel_row, None, "地址无效", "发货地址已在可信地址库中标记为无效，未计算距离。",
                    self.input_digest(row, mode),
                    warning_fields=["origin_address", "status", "explanation"], audit=audit,
                )
            if origin_geo is None or origin_record.risk_level == AddressRiskLevel.BLOCKED.value:
                audit.update({
                    "origin_address_id": origin_record.address_id,
                    "origin_address_status": origin_record.confirmation_status,
                    "origin_address_risk": origin_record.risk_level,
                    "origin_address_risk_reason": origin_record.risk_reason,
                })
                return RowOutcome(
                    row.excel_row, None, "地址风险过高—未计算",
                    f"发货地址：{origin_record.risk_reason}，必须人工修正或确认后再算路。",
                    self.input_digest(row, mode),
                    warning_fields=["origin_address", "status", "explanation"], audit=audit,
                )
        else:
            origin_record = None
        if origin_geo is None or not origin_geo.route_eligible:
            return self._api_error_outcome(
                row,
                input_digest,
                audit,
                AmapApiError(AmapErrorKind.LOW_GEOCODE_PRECISION),
                ["origin_address"],
                geocode_stage=True,
            )
        try:
            if mode == TaskMode.DRIVING_REAL:
                destination_resolution = address_book.resolve(
                    row.destination_city, row.destination_address,
                    city_conflict=destination_conflict,
                )
                destination_geo = destination_resolution.geocode
                destination_geo_hit = destination_resolution.geocode_cache_reused
            else:
                destination_resolution = None
                destination_geo, destination_geo_hit = self._geocode(
                    destination.cleaned_address, row.destination_city
                )
        except AmapApiError as exc:
            return self._api_error_outcome(
                row, input_digest, audit, exc, ["destination_address"], geocode_stage=True
            )
        if mode == TaskMode.DRIVING_REAL and destination_resolution is not None:
            destination_record = destination_resolution.record
            if destination_record.confirmation_status == AddressConfirmationStatus.INVALID.value:
                return RowOutcome(
                    row.excel_row, None, "地址无效", "目的地址已在可信地址库中标记为无效，未计算距离。",
                    self.input_digest(row, mode),
                    warning_fields=["destination_address", "status", "explanation"], audit=audit,
                )
            if destination_geo is None or destination_record.risk_level == AddressRiskLevel.BLOCKED.value:
                audit.update({
                    "destination_address_id": destination_record.address_id,
                    "destination_address_status": destination_record.confirmation_status,
                    "destination_address_risk": destination_record.risk_level,
                    "destination_address_risk_reason": destination_record.risk_reason,
                })
                return RowOutcome(
                    row.excel_row, None, "地址风险过高—未计算",
                    f"目的地址：{destination_record.risk_reason}，必须人工修正或确认后再算路。",
                    self.input_digest(row, mode),
                    warning_fields=["destination_address", "status", "explanation"], audit=audit,
                )
        else:
            destination_record = None
        if destination_geo is None or not destination_geo.route_eligible:
            return self._api_error_outcome(
                row,
                input_digest,
                audit,
                AmapApiError(AmapErrorKind.LOW_GEOCODE_PRECISION),
                ["destination_address"],
                geocode_stage=True,
            )
        try:
            route, route_hit = self._route(
                origin_geo, destination_geo, force_refresh=force_route_refresh
            )
        except AmapApiError as exc:
            return self._api_error_outcome(row, input_digest, audit, exc, [])

        input_digest = self.input_digest(row, mode)
        audit.update(
            {
                "origin_geocode_key": origin_geo.cache_key,
                "destination_geocode_key": destination_geo.cache_key,
                "origin_formatted_address": origin_geo.formatted_address,
                "destination_formatted_address": destination_geo.formatted_address,
                "origin_coordinate": [origin_geo.longitude, origin_geo.latitude],
                "destination_coordinate": [destination_geo.longitude, destination_geo.latitude],
                "origin_geocode_level": origin_geo.level,
                "destination_geocode_level": destination_geo.level,
                "route_cache_key": route.cache_key,
                "geocode_cache_reused": origin_geo_hit or destination_geo_hit,
                "raw_distance_meters": route.raw_distance,
                "route_path_count": route.path_count,
                "route_api_contract_version": route.api_contract_version,
                "origin_address_id": getattr(origin_geo, "address_id", ""),
                "destination_address_id": getattr(destination_geo, "address_id", ""),
                "origin_geocode_version": getattr(origin_geo, "geocode_version", ""),
                "destination_geocode_version": getattr(destination_geo, "geocode_version", ""),
                "origin_address_status": getattr(origin_geo, "confirmation_status", ""),
                "destination_address_status": getattr(destination_geo, "confirmation_status", ""),
                "origin_address_source": getattr(origin_geo, "data_source", ""),
                "destination_address_source": getattr(destination_geo, "data_source", ""),
            }
        )

        if mode == TaskMode.DRIVING_REAL:
            origin_trusted = bool(origin_record and origin_record.confirmation_status in TRUSTED_STATUSES)
            destination_trusted = bool(destination_record and destination_record.confirmation_status in TRUSTED_STATUSES)
            active_conflicts: list[str] = []
            if origin_conflict and not origin_trusted:
                active_conflicts.append(conflict_messages[0])
            if destination_conflict and not destination_trusted:
                active_conflicts.append(conflict_messages[-1])
            review_reasons: list[str] = []
            if origin_record and not origin_trusted and origin_record.risk_level == AddressRiskLevel.REVIEW.value:
                review_reasons.append(f"发货地址：{origin_record.risk_reason}")
            if destination_record and not destination_trusted and destination_record.risk_level == AddressRiskLevel.REVIEW.value:
                review_reasons.append(f"目的地址：{destination_record.risk_reason}")
        else:
            origin_trusted = destination_trusted = False
            active_conflicts = conflict_messages
            review_reasons = []

        if mode == TaskMode.DRIVING_REAL and active_conflicts:
            status = "查询成功—地址冲突待确认"
            explanation = "；".join(active_conflicts) + "；仍按详细地址坐标计算，请人工确认。" + DRIVING_NOTICE
            if origin_conflict and not origin_trusted:
                warning_fields += ["origin_city", "origin_address"]
            if destination_conflict and not destination_trusted:
                warning_fields += ["destination_city", "destination_address"]
            warning_fields += ["status", "explanation"]
        elif mode == TaskMode.DRIVING_REAL and review_reasons:
            status = "查询成功—定位待复核"
            explanation = "；".join(review_reasons) + "。" + DRIVING_NOTICE
            if origin_record and not origin_trusted and origin_record.risk_level == AddressRiskLevel.REVIEW.value:
                warning_fields.append("origin_address")
            if destination_record and not destination_trusted and destination_record.risk_level == AddressRiskLevel.REVIEW.value:
                warning_fields.append("destination_address")
            warning_fields += ["status", "explanation"]
        elif mode == TaskMode.DRIVING_REAL and route_hit:
            status = "缓存复用—普通驾车参考"
            confirmed_note = (
                "可信地址库复用；" if origin_resolution.confirmed_reused or destination_resolution.confirmed_reused else ""
            )
            explanation = confirmed_note + "命中 driving_real 普通驾车路线缓存。" + DRIVING_NOTICE
        elif mode == TaskMode.DRIVING_REAL:
            status = "查询成功—普通驾车参考"
            explanation = DRIVING_NOTICE
        elif conflict_messages:
            status = "模拟测试—地址冲突待确认"
            explanation = MOCK_WARNING + "；".join(conflict_messages) + "；仍按详细地址的模拟坐标生成距离。"
            warning_fields += conflict_warning_fields + ["status", "explanation"]
        elif route_hit:
            status = "缓存复用—模拟数据"
            explanation = MOCK_WARNING + "命中 mock 模式路线缓存。"
        else:
            status = "模拟测试"
            explanation = MOCK_WARNING + "由确定性 mock 地理编码和路线生成，仅用于开发验证。"

        return RowOutcome(
            row.excel_row,
            route.distance_km,
            status,
            explanation,
            input_digest,
            cache_reused=route_hit,
            warning_fields=warning_fields,
            audit=audit,
        )

    def process(
        self,
        rows: Iterable[RowInput],
        *,
        task_id: str,
        mode: TaskMode,
        city_catalog: Iterable[str],
        force_all: bool = False,
        force_route_refresh: bool = False,
        controller=None,
        progress: Callable[[ProgressSnapshot], None] | None = None,
        checkpoint: Callable[[list[RowOutcome], bool], None] | None = None,
        checkpoint_batch: int = 10,
        checkpoint_seconds: float = 60.0,
        resume_after: int = 0,
    ) -> list[RowOutcome]:
        self._refreshed_route_keys.clear()
        target_rows = [row for row in rows if is_target_quote(row.quote_type)]
        outcomes: list[RowOutcome] = []
        cache_hits = 0
        warning = 0
        last_checkpoint = time.monotonic()
        for index, row in enumerate(target_rows, start=1):
            if controller and not controller.safe_point(
                on_pause=lambda: checkpoint(outcomes, True) if checkpoint else None,
                on_stop=lambda: checkpoint(outcomes, True) if checkpoint else None,
            ):
                break
            digest = self.input_digest(row, mode)
            prior = None if force_all else self.repository.load_row_outcome(
                task_id, row.excel_row, digest
            )
            outcome = prior or self.process_row(
                row,
                mode,
                city_catalog,
                force_route_refresh=force_route_refresh,
            )
            self.repository.save_row_outcome(task_id, outcome)
            outcomes.append(outcome)
            cache_hits += int(outcome.cache_reused)
            warning += int(bool(outcome.warning_fields))
            if progress:
                progress(
                    ProgressSnapshot(
                        "处理业务行",
                        index,
                        len(target_rows),
                        index,
                        index - warning,
                        warning,
                        0,
                        cache_hits,
                        row.excel_row,
                    )
                )
            new_processed = max(0, index - resume_after)
            if checkpoint and index > resume_after and (
                new_processed % checkpoint_batch == 0
                or time.monotonic() - last_checkpoint >= checkpoint_seconds
            ):
                checkpoint(outcomes, False)
                last_checkpoint = time.monotonic()
        stopped = bool(
            controller and getattr(controller.state, "value", controller.state) == "STOPPED"
        )
        if checkpoint and outcomes and not stopped and (
            len(outcomes) % checkpoint_batch or len(outcomes) < len(target_rows)
        ):
            checkpoint(outcomes, True)
        return outcomes
