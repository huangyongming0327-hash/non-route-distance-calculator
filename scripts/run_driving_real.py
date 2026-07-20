from __future__ import annotations

import argparse
from datetime import datetime
import json
from math import asin, cos, radians, sin, sqrt
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.amap.distance import meters_to_kilometers
from src.amap.driving_clients import (
    DRIVING_API_VERSION,
    DRIVING_MODE,
    RealDrivingRouter,
    test_connection,
)
from src.amap.http_client import AmapHttpClient, RealApiAuditLogger
from src.amap.real_clients import RealGeocoder
from src.application.processor import BusinessProcessor, DRIVING_NOTICE
from src.application.runner import PrototypeRunner
from src.cache.sqlite_cache import CacheRepository
from src.domain.models import OfficeEngine, RowInput, TaskMode, WorkbookSelection
from src.security.key_store import SecureKeyStore
from src.utils.files import fingerprint
from src.validation.address import CLEANER_VERSION
from src.workbook.preview import inspect_workbook
from src.workbook.verification import validate_prototype_output, write_validation_report


SOURCE_NAME = "副本26年6月干线账单 2.1-对账2.0-物流商(2).xlsx"
OUTPUT_DIR = ROOT / "samples" / "expected" / "driving_real"
EVIDENCE_DIR = ROOT / "docs" / "evidence"
ROUTES = (
    ("滁州", "滁州雷桥路2号元气森林", "杭州", "杭州萧山区瓜沥镇鸿达纺织库房"),
    ("苏州", "苏州太仓东仓北路与湖川塘路交汇", "南京", "南京江宁区融链云仓"),
    ("西安", "西安未央区达能饮料工厂西门", "深圳", "深圳石岩三江名创科技园"),
)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temporary, path)


def _http(log_name: str, *, max_attempts: int = 3) -> AmapHttpClient:
    key_store = SecureKeyStore(ROOT)
    if not key_store.get_key():
        raise RuntimeError("本机尚未安全保存高德 Web 服务 Key。")
    return AmapHttpClient(
        key_store,
        audit_logger=RealApiAuditLogger(ROOT / "logs" / "driving_real" / log_name / "http"),
        max_attempts=max_attempts,
    )


def run_connection() -> dict[str, Any]:
    http = _http("connection_validation", max_attempts=1)
    result = test_connection(http)
    report = {
        "tested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "api_version": DRIVING_API_VERSION,
        "key_valid": result.key_valid,
        "geocode_available": result.geocode_available,
        "driving_available": result.driving_available,
        "actual_http_calls": result.actual_calls,
        "message": result.message,
        "passed": (
            result.key_valid
            and result.geocode_available
            and result.driving_available
            and result.actual_calls <= 2
        ),
    }
    _write_json_atomic(EVIDENCE_DIR / "TASK004R_CONNECTION.json", report)
    return report


def _straight_line_km(origin: list[float], destination: list[float]) -> float:
    lon1, lat1 = map(radians, origin)
    lon2, lat2 = map(radians, destination)
    dlon, dlat = lon2 - lon1, lat2 - lat1
    term = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(term))


def run_small_routes() -> dict[str, Any]:
    http = _http("small_route_validation")
    geocoder = RealGeocoder(http, cleaner_version=CLEANER_VERSION, mode=DRIVING_MODE)
    router = RealDrivingRouter(http, cleaner_version=CLEANER_VERSION)
    route_reports: list[dict[str, Any]] = []
    with CacheRepository(ROOT / "cache" / "driving_real.sqlite") as repository:
        processor = BusinessProcessor(repository, geocoder=geocoder, router=router)
        for index, (origin_city, origin_address, destination_city, destination_address) in enumerate(ROUTES, start=1):
            outcome = processor.process_row(
                RowInput(
                    index + 1,
                    "非线路报价",
                    origin_city,
                    origin_address,
                    destination_city,
                    destination_address,
                    None,
                ),
                TaskMode.DRIVING_REAL,
                [item for route in ROUTES for item in (route[0], route[2])],
                force_route_refresh=True,
            )
            origin_coord = outcome.audit.get("origin_coordinate")
            destination_coord = outcome.audit.get("destination_coordinate")
            straight = (
                _straight_line_km(origin_coord, destination_coord)
                if isinstance(origin_coord, list) and isinstance(destination_coord, list)
                else None
            )
            distance = outcome.distance_km
            raw = outcome.audit.get("raw_distance_meters")
            conversion_ok = raw is not None and distance == meters_to_kilometers(raw)
            reasonable = bool(
                distance is not None
                and straight is not None
                and distance >= straight * 0.90
                and distance <= straight * 2.5 + 50
            )
            route_reports.append(
                {
                    "route_no": index,
                    "origin": origin_address,
                    "destination": destination_address,
                    "origin_formatted_address": outcome.audit.get("origin_formatted_address"),
                    "destination_formatted_address": outcome.audit.get("destination_formatted_address"),
                    "origin_geocode_level": outcome.audit.get("origin_geocode_level"),
                    "destination_geocode_level": outcome.audit.get("destination_geocode_level"),
                    "raw_distance_meters": raw,
                    "distance_km": distance,
                    "straight_line_km": round(straight, 1) if straight is not None else None,
                    "road_to_straight_ratio": round(distance / straight, 3) if distance and straight else None,
                    "status": outcome.status,
                    "explanation": outcome.explanation,
                    "conversion_ok": conversion_ok,
                    "reasonable_range_check": reasonable,
                    "returned_path_count": outcome.audit.get("route_path_count"),
                    "first_path_selected": outcome.audit.get("route_path_count", 0) >= 1,
                    "passed": bool(distance is not None and conversion_ok and reasonable and DRIVING_NOTICE in outcome.explanation),
                }
            )
    report = {
        "tested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "api_version": DRIVING_API_VERSION,
        "strategy": 32,
        "cartype": 0,
        "ferry": 1,
        "alternative_route": 1,
        "actual_http_calls": http.actual_calls,
        "routes": route_reports,
        "passed": len(route_reports) == 3 and all(item["passed"] for item in route_reports),
    }
    _write_json_atomic(EVIDENCE_DIR / "TASK004R_SMALL_ROUTES.json", report)
    return report


def run_office(engine: OfficeEngine) -> dict[str, Any]:
    source = ROOT / "samples" / "input" / SOURCE_NAME
    before = fingerprint(source)
    info = inspect_workbook(source)
    selection = WorkbookSelection(
        str(source), info.selected_sheet, info.header_row, info.recommended_mapping
    )
    output_name = (
        "Excel_样表_普通驾车距离结果_待验收.xlsm"
        if engine == OfficeEngine.EXCEL
        else "WPS_样表_普通驾车距离结果_待验收.xlsm"
    )
    output = OUTPUT_DIR / output_name
    task_id = f"task004r_{engine.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    summary = PrototypeRunner(ROOT).run(
        selection,
        engine=engine,
        mode=TaskMode.DRIVING_REAL,
        output_dir=OUTPUT_DIR,
        final_path=output,
        task_id=task_id,
        force_all=True,
        force_route_refresh=False,
        checkpoint_batch=10,
        checkpoint_seconds=60.0,
    )
    validation = validate_prototype_output(
        source,
        output,
        sheet_name=info.selected_sheet,
        header_row=info.header_row,
        fields=info.recommended_mapping,
        results=info.result_columns,
        expected_source_fingerprint=before,
        mode=TaskMode.DRIVING_REAL,
    )
    validation["run_summary"] = summary.__dict__
    report_path = EVIDENCE_DIR / f"TASK004R_{engine.value.upper()}_VALIDATION.json"
    write_validation_report(report_path, validation)
    if not validation["passed"]:
        raise RuntimeError(f"{engine.value} 正式输出验证失败：{validation['failed_checks']}")
    return {
        "engine": engine.value,
        "output": str(output),
        "validation": str(report_path),
        "summary": summary.__dict__,
        "passed": True,
    }


def validate_existing(engine: OfficeEngine) -> dict[str, Any]:
    source = ROOT / "samples" / "input" / SOURCE_NAME
    info = inspect_workbook(source)
    output = OUTPUT_DIR / (
        "Excel_样表_普通驾车距离结果_待验收.xlsm"
        if engine == OfficeEngine.EXCEL
        else "WPS_样表_普通驾车距离结果_待验收.xlsm"
    )
    report_path = EVIDENCE_DIR / f"TASK004R_{engine.value.upper()}_VALIDATION.json"
    prior = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    validation = validate_prototype_output(
        source,
        output,
        sheet_name=info.selected_sheet,
        header_row=info.header_row,
        fields=info.recommended_mapping,
        results=info.result_columns,
        expected_source_fingerprint=fingerprint(source),
        mode=TaskMode.DRIVING_REAL,
    )
    if "run_summary" in prior:
        validation["run_summary"] = prior["run_summary"]
    write_validation_report(report_path, validation)
    if not validation["passed"]:
        raise RuntimeError(f"{engine.value} 重新验证失败：{validation['failed_checks']}")
    return {"engine": engine.value, "output": str(output), "validation": str(report_path), "passed": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="TASK-004R 高德普通驾车真实联调")
    parser.add_argument(
        "phase",
        choices=("connection", "small", "excel", "wps", "validate-excel", "validate-wps", "all"),
        help="必须先 connection，再 small；small 通过后才能执行 Excel/WPS 批量。",
    )
    args = parser.parse_args()
    results: dict[str, Any] = {}
    if args.phase in {"connection", "all"}:
        results["connection"] = run_connection()
        if not results["connection"]["passed"]:
            raise SystemExit("连接测试未通过，已停止。")
    if args.phase in {"small", "all"}:
        results["small"] = run_small_routes()
        if not results["small"]["passed"]:
            raise SystemExit("3 条路线小范围测试未通过，已停止，不执行 74 行批量。")
    if args.phase in {"excel", "wps"}:
        small_path = EVIDENCE_DIR / "TASK004R_SMALL_ROUTES.json"
        if not small_path.exists() or not json.loads(small_path.read_text(encoding="utf-8")).get("passed"):
            raise SystemExit("缺少已通过的 3 条路线验证证据，拒绝批量。")
        results[args.phase] = run_office(OfficeEngine(args.phase))
    elif args.phase in {"validate-excel", "validate-wps"}:
        engine = OfficeEngine(args.phase.removeprefix("validate-"))
        results[args.phase] = validate_existing(engine)
    elif args.phase == "all":
        results["excel"] = run_office(OfficeEngine.EXCEL)
        results["wps"] = run_office(OfficeEngine.WPS)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
