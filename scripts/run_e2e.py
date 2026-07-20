from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.application.runner import PrototypeRunner
from src.domain.models import OfficeEngine, TaskMode, WorkbookSelection
from src.utils.files import fingerprint
from src.workbook.preview import inspect_workbook
from src.workbook.verification import validate_prototype_output, write_validation_report


SOURCE_NAME = "副本26年6月干线账单 2.1-对账2.0-物流商(2).xlsx"


def run_engine(engine: OfficeEngine, checkpoint_batch: int, task_id: str | None = None, force_all: bool = True) -> dict:
    source = ROOT / "samples" / "input" / SOURCE_NAME
    before = fingerprint(source)
    info = inspect_workbook(source)
    selection = WorkbookSelection(str(source), info.selected_sheet, info.header_row, info.recommended_mapping)
    output_dir = ROOT / "samples" / "expected" / "prototype"
    output = output_dir / ("Excel_样表_模拟结果.xlsm" if engine == OfficeEngine.EXCEL else "WPS_样表_模拟结果.xlsm")
    runner = PrototypeRunner(ROOT)

    def progress(item) -> None:
        if item.stage.startswith("Office"):
            print(f"[{engine.value}] {item.stage}: 已处理 {item.processed}", flush=True)

    summary = runner.run(
        selection, engine=engine, mode=TaskMode.MOCK, output_dir=output_dir,
        final_path=output, task_id=task_id, force_all=force_all, progress=progress,
        checkpoint_batch=checkpoint_batch, checkpoint_seconds=60.0,
    )
    report = validate_prototype_output(
        source, output, sheet_name=info.selected_sheet, header_row=info.header_row,
        fields=info.recommended_mapping, results=info.result_columns,
        expected_source_fingerprint=before,
    )
    report["run_summary"] = summary.__dict__
    report_path = output_dir / f"{output.stem}_validation.json"
    write_validation_report(report_path, report)
    if not report["passed"]:
        raise RuntimeError(f"{engine.value} 端到端验收失败：{report['failed_checks']}")
    return {"summary": summary.__dict__, "validation": str(report_path), "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description="TASK-003B Excel/WPS 模拟端到端验证")
    parser.add_argument("engine", choices=("excel", "wps", "all"), default="all", nargs="?")
    parser.add_argument("--checkpoint-batch", type=int, default=10)
    parser.add_argument("--task-id", help="恢复既有 SQLite/partial 任务时使用")
    parser.add_argument("--resume", action="store_true", help="复用未变化的行结果并从保存水位继续")
    args = parser.parse_args()
    if args.resume and not args.task_id:
        parser.error("--resume 必须同时提供 --task-id")
    engines = [OfficeEngine.EXCEL, OfficeEngine.WPS] if args.engine == "all" else [OfficeEngine(args.engine)]
    results = [run_engine(engine, args.checkpoint_batch, args.task_id, not args.resume) for engine in engines]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
