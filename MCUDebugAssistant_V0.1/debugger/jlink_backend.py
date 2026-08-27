from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


class _JLinkAreaInfo(ctypes.Structure):
    _fields_ = [
        ("Addr", ctypes.c_uint32),
        ("Size", ctypes.c_uint32),
    ]


class _JLinkDeviceInfo(ctypes.Structure):
    # Layout follows JLINKARM_DEVICE_INFO from the J-Link SDK.
    _fields_ = [
        ("SizeofStruct", ctypes.c_uint32),
        ("sName", ctypes.c_char_p),
        ("CoreId", ctypes.c_uint32),
        ("FlashAddr", ctypes.c_uint32),
        ("RAMAddr", ctypes.c_uint32),
        ("EndianMode", ctypes.c_char),
        ("FlashSize", ctypes.c_uint32),
        ("RAMSize", ctypes.c_uint32),
        ("sManu", ctypes.c_char_p),
        ("aFlashArea", _JLinkAreaInfo * 32),
        ("aRAMArea", _JLinkAreaInfo * 32),
        ("Core", ctypes.c_uint32),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.SizeofStruct = ctypes.sizeof(self)


class _JLinkDeviceSelectInfo(ctypes.Structure):
    _fields_ = [
        ("SizeOfStruct", ctypes.c_uint32),
        ("CoreIndex", ctypes.c_uint32),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.SizeOfStruct = ctypes.sizeof(self)
        self.CoreIndex = 0


@dataclass
class TargetDeviceInfo:
    index: int
    name: str
    manufacturer: str = ""
    core_id: int = 0
    core: int = 0
    flash_addr: int = 0
    flash_size: int = 0
    ram_addr: int = 0
    ram_size: int = 0
    core_index: int = 0


class JLinkError(RuntimeError):
    pass


@dataclass
class ConnectionConfig:
    dll_path: str
    device: str
    interface: str = "SWD"
    speed_khz: int = 4000


class JLinkBackend:
    """Minimal J-Link DLL wrapper for V0.1.

    Scope:
      * Open/close J-Link DLL session
      * Select SWD/JTAG
      * Select target device
      * Set interface speed
      * Connect to target
      * Read with JLINK_ReadMemEx
      * Write with JLINK_WriteMemEx

    HSS / RTT / AXF / ELF intentionally do not live here yet.
    """

    TIF_JTAG = 0
    TIF_SWD = 1
    ACCESS_WIDTH_AUTO = 0

    def __init__(self) -> None:
        self._dll = None
        self._dll_path: Optional[str] = None
        self._is_open = False
        self._is_target_connected = False

        self._fn_open = None
        self._fn_close = None
        self._fn_tif_select = None
        self._fn_exec_command = None
        self._fn_set_speed = None
        self._fn_connect = None
        self._fn_read_mem_ex = None
        self._fn_write_mem_ex = None
        self._fn_is_connected = None
        self._fn_get_dll_version = None
        self._fn_device_select_dialog = None
        self._fn_device_get_info = None

    @property
    def dll_path(self) -> Optional[str]:
        return self._dll_path

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def is_target_connected(self) -> bool:
        if self._dll is not None and self._fn_is_connected is not None:
            try:
                return bool(self._fn_is_connected())
            except Exception:
                pass
        return self._is_target_connected

    def load_library(self, dll_path: str) -> None:
        path = Path(dll_path).expanduser()
        if not path.is_file():
            raise JLinkError(f"J-Link DLL not found: {path}")

        try:
            # SEGGER API is STDCALL on Windows. WinDLL is the correct ctypes loader.
            self._dll = ctypes.WinDLL(str(path)) if os.name == "nt" else ctypes.CDLL(str(path))
        except OSError as exc:
            arch_hint = (
                " Ensure Python and J-Link DLL bitness match "
                "(64-bit Python -> JLink_x64.dll; 32-bit Python -> JLinkARM.dll)."
            )
            raise JLinkError(f"Failed to load {path}.{arch_hint}\n{exc}") from exc

        self._dll_path = str(path)
        self._bind_api()

    def _resolve(self, modern_name: str, legacy_name: str):
        if self._dll is None:
            raise JLinkError("J-Link DLL is not loaded")
        for name in (modern_name, legacy_name):
            try:
                return getattr(self._dll, name)
            except AttributeError:
                continue
        raise JLinkError(f"DLL does not export {modern_name} or {legacy_name}")

    def _resolve_optional(self, modern_name: str, legacy_name: str):
        if self._dll is None:
            return None
        for name in (modern_name, legacy_name):
            try:
                return getattr(self._dll, name)
            except AttributeError:
                continue
        return None

    def _bind_api(self) -> None:
        self._fn_open = self._resolve("JLINK_Open", "JLINKARM_Open")
        self._fn_open.argtypes = []
        self._fn_open.restype = ctypes.c_char_p

        self._fn_close = self._resolve("JLINK_Close", "JLINKARM_Close")
        self._fn_close.argtypes = []
        self._fn_close.restype = None

        self._fn_tif_select = self._resolve("JLINK_TIF_Select", "JLINKARM_TIF_Select")
        self._fn_tif_select.argtypes = [ctypes.c_int]
        self._fn_tif_select.restype = ctypes.c_int

        self._fn_exec_command = self._resolve("JLINK_ExecCommand", "JLINKARM_ExecCommand")
        self._fn_exec_command.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        self._fn_exec_command.restype = ctypes.c_int

        self._fn_set_speed = self._resolve("JLINK_SetSpeed", "JLINKARM_SetSpeed")
        self._fn_set_speed.argtypes = [ctypes.c_int]
        self._fn_set_speed.restype = None

        self._fn_connect = self._resolve("JLINK_Connect", "JLINKARM_Connect")
        self._fn_connect.argtypes = []
        self._fn_connect.restype = ctypes.c_int

        self._fn_read_mem_ex = self._resolve("JLINK_ReadMemEx", "JLINKARM_ReadMemEx")
        self._fn_read_mem_ex.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        self._fn_read_mem_ex.restype = ctypes.c_int

        self._fn_write_mem_ex = self._resolve("JLINK_WriteMemEx", "JLINKARM_WriteMemEx")
        self._fn_write_mem_ex.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        self._fn_write_mem_ex.restype = ctypes.c_int

        self._fn_is_connected = self._resolve_optional("JLINK_IsConnected", "JLINKARM_IsConnected")
        if self._fn_is_connected is not None:
            self._fn_is_connected.argtypes = []
            self._fn_is_connected.restype = ctypes.c_char

        self._fn_get_dll_version = self._resolve_optional(
            "JLINK_GetDLLVersion", "JLINKARM_GetDLLVersion"
        )
        if self._fn_get_dll_version is not None:
            self._fn_get_dll_version.argtypes = []
            self._fn_get_dll_version.restype = ctypes.c_uint32

        # Native SEGGER "Target Device Settings" dialog used by tools such
        # as J-Scope. It can be called before JLINK_Open().
        self._fn_device_select_dialog = self._resolve_optional(
            "JLINK_DEVICE_SelectDialog", "JLINKARM_DEVICE_SelectDialog"
        )
        if self._fn_device_select_dialog is not None:
            self._fn_device_select_dialog.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.POINTER(_JLinkDeviceSelectInfo),
            ]
            self._fn_device_select_dialog.restype = ctypes.c_int

        self._fn_device_get_info = self._resolve_optional(
            "JLINK_DEVICE_GetInfo", "JLINKARM_DEVICE_GetInfo"
        )
        if self._fn_device_get_info is not None:
            self._fn_device_get_info.argtypes = [
                ctypes.c_int,
                ctypes.POINTER(_JLinkDeviceInfo),
            ]
            self._fn_device_get_info.restype = ctypes.c_int

    def select_target_device(
        self, dll_path: str, parent_hwnd: int | None = None
    ) -> TargetDeviceInfo | None:
        """Show SEGGER's native Target Device Settings dialog.

        JLINK_DEVICE_SelectDialog() only returns a database index; it does
        not select the device inside the DLL. We therefore resolve the index
        with JLINK_DEVICE_GetInfo() and let connect() explicitly issue
        ``Device=<name>`` afterwards.

        Returns None when the user cancels the dialog.
        """
        wanted = str(Path(dll_path).expanduser())
        if self._dll is None or self._dll_path != wanted:
            self.close()
            self.load_library(wanted)

        if self._fn_device_select_dialog is None or self._fn_device_get_info is None:
            raise JLinkError(
                "This J-Link DLL does not export DEVICE_SelectDialog / DEVICE_GetInfo. "
                "Please use a current SEGGER J-Link DLL."
            )

        sel = _JLinkDeviceSelectInfo()
        hwnd = ctypes.c_void_p(parent_hwnd or 0)
        index = int(self._fn_device_select_dialog(hwnd, 0, ctypes.byref(sel)))
        if index < 0:
            return None

        info = _JLinkDeviceInfo()
        rc = int(self._fn_device_get_info(index, ctypes.byref(info)))
        if rc != 0:
            raise JLinkError(f"JLINK_DEVICE_GetInfo failed for index {index}, rc={rc}")

        name = info.sName.decode("utf-8", errors="replace") if info.sName else ""
        manufacturer = (
            info.sManu.decode("utf-8", errors="replace") if info.sManu else ""
        )
        if not name:
            raise JLinkError(f"Selected device index {index} has no device name")

        return TargetDeviceInfo(
            index=index,
            name=name,
            manufacturer=manufacturer,
            core_id=int(info.CoreId),
            core=int(info.Core),
            flash_addr=int(info.FlashAddr),
            flash_size=int(info.FlashSize),
            ram_addr=int(info.RAMAddr),
            ram_size=int(info.RAMSize),
            core_index=int(sel.CoreIndex),
        )

    def open(self) -> None:
        if self._dll is None:
            raise JLinkError("Load a J-Link DLL first")
        if self._is_open:
            return

        error_ptr = self._fn_open()
        if error_ptr:
            message = error_ptr.decode("utf-8", errors="replace")
            raise JLinkError(f"JLINK_Open failed: {message}")
        self._is_open = True

    def close(self) -> None:
        if self._dll is not None and self._is_open:
            try:
                self._fn_close()
            finally:
                self._is_open = False
                self._is_target_connected = False

    def exec_command(self, command: str) -> tuple[int, str]:
        self._require_open()
        out = ctypes.create_string_buffer(1024)
        rc = self._fn_exec_command(command.encode("ascii"), out, len(out))
        text = out.value.decode("utf-8", errors="replace")
        return rc, text

    def connect(self, config: ConnectionConfig) -> None:
        if self._dll is None or self._dll_path != str(Path(config.dll_path).expanduser()):
            self.close()
            self.load_library(config.dll_path)

        self.open()

        interface = config.interface.strip().upper()
        if interface == "SWD":
            tif = self.TIF_SWD
        elif interface == "JTAG":
            tif = self.TIF_JTAG
        else:
            raise JLinkError(f"Unsupported interface: {config.interface}")

        rc = self._fn_tif_select(tif)
        if rc < 0:
            raise JLinkError(f"JLINK_TIF_Select failed, rc={rc}")

        device = config.device.strip()
        if device:
            rc, out = self.exec_command(f"Device={device}")
            if rc < 0:
                raise JLinkError(
                    f"Failed to select device '{device}', rc={rc}, output={out}"
                )
        else:
            # SEGGER's generic IDE behavior: if no target device/core is
            # specified, J-Link DLL is allowed to present its own target
            # device selection dialog during JLINK_Connect(). Explicitly
            # make sure that dialog suppression is disabled when supported.
            try:
                self.exec_command("HideDeviceSelection = 0")
            except Exception:
                # Older DLLs may not know this command. The default DLL
                # behavior is still to show device selection when needed.
                pass

        if config.speed_khz <= 0:
            raise JLinkError("SWD/JTAG speed must be > 0 kHz")
        self._fn_set_speed(int(config.speed_khz))

        rc = self._fn_connect()
        if rc < 0:
            raise JLinkError(f"JLINK_Connect failed, rc={rc}")

        self._is_target_connected = True

    def read_memory(self, address: int, size: int) -> bytes:
        self._require_target()
        self._validate_range(address, size)

        buffer_type = ctypes.c_ubyte * size
        buffer = buffer_type()
        rc = self._fn_read_mem_ex(
            ctypes.c_uint32(address),
            ctypes.c_uint32(size),
            ctypes.cast(buffer, ctypes.c_void_p),
            ctypes.c_uint32(self.ACCESS_WIDTH_AUTO),
        )
        if rc < 0:
            raise JLinkError(f"JLINK_ReadMemEx failed: addr=0x{address:08X}, size={size}, rc={rc}")
        if rc != size:
            raise JLinkError(
                f"JLINK_ReadMemEx partial read: requested={size}, returned={rc}, "
                f"addr=0x{address:08X}"
            )
        return bytes(buffer)

    def write_memory(self, address: int, data: bytes) -> int:
        self._require_target()
        if not data:
            raise JLinkError("No data to write")
        self._validate_range(address, len(data))

        buffer_type = ctypes.c_ubyte * len(data)
        buffer = buffer_type.from_buffer_copy(data)
        rc = self._fn_write_mem_ex(
            ctypes.c_uint32(address),
            ctypes.c_uint32(len(data)),
            ctypes.cast(buffer, ctypes.c_void_p),
            ctypes.c_uint32(self.ACCESS_WIDTH_AUTO),
        )
        if rc < 0:
            raise JLinkError(f"JLINK_WriteMemEx failed: addr=0x{address:08X}, size={len(data)}, rc={rc}")
        if rc != len(data):
            raise JLinkError(
                f"JLINK_WriteMemEx partial write: requested={len(data)}, returned={rc}, "
                f"addr=0x{address:08X}"
            )
        return rc

    def write_and_verify(self, address: int, data: bytes) -> bytes:
        self.write_memory(address, data)
        readback = self.read_memory(address, len(data))
        if readback != data:
            raise JLinkError(
                f"Write verify mismatch at 0x{address:08X}: "
                f"write={data.hex(' ')}, read={readback.hex(' ')}"
            )
        return readback

    def get_dll_version_text(self) -> str:
        if self._fn_get_dll_version is None:
            return "unknown"
        raw = int(self._fn_get_dll_version())
        # SEGGER versions are commonly encoded as e.g. 83800 -> V8.38.
        if raw <= 0:
            return str(raw)
        major = raw // 10000
        minor = (raw % 10000) // 100
        patch = raw % 100
        suffix = f".{patch:02d}" if patch else ""
        return f"V{major}.{minor:02d}{suffix} ({raw})"

    def _require_open(self) -> None:
        if not self._is_open:
            raise JLinkError("J-Link session is not open")

    def _require_target(self) -> None:
        self._require_open()
        if not self.is_target_connected:
            raise JLinkError("Target is not connected")

    @staticmethod
    def _validate_range(address: int, size: int) -> None:
        if address < 0 or address > 0xFFFFFFFF:
            raise JLinkError(f"Address is outside V0.1 32-bit range: 0x{address:X}")
        if size <= 0:
            raise JLinkError("Memory size must be > 0")
        if address + size - 1 > 0xFFFFFFFF:
            raise JLinkError("Memory access crosses 32-bit address space")
