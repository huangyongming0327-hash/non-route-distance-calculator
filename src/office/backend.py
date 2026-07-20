from __future__ import annotations

import json
import subprocess
import sys
import uuid
import winreg
from pathlib import Path
from typing import Any

from src.domain.models import FieldMapping, OfficeEngine, ResultColumns, RowOutcome


def engine_installed(engine: OfficeEngine) -> bool:
    progid = "Excel.Application" if engine == OfficeEngine.EXCEL else "KET.Application"
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r"\CLSID") as key:
            return bool(winreg.QueryValueEx(key, None)[0])
    except OSError:
        return False


class OfficeBackend:
    def __init__(self, engine: OfficeEngine, runtime_dir: str | Path, log_dir: str | Path) -> None:
        self.engine = engine
        self.runtime_dir = Path(runtime_dir)
        self.log_dir = Path(log_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if not engine_installed(engine):
            raise RuntimeError(f"未检测到 {engine.value} COM 注册，当前保存引擎不可用。")

    def _run_worker(self, payload: dict[str, Any], timeout: int = 240) -> dict[str, Any]:
        token = uuid.uuid4().hex
        job_path = self.runtime_dir / f"office_job_{token}.json"
        response_path = self.runtime_dir / f"office_response_{token}.json"
        payload["engine"] = self.engine.value
        job_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "-m", "src.office.worker", str(job_path), str(response_path)],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=timeout, shell=False,
        )
        if not response_path.exists():
            raise RuntimeError(f"Office 辅助进程未返回审计结果（退出码 {completed.returncode}）：{completed.stderr[-1000:]}")
        response = json.loads(response_path.read_text(encoding="utf-8"))
        audit_path = self.log_dir / f"{self.engine.value}_{payload['operation']}_{token}.json"
        audit_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
        if completed.returncode or not response.get("ok"):
            raise RuntimeError(f"{self.engine.value} Office 操作失败：{response.get('error', completed.stderr[-1000:])}")
        return response

    def write_checkpoint(
        self,
        *,
        source_path: str | Path,
        output_path: str | Path,
        first_save: bool,
        sheet_name: str,
        header_row: int,
        field_mapping: FieldMapping,
        result_columns: ResultColumns,
        outcomes: list[RowOutcome],
        last_data_row: int,
    ) -> dict[str, Any]:
        return self._run_worker(
            {
                "operation": "write", "source_path": str(Path(source_path).resolve()),
                "output_path": str(Path(output_path).resolve()), "first_save": first_save,
                "sheet_name": sheet_name, "header_row": header_row,
                "field_mapping": field_mapping.as_dict(), "result_columns": result_columns.as_dict(),
                "outcomes": [item.as_dict() for item in outcomes], "last_data_row": last_data_row,
            }
        )

    def verify(
        self,
        *,
        path: str | Path,
        sheet_name: str,
        header_row: int,
        result_columns: ResultColumns,
        target_rows: list[int],
        last_data_row: int,
        warning_cells: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._run_worker(
            {
                "operation": "verify", "source_path": str(Path(path).resolve()),
                "sheet_name": sheet_name, "header_row": header_row,
                "result_columns": result_columns.as_dict(), "target_rows": target_rows,
                "last_data_row": last_data_row, "warning_cells": warning_cells or [],
            }
        )
