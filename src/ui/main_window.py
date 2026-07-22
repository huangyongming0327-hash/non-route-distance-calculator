from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QCloseEvent, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.addressing.exchange import export_pending_addresses, import_confirmation_results
from src.addressing.service import AddressBookService, TRUSTED_STATUSES
from src.application.runner import PrototypeRunner
from src.amap.driving_clients import DRIVING_MODE, test_connection
from src.amap.errors import AmapApiError
from src.amap.http_client import AmapHttpClient, RealApiAuditLogger
from src.cache.sqlite_cache import CacheRepository
from src.cache.transfer import (
    export_driving_cache,
    export_trusted_addresses,
    import_driving_cache,
    import_trusted_addresses,
)
from src.domain.models import FieldMapping, OfficeEngine, TaskMode, WorkbookSelection
from src.office.backend import engine_installed
from src.performance import PerformanceLogger
from src.security.key_store import SecureKeyStore
from src.workbook.preview import (
    InspectionCancelled,
    WorkbookInfo,
    inspect_workbook_detailed,
    iter_row_inputs,
)
from src.amap.real_clients import RealGeocoder


FIELD_LABELS = {
    "quote_type": "报价类型",
    "origin_city": "始发城市",
    "origin_address": "始发详细地址",
    "destination_city": "目的城市",
    "destination_address": "目的详细地址",
    "vehicle": "车型（可选，不参与普通驾车距离计算）",
}


def _ui_normalized_path(path: str | Path) -> str:
    """只做词法规范化，避免 GUI 线程为网络路径执行文件系统解析。"""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


class RunWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress_changed = Signal(object)

    def __init__(self, runner: PrototypeRunner, selection: WorkbookSelection, options: dict) -> None:
        super().__init__()
        self.runner = runner
        self.selection = selection
        self.options = options

    @Slot()
    def run(self) -> None:
        try:
            summary = self.runner.run(
                self.selection, progress=self.progress_changed.emit, **self.options
            )
            self.finished.emit(summary)
        except Exception as exc:
            self.failed.emit(str(exc))


class WorkbookInspectWorker(QObject):
    finished = Signal(int, object, bool)
    failed = Signal(int, str)
    cancelled = Signal(int)
    progress_changed = Signal(int, str)

    def __init__(
        self,
        request_id: int,
        path: Path,
        sheet_name: str | None,
        header_row: int | None,
        cache_dir: Path,
        performance_logger: PerformanceLogger,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.path = path
        self.sheet_name = sheet_name
        self.header_row = header_row
        self.cache_dir = cache_dir
        self.performance_logger = performance_logger
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def _record_timing(
        self, stage: str, elapsed_ms: float, status: str, details: dict
    ) -> None:
        self.performance_logger.record(
            f"工作簿检测#{self.request_id}", stage, elapsed_ms, status=status, details=details
        )

    @Slot()
    def run(self) -> None:
        started = time.perf_counter()
        try:
            outcome = inspect_workbook_detailed(
                self.path,
                self.sheet_name,
                self.header_row,
                cache_dir=self.cache_dir,
                cancel_event=self.cancel_event,
                progress=lambda text: self.progress_changed.emit(self.request_id, text),
                timing=self._record_timing,
            )
            self.performance_logger.record(
                f"工作簿检测#{self.request_id}",
                "检测总计",
                (time.perf_counter() - started) * 1000,
                details={"file": self.path.name, "cache_hit": outcome.cache_hit},
            )
            self.finished.emit(self.request_id, outcome.info, outcome.cache_hit)
        except InspectionCancelled:
            self.performance_logger.record(
                f"工作簿检测#{self.request_id}",
                "检测总计",
                (time.perf_counter() - started) * 1000,
                status="cancelled",
                details={"file": self.path.name},
            )
            self.cancelled.emit(self.request_id)
        except Exception as exc:
            self.performance_logger.record(
                f"工作簿检测#{self.request_id}",
                "检测总计",
                (time.perf_counter() - started) * 1000,
                status="failed",
                details={"file": self.path.name, "error_type": type(exc).__name__},
            )
            self.failed.emit(self.request_id, str(exc))


class OutputPermissionWorker(QObject):
    finished = Signal(int, str, str)

    def __init__(
        self,
        request_id: int,
        path: str,
        performance_logger: PerformanceLogger,
        *,
        timeout_seconds: float = 3.0,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.path = path
        self.performance_logger = performance_logger
        self.timeout_seconds = timeout_seconds

    def _probe(self) -> tuple[str, str]:
        directory = Path(self.path)
        if not directory.exists():
            return "missing", "目录不存在"
        if not directory.is_dir():
            return "invalid", "所选路径不是目录"
        probe = directory / f".task007a_write_probe_{uuid.uuid4().hex}.tmp"
        try:
            descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            os.close(descriptor)
            return "writable", "可写"
        except PermissionError:
            return "denied", "无写入权限"
        except OSError as exc:
            return "error", f"权限检查失败：{exc}"
        finally:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass

    @Slot()
    def run(self) -> None:
        started = time.perf_counter()
        result: list[tuple[str, str]] = []

        def probe() -> None:
            result.append(self._probe())

        # 系统文件调用可能被慢磁盘或网络目录挂起；用守护线程隔离并在超时后恢复 UI。
        probe_thread = threading.Thread(target=probe, daemon=True, name="output-permission-probe")
        probe_thread.start()
        probe_thread.join(self.timeout_seconds)
        if probe_thread.is_alive():
            status, message = "timeout", f"写入权限检查超过 {self.timeout_seconds:g} 秒，已停止等待"
        else:
            status, message = result[0] if result else ("error", "权限检查未返回结果")
        self.performance_logger.record(
            f"输出目录检查#{self.request_id}",
            "输出目录权限检查",
            (time.perf_counter() - started) * 1000,
            status=status,
            details={"directory_name": Path(self.path).name},
        )
        self.finished.emit(self.request_id, status, message)


class AddressRefreshWorker(QObject):
    finished = Signal(int, object, object, bool)
    failed = Signal(int, str)

    def __init__(
        self,
        request_id: int,
        root: Path,
        selection: WorkbookSelection | None,
        city_catalog: tuple[str, ...],
        performance_logger: PerformanceLogger,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.root = root
        self.selection = selection
        self.city_catalog = city_catalog
        self.performance_logger = performance_logger

    @Slot()
    def run(self) -> None:
        repository = None
        overall_started = time.perf_counter()
        try:
            sqlite_started = time.perf_counter()
            repository = CacheRepository(self.root / "cache" / "driving_real.sqlite")
            self.performance_logger.record(
                f"地址清单#{self.request_id}",
                "SQLite加载",
                (time.perf_counter() - sqlite_started) * 1000,
            )
            usage = {}
            if self.selection is not None:
                http = AmapHttpClient(
                    SecureKeyStore(self.root),
                    audit_logger=RealApiAuditLogger(
                        self.root / "logs" / "address_confirmation" / "http"
                    ),
                    max_attempts=3,
                )
                service = AddressBookService(
                    repository, geocoder=RealGeocoder(http, mode=DRIVING_MODE)
                )
                usage_started = time.perf_counter()
                _, usage = service.sync_rows(
                    iter_row_inputs(self.selection), self.city_catalog
                )
                self.performance_logger.record(
                    f"地址清单#{self.request_id}",
                    "后台同步工作簿地址",
                    (time.perf_counter() - usage_started) * 1000,
                    details={"file": Path(self.selection.path).name},
                )
            records = repository.list_addresses()
            self.performance_logger.record(
                f"地址清单#{self.request_id}",
                "地址清单总计",
                (time.perf_counter() - overall_started) * 1000,
                details={"record_count": len(records)},
            )
            self.finished.emit(
                self.request_id, records, usage, self.selection is not None
            )
        except Exception as exc:
            self.failed.emit(self.request_id, str(exc))
        finally:
            if repository:
                repository.close()


class MainWindow(QMainWindow):
    def __init__(
        self,
        project_root: str | Path,
        *,
        defer_initial_load: bool = False,
        startup_recorder: Callable[[str, float], None] | None = None,
    ) -> None:
        super().__init__()
        self.root = Path(project_root).resolve()
        self.performance_logger = PerformanceLogger(self.root / "logs" / "performance_task007a.jsonl")
        self.startup_recorder = startup_recorder
        self.startup_timings: list[tuple[str, float]] = []
        self.runner: PrototypeRunner | None = None
        self.worker_thread: QThread | None = None
        self.worker: RunWorker | None = None
        self.startup_thread: QThread | None = None
        self.startup_worker: WorkbookInspectWorker | None = None
        self.inspection_request_sequence = 0
        self.latest_inspection_request_id = 0
        self.active_inspection_request: dict | None = None
        self.pending_inspection_request: dict | None = None
        self.last_inspection_error: tuple[str, str] | None = None
        self.startup_workbook_started = 0.0
        self.pending_inspection_stage = "读取工作簿"
        self.pending_refresh_addresses = True
        self.close_when_startup_done = False
        self.close_when_background_done = False
        self.output_permission_thread: QThread | None = None
        self.output_permission_worker: OutputPermissionWorker | None = None
        self.output_permission_request_id = 0
        self.latest_output_permission_request_id = 0
        self.pending_output_permission_path: str | None = None
        self.address_refresh_thread: QThread | None = None
        self.address_refresh_worker: AddressRefreshWorker | None = None
        self.address_refresh_request_id = 0
        self.latest_address_refresh_request_id = 0
        self.pending_address_refresh = False
        self.pending_address_sync_workbook = False
        self.address_refresh_started = 0.0
        self.address_refresh_record_startup = False
        self.info: WorkbookInfo | None = None
        self.last_output: Path | None = None
        self.close_when_done = False
        self.mapping_boxes: dict[str, QComboBox] = {}
        self.address_records = []
        self.address_usage = {}
        self.output_manually_selected = False
        self.key_store = SecureKeyStore(self.root)
        self.setWindowTitle("非线路运距计算工具 V1.0 — 高德普通驾车距离版")
        self.resize(1200, 820)
        self.setMinimumSize(780, 560)
        self._build_ui()
        self._wire_events()
        if defer_initial_load:
            QTimer.singleShot(120, self._initialize_after_show)
        else:
            self._initialize_synchronously()

    def _record_startup_timing(self, stage: str, elapsed_ms: float) -> None:
        elapsed_ms = round(elapsed_ms, 2)
        self.startup_timings.append((stage, elapsed_ms))
        if self.startup_recorder:
            self.startup_recorder(stage, elapsed_ms)

    def _measure_startup(self, stage: str, action: Callable[[], object]) -> object:
        started = time.perf_counter()
        try:
            return action()
        finally:
            self._record_startup_timing(stage, (time.perf_counter() - started) * 1000)

    def _initialize_synchronously(self) -> None:
        self._measure_startup("加载配置", self._refresh_key_state)
        self._measure_startup("检测Excel/WPS", self._refresh_office_engines)
        self._measure_startup(
            "加载默认工作簿", lambda: self._load_default_sample(refresh_addresses=False)
        )
        self._refresh_address_table(record_startup=True)

    @Slot()
    def _initialize_after_show(self) -> None:
        """将非必要启动工作放到首帧显示后，不启动 Office 也不调用 API。"""
        self._measure_startup("加载配置", self._refresh_key_state)
        QTimer.singleShot(0, self._initialize_office_after_show)

    @Slot()
    def _initialize_office_after_show(self) -> None:
        self._measure_startup("检测Excel/WPS", self._refresh_office_engines)
        self._record_startup_timing("等待用户选择工作簿", 0.0)
        self.summary_label.setText("启动完成。请选择 Excel 文件，程序将在选择后读取工作表和字段。")
        QTimer.singleShot(0, lambda: self._refresh_address_table(record_startup=True))

    @Slot()
    def _initialize_workbook_after_show(self) -> None:
        sample = self._default_sample()
        if sample is None:
            self._record_startup_timing("加载默认工作簿", 0.0)
            QTimer.singleShot(0, lambda: self._refresh_address_table(record_startup=True))
            return
        self.file_edit.setText(str(sample))
        self._start_workbook_inspection(
            sample,
            stage="加载默认工作簿",
            refresh_addresses=False,
        )

    def _start_workbook_inspection(
        self,
        path: Path,
        *,
        sheet_name: str | None = None,
        header_row: int | None = None,
        stage: str = "读取用户工作簿",
        refresh_addresses: bool = True,
    ) -> None:
        source = Path(_ui_normalized_path(path))
        active = self.active_inspection_request
        if active and (
            active["path"] == source
            and active["sheet_name"] == sheet_name
            and active["header_row"] == header_row
        ):
            self.performance_logger.record(
                f"工作簿检测#{active['id']}", "阻止重复检测", 0, status="ignored"
            )
            return
        self.inspection_request_sequence += 1
        request = {
            "id": self.inspection_request_sequence,
            "path": source,
            "sheet_name": sheet_name,
            "header_row": header_row,
            "stage": stage,
            "refresh_addresses": refresh_addresses,
        }
        self.latest_inspection_request_id = request["id"]
        if self.startup_thread and self.startup_thread.isRunning():
            self.pending_inspection_request = request
            if self.startup_worker:
                self.startup_worker.cancel()
            self.detection_status_label.setText("正在取消旧检测，随后读取新文件…")
            self.cancel_detect_button.setEnabled(True)
            return
        self._launch_workbook_inspection(request)

    def _launch_workbook_inspection(self, request: dict) -> None:
        self.active_inspection_request = request
        self.pending_inspection_stage = request["stage"]
        self.pending_refresh_addresses = request["refresh_addresses"]
        self.startup_workbook_started = time.perf_counter()
        self.detection_status_label.setText("正在读取工作表")
        self._set_inspection_busy(True)
        self.startup_thread = QThread(self)
        self.startup_worker = WorkbookInspectWorker(
            request["id"],
            request["path"],
            request["sheet_name"],
            request["header_row"],
            self.root / "cache" / "workbook_detection",
            self.performance_logger,
        )
        self.startup_worker.moveToThread(self.startup_thread)
        self.startup_thread.started.connect(self.startup_worker.run)
        self.startup_worker.finished.connect(self._startup_workbook_loaded)
        self.startup_worker.failed.connect(self._startup_workbook_failed)
        self.startup_worker.cancelled.connect(self._startup_workbook_cancelled)
        self.startup_worker.progress_changed.connect(self._inspection_progress)
        self.startup_worker.finished.connect(self.startup_thread.quit)
        self.startup_worker.failed.connect(self.startup_thread.quit)
        self.startup_worker.cancelled.connect(self.startup_thread.quit)
        self.startup_thread.finished.connect(self._startup_thread_finished)
        self.startup_thread.start()

    def _set_inspection_busy(self, busy: bool) -> None:
        self.detect_button.setEnabled(not busy and bool(self.file_edit.text().strip()))
        self.detect_button.setText("检测中…" if busy else "自动检测表头/字段")
        self.cancel_detect_button.setEnabled(busy)
        self.sheet_combo.setEnabled(not busy)

    @Slot()
    def _cancel_workbook_inspection(self) -> None:
        self.pending_inspection_request = None
        self.latest_inspection_request_id += 1
        if self.startup_worker:
            self.startup_worker.cancel()
            self.detection_status_label.setText("正在取消当前检测…")

    @Slot(int, str)
    def _inspection_progress(self, request_id: int, text: str) -> None:
        if request_id == self.latest_inspection_request_id:
            self.detection_status_label.setText(text)

    @Slot(int, object, bool)
    def _startup_workbook_loaded(
        self, request_id: int, info: WorkbookInfo, cache_hit: bool
    ) -> None:
        self._record_startup_timing(
            self.pending_inspection_stage,
            (time.perf_counter() - self.startup_workbook_started) * 1000,
        )
        if request_id != self.latest_inspection_request_id:
            return
        try:
            current_path = _ui_normalized_path(self.file_edit.text())
        except OSError:
            return
        if current_path != _ui_normalized_path(info.path):
            return
        self.last_inspection_error = None
        self._apply_workbook_info(
            info,
            refresh_addresses=self.pending_refresh_addresses,
        )
        source = "检测缓存" if cache_hit else "只读 OOXML"
        self.detection_status_label.setText(
            f"检测完成（{source}）：工作表“{info.selected_sheet}”，表头第 {info.header_row} 行"
        )

    @Slot(int, str)
    def _startup_workbook_failed(self, request_id: int, message: str) -> None:
        self._record_startup_timing(
            self.pending_inspection_stage,
            (time.perf_counter() - self.startup_workbook_started) * 1000,
        )
        if request_id != self.latest_inspection_request_id:
            return
        self.detection_status_label.setText(f"检测失败：{message}")
        error_key = (self.file_edit.text(), message)
        if error_key != self.last_inspection_error:
            self.last_inspection_error = error_key
            QMessageBox.warning(self, "无法读取工作簿", message)

    @Slot(int)
    def _startup_workbook_cancelled(self, request_id: int) -> None:
        if request_id == self.latest_inspection_request_id:
            self.detection_status_label.setText("检测已取消。")

    @Slot()
    def _startup_thread_finished(self) -> None:
        if self.startup_worker:
            self.startup_worker.deleteLater()
        if self.startup_thread:
            self.startup_thread.deleteLater()
        self.startup_worker = None
        self.startup_thread = None
        self.active_inspection_request = None
        pending = self.pending_inspection_request
        self.pending_inspection_request = None
        if pending:
            self._launch_workbook_inspection(pending)
            return
        self._set_inspection_busy(False)
        if self.close_when_startup_done:
            self.close()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("main_tabs")
        root_layout.addWidget(self.tab_widget)
        self._build_calculation_page()
        self._build_address_page()
        self._build_api_page()
        self.setCentralWidget(central)
        self._set_running(False)
        self._update_address_actions()

    @staticmethod
    def _configure_form_layout(layout: QFormLayout) -> None:
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    @staticmethod
    def _make_scroll_page(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _set_expanding(widget: QWidget) -> None:
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def _build_calculation_page(self) -> None:
        content = QWidget()
        page_layout = QVBoxLayout(content)
        page_layout.setContentsMargins(8, 8, 8, 8)

        self.warning_label = QLabel("普通驾车参考距离，不代表货车实际可通行路线")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet(
            "QLabel { color:#7a5200; background:#fff4ce; border:2px solid #d6a100; "
            "font-weight:700; padding:8px; }"
        )
        self.warning_label.setAlignment(QtAlignmentCenter)
        page_layout.addWidget(self.warning_label)

        file_group = QGroupBox("1. 工作簿与输出")
        file_grid = QGridLayout(file_group)
        self.file_edit = QLineEdit()
        self.select_button = QPushButton("选择 Excel 文件")
        self.output_edit = QLineEdit(str(self.root / "outputs"))
        self.output_button = QPushButton("选择输出目录")
        self.output_status_label = QLabel("输出目录：尚未检查")
        self.output_status_label.setWordWrap(True)
        self.sheet_combo = QComboBox()
        self.header_spin = QSpinBox()
        self.header_spin.setRange(1, 1000)
        self.detect_button = QPushButton("自动检测表头/字段")
        self.cancel_detect_button = QPushButton("取消当前检测")
        self.cancel_detect_button.setEnabled(False)
        self.detection_status_label = QLabel("工作簿检测：待开始")
        self.detection_status_label.setWordWrap(True)
        for widget in (self.file_edit, self.output_edit, self.sheet_combo):
            self._set_expanding(widget)
        file_grid.setColumnStretch(1, 1)
        file_grid.addWidget(QLabel("输入文件"), 0, 0)
        file_grid.addWidget(self.file_edit, 0, 1)
        file_grid.addWidget(self.select_button, 0, 2)
        file_grid.addWidget(QLabel("输出目录"), 1, 0)
        file_grid.addWidget(self.output_edit, 1, 1)
        file_grid.addWidget(self.output_button, 1, 2)
        file_grid.addWidget(self.output_status_label, 2, 1, 1, 3)
        file_grid.addWidget(QLabel("工作表"), 3, 0)
        file_grid.addWidget(self.sheet_combo, 3, 1)
        file_grid.addWidget(QLabel("表头行"), 4, 0)
        file_grid.addWidget(self.header_spin, 4, 1)
        file_grid.addWidget(self.detect_button, 4, 2)
        file_grid.addWidget(self.cancel_detect_button, 4, 3)
        file_grid.addWidget(self.detection_status_label, 5, 1, 1, 3)
        page_layout.addWidget(file_group)

        mapping_group = QGroupBox("2. 字段映射（列字母｜表头｜样例内容）")
        mapping_layout = QFormLayout(mapping_group)
        self._configure_form_layout(mapping_layout)
        for key, label in FIELD_LABELS.items():
            box = QComboBox()
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(24)
            self._set_expanding(box)
            self.mapping_boxes[key] = box
            mapping_layout.addRow(label, box)
        page_layout.addWidget(mapping_group)

        settings_group = QGroupBox("3. 运行设置")
        settings_layout = QFormLayout(settings_group)
        self._configure_form_layout(settings_layout)
        self.engine_combo = QComboBox()
        for engine, label in ((OfficeEngine.EXCEL, "Microsoft Excel"), (OfficeEngine.WPS, "WPS 表格（实验性隔离）")):
            self.engine_combo.addItem(f"{label}｜等待检测", engine.value)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("普通驾车正式计算：高德地理编码 + v5 驾车路线", TaskMode.DRIVING_REAL.value)
        self.mode_combo.addItem("仅本地校验：不生成距离", TaskMode.LOCAL_VALIDATION.value)
        self.force_refresh_checkbox = QCheckBox("强制重新查询全部非线路报价（忽略普通驾车路线缓存）")
        self.confirm_checkbox = QCheckBox("我已确认字段映射，并知悉普通驾车距离仅作非线路报价参考")
        self.summary_label = QLabel("请选择工作簿并确认字段。")
        self.summary_label.setWordWrap(True)
        self.confirm_checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.force_refresh_checkbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._set_expanding(self.engine_combo)
        self._set_expanding(self.mode_combo)
        settings_layout.addRow("保存引擎", self.engine_combo)
        settings_layout.addRow("运行模式", self.mode_combo)
        settings_layout.addRow(self.force_refresh_checkbox)
        settings_layout.addRow(self.confirm_checkbox)
        settings_layout.addRow("运行前摘要", self.summary_label)
        page_layout.addWidget(settings_group)

        preview_group = QGroupBox("4. 前 10 行只读预览")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setObjectName("calculation_preview_table")
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.preview_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.preview_table.setMinimumHeight(240)
        self.preview_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.preview_table)
        page_layout.addWidget(preview_group)

        progress_group = QGroupBox("5. 处理进度")
        progress_layout = QGridLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.stage_label = QLabel("待开始")
        self.counter_label = QLabel("目标 0｜已处理 0｜警告 0｜缓存复用 0")
        self.stage_label.setWordWrap(True)
        self.counter_label.setWordWrap(True)
        progress_layout.addWidget(self.progress_bar, 0, 0, 1, 4)
        progress_layout.addWidget(self.stage_label, 1, 0, 1, 2)
        progress_layout.addWidget(self.counter_label, 1, 2, 1, 2)
        page_layout.addWidget(progress_group)

        action_group = QGroupBox("任务与结果")
        action_layout = QGridLayout(action_group)
        self.start_button = QPushButton("开始处理")
        self.pause_button = QPushButton("暂停")
        self.resume_button = QPushButton("继续")
        self.stop_button = QPushButton("停止")
        self.open_result_button = QPushButton("打开结果")
        self.open_folder_button = QPushButton("打开结果文件夹")
        self.logs_button = QPushButton("查看日志")
        action_buttons = (
            self.start_button, self.pause_button, self.resume_button, self.stop_button,
            self.open_result_button, self.open_folder_button, self.logs_button,
        )
        for index, button in enumerate(action_buttons):
            action_layout.addWidget(button, index // 4, index % 4)
        for column in range(4):
            action_layout.setColumnStretch(column, 1)
        page_layout.addWidget(action_group)
        page_layout.addStretch(1)

        self.calculation_scroll = self._make_scroll_page(content)
        self.calculation_scroll.setObjectName("calculation_page")
        self.tab_widget.addTab(self.calculation_scroll, "运距计算")

    def _build_address_page(self) -> None:
        self.address_page = QWidget()
        address_layout = QVBoxLayout(self.address_page)
        address_layout.setContentsMargins(8, 8, 8, 8)

        address_title = QLabel("唯一地址确认：原 Excel 城市和详细地址始终只读，仅修改用于查询的地址。")
        address_title.setWordWrap(True)
        address_title.setStyleSheet("QLabel { color:#264653; background:#eef7f8; padding:6px; }")
        address_layout.addWidget(address_title)

        address_tools = QGridLayout()
        self.refresh_addresses_button = QPushButton("刷新唯一地址清单")
        self.reparse_address_button = QPushButton("重新解析当前地址")
        self.use_original_address_button = QPushButton("使用原始地址")
        self.use_formatted_address_button = QPushButton("使用高德标准地址")
        self.save_corrected_address_button = QPushButton("保存修正地址")
        self.confirm_address_button = QPushButton("确认定位正确")
        self.invalid_address_button = QPushButton("标记地址无效")
        self.batch_confirm_button = QPushButton("批量确认高可信地址")
        toolbar_buttons = (
            self.refresh_addresses_button, self.reparse_address_button,
            self.use_original_address_button, self.use_formatted_address_button,
            self.save_corrected_address_button, self.confirm_address_button,
            self.invalid_address_button, self.batch_confirm_button,
        )
        for index, button in enumerate(toolbar_buttons):
            address_tools.addWidget(button, index // 4, index % 4)
        self.refresh_addresses_button.setToolTip("重新读取当前可信地址库和所选工作簿中的唯一地址。")
        self.reparse_address_button.setToolTip("使用当前查询地址重新获取高德坐标。")
        self.use_original_address_button.setToolTip("将查询地址恢复为原 Excel 地址，不修改原 Excel。")
        self.use_formatted_address_button.setToolTip("将查询地址改为高德返回的标准地址。")
        self.save_corrected_address_button.setToolTip("保存修正后的查询地址；不会修改原 Excel。")
        self.confirm_address_button.setToolTip("人工认可当前标准地址和坐标。")
        self.invalid_address_button.setToolTip("阻止该地址自动计算。")
        self.batch_confirm_button.setToolTip("仅确认系统判定为高可信的地址。")
        for column in range(4):
            address_tools.setColumnStretch(column, 1)
        address_layout.addLayout(address_tools)

        address_exchange = QGridLayout()
        self.only_unconfirmed_checkbox = QCheckBox("仅查看未确认")
        self.export_addresses_button = QPushButton("导出待确认清单")
        self.import_addresses_button = QPushButton("导入确认结果")
        self.address_summary_label = QLabel("尚未加载唯一地址。")
        self.address_summary_label.setWordWrap(True)
        address_exchange.addWidget(self.only_unconfirmed_checkbox, 0, 0)
        address_exchange.addWidget(self.export_addresses_button, 0, 1)
        address_exchange.addWidget(self.import_addresses_button, 0, 2)
        address_exchange.addWidget(self.address_summary_label, 1, 0, 1, 3)
        address_exchange.setColumnStretch(2, 1)
        address_layout.addLayout(address_exchange)

        self.address_edit_hint_label = QLabel("选中一行后可修改查询地址；修改后需保存并重新解析。")
        self.address_edit_hint_label.setWordWrap(True)
        self.address_edit_hint_label.setStyleSheet("QLabel { color:#5f4b00; background:#fff8dc; padding:5px; }")
        address_layout.addWidget(self.address_edit_hint_label)

        self.address_table = QTableWidget()
        self.address_table.setObjectName("address_confirmation_table")
        address_headers = (
            "地址ID", "地址用途", "Excel城市", "Excel原始详细地址", "高德标准地址",
            "高德定位层级", "经度", "纬度", "城市是否冲突", "确认状态 / 风险",
            "用于查询的修正地址", "关联订单行数", "关联路线数量",
        )
        self.address_table.setColumnCount(len(address_headers))
        self.address_table.setHorizontalHeaderLabels(address_headers)
        self.address_table.setAlternatingRowColors(True)
        self.address_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.address_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.address_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.address_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.address_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.address_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.address_table.setMinimumHeight(340)
        self.address_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.address_table.horizontalHeader().setMinimumSectionSize(70)
        self.address_table.verticalHeader().setDefaultSectionSize(
            max(34, self.address_table.fontMetrics().height() * 2 + 8)
        )
        for column, width in {
            1: 90, 2: 100, 3: 260, 4: 240, 5: 120, 6: 110, 7: 110,
            8: 120, 9: 180, 10: 260, 11: 110, 12: 110,
        }.items():
            self.address_table.setColumnWidth(column, width)
        self.address_table.hideColumn(0)
        address_layout.addWidget(self.address_table, 1)
        self.tab_widget.addTab(self.address_page, "地址确认")

    def _build_api_page(self) -> None:
        content = QWidget()
        page_layout = QVBoxLayout(content)
        page_layout.setContentsMargins(8, 8, 8, 8)

        api_group = QGroupBox("API Key（仅通过现有安全存储读取和保存）")
        api_layout = QGridLayout(api_group)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("输入高德 Web 服务 Key；请勿粘贴到聊天、配置或报告")
        self.save_key_button = QPushButton("保存 Key")
        self.delete_key_button = QPushButton("删除 Key")
        self.test_key_button = QPushButton("测试连接（最多 2 个成功请求）")
        self.key_state_label = QLabel("已存 Key：等待读取本机安全存储")
        self.driving_status_label = QLabel("普通驾车接口：尚未测试")
        self.office_status_label = QLabel("Excel/WPS：等待检测")
        self.key_state_label.setWordWrap(True)
        self.driving_status_label.setWordWrap(True)
        self.office_status_label.setWordWrap(True)
        api_layout.setColumnStretch(1, 1)
        api_layout.addWidget(QLabel("Key"), 0, 0)
        api_layout.addWidget(self.key_edit, 0, 1, 1, 3)
        api_layout.addWidget(self.save_key_button, 1, 1)
        api_layout.addWidget(self.delete_key_button, 1, 2)
        api_layout.addWidget(self.test_key_button, 1, 3)
        api_layout.addWidget(QLabel("持久化状态"), 2, 0)
        api_layout.addWidget(self.key_state_label, 2, 1, 1, 3)
        api_layout.addWidget(QLabel("接口状态"), 3, 0)
        api_layout.addWidget(self.driving_status_label, 3, 1, 1, 3)
        api_layout.addWidget(QLabel("办公软件"), 4, 0)
        api_layout.addWidget(self.office_status_label, 4, 1, 1, 3)
        page_layout.addWidget(api_group)

        data_group = QGroupBox("数据备份与缓存")
        data_layout = QGridLayout(data_group)
        self.clear_cache_button = QPushButton("清除普通驾车路线缓存")
        self.export_address_book_button = QPushButton("导出可信地址库")
        self.import_address_book_button = QPushButton("导入可信地址库")
        self.export_driving_cache_button = QPushButton("导出普通驾车缓存")
        self.import_driving_cache_button = QPushButton("导入普通驾车缓存")
        for index, button in enumerate((
            self.export_address_book_button,
            self.import_address_book_button,
            self.export_driving_cache_button,
            self.import_driving_cache_button,
        )):
            data_layout.addWidget(button, index // 2, index % 2)
        data_layout.addWidget(self.clear_cache_button, 2, 0, 1, 2)
        data_note = QLabel(
            "备份文件可能包含业务地址，请妥善保管。清理路线缓存不会删除可信地址库。"
        )
        data_note.setWordWrap(True)
        data_note.setStyleSheet("QLabel { color:#444; background:#f4f4f4; padding:6px; }")
        data_layout.addWidget(data_note, 3, 0, 1, 2)
        page_layout.addWidget(data_group)

        self.developer_group = QGroupBox("开发模式（默认收起）")
        self.developer_group.setCheckable(True)
        self.developer_group.setChecked(False)
        developer_layout = QVBoxLayout(self.developer_group)
        self.dev_checkbox = QCheckBox("在运行模式中显示模拟测试模式")
        self.dev_checkbox.setVisible(False)
        developer_layout.addWidget(self.dev_checkbox)
        self.developer_group.toggled.connect(self.dev_checkbox.setVisible)
        page_layout.addWidget(self.developer_group)
        page_layout.addStretch(1)

        self.api_scroll = self._make_scroll_page(content)
        self.api_scroll.setObjectName("api_settings_page")
        self.tab_widget.addTab(self.api_scroll, "API与设置")

    def _wire_events(self) -> None:
        self.select_button.clicked.connect(self._select_file)
        self.output_button.clicked.connect(self._select_output)
        self.detect_button.clicked.connect(lambda: self._inspect_current(force_auto_header=True))
        self.cancel_detect_button.clicked.connect(self._cancel_workbook_inspection)
        self.sheet_combo.currentTextChanged.connect(lambda: self._sheet_changed())
        self.start_button.clicked.connect(self._start)
        self.pause_button.clicked.connect(lambda: self.runner and self.runner.pause())
        self.resume_button.clicked.connect(lambda: self.runner and self.runner.resume())
        self.stop_button.clicked.connect(lambda: self.runner and self.runner.stop())
        self.open_result_button.clicked.connect(self._open_result)
        self.open_folder_button.clicked.connect(self._open_folder)
        self.logs_button.clicked.connect(lambda: os.startfile(self.root / "logs"))
        self.confirm_checkbox.toggled.connect(lambda: self._refresh_summary())
        self.mode_combo.currentIndexChanged.connect(lambda: self._mode_changed())
        self.save_key_button.clicked.connect(self._save_key)
        self.delete_key_button.clicked.connect(self._delete_key)
        self.test_key_button.clicked.connect(self._test_key)
        self.clear_cache_button.clicked.connect(self._clear_driving_cache)
        self.export_address_book_button.clicked.connect(self._export_address_book)
        self.import_address_book_button.clicked.connect(self._import_address_book)
        self.export_driving_cache_button.clicked.connect(self._export_driving_cache)
        self.import_driving_cache_button.clicked.connect(self._import_driving_cache)
        self.dev_checkbox.toggled.connect(self._toggle_dev_mode)
        self.force_refresh_checkbox.toggled.connect(lambda: self._refresh_summary())
        self.refresh_addresses_button.clicked.connect(
            lambda: self._refresh_address_table(sync_workbook=True)
        )
        self.reparse_address_button.clicked.connect(self._reparse_current_address)
        self.use_original_address_button.clicked.connect(lambda: self._use_address_value(False))
        self.use_formatted_address_button.clicked.connect(lambda: self._use_address_value(True))
        self.save_corrected_address_button.clicked.connect(self._save_corrected_address)
        self.confirm_address_button.clicked.connect(self._confirm_current_address)
        self.invalid_address_button.clicked.connect(self._mark_current_address_invalid)
        self.batch_confirm_button.clicked.connect(self._batch_confirm_addresses)
        self.only_unconfirmed_checkbox.toggled.connect(lambda: self._populate_address_table())
        self.export_addresses_button.clicked.connect(self._export_pending_addresses)
        self.import_addresses_button.clicked.connect(self._import_address_results)
        self.address_table.itemSelectionChanged.connect(self._update_address_actions)
        self.address_table.itemChanged.connect(self._address_query_edited)
        self.tab_widget.currentChanged.connect(self._tab_changed)
        for box in self.mapping_boxes.values():
            box.currentIndexChanged.connect(lambda: self._mapping_changed())

    def _refresh_office_engines(self) -> None:
        overall_started = time.perf_counter()
        selected = self.engine_combo.currentData()
        self.engine_combo.blockSignals(True)
        self.engine_combo.clear()
        statuses = []
        for engine, label in (
            (OfficeEngine.EXCEL, "Microsoft Excel"),
            (OfficeEngine.WPS, "WPS 表格（实验性隔离）"),
        ):
            engine_started = time.perf_counter()
            installed = engine_installed(engine)
            self.performance_logger.record(
                "启动检查",
                f"Office检测-{engine.value}",
                (time.perf_counter() - engine_started) * 1000,
                details={"installed": installed},
            )
            statuses.append(f"{label}：{'已安装' if installed else '未检测到'}")
            self.engine_combo.addItem(
                f"{label}｜{'已安装' if installed else '未检测到'}", engine.value
            )
        restored = self.engine_combo.findData(selected)
        self.engine_combo.setCurrentIndex(max(0, restored))
        self.engine_combo.blockSignals(False)
        self.office_status_label.setText("｜".join(statuses))
        self.performance_logger.record(
            "启动检查",
            "Office检测",
            (time.perf_counter() - overall_started) * 1000,
        )

    def _refresh_key_state(self) -> None:
        state = self.key_store.load()
        persistence = "持久化" if state.persisted else "未持久化"
        self.key_state_label.setText(f"已存 Key：{state.masked}｜{state.backend}｜{persistence}")

    @Slot()
    def _save_key(self) -> None:
        try:
            state = self.key_store.save(self.key_edit.text())
            self.key_edit.clear()
            self._refresh_key_state()
            QMessageBox.information(self, "Key 已保存", f"保存位置：{state.backend}\n界面仅显示：{state.masked}")
        except Exception as exc:
            QMessageBox.critical(self, "Key 保存失败", str(exc))

    @Slot()
    def _delete_key(self) -> None:
        answer = QMessageBox.question(
            self,
            "删除 Key",
            "确定删除本工具在 Credential Manager、DPAPI 文件和当前内存中的 Key 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.key_store.delete()
            self.key_edit.clear()
            self.driving_status_label.setText("普通驾车接口：尚未测试")
            self._refresh_key_state()
        except Exception as exc:
            QMessageBox.critical(self, "Key 删除不完整", str(exc))

    @Slot()
    def _test_key(self) -> None:
        typed = self.key_edit.text().strip()
        provider = (lambda: typed or self.key_store.get_key())
        try:
            http = AmapHttpClient(
                provider,
                audit_logger=RealApiAuditLogger(self.root / "logs" / "driving_real" / "connection_tests"),
                max_attempts=3,
            )
            result = test_connection(http)
            self.driving_status_label.setText(
                "普通驾车接口：可用" if result.driving_available else "普通驾车接口：不可用"
            )
            QMessageBox.information(
                self,
                "连接测试完成",
                f"{result.message}\n本次实际 HTTP 调用：{result.actual_calls} 次。",
            )
        except AmapApiError as exc:
            self.driving_status_label.setText("普通驾车接口：不可用")
            QMessageBox.warning(self, exc.status, exc.user_message)
        except Exception as exc:
            self.driving_status_label.setText("普通驾车接口：不可用")
            QMessageBox.critical(self, "连接测试失败", str(exc))

    @Slot()
    def _clear_driving_cache(self) -> None:
        answer = QMessageBox.question(
            self,
            "清除普通驾车路线缓存",
            "确定清除 driving_real 路线缓存吗？地理编码缓存和历史任务记录将保留。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        with CacheRepository(self.root / "cache" / "driving_real.sqlite") as repository:
            removed = repository.clear_route_cache(mode=DRIVING_MODE)
        QMessageBox.information(self, "缓存已清除", f"已清除 {removed} 条普通驾车路线缓存。")

    def _cache_repository(self) -> CacheRepository:
        return CacheRepository(self.root / "cache" / "driving_real.sqlite")

    @Slot()
    def _export_address_book(self) -> None:
        default = self.root / "outputs" / "可信地址库备份.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出可信地址库", str(default), "JSON 备份 (*.json)"
        )
        if not path:
            return
        try:
            with self._cache_repository() as repository:
                exported = export_trusted_addresses(repository, path)
            QMessageBox.information(self, "导出完成", str(exported))
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    @Slot()
    def _import_address_book(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入可信地址库", str(self.root / "outputs"), "JSON 备份 (*.json)"
        )
        if not path:
            return
        try:
            with self._cache_repository() as repository:
                summary = import_trusted_addresses(repository, path)
            self._refresh_address_table()
            QMessageBox.information(
                self,
                "导入完成",
                f"导入 {summary.imported} 条，跳过 {summary.skipped} 条。",
            )
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", str(exc))

    @Slot()
    def _export_driving_cache(self) -> None:
        default = self.root / "outputs" / "普通驾车缓存备份.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出普通驾车缓存", str(default), "JSON 备份 (*.json)"
        )
        if not path:
            return
        try:
            with self._cache_repository() as repository:
                exported = export_driving_cache(repository, path)
            QMessageBox.information(self, "导出完成", str(exported))
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    @Slot()
    def _import_driving_cache(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入普通驾车缓存", str(self.root / "outputs"), "JSON 备份 (*.json)"
        )
        if not path:
            return
        try:
            with self._cache_repository() as repository:
                summary = import_driving_cache(repository, path)
            QMessageBox.information(
                self,
                "导入完成",
                f"地理编码 {summary.geocodes} 条，路线 {summary.routes} 条，"
                f"跳过 {summary.skipped} 条。",
            )
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", str(exc))

    @Slot(bool)
    def _toggle_dev_mode(self, visible: bool) -> None:
        mock_index = self.mode_combo.findData(TaskMode.MOCK.value)
        if visible and mock_index < 0:
            self.mode_combo.addItem("模拟测试：mock 地理编码 + mock 路线", TaskMode.MOCK.value)
        elif not visible and mock_index >= 0:
            if self.mode_combo.currentData() == TaskMode.MOCK.value:
                self.mode_combo.setCurrentIndex(0)
            self.mode_combo.removeItem(mock_index)

    @Slot()
    def _mode_changed(self) -> None:
        mode = TaskMode(self.mode_combo.currentData())
        if mode == TaskMode.MOCK:
            self.warning_label.setText("模拟数据，不可用于正式业务")
            self.warning_label.setStyleSheet(
                "QLabel { color:#b00020; background:#ffe5e8; border:2px solid #b00020; "
                "font-weight:700; padding:8px; }"
            )
            self.confirm_checkbox.setText("我已确认字段映射，并知悉结果全部为模拟数据")
        elif mode == TaskMode.DRIVING_REAL:
            self.warning_label.setText("普通驾车参考距离，不代表货车实际可通行路线")
            self.warning_label.setStyleSheet(
                "QLabel { color:#7a5200; background:#fff4ce; border:2px solid #d6a100; "
                "font-weight:700; padding:8px; }"
            )
            self.confirm_checkbox.setText("我已确认字段映射，并知悉普通驾车距离仅作非线路报价参考")
        else:
            self.warning_label.setText("仅本地校验：不会调用任何 API，也不生成距离")
            self.warning_label.setStyleSheet(
                "QLabel { color:#004a7c; background:#e5f2ff; border:2px solid #3584c6; "
                "font-weight:700; padding:8px; }"
            )
            self.confirm_checkbox.setText("我已确认字段映射，并知悉此模式不生成距离")
        self.confirm_checkbox.setChecked(False)
        self._refresh_summary()

    def _default_sample(self) -> Path | None:
        # 只取默认输入目录的第一个样例，不扫描项目内全部 Excel。
        return next((self.root / "samples" / "input").glob("*.xlsx"), None)

    def _load_default_sample(self, *, refresh_addresses: bool = True) -> None:
        sample = self._default_sample()
        if sample:
            self.file_edit.setText(str(sample))
            self._inspect_current(refresh_addresses=refresh_addresses)

    @Slot()
    def _select_file(self) -> None:
        operation = f"选择输入文件#{uuid.uuid4().hex[:8]}"
        click_started = time.perf_counter()
        self.performance_logger.record(operation, "点击选择输入文件", 0)
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Excel/WPS 工作簿", str(self.root), "Excel 工作簿 (*.xlsx *.xlsm)"
        )
        self.performance_logger.record(
            operation,
            "文件对话框返回",
            (time.perf_counter() - click_started) * 1000,
            status="selected" if path else "cancelled",
            details={"file": Path(path).name if path else ""},
        )
        if path:
            self.file_edit.setText(path)
            self.info = None
            self.confirm_checkbox.setChecked(False)
            self.start_button.setEnabled(False)
            self.detection_status_label.setText("文件已选择，等待后台检测…")
            if not self.output_manually_selected:
                self.output_edit.setText(str(Path(os.path.abspath(path)).parent))
            self._start_workbook_inspection(Path(path))

    @Slot()
    def _select_output(self) -> None:
        operation = f"选择输出目录#{uuid.uuid4().hex[:8]}"
        click_started = time.perf_counter()
        self.performance_logger.record(operation, "点击选择输出目录", 0)
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_edit.text())
        self.performance_logger.record(
            operation,
            "输出目录对话框返回",
            (time.perf_counter() - click_started) * 1000,
            status="selected" if path else "cancelled",
            details={"directory_name": Path(path).name if path else ""},
        )
        if path:
            # 返回后只保存字符串和更新界面；存在性/写权限检查在后台执行。
            self.output_edit.setText(path)
            self.output_manually_selected = True
            self.output_status_label.setText("输出目录：正在后台检查…")
            QTimer.singleShot(0, lambda selected=path: self._start_output_permission_check(selected))

    def _start_output_permission_check(self, path: str) -> None:
        self.output_permission_request_id += 1
        request_id = self.output_permission_request_id
        self.latest_output_permission_request_id = request_id
        if self.output_permission_thread and self.output_permission_thread.isRunning():
            self.pending_output_permission_path = path
            return
        self.pending_output_permission_path = None
        self.output_permission_thread = QThread(self)
        self.output_permission_worker = OutputPermissionWorker(
            request_id, path, self.performance_logger
        )
        self.output_permission_worker.moveToThread(self.output_permission_thread)
        self.output_permission_thread.started.connect(self.output_permission_worker.run)
        self.output_permission_worker.finished.connect(self._output_permission_finished)
        self.output_permission_worker.finished.connect(self.output_permission_thread.quit)
        self.output_permission_thread.finished.connect(self._output_permission_thread_finished)
        self.output_permission_thread.start()

    @Slot(int, str, str)
    def _output_permission_finished(
        self, request_id: int, status: str, message: str
    ) -> None:
        if request_id != self.latest_output_permission_request_id:
            return
        prefix = "输出目录检查完成" if status == "writable" else "输出目录检查提示"
        self.output_status_label.setText(f"{prefix}：{message}")

    @Slot()
    def _output_permission_thread_finished(self) -> None:
        if self.output_permission_worker:
            self.output_permission_worker.deleteLater()
        if self.output_permission_thread:
            self.output_permission_thread.deleteLater()
        self.output_permission_worker = None
        self.output_permission_thread = None
        pending = self.pending_output_permission_path
        self.pending_output_permission_path = None
        if pending:
            self._start_output_permission_check(pending)
        elif self.close_when_background_done:
            self.close()

    @Slot()
    def _sheet_changed(self) -> None:
        if self.sheet_combo.currentText() and self.info and self.sheet_combo.currentText() != self.info.selected_sheet:
            self._inspect_current(
                manual_sheet=self.sheet_combo.currentText(), force_auto_header=True
            )

    def _inspect_current(
        self,
        manual_sheet: str | None = None,
        *,
        refresh_addresses: bool = True,
        force_auto_header: bool = False,
    ) -> None:
        text = self.file_edit.text().strip()
        if not text:
            self.detection_status_label.setText("请先选择工作簿。")
            return
        header = None if force_auto_header else (
            self.header_spin.value() if self.header_spin.value() > 1 else None
        )
        selected_sheet = manual_sheet or (self.sheet_combo.currentText() or None)
        self._start_workbook_inspection(
            Path(text),
            sheet_name=selected_sheet,
            header_row=header,
            refresh_addresses=refresh_addresses,
        )

    def _apply_workbook_info(
        self,
        info: WorkbookInfo,
        *,
        refresh_addresses: bool,
    ) -> None:
        self.info = info
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(self.info.sheets)
        self.sheet_combo.setCurrentText(self.info.selected_sheet)
        self.sheet_combo.blockSignals(False)
        self.header_spin.setValue(self.info.header_row)
        for key, box in self.mapping_boxes.items():
            box.blockSignals(True)
            box.clear()
            if key == "vehicle":
                box.addItem("（可选，不参与普通驾车距离计算）", None)
            for col, descriptor in enumerate(self.info.descriptors, start=1):
                box.addItem(descriptor, col)
            recommended = getattr(self.info.recommended_mapping, key)
            if key == "vehicle":
                box.setCurrentIndex(0 if recommended is None else recommended)
            else:
                box.setCurrentIndex(recommended - 1)
            box.blockSignals(False)
        self._populate_preview()
        self.confirm_checkbox.setChecked(False)
        self._refresh_summary()
        if refresh_addresses:
            self._refresh_address_table(sync_workbook=True)

    def _address_service(self, *, require_key: bool = False) -> tuple[CacheRepository, AddressBookService]:
        if require_key and not self.key_store.get_key():
            raise RuntimeError("请先在本机安全保存高德 Web 服务 Key。")
        repository = CacheRepository(self.root / "cache" / "driving_real.sqlite")
        http = AmapHttpClient(
            self.key_store,
            audit_logger=RealApiAuditLogger(self.root / "logs" / "address_confirmation" / "http"),
            max_attempts=3,
        )
        return repository, AddressBookService(
            repository,
            geocoder=RealGeocoder(http, mode=DRIVING_MODE),
        )

    @Slot(int)
    def _tab_changed(self, index: int) -> None:
        if self.tab_widget.widget(index) is self.address_page and not self.address_records:
            self._refresh_address_table()

    @Slot()
    def _refresh_address_table(
        self,
        *,
        record_startup: bool = False,
        sync_workbook: bool = False,
    ) -> None:
        if self.address_refresh_thread and self.address_refresh_thread.isRunning():
            self.pending_address_refresh = True
            self.pending_address_sync_workbook = (
                self.pending_address_sync_workbook or sync_workbook
            )
            self.address_refresh_record_startup = (
                self.address_refresh_record_startup or record_startup
            )
            return

        selection = None
        city_catalog: tuple[str, ...] = ()
        if self.info and sync_workbook:
            selection = WorkbookSelection(
                self.info.path,
                self.info.selected_sheet,
                self.header_spin.value(),
                self._current_mapping(),
            )
            city_catalog = self.info.city_catalog
        elif not self.info:
            self.address_usage = {}

        self.address_refresh_request_id += 1
        request_id = self.address_refresh_request_id
        self.latest_address_refresh_request_id = request_id
        self.address_refresh_started = time.perf_counter()
        self.address_refresh_record_startup = record_startup
        self.address_summary_label.setText("正在后台加载地址清单…")
        self.address_refresh_thread = QThread(self)
        self.address_refresh_worker = AddressRefreshWorker(
            request_id,
            self.root,
            selection,
            city_catalog,
            self.performance_logger,
        )
        self.address_refresh_worker.moveToThread(self.address_refresh_thread)
        self.address_refresh_thread.started.connect(self.address_refresh_worker.run)
        self.address_refresh_worker.finished.connect(self._address_refresh_finished)
        self.address_refresh_worker.failed.connect(self._address_refresh_failed)
        self.address_refresh_worker.finished.connect(self.address_refresh_thread.quit)
        self.address_refresh_worker.failed.connect(self.address_refresh_thread.quit)
        self.address_refresh_thread.finished.connect(self._address_refresh_thread_finished)
        self.address_refresh_thread.start()

    @Slot(int, object, object, bool)
    def _address_refresh_finished(
        self, request_id: int, records: list, usage: dict, workbook_synced: bool
    ) -> None:
        if request_id != self.latest_address_refresh_request_id:
            return
        self.address_records = records
        if workbook_synced:
            self.address_usage = usage
        self._populate_address_table()

    @Slot(int, str)
    def _address_refresh_failed(self, request_id: int, message: str) -> None:
        if request_id == self.latest_address_refresh_request_id:
            self.address_summary_label.setText(f"地址清单加载失败：{message}")

    @Slot()
    def _address_refresh_thread_finished(self) -> None:
        if self.address_refresh_record_startup:
            elapsed = (time.perf_counter() - self.address_refresh_started) * 1000
            self._record_startup_timing("打开SQLite", elapsed)
            self._record_startup_timing("加载地址清单", elapsed)
        if self.address_refresh_worker:
            self.address_refresh_worker.deleteLater()
        if self.address_refresh_thread:
            self.address_refresh_thread.deleteLater()
        self.address_refresh_worker = None
        self.address_refresh_thread = None
        pending = self.pending_address_refresh
        sync_workbook = self.pending_address_sync_workbook
        record_startup = self.address_refresh_record_startup
        self.pending_address_refresh = False
        self.pending_address_sync_workbook = False
        self.address_refresh_record_startup = False
        if pending:
            self._refresh_address_table(
                record_startup=record_startup, sync_workbook=sync_workbook
            )
        elif self.close_when_background_done:
            self.close()

    def _populate_address_table(self) -> None:
        records = [
            item for item in self.address_records
            if not self.only_unconfirmed_checkbox.isChecked()
            or item.confirmation_status not in TRUSTED_STATUSES
        ]
        self.address_table.blockSignals(True)
        try:
            self.address_table.clearContents()
            self.address_table.setRowCount(len(records))
            for row, item in enumerate(records):
                usage = self.address_usage.get(item.address_id)
                values = (
                    item.address_id,
                    "/".join(usage.purposes) if usage else "",
                    item.original_city,
                    item.original_address,
                    item.formatted_address,
                    item.level,
                    "" if item.longitude is None else f"{item.longitude:.6f}",
                    "" if item.latitude is None else f"{item.latitude:.6f}",
                    "是" if item.city_conflict else "否",
                    f"{item.confirmation_status}\n风险：{item.risk_level}",
                    item.query_address,
                    str(usage.order_count if usage else 0),
                    str(usage.route_count if usage else 0),
                )
                for column, value in enumerate(values):
                    table_item = QTableWidgetItem(value)
                    if column != 10:
                        table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if column == 8 and item.city_conflict:
                        table_item.setBackground(QBrush(QColor("#ffd9d9")))
                        table_item.setForeground(QBrush(QColor("#7a0000")))
                        table_item.setToolTip("城市与详细地址冲突，需人工复核。")
                    if column == 9:
                        table_item.setToolTip(item.risk_reason)
                        if item.risk_level == "高可信":
                            table_item.setBackground(QBrush(QColor("#dff3e4")))
                            table_item.setForeground(QBrush(QColor("#174d2b")))
                        elif item.risk_level == "不允许自动算路":
                            table_item.setBackground(QBrush(QColor("#ffd9d9")))
                            table_item.setForeground(QBrush(QColor("#7a0000")))
                        else:
                            table_item.setBackground(QBrush(QColor("#fff0c2")))
                            table_item.setForeground(QBrush(QColor("#624500")))
                    if column == 10 and "等待重新解析" in item.risk_reason:
                        table_item.setBackground(QBrush(QColor("#fff0c2")))
                        table_item.setToolTip("已保存修正地址，需要重新解析。")
                    self.address_table.setItem(row, column, table_item)
            self.address_table.clearSelection()
            self.address_table.setCurrentCell(-1, -1)
        finally:
            self.address_table.blockSignals(False)
        trusted = sum(item.confirmation_status in TRUSTED_STATUSES for item in self.address_records)
        pending = len(self.address_records) - trusted
        self.address_summary_label.setText(
            f"唯一地址 {len(self.address_records)}｜已可信 {trusted}｜"
            f"待确认/无效 {pending}｜当前显示 {len(records)}"
        )
        self._update_address_actions()

    def _record_for_address_id(self, address_id: str):
        return next((item for item in self.address_records if item.address_id == address_id), None)

    def _current_address_record(self):
        row = self.address_table.currentRow()
        if row < 0 or not self.address_table.item(row, 0):
            return None
        return self._record_for_address_id(self.address_table.item(row, 0).text())

    @Slot()
    def _update_address_actions(self) -> None:
        selected = self._current_address_record() is not None
        for button in (
            self.reparse_address_button,
            self.use_original_address_button,
            self.use_formatted_address_button,
            self.save_corrected_address_button,
            self.confirm_address_button,
            self.invalid_address_button,
        ):
            button.setEnabled(selected)
        # 批量、导入、导出和刷新操作不依赖单行选择。
        self.import_addresses_button.setEnabled(True)
        if not selected:
            self.address_edit_hint_label.setText(
                "选中一行后可修改查询地址；修改后需保存并重新解析。"
            )
            return
        record = self._current_address_record()
        if record and "等待重新解析" in record.risk_reason:
            self.address_edit_hint_label.setText("此地址已修改并保存，需要重新解析后才能继续确认。")
        else:
            self.address_edit_hint_label.setText(
                "可编辑“用于查询的修正地址”列；原 Excel 城市和详细地址不会被修改。"
            )

    def _address_query_edited(self, table_item: QTableWidgetItem) -> None:
        if table_item.column() != 10:
            return
        id_item = self.address_table.item(table_item.row(), 0)
        record = self._record_for_address_id(id_item.text()) if id_item else None
        if not record:
            return
        changed = table_item.text().strip() != record.query_address
        self.address_table.blockSignals(True)
        try:
            if changed:
                table_item.setBackground(QBrush(QColor("#fff0c2")))
                table_item.setToolTip("未保存的修改；保存后必须重新解析。")
                self.address_edit_hint_label.setText(
                    "查询地址已修改：请先“保存修正地址”，再“重新解析当前地址”。"
                )
            elif "等待重新解析" in record.risk_reason:
                table_item.setBackground(QBrush(QColor("#fff0c2")))
                table_item.setToolTip("已保存修正地址，需要重新解析。")
            else:
                table_item.setBackground(QBrush())
                table_item.setToolTip("")
        finally:
            self.address_table.blockSignals(False)

    def _selected_address_id(self) -> str:
        row = self.address_table.currentRow()
        if row < 0 or not self.address_table.item(row, 0):
            raise ValueError("请先在唯一地址清单中选择一行。")
        return self.address_table.item(row, 0).text()

    @Slot()
    def _save_corrected_address(self) -> None:
        if not self._current_address_record():
            return
        repository = None
        try:
            address_id = self._selected_address_id()
            query = self.address_table.item(self.address_table.currentRow(), 10).text()
            repository, service = self._address_service()
            service.save_query_address(address_id, query)
            QMessageBox.information(self, "修正地址已保存", "原 Excel 地址未修改；相关旧路线缓存已失效，请重新解析。")
            self._refresh_address_table()
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
        finally:
            if repository:
                repository.close()

    def _use_address_value(self, formatted: bool) -> None:
        if not self._current_address_record():
            return
        try:
            row = self.address_table.currentRow()
            self._selected_address_id()
            source_column = 4 if formatted else 3
            value = self.address_table.item(row, source_column).text()
            if not value:
                raise ValueError("所选地址值为空。")
            self.address_table.item(row, 10).setText(value)
        except Exception as exc:
            QMessageBox.warning(self, "无法使用该地址", str(exc))

    @Slot()
    def _reparse_current_address(self) -> None:
        if not self._current_address_record():
            return
        repository = None
        try:
            address_id = self._selected_address_id()
            query = self.address_table.item(self.address_table.currentRow(), 10).text()
            repository, service = self._address_service(require_key=True)
            current = repository.get_address(address_id)
            if current and query != current.query_address:
                service.save_query_address(address_id, query)
            service.reparse(address_id)
            QMessageBox.information(self, "重新解析完成", "已保存新的高德标准地址和坐标；原 Excel 地址未修改。")
            self._refresh_address_table()
        except Exception as exc:
            QMessageBox.warning(self, "重新解析失败", str(exc))
        finally:
            if repository:
                repository.close()

    @Slot()
    def _confirm_current_address(self) -> None:
        if not self._current_address_record():
            return
        repository = None
        try:
            repository, service = self._address_service()
            service.confirm(self._selected_address_id())
            QMessageBox.information(self, "已确认", "该唯一地址以后将直接复用，不再重复提示。")
            self._refresh_address_table()
        except Exception as exc:
            QMessageBox.warning(self, "确认失败", str(exc))
        finally:
            if repository:
                repository.close()

    @Slot()
    def _mark_current_address_invalid(self) -> None:
        if not self._current_address_record():
            return
        repository = None
        try:
            repository, service = self._address_service()
            service.mark_invalid(self._selected_address_id())
            QMessageBox.information(self, "已标记无效", "该地址将阻止自动算路。")
            self._refresh_address_table()
        except Exception as exc:
            QMessageBox.warning(self, "操作失败", str(exc))
        finally:
            if repository:
                repository.close()

    @Slot()
    def _batch_confirm_addresses(self) -> None:
        repository = None
        try:
            repository, service = self._address_service()
            count = service.batch_confirm_high_trust()
            QMessageBox.information(self, "批量确认完成", f"已确认 {count} 个系统高可信地址。")
            self._refresh_address_table()
        finally:
            if repository:
                repository.close()

    @Slot()
    def _export_pending_addresses(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出待确认清单", str(self.root / "outputs" / "待确认地址清单.xlsx"),
            "Excel 工作簿 (*.xlsx)",
        )
        if not path:
            return
        try:
            export_pending_addresses(path, self.address_records)
            QMessageBox.information(self, "导出完成", path)
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    @Slot()
    def _import_address_results(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入确认结果", str(self.root / "outputs"), "Excel 工作簿 (*.xlsx)"
        )
        if not path:
            return
        repository = None
        try:
            repository, service = self._address_service(require_key=False)
            summary = import_confirmation_results(path, service)
            QMessageBox.information(
                self, "导入完成",
                f"成功 {summary.success}｜跳过 {summary.skipped}｜失败 {summary.failed}"
                + ("\n" + "\n".join(summary.errors[:5]) if summary.errors else ""),
            )
            self._refresh_address_table()
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
        finally:
            if repository:
                repository.close()

    def _populate_preview(self) -> None:
        if not self.info:
            return
        rows = self.info.preview_rows
        columns = len(rows[0]) if rows else 0
        self.preview_table.setRowCount(len(rows))
        self.preview_table.setColumnCount(columns)
        self.preview_table.setHorizontalHeaderLabels(
            [descriptor.split("｜", 1)[0] for descriptor in self.info.descriptors[:columns]]
        )
        for row_index, values in enumerate(rows):
            for col_index, value in enumerate(values):
                self.preview_table.setItem(row_index, col_index, QTableWidgetItem("" if value is None else str(value)))
        self.preview_table.resizeColumnsToContents()

    @Slot()
    def _mapping_changed(self) -> None:
        self.confirm_checkbox.setChecked(False)
        self._refresh_summary()

    def _current_mapping(self) -> FieldMapping:
        return FieldMapping(
            **{
                key: (None if box.currentData() is None else int(box.currentData()))
                for key, box in self.mapping_boxes.items()
            }
        )

    @Slot()
    def _refresh_summary(self) -> None:
        if not self.info:
            return
        mapping = self._current_mapping()
        result = self.info.result_columns
        self.summary_label.setText(
            f"工作表：{self.info.selected_sheet}\n表头：第 {self.info.header_row} 行（评分 {self.info.header_score}）\n"
            f"字段列：报价 {mapping.quote_type}，始发 {mapping.origin_city}/{mapping.origin_address}，"
            f"目的 {mapping.destination_city}/{mapping.destination_address}，"
            f"车型 {mapping.vehicle if mapping.vehicle is not None else '未映射（允许）'}\n"
            f"结果列：{result.distance}/{result.status}/{result.explanation}；只精确处理“非线路报价”。\n"
            f"计算范围：{'强制重新查询全部唯一路线' if self.force_refresh_checkbox.isChecked() else '仅未完成及已变更行'}。"
        )
        self.start_button.setEnabled(self.confirm_checkbox.isChecked() and self.worker_thread is None)

    @Slot()
    def _start(self) -> None:
        if not self.info or not self.confirm_checkbox.isChecked():
            return
        engine = OfficeEngine(self.engine_combo.currentData())
        if not engine_installed(engine):
            QMessageBox.warning(self, "保存引擎不可用", "未检测到所选 Office COM 注册。")
            return
        mode = TaskMode(self.mode_combo.currentData())
        if mode == TaskMode.DRIVING_REAL:
            if not self.key_store.get_key():
                QMessageBox.warning(self, "API Key 未配置", "请在本机 API 设置中输入并保存 Key；不要在聊天中发送。")
                return
        selection = WorkbookSelection(
            str(Path(self.file_edit.text()).resolve()), self.info.selected_sheet,
            self.header_spin.value(), self._current_mapping(),
        )
        self.runner = PrototypeRunner(self.root)
        self.worker_thread = QThread(self)
        self.worker = RunWorker(
            self.runner,
            selection,
            {
                "engine": engine,
                "mode": mode,
                "output_dir": self.output_edit.text(),
                "force_all": self.force_refresh_checkbox.isChecked(),
                "force_route_refresh": self.force_refresh_checkbox.isChecked(),
            },
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress_changed.connect(self._progress)
        self.worker.finished.connect(self._finished)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._thread_finished)
        self._set_running(True)
        self.worker_thread.start()

    @Slot(object)
    def _progress(self, snapshot) -> None:
        total = max(snapshot.target_total, self.progress_bar.maximum(), 1)
        if snapshot.target_total:
            self.progress_bar.setMaximum(snapshot.target_total)
        self.progress_bar.setValue(min(snapshot.processed, total))
        current = f"，当前 Excel 行 {snapshot.current_row}" if snapshot.current_row else ""
        self.stage_label.setText(snapshot.stage + current)
        self.counter_label.setText(
            f"目标 {snapshot.target_total or self.progress_bar.maximum()}｜已处理 {snapshot.processed}｜"
            f"警告 {snapshot.warning}｜缓存复用 {snapshot.cache_hits}"
        )

    @Slot(object)
    def _finished(self, summary) -> None:
        self.last_output = Path(summary.output_path) if summary.output_path else None
        title = "任务已停止" if summary.stopped else "处理完成"
        state_text = "已安全停止" if summary.stopped else "已完成"
        QMessageBox.information(
            self,
            title,
            f"状态：{state_text}\n需要处理：{summary.target_total} 行\n已处理：{summary.processed} 行\n"
            f"已生成距离：{summary.distance_count} 行\n需要留意：{summary.warning_count} 行\n"
            f"复用已有结果：{summary.cache_hits} 行\n结果文件：{summary.output_path or '未生成'}",
        )

    @Slot(str)
    def _failed(self, message: str) -> None:
        QMessageBox.critical(self, "任务失败（未生成完整结果）", message)

    @Slot()
    def _thread_finished(self) -> None:
        if self.worker:
            self.worker.deleteLater()
        if self.worker_thread:
            self.worker_thread.deleteLater()
        self.worker = None
        self.worker_thread = None
        self._set_running(False)
        if self.close_when_done:
            self.close()

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running and self.confirm_checkbox.isChecked())
        self.pause_button.setEnabled(running)
        self.resume_button.setEnabled(running)
        self.stop_button.setEnabled(running)
        self.open_result_button.setEnabled(not running and self.last_output is not None)
        self.open_folder_button.setEnabled(not running)

    @Slot()
    def _open_result(self) -> None:
        if self.last_output and self.last_output.exists():
            os.startfile(self.last_output)

    @Slot()
    def _open_folder(self) -> None:
        path = self.last_output.parent if self.last_output else Path(self.output_edit.text())
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.startup_thread is not None and self.startup_thread.isRunning():
            self.close_when_startup_done = True
            self.pending_inspection_request = None
            if self.startup_worker:
                self.startup_worker.cancel()
            self.summary_label.setText("正在完成只读工作簿检查，完成后将自动关闭。")
            event.ignore()
            return
        if self.worker_thread is not None and self.worker_thread.isRunning():
            answer = QMessageBox.question(
                self, "任务仍在运行", "是否先安全停止任务、保存已完成结果，再关闭窗口？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.close_when_done = True
                if self.runner:
                    self.runner.stop()
            event.ignore()
            return
        if (
            self.output_permission_thread is not None
            and self.output_permission_thread.isRunning()
        ) or (
            self.address_refresh_thread is not None
            and self.address_refresh_thread.isRunning()
        ):
            self.close_when_background_done = True
            self.pending_output_permission_path = None
            self.pending_address_refresh = False
            self.summary_label.setText("正在结束后台检查，完成后将自动关闭。")
            event.ignore()
            return
        event.accept()


# PySide6.Qt.AlignmentFlag 在不同补丁版中的导出方式不同，集中兼容。
try:
    from PySide6.QtCore import Qt

    QtAlignmentCenter = Qt.AlignmentFlag.AlignCenter
except AttributeError:  # pragma: no cover - 兼容旧 Qt6
    QtAlignmentCenter = Qt.AlignCenter
