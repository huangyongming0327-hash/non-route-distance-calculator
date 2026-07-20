from __future__ import annotations

import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import_started = time.perf_counter()
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import_ms = (time.perf_counter() - import_started) * 1000

from src.ui.main_window import MainWindow


def main() -> int:
    results: list[dict[str, object]] = [
        {"stage": "导入PySide6", "elapsed_ms": round(import_ms, 2)}
    ]

    def record(stage: str, elapsed_ms: float) -> None:
        results.append({"stage": stage, "elapsed_ms": round(elapsed_ms, 2)})

    app = QApplication.instance() or QApplication(sys.argv)
    create_started = time.perf_counter()
    window = MainWindow(ROOT, defer_initial_load=True, startup_recorder=record)
    record("创建主窗口", (time.perf_counter() - create_started) * 1000)

    show_started = time.perf_counter()
    window.show()
    app.processEvents()
    record("主窗口首次显示", (time.perf_counter() - show_started) * 1000)

    timeout_started = time.perf_counter()

    def finish_when_ready() -> None:
        stages = {str(item["stage"]) for item in results}
        if "加载地址清单" in stages:
            target = ROOT / "docs" / "evidence" / "ui_fix" / "startup_timing.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(results, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            window.close()
            app.quit()
            return
        if time.perf_counter() - timeout_started > 30:
            raise TimeoutError("启动阶段超过 30 秒")
        QTimer.singleShot(100, finish_when_ready)

    QTimer.singleShot(100, finish_when_ready)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
