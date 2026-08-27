from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Any, Dict


@dataclass(frozen=True)
class DataTypeInfo:
    name: str
    struct_format: str
    size: int
    integer: bool
    signed: bool | None


# V0.1 targets the normal little-endian Cortex-M memory layout.
_DATA_TYPES: Dict[str, DataTypeInfo] = {
    "int8": DataTypeInfo("int8", "<b", 1, True, True),
    "uint8": DataTypeInfo("uint8", "<B", 1, True, False),
    "int16": DataTypeInfo("int16", "<h", 2, True, True),
    "uint16": DataTypeInfo("uint16", "<H", 2, True, False),
    "int32": DataTypeInfo("int32", "<i", 4, True, True),
    "uint32": DataTypeInfo("uint32", "<I", 4, True, False),
    "int64": DataTypeInfo("int64", "<q", 8, True, True),
    "uint64": DataTypeInfo("uint64", "<Q", 8, True, False),
    "float": DataTypeInfo("float", "<f", 4, False, None),
    "double": DataTypeInfo("double", "<d", 8, False, None),
}


def supported_types() -> list[str]:
    return list(_DATA_TYPES.keys())


def get_type_info(type_name: str) -> DataTypeInfo:
    try:
        return _DATA_TYPES[type_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported data type: {type_name}") from exc


def decode_value(raw: bytes, type_name: str) -> Any:
    info = get_type_info(type_name)
    if len(raw) != info.size:
        raise ValueError(
            f"{type_name} requires {info.size} bytes, got {len(raw)} bytes"
        )
    return struct.unpack(info.struct_format, raw)[0]


def encode_value(value_text: str, type_name: str) -> bytes:
    info = get_type_info(type_name)
    text = value_text.strip()
    if not text:
        raise ValueError("Value is empty")

    try:
        if info.integer:
            # int(..., 0) accepts decimal as well as 0x / 0b / 0o input.
            value = int(text, 0)
        else:
            value = float(text)
            if not math.isfinite(value):
                raise ValueError("NaN/Inf writes are disabled in V0.1")
        return struct.pack(info.struct_format, value)
    except (ValueError, struct.error, OverflowError) as exc:
        raise ValueError(f"Invalid {type_name} value: {value_text}") from exc


def format_value(value: Any, type_name: str) -> str:
    info = get_type_info(type_name)
    if info.integer:
        return str(value)
    # Enough significant digits for useful round-trip display without excessive noise.
    return f"{value:.9g}"
