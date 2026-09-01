from __future__ import annotations

from dataclasses import dataclass
import re
import struct
from typing import Iterable

from core.datatype import decode_value, get_type_info


@dataclass(frozen=True)
class ScopeChannelSpec:
    channel_id: int
    name: str
    address: int
    type_name: str
    enabled: bool = True

    @property
    def size(self) -> int:
        return get_type_info(self.type_name).size


@dataclass(frozen=True)
class ScopeReadBlock:
    address: int
    size: int
    channels: tuple[ScopeChannelSpec, ...]


class ScopeReadPlanner:
    """Create deterministic contiguous HSS memory blocks.

    Only overlapping/adjacent regions are merged. This keeps each HSS block compact and
    avoids reading unrelated memory-mapped registers merely to reduce descriptor count.
    """

    def __init__(self, max_block_bytes: int = 256) -> None:
        self.max_block_bytes = max(1, int(max_block_bytes))

    def plan(self, channels: Iterable[ScopeChannelSpec]) -> list[ScopeReadBlock]:
        items = sorted(
            (c for c in channels if c.enabled),
            key=lambda c: (c.address, c.size, c.channel_id),
        )
        if not items:
            return []

        result: list[ScopeReadBlock] = []
        start = items[0].address
        end = start + items[0].size
        group = [items[0]]
        for channel in items[1:]:
            c_start = channel.address
            c_end = c_start + channel.size
            candidate_end = max(end, c_end)
            if c_start <= end and candidate_end - start <= self.max_block_bytes:
                group.append(channel)
                end = candidate_end
            else:
                result.append(ScopeReadBlock(start, end - start, tuple(group)))
                start = c_start
                end = c_end
                group = [channel]
        result.append(ScopeReadBlock(start, end - start, tuple(group)))
        return result


class HssFrameDecoder:
    """Decode the SEGGER HSS byte stream.

    With ``JLINK_HSS_FLAG_TIMESTAMP_US`` enabled, every HSS sample returned by
    ``JLINK_HSS_Read()`` starts with a little-endian U32 timestamp in microseconds,
    followed by the configured memory blocks concatenated in descriptor order::

        [timestamp_us:U32][block0 bytes][block1 bytes]...

    V0.3 incorrectly treated the timestamp as sampled target data. For a constant
    U32 value this produced alternating ``timestamp, value, timestamp, value`` points
    and therefore the characteristic dense triangular/ramp waveform.
    """

    TIMESTAMP_SIZE = 4

    def __init__(self, blocks: list[ScopeReadBlock]) -> None:
        if not blocks:
            raise ValueError("HSS requires at least one memory block")
        self.blocks = list(blocks)
        self.payload_size = sum(b.size for b in self.blocks)
        if self.payload_size <= 0:
            raise ValueError("Invalid HSS payload size")
        self.frame_size = self.TIMESTAMP_SIZE + self.payload_size
        self._remainder = bytearray()
        self._timestamp_wrap_base = 0
        self._last_timestamp_raw: int | None = None
        self._first_timestamp_us: int | None = None

    def reset(self) -> None:
        self._remainder.clear()
        self._timestamp_wrap_base = 0
        self._last_timestamp_raw = None
        self._first_timestamp_us = None

    def _decode_timestamp_s(self, raw: bytes) -> float:
        raw_us = struct.unpack("<I", raw)[0]
        if self._last_timestamp_raw is not None:
            # U32 microsecond timestamp wraps roughly every 71.6 minutes.
            if raw_us < self._last_timestamp_raw and self._last_timestamp_raw - raw_us > 0x80000000:
                self._timestamp_wrap_base += 1 << 32
        self._last_timestamp_raw = raw_us
        total_us = self._timestamp_wrap_base + raw_us
        if self._first_timestamp_us is None:
            self._first_timestamp_us = total_us
        return (total_us - self._first_timestamp_us) / 1_000_000.0

    def feed(self, data: bytes) -> tuple[list[float], list[dict[int, float | int]]]:
        if data:
            self._remainder.extend(data)
        complete = len(self._remainder) // self.frame_size
        if complete <= 0:
            return [], []

        consumed = complete * self.frame_size
        payload = bytes(self._remainder[:consumed])
        del self._remainder[:consumed]

        times: list[float] = []
        rows: list[dict[int, float | int]] = []
        for frame_index in range(complete):
            base = frame_index * self.frame_size
            timestamp_raw = payload[base : base + self.TIMESTAMP_SIZE]
            times.append(self._decode_timestamp_s(timestamp_raw))
            cursor = base + self.TIMESTAMP_SIZE
            values: dict[int, float | int] = {}
            for block in self.blocks:
                raw_block = payload[cursor : cursor + block.size]
                cursor += block.size
                for channel in block.channels:
                    offset = channel.address - block.address
                    raw = raw_block[offset : offset + channel.size]
                    values[channel.channel_id] = decode_value(raw, channel.type_name)
            rows.append(values)
        return times, rows


@dataclass(frozen=True)
class RttField:
    kind: str
    size: int
    type_name: str | None

    @property
    def is_timestamp(self) -> bool:
        return self.kind == "t"


@dataclass(frozen=True)
class JScopeRttFormat:
    channel_name: str
    fields: tuple[RttField, ...]

    @property
    def packet_size(self) -> int:
        return sum(f.size for f in self.fields)

    @property
    def has_timestamp(self) -> bool:
        return bool(self.fields and self.fields[0].is_timestamp)

    @property
    def value_fields(self) -> tuple[RttField, ...]:
        return tuple(f for f in self.fields if not f.is_timestamp)


_RTT_TOKEN_RE = re.compile(r"([tbfiu])(\d+)", re.IGNORECASE)


def parse_jscope_rtt_channel_name(name: str) -> JScopeRttFormat:
    """Parse J-Scope RTT-normal names such as JScope_t4f4u2i4."""
    if not name.lower().startswith("jscope_"):
        raise ValueError("RTT channel name must start with JScope_")
    format_text = name[len("JScope_") :]
    if not format_text:
        raise ValueError("JScope RTT format is empty")

    fields: list[RttField] = []
    pos = 0
    for match in _RTT_TOKEN_RE.finditer(format_text):
        if match.start() != pos:
            raise ValueError(f"Invalid J-Scope RTT format near '{format_text[pos:]}'")
        kind = match.group(1).lower()
        size = int(match.group(2))
        pos = match.end()

        if kind == "t":
            if size != 4:
                raise ValueError("J-Scope timestamp must be t4")
            type_name = None
        elif kind == "b":
            if size != 1:
                raise ValueError("J-Scope boolean must be b1")
            type_name = "uint8"
        elif kind == "f":
            if size != 4:
                raise ValueError("J-Scope float must be f4")
            type_name = "float"
        elif kind == "i":
            if size not in (1, 2, 4):
                raise ValueError("J-Scope signed integer sizes are 1, 2, 4")
            type_name = {1: "int8", 2: "int16", 4: "int32"}[size]
        elif kind == "u":
            if size not in (1, 2, 4):
                raise ValueError("J-Scope unsigned integer sizes are 1, 2, 4")
            type_name = {1: "uint8", 2: "uint16", 4: "uint32"}[size]
        else:  # pragma: no cover
            raise ValueError(f"Unsupported J-Scope field type: {kind}")
        fields.append(RttField(kind, size, type_name))

    if pos != len(format_text):
        raise ValueError(f"Invalid J-Scope RTT format near '{format_text[pos:]}'")
    if not fields:
        raise ValueError("J-Scope RTT format contains no fields")
    if any(f.is_timestamp for f in fields[1:]):
        raise ValueError("J-Scope timestamp may only be the first field")
    if len(fields) > 12:
        raise ValueError("J-Scope RTT-normal supports at most 12 fields including timestamp")
    return JScopeRttFormat(channel_name=name, fields=tuple(fields))


class JScopeRttPacketDecoder:
    """Stream decoder for J-Scope RTT-normal packets."""

    def __init__(self, fmt: JScopeRttFormat) -> None:
        self.format = fmt
        self._remainder = bytearray()
        self._timestamp_wrap_base = 0
        self._last_timestamp_raw: int | None = None
        self._first_timestamp_us: int | None = None
        self._sample_index = 0

    def reset(self) -> None:
        self._remainder.clear()
        self._timestamp_wrap_base = 0
        self._last_timestamp_raw = None
        self._first_timestamp_us = None
        self._sample_index = 0

    def feed(self, data: bytes) -> tuple[list[float], dict[int, list[float | int]]]:
        if data:
            self._remainder.extend(data)
        packet_size = self.format.packet_size
        complete = len(self._remainder) // packet_size
        if complete <= 0:
            return [], {}

        consumed = complete * packet_size
        payload = bytes(self._remainder[:consumed])
        del self._remainder[:consumed]

        times: list[float] = []
        value_fields = self.format.value_fields
        values: dict[int, list[float | int]] = {
            i + 1: [] for i in range(len(value_fields))
        }

        for packet_index in range(complete):
            cursor = packet_index * packet_size
            timestamp_s: float | None = None
            value_index = 0
            for field in self.format.fields:
                raw = payload[cursor : cursor + field.size]
                cursor += field.size
                if field.is_timestamp:
                    raw_us = struct.unpack("<I", raw)[0]
                    if self._last_timestamp_raw is not None:
                        if raw_us < self._last_timestamp_raw and self._last_timestamp_raw - raw_us > 0x80000000:
                            self._timestamp_wrap_base += 1 << 32
                    self._last_timestamp_raw = raw_us
                    total_us = self._timestamp_wrap_base + raw_us
                    if self._first_timestamp_us is None:
                        self._first_timestamp_us = total_us
                    timestamp_s = (total_us - self._first_timestamp_us) / 1_000_000.0
                    continue

                value_index += 1
                if field.kind == "b":
                    value: float | int = 1 if raw[0] else 0
                else:
                    assert field.type_name is not None
                    value = decode_value(raw, field.type_name)
                values[value_index].append(value)

            if timestamp_s is None:
                # J-Scope itself falls back to sample numbering when no target timestamp
                # is supplied. Keep that exact semantic rather than inventing host times.
                timestamp_s = float(self._sample_index)
            times.append(timestamp_s)
            self._sample_index += 1

        return times, values
