from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.office.process_safety import excel_session, wps_session
from src.utils.files import sha256_file


OUTPUT_DIR = ROOT / "samples" / "expected" / "driving_real"
VISUAL_DIR = ROOT / "docs" / "evidence" / "visuals"
RANGES = {
    "top": "M1:S12",
    "conflict": "E35:S42",
    "multi_destination": "E244:S250",
}


def _image_meta(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        return {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "pixel_size": list(rgba.size),
            "rgba_pixel_sha256": hashlib.sha256(rgba.tobytes()).hexdigest().upper(),
        }


def _capture(label: str, path: Path, *, session_engine: str | None = None) -> dict[str, Any]:
    target_dir = VISUAL_DIR / label
    target_dir.mkdir(parents=True, exist_ok=True)

    def job(app: Any, _: dict[str, Any]) -> list[dict[str, Any]]:
        workbook = worksheet = None
        captures: list[dict[str, Any]] = []
        try:
            workbook = app.Workbooks.Open(
                str(path), UpdateLinks=0, ReadOnly=True,
                IgnoreReadOnlyRecommended=True, AddToMru=False,
            )
            worksheet = workbook.Worksheets(1)
            for label, address in RANGES.items():
                output = target_dir / f"{label}.png"
                chart_object = None
                try:
                    worksheet.Range(address).CopyPicture(1, 2)
                    chart_object = worksheet.ChartObjects().Add(0, 0, 1500, 520)
                    chart_object.Chart.Paste()
                    chart_object.Chart.Export(str(output))
                    captures.append({
                        "label": label, "range": address, "output": str(output),
                        "image": _image_meta(output),
                    })
                finally:
                    if chart_object is not None:
                        chart_object.Delete()
                        del chart_object
            return captures
        finally:
            if workbook is not None:
                workbook.Close(False)
            if worksheet is not None:
                del worksheet
            if workbook is not None:
                del workbook

    actual_engine = session_engine or label
    session = excel_session if actual_engine == "excel" else wps_session
    captures, audit = session(job)
    if captures is None or audit.get("own_pid_residual"):
        raise RuntimeError(f"{label} 视觉截图会话未安全完成：{audit}")
    return {
        "label": label, "render_engine": actual_engine, "path": str(path),
        "captures": captures, "session": audit,
    }


def main() -> None:
    files = {
        "excel": OUTPUT_DIR / "Excel_样表_普通驾车距离结果_待验收.xlsm",
        "wps": OUTPUT_DIR / "WPS_样表_普通驾车距离结果_待验收.xlsm",
    }
    report = {
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "files": {
            "excel_native": _capture("excel_native", files["excel"], session_engine="excel"),
            "excel_via_wps": _capture("excel_via_wps", files["excel"], session_engine="wps"),
            "wps_native": _capture("wps_native", files["wps"], session_engine="wps"),
        },
    }
    report_path = ROOT / "docs" / "evidence" / "TASK004R_VISUAL_CAPTURE.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        engine: [item["output"] for item in data["captures"]]
        for engine, data in report["files"].items()
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
