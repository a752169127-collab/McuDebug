from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.datatype import supported_types
from core.scope import ScopeChannelSpec


class ScopeChannelTable(QTableWidget):
    definition_changed = Signal()
    display_changed = Signal(object)
    selected_channel_changed = Signal(object)

    COL_VISIBLE = 0
    COL_NAME = 1
    COL_ADDRESS = 2
    COL_TYPE = 3
    COL_CURRENT = 4
    COL_AVG = 5
    COL_MIN = 6
    COL_MAX = 7
    COL_GAIN = 8
    COL_OFFSET = 9
    HEADERS = ["Show", "Name", "Address", "Type", "Current", "Average", "Min", "Max", "Gain", "Offset"]

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(23)
        self.setAlternatingRowColors(True)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(self.COL_VISIBLE, 52)
        self.setColumnWidth(self.COL_ADDRESS, 108)
        self.setColumnWidth(self.COL_TYPE, 82)
        for col in (self.COL_CURRENT, self.COL_AVG, self.COL_MIN, self.COL_MAX):
            self.setColumnWidth(col, 92)
        self.setColumnWidth(self.COL_GAIN, 72)
        self.setColumnWidth(self.COL_OFFSET, 82)
        self._next_id = 1
        self._rtt_mode = False
        self._internal_update = False
        self.itemChanged.connect(self._item_changed)
        self.itemSelectionChanged.connect(self._emit_selected)

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._internal_update:
            return
        if item.column() in (self.COL_GAIN, self.COL_OFFSET):
            try:
                float(item.text().strip())
            except ValueError:
                return
            cid = self._channel_id_for_row(item.row())
            self.display_changed.emit(cid)
        else:
            self.definition_changed.emit()

    def _channel_id_for_row(self, row: int) -> int | None:
        item = self.item(row, self.COL_VISIBLE)
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    @staticmethod
    def _readonly_item(text: str = "-") -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    def set_rtt_mode(self, enabled: bool) -> None:
        self._rtt_mode = bool(enabled)
        self._update_editability()

    def add_channel(
        self,
        name: str = "Value1",
        address: str = "0x20000000",
        type_name: str = "float",
        enabled: bool = True,
        channel_id: int | None = None,
        gain: float = 1.0,
        offset: float = 0.0,
    ) -> int:
        row = self.rowCount()
        self.insertRow(row)
        cid = int(channel_id) if channel_id is not None else self._next_id
        self._next_id = max(self._next_id, cid + 1)

        visible = QTableWidgetItem()
        visible.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
        visible.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
        visible.setData(Qt.ItemDataRole.UserRole, cid)
        self.setItem(row, self.COL_VISIBLE, visible)
        self.setItem(row, self.COL_NAME, QTableWidgetItem(name))
        self.setItem(row, self.COL_ADDRESS, QTableWidgetItem(address))

        combo = QComboBox(self)
        combo.addItems(supported_types())
        combo.setCurrentText(type_name if type_name in supported_types() else "float")
        combo.currentTextChanged.connect(lambda *_: self.definition_changed.emit())
        self.setCellWidget(row, self.COL_TYPE, combo)

        for col in (self.COL_CURRENT, self.COL_AVG, self.COL_MIN, self.COL_MAX):
            self.setItem(row, col, self._readonly_item())
        self.setItem(row, self.COL_GAIN, QTableWidgetItem(f"{float(gain):.9g}"))
        self.setItem(row, self.COL_OFFSET, QTableWidgetItem(f"{float(offset):.9g}"))
        self._update_row_editability(row)
        if self.rowCount() == 1:
            self.selectRow(0)
        return cid

    def set_rtt_channels(self, channels: list[dict]) -> None:
        old_display = {}
        for row in range(self.rowCount()):
            cid = self._channel_id_for_row(row)
            name_item = self.item(row, self.COL_NAME)
            if cid is not None and name_item is not None:
                old_display[(cid, name_item.text().strip())] = self.gain_offset(cid)
        blocked = self.blockSignals(True)
        self._internal_update = True
        try:
            self.setRowCount(0)
            self._next_id = 1
            for ch in channels:
                cid = int(ch.get("channel_id", self.rowCount() + 1))
                name = str(ch.get("name", f"RTT_Value{self.rowCount()+1}"))
                gain, offset = old_display.get((cid, name), (1.0, 0.0))
                self.add_channel(
                    name=name,
                    address="-",
                    type_name=str(ch.get("type_name", "uint32")),
                    enabled=True,
                    channel_id=cid,
                    gain=gain,
                    offset=offset,
                )
            self._rtt_mode = True
            self._update_editability()
        finally:
            self._internal_update = False
            self.blockSignals(blocked)
        if self.rowCount():
            self.selectRow(0)
        self.definition_changed.emit()

    def clear_channels(self) -> None:
        self.setRowCount(0)
        self._next_id = 1
        self.definition_changed.emit()

    def remove_selected(self) -> int:
        if self._rtt_mode:
            return 0
        rows = sorted({i.row() for i in self.selectionModel().selectedRows()}, reverse=True)
        if not rows and self.currentRow() >= 0:
            rows = [self.currentRow()]
        for row in rows:
            self.removeRow(row)
        if rows:
            self.definition_changed.emit()
        return len(rows)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Delete and not self._rtt_mode:
            self.remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def contains_channel(self, name: str, address: int) -> bool:
        for row in range(self.rowCount()):
            ni = self.item(row, self.COL_NAME)
            ai = self.item(row, self.COL_ADDRESS)
            if ni is None or ai is None or ni.text().strip() != name.strip():
                continue
            try:
                if int(ai.text().strip(), 0) == int(address):
                    return True
            except ValueError:
                pass
        return False

    def specs(self) -> list[ScopeChannelSpec]:
        result: list[ScopeChannelSpec] = []
        for row in range(self.rowCount()):
            visible = self.item(row, self.COL_VISIBLE)
            name_item = self.item(row, self.COL_NAME)
            addr_item = self.item(row, self.COL_ADDRESS)
            combo = self.cellWidget(row, self.COL_TYPE)
            if visible is None or name_item is None or addr_item is None or not isinstance(combo, QComboBox):
                continue
            cid = int(visible.data(Qt.ItemDataRole.UserRole))
            if self._rtt_mode:
                address = 0
            else:
                try:
                    address = int(addr_item.text().strip(), 0)
                except ValueError as exc:
                    raise ValueError(f"Scope '{name_item.text()}' address is invalid") from exc
                if not 0 <= address <= 0xFFFFFFFF:
                    raise ValueError(f"Scope '{name_item.text()}' address is outside 32-bit range")
            result.append(ScopeChannelSpec(
                channel_id=cid,
                name=name_item.text().strip() or f"Value{cid}",
                address=address,
                type_name=combo.currentText(),
                enabled=visible.checkState() == Qt.CheckState.Checked,
            ))
        return result

    def selected_channel_id(self) -> int | None:
        row = self.currentRow()
        return self._channel_id_for_row(row) if row >= 0 else None

    def select_channel_id(self, channel_id: int | None) -> None:
        if channel_id is None:
            return
        for row in range(self.rowCount()):
            if self._channel_id_for_row(row) == int(channel_id):
                self.selectRow(row)
                return

    def selected_channel_name(self) -> str:
        row = self.currentRow()
        item = self.item(row, self.COL_NAME) if row >= 0 else None
        return item.text().strip() if item else ""

    def channel_names(self) -> dict[int, str]:
        result = {}
        for row in range(self.rowCount()):
            cid = self._channel_id_for_row(row)
            name = self.item(row, self.COL_NAME)
            if cid is not None and name is not None:
                result[cid] = name.text().strip()
        return result

    def visible_channel_ids(self) -> list[int]:
        result = []
        for row in range(self.rowCount()):
            item = self.item(row, self.COL_VISIBLE)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                result.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return result

    def ordered_channel_ids(self) -> list[int]:
        result = []
        for row in range(self.rowCount()):
            cid = self._channel_id_for_row(row)
            if cid is not None:
                result.append(cid)
        return result

    def gain_offset(self, channel_id: int) -> tuple[float, float]:
        for row in range(self.rowCount()):
            if self._channel_id_for_row(row) != int(channel_id):
                continue
            gain_item = self.item(row, self.COL_GAIN)
            offset_item = self.item(row, self.COL_OFFSET)
            try:
                gain = float(gain_item.text().strip()) if gain_item is not None else 1.0
            except ValueError:
                gain = 1.0
            try:
                offset = float(offset_item.text().strip()) if offset_item is not None else 0.0
            except ValueError:
                offset = 0.0
            if not math.isfinite(gain) or abs(gain) < 1e-12:
                gain = 1.0
            if not math.isfinite(offset):
                offset = 0.0
            return gain, offset
        return 1.0, 0.0

    def set_gain_offset(self, channel_id: int, *, gain: float | None = None, offset: float | None = None) -> bool:
        for row in range(self.rowCount()):
            if self._channel_id_for_row(row) != int(channel_id):
                continue
            old_guard = self._internal_update
            self._internal_update = True
            try:
                if gain is not None:
                    gain = max(1e-9, min(1e9, float(gain)))
                    self.item(row, self.COL_GAIN).setText(f"{gain:.9g}")
                if offset is not None:
                    offset = float(offset)
                    if math.isfinite(offset):
                        self.item(row, self.COL_OFFSET).setText(f"{offset:.9g}")
            finally:
                self._internal_update = old_guard
            self.display_changed.emit(int(channel_id))
            return True
        return False

    def update_statistics(self, stats: dict[int, dict]) -> None:
        self._internal_update = True
        self.setUpdatesEnabled(False)
        try:
            for row in range(self.rowCount()):
                cid = self._channel_id_for_row(row)
                if cid is None:
                    continue
                s = stats.get(cid)
                values = ("-", "-", "-", "-") if not s else (
                    self._fmt(s.get("current")),
                    self._fmt(s.get("average")),
                    self._fmt(s.get("minimum")),
                    self._fmt(s.get("maximum")),
                )
                for col, text in zip((self.COL_CURRENT, self.COL_AVG, self.COL_MIN, self.COL_MAX), values):
                    item = self.item(row, col)
                    if item is not None and item.text() != text:
                        item.setText(text)
        finally:
            self.setUpdatesEnabled(True)
            self._internal_update = False

    @staticmethod
    def _fmt(value) -> str:
        if value is None:
            return "-"
        try:
            f = float(value)
        except Exception:
            return str(value)
        return f"{f:.9g}" if math.isfinite(f) else "-"

    def set_definition_editable(self, editable: bool) -> None:
        self._definition_editable = bool(editable)
        self._update_editability()

    def _update_editability(self) -> None:
        for row in range(self.rowCount()):
            self._update_row_editability(row)

    def _update_row_editability(self, row: int) -> None:
        editable = getattr(self, "_definition_editable", True) and not self._rtt_mode
        for col in (self.COL_NAME, self.COL_ADDRESS):
            item = self.item(row, col)
            if item is None:
                continue
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            if editable:
                flags |= Qt.ItemFlag.ItemIsEditable
            item.setFlags(flags)
        # Gain / Offset are display parameters and remain editable while sampling.
        for col in (self.COL_GAIN, self.COL_OFFSET):
            item = self.item(row, col)
            if item is not None:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
        combo = self.cellWidget(row, self.COL_TYPE)
        if isinstance(combo, QComboBox):
            combo.setEnabled(editable)

    def rebind_symbols(self, symbols) -> dict[str, int]:
        if self._rtt_mode:
            return {"updated": 0, "unchanged": 0, "removed": 0}
        by_name: dict[str, list] = {}
        for sym in symbols:
            if getattr(sym, "addable", False):
                by_name.setdefault(str(sym.name), []).append(sym)
        summary = {"updated": 0, "unchanged": 0, "removed": 0}
        remove_rows = []
        blocked = self.blockSignals(True)
        try:
            for row in range(self.rowCount()):
                name = self.item(row, self.COL_NAME).text().strip()
                addr_item = self.item(row, self.COL_ADDRESS)
                combo = self.cellWidget(row, self.COL_TYPE)
                candidates = by_name.get(name, [])
                if not candidates:
                    remove_rows.append(row)
                    continue
                try:
                    old_addr = int(addr_item.text(), 0)
                except ValueError:
                    old_addr = None
                if len(candidates) == 1:
                    sym = candidates[0]
                else:
                    same = [s for s in candidates if old_addr is not None and int(s.address) == old_addr]
                    if len(same) != 1:
                        remove_rows.append(row)
                        continue
                    sym = same[0]
                changed = old_addr != int(sym.address)
                addr_item.setText(f"0x{int(sym.address):08X}")
                if sym.type_name in supported_types() and isinstance(combo, QComboBox):
                    changed = changed or combo.currentText() != sym.type_name
                    combo.setCurrentText(sym.type_name)
                summary["updated" if changed else "unchanged"] += 1
            for row in reversed(remove_rows):
                self.removeRow(row)
                summary["removed"] += 1
        finally:
            self.blockSignals(blocked)
        self.definition_changed.emit()
        return summary

    def to_json(self) -> str:
        if self._rtt_mode:
            return "[]"
        rows = []
        for spec in self.specs():
            gain, offset = self.gain_offset(spec.channel_id)
            rows.append({
                "name": spec.name,
                "address": spec.address,
                "type": spec.type_name,
                "enabled": spec.enabled,
                "gain": gain,
                "offset": offset,
            })
        return json.dumps(rows, ensure_ascii=False)

    def load_json(self, text: str) -> None:
        if not text:
            return
        data = json.loads(text)
        self.setRowCount(0)
        self._next_id = 1
        self._rtt_mode = False
        for row in data:
            self.add_channel(
                str(row.get("name", "Value")),
                f"0x{int(row.get('address', 0)):08X}",
                str(row.get("type", "float")),
                bool(row.get("enabled", True)),
                gain=float(row.get("gain", 1.0)),
                offset=float(row.get("offset", 0.0)),
            )

    def _emit_selected(self) -> None:
        self.selected_channel_changed.emit(self.selected_channel_id())


class ScopePlotWidget(pg.PlotWidget):
    """Plot widget with J-Scope-like channel transform shortcuts.

    + / -      : increase / decrease selected channel display Gain
    Ctrl + / - : increase / decrease selected channel display Offset
    """

    command_requested = Signal(str)
    mouse_left = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.mouse_left.emit()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        plus = key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal)
        minus = key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore)
        if plus:
            self.command_requested.emit("offset_up" if ctrl else "gain_up")
            event.accept()
            return
        if minus:
            self.command_requested.emit("offset_down" if ctrl else "gain_down")
            event.accept()
            return
        super().keyPressEvent(event)


class ScopeDataStore:
    """In-memory Scope buffer plus raw-value session statistics.

    Stopping acquisition does not clear this store.  If a restarted HSS/RTT source
    restarts its timestamp at zero, the new chunk is shifted forward so paused
    captures remain one continuous X timeline for analysis.
    """

    def __init__(self, seconds: float = 30.0, max_points: int = 1500000) -> None:
        self.seconds = float(seconds)
        self.max_points = int(max_points)
        self.x = np.empty(0, dtype=np.float64)
        self.values: dict[int, np.ndarray] = {}
        self.x_is_time = True
        self._stats: dict[int, dict[str, float | int | None]] = {}

    def set_seconds(self, seconds: float) -> None:
        self.seconds = max(1.0, float(seconds))
        self._trim()

    def clear(self) -> None:
        self.x = np.empty(0, dtype=np.float64)
        self.values = {}
        self._stats = {}

    def append(self, times, values: dict[int, list], x_is_time: bool) -> None:
        x_new = np.asarray(times, dtype=np.float64)
        if x_new.size == 0:
            return
        self.x_is_time = bool(x_is_time)
        # HSS/RTT decoder timestamps are relative to each acquisition start.  On
        # resume, keep the old capture and shift the restarted sequence forward.
        if self.x.size and x_new[0] <= self.x[-1]:
            if x_new.size >= 2:
                diffs = np.diff(x_new)
                positive = diffs[diffs > 0]
                step = float(np.median(positive)) if positive.size else (1e-6 if x_is_time else 1.0)
            elif self.x.size >= 2:
                diffs = np.diff(self.x)
                positive = diffs[diffs > 0]
                step = float(np.median(positive)) if positive.size else (1e-6 if x_is_time else 1.0)
            else:
                step = 1e-6 if x_is_time else 1.0
            x_new = x_new + (float(self.x[-1]) + step - float(x_new[0]))

        old_n = self.x.size
        self.x = np.concatenate((self.x, x_new))
        all_ids = set(self.values) | {int(k) for k in values}
        for cid in all_ids:
            old = self.values.get(cid, np.full(old_n, np.nan, dtype=np.float64))
            seq = values.get(cid)
            if seq is None:
                new = np.full(x_new.size, np.nan, dtype=np.float64)
            else:
                new = np.asarray(seq, dtype=np.float64)
                if new.size != x_new.size:
                    padded = np.full(x_new.size, np.nan, dtype=np.float64)
                    padded[: min(new.size, x_new.size)] = new[: x_new.size]
                    new = padded
                self._update_stats(int(cid), new)
            self.values[cid] = np.concatenate((old, new))
        self._trim()

    def _update_stats(self, channel_id: int, values: np.ndarray) -> None:
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return
        state = self._stats.setdefault(channel_id, {
            "count": 0,
            "sum": 0.0,
            "current": None,
            "minimum": None,
            "maximum": None,
        })
        state["count"] = int(state["count"]) + int(finite.size)
        state["sum"] = float(state["sum"]) + float(np.sum(finite, dtype=np.float64))
        state["current"] = float(finite[-1])
        chunk_min = float(np.min(finite))
        chunk_max = float(np.max(finite))
        state["minimum"] = chunk_min if state["minimum"] is None else min(float(state["minimum"]), chunk_min)
        state["maximum"] = chunk_max if state["maximum"] is None else max(float(state["maximum"]), chunk_max)

    def stats_snapshot(self) -> dict[int, dict]:
        result = {}
        for cid, s in self._stats.items():
            count = int(s["count"])
            result[cid] = {
                "count": count,
                "current": s["current"],
                "average": (float(s["sum"]) / count) if count else None,
                "minimum": s["minimum"],
                "maximum": s["maximum"],
            }
        return result

    def _trim(self) -> None:
        if self.x.size == 0:
            return
        start = 0
        if self.x_is_time and self.x[-1] - self.x[0] > self.seconds:
            cutoff = self.x[-1] - self.seconds
            start = int(np.searchsorted(self.x, cutoff, side="left"))
        if self.x.size - start > self.max_points:
            start = self.x.size - self.max_points
        if start > 0:
            self.x = self.x[start:]
            for cid in list(self.values):
                self.values[cid] = self.values[cid][start:]

    def curve(self, channel_id: int, display_limit: int = 10000) -> tuple[np.ndarray, np.ndarray]:
        y = self.values.get(int(channel_id))
        if y is None or self.x.size == 0:
            return np.empty(0), np.empty(0)
        if self.x.size <= display_limit:
            return self.x, y
        step = max(1, math.ceil(self.x.size / display_limit))
        return self.x[::step], y[::step]

    def nearest(self, channel_id: int, x_value: float) -> tuple[float, float] | None:
        y = self.values.get(int(channel_id))
        if y is None or self.x.size == 0:
            return None
        idx = int(np.searchsorted(self.x, x_value))
        if idx <= 0:
            idx = 0
        elif idx >= self.x.size:
            idx = self.x.size - 1
        elif abs(self.x[idx - 1] - x_value) <= abs(self.x[idx] - x_value):
            idx -= 1
        value = float(y[idx])
        if not math.isfinite(value):
            return None
        return float(self.x[idx]), value


class ScopePage(QWidget):
    start_requested = Signal(str, object, int)
    stop_requested = Signal()
    add_symbol_requested = Signal()
    log_requested = Signal(str)
    fps_changed = Signal(int)

    DEFAULT_BUFFER_SECONDS = 30.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connected = False
        self._sampling = False
        self._source = "HSS"
        self._hss_saved_json = "[]"
        self._data = ScopeDataStore(seconds=self.DEFAULT_BUFFER_SECONDS, max_points=1500000)
        self._plots: list[pg.PlotWidget] = []
        self._curves: dict[int, object] = {}
        self._plot_channel_ids: dict[int, int | None] = {}
        self._hover_lines: list[pg.InfiniteLine] = []
        self._mouse_proxies: list[object] = []
        self._hover_x: float | None = None
        self._x_lines: dict[str, list[pg.InfiniteLine]] = {"X1": [], "X2": []}
        self._y_lines: dict[str, pg.InfiniteLine | None] = {"Y1": None, "Y2": None}
        self._cursor_values: dict[str, float | None] = {"X1": None, "X2": None, "Y1": None, "Y2": None}
        self._syncing_cursor = False
        self._need_fit = True
        self._x_is_time = True
        self._rtt_channel_name = ""
        self._rtt_signature: tuple | None = None
        # Live-follow keeps the user-selected X zoom span.  It only translates
        # that window so its right edge stays on the newest sample.
        self._follow_x_span: float | None = None
        self._applying_follow_range = False

        # Scope acquisition and rendering are intentionally decoupled. Raw samples
        # are appended whenever the worker emits a chunk (up to 60 Hz), while
        # pyqtgraph redraws at the user-selected FPS.
        self._render_dirty = False
        self._latest_actual_hz = 0.0
        self._render_timer = QTimer(self)
        self._render_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._render_timer.timeout.connect(self._render_if_dirty)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_toolbar())
        shortcut_hint = QLabel("快捷键：+ / - 调整选中通道 Gain；Ctrl + / Ctrl - 调整选中通道 Offset。Gain/Offset 只改变显示波形，原始采样值与导出数据不变；鼠标移动会显示同一时刻全部通道值。")
        shortcut_hint.setWordWrap(True)
        layout.addWidget(shortcut_hint)

        splitter = QSplitter(Qt.Orientation.Vertical)
        plot_panel = QWidget()
        plot_panel_layout = QVBoxLayout(plot_panel)
        plot_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_host = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_host)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_panel_layout.addWidget(self.plot_host, 1)
        self.cursor_label = QLabel("X1=-  X2=-  ΔX=-    Y1=-  Y2=-  ΔY=-    Selected=-  Value@X1=-  Value@X2=-")
        self.cursor_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        plot_panel_layout.addWidget(self.cursor_label)
        splitter.addWidget(plot_panel)

        self.channel_table = ScopeChannelTable()
        self.channel_table.setMinimumHeight(135)
        self.channel_table.setMaximumHeight(260)
        self.channel_table.definition_changed.connect(self._rebuild_plots)
        self.channel_table.display_changed.connect(self._display_transform_changed)
        self.channel_table.selected_channel_changed.connect(self._selected_channel_changed)
        splitter.addWidget(self.channel_table)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([620, 170])
        layout.addWidget(splitter, 1)

        self.hover_label = QLabel(self.plot_host)
        self.hover_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hover_label.setStyleSheet(
            "QLabel { background: rgba(28,28,28,220); color: white; border: 1px solid #808080; "
            "padding: 5px 7px; font-family: Consolas, 'Courier New', monospace; }"
        )
        self.hover_label.hide()

        self.channel_table.add_channel("Value1", "0x20000000", "float")
        self._source_changed("HSS")
        self._fps_changed()

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.addItems(["HSS", "RTT"])
        self.source_combo.currentTextChanged.connect(self._source_changed)
        self.add_btn = QPushButton("AXF添加成员...")
        self.add_btn.clicked.connect(self.add_symbol_requested.emit)
        self.remove_btn = QPushButton("删除成员")
        self.remove_btn.clicked.connect(self.channel_table_remove)
        self.sample_hz_spin = QSpinBox()
        self.sample_hz_spin.setRange(1, 10000)
        self.sample_hz_spin.setValue(1000)
        self.sample_hz_spin.setSuffix(" Hz")
        self.period_label = QLabel("1.000 ms/sample")
        self.sample_hz_spin.valueChanged.connect(self._update_period_label)
        self.view_combo = QComboBox()
        self.view_combo.addItems(["Overlay", "Stacked"])
        self.view_combo.currentTextChanged.connect(lambda *_: self._rebuild_plots())
        self.buffer_seconds_spin = QSpinBox()
        self.buffer_seconds_spin.setRange(1, 120)
        self.buffer_seconds_spin.setValue(int(self.DEFAULT_BUFFER_SECONDS))
        self.buffer_seconds_spin.setSuffix(" s")
        self.buffer_seconds_spin.setToolTip("Scope 内存缓存时间；导出 CSV 导出当前缓存中的原始采样数据")
        self.buffer_seconds_spin.valueChanged.connect(self._buffer_seconds_changed)
        self.fps_combo = QComboBox()
        self.fps_combo.setEditable(True)
        self.fps_combo.addItems(["1", "2", "5", "10", "15", "20", "25", "30", "40", "50", "60"])
        self.fps_combo.setCurrentText("30")
        self.fps_combo.setToolTip("Scope 波形界面刷新率，1~60 FPS；不改变 HSS/RTT 实际采样频率")
        if self.fps_combo.lineEdit() is not None:
            self.fps_combo.lineEdit().setValidator(QIntValidator(1, 60, self.fps_combo))
            self.fps_combo.lineEdit().editingFinished.connect(self._fps_changed)
        self.fps_combo.activated.connect(lambda *_: self._fps_changed())
        self.view_all_btn = QPushButton("查看所有波形")
        self.view_all_btn.clicked.connect(self.view_all)
        self.follow_latest_check = QCheckBox("跟随最新数据")
        self.follow_latest_check.setChecked(True)
        self.follow_latest_check.setToolTip("勾选后仍可手动缩放 X/Y；程序只保存当前 X 窗口宽度并随最新样本向右滚动，Y 轴不自动变化")
        self.follow_latest_check.toggled.connect(self._follow_latest_toggled)
        self.actual_label = QLabel("Actual: -")
        self.start_btn = QPushButton("开始采样")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("暂停采样")
        self.stop_btn.clicked.connect(self.stop_requested.emit)

        bar.addWidget(QLabel("Source"))
        bar.addWidget(self.source_combo)
        bar.addWidget(self.add_btn)
        bar.addWidget(self.remove_btn)
        bar.addSpacing(12)
        bar.addWidget(QLabel("Sampling"))
        bar.addWidget(self.sample_hz_spin)
        bar.addWidget(self.period_label)
        bar.addSpacing(12)
        bar.addWidget(QLabel("View"))
        bar.addWidget(self.view_combo)
        bar.addWidget(QLabel("Buffer"))
        bar.addWidget(self.buffer_seconds_spin)
        bar.addWidget(QLabel("FPS"))
        bar.addWidget(self.fps_combo)
        bar.addWidget(self.view_all_btn)
        bar.addWidget(self.follow_latest_check)
        bar.addWidget(self.actual_label)
        bar.addStretch(1)
        bar.addWidget(self.start_btn)
        bar.addWidget(self.stop_btn)
        return bar

    def set_connected(self, connected: bool) -> None:
        self._connected = bool(connected)
        self._update_controls()

    def set_sampling(self, active: bool, source_text: str = "") -> None:
        self._sampling = bool(active)
        if not active:
            self.actual_label.setText("Actual: -")
        self._update_controls()

    def _update_controls(self) -> None:
        self.start_btn.setEnabled(self._connected and not self._sampling)
        self.stop_btn.setEnabled(self._connected and self._sampling)
        self.source_combo.setEnabled(not self._sampling)
        self.sample_hz_spin.setEnabled(not self._sampling and self._source == "HSS")
        self.add_btn.setEnabled(not self._sampling and self._source == "HSS")
        self.remove_btn.setEnabled(not self._sampling and self._source == "HSS")
        self.channel_table.set_definition_editable(not self._sampling)

    def _source_changed(self, source: str) -> None:
        source = source.upper()
        if source == self._source:
            self._update_controls()
            return
        if self._source == "HSS":
            try:
                self._hss_saved_json = self.channel_table.to_json()
            except Exception:
                pass
        self._source = source
        self._data.clear()
        if source == "RTT":
            self.channel_table.clear_channels()
            self.channel_table.set_rtt_mode(True)
            self.period_label.setText("Target-defined")
        else:
            # Leaving RTT restores the independent HSS symbol list. RTT-normal channels
            # are target-defined and must never overwrite the saved HSS selection.
            self.channel_table.clear_channels()
            self.channel_table.set_rtt_mode(False)
            try:
                self.channel_table.load_json(self._hss_saved_json)
            except Exception:
                pass
            if self.channel_table.rowCount() == 0:
                self.channel_table.add_channel("Value1", "0x20000000", "float")
            self._update_period_label()
        self._update_controls()
        self._rebuild_plots()

    def _fps_value(self) -> int:
        try:
            value = int(self.fps_combo.currentText().strip())
        except Exception:
            value = 30
        return max(1, min(60, value))

    def _fps_changed(self, _text: str = "") -> None:
        fps = self._fps_value()
        normalized = str(fps)
        if self.fps_combo.currentText().strip() != normalized:
            self.fps_combo.blockSignals(True)
            self.fps_combo.setCurrentText(normalized)
            self.fps_combo.blockSignals(False)
        interval_ms = max(1, round(1000.0 / fps))
        self._render_timer.setInterval(interval_ms)
        if not self._render_timer.isActive():
            self._render_timer.start()
        self.fps_changed.emit(fps)
        # Make an FPS change visible immediately instead of waiting for the next sample.
        self._render_dirty = True

    def _render_if_dirty(self) -> None:
        if not self._render_dirty:
            return
        self._render_dirty = False
        if self._latest_actual_hz > 0:
            self.actual_label.setText(f"Actual: {self._latest_actual_hz:.4g} Hz")
        self._update_curves()
        self._update_cursor_label()

    def _update_period_label(self) -> None:
        hz = max(1, self.sample_hz_spin.value())
        period_ms = 1000.0 / hz
        if period_ms >= 1:
            self.period_label.setText(f"{period_ms:.3f} ms/sample")
        else:
            self.period_label.setText(f"{period_ms * 1000:.3f} us/sample")

    def _buffer_seconds_changed(self, seconds: int) -> None:
        self._data.set_seconds(float(seconds))
        self._update_curves()
        if self._sampling and self.follow_latest_check.isChecked():
            self._follow_latest()

    def _export_data(self) -> None:
        if self._data.x.size == 0:
            self.log_requested.emit("Scope export: no buffered samples")
            return
        default_name = f"scope_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "导出 Scope 原始数据", default_name, "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        names = self.channel_table.channel_names()
        channel_ids = self.channel_table.ordered_channel_ids()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fp:
                writer = csv.writer(fp)
                x_name = "Time(s)" if self._data.x_is_time else "Sample Index"
                writer.writerow([x_name] + [names.get(cid, str(cid)) for cid in channel_ids])
                arrays = [self._data.values.get(cid) for cid in channel_ids]
                for i, x in enumerate(self._data.x):
                    row = [f"{float(x):.12g}"]
                    for arr in arrays:
                        if arr is None or i >= arr.size or not math.isfinite(float(arr[i])):
                            row.append("")
                        else:
                            row.append(f"{float(arr[i]):.12g}")
                    writer.writerow(row)
            self.log_requested.emit(
                f"Scope export: {self._data.x.size} sample(s), {len(channel_ids)} channel(s) -> {path}"
            )
        except Exception as exc:
            self.log_requested.emit(f"Scope export ERROR: {exc}")

    def _start(self) -> None:
        try:
            specs = self.channel_table.specs() if self._source == "HSS" else []
            if self._source == "HSS" and not any(s.enabled for s in specs):
                raise ValueError("至少添加并显示一个 Scope 成员")
            # Resume keeps the buffered capture for analysis.  Data is only
            # cleared explicitly (right-click -> Clear buffered data), when the
            # acquisition source changes, or when an incompatible RTT format appears.
            self._need_fit = self._data.x.size == 0
            self.start_requested.emit(self._source, specs, self.sample_hz_spin.value())
        except Exception as exc:
            self.log_requested.emit(f"SCOPE START ERROR: {exc}")

    def channel_table_remove(self) -> None:
        count = self.channel_table.remove_selected()
        if count:
            self.log_requested.emit(f"Scope: removed {count} channel(s)")

    def add_symbol(self, name: str, address: int, type_name: str) -> bool:
        if self._source != "HSS":
            return False
        if self.channel_table.contains_channel(name, address):
            return False
        self.channel_table.add_channel(name, f"0x{int(address):08X}", type_name, True)
        return True

    def rebind_symbols(self, symbols) -> dict[str, int]:
        return self.channel_table.rebind_symbols(symbols)

    def set_rtt_format(self, channel_name: str, channels: list[dict], has_timestamp: bool) -> None:
        signature = (
            str(channel_name),
            bool(has_timestamp),
            tuple((int(c.get("channel_id", 0)), str(c.get("name", "")), str(c.get("type_name", ""))) for c in channels),
        )
        compatible_resume = self._rtt_signature == signature
        self._rtt_signature = signature
        self._rtt_channel_name = channel_name
        self._x_is_time = bool(has_timestamp)
        self.channel_table.set_rtt_channels(channels)
        if not compatible_resume:
            self._data.clear()
            self._need_fit = True
        if not has_timestamp:
            self.log_requested.emit("RTT format has no t4 timestamp: X axis uses sample index, matching J-Scope semantics")
        self.log_requested.emit(
            f"RTT detected: {channel_name} | {len(channels)} value channel(s)"
            + (" | resumed existing capture" if compatible_resume and self._data.x.size else "")
        )

    def append_samples(self, times, values, actual_hz: float, x_is_time: bool) -> None:
        self._x_is_time = bool(x_is_time)
        self._data.append(times, values, x_is_time)
        if actual_hz > 0:
            self._latest_actual_hz = float(actual_hz)
        # Do not redraw pyqtgraph for every acquisition chunk. The render timer
        # consumes only the newest state at the selected 1..60 FPS, while every
        # sample remains in ScopeDataStore and contributes to statistics/export.
        self._render_dirty = True

    def _clear_plot_layout(self) -> None:
        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._plots = []
        self._curves = {}
        self._plot_channel_ids = {}
        self._hover_lines = []
        self._mouse_proxies = []
        self._x_lines = {"X1": [], "X2": []}
        self._y_lines = {"Y1": None, "Y2": None}
        if hasattr(self, "hover_label"):
            self.hover_label.hide()

    def _rebuild_plots(self) -> None:
        if not hasattr(self, "plot_layout"):
            return
        self._clear_plot_layout()
        visible_ids = self.channel_table.visible_channel_ids()
        names = self.channel_table.channel_names()
        if not visible_ids:
            empty = QLabel("没有显示的波形通道")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.plot_layout.addWidget(empty)
            return

        if self.view_combo.currentText() == "Overlay":
            plot = self._new_plot(None)
            self.plot_layout.addWidget(plot, 1)
            self._plots.append(plot)
            self._plot_channel_ids[id(plot)] = None
            plot.addLegend(offset=(8, 8))
            hues = max(1, len(visible_ids))
            for i, cid in enumerate(visible_ids):
                curve = plot.plot(name=names.get(cid, str(cid)), pen=pg.mkPen(pg.intColor(i, hues=hues), width=1.3))
                self._curves[cid] = curve
        else:
            first = None
            hues = max(1, len(visible_ids))
            for i, cid in enumerate(visible_ids):
                plot = self._new_plot(cid)
                if first is None:
                    first = plot
                else:
                    plot.setXLink(first)
                plot.setLabel("left", names.get(cid, str(cid)))
                curve = plot.plot(pen=pg.mkPen(pg.intColor(i, hues=hues), width=1.2))
                self._curves[cid] = curve
                self._plots.append(plot)
                self._plot_channel_ids[id(plot)] = cid
                self.plot_layout.addWidget(plot, 1)

        self._install_cursor_lines()
        self._update_curves()
        self._update_axis_labels()

    def _new_plot(self, channel_id: int | None) -> pg.PlotWidget:
        plot = ScopePlotWidget()
        plot.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.setMouseEnabled(x=True, y=True)
        plot_item = plot.getPlotItem()
        plot_item.setClipToView(True)
        plot_item.setDownsampling(auto=True, mode="peak")
        # Disable pyqtgraph's built-in right-click menu (View All / X axis / Export...).
        # Scope owns right click exclusively for X1/X2/Y1/Y2 cursor operations.
        if hasattr(plot_item, "setMenuEnabled"):
            plot_item.setMenuEnabled(False)
        # Hide pyqtgraph's built-in "A" auto-range button.  Live scrolling is
        # controlled exclusively by the toolbar checkbox and only moves X.
        if hasattr(plot_item, "hideButtons"):
            plot_item.hideButtons()
        vb = plot_item.vb
        if hasattr(vb, "setMenuEnabled"):
            vb.setMenuEnabled(False)
        # Never leave pyqtgraph automatic X/Y ranging enabled while samples arrive.
        # The user's Y scale/baseline remains stable until an explicit view operation.
        if hasattr(vb, "disableAutoRange"):
            vb.disableAutoRange()
        # Track manual X zoom even while live-follow is enabled.  Programmatic
        # follow moves are guarded so they do not overwrite the saved span.
        if hasattr(vb, "sigXRangeChanged"):
            vb.sigXRangeChanged.connect(lambda _vb, rng, p=plot: self._x_range_changed(p, rng))
        plot.command_requested.connect(lambda command, p=plot: self._plot_key_command(command, p))
        plot.mouse_left.connect(self._hide_hover)
        plot.scene().sigMouseClicked.connect(lambda ev, p=plot, cid=channel_id: self._plot_clicked(ev, p, cid))
        hover_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen((190, 190, 190, 170), width=1))
        hover_line.hide()
        plot.addItem(hover_line, ignoreBounds=True)
        self._hover_lines.append(hover_line)
        proxy = pg.SignalProxy(
            plot.scene().sigMouseMoved,
            rateLimit=60,
            slot=lambda args, p=plot, cid=channel_id: self._mouse_moved(args[0], p, cid),
        )
        self._mouse_proxies.append(proxy)
        return plot

    def _plot_key_command(self, command: str, plot: pg.PlotWidget) -> None:
        channel_id = self._plot_channel_ids.get(id(plot))
        if channel_id is None:
            channel_id = self.channel_table.selected_channel_id()
        if channel_id is None:
            return
        self.channel_table.select_channel_id(channel_id)
        gain, offset = self.channel_table.gain_offset(channel_id)
        if command == "gain_up":
            self.channel_table.set_gain_offset(channel_id, gain=gain * 1.25)
        elif command == "gain_down":
            self.channel_table.set_gain_offset(channel_id, gain=gain / 1.25)
        elif command in ("offset_up", "offset_down"):
            stats = self._data.stats_snapshot().get(channel_id, {})
            minimum = stats.get("minimum")
            maximum = stats.get("maximum")
            current = stats.get("current")
            if minimum is not None and maximum is not None and float(maximum) > float(minimum):
                step = abs(float(maximum) - float(minimum)) * abs(gain) * 0.10
            elif current is not None:
                step = max(1.0, abs(float(current) * gain)) * 0.10
            else:
                step = 1.0
            new_offset = offset + step if command == "offset_up" else offset - step
            self.channel_table.set_gain_offset(channel_id, offset=new_offset)

    def _display_transform_changed(self, channel_id) -> None:
        # Gain/Offset changes only the rendered curve; raw buffer/statistics stay intact.
        self._update_curves()
        if self._hover_x is not None:
            self._update_hover_tooltip(self._hover_x)

    def _selected_channel_changed(self, channel_id) -> None:
        # In Stacked view, Y1/Y2 belong to the selected channel plot. Recreate
        # only those horizontal cursor lines instead of rebuilding every plot.
        if self.view_combo.currentText() == "Stacked":
            for name in ("Y1", "Y2"):
                value = self._cursor_values.get(name)
                line = self._y_lines.get(name)
                if line is not None:
                    for plot in self._plots:
                        try:
                            plot.removeItem(line)
                        except Exception:
                            pass
                    self._y_lines[name] = None
                if value is not None:
                    self._create_y_line(name, float(value))
        self._update_cursor_label()

    def _mouse_moved(self, scene_pos, plot: pg.PlotWidget, channel_id: int | None) -> None:
        if not self._data.x.size:
            self._hide_hover()
            return
        vb = plot.getPlotItem().vb
        try:
            if not vb.sceneBoundingRect().contains(scene_pos):
                return
            point = vb.mapSceneToView(scene_pos)
            x_value = float(point.x())
        except Exception:
            return
        self._hover_x = x_value
        for line in self._hover_lines:
            line.setValue(x_value)
            line.show()
        self._update_hover_tooltip(x_value)

        # Keep the floating readout close to the mouse but inside the plot host.
        try:
            local_plot = plot.mapFromScene(scene_pos)
            local_host = plot.mapTo(self.plot_host, local_plot)
            self.hover_label.adjustSize()
            x = min(max(4, local_host.x() + 14), max(4, self.plot_host.width() - self.hover_label.width() - 4))
            y = min(max(4, local_host.y() + 14), max(4, self.plot_host.height() - self.hover_label.height() - 4))
            self.hover_label.move(x, y)
            self.hover_label.raise_()
            self.hover_label.show()
        except Exception:
            pass

    def _update_hover_tooltip(self, x_value: float) -> None:
        names = self.channel_table.channel_names()
        lines = []
        nearest_x = None
        for cid in self.channel_table.visible_channel_ids():
            pair = self._data.nearest(cid, x_value)
            if pair is None:
                continue
            sample_x, raw = pair
            if nearest_x is None:
                nearest_x = sample_x
            gain, offset = self.channel_table.gain_offset(cid)
            display = raw * gain + offset
            if abs(gain - 1.0) > 1e-12 or abs(offset) > 1e-12:
                lines.append(f"{names.get(cid, cid)}: {raw:.9g}  ->  {display:.9g}")
            else:
                lines.append(f"{names.get(cid, cid)}: {raw:.9g}")
        if nearest_x is None:
            self.hover_label.hide()
            return
        x_unit = " s" if self._x_is_time else ""
        self.hover_label.setText(f"X = {nearest_x:.9g}{x_unit}\n" + "\n".join(lines))

    def _hide_hover(self) -> None:
        self._hover_x = None
        for line in self._hover_lines:
            line.hide()
        if hasattr(self, "hover_label"):
            self.hover_label.hide()

    def _clear_buffered_data(self) -> None:
        self._data.clear()
        self.channel_table.update_statistics({})
        for curve in self._curves.values():
            curve.setData([], [])
        self._hover_x = None
        self._hide_hover()
        self._need_fit = True
        self.actual_label.setText("Actual: -")
        self._update_cursor_label()
        self.log_requested.emit("Scope: buffered data and statistics cleared")

    def _update_axis_labels(self) -> None:
        label = "Time" if self._x_is_time else "Sample Index"
        units = "s" if self._x_is_time else ""
        for plot in self._plots:
            plot.setLabel("bottom", label, units=units)

    def _update_curves(self) -> None:
        for cid, curve in self._curves.items():
            x, y = self._data.curve(cid)
            gain, offset = self.channel_table.gain_offset(cid)
            curve.setData(x, y * gain + offset)
        self.channel_table.update_statistics(self._data.stats_snapshot())
        self._update_axis_labels()
        if self._need_fit and self._data.x.size:
            # First samples: fit Y once, but do not let the tiny initial data
            # width become the live-follow X span. Follow starts with the user
            # configured buffer width and remains manually adjustable afterward.
            self._fit_all(capture_follow_span=False)
            self._need_fit = False
            if self.follow_latest_check.isChecked():
                self._follow_x_span = float(self._data.seconds) if self._x_is_time else max(1.0, float(self._data.x.size))
                self._follow_latest()
        elif self._sampling and self.follow_latest_check.isChecked() and self._data.x.size:
            self._follow_latest()

    def _x_range_changed(self, plot: pg.PlotWidget, x_range) -> None:
        """Remember the user's current X zoom span for live-follow.

        A follow update itself also emits sigXRangeChanged, so those events are
        ignored.  Any mouse/axis/manual zoom is therefore allowed while the
        checkbox remains enabled; the next sample keeps that new span.
        """
        if self._applying_follow_range:
            return
        try:
            low, high = float(x_range[0]), float(x_range[1])
        except Exception:
            return
        span = high - low
        if math.isfinite(span) and span > 1e-12:
            self._follow_x_span = span

    def _current_x_span(self) -> float | None:
        if self._follow_x_span is not None and math.isfinite(self._follow_x_span) and self._follow_x_span > 1e-12:
            return self._follow_x_span
        if self._plots:
            try:
                low, high = self._plots[0].getPlotItem().vb.viewRange()[0]
                span = float(high) - float(low)
                if math.isfinite(span) and span > 1e-12:
                    return span
            except Exception:
                pass
        if self._data.x.size >= 2:
            span = float(self._data.x[-1]) - float(self._data.x[0])
            if math.isfinite(span) and span > 1e-12:
                return span
        return float(self._data.seconds) if self._x_is_time else 1.0

    def _follow_latest_toggled(self, checked: bool) -> None:
        # Single source of truth for live scrolling. Enabling it captures the
        # current user-visible X width; it does not fit/reset X or Y.
        if checked:
            self._follow_x_span = self._current_x_span()
            if self._data.x.size:
                self._follow_latest()

    def _follow_latest(self) -> None:
        if not self._plots or self._data.x.size == 0:
            return
        last_x = float(self._data.x[-1])
        span = self._current_x_span()
        if span is None or not math.isfinite(span) or span <= 1e-12:
            span = float(self._data.seconds) if self._x_is_time else 1.0

        # Preserve every plot's Y range exactly.  This makes live-follow a pure
        # X translation even with linked ViewBoxes or pyqtgraph internals.
        y_ranges = []
        for plot in self._plots:
            try:
                yr = plot.getPlotItem().vb.viewRange()[1]
                y_ranges.append((float(yr[0]), float(yr[1])))
            except Exception:
                y_ranges.append(None)

        left = last_x - span
        right = last_x
        if right <= left:
            right = left + (1e-6 if self._x_is_time else 1.0)

        self._applying_follow_range = True
        try:
            # Stacked plots share X via setXLink(); update only the master plot to
            # avoid N-way linked range notifications on every render frame.
            self._plots[0].setXRange(left, right, padding=0)
            for plot, yr in zip(self._plots, y_ranges):
                if yr is not None:
                    plot.getPlotItem().vb.setYRange(yr[0], yr[1], padding=0)
        finally:
            self._applying_follow_range = False

    @staticmethod
    def _padded_y_range(y_min: float, y_max: float) -> tuple[float, float]:
        """Return a stable display range for a full-buffer Y fit.

        Constant signals (for example an int16 value fixed at 1000) need a
        non-zero range or they collapse onto a single pixel.  For non-constant
        signals use 5% padding on both sides.
        """
        y_min = float(y_min)
        y_max = float(y_max)
        if not (math.isfinite(y_min) and math.isfinite(y_max)):
            return -1.0, 1.0
        span = y_max - y_min
        if span <= 1e-15:
            pad = max(abs(y_min) * 0.05, 1.0)
        else:
            pad = span * 0.05
        return y_min - pad, y_max + pad

    def _full_buffer_x_range(self) -> tuple[float, float] | None:
        """Range of the data that is actually retained by ScopeDataStore.

        This deliberately ignores the current ViewBox range.  The buffer trim
        policy is the source of truth: once a 30 s buffer is full, this range is
        the newest 30 s; before it is full, it is all captured data so there is
        no artificial empty area.
        """
        if self._data.x.size == 0:
            return None
        left = float(self._data.x[0])
        right = float(self._data.x[-1])
        if not (math.isfinite(left) and math.isfinite(right)):
            return None
        if right <= left:
            half = 0.5e-3 if self._x_is_time else 0.5
            return left - half, right + half
        return left, right

    def _channel_display_extrema(self, channel_id: int) -> tuple[float, float] | None:
        raw = self._data.values.get(int(channel_id))
        if raw is None or raw.size == 0:
            return None
        finite = raw[np.isfinite(raw)]
        if finite.size == 0:
            return None
        raw_min = float(np.min(finite))
        raw_max = float(np.max(finite))
        gain, offset = self.channel_table.gain_offset(int(channel_id))
        a = raw_min * float(gain) + float(offset)
        b = raw_max * float(gain) + float(offset)
        return min(a, b), max(a, b)

    def _channel_full_y_range(self, channel_id: int) -> tuple[float, float] | None:
        extrema = self._channel_display_extrema(channel_id)
        if extrema is None:
            return None
        return self._padded_y_range(extrema[0], extrema[1])

    def _fit_all(self, capture_follow_span: bool) -> None:
        """Fit the *entire retained buffer*, independent of current zoom.

        pyqtgraph.autoRange() can inherit current ViewBox/link state and in prior
        versions made "查看所有波形" behave as though the old X width were
        still authoritative.  Here the retained ScopeDataStore is authoritative:
        X is [first buffered sample, last buffered sample], and Y comes from all
        visible buffered samples after Gain/Offset.
        """
        x_range = self._full_buffer_x_range()
        if x_range is None or not self._plots:
            return
        x_left, x_right = x_range

        visible_ids = [cid for cid in self.channel_table.visible_channel_ids() if cid in self._curves]
        mode = self.view_combo.currentText().strip().lower()

        # Overlay uses one common Y range across every visible channel.
        overlay_y: tuple[float, float] | None = None
        if mode == "overlay":
            extrema = [self._channel_display_extrema(cid) for cid in visible_ids]
            extrema = [item for item in extrema if item is not None]
            if extrema:
                overlay_y = self._padded_y_range(
                    min(item[0] for item in extrema),
                    max(item[1] for item in extrema),
                )

        self._applying_follow_range = True
        try:
            # In Stacked mode every plot is X-linked to the first plot. Setting
            # XRange on every linked ViewBox causes a storm of reciprocal range
            # notifications and can freeze the GUI when many channels exist.
            # Set the shared X range exactly once on the master plot.
            for plot in self._plots:
                vb = plot.getPlotItem().vb
                if hasattr(vb, "disableAutoRange"):
                    vb.disableAutoRange()
            self._plots[0].setXRange(x_left, x_right, padding=0)

            if mode == "overlay":
                if overlay_y is not None:
                    self._plots[0].getPlotItem().vb.setYRange(overlay_y[0], overlay_y[1], padding=0)
            else:
                for plot in self._plots:
                    cid = self._plot_channel_ids.get(id(plot))
                    if cid is None:
                        continue
                    yr = self._channel_full_y_range(cid)
                    if yr is not None:
                        plot.getPlotItem().vb.setYRange(yr[0], yr[1], padding=0)
        finally:
            self._applying_follow_range = False

        if capture_follow_span:
            span = x_right - x_left
            if math.isfinite(span) and span > 1e-12:
                self._follow_x_span = span

    def view_all(self) -> None:
        # Explicit user action: first paint any pending raw data immediately,
        # then fit the entire retained buffer. It does not change the follow
        # checkbox. If follow is enabled, the complete buffered width becomes
        # the new rolling X span on subsequent samples.
        if self._render_dirty:
            self._render_if_dirty()
        self._fit_all(capture_follow_span=True)

    # ---------- Cursor logic ----------
    def _install_cursor_lines(self) -> None:
        for name in ("X1", "X2"):
            value = self._cursor_values[name]
            if value is None:
                continue
            self._create_x_lines(name, value)
        for name in ("Y1", "Y2"):
            value = self._cursor_values[name]
            if value is not None:
                self._create_y_line(name, value)

    def _plot_clicked(self, event, plot: pg.PlotWidget, channel_id: int | None) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if channel_id is not None:
                self.channel_table.select_channel_id(channel_id)
            return
        if event.button() != Qt.MouseButton.RightButton:
            return
        if channel_id is not None:
            self.channel_table.select_channel_id(channel_id)
        pos = plot.getPlotItem().vb.mapSceneToView(event.scenePos())
        menu = QMenu(self)
        actions = {
            menu.addAction("设置 X1"): lambda: self.set_cursor("X1", float(pos.x())),
            menu.addAction("设置 X2"): lambda: self.set_cursor("X2", float(pos.x())),
            menu.addAction("设置 Y1"): lambda: self.set_cursor("Y1", float(pos.y())),
            menu.addAction("设置 Y2"): lambda: self.set_cursor("Y2", float(pos.y())),
        }
        menu.addSeparator()
        for key in ("X1", "X2", "Y1", "Y2"):
            action = menu.addAction(f"删除 {key}")
            actions[action] = lambda k=key: self.delete_cursor(k)
        menu.addSeparator()
        actions[menu.addAction("删除全部游标")] = self.delete_all_cursors
        menu.addSeparator()
        actions[menu.addAction("导出缓存数据...")] = self._export_data
        actions[menu.addAction("清空缓存数据")] = self._clear_buffered_data
        screen_pos = event.screenPos()
        chosen = menu.exec(screen_pos.toPoint() if hasattr(screen_pos, "toPoint") else screen_pos)
        if chosen in actions:
            actions[chosen]()
        event.accept()

    def set_cursor(self, name: str, value: float) -> None:
        self._cursor_values[name] = float(value)
        if name.startswith("X"):
            for line in self._x_lines[name]:
                for plot in self._plots:
                    try:
                        plot.removeItem(line)
                    except Exception:
                        pass
            self._x_lines[name] = []
            self._create_x_lines(name, value)
        else:
            line = self._y_lines.get(name)
            if line is not None:
                for plot in self._plots:
                    try:
                        plot.removeItem(line)
                    except Exception:
                        pass
            self._y_lines[name] = None
            self._create_y_line(name, value)
        self._update_cursor_label()

    def _create_x_lines(self, name: str, value: float) -> None:
        lines = []
        for plot in self._plots:
            line = pg.InfiniteLine(pos=value, angle=90, movable=True, label=name, labelOpts={"position": 0.92})
            line.sigPositionChanged.connect(lambda ln, k=name: self._x_line_moved(k, ln))
            plot.addItem(line)
            lines.append(line)
        self._x_lines[name] = lines

    def _selected_plot(self) -> pg.PlotWidget | None:
        if not self._plots:
            return None
        if self.view_combo.currentText() == "Overlay":
            return self._plots[0]
        selected = self.channel_table.selected_channel_id()
        visible = self.channel_table.visible_channel_ids()
        if selected in visible:
            return self._plots[visible.index(selected)]
        return self._plots[0]

    def _create_y_line(self, name: str, value: float) -> None:
        plot = self._selected_plot()
        if plot is None:
            return
        line = pg.InfiniteLine(pos=value, angle=0, movable=True, label=name, labelOpts={"position": 0.92})
        line.sigPositionChanged.connect(lambda ln, k=name: self._y_line_moved(k, ln))
        plot.addItem(line)
        self._y_lines[name] = line

    def _x_line_moved(self, name: str, line: pg.InfiniteLine) -> None:
        if self._syncing_cursor:
            return
        self._syncing_cursor = True
        try:
            value = float(line.value())
            self._cursor_values[name] = value
            for other in self._x_lines[name]:
                if other is not line:
                    other.setValue(value)
        finally:
            self._syncing_cursor = False
        self._update_cursor_label()

    def _y_line_moved(self, name: str, line: pg.InfiniteLine) -> None:
        self._cursor_values[name] = float(line.value())
        self._update_cursor_label()

    def delete_cursor(self, name: str) -> None:
        self._cursor_values[name] = None
        if name.startswith("X"):
            for line in self._x_lines[name]:
                for plot in self._plots:
                    try:
                        plot.removeItem(line)
                    except Exception:
                        pass
            self._x_lines[name] = []
        else:
            line = self._y_lines.get(name)
            if line is not None:
                for plot in self._plots:
                    try:
                        plot.removeItem(line)
                    except Exception:
                        pass
            self._y_lines[name] = None
        self._update_cursor_label()

    def delete_all_cursors(self) -> None:
        for name in ("X1", "X2", "Y1", "Y2"):
            self.delete_cursor(name)

    def _update_cursor_label(self) -> None:
        x1, x2 = self._cursor_values["X1"], self._cursor_values["X2"]
        y1, y2 = self._cursor_values["Y1"], self._cursor_values["Y2"]
        selected = self.channel_table.selected_channel_id()
        selected_name = self.channel_table.selected_channel_name() or "-"
        at1 = self._data.nearest(selected, x1) if selected is not None and x1 is not None else None
        at2 = self._data.nearest(selected, x2) if selected is not None and x2 is not None else None
        x_unit = " s" if self._x_is_time else ""

        def f(v):
            return "-" if v is None else f"{v:.9g}"

        dx = None if x1 is None or x2 is None else abs(x2 - x1)
        dy = None if y1 is None or y2 is None else abs(y2 - y1)
        v1 = None if at1 is None else at1[1]
        v2 = None if at2 is None else at2[1]
        self.cursor_label.setText(
            f"X1={f(x1)}{x_unit}  X2={f(x2)}{x_unit}  ΔX={f(dx)}{x_unit}    "
            f"Y1={f(y1)}  Y2={f(y2)}  ΔY={f(dy)}    "
            f"Selected={selected_name}  Value@X1={f(v1)}  Value@X2={f(v2)}"
        )

    # ---------- Persistence ----------
    def settings_state(self) -> dict:
        if self._source == "HSS":
            try:
                hss_json = self.channel_table.to_json()
            except Exception:
                hss_json = self._hss_saved_json
        else:
            hss_json = self._hss_saved_json
        return {
            "source": self._source,
            "sample_hz": self.sample_hz_spin.value(),
            "buffer_seconds": self.buffer_seconds_spin.value(),
            "fps": self._fps_value(),
            "view": self.view_combo.currentText(),
            "follow_latest": self.follow_latest_check.isChecked(),
            "hss_channels": hss_json,
        }

    def load_settings_state(self, state: dict) -> None:
        self._hss_saved_json = str(state.get("hss_channels", "[]") or "[]")
        try:
            self.sample_hz_spin.setValue(int(state.get("sample_hz", 1000)))
        except Exception:
            pass
        try:
            self.buffer_seconds_spin.setValue(int(state.get("buffer_seconds", self.DEFAULT_BUFFER_SECONDS)))
        except Exception:
            pass
        try:
            self.fps_combo.setCurrentText(str(max(1, min(60, int(state.get("fps", 30))))))
        except Exception:
            self.fps_combo.setCurrentText("30")
        self._fps_changed()
        view = str(state.get("view", "Overlay"))
        if self.view_combo.findText(view) >= 0:
            self.view_combo.setCurrentText(view)
        self.follow_latest_check.setChecked(bool(state.get("follow_latest", True)))

        # Populate the saved HSS selection before changing Source. Otherwise the
        # HSS->RTT transition would save the default Value1 over the persisted list.
        self.channel_table.clear_channels()
        self.channel_table.set_rtt_mode(False)
        try:
            self.channel_table.load_json(self._hss_saved_json)
        except Exception:
            pass
        if self.channel_table.rowCount() == 0:
            self.channel_table.add_channel("Value1", "0x20000000", "float")
        self._hss_saved_json = self.channel_table.to_json()

        source = str(state.get("source", "HSS")).upper()
        source = source if source in ("HSS", "RTT") else "HSS"
        if self.source_combo.currentText() != source:
            self.source_combo.setCurrentText(source)
        else:
            self._source = source
            self._update_controls()
        self._rebuild_plots()
