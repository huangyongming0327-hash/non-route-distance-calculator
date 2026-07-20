from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from src.application.processor import DRIVING_NOTICE
from src.domain.models import FieldMapping, ResultColumns, TaskMode
from src.utils.files import fingerprint, sha256_file
from src.validation.quote import is_target_quote
from src.workbook.preview import RESULT_HEADERS
from src.workbook.writeback import WARNING_MARKER_NAME


def _formula_snapshot(ws: Any, max_col: int = 16) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in ws.iter_rows(min_col=1, max_col=max_col):
        for cell in row:
            if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("=")):
                result[cell.coordinate] = str(cell.value)
    return result


def _value_formula_digest_payload(ws: Any, max_col: int = 16) -> list[list[Any]]:
    payload: list[list[Any]] = []
    for row in ws.iter_rows(min_col=1, max_col=max_col):
        for cell in row:
            if cell.value is not None:
                payload.append([cell.coordinate, str(cell.value), cell.data_type])
    return payload


def _conditional_ranges(ws: Any) -> dict[str, int]:
    return {str(item.sqref): len(ws.conditional_formatting[item]) for item in ws.conditional_formatting}


def _media(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {
            name: __import__("hashlib").sha256(archive.read(name)).hexdigest().upper()
            for name in archive.namelist()
            if name.lower().startswith("xl/media/") and name.lower().endswith((".jpg", ".jpeg"))
        }


def validate_prototype_output(
    source_path: str | Path,
    output_path: str | Path,
    *,
    sheet_name: str,
    header_row: int,
    fields: FieldMapping,
    results: ResultColumns,
    expected_source_fingerprint=None,
    mode: TaskMode = TaskMode.MOCK,
) -> dict[str, Any]:
    source_path = Path(source_path).resolve()
    output_path = Path(output_path).resolve()
    if expected_source_fingerprint is not None and fingerprint(source_path) != expected_source_fingerprint:
        raise AssertionError("源文件哈希/大小/修改时间发生变化")
    if not zipfile.is_zipfile(output_path):
        raise AssertionError("结果不是有效 OOXML ZIP")
    with zipfile.ZipFile(output_path) as archive:
        bad_member = archive.testzip()
        content_types = archive.read("[Content_Types].xml")
        macro_enabled = b"application/vnd.ms-excel.sheet.macroEnabled.main+xml" in content_types
    if bad_member or not macro_enabled:
        raise AssertionError(f"结果包损坏或并非真正 .xlsm：bad_member={bad_member}")

    source_book = load_workbook(source_path, read_only=False, data_only=False, keep_links=False)
    output_book = load_workbook(output_path, read_only=False, data_only=False, keep_vba=True, keep_links=False)
    try:
        source_ws = source_book[sheet_name]
        output_ws = output_book[sheet_name]
        target_rows = [
            row for row in range(header_row + 1, source_ws.max_row + 1)
            if is_target_quote(source_ws.cell(row, fields.quote_type).value)
        ]
        non_target_rows = [
            row for row in range(header_row + 1, source_ws.max_row + 1)
            if not is_target_quote(source_ws.cell(row, fields.quote_type).value)
        ]
        statuses = {row: output_ws.cell(row, results.status).value for row in target_rows}
        explanations = {row: output_ws.cell(row, results.explanation).value for row in target_rows}
        distances = {row: output_ws.cell(row, results.distance).value for row in target_rows}
        multi_rows = [row for row, status in statuses.items() if status == "多目的地待确认"]
        conflict_status = (
            "查询成功—地址冲突待确认"
            if mode == TaskMode.DRIVING_REAL
            else "模拟测试—地址冲突待确认"
        )
        conflict_rows = [row for row, status in statuses.items() if status == conflict_status]
        blank_address_rows = [row for row, status in statuses.items() if status == "地址为空"]
        cache_status = (
            "缓存复用—普通驾车参考"
            if mode == TaskMode.DRIVING_REAL
            else "缓存复用—模拟数据"
        )
        cache_rows = [row for row, status in statuses.items() if status == cache_status]
        headers = [output_ws.cell(header_row, col).value for col in results.as_dict().values()]
        non_target_written = [
            row for row in non_target_rows
            if any(output_ws.cell(row, col).value is not None for col in results.as_dict().values())
        ]
        protected_last_column = results.distance - 1
        source_formulas = _formula_snapshot(source_ws, protected_last_column)
        output_formulas = _formula_snapshot(output_ws, protected_last_column)
        dispimg = [cell for cell, formula in output_formulas.items() if "DISPIMG" in formula.upper()]
        source_cf = _conditional_ranges(source_ws)
        output_cf = _conditional_ranges(output_ws)
        defined_names = [item.name for item in output_book.defined_names.values()]
        tool_cf_count = 0
        tool_cf_formulas: list[str] = []
        for item in output_ws.conditional_formatting:
            for rule in output_ws.conditional_formatting[item]:
                if any(WARNING_MARKER_NAME in str(formula) for formula in (getattr(rule, "formula", None) or [])):
                    tool_cf_count += 1
                    tool_cf_formulas.extend(str(formula) for formula in (getattr(rule, "formula", None) or []))
        success_explanations = [
            explanations[row] for row, distance in distances.items() if distance is not None
        ]
        forbidden_text = (
            "货车查询成功", "货车可通行", "货车路线", "专业货车已开通", "车型未识别"
        )
        output_text = "\n".join(str(value or "") for value in (*statuses.values(), *explanations.values()))
        checks = {
            "valid_xlsm": macro_enabled and bad_member is None,
            "target_count_74": len(target_rows) == 74,
            "all_target_status_written": all(statuses.values()),
            "non_target_result_columns_untouched": not non_target_written,
            "multi_destination_row_248": multi_rows == [248] and distances.get(248) is None,
            "conflict_rows_39_78_272": conflict_rows == [39, 78, 272],
            "no_blank_address_in_sample": not blank_address_rows,
            "result_headers": headers == list(RESULT_HEADERS),
            "success_explanations_match_mode": all(
                isinstance(value, str)
                and (
                    DRIVING_NOTICE in value
                    if mode == TaskMode.DRIVING_REAL
                    else "模拟数据，不可用于正式业务" in value
                )
                for value in success_explanations
            ),
            "no_forbidden_truck_claims": not any(token in output_text for token in forbidden_text),
            "original_formulas_preserved": source_formulas == output_formulas,
            "formula_count_245": len(output_formulas) == 245,
            "dispimg_count_5": len(dispimg) == 5,
            "jpeg_count_2_and_preserved": len(_media(output_path)) == 2 and _media(source_path) == _media(output_path),
            "auto_filter_preserved": source_ws.auto_filter.ref == output_ws.auto_filter.ref,
            "hidden_rows_206_preserved": [r for r, d in source_ws.row_dimensions.items() if d.hidden]
            == [r for r, d in output_ws.row_dimensions.items() if d.hidden]
            and sum(bool(d.hidden) for d in output_ws.row_dimensions.values()) == 206,
            "original_conditional_format_ranges_preserved": all(
                output_cf.get(key, 0) >= count for key, count in source_cf.items()
            ) and sum(source_cf.values()) == 3,
            # Excel 会把公式相同且相邻的 E/F、G/H 规则合并为连续区域；
            # 5 条是 7 次 Add 调用的等价序列化结果。
            # 去掉车型规则后，Excel 会把 6 次 Add 合并序列化为 4 组区域规则。
            "tool_conditional_formatting_present": WARNING_MARKER_NAME in defined_names and tool_cf_count >= 4,
            "tool_conditional_formulas_bounded": all(
                not re.search(r"\$(?:R|S)\d{4,}", formula, flags=re.I) for formula in tool_cf_formulas
            ),
            "source_values_formulas_unchanged": _value_formula_digest_payload(
                source_ws, protected_last_column
            ) == _value_formula_digest_payload(output_ws, protected_last_column),
        }
        failed = [name for name, passed in checks.items() if not passed]
        return {
            "source": str(source_path), "output": str(output_path),
            "source_sha256": sha256_file(source_path), "output_sha256": sha256_file(output_path),
            "target_rows": target_rows, "target_count": len(target_rows),
            "distance_count": sum(value is not None for value in distances.values()),
            "multi_destination_rows": multi_rows, "conflict_rows": conflict_rows,
            "cache_reuse_rows": cache_rows, "cache_reuse_count": len(cache_rows),
            "formula_count": len(output_formulas), "dispimg_positions": dispimg,
            "jpeg_media": _media(output_path), "source_conditional_formatting": source_cf,
            "output_conditional_formatting": output_cf, "tool_cf_count": tool_cf_count,
            "checks": checks, "failed_checks": failed, "passed": not failed,
        }
    finally:
        source_book.close()
        output_book.close()


def write_validation_report(path: str | Path, report: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
