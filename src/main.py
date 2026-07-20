from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("非线路运距计算工具 V1.0")
    app.setOrganizationName("内部工具")
    window = MainWindow(Path(__file__).resolve().parents[1])
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
