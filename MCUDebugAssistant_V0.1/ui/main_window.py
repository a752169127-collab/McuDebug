from __future__ import annotations

import os
import struct
from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
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
    QVBoxLayout,
    QWidget,
)

from core.datatype import (
    decode_value,
    encode_value,
    format_value,
    get_type_info,
    supported_types,
)
from debugger.jlink_backend import ConnectionConfig, JLinkBackend


# Common numeric J-Link interface speeds. The combo is editable, so the user
# can still enter any speed accepted by J-Link.
JLINK_SPEED_PRESETS_KHZ = [
    100,
    200,
    400,
    500,
    800,
    1000,
    1334,
    1600,
    2000,
    2667,
    3200,
    4000,
    4800,
    5334,
    6000,
    8000,
    10000,
    12000,
    15000,
    20000,
    25000,
    50000,
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MCU Debug Assistant V0.1.2")
        self.resize(980, 690)

        self._jlink = JLinkBackend()
        self._settings = QSettings("MCUDebugAssistant", "V0.1")

        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_connection_group())
        layout.addWidget(self._build_memory_group())
        layout.addWidget(self._build_log_group(), 1)

        self._load_settings()
        self._update_connection_ui(False)

    def _build_connection_group(self) -> QGroupBox:
        box = QGroupBox("J-Link Connection")
        grid = QGridLayout(box)

        # Select a directory, then show the J-Link DLLs directly from it.
        self.dll_dir_edit = QLineEdit()
        self.dll_dir_edit.setPlaceholderText("J-Link安装目录，或把DLL放到本程序目录")
        self.dll_dir_edit.editingFinished.connect(self._scan_dlls)

        self.dll_dir_btn = QPushButton("选择目录...")
        self.dll_dir_btn.clicked.connect(self._browse_dll_directory)

        self.dll_refresh_btn = QPushButton("刷新DLL")
        self.dll_refresh_btn.clicked.connect(self._scan_dlls)

        self.dll_combo = QComboBox()
        self.dll_combo.setMinimumContentsLength(28)

        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText(
            "可直接输入芯片名，或点击右侧 ... 打开 SEGGER Target Device Settings"
        )
        self.device_select_btn = QPushButton("...")
        self.device_select_btn.setFixedWidth(38)
        self.device_select_btn.setToolTip("打开 SEGGER Target Device Settings")
        self.device_select_btn.clicked.connect(self._select_target_device)

        self.interface_combo = QComboBox()
        self.interface_combo.addItems(["SWD", "JTAG"])

        # J-Link-style editable speed dropdown rather than a spin box.
        self.speed_combo = QComboBox()
        self.speed_combo.setEditable(True)
        self.speed_combo.addItems([str(v) for v in JLINK_SPEED_PRESETS_KHZ])
        self.speed_combo.setCurrentText("4000")
        self.speed_combo.setMinimumWidth(105)

        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        self.connect_btn.clicked.connect(self._connect)
        self.disconnect_btn.clicked.connect(self._disconnect)

        self.status_label = QLabel("Disconnected")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        grid.addWidget(QLabel("J-Link目录"), 0, 0)
        grid.addWidget(self.dll_dir_edit, 0, 1, 1, 3)
        grid.addWidget(self.dll_dir_btn, 0, 4)
        grid.addWidget(self.dll_refresh_btn, 0, 5)

        grid.addWidget(QLabel("DLL"), 1, 0)
        grid.addWidget(self.dll_combo, 1, 1, 1, 2)
        grid.addWidget(QLabel("Interface"), 1, 3)
        grid.addWidget(self.interface_combo, 1, 4)
        speed_row = QHBoxLayout()
        speed_row.setContentsMargins(0, 0, 0, 0)
        speed_row.addWidget(self.speed_combo)
        speed_row.addWidget(QLabel("kHz"))
        speed_widget = QWidget()
        speed_widget.setLayout(speed_row)
        grid.addWidget(speed_widget, 1, 5)

        grid.addWidget(QLabel("Device"), 2, 0)
        grid.addWidget(self.device_edit, 2, 1, 1, 4)
        grid.addWidget(self.device_select_btn, 2, 5)

        grid.addWidget(self.connect_btn, 3, 3)
        grid.addWidget(self.disconnect_btn, 3, 4)
        grid.addWidget(self.status_label, 3, 5)
        return box

    def _build_memory_group(self) -> QGroupBox:
        box = QGroupBox("Memory Read / Write")
        grid = QGridLayout(box)

        self.address_edit = QLineEdit("0x20000000")
        self.address_edit.setPlaceholderText("0x20000000")

        self.type_combo = QComboBox()
        self.type_combo.addItems(supported_types())
        self.type_combo.setCurrentText("float")
        self.type_combo.currentTextChanged.connect(self._type_changed)

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

        self.type_info_label = QLabel()
        self._type_changed(self.type_combo.currentText())

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
        return box

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit)
        return box

    def _browse_dll_directory(self) -> None:
        start = self.dll_dir_edit.text().strip() or self._default_dll_directory()
        path = QFileDialog.getExistingDirectory(self, "选择 SEGGER J-Link DLL 目录", start)
        if path:
            self.dll_dir_edit.setText(path)
            self._scan_dlls()

    def _default_dll_directory(self) -> str:
        # Priority 1: program/project directory. This makes it convenient to
        # place a J-Link DLL beside the tool and have it detected immediately.
        app_dir = Path(__file__).resolve().parents[1]
        if self._find_jlink_dlls(app_dir):
            return str(app_dir)

        cwd = Path.cwd()
        if cwd != app_dir and self._find_jlink_dlls(cwd):
            return str(cwd)

        # Priority 2: latest SEGGER J-Link installation on Windows.
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
        # Case-insensitive de-duplication on Windows-like file names.
        unique = {str(p).lower(): p for p in result}
        return list(unique.values())

    def _scan_dlls(self, preferred_name: str | None = None) -> None:
        folder_text = self.dll_dir_edit.text().strip()
        folder = Path(folder_text).expanduser() if folder_text else Path(self._default_dll_directory())
        if not folder_text:
            self.dll_dir_edit.setText(str(folder))

        dlls = self._find_jlink_dlls(folder)
        is_64bit_python = struct.calcsize("P") == 8

        def sort_key(path: Path):
            name = path.name.lower()
            preferred = (
                (is_64bit_python and name == "jlink_x64.dll")
                or ((not is_64bit_python) and name == "jlinkarm.dll")
            )
            return (0 if preferred else 1, name)

        dlls.sort(key=sort_key)

        previous = preferred_name or self.dll_combo.currentText()
        self.dll_combo.clear()
        self.dll_combo.addItems([p.name for p in dlls])

        if previous:
            idx = self.dll_combo.findText(previous, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.dll_combo.setCurrentIndex(idx)

        if not dlls:
            self.dll_combo.addItem("<未找到 J-Link DLL>")
            self._log(f"No J-Link DLL found in: {folder}")

    def _selected_dll_path(self) -> str:
        folder = Path(self.dll_dir_edit.text().strip()).expanduser()
        name = self.dll_combo.currentText().strip()
        if not name or name.startswith("<"):
            raise ValueError("当前目录没有找到 J-Link DLL，请选择正确的 J-Link 安装目录")
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

    def _select_target_device(self) -> bool:
        """Open the native SEGGER Target Device Settings dialog."""
        try:
            dll_path = self._selected_dll_path()
            selected = self._jlink.select_target_device(
                dll_path=dll_path,
                parent_hwnd=int(self.winId()),
            )
            if selected is None:
                self._log("Target device selection cancelled")
                return False

            self.device_edit.setText(selected.name)
            details = [f"device={selected.name}"]
            if selected.manufacturer:
                details.append(f"manufacturer={selected.manufacturer}")
            if selected.flash_size:
                details.append(f"flash={selected.flash_size / 1024:.0f} KiB")
            if selected.ram_size:
                details.append(f"ram={selected.ram_size / 1024:.0f} KiB")
            if selected.core_index:
                details.append(f"core_index={selected.core_index}")
            self._log("Selected target: " + ", ".join(details))
            return True
        except Exception as exc:
            self._show_error("Target Device Settings failed", exc)
            return False

    def _connect(self) -> None:
        try:
            # J-Scope-like behavior: if Device is blank, open SEGGER's native
            # Target Device Settings first instead of relying on an implicit
            # dialog during JLINK_Connect().
            if not self.device_edit.text().strip():
                if not self._select_target_device():
                    return

            config = ConnectionConfig(
                dll_path=self._selected_dll_path(),
                device=self.device_edit.text().strip(),
                interface=self.interface_combo.currentText(),
                speed_khz=self._parse_speed_khz(),
            )
            device_text = config.device
            self._log(
                f"Connecting: device={device_text}, interface={config.interface}, "
                f"speed={config.speed_khz} kHz, dll={Path(config.dll_path).name}"
            )
            self._jlink.connect(config)
            self._save_settings()
            self._update_connection_ui(True)
            self._log(f"Connected. J-Link DLL version: {self._jlink.get_dll_version_text()}")
        except Exception as exc:
            self._update_connection_ui(False)
            self._show_error("Connect failed", exc)

    def _disconnect(self) -> None:
        try:
            self._jlink.close()
            self._log("Disconnected")
        finally:
            self._update_connection_ui(False)

    def _read_value(self) -> None:
        try:
            address = self._parse_address()
            type_name = self.type_combo.currentText()
            info = get_type_info(type_name)
            raw = self._jlink.read_memory(address, info.size)
            value = decode_value(raw, type_name)

            self.current_value_edit.setText(format_value(value, type_name))
            self.raw_value_edit.setText(raw.hex(" ").upper())
            self._log(
                f"READ  0x{address:08X}  {type_name:<6}  "
                f"value={format_value(value, type_name)}  raw={raw.hex(' ').upper()}"
            )
        except Exception as exc:
            self._show_error("Read failed", exc)

    def _write_value(self) -> None:
        try:
            address = self._parse_address()
            type_name = self.type_combo.currentText()
            data = encode_value(self.write_value_edit.text(), type_name)

            new_value = decode_value(data, type_name)
            answer = QMessageBox.question(
                self,
                "Confirm memory write",
                f"Address: 0x{address:08X}\n"
                f"Type: {type_name}\n"
                f"New value: {format_value(new_value, type_name)}\n"
                f"Raw: {data.hex(' ').upper()}\n\n"
                "Write to target memory and verify by reading it back?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            readback = self._jlink.write_and_verify(address, data)
            value = decode_value(readback, type_name)
            self.current_value_edit.setText(format_value(value, type_name))
            self.raw_value_edit.setText(readback.hex(" ").upper())
            self._log(
                f"WRITE 0x{address:08X}  {type_name:<6}  "
                f"value={format_value(value, type_name)}  VERIFY=OK"
            )
        except Exception as exc:
            self._show_error("Write failed", exc)

    def _parse_address(self) -> int:
        text = self.address_edit.text().strip()
        if not text:
            raise ValueError("Address is empty")
        try:
            address = int(text, 0)
        except ValueError as exc:
            raise ValueError(f"Invalid address: {text}") from exc
        if not 0 <= address <= 0xFFFFFFFF:
            raise ValueError("V0.1 supports 32-bit MCU addresses only")
        return address

    def _type_changed(self, type_name: str) -> None:
        info = get_type_info(type_name)
        self.type_info_label.setText(f"{info.size} byte{'s' if info.size != 1 else ''}")

    def _update_connection_ui(self, connected: bool) -> None:
        self.status_label.setText("Connected" if connected else "Disconnected")
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected)
        self.read_btn.setEnabled(connected)
        self.write_btn.setEnabled(connected)

        self.dll_dir_edit.setEnabled(not connected)
        self.dll_dir_btn.setEnabled(not connected)
        self.dll_refresh_btn.setEnabled(not connected)
        self.dll_combo.setEnabled(not connected)
        self.device_edit.setEnabled(not connected)
        self.device_select_btn.setEnabled(not connected)
        self.interface_combo.setEnabled(not connected)
        self.speed_combo.setEnabled(not connected)

    def _show_error(self, title: str, exc: Exception) -> None:
        text = str(exc)
        self._log(f"ERROR: {text}")
        QMessageBox.critical(self, title, text)

    def _log(self, text: str) -> None:
        self.log_edit.appendPlainText(text)

    def _load_settings(self) -> None:
        saved_dir = str(self._settings.value("dll_dir", "") or "")
        # Upgrade old V0.1 setting that stored the full DLL path.
        old_dll_path = str(self._settings.value("dll_path", "") or "")
        if not saved_dir and old_dll_path:
            old_path = Path(old_dll_path)
            if old_path.parent:
                saved_dir = str(old_path.parent)

        dll_dir = saved_dir or self._default_dll_directory()
        saved_dll_name = str(self._settings.value("dll_name", "") or "")
        if not saved_dll_name and old_dll_path:
            saved_dll_name = Path(old_dll_path).name

        device = str(self._settings.value("device", "") or "")
        interface = str(self._settings.value("interface", "SWD") or "SWD")
        speed = str(self._settings.value("speed_khz", "4000") or "4000")

        self.dll_dir_edit.setText(dll_dir)
        self._scan_dlls(preferred_name=saved_dll_name)
        self.device_edit.setText(device)
        self.interface_combo.setCurrentText(interface)
        self.speed_combo.setCurrentText(speed)

    def _save_settings(self) -> None:
        self._settings.setValue("dll_dir", self.dll_dir_edit.text().strip())
        if not self.dll_combo.currentText().startswith("<"):
            self._settings.setValue("dll_name", self.dll_combo.currentText())
        self._settings.setValue("device", self.device_edit.text().strip())
        self._settings.setValue("interface", self.interface_combo.currentText())
        self._settings.setValue("speed_khz", self.speed_combo.currentText().strip())

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self._save_settings()
        self._jlink.close()
        super().closeEvent(event)
