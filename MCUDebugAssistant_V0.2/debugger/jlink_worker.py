from __future__ import annotations

import math
import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal, Slot, Qt

from core.datatype import decode_value, encode_value, format_value, get_type_info
from core.watch import MemoryReadPlanner, RunningStats, WatchVariableSpec
from debugger.jlink_backend import ConnectionConfig, JLinkBackend


class JLinkWorker(QObject):
    connection_changed = Signal(bool, str)
    manual_read_done = Signal(int, bool, object, str, str)
    manual_write_done = Signal(int, bool, object, str, str)
    # IMPORTANT: this signal is a throttled GUI snapshot, not a signal for every
    # acquisition cycle. The worker may sample/accumulate much faster than Qt paints.
    watch_samples = Signal(object, float, float)  # list[dict], elapsed_s, actual_hz
    watch_error = Signal(str)
    sampling_state_changed = Signal(bool)

    # Watch is a numeric monitor. 25 FPS is already visually smooth for text while
    # keeping the GUI event queue small even if acquisition runs at hundreds of Hz.
    GUI_SNAPSHOT_HZ = 25.0

    def __init__(self) -> None:
        super().__init__()
        self._jlink = JLinkBackend()
        self._timer: QTimer | None = None
        self._watch_specs: list[WatchVariableSpec] = []
        self._planner = MemoryReadPlanner(max_gap_bytes=0, max_block_bytes=256)
        self._sample_interval_ms = 100
        self._sampling_started_at = 0.0
        self._sample_count = 0

        # Acquisition/statistics state lives in the J-Link owner thread. This keeps
        # high-rate samples out of the GUI thread. Only the latest 25 Hz snapshot is
        # emitted to the UI; Mean/Min/Max still include every successful sample.
        self._watch_stats: dict[int, RunningStats] = {}
        self._watch_signatures: dict[int, tuple[int, str]] = {}
        self._latest_values: dict[int, float | int] = {}

        self._gui_snapshot_period_s = 1.0 / self.GUI_SNAPSHOT_HZ
        self._last_gui_emit_at = 0.0

        # Short rolling window for a useful measured acquisition rate.
        self._rate_window_started_at = 0.0
        self._rate_window_samples = 0
        self._actual_hz = 0.0

    @Slot(object)
    def connect_target(self, config: ConnectionConfig) -> None:
        try:
            self._stop_sampling_internal()
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
            self._stop_sampling_internal()
            self._jlink.close()
            self.connection_changed.emit(False, "Disconnected")
        except Exception as exc:
            self.connection_changed.emit(False, f"Disconnect error: {exc}")

    @Slot(int, object, str)
    def read_typed(self, request_id: int, address: int, type_name: str) -> None:
        try:
            address = int(address)
            info = get_type_info(type_name)
            raw = self._jlink.read_memory(address, info.size)
            value = decode_value(raw, type_name)
            self.manual_read_done.emit(
                request_id, True, value, raw.hex(" ").upper(), ""
            )
        except Exception as exc:
            self.manual_read_done.emit(request_id, False, None, "", str(exc))

    @Slot(int, object, str, str)
    def write_typed(
        self, request_id: int, address: int, type_name: str, value_text: str
    ) -> None:
        try:
            address = int(address)
            data = encode_value(value_text, type_name)
            readback = self._jlink.write_and_verify(address, data)
            value = decode_value(readback, type_name)
            self.manual_write_done.emit(
                request_id, True, value, readback.hex(" ").upper(), ""
            )
        except Exception as exc:
            self.manual_write_done.emit(request_id, False, None, "", str(exc))

    @Slot(object, int)
    def start_watch_sampling(self, specs: list[WatchVariableSpec], interval_ms: int) -> None:
        try:
            if not self._jlink.is_target_connected:
                raise RuntimeError("Target is not connected")
            if interval_ms < 1:
                raise ValueError("Watch sample interval must be >= 1 ms")

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
            self._stop_sampling_internal()
            self.watch_error.emit(str(exc))

    @Slot(object)
    def update_watch_specs(self, specs: list[WatchVariableSpec]) -> None:
        self._configure_watch_specs(specs)
        if self._timer is not None and self._timer.isActive() and not self._watch_specs:
            self._stop_sampling_internal()

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
        """Clear Mean/Min/Max without stopping acquisition or clearing Current."""
        for stats in self._watch_stats.values():
            stats.clear()
        # Do not clear _latest_values: Current should stay visible.
        if self._timer is not None and self._timer.isActive():
            self._emit_watch_snapshot(time.perf_counter(), force=True)

    @Slot()
    def stop_watch_sampling(self) -> None:
        self._stop_sampling_internal()

    @Slot()
    def shutdown(self) -> None:
        self._stop_sampling_internal()
        self._jlink.close()

    def _configure_watch_specs(self, specs: list[WatchVariableSpec]) -> None:
        """Apply Watch definitions while preserving statistics for unchanged rows.

        A row keeps its statistics across Stop/Start when address and type are unchanged.
        Editing/rebinding the address or type resets that row so old firmware data is
        never mixed with the new object.
        """
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
                    size = var.size
                    raw = raw_block[offset : offset + size]
                    value = decode_value(raw, var.type_name)
                    self._latest_values[var.row_id] = value
                    self._watch_stats.setdefault(var.row_id, RunningStats()).add(value)

            completed_at = time.perf_counter()
            self._sample_count += 1
            self._rate_window_samples += 1
            self._update_actual_rate(completed_at)

            # This is the key performance boundary: acquisition/statistics happen on
            # every cycle, but Qt receives at most 25 snapshots/s. Intermediate GUI
            # frames are intentionally discarded; statistics are not discarded.
            if (
                self._last_gui_emit_at <= 0.0
                or completed_at - self._last_gui_emit_at >= self._gui_snapshot_period_s
            ):
                self._emit_watch_snapshot(completed_at)
        except Exception as exc:
            self.watch_error.emit(str(exc))
            self._stop_sampling_internal()

    def _emit_watch_snapshot(self, now: float, *, force: bool = False) -> None:
        if not force and self._last_gui_emit_at > 0.0:
            if now - self._last_gui_emit_at < self._gui_snapshot_period_s:
                return

        results: list[dict[str, Any]] = []
        for var in self._watch_specs:
            if var.row_id not in self._latest_values:
                continue
            value = self._latest_values[var.row_id]
            count, avg, minimum, maximum = self._watch_stats.setdefault(
                var.row_id, RunningStats()
            ).snapshot()
            results.append(
                {
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
                }
            )

        elapsed = max(0.0, now - self._sampling_started_at)
        # Before the rolling window has matured, use the cumulative measured rate so
        # the label is still useful immediately after Start.
        if self._actual_hz > 0.0:
            actual_hz = self._actual_hz
        elif elapsed > 0.0:
            actual_hz = self._sample_count / elapsed
        else:
            actual_hz = 0.0

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
        if elapsed > 0.0:
            measured = self._rate_window_samples / elapsed
            if math.isfinite(measured):
                self._actual_hz = measured
        self._rate_window_started_at = now
        self._rate_window_samples = 0

    def _stop_sampling_internal(self) -> None:
        if self._timer is not None and self._timer.isActive():
            # Push the latest accumulated statistics once before stopping so the UI
            # does not miss up to one 40 ms display interval.
            self._emit_watch_snapshot(time.perf_counter(), force=True)
            self._timer.stop()
        self.sampling_state_changed.emit(False)
