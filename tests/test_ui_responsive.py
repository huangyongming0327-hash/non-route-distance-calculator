from __future__ import annotations

import os
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QSizePolicy

from src.amap.http_client import StandardLibraryTransport
from src.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def ui(app: QApplication, project_root: Path):
    with patch.object(
        StandardLibraryTransport,
        "get",
        autospec=True,
        side_effect=AssertionError("GUI 离线测试禁止真实 HTTP 调用"),
    ) as transport_get:
        window = MainWindow(project_root)
        window.resize(1366, 768)
        window.show()
        app.processEvents()
        yield window, transport_get
        window.close()
        app.processEvents()


def _show_tab(app: QApplication, window: MainWindow, index: int) -> None:
    window.tab_widget.setCurrentIndex(index)
    app.processEvents()


def test_main_window_is_created(ui) -> None:
    window, _ = ui
    assert window.windowTitle().startswith("非线路运距计算工具")
    assert window.centralWidget() is not None


def test_three_required_tabs_exist(ui) -> None:
    window, _ = ui
    assert window.tab_widget.count() == 3
    assert [window.tab_widget.tabText(index) for index in range(3)] == [
        "运距计算",
        "地址确认",
        "API与设置",
    ]


def test_calculation_page_has_primary_controls(app: QApplication, ui) -> None:
    window, _ = ui
    _show_tab(app, window, 0)
    required = (
        window.file_edit,
        window.output_edit,
        window.sheet_combo,
        window.header_spin,
        window.engine_combo,
        window.mode_combo,
        window.confirm_checkbox,
        window.preview_table,
        window.start_button,
        window.pause_button,
        window.resume_button,
        window.stop_button,
        window.progress_bar,
        window.open_result_button,
        window.open_folder_button,
        window.logs_button,
    )
    assert all(widget is not None for widget in required)
    assert set(window.mapping_boxes) == {
        "quote_type", "origin_city", "origin_address",
        "destination_city", "destination_address", "vehicle",
    }


def test_address_table_is_visible_and_expanding(app: QApplication, ui) -> None:
    window, _ = ui
    _show_tab(app, window, 1)
    assert window.address_table.isVisibleTo(window.address_page)
    assert window.address_table.rowCount() >= 8
    assert window.address_table.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert window.address_table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert window.address_table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded


def test_api_settings_page_has_required_controls(app: QApplication, ui) -> None:
    window, _ = ui
    _show_tab(app, window, 2)
    required = (
        window.key_edit,
        window.save_key_button,
        window.delete_key_button,
        window.test_key_button,
        window.key_state_label,
        window.driving_status_label,
        window.dev_checkbox,
        window.clear_cache_button,
    )
    assert all(widget is not None for widget in required)


def test_single_address_buttons_disabled_without_selection(app: QApplication, ui) -> None:
    window, _ = ui
    _show_tab(app, window, 1)
    window.address_table.clearSelection()
    window.address_table.setCurrentCell(-1, -1)
    app.processEvents()
    assert not any(button.isEnabled() for button in (
        window.reparse_address_button,
        window.use_original_address_button,
        window.use_formatted_address_button,
        window.save_corrected_address_button,
        window.confirm_address_button,
        window.invalid_address_button,
    ))


def test_single_address_buttons_enable_after_selection(app: QApplication, ui) -> None:
    window, _ = ui
    _show_tab(app, window, 1)
    window.address_table.selectRow(0)
    app.processEvents()
    assert all(button.isEnabled() for button in (
        window.reparse_address_button,
        window.use_original_address_button,
        window.use_formatted_address_button,
        window.save_corrected_address_button,
        window.confirm_address_button,
        window.invalid_address_button,
    ))


def test_import_confirmation_does_not_require_selection(app: QApplication, ui) -> None:
    window, _ = ui
    _show_tab(app, window, 1)
    window.address_table.clearSelection()
    window.address_table.setCurrentCell(-1, -1)
    app.processEvents()
    assert window.import_addresses_button.isEnabled()


@pytest.mark.parametrize(
    ("physical_width", "physical_height", "scale"),
    [
        (1366, 768, 1.00),
        (1366, 768, 1.25),
        (1920, 1080, 1.00),
        (1920, 1080, 1.25),
        (1920, 1080, 1.50),
    ],
)
def test_supported_screen_and_scale_layouts(
    app: QApplication,
    ui,
    physical_width: int,
    physical_height: int,
    scale: float,
) -> None:
    window, _ = ui
    logical_width = round(physical_width / scale)
    logical_height = round(physical_height / scale)
    window.showNormal()
    window.resize(logical_width, logical_height)
    _show_tab(app, window, 0)
    assert window.calculation_scroll.horizontalScrollBar().maximum() == 0
    required_warning_height = window.warning_label.heightForWidth(window.warning_label.width())
    assert window.warning_label.height() >= required_warning_height
    for combo in (*window.mapping_boxes.values(), window.engine_combo, window.mode_combo):
        assert combo.height() >= combo.sizeHint().height()

    _show_tab(app, window, 1)
    visible_rows = (
        window.address_table.viewport().height()
        // window.address_table.verticalHeader().defaultSectionSize()
    )
    assert visible_rows >= 8
    for button in (
        window.refresh_addresses_button,
        window.reparse_address_button,
        window.use_original_address_button,
        window.use_formatted_address_button,
        window.save_corrected_address_button,
        window.confirm_address_button,
        window.invalid_address_button,
        window.batch_confirm_button,
    ):
        top_left = button.mapTo(window.address_page, QPoint(0, 0))
        assert top_left.x() >= 0
        assert top_left.x() + button.width() <= window.address_page.width() + 1


def test_table_expands_at_1920x1080(app: QApplication, ui) -> None:
    window, _ = ui
    window.showNormal()
    window.resize(1366, 768)
    _show_tab(app, window, 1)
    small = window.address_table.size()
    window.resize(1920, 1080)
    app.processEvents()
    large = window.address_table.size()
    assert large.width() > small.width()
    assert large.height() > small.height()


def test_maximized_widgets_do_not_clip_text(app: QApplication, ui) -> None:
    window, _ = ui
    window.showMaximized()
    _show_tab(app, window, 0)
    for combo in (*window.mapping_boxes.values(), window.engine_combo, window.mode_combo):
        assert combo.height() >= combo.sizeHint().height()
    _show_tab(app, window, 1)
    for button in (
        window.refresh_addresses_button,
        window.reparse_address_button,
        window.use_original_address_button,
        window.use_formatted_address_button,
        window.save_corrected_address_button,
        window.confirm_address_button,
        window.invalid_address_button,
        window.batch_confirm_button,
    ):
        assert button.width() >= button.sizeHint().width()


def test_high_dpi_widgets_have_no_fixed_height_conflict(ui) -> None:
    window, _ = ui
    widgets = (
        *window.mapping_boxes.values(),
        window.engine_combo,
        window.mode_combo,
        window.key_edit,
        window.address_table,
        window.preview_table,
    )
    assert all(widget.minimumHeight() < widget.maximumHeight() for widget in widgets)


def test_original_excel_address_is_read_only_and_query_is_editable(ui) -> None:
    window, _ = ui
    assert window.address_table.rowCount() > 0
    original = window.address_table.item(0, 3)
    query = window.address_table.item(0, 10)
    assert not bool(original.flags() & Qt.ItemFlag.ItemIsEditable)
    assert bool(query.flags() & Qt.ItemFlag.ItemIsEditable)


def test_startup_and_tab_navigation_never_call_http(app: QApplication, ui) -> None:
    window, transport_get = ui
    for index in range(window.tab_widget.count()):
        _show_tab(app, window, index)
    assert transport_get.call_count == 0


def test_batch_script_can_smoke_start(project_root: Path) -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        ["cmd", "/c", str(project_root / "scripts" / "run_prototype.bat"), "--smoke-test"],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
