from __future__ import annotations

import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

_program_started = time.perf_counter()

_pyside_import_started = time.perf_counter()
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
_pyside_import_ms = (time.perf_counter() - _pyside_import_started) * 1000

from src import __version__
from src.ui.main_window import MainWindow
from src.runtime_paths import application_root, ensure_runtime_directories


def _startup_recorder(project_root: Path):
    log_path = project_root / "logs" / "startup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    session = datetime.now().astimezone().isoformat(timespec="seconds")

    def record(stage: str, elapsed_ms: float) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{session} | {stage} | {elapsed_ms:.2f} ms\n")

    return record


def _install_exception_logger(project_root: Path) -> None:
    crash_log = project_root / "logs" / "startup_error.log"

    def report(exc_type, exc_value, exc_traceback) -> None:
        crash_log.parent.mkdir(parents=True, exist_ok=True)
        with crash_log.open("a", encoding="utf-8") as handle:
            handle.write("\n" + datetime.now().astimezone().isoformat(timespec="seconds") + "\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=handle)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = report


def main() -> int:
    if "--office-worker" in sys.argv:
        from src.office.worker import main as office_worker_main

        marker = sys.argv.index("--office-worker")
        return office_worker_main(sys.argv[marker + 1 :])

    project_root = application_root()
    ensure_runtime_directories(project_root)
    _install_exception_logger(project_root)
    record_startup = _startup_recorder(project_root)
    record_startup("导入PySide6", _pyside_import_ms)
    record_startup("进入主程序", (time.perf_counter() - _program_started) * 1000)
    # Qt 6 原生高 DPI 缩放；PassThrough 保留 Windows 125%/150% 等非整数缩放。
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    smoke_test = "--smoke-test" in sys.argv
    app = QApplication([arg for arg in sys.argv if arg != "--smoke-test"])
    app.setApplicationName("非线路运距计算工具 V1.0")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("内部工具")
    create_started = time.perf_counter()
    window = MainWindow(
        project_root,
        defer_initial_load=True,
        startup_recorder=record_startup,
    )
    record_startup("创建主窗口", (time.perf_counter() - create_started) * 1000)
    window.show()
    QTimer.singleShot(
        0,
        lambda: record_startup("主窗口已显示", (time.perf_counter() - _program_started) * 1000),
    )
    if smoke_test:
        QTimer.singleShot(50, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
