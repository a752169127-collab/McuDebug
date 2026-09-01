from __future__ import annotations

import math
import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal, Slot, Qt

from core.datatype import decode_value, encode_value, format_value, get_type_info
from core.scope import (
    HssFrameDecoder,
    JScopeRttPacketDecoder,
    ScopeChannelSpec,
    ScopeReadPlanner,
    parse_jscope_rtt_channel_name,
)
from core.watch import MemoryReadPlanner, RunningStats, WatchVariableSpec
from debugger.jlink_backend import ConnectionConfig, JLinkBackend


class JLinkWorker(QObject):
    connection_changed = Signal(bool, str)
    manual_read_done = Signal(int, bool, object, str, str)
    manual_write_done = Signal(int, bool, object, str, str)

    watch_samples = Signal(object, float, float)
    watch_error = Signal(str)
    sampling_state_changed = Signal(bool)

    # Scope sends chunks, not one Qt signal per sample.
    # args: times(list[float]), values(dict[channel_id,list]), actual_hz, x_is_time
    scope_samples = Signal(object, object, float, bool)
    scope_error = Signal(str)
    scope_state_changed = Signal(bool, str)
    # RTT-normal discovers its channels from JScope_<FORMAT>.
    # args: channel name, list[dict{id,name,type_name}], has_timestamp
    scope_rtt_format = Signal(str, object, bool)

    # Watch UI remains capped at 25 Hz. Scope worker->GUI delivery is intentionally
    # independent from viewport FPS. V0.4.1 forwarded up to 60 chunks/s into the
    # GUI thread when FPS=60, competing with the 60 Hz presentation timer and
    # creating event-loop jitter. Raw HSS/RTT sampling is unchanged; samples are
    # simply batched into fewer, larger GUI chunks.
    GUI_SNAPSHOT_HZ = 25.0
    SCOPE_EMIT_MAX_HZ = 30.0
    SCOPE_DEFAULT_GUI_HZ = 20.0
    SCOPE_POLL_MS = 5

    def __init__(self) -> None:
        super().__init__()
        self._jlink = JLinkBackend()

        # Watch state.
        self._timer: QTimer | None = None
        self._watch_specs: list[WatchVariableSpec] = []
        self._planner = MemoryReadPlanner(max_gap_bytes=0, max_block_bytes=256)
        self._sample_interval_ms = 100
        self._sampling_started_at = 0.0
        self._sample_count = 0
        self._watch_stats: dict[int, RunningStats] = {}
        self._watch_signatures: dict[int, tuple[int, str]] = {}
        self._latest_values: dict[int, float | int] = {}
        self._gui_snapshot_period_s = 1.0 / self.GUI_SNAPSHOT_HZ
        self._scope_emit_period_s = 1.0 / self.SCOPE_DEFAULT_GUI_HZ
        self._last_gui_emit_at = 0.0
        self._rate_window_started_at = 0.0
        self._rate_window_samples = 0
        self._actual_hz = 0.0

        # Scope state. HSS/RTT acquisition stays in this same J-Link owner thread.
        self._scope_timer: QTimer | None = None
        self._scope_source = ""
        self._scope_specs: list[ScopeChannelSpec] = []
        self._scope_period_us = 1000
        self._scope_hss_decoder: HssFrameDecoder | None = None
        self._scope_rtt_decoder: JScopeRttPacketDecoder | None = None
        self._scope_rtt_buffer_index: int | None = None
        self._scope_pending_times: list[float] = []
        self._scope_pending_values: dict[int, list[float | int]] = {}
        self._scope_last_emit_at = 0.0
        self._scope_rate_started_at = 0.0
        self._scope_rate_samples = 0
        self._scope_actual_hz = 0.0
        self._scope_x_is_time = True
        self._scope_rtt_find_deadline = 0.0

    # ---------- Connection ----------
    @Slot(object)
    def connect_target(self, config: ConnectionConfig) -> None:
        try:
            self._stop_watch_sampling_internal()
            self._stop_scope_sampling_internal()
            self._jlink.connect(config)
            self.connection_changed.emit(
                True,
                f"Connected | DLL {self._jlink.get_dll_version_text()} | "
                f"{config.interface} {config.speed_khz} kHz | {config.device}",
            )
        except Exception as exc:
            self._jlink.close()
            self.connection_changed.emit(False, str(exc))

    @Slot()
    def disconnect_target(self) -> None:
        try:
            self._stop_watch_sampling_internal()
            self._stop_scope_sampling_internal()
            self._jlink.close()
            self.connection_changed.emit(False, "Disconnected")
        except Exception as exc:
            self.connection_changed.emit(False, f"Disconnect error: {exc}")

    # ---------- Manual ----------
    @Slot(int, object, str)
    def read_typed(self, request_id: int, address: int, type_name: str) -> None:
        try:
            address = int(address)
            info = get_type_info(type_name)
            raw = self._jlink.read_memory(address, info.size)
            value = decode_value(raw, type_name)
            self.manual_read_done.emit(request_id, True, value, raw.hex(" ").upper(), "")
        except Exception as exc:
            self.manual_read_done.emit(request_id, False, None, "", str(exc))

    @Slot(int, object, str, str)
    def write_typed(self, request_id: int, address: int, type_name: str, value_text: str) -> None:
        try:
            address = int(address)
            data = encode_value(value_text, type_name)
            readback = self._jlink.write_and_verify(address, data)
            value = decode_value(readback, type_name)
            self.manual_write_done.emit(request_id, True, value, readback.hex(" ").upper(), "")
        except Exception as exc:
            self.manual_write_done.emit(request_id, False, None, "", str(exc))

    # ---------- Watch ----------
    @Slot(object, int)
    def start_watch_sampling(self, specs: list[WatchVariableSpec], interval_ms: int) -> None:
        try:
            if not self._jlink.is_target_connected:
                raise RuntimeError("Target is not connected")
            if interval_ms < 1:
                raise ValueError("Watch sample interval must be >= 1 ms")
            self._stop_scope_sampling_internal()
            self._configure_watch_specs(specs)
            if not self._watch_specs:
                raise ValueError("No enabled Watch variables")

            self._sample_interval_ms = int(interval_ms)
            self._sampling_started_at = time.perf_counter()
            self._sample_count = 0
            self._last_gui_emit_at = 0.0
            self._reset_rate_window(self._sampling_started_at)

            if self._timer is None:
                self._timer = QTimer(self)
                self._timer.setTimerType(Qt.TimerType.PreciseTimer)
                self._timer.timeout.connect(self._sample_watch_once)
            self._timer.setInterval(self._sample_interval_ms)
            self._timer.start()
            self.sampling_state_changed.emit(True)
            self._sample_watch_once()
        except Exception as exc:
            self._stop_watch_sampling_internal()
            self.watch_error.emit(str(exc))

    @Slot(object)
    def update_watch_specs(self, specs: list[WatchVariableSpec]) -> None:
        self._configure_watch_specs(specs)
        if self._timer is not None and self._timer.isActive() and not self._watch_specs:
            self._stop_watch_sampling_internal()

    @Slot(int)
    def update_watch_interval(self, interval_ms: int) -> None:
        if interval_ms < 1:
            return
        self._sample_interval_ms = int(interval_ms)
        if self._timer is not None and self._timer.isActive():
            self._timer.setInterval(self._sample_interval_ms)
            self._reset_rate_window(time.perf_counter())

    @Slot()
    def clear_watch_statistics(self) -> None:
        for stats in self._watch_stats.values():
            stats.clear()
        if self._timer is not None and self._timer.isActive():
            self._emit_watch_snapshot(time.perf_counter(), force=True)

    @Slot()
    def stop_watch_sampling(self) -> None:
        self._stop_watch_sampling_internal()

    def _configure_watch_specs(self, specs: list[WatchVariableSpec]) -> None:
        all_specs = list(specs)
        incoming_ids = {v.row_id for v in all_specs}
        for row_id in list(self._watch_signatures):
            if row_id not in incoming_ids:
                self._watch_signatures.pop(row_id, None)
                self._watch_stats.pop(row_id, None)
                self._latest_values.pop(row_id, None)
        for var in all_specs:
            get_type_info(var.type_name)
            if not 0 <= var.address <= 0xFFFFFFFF:
                raise ValueError(f"Invalid Watch address: {var.name}")
            signature = (int(var.address), str(var.type_name))
            if self._watch_signatures.get(var.row_id) != signature:
                self._watch_signatures[var.row_id] = signature
                self._watch_stats[var.row_id] = RunningStats()
                self._latest_values.pop(var.row_id, None)
            else:
                self._watch_stats.setdefault(var.row_id, RunningStats())
        self._watch_specs = [v for v in all_specs if v.enabled]

    @Slot()
    def _sample_watch_once(self) -> None:
        try:
            if not self._watch_specs:
                return
            blocks = self._planner.plan(self._watch_specs)
            for block in blocks:
                raw_block = self._jlink.read_memory(block.address, block.size)
                for var in block.variables:
                    offset = var.address - block.address
                    raw = raw_block[offset : offset + var.size]
                    value = decode_value(raw, var.type_name)
                    self._latest_values[var.row_id] = value
                    self._watch_stats.setdefault(var.row_id, RunningStats()).add(value)
            completed_at = time.perf_counter()
            self._sample_count += 1
            self._rate_window_samples += 1
            self._update_actual_rate(completed_at)
            if self._last_gui_emit_at <= 0.0 or completed_at - self._last_gui_emit_at >= self._gui_snapshot_period_s:
                self._emit_watch_snapshot(completed_at)
        except Exception as exc:
            self.watch_error.emit(str(exc))
            self._stop_watch_sampling_internal()

    def _emit_watch_snapshot(self, now: float, *, force: bool = False) -> None:
        if not force and self._last_gui_emit_at > 0.0 and now - self._last_gui_emit_at < self._gui_snapshot_period_s:
            return
        results: list[dict[str, Any]] = []
        for var in self._watch_specs:
            if var.row_id not in self._latest_values:
                continue
            value = self._latest_values[var.row_id]
            count, avg, minimum, maximum = self._watch_stats.setdefault(var.row_id, RunningStats()).snapshot()
            results.append({
                "row_id": var.row_id,
                "name": var.name,
                "address": var.address,
                "type_name": var.type_name,
                "value": value,
                "formatted": format_value(value, var.type_name),
                "count": count,
                "average": avg,
                "minimum": minimum,
                "maximum": maximum,
            })
        elapsed = max(0.0, now - self._sampling_started_at)
        actual_hz = self._actual_hz if self._actual_hz > 0.0 else (self._sample_count / elapsed if elapsed > 0 else 0.0)
        self._last_gui_emit_at = now
        self.watch_samples.emit(results, elapsed, actual_hz)

    def _reset_rate_window(self, now: float) -> None:
        self._rate_window_started_at = now
        self._rate_window_samples = 0
        self._actual_hz = 0.0

    def _update_actual_rate(self, now: float) -> None:
        elapsed = now - self._rate_window_started_at
        if elapsed < 0.5:
            return
        if elapsed > 0:
            measured = self._rate_window_samples / elapsed
            if math.isfinite(measured):
                self._actual_hz = measured
        self._rate_window_started_at = now
        self._rate_window_samples = 0

    def _stop_watch_sampling_internal(self) -> None:
        if self._timer is not None and self._timer.isActive():
            self._emit_watch_snapshot(time.perf_counter(), force=True)
            self._timer.stop()
        self.sampling_state_changed.emit(False)

    @Slot(int)
    def update_scope_emit_fps(self, fps: int) -> None:
        # This controls only how often accumulated Scope chunks cross into the
        # GUI thread. HSS/RTT acquisition itself continues at its own rate.
        fps = max(1, min(int(self.SCOPE_EMIT_MAX_HZ), int(fps)))
        self._scope_emit_period_s = 1.0 / float(fps)

    # ---------- Scope ----------
    @Slot(str, object, int)
    def start_scope_sampling(self, source: str, specs: list[ScopeChannelSpec], sample_hz: int) -> None:
        try:
            if not self._jlink.is_target_connected:
                raise RuntimeError("Target is not connected")
            self._stop_watch_sampling_internal()
            self._stop_scope_sampling_internal()

            source = source.strip().upper()
            self._scope_source = source
            started_at = time.perf_counter()
            self._scope_pending_times.clear()
            self._scope_pending_values.clear()
            self._scope_last_emit_at = 0.0
            self._scope_rate_started_at = started_at
            self._scope_rate_samples = 0
            self._scope_actual_hz = 0.0
            self._scope_x_is_time = True

            if source == "HSS":
                enabled = [s for s in specs if s.enabled]
                if not enabled:
                    raise ValueError("HSS Scope requires at least one enabled channel")
                if not 1 <= int(sample_hz) <= 10000:
                    raise ValueError("HSS sample rate must be 1..10000 Hz")
                for spec in enabled:
                    get_type_info(spec.type_name)
                self._scope_specs = enabled
                blocks = ScopeReadPlanner(max_block_bytes=256).plan(enabled)
                self._scope_hss_decoder = HssFrameDecoder(blocks)
                self._scope_period_us = max(1, round(1_000_000 / int(sample_hz)))
                self._jlink.hss_start([(b.address, b.size) for b in blocks], self._scope_period_us)
                self._scope_rtt_decoder = None
                self._scope_rtt_buffer_index = None
                self._start_scope_poll_timer()
                self.scope_state_changed.emit(True, f"HSS | requested {1_000_000 / self._scope_period_us:.6g} Hz")
                return

            if source == "RTT":
                # RTT-normal is target-defined, just like J-Scope: no AXF symbol selection
                # is required and the first JScope_<FORMAT> up channel defines the packet.
                self._scope_specs = []
                self._scope_hss_decoder = None
                self._jlink.rtt_start()
                self._scope_rtt_decoder = None
                self._scope_rtt_buffer_index = None
                self._scope_rtt_find_deadline = time.perf_counter() + 3.0
                self._start_scope_poll_timer()
                self.scope_state_changed.emit(True, "RTT | searching JScope_<FORMAT> up channel")
                return

            raise ValueError(f"Unknown Scope source: {source}")
        except Exception as exc:
            self._stop_scope_sampling_internal()
            self.scope_error.emit(str(exc))

    @Slot()
    def stop_scope_sampling(self) -> None:
        self._stop_scope_sampling_internal()

    def _start_scope_poll_timer(self) -> None:
        if self._scope_timer is None:
            self._scope_timer = QTimer(self)
            self._scope_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._scope_timer.timeout.connect(self._poll_scope)
        self._scope_timer.setInterval(self.SCOPE_POLL_MS)
        self._scope_timer.start()

    @Slot()
    def _poll_scope(self) -> None:
        try:
            if self._scope_source == "HSS":
                self._poll_hss()
            elif self._scope_source == "RTT":
                self._poll_rtt()
        except Exception as exc:
            self.scope_error.emit(str(exc))
            self._stop_scope_sampling_internal()

    def _poll_hss(self) -> None:
        assert self._scope_hss_decoder is not None
        raw = self._jlink.hss_read()
        times, rows = self._scope_hss_decoder.feed(raw)
        if rows:
            values: dict[int, list[float | int]] = {}
            for row in rows:
                for channel_id, value in row.items():
                    values.setdefault(channel_id, []).append(value)
            self._scope_accumulate(times, values, True)

    def _poll_rtt(self) -> None:
        if self._scope_rtt_decoder is None:
            buffers = self._jlink.rtt_list_up_buffers()
            match = next((b for b in buffers if b[1].lower().startswith("jscope_")), None)
            if match is None:
                if time.perf_counter() >= self._scope_rtt_find_deadline:
                    raise RuntimeError("No RTT up channel named JScope_<FORMAT> found within 3 s")
                return
            index, name, _size, _flags = match
            fmt = parse_jscope_rtt_channel_name(name)
            self._scope_rtt_decoder = JScopeRttPacketDecoder(fmt)
            self._scope_rtt_buffer_index = index
            channels = []
            for i, field in enumerate(fmt.value_fields, start=1):
                channels.append({
                    "channel_id": i,
                    "name": f"RTT_Value{i}",
                    "type_name": field.type_name or "uint32",
                })
            self._scope_x_is_time = fmt.has_timestamp
            self.scope_rtt_format.emit(name, channels, fmt.has_timestamp)

        assert self._scope_rtt_decoder is not None
        assert self._scope_rtt_buffer_index is not None
        raw = self._jlink.rtt_read(self._scope_rtt_buffer_index)
        times, values = self._scope_rtt_decoder.feed(raw)
        if times:
            self._scope_accumulate(times, values, self._scope_x_is_time)

    def _scope_accumulate(self, times, values, x_is_time: bool) -> None:
        if not times:
            return
        self._scope_pending_times.extend(times)
        for channel_id, seq in values.items():
            self._scope_pending_values.setdefault(int(channel_id), []).extend(seq)
        self._scope_rate_samples += len(times)

        now = time.perf_counter()
        rate_elapsed = now - self._scope_rate_started_at
        if rate_elapsed >= 0.5:
            self._scope_actual_hz = self._scope_rate_samples / rate_elapsed if rate_elapsed > 0 else 0.0
            self._scope_rate_started_at = now
            self._scope_rate_samples = 0

        if self._scope_last_emit_at <= 0.0 or now - self._scope_last_emit_at >= self._scope_emit_period_s:
            self._emit_scope_chunk(now, x_is_time)

    def _emit_scope_chunk(self, now: float, x_is_time: bool, *, force: bool = False) -> None:
        if not self._scope_pending_times:
            return
        if not force and self._scope_last_emit_at > 0 and now - self._scope_last_emit_at < self._scope_emit_period_s:
            return
        times = self._scope_pending_times
        values = self._scope_pending_values
        self._scope_pending_times = []
        self._scope_pending_values = {}
        self._scope_last_emit_at = now
        self.scope_samples.emit(times, values, self._scope_actual_hz, x_is_time)

    def _stop_scope_sampling_internal(self) -> None:
        if self._scope_timer is not None and self._scope_timer.isActive():
            self._emit_scope_chunk(time.perf_counter(), self._scope_x_is_time, force=True)
            self._scope_timer.stop()
        try:
            if self._scope_source == "HSS":
                self._jlink.hss_stop()
            elif self._scope_source == "RTT":
                self._jlink.rtt_stop()
        finally:
            was_active = bool(self._scope_source)
            old_source = self._scope_source
            self._scope_source = ""
            self._scope_hss_decoder = None
            self._scope_rtt_decoder = None
            self._scope_rtt_buffer_index = None
            self._scope_pending_times = []
            self._scope_pending_values = {}
            if was_active:
                self.scope_state_changed.emit(False, old_source)

    # ---------- Shutdown ----------
    @Slot()
    def shutdown(self) -> None:
        self._stop_watch_sampling_internal()
        self._stop_scope_sampling_internal()
        self._jlink.close()
