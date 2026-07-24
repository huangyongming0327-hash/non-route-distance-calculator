from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from src.ui.main_window import MainWindow
from src.domain.models import TaskMode


def test_main_window_loads_sample_and_requires_confirmation(project_root, sample_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(project_root)
    try:
        for _ in range(100):
            app.processEvents()
            if window.info is not None and window.address_records:
                break
            QTest.qWait(20)
        assert window.info is not None
        assert window.info.recommended_mapping.quote_type == 13
        assert window.start_button.isEnabled() is False
        assert window.mapping_boxes["vehicle"].itemData(0) is None
        assert window.mode_combo.findData(TaskMode.MOCK.value) == -1
        assert window.address_records
        assert len({item.address_id for item in window.address_records}) == len(window.address_records)
        assert window.address_table.columnCount() == 13
        assert window.export_addresses_button.text() == "导出待确认清单"
        window.confirm_checkbox.setChecked(True)
        app.processEvents()
        assert window.start_button.isEnabled() is True
    finally:
        window.close()
        for _ in range(100):
            app.processEvents()
            if not window.isVisible():
                break
            QTest.qWait(10)
