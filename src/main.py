from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

_pyside_import_started = time.perf_counter()
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
_pyside_import_ms = (time.perf_counter() - _pyside_import_started) * 1000

from src.ui.main_window import MainWindow


def _startup_recorder(project_root: Path):
    log_path = project_root / "logs" / "startup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    session = datetime.now().astimezone().isoformat(timespec="seconds")

    def record(stage: str, elapsed_ms: float) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{session} | {stage} | {elapsed_ms:.2f} ms\n")

    return record


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    record_startup = _startup_recorder(project_root)
    record_startup("导入PySide6", _pyside_import_ms)
    # Qt 6 原生高 DPI 缩放；PassThrough 保留 Windows 125%/150% 等非整数缩放。
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    smoke_test = "--smoke-test" in sys.argv
    app = QApplication([arg for arg in sys.argv if arg != "--smoke-test"])
    app.setApplicationName("非线路运距计算工具 V1.0")
    app.setOrganizationName("内部工具")
    create_started = time.perf_counter()
    window = MainWindow(
        project_root,
        defer_initial_load=True,
        startup_recorder=record_startup,
    )
    record_startup("创建主窗口", (time.perf_counter() - create_started) * 1000)
    window.show()
    if smoke_test:
        QTimer.singleShot(50, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
