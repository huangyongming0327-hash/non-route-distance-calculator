from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.addressing.service import AddressBookService
from src.amap.driving_clients import RealDrivingRouter
from src.amap.real_clients import RealGeocoder
from src.application.processor import BusinessProcessor
from src.cache.sqlite_cache import CacheRepository
from src.domain.models import TaskMode, WorkbookSelection
from src.utils.files import sha256_file
from src.validation.precision import canonical_geocode_level
from src.workbook.preview import inspect_workbook, iter_row_inputs


OLD_HIGH_LEVELS = {"门牌号", "兴趣点", "道路", "道路交叉口"}


class NoHttp:
    actual_calls = 0

    def request(self, *args, **kwargs):
        raise AssertionError(f"地址精度分析不得调用 HTTP：{args!r} {kwargs!r}")


def _old_task_rows(connection: sqlite3.Connection) -> tuple[str, list[dict]]:
    task = connection.execute(
        """SELECT task_id FROM tasks
           WHERE task_id LIKE 'task004r_%' AND state='COMPLETED'
           ORDER BY created_at DESC LIMIT 1"""
    ).fetchone()
    if not task:
        raise RuntimeError("未找到 TASK-004R 已完成任务。")
    rows = [
        json.loads(row[0])
        for row in connection.execute(
            "SELECT outcome_json FROM row_results WHERE task_id=? ORDER BY excel_row", (task[0],)
        )
    ]
    return str(task[0]), rows


def build_report() -> dict:
    source = next((ROOT / "samples" / "input").glob("*.xlsx"))
    info = inspect_workbook(source)
    selection = WorkbookSelection(
        str(source), info.selected_sheet, info.header_row, info.recommended_mapping
    )
    rows = list(iter_row_inputs(selection))
    target_rows = [row for row in rows if str(row.quote_type or "").replace(" ", "") == "非线路报价"]
    cache_path = ROOT / "cache" / "driving_real.sqlite"

    raw_origin = {str(row.origin_address or "").strip() for row in target_rows}
    raw_destination = {str(row.destination_address or "").strip() for row in target_rows}
    raw_all = raw_origin | raw_destination
    qualified = {
        (str(city or "").strip(), str(address or "").strip())
        for row in target_rows
        for city, address in (
            (row.origin_city, row.origin_address),
            (row.destination_city, row.destination_address),
        )
    }

    with CacheRepository(cache_path) as repository:
        service = AddressBookService(repository)
        addresses, usage = service.sync_rows(rows, info.city_catalog)
        address_by_id = {item.address_id: item for item in addresses}
        connection = repository._connection
        old_task_id, old_rows = _old_task_rows(connection)

        old_low = [item for item in old_rows if item["status"] == "查询成功—定位精度较低"]
        origin_low = sum(
            item["audit"].get("origin_geocode_level") not in OLD_HIGH_LEVELS for item in old_low
        )
        destination_low = sum(
            item["audit"].get("destination_geocode_level") not in OLD_HIGH_LEVELS for item in old_low
        )
        both_low = sum(
            item["audit"].get("origin_geocode_level") not in OLD_HIGH_LEVELS
            and item["audit"].get("destination_geocode_level") not in OLD_HIGH_LEVELS
            for item in old_low
        )

        geocoded = [item for item in addresses if item.geocode_version]
        raw_levels = Counter(item.level or "(未解析)" for item in addresses)
        canonical_levels = Counter(
            canonical_geocode_level(item.level) if item.geocode_version else "(未解析)"
            for item in addresses
        )
        formatted_distribution = Counter(
            item.formatted_address or "(未解析)" for item in addresses
        )

        purpose_occurrence = Counter()
        for item in old_rows:
            if item.get("distance_km") is None:
                continue
            purpose_occurrence[f"发货:{item['audit'].get('origin_geocode_level')}"] += 1
            purpose_occurrence[f"目的:{item['audit'].get('destination_geocode_level')}"] += 1

        grouped_text: dict[str, list] = defaultdict(list)
        for item in addresses:
            grouped_text[item.original_address].append(item)
        repeated_text_results = []
        for text, items in grouped_text.items():
            if len(items) < 2:
                continue
            signatures = {
                (item.formatted_address, item.longitude, item.latitude, item.level)
                for item in items
            }
            repeated_text_results.append({
                "original_address": text,
                "original_cities": sorted(item.original_city for item in items),
                "result_count": len(signatures),
                "different_result": len(signatures) > 1,
                "results": [
                    {
                        "city": item.original_city,
                        "formatted_address": item.formatted_address,
                        "level": item.level,
                        "longitude": item.longitude,
                        "latitude": item.latitude,
                    }
                    for item in items
                ],
            })

        processor = BusinessProcessor(
            repository,
            geocoder=RealGeocoder(NoHttp(), mode="driving_real"),
            router=RealDrivingRouter(NoHttp()),
        )
        projected = [
            processor.process_row(row, TaskMode.DRIVING_REAL, info.city_catalog)
            for row in target_rows
        ]

    requested_level_counts = {
        "道路": canonical_levels.get("道路", 0) + canonical_levels.get("道路交叉口", 0),
        "门牌号（含高德门址）": canonical_levels.get("门牌号", 0),
        "兴趣点": canonical_levels.get("兴趣点", 0),
        "住宅区": canonical_levels.get("住宅区", 0),
        "乡镇": canonical_levels.get("乡镇", 0),
        "街道": canonical_levels.get("街道", 0),
        "区县": canonical_levels.get("区县", 0),
        "市级": canonical_levels.get("市", 0),
    }
    risk_counts = Counter(item.risk_level for item in addresses)
    status_counts = Counter(item.confirmation_status for item in addresses)
    projected_status = Counter(item.status for item in projected)
    system_overstrict = [
        {
            "address_id": item.address_id,
            "original_city": item.original_city,
            "original_address": item.original_address,
            "formatted_address": item.formatted_address,
            "raw_level": item.level,
            "reason": item.risk_reason,
            "order_count": usage[item.address_id].order_count,
        }
        for item in addresses
        if item.risk_level == "高可信" and item.level in {"门址", "住宅区"}
    ]
    needs_manual = [
        {
            "address_id": item.address_id,
            "original_city": item.original_city,
            "original_address": item.original_address,
            "formatted_address": item.formatted_address,
            "level": item.level or "(未解析)",
            "query_address": item.query_address,
            "confirmation_status": item.confirmation_status,
            "confirmation_note": item.confirmation_note,
            "risk_level": item.risk_level,
            "reason": item.risk_reason,
            "city_conflict": item.city_conflict,
            "order_count": usage[item.address_id].order_count,
            "route_count": usage[item.address_id].route_count,
        }
        for item in addresses
        if item.risk_level != "高可信"
    ]
    city_conflicts = [item for item in needs_manual if item["city_conflict"]]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": str(source),
        "source_sha256": sha256_file(source),
        "sheet": info.selected_sheet,
        "task004r_task_id": old_task_id,
        "target_row_count": len(target_rows),
        "unique_raw_address_count": len(raw_all),
        "unique_qualified_address_count": len(qualified),
        "unique_origin_address_count": len(raw_origin),
        "unique_destination_address_count": len(raw_destination),
        "geocoded_unique_count": len(geocoded),
        "raw_level_distribution": dict(raw_levels),
        "canonical_level_distribution": dict(canonical_levels),
        "requested_level_counts": requested_level_counts,
        "formatted_address_distribution": dict(formatted_distribution),
        "endpoint_level_occurrence": dict(purpose_occurrence),
        "task004r_status_counts": dict(Counter(item["status"] for item in old_rows)),
        "old_low_precision_routes": {
            "total": len(old_low),
            "origin_low": origin_low,
            "destination_low": destination_low,
            "both_low": both_low,
        },
        "city_conflict_addresses": city_conflicts,
        "same_text_result_comparison": repeated_text_results,
        "same_text_different_result_count": sum(
            item["different_result"] for item in repeated_text_results
        ),
        "risk_counts": dict(risk_counts),
        "confirmation_status_counts": dict(status_counts),
        "possible_overstrict_cases": system_overstrict,
        "manual_review_cases": needs_manual,
        "projected_task005a": {
            "status_counts": dict(projected_status),
            "distance_count": sum(item.distance_km is not None for item in projected),
            "warning_count": sum(bool(item.warning_fields) for item in projected),
            "multi_destination_rows": [item.excel_row for item in projected if item.status == "多目的地待确认"],
            "blocked_rows": [item.excel_row for item in projected if item.status == "地址风险过高—未计算"],
            "city_conflict_rows": [item.excel_row for item in projected if item.status == "查询成功—地址冲突待确认"],
            "http_calls": 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "docs" / "evidence" / "TASK005A_ADDRESS_ANALYSIS.json"),
    )
    args = parser.parse_args()
    report = build_report()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(target),
        "target_rows": report["target_row_count"],
        "unique_qualified_addresses": report["unique_qualified_address_count"],
        "risk_counts": report["risk_counts"],
        "projected": report["projected_task005a"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
