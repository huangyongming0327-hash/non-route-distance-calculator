from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from oletools.olevba import VBA_Parser


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = "非线路运距计算工具"


def _macro_sources(path: Path) -> dict[str, str]:
    parser = VBA_Parser(str(path))
    try:
        return {
            filename: source.replace("\r\n", "\n")
            for _container, _stream, filename, source in parser.extract_macros()
        }
    finally:
        parser.close()


def _job(source: Path, output: Path, engine: str) -> dict:
    return {
        "operation": "write",
        "engine": engine,
        "source_path": str(source.resolve()),
        "output_path": str(output.resolve()),
        "first_save": True,
        "sheet_name": "MacroFixture",
        "header_row": 1,
        "field_mapping": {
            "quote_type": 1,
            "origin_city": 2,
            "origin_address": 3,
            "destination_city": 4,
            "destination_address": 5,
            "vehicle": 6,
        },
        "result_columns": {"distance": 27, "status": 28, "explanation": 29},
        "outcomes": [
            {
                "excel_row": 2,
                "distance_km": 12.3,
                "status": "缓存复用—普通驾车参考",
                "explanation": "普通驾车参考距离，不代表货车实际可通行路线。",
                "input_digest": "frozen-office-test",
                "cache_reused": True,
                "warning_fields": [],
                "audit": {},
            }
        ],
        "last_data_row": 2,
    }


def run_engine(exe: Path, engine: str, working: Path) -> dict:
    source = ROOT / "tests" / "fixtures" / "office_spike_macro_fixture.xlsm"
    local_source = working / f"{engine}_source.xlsm"
    output = working / f"{engine}_output.xlsm"
    job_path = working / f"{engine}_job.json"
    response_path = working / f"{engine}_response.json"
    shutil.copy2(source, local_source)
    job_path.write_text(
        json.dumps(_job(local_source, output, engine), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [str(exe), "--office-worker", str(job_path), str(response_path)],
        cwd=exe.parent,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if not response_path.exists():
        raise RuntimeError(
            f"{engine} 冻结辅助进程没有响应：rc={completed.returncode}, stderr={completed.stderr}"
        )
    response = json.loads(response_path.read_text(encoding="utf-8"))
    session = response.get("session", {})
    security = session.get("security_settings", {})
    checks = {
        "exit_code_zero": completed.returncode == 0,
        "response_ok": response.get("ok") is True,
        "valid_xlsm_format": response.get("result", {}).get("file_format") == 52,
        "vba_sources_preserved": _macro_sources(output) == _macro_sources(local_source),
        "automation_security_disabled": security.get("AutomationSecurity", {}).get("readback") == 3,
        "events_disabled": security.get("EnableEvents", {}).get("readback") is False,
        "own_process_released": session.get("own_pid_residual") is False,
        "preexisting_processes_unchanged": session.get("preexisting_processes_unchanged") is True,
    }
    if engine == "wps":
        checks["preexisting_windows_unchanged"] = (
            session.get("preexisting_visible_windows_unchanged") is True
        )
    return {
        "engine": engine,
        "output": str(output),
        "response": str(response_path),
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release-root",
        type=Path,
        default=ROOT / "release" / "非线路运距计算工具_V1.0",
    )
    args = parser.parse_args()
    exe = args.release_root.resolve() / f"{PRODUCT}.exe"
    if not exe.exists():
        raise FileNotFoundError(exe)
    working = ROOT / "temp" / "frozen_office_verification"
    if working.exists():
        shutil.rmtree(working)
    working.mkdir(parents=True)
    results = [run_engine(exe, engine, working) for engine in ("excel", "wps")]
    report = {
        "exe": str(exe),
        "results": results,
        "passed": all(item["passed"] for item in results),
    }
    evidence = ROOT / "docs" / "evidence" / "release" / "frozen_office_worker.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
