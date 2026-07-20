from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


OUTPUT = ROOT / "docs" / "evidence" / "ui_fix"


def _settle(app: QApplication) -> None:
    for _ in range(4):
        app.processEvents()


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    # offscreen 平台不会自动枚举 Windows 字体，仅为验收截图加载系统中文字体。
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc"
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app_font = app.font()
            app_font.setFamily(families[0])
            app.setFont(app_font)
    window = MainWindow(ROOT)
    window.show()
    _settle(app)

    pages = (
        (0, "calculation"),
        (1, "address_confirmation"),
        (2, "api_settings"),
    )
    audit: list[dict[str, object]] = []
    for width, height in ((1366, 768), (1920, 1080)):
        window.showNormal()
        window.resize(width, height)
        _settle(app)
        for index, suffix in pages:
            window.tab_widget.setCurrentIndex(index)
            if index == 0:
                window.calculation_scroll.verticalScrollBar().setValue(0)
            if index == 2:
                window.api_scroll.verticalScrollBar().setValue(0)
            _settle(app)
            target = OUTPUT / f"{width}x{height}_{suffix}.png"
            if not window.grab().save(str(target), "PNG"):
                raise RuntimeError(f"无法保存截图：{target}")
            audit.append(
                {
                    "file": target.name,
                    "window": [window.width(), window.height()],
                    "tab": window.tab_widget.tabText(index),
                    "calculation_vertical_scroll_max": (
                        window.calculation_scroll.verticalScrollBar().maximum()
                        if index == 0 else None
                    ),
                    "calculation_horizontal_scroll_max": (
                        window.calculation_scroll.horizontalScrollBar().maximum()
                        if index == 0 else None
                    ),
                    "address_rows": window.address_table.rowCount() if index == 1 else None,
                    "address_table_height": window.address_table.height() if index == 1 else None,
                    "address_visible_row_capacity": (
                        window.address_table.viewport().height()
                        // window.address_table.verticalHeader().defaultSectionSize()
                        if index == 1 else None
                    ),
                }
            )

    (OUTPUT / "layout_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
