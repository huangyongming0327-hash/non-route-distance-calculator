from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

from openpyxl.utils import get_column_letter

from src.domain.models import FieldMapping, ResultColumns, RowOutcome
from src.office.process_safety import excel_session, wps_session
from src.utils.files import reject_xlm_macro_sheets
from src.workbook.writeback import write_results


XL_MACRO_ENABLED = 52


def _open(app: Any, path: Path, read_only: bool):
    return app.Workbooks.Open(
        str(path), UpdateLinks=0, ReadOnly=read_only,
        IgnoreReadOnlyRecommended=True, AddToMru=False,
    )


def write_job(app: Any, job: dict[str, Any]) -> dict[str, Any]:
    source = Path(job["source_path"]).resolve()
    output = Path(job["output_path"]).resolve()
    first_save = bool(job["first_save"])
    reject_xlm_macro_sheets(source)
    workbook = worksheet = None
    try:
        workbook = _open(app, source, False)
        worksheet = workbook.Worksheets(job["sheet_name"])
        mapping = FieldMapping(**job["field_mapping"])
        result_columns = ResultColumns(**job["result_columns"])
        outcomes = [RowOutcome(**item) for item in job["outcomes"]]
        write_audit = write_results(
            workbook, worksheet, int(job["header_row"]), mapping, result_columns,
            outcomes, int(job["last_data_row"]),
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        if first_save:
            workbook.SaveAs(str(output), FileFormat=XL_MACRO_ENABLED, AddToMru=False)
        else:
            workbook.Save()
        return {
            "operation": "SaveAs(FileFormat=52)" if first_save else "Workbook.Save()",
            "file_format": int(workbook.FileFormat), "full_name": str(workbook.FullName), **write_audit,
        }
    finally:
        if workbook is not None:
            workbook.Close(False)
        if worksheet is not None:
            del worksheet
        if workbook is not None:
            del workbook


def verify_job(app: Any, job: dict[str, Any]) -> dict[str, Any]:
    path = Path(job["source_path"]).resolve()
    workbook = worksheet = None
    try:
        workbook = _open(app, path, True)
        worksheet = workbook.Worksheets(job["sheet_name"])
        results = ResultColumns(**job["result_columns"])
        target_rows = [int(item) for item in job.get("target_rows", [])]
        conditional_display: dict[str, Any] = {}
        for address in job.get("warning_cells", []):
            cell = worksheet.Range(address)
            try:
                conditional_display[address] = {
                    "format_condition_count": int(cell.FormatConditions.Count),
                    "display_fill_color": int(cell.DisplayFormat.Interior.Color),
                    "display_font_color": int(cell.DisplayFormat.Font.Color),
                }
            except Exception as exc:
                conditional_display[address] = {
                    "format_condition_count": int(cell.FormatConditions.Count),
                    "display_format_error": repr(exc),
                }
            del cell
        return {
            "file_format": int(workbook.FileFormat),
            "sheet_count": int(workbook.Worksheets.Count),
            "used_range": str(worksheet.UsedRange.Address),
            "headers": [worksheet.Cells(int(job["header_row"]), col).Value2 for col in results.as_dict().values()],
            "distance_count": sum(worksheet.Cells(row, results.distance).Value2 is not None for row in target_rows),
            "status_count": sum(bool(worksheet.Cells(row, results.status).Value2) for row in target_rows),
            "explanation_count": sum(bool(worksheet.Cells(row, results.explanation).Value2) for row in target_rows),
            "formula_count": sum(
                isinstance(cell, str) and cell.startswith("=")
                for matrix_row in worksheet.Range(
                    f"A1:{get_column_letter(results.explanation)}{int(job['last_data_row'])}"
                ).Formula
                for cell in (matrix_row if isinstance(matrix_row, tuple) else (matrix_row,))
            ),
            "shape_count": int(worksheet.Shapes.Count),
            "defined_names": [str(workbook.Names(i).Name) for i in range(1, int(workbook.Names.Count) + 1)],
            "conditional_display": conditional_display,
        }
    finally:
        if workbook is not None:
            workbook.Close(False)
        if worksheet is not None:
            del worksheet
        if workbook is not None:
            del workbook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_file")
    parser.add_argument("response_file")
    args = parser.parse_args(argv)
    job = json.loads(Path(args.job_file).read_text(encoding="utf-8"))
    response: dict[str, Any] = {"ok": False, "job": job.get("operation"), "engine": job.get("engine")}
    try:
        action = write_job if job["operation"] == "write" else verify_job
        session = excel_session if job["engine"] == "excel" else wps_session
        result, audit = session(lambda app, _: action(app, job))
        # 即使后续安全断言拒绝结果，也先保留完整的前后进程审计。
        response.update({"result": result, "session": audit})
        if result is None:
            raise RuntimeError(audit.get("error", "Office 操作未返回结果"))
        if audit.get("own_pid_residual"):
            raise RuntimeError("本工具创建的 Office 进程未完全退出，结果未通过安全校验。")
        if not audit.get("preexisting_processes_unchanged", True):
            raise RuntimeError("检测到用户原有 Office 进程变化，结果未通过安全校验。")
        if job["engine"] == "wps" and not audit.get("preexisting_visible_windows_unchanged"):
            raise RuntimeError("检测到用户原有 WPS 可见窗口变化，结果未通过安全校验。")
        response.update({"ok": True})
    except Exception as exc:
        response.update({"error": repr(exc), "traceback": traceback.format_exc()})
    Path(args.response_file).write_text(json.dumps(response, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if not response["ok"]:
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    main()
