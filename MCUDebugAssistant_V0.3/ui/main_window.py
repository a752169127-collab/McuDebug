from __future__ import annotations

import json
import os
import struct
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QThread, Signal, QMetaObject
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.datatype import decode_value, encode_value, format_value, get_type_info, supported_types
from debugger.jlink_backend import ConnectionConfig, JLinkBackend
from debugger.jlink_worker import JLinkWorker
from ui.watch_table import WatchTable
from ui.symbol_browser import SymbolBrowserDialog
from ui.scope_page import ScopePage
from symbols.elf_parser import ElfParseResult, parse_elf_symbols


JLINK_SPEED_PRESETS_KHZ = [
    100, 200, 400, 500, 800, 1000, 1334, 1600, 2000, 2667, 3200,
    4000, 4800, 5334, 6000, 8000, 10000, 12000, 15000, 20000, 25000, 50000,
]


class MainWindow(QMainWindow):
    connect_requested = Signal(object)
    disconnect_requested = Signal()
    # Address is carried as Python object rather than Qt C++ int so the full
    # 0x00000000..0xFFFFFFFF MCU address range is safe on Windows.
    manual_read_requested = Signal(int, object, str)
    manual_write_requested = Signal(int, object, str, str)
    start_sampling_requested = Signal(object, int)
    stop_sampling_requested = Signal()
    update_watch_specs_requested = Signal(object)
    update_watch_interval_requested = Signal(int)
    clear_watch_stats_requested = Signal()
    start_scope_requested = Signal(str, object, int)
    stop_scope_requested = Signal()
    update_scope_fps_requested = Signal(int)
    shutdown_worker_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MCU Debug Assistant V0.3.7 - Scope HSS / RTT")
        self.resize(1220, 820)

        self._settings = QSettings("MCUDebugAssistant", "V0.2")
        self._legacy_settings = QSettings("MCUDebugAssistant", "V0.1")
        self._selector_backend = JLinkBackend()
        self._connected = False
        self._sampling = False
        self._scope_sampling = False
        self._request_id = 0
        self._pending_manual: dict[int, str] = {}
        self._pending_watch_write: dict[int, int] = {}
        self._symbol_result: ElfParseResult | None = None

        self._thread = QThread(self)
        self._worker = JLinkWorker()
        self._worker.moveToThread(self._thread)
        self.connect_requested.connect(self._worker.connect_target)
        self.disconnect_requested.connect(self._worker.disconnect_target)
        self.manual_read_requested.connect(self._worker.read_typed)
        self.manual_write_requested.connect(self._worker.write_typed)
        self.start_sampling_requested.connect(self._worker.start_watch_sampling)
        self.stop_sampling_requested.connect(self._worker.stop_watch_sampling)
        self.update_watch_specs_requested.connect(self._worker.update_watch_specs)
        self.update_watch_interval_requested.connect(self._worker.update_watch_interval)
        self.clear_watch_stats_requested.connect(self._worker.clear_watch_statistics)
        self.start_scope_requested.connect(self._worker.start_scope_sampling)
        self.stop_scope_requested.connect(self._worker.stop_scope_sampling)
        self.update_scope_fps_requested.connect(self._worker.update_scope_emit_fps)
        self.shutdown_worker_requested.connect(self._worker.shutdown)
        self._worker.connection_changed.connect(self._on_connection_changed)
        self._worker.manual_read_done.connect(self._on_manual_read_done)
        self._worker.manual_write_done.connect(self._on_manual_write_done)
        self._worker.watch_samples.connect(self._on_watch_samples)
        self._worker.watch_error.connect(self._on_watch_error)
        self._worker.sampling_state_changed.connect(self._on_sampling_state_changed)
        self._worker.scope_samples.connect(self._on_scope_samples)
        self._worker.scope_error.connect(self._on_scope_error)
        self._worker.scope_state_changed.connect(self._on_scope_state_changed)
        self._worker.scope_rtt_format.connect(self._on_scope_rtt_format)
        self._thread.start()

        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.addWidget(self._build_connection_group())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_watch_page(), "Watch")
        self.scope_page = ScopePage()
        self.scope_page.start_requested.connect(self._start_scope_sampling)
        self.scope_page.stop_requested.connect(lambda: self.stop_scope_requested.emit())
        self.scope_page.add_symbol_requested.connect(self._open_scope_symbol_browser)
        self.scope_page.log_requested.connect(self._log)
        self.scope_page.fps_changed.connect(self.update_scope_fps_requested.emit)
        self.tabs.addTab(self.scope_page, "Scope")
        self.tabs.addTab(self._build_manual_memory_page(), "Memory R/W")
        self.tabs.addTab(self._build_log_page(), "Log")
        layout.addWidget(self.tabs, 1)

        self._load_settings()
        self._update_connection_ui(False)
        self._update_sampling_labels()

    # ---------- Connection ----------
    def _build_connection_group(self) -> QGroupBox:
        box = QGroupBox("J-Link Connection")
        grid = QGridLayout(box)

        self.dll_dir_edit = QLineEdit()
        self.dll_dir_btn = QPushButton("目录...")
        self.dll_dir_btn.clicked.connect(self._browse_dll_directory)
        self.dll_refresh_btn = QPushButton("刷新DLL")
        self.dll_refresh_btn.clicked.connect(self._scan_dlls)
        self.dll_combo = QComboBox()

        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("留空后点击 ... 选择 Target Device")
        self.device_select_btn = QPushButton("...")
        self.device_select_btn.setFixedWidth(42)
        self.device_select_btn.clicked.connect(self._select_target_device)

        self.interface_combo = QComboBox()
        self.interface_combo.addItems(["SWD", "JTAG"])
        self.speed_combo = QComboBox()
        self.speed_combo.setEditable(True)
        self.speed_combo.addItems([str(v) for v in JLINK_SPEED_PRESETS_KHZ])
        self.speed_combo.setCurrentText("4000")

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._connect)
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(lambda: self.disconnect_requested.emit())
        self.status_label = QLabel("Disconnected")

        grid.addWidget(QLabel("J-Link目录"), 0, 0)
        grid.addWidget(self.dll_dir_edit, 0, 1, 1, 4)
        grid.addWidget(self.dll_dir_btn, 0, 5)
        grid.addWidget(self.dll_refresh_btn, 0, 6)
        grid.addWidget(QLabel("DLL"), 1, 0)
        grid.addWidget(self.dll_combo, 1, 1, 1, 2)
        grid.addWidget(QLabel("Device"), 1, 3)
        grid.addWidget(self.device_edit, 1, 4, 1, 2)
        grid.addWidget(self.device_select_btn, 1, 6)
        grid.addWidget(QLabel("Interface"), 2, 0)
        grid.addWidget(self.interface_combo, 2, 1)
        grid.addWidget(QLabel("Speed"), 2, 2)
        grid.addWidget(self.speed_combo, 2, 3)
        grid.addWidget(QLabel("kHz"), 2, 4)
        grid.addWidget(self.connect_btn, 2, 5)
        grid.addWidget(self.disconnect_btn, 2, 6)
        grid.addWidget(self.status_label, 3, 0, 1, 7)
        return box

    # ---------- Watch ----------
    def _build_watch_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        toolbar = QHBoxLayout()
        self.watch_add_btn = QPushButton("+ 添加变量")
        self.watch_add_btn.clicked.connect(self._add_watch_variable)
        self.watch_remove_btn = QPushButton("删除变量")
        self.watch_remove_btn.clicked.connect(self._remove_watch_variable)
        self.sample_interval_spin = QSpinBox()
        self.sample_interval_spin.setRange(1, 60000)
        self.sample_interval_spin.setValue(100)
        self.sample_interval_spin.setSuffix(" ms")
        self.sample_interval_spin.valueChanged.connect(self._sampling_interval_changed)
        self.sample_rate_label = QLabel("10 Hz")
        self.actual_rate_label = QLabel("Actual: -")

        self.watch_start_btn = QPushButton("开始采样")
        self.watch_start_btn.clicked.connect(self._start_watch_sampling)
        self.watch_stop_btn = QPushButton("停止采样")
        self.watch_stop_btn.clicked.connect(lambda: self.stop_sampling_requested.emit())
        self.watch_clear_btn = QPushButton("清空统计")
        self.watch_clear_btn.clicked.connect(self._clear_watch_stats)
        self.watch_save_btn = QPushButton("复制平均值")
        self.watch_save_btn.clicked.connect(self._copy_average_snapshot)

        toolbar.addWidget(self.watch_add_btn)
        toolbar.addWidget(self.watch_remove_btn)
        toolbar.addSpacing(20)
        toolbar.addWidget(QLabel("Sample every"))
        toolbar.addWidget(self.sample_interval_spin)
        toolbar.addWidget(QLabel("Sample Rate:"))
        toolbar.addWidget(self.sample_rate_label)
        toolbar.addWidget(self.actual_rate_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.watch_start_btn)
        toolbar.addWidget(self.watch_stop_btn)
        toolbar.addWidget(self.watch_clear_btn)
        toolbar.addWidget(self.watch_save_btn)
        layout.addLayout(toolbar)

        symbol_bar = QHBoxLayout()
        symbol_bar.addWidget(QLabel("AXF / ELF"))
        self.symbol_file_edit = QLineEdit()
        self.symbol_file_edit.setPlaceholderText("选择 Keil .axf 或 ELF 文件")
        symbol_bar.addWidget(self.symbol_file_edit, 1)
        self.symbol_file_btn = QPushButton("选择文件...")
        self.symbol_file_btn.clicked.connect(self._browse_symbol_file)
        symbol_bar.addWidget(self.symbol_file_btn)
        self.symbol_reload_btn = QPushButton("重新加载")
        self.symbol_reload_btn.clicked.connect(self._reload_symbol_file)
        symbol_bar.addWidget(self.symbol_reload_btn)
        self.symbol_add_btn = QPushButton("添加成员...")
        self.symbol_add_btn.clicked.connect(self._open_symbol_browser)
        symbol_bar.addWidget(self.symbol_add_btn)
        layout.addLayout(symbol_bar)

        hint = QLabel(
            "Watch 使用 JLINK_ReadMemEx 周期采样；相邻变量会自动合并读取。"
            "采样/统计在 J-Link Worker 中按设定频率运行，界面最多约 25 Hz 批量刷新，"
            "因此 Average/Min/Max 不会因为降低 GUI 刷新率而丢样本。"
            "Set Value 按 Enter 立即写入并回读校验；Shift/Ctrl 多选，Delete 可批量删除。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.watch_table = WatchTable()
        self.watch_table.definition_changed.connect(self._watch_definition_changed)
        self.watch_table.write_requested.connect(self._write_watch_row)
        layout.addWidget(self.watch_table, 1)
        return page

    # ---------- Manual R/W ----------
    def _build_manual_memory_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("Memory Read / Write")
        grid = QGridLayout(box)

        self.address_edit = QLineEdit("0x20000000")
        self.type_combo = QComboBox()
        self.type_combo.addItems(supported_types())
        self.type_combo.setCurrentText("float")
        self.type_combo.currentTextChanged.connect(self._type_changed)
        self.type_info_label = QLabel()
        self._type_changed(self.type_combo.currentText())

        self.read_btn = QPushButton("Read")
        self.read_btn.clicked.connect(self._read_value)
        self.current_value_edit = QLineEdit()
        self.current_value_edit.setReadOnly(True)
        self.raw_value_edit = QLineEdit()
        self.raw_value_edit.setReadOnly(True)
        self.write_value_edit = QLineEdit()
        self.write_value_edit.setPlaceholderText("decimal / 0x... for integer")
        self.write_btn = QPushButton("Write + Verify")
        self.write_btn.clicked.connect(self._write_value)

        grid.addWidget(QLabel("Address"), 0, 0)
        grid.addWidget(self.address_edit, 0, 1)
        grid.addWidget(QLabel("Type"), 0, 2)
        grid.addWidget(self.type_combo, 0, 3)
        grid.addWidget(self.type_info_label, 0, 4)
        grid.addWidget(self.read_btn, 0, 5)
        grid.addWidget(QLabel("Current"), 1, 0)
        grid.addWidget(self.current_value_edit, 1, 1, 1, 2)
        grid.addWidget(QLabel("Raw"), 1, 3)
        grid.addWidget(self.raw_value_edit, 1, 4, 1, 2)
        grid.addWidget(QLabel("Write value"), 2, 0)
        grid.addWidget(self.write_value_edit, 2, 1, 1, 4)
        grid.addWidget(self.write_btn, 2, 5)
        layout.addWidget(box)
        layout.addStretch(1)
        return page

    def _build_log_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit, 1)
        return page

    # ---------- Watch actions ----------
    def _add_watch_variable(self) -> None:
        n = self.watch_table.rowCount() + 1
        self.watch_table.add_variable(name=f"Value{n}")
        self._push_watch_specs_if_sampling()

    def _remove_watch_variable(self) -> None:
        removed = self.watch_table.remove_selected()
        if removed:
            self._log(f"Watch: removed {removed} variable(s)")

    def _start_watch_sampling(self) -> None:
        try:
            if self._scope_sampling:
                self.stop_scope_requested.emit()
            specs = self.watch_table.specs()
            if not any(v.enabled for v in specs):
                raise ValueError("至少启用一个 Watch 变量")
            self.start_sampling_requested.emit(specs, self.sample_interval_spin.value())
        except Exception as exc:
            self._show_error("Start sampling failed", exc)

    def _sampling_interval_changed(self, value: int) -> None:
        self._update_sampling_labels()
        if self._sampling:
            self.update_watch_interval_requested.emit(value)

    def _update_sampling_labels(self) -> None:
        interval_ms = max(1, self.sample_interval_spin.value())
        hz = 1000.0 / interval_ms
        if hz >= 1000:
            text = f"{hz / 1000:.3g} kHz"
        else:
            text = f"{hz:.6g} Hz"
        self.sample_rate_label.setText(text)

    def _watch_definition_changed(self) -> None:
        self._push_watch_specs_if_sampling()

    def _push_watch_specs_if_sampling(self) -> None:
        if not self._sampling:
            return
        try:
            self.update_watch_specs_requested.emit(self.watch_table.specs())
        except Exception as exc:
            self._on_watch_error(str(exc))

    def _clear_watch_stats(self) -> None:
        # Clear immediately in the UI and also clear the worker-side authoritative
        # statistics so a later GUI snapshot cannot restore the old values.
        self.watch_table.clear_statistics()
        self.clear_watch_stats_requested.emit()
        self._log("Watch statistics cleared")

    def _write_watch_row(self, row_id: int) -> None:
        """Write Set Value immediately when Enter is pressed in that Watch row."""
        try:
            if not self._connected:
                raise RuntimeError("J-Link is not connected")
            spec, value_text = self.watch_table.write_request(row_id)
            # Validate before queuing the request. The worker performs the actual
            # WriteMemEx + ReadMemEx verification in the J-Link owner thread.
            data = encode_value(value_text, spec.type_name)
            value = decode_value(data, spec.type_name)
            request_id = self._new_request_id("watch_write")
            self._pending_watch_write[request_id] = spec.row_id
            self.manual_write_requested.emit(request_id, spec.address, spec.type_name, value_text)
            self._log(
                f"WATCH WRITE REQUEST {spec.name} @ 0x{spec.address:08X} "
                f"= {format_value(value, spec.type_name)}"
            )
        except Exception as exc:
            self._show_error("Watch write failed", exc)

    def _copy_average_snapshot(self) -> None:
        rows = self.watch_table.average_snapshot()
        if not rows:
            self._log("COPY AVERAGES: Watch list is empty")
            return
        # Excel-friendly single-row snapshot: values only, TAB-separated.
        # Keep an empty field for variables without samples so the Watch column
        # order remains identical after pasting into Excel.
        values = ["" if avg is None else f"{avg:.9g}" for _, avg in rows]
        text = "\t".join(values)
        QApplication.clipboard().setText(text)
        valid_count = sum(avg is not None for _, avg in rows)
        self._log(
            f"Copied {valid_count}/{len(rows)} Watch averages to clipboard "
            f"(values only, Excel row format)"
        )

    def _browse_symbol_file(self) -> None:
        start = self.symbol_file_edit.text().strip() or str(Path.cwd())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 AXF / ELF 文件",
            start,
            "AXF / ELF (*.axf *.elf *.out);;All files (*.*)",
        )
        if not path:
            return
        self.symbol_file_edit.setText(path)
        self._load_symbol_file(path, rebind_watch=True)

    def _reload_symbol_file(self) -> None:
        path = self.symbol_file_edit.text().strip()
        if not path:
            self._log("AXF/ELF reload: no file selected")
            return
        self._load_symbol_file(path, rebind_watch=True)

    def _load_symbol_file(self, path: str | None = None, *, rebind_watch: bool = False) -> bool:
        symbol_path = (path or self.symbol_file_edit.text()).strip()
        if not symbol_path:
            self._log("AXF/ELF: no file selected")
            return False
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            result = parse_elf_symbols(symbol_path)
            self._symbol_result = result
            self.symbol_file_edit.setText(result.path)
            addable = sum(1 for sym in result.symbols if sym.addable)
            mode = "DWARF + ELF" if result.used_dwarf else "ELF symbol table"
            self._log(
                f"Loaded AXF/ELF: {Path(result.path).name} | {len(result.symbols)} symbols | "
                f"{addable} addable | {mode}"
            )
            if result.warning:
                self._log(f"AXF/ELF WARNING: {result.warning}")
            if rebind_watch:
                summary = self.watch_table.rebind_symbols(result.symbols)
                self._log(
                    "AXF/ELF Watch refresh: "
                    f"updated {summary['updated']}, unchanged {summary['unchanged']}, "
                    f"removed missing {summary['removed_missing']}, "
                    f"removed ambiguous {summary['removed_ambiguous']}"
                )
                if summary["type_updated"]:
                    self._log(f"AXF/ELF Watch refresh: Type updated for {summary['type_updated']} variable(s)")
                if hasattr(self, "scope_page"):
                    scope_summary = self.scope_page.rebind_symbols(result.symbols)
                    if any(scope_summary.values()):
                        self._log(
                            "AXF/ELF Scope refresh: "
                            f"updated {scope_summary['updated']}, unchanged {scope_summary['unchanged']}, "
                            f"removed {scope_summary['removed']}"
                        )
            return True
        except Exception as exc:
            self._symbol_result = None
            self._show_error("AXF/ELF parse failed", exc)
            return False
        finally:
            QApplication.restoreOverrideCursor()

    def _open_symbol_browser(self) -> None:
        path = self.symbol_file_edit.text().strip()
        if not path:
            self._browse_symbol_file()
            path = self.symbol_file_edit.text().strip()
            if not path:
                return
        resolved = str(Path(path).expanduser().resolve())
        if self._symbol_result is None or self._symbol_result.path != resolved:
            if not self._load_symbol_file(path, rebind_watch=False):
                return
        if self._symbol_result is None:
            return

        dialog = SymbolBrowserDialog(self._symbol_result.symbols, self, self._symbol_result.path)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        selected = dialog.selected_symbols()
        if not selected:
            self._log("AXF/ELF: no symbols selected")
            return

        added = 0
        skipped = 0
        for sym in selected:
            if sym.type_name is None:
                skipped += 1
                continue
            if self.watch_table.contains_variable(sym.name, sym.address):
                skipped += 1
                continue
            self.watch_table.add_variable(
                name=sym.name,
                address=f"0x{sym.address:08X}",
                type_name=sym.type_name,
                enabled=True,
            )
            added += 1
        self._log(f"AXF/ELF -> Watch: added {added}, skipped {skipped}")
        self._push_watch_specs_if_sampling()

    def _open_scope_symbol_browser(self) -> None:
        if self.scope_page.source_combo.currentText().upper() != "HSS":
            self._log("Scope RTT mode: channels are defined by target JScope_<FORMAT>, AXF symbols are not used")
            return
        path = self.symbol_file_edit.text().strip()
        if not path:
            self._browse_symbol_file()
            path = self.symbol_file_edit.text().strip()
            if not path:
                return
        resolved = str(Path(path).expanduser().resolve())
        if self._symbol_result is None or self._symbol_result.path != resolved:
            if not self._load_symbol_file(path, rebind_watch=False):
                return
        if self._symbol_result is None:
            return
        dialog = SymbolBrowserDialog(self._symbol_result.symbols, self, self._symbol_result.path)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        added = 0
        skipped = 0
        for sym in dialog.selected_symbols():
            if sym.type_name is None:
                skipped += 1
                continue
            if self.scope_page.add_symbol(sym.name, sym.address, sym.type_name):
                added += 1
            else:
                skipped += 1
        self._log(f"AXF/ELF -> Scope: added {added}, skipped {skipped}")

    def _start_scope_sampling(self, source: str, specs, sample_hz: int) -> None:
        try:
            if not self._connected:
                raise RuntimeError("J-Link is not connected")
            if self._sampling:
                self.stop_sampling_requested.emit()
            self.start_scope_requested.emit(source, specs, int(sample_hz))
        except Exception as exc:
            self._show_error("Start Scope failed", exc)

    def _on_scope_samples(self, times, values, actual_hz: float, x_is_time: bool) -> None:
        self.scope_page.append_samples(times, values, actual_hz, x_is_time)

    def _on_scope_error(self, message: str) -> None:
        self._log(f"SCOPE ERROR: {message}")
        QMessageBox.critical(self, "Scope sampling stopped", message)

    def _on_scope_state_changed(self, active: bool, detail: str) -> None:
        self._scope_sampling = bool(active)
        self.scope_page.set_sampling(active, detail)
        if active:
            self._log(f"Scope started: {detail}")
        else:
            self._log(f"Scope stopped: {detail}")

    def _on_scope_rtt_format(self, channel_name: str, channels, has_timestamp: bool) -> None:
        self.scope_page.set_rtt_format(channel_name, channels, has_timestamp)

    # ---------- Connection actions ----------
    def _connect(self) -> None:
        try:
            if not self.device_edit.text().strip():
                if not self._select_target_device():
                    return
            config = ConnectionConfig(
                dll_path=self._selected_dll_path(),
                device=self.device_edit.text().strip(),
                interface=self.interface_combo.currentText(),
                speed_khz=self._parse_speed_khz(),
            )
            self.status_label.setText("Connecting...")
            self.connect_btn.setEnabled(False)
            self.connect_requested.emit(config)
        except Exception as exc:
            self._show_error("Connect failed", exc)
            self._update_connection_ui(False)

    def _on_connection_changed(self, connected: bool, message: str) -> None:
        self._connected = connected
        self._update_connection_ui(connected)
        self.status_label.setText(message)
        if hasattr(self, "scope_page"):
            self.scope_page.set_connected(connected)
        self._log(message)

    def _select_target_device(self) -> bool:
        try:
            selected = self._selector_backend.select_target_device(
                self._selected_dll_path(), parent_hwnd=int(self.winId())
            )
            if selected is None:
                self._log("Target device selection cancelled")
                return False
            self.device_edit.setText(selected.name)
            self._log(f"Selected target: {selected.name}")
            return True
        except Exception as exc:
            self._show_error("Target Device Settings failed", exc)
            return False

    # ---------- Manual actions ----------
    def _read_value(self) -> None:
        try:
            request_id = self._new_request_id("manual_read")
            self.manual_read_requested.emit(request_id, self._parse_address(), self.type_combo.currentText())
        except Exception as exc:
            self._show_error("Read failed", exc)

    def _write_value(self) -> None:
        try:
            address = self._parse_address()
            type_name = self.type_combo.currentText()
            data = encode_value(self.write_value_edit.text(), type_name)
            value = decode_value(data, type_name)
            answer = QMessageBox.question(
                self,
                "Confirm memory write",
                f"Address: 0x{address:08X}\nType: {type_name}\n"
                f"New value: {format_value(value, type_name)}\nRaw: {data.hex(' ').upper()}\n\n"
                "Write to target memory and verify?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            request_id = self._new_request_id("manual_write")
            self.manual_write_requested.emit(request_id, address, type_name, self.write_value_edit.text())
        except Exception as exc:
            self._show_error("Write failed", exc)

    def _on_manual_read_done(self, request_id: int, ok: bool, value, raw: str, error: str) -> None:
        kind = self._pending_manual.pop(request_id, "")
        if not ok:
            self._show_error("Read failed", RuntimeError(error))
            return
        if kind == "manual_read":
            type_name = self.type_combo.currentText()
            self.current_value_edit.setText(format_value(value, type_name))
            self.raw_value_edit.setText(raw)
            self._log(f"READ value={self.current_value_edit.text()} raw={raw}")

    def _on_manual_write_done(self, request_id: int, ok: bool, value, raw: str, error: str) -> None:
        kind = self._pending_manual.pop(request_id, "")
        row_id = self._pending_watch_write.pop(request_id, None)
        if not ok:
            self._show_error("Write failed", RuntimeError(error))
            return
        if row_id is not None:
            # Sampling will refresh the row immediately afterwards; still update Current now.
            for spec in self.watch_table.specs():
                if spec.row_id == row_id:
                    self.watch_table.set_current_only(row_id, value, format_value(value, spec.type_name))
                    self._log(f"WATCH WRITE {spec.name} = {format_value(value, spec.type_name)} VERIFY=OK")
                    break
        elif kind == "manual_write":
            type_name = self.type_combo.currentText()
            self.current_value_edit.setText(format_value(value, type_name))
            self.raw_value_edit.setText(raw)
            self._log(f"WRITE value={self.current_value_edit.text()} VERIFY=OK")

    def _new_request_id(self, kind: str) -> int:
        self._request_id += 1
        self._pending_manual[self._request_id] = kind
        return self._request_id

    # ---------- Worker callbacks ----------
    def _on_watch_samples(self, samples, elapsed_s: float, actual_hz: float) -> None:
        # Worker emits a latest-state snapshot at <=25 Hz instead of one Qt event per
        # acquisition cycle. Apply all changed Watch cells in one repaint batch.
        self.watch_table.apply_snapshot(samples)
        if actual_hz > 0:
            self.actual_rate_label.setText(f"Actual: {actual_hz:.3g} Hz")
        else:
            self.actual_rate_label.setText("Actual: -")

    def _on_watch_error(self, message: str) -> None:
        self._log(f"WATCH ERROR: {message}")
        QMessageBox.critical(self, "Watch sampling stopped", message)

    def _on_sampling_state_changed(self, active: bool) -> None:
        self._sampling = active
        self.watch_start_btn.setEnabled(self._connected and not active)
        self.watch_stop_btn.setEnabled(self._connected and active)
        self.watch_add_btn.setEnabled(not active)
        self.watch_remove_btn.setEnabled(not active)
        self.symbol_add_btn.setEnabled(not active)
        self.watch_table.set_definition_editable(not active)
        if not active:
            self.actual_rate_label.setText("Actual: -")

    # ---------- Common helpers ----------
    def _parse_address(self) -> int:
        text = self.address_edit.text().strip()
        if not text:
            raise ValueError("Address is empty")
        try:
            address = int(text, 0)
        except ValueError as exc:
            raise ValueError(f"Invalid address: {text}") from exc
        if not 0 <= address <= 0xFFFFFFFF:
            raise ValueError("32-bit MCU addresses only")
        return address

    def _type_changed(self, type_name: str) -> None:
        info = get_type_info(type_name)
        self.type_info_label.setText(f"{info.size} byte{'s' if info.size != 1 else ''}")

    def _update_connection_ui(self, connected: bool) -> None:
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected)
        self.read_btn.setEnabled(connected)
        self.write_btn.setEnabled(connected)
        self.watch_start_btn.setEnabled(connected and not self._sampling)
        self.watch_stop_btn.setEnabled(connected and self._sampling)
        if hasattr(self, "scope_page"):
            self.scope_page.set_connected(connected)
        for w in (
            self.dll_dir_edit, self.dll_dir_btn, self.dll_refresh_btn, self.dll_combo,
            self.device_edit, self.device_select_btn, self.interface_combo, self.speed_combo,
        ):
            w.setEnabled(not connected)

    def _browse_dll_directory(self) -> None:
        start = self.dll_dir_edit.text().strip() or self._default_dll_directory()
        path = QFileDialog.getExistingDirectory(self, "选择 SEGGER J-Link DLL 目录", start)
        if path:
            self.dll_dir_edit.setText(path)
            self._scan_dlls()

    def _default_dll_directory(self) -> str:
        app_dir = Path(__file__).resolve().parents[1]
        if self._find_jlink_dlls(app_dir):
            return str(app_dir)
        cwd = Path.cwd()
        if cwd != app_dir and self._find_jlink_dlls(cwd):
            return str(cwd)
        if os.name == "nt":
            candidates: list[Path] = []
            for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
                if not base:
                    continue
                segger = Path(base) / "SEGGER"
                if segger.is_dir():
                    candidates.extend(p for p in segger.glob("JLink*") if p.is_dir())
            for folder in sorted(candidates, reverse=True):
                if self._find_jlink_dlls(folder):
                    return str(folder)
        return str(app_dir)

    @staticmethod
    def _find_jlink_dlls(folder: Path) -> list[Path]:
        if not folder.is_dir():
            return []
        result = []
        for pattern in ("JLink*.dll", "jlink*.dll"):
            result.extend(p for p in folder.glob(pattern) if p.is_file())
        return list({str(p).lower(): p for p in result}.values())

    def _scan_dlls(self, preferred_name: str | None = None) -> None:
        folder_text = self.dll_dir_edit.text().strip()
        folder = Path(folder_text).expanduser() if folder_text else Path(self._default_dll_directory())
        if not folder_text:
            self.dll_dir_edit.setText(str(folder))
        dlls = self._find_jlink_dlls(folder)
        is_64bit_python = struct.calcsize("P") == 8
        dlls.sort(key=lambda p: (0 if ((is_64bit_python and p.name.lower() == "jlink_x64.dll") or ((not is_64bit_python) and p.name.lower() == "jlinkarm.dll")) else 1, p.name.lower()))
        previous = preferred_name or self.dll_combo.currentText()
        self.dll_combo.clear()
        self.dll_combo.addItems([p.name for p in dlls])
        if previous:
            idx = self.dll_combo.findText(previous, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.dll_combo.setCurrentIndex(idx)
        if not dlls:
            self.dll_combo.addItem("<未找到 J-Link DLL>")

    def _selected_dll_path(self) -> str:
        folder = Path(self.dll_dir_edit.text().strip()).expanduser()
        name = self.dll_combo.currentText().strip()
        if not name or name.startswith("<"):
            raise ValueError("当前目录没有找到 J-Link DLL")
        return str(folder / name)

    def _parse_speed_khz(self) -> int:
        text = self.speed_combo.currentText().strip()
        try:
            speed = int(text, 10)
        except ValueError as exc:
            raise ValueError(f"Invalid interface speed: {text}") from exc
        if speed <= 0 or speed > 100000:
            raise ValueError("Interface speed must be in range 1..100000 kHz")
        return speed

    def _show_error(self, title: str, exc: Exception) -> None:
        text = str(exc)
        self._log(f"ERROR: {text}")
        QMessageBox.critical(self, title, text)

    def _log(self, text: str) -> None:
        self.log_edit.appendPlainText(text)

    # ---------- Persistence ----------
    def _setting(self, key: str, default=None):
        value = self._settings.value(key, None)
        if value is None or value == "":
            legacy = self._legacy_settings.value(key, None)
            if legacy is not None and legacy != "":
                return legacy
        return default if value is None else value

    def _load_settings(self) -> None:
        saved_dir = str(self._setting("dll_dir", "") or "")
        old_dll_path = str(self._setting("dll_path", "") or "")
        if not saved_dir and old_dll_path:
            saved_dir = str(Path(old_dll_path).parent)
        dll_dir = saved_dir or self._default_dll_directory()
        saved_dll_name = str(self._setting("dll_name", "") or "")
        if not saved_dll_name and old_dll_path:
            saved_dll_name = Path(old_dll_path).name

        self.dll_dir_edit.setText(dll_dir)
        self._scan_dlls(preferred_name=saved_dll_name)
        self.device_edit.setText(str(self._setting("device", "") or ""))
        self.interface_combo.setCurrentText(str(self._setting("interface", "SWD") or "SWD"))
        self.speed_combo.setCurrentText(str(self._setting("speed_khz", "4000") or "4000"))
        self.sample_interval_spin.setValue(int(self._setting("watch_interval_ms", 100) or 100))
        self.symbol_file_edit.setText(str(self._setting("symbol_file", "") or ""))

        watch_json = str(self._setting("watch_variables", "") or "")
        try:
            self.watch_table.load_json(watch_json)
        except Exception:
            pass
        if self.watch_table.rowCount() == 0:
            self.watch_table.add_variable("Value1", "0x20000000", "float")

        if hasattr(self, "scope_page"):
            scope_text = str(self._setting("scope_state", "") or "")
            if scope_text:
                try:
                    self.scope_page.load_settings_state(json.loads(scope_text))
                except Exception:
                    pass

    def _save_settings(self) -> None:
        self._settings.setValue("dll_dir", self.dll_dir_edit.text().strip())
        if not self.dll_combo.currentText().startswith("<"):
            self._settings.setValue("dll_name", self.dll_combo.currentText())
        self._settings.setValue("device", self.device_edit.text().strip())
        self._settings.setValue("interface", self.interface_combo.currentText())
        self._settings.setValue("speed_khz", self.speed_combo.currentText().strip())
        self._settings.setValue("watch_interval_ms", self.sample_interval_spin.value())
        self._settings.setValue("symbol_file", self.symbol_file_edit.text().strip())
        self._settings.setValue("watch_variables", self.watch_table.to_json())
        if hasattr(self, "scope_page"):
            self._settings.setValue("scope_state", json.dumps(self.scope_page.settings_state(), ensure_ascii=False))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_settings()
        if self._thread.isRunning():
            try:
                # Ensure the J-Link session is closed by its owning worker
                # thread before the event loop is stopped.
                QMetaObject.invokeMethod(
                    self._worker,
                    "shutdown",
                    Qt.ConnectionType.BlockingQueuedConnection,
                )
            except Exception:
                pass
            self._thread.quit()
            self._thread.wait(2000)
        self._selector_backend.close()
        super().closeEvent(event)
