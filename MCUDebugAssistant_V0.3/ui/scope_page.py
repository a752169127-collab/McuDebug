from __future__ import annotations

import csv
import json
import math
import time
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QBrush, QColor, QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QFrame,
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
from core.scope_buffer import ScopeDataStore


class ScopeChannelTable(QTableWidget):
    definition_changed = Signal()
    display_changed = Signal(object)
    visibility_changed = Signal(object)
    selected_channel_changed = Signal(object)
    command_requested = Signal(str)
    color_changed = Signal(object)

    COL_VISIBLE = 0
    COL_COLOR = 1
    COL_NAME = 2
    COL_ADDRESS = 3
    COL_TYPE = 4
    COL_CURRENT = 5
    COL_AVG = 6
    COL_MIN = 7
    COL_MAX = 8
    COL_GAIN = 9
    COL_OFFSET = 10
    HEADERS = ["Show", "", "Name", "Address", "Type", "Current", "Average", "Min", "Max", "Gain", "Offset"]
    DEFAULT_COLORS = [
        "#ff3030", "#00e5ff", "#2979ff", "#00e676", "#ffd740",
        "#e040fb", "#ff6d00", "#64ffda", "#ffffff", "#7c4dff",
    ]

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
        self.setColumnWidth(self.COL_VISIBLE, 48)
        self.setColumnWidth(self.COL_COLOR, 30)
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
        self.cellDoubleClicked.connect(self._cell_double_clicked)

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._internal_update:
            return
        if item.column() == self.COL_VISIBLE:
            # Show is display state only. It must never redefine HSS channels or
            # disturb the retained raw Scope buffer. This mirrors J-Scope: a
            # hidden channel keeps sampling and can be shown later with its full
            # capture history intact.
            cid = self._channel_id_for_row(item.row())
            self.visibility_changed.emit(cid)
        elif item.column() in (self.COL_GAIN, self.COL_OFFSET):
            try:
                float(item.text().strip())
            except ValueError:
                return
            cid = self._channel_id_for_row(item.row())
            self.display_changed.emit(cid)
        elif item.column() == self.COL_COLOR:
            cid = self._channel_id_for_row(item.row())
            self.color_changed.emit(cid)
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
        color: str | None = None,
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
        color_text = str(color or self.DEFAULT_COLORS[(cid - 1) % len(self.DEFAULT_COLORS)])
        self._set_color_item(row, color_text)
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
                gain, offset = self.gain_offset(cid)
                old_display[(cid, name_item.text().strip())] = (gain, offset, self.channel_color(cid))
        blocked = self.blockSignals(True)
        self._internal_update = True
        try:
            self.setRowCount(0)
            self._next_id = 1
            for ch in channels:
                cid = int(ch.get("channel_id", self.rowCount() + 1))
                name = str(ch.get("name", f"RTT_Value{self.rowCount()+1}"))
                gain, offset, color = old_display.get(
                    (cid, name),
                    (1.0, 0.0, self.DEFAULT_COLORS[(max(1, cid) - 1) % len(self.DEFAULT_COLORS)]),
                )
                self.add_channel(
                    name=name,
                    address="-",
                    type_name=str(ch.get("type_name", "uint32")),
                    enabled=True,
                    channel_id=cid,
                    gain=gain,
                    offset=offset,
                    color=color,
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
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
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

    def _set_color_item(self, row: int, color_text: str) -> None:
        color = QColor(str(color_text))
        if not color.isValid():
            color = QColor(self.DEFAULT_COLORS[row % len(self.DEFAULT_COLORS)])
        item = self.item(row, self.COL_COLOR)
        old_guard = self._internal_update
        self._internal_update = True
        try:
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.setItem(row, self.COL_COLOR, item)
            # J-Scope-style pure swatch: keep the actual color as metadata and
            # deliberately show no #RRGGBB text in the table.
            item.setText("")
            item.setData(Qt.ItemDataRole.UserRole, color.name())
            item.setBackground(QBrush(color))
            item.setToolTip(f"波形颜色 {color.name().upper()}；双击修改")
        finally:
            self._internal_update = old_guard

    def _cell_double_clicked(self, row: int, column: int) -> None:
        if column != self.COL_COLOR:
            return
        cid = self._channel_id_for_row(row)
        if cid is None:
            return
        current = QColor(self.channel_color(cid))
        chosen = QColorDialog.getColor(current, self, "选择波形颜色")
        if not chosen.isValid():
            return
        self._set_color_item(row, chosen.name())
        self.color_changed.emit(cid)

    def channel_color(self, channel_id: int) -> str:
        for row in range(self.rowCount()):
            if self._channel_id_for_row(row) != int(channel_id):
                continue
            item = self.item(row, self.COL_COLOR)
            if item is not None:
                stored = item.data(Qt.ItemDataRole.UserRole)
                color = QColor(str(stored or ""))
                if color.isValid():
                    return color.name()
        return self.DEFAULT_COLORS[(max(1, int(channel_id)) - 1) % len(self.DEFAULT_COLORS)]

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
                enabled=True,  # Show only hides/shows; hidden channels keep sampling/history.
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
        # setFlags()/setEnabled() can cause QTableWidget to emit itemChanged on
        # some Qt/Windows builds. During Pause, that previously escaped through
        # _item_changed() as definition_changed -> _rebuild_plots(), replacing
        # the current ViewBox with a fresh default range. The raw Scope buffer
        # was still present, but every curve appeared empty, which looked exactly
        # like Pause had cleared the capture. Editability is UI state only, so
        # suppress table notifications while changing it.
        self._definition_editable = bool(editable)
        old_guard = self._internal_update
        blocked = self.blockSignals(True)
        self._internal_update = True
        try:
            self._update_editability()
        finally:
            self._internal_update = old_guard
            self.blockSignals(blocked)

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
        visible_ids = set(self.visible_channel_ids())
        for spec in self.specs():
            gain, offset = self.gain_offset(spec.channel_id)
            rows.append({
                "name": spec.name,
                "address": spec.address,
                "type": spec.type_name,
                "enabled": spec.channel_id in visible_ids,
                "gain": gain,
                "offset": offset,
                "color": self.channel_color(spec.channel_id),
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
                color=str(row.get("color") or "") or None,
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
    left_drag_started = Signal()
    left_drag_finished = Signal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._left_press_pos = None
        self._left_drag_emitted = False

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                self._left_press_pos = event.position()
            except Exception:
                self._left_press_pos = None
            self._left_drag_emitted = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        # A normal left click must not disable live follow. Only when the pointer
        # has actually moved a few pixels with the left button held do we treat
        # the gesture as a manual waveform pan/drag.
        if (
            not self._left_drag_emitted
            and self._left_press_pos is not None
            and bool(event.buttons() & Qt.MouseButton.LeftButton)
        ):
            try:
                delta = event.position() - self._left_press_pos
                if abs(float(delta.x())) + abs(float(delta.y())) >= 4.0:
                    self._left_drag_emitted = True
                    self.left_drag_started.emit()
            except Exception:
                pass
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._left_drag_emitted
            self._left_press_pos = None
            self._left_drag_emitted = False
            if was_dragging:
                self.left_drag_finished.emit()

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


class ScopePage(QWidget):
    # Follow scrolling is adaptive. Overlay may scroll at the requested GUI FPS;
    # Stacked shares a bounded total ViewBox update budget across all plots.
    # With 3 channels and FPS=60 this gives ~30 Hz X scrolling instead of the
    # visibly stepped 12 Hz used by V0.3.11, while avoiding the old 180 range
    # writes/s path that could freeze Qt.
    FOLLOW_STACKED_VIEWBOX_BUDGET_HZ = 90.0
    STATS_REFRESH_MAX_HZ = 10.0
    # Curve data itself does not need to be rebuilt at the full viewport FPS.
    # Keeping curve materialization at <=30 Hz leaves much more GUI budget for
    # smooth ViewBox transforms while Follow can still animate at 60 FPS.
    CURVE_REFRESH_MAX_HZ = 30.0
    # During a manual pan all curves are frozen into an interaction cache, so
    # follower ViewBoxes can be synchronized more frequently without also
    # paying curve.setData()/downsampling cost on every mouse move.
    MANUAL_STACKED_SYNC_HZ = 60.0

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
        self._curve_colors: dict[int, object] = {}
        self._mouse_proxies: list[object] = []
        self._plot_signal_connections: list[tuple[object, object]] = []
        self._rebuilding_plots = False
        self._hover_x: float | None = None
        self._hover_plot: pg.PlotWidget | None = None
        self._hover_scene_pos = None
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
        # Do not use pyqtgraph ViewBox XLink for Stacked live scrolling. With
        # three or more linked ViewBoxes, repeated setXRange() can trigger a
        # cascade of reciprocal linked-view updates on Windows. We synchronize
        # X ranges ourselves under this re-entry guard instead.
        self._syncing_x_range = False
        self._last_follow_right: float | None = None
        self._last_follow_span: float | None = None
        self._last_follow_scroll_at = 0.0
        self._last_stats_refresh_at = 0.0
        self._last_curve_refresh_at = 0.0
        self._curve_data_pending = False
        self._user_dragging = False
        # Interaction cache: while panning, curves contain a lightweight
        # full-buffer snapshot and never receive setData().  Mouse movement then
        # mostly changes the ViewBox transform instead of rebuilding waveform
        # arrays.  On release the current viewport is redrawn at full detail.
        self._interaction_cache_active = False
        self._interaction_cache_range: tuple[float, float] | None = None
        self._latest_data_arrival_at = 0.0
        self._latest_data_x: float | None = None
        self._render_frames = 0
        self._render_rate_started_at = time.perf_counter()

        # Scope acquisition and rendering are intentionally decoupled. Raw samples
        # are appended whenever the worker emits a chunk (up to 60 Hz), while
        # pyqtgraph redraws at the user-selected FPS.
        self._render_dirty = False
        # Rendering has two independent causes: new acquisition data and a
        # changed viewport/display transform. When live-follow is OFF, samples
        # arriving to the right of a fixed historical X window do not change
        # what is visible, so we intentionally skip curve.setData(). This is
        # the key to keeping history pan/zoom responsive while acquisition keeps
        # running in the background.
        self._view_dirty = True
        self._force_curve_redraw = True
        self._last_rendered_data_first_x: float | None = None
        self._last_rendered_data_last_x: float | None = None
        self._pending_shared_x_range: tuple[float, float, object] | None = None
        self._last_manual_x_sync_at = 0.0
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
        self.channel_table.visibility_changed.connect(self._channel_visibility_changed)
        self.channel_table.selected_channel_changed.connect(self._selected_channel_changed)
        self.channel_table.command_requested.connect(self._table_key_command)
        self.channel_table.color_changed.connect(self._channel_color_changed)
        splitter.addWidget(self.channel_table)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([620, 170])
        layout.addWidget(splitter, 1)

        # Mouse probe is a QWidget overlay instead of a pyqtgraph InfiniteLine.
        # A data-coordinate InfiniteLine is translated by every live-follow X-range
        # change even when the mouse itself is stationary; on some Windows/Qt
        # paint paths that produced the accumulated vertical "ghost lines" seen in
        # long-running Stacked captures.  The pixel overlay stays attached to the
        # mouse and does not invalidate any PlotDataItem.
        self.hover_vline = QFrame(self.plot_host)
        self.hover_vline.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hover_vline.setFrameShape(QFrame.Shape.NoFrame)
        self.hover_vline.setStyleSheet("background: rgba(210, 210, 210, 180);")
        self.hover_vline.setFixedWidth(1)
        self.hover_vline.hide()

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

    def _build_toolbar(self) -> QGridLayout:
        # Two compact rows keep the main window genuinely horizontally resizable.
        # The old one-line HBox imposed a very large minimum width because every
        # Scope control contributed to the layout's minimumSizeHint.
        bar = QGridLayout()
        bar.setHorizontalSpacing(8)
        bar.setVerticalSpacing(4)
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
        self.view_combo.currentTextChanged.connect(self._view_changed)
        self.buffer_seconds_spin = QSpinBox()
        self.buffer_seconds_spin.setRange(1, 120)
        self.buffer_seconds_spin.setValue(int(self.DEFAULT_BUFFER_SECONDS))
        self.buffer_seconds_spin.setSuffix(" s")
        self.buffer_seconds_spin.setToolTip("Scope 内存缓存时间；右键波形可导出当前缓存中的原始采样数据")
        self.buffer_seconds_spin.valueChanged.connect(self._buffer_seconds_changed)
        self.fps_combo = QComboBox()
        self.fps_combo.setEditable(True)
        self.fps_combo.addItems(["1", "2", "5", "10", "15", "20", "25", "30", "40", "50", "60"])
        self.fps_combo.setCurrentText("30")
        self.fps_combo.setToolTip("Scope 固定渲染时钟 1~60 FPS；不改变 HSS/RTT 实际采样频率")
        if self.fps_combo.lineEdit() is not None:
            self.fps_combo.lineEdit().setValidator(QIntValidator(1, 60, self.fps_combo))
            self.fps_combo.lineEdit().editingFinished.connect(self._fps_changed)
        self.fps_combo.activated.connect(lambda *_: self._fps_changed())
        self.view_all_btn = QPushButton("查看所有波形")
        self.view_all_btn.clicked.connect(self.view_all)
        self.follow_latest_check = QCheckBox("跟随最新数据")
        self.follow_latest_check.setChecked(True)
        self.follow_latest_check.setToolTip("勾选后按固定渲染节拍平滑滚动；手动左键拖动会自动取消跟随")
        self.follow_latest_check.toggled.connect(self._follow_latest_toggled)
        self.actual_label = QLabel("Actual: -")
        self.start_btn = QPushButton("开始采样")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("暂停采样")
        self.stop_btn.clicked.connect(self.stop_requested.emit)

        # Row 0: acquisition / display setup.
        widgets0 = [
            QLabel("Source"), self.source_combo, self.add_btn, self.remove_btn,
            QLabel("Sampling"), self.sample_hz_spin, self.period_label,
            QLabel("View"), self.view_combo, QLabel("Buffer"), self.buffer_seconds_spin,
            QLabel("FPS"), self.fps_combo,
        ]
        for col, widget in enumerate(widgets0):
            bar.addWidget(widget, 0, col)

        # Row 1: view state and transport; stretch before Start/Pause.
        bar.addWidget(self.view_all_btn, 1, 0, 1, 2)
        bar.addWidget(self.follow_latest_check, 1, 2, 1, 2)
        bar.addWidget(self.actual_label, 1, 4, 1, 3)
        bar.setColumnStretch(7, 1)
        bar.addWidget(self.start_btn, 1, 11)
        bar.addWidget(self.stop_btn, 1, 12)
        return bar

    def set_connected(self, connected: bool) -> None:
        self._connected = bool(connected)
        self._update_controls()

    def set_sampling(self, active: bool, source_text: str = "") -> None:
        previous = self._sampling
        self._sampling = bool(active)
        if not active:
            # Pause is an analysis state. Preserve the last measured acquisition
            # rate instead of replacing it with '-', so the captured data keeps
            # its sampling context while the user inspects it.
            if self._latest_actual_hz > 0:
                self.actual_label.setText(f"Actual: {self._latest_actual_hz:.4g} Hz (paused)")
        self._update_controls()

        if previous == self._sampling:
            return

        if self._sampling:
            if self._latest_actual_hz > 0:
                self.actual_label.setText(f"Actual: {self._latest_actual_hz:.4g} Hz")
            # Start begins a fresh acquisition session; _start() has already
            # cleared the previous buffer. The first arriving samples perform
            # the initial fit through _need_fit.
        else:
            # Pause is an analysis operation: stop acquisition and preserve the
            # exact current X/Y window. Flush only the newest pending display
            # state; never call View All / fit here.
            if self._render_dirty:
                QTimer.singleShot(0, self._render_if_dirty)

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
        if self._rebuilding_plots:
            return

        # The timer is the sole GUI render clock. Acquisition can be bursty, but
        # curve materialization and viewport animation are intentionally
        # decoupled so a 60 FPS UI does not imply 60 expensive setData() calls.
        data_dirty = bool(self._render_dirty)
        if data_dirty:
            self._render_dirty = False
            self._curve_data_pending = True

        now = time.perf_counter()

        # Manual pan is interaction-priority mode.  Do *not* touch QTableWidget,
        # hover/nearest-value lookup, curve data, or statistics text while the
        # mouse is held.  HSS/RTT still appends raw samples in the background.
        if self._user_dragging:
            self._flush_pending_manual_x_sync(force=False)
            self._render_frames += 1
            return

        if data_dirty and now - self._last_stats_refresh_at >= 1.0 / self.STATS_REFRESH_MAX_HZ:
            self.channel_table.update_statistics(self._data.stats_snapshot())
            self._last_stats_refresh_at = now
            if self._latest_actual_hz > 0:
                suffix = "" if self._sampling else " (paused)"
                self.actual_label.setText(f"Actual: {self._latest_actual_hz:.4g} Hz{suffix}")

        follow_moved = False
        follow_enabled = self._sampling and self.follow_latest_check.isChecked() and self._data.has_data
        if follow_enabled:
            follow_moved = self._follow_latest(force=False, smooth=True)

        redraw = bool(self._force_curve_redraw or self._view_dirty)
        if self._curve_data_pending and not redraw:
            if follow_enabled:
                redraw = True
            else:
                redraw = self._new_data_affects_visible_window()

        # Cap expensive curve rebuilds independently from the viewport/render
        # FPS.  A 60 FPS Follow still moves smoothly, while the waveform samples
        # are refreshed up to 30 times/s (or immediately for explicit zoom/
        # display changes).  Keep the pending bit set when a frame is skipped.
        explicit_redraw = bool(self._force_curve_redraw or self._view_dirty)
        if redraw and not explicit_redraw and self._last_curve_refresh_at > 0.0:
            if now - self._last_curve_refresh_at < 1.0 / self.CURVE_REFRESH_MAX_HZ:
                redraw = False

        if redraw:
            self._update_curves(skip_follow=True)
            self._update_cursor_label()
            self._force_curve_redraw = False
            self._view_dirty = False
            self._curve_data_pending = False
            self._last_curve_refresh_at = now
            self._last_rendered_data_first_x = self._data.first_x
            self._last_rendered_data_last_x = self._data.last_x
        elif follow_moved:
            self._refresh_hover_probe()

        self._render_frames += 1

    def _new_data_affects_visible_window(self) -> bool:
        """Whether appended/trimmed raw data can change the fixed visible X slice.

        With Follow disabled, a window such as 10..12 s is visually immutable
        once acquisition has progressed past 12 s. Rebuilding the exact same
        curve 30/60 times per second only steals GUI time from pan/zoom. We do
        redraw while the newest data is still entering the window, and again if
        rolling-buffer trimming reaches that historical window.
        """
        if not self._data.has_data:
            return False
        visible = self._current_visible_x_range()
        if visible is None:
            return True
        _low, high = visible
        prev_last = self._last_rendered_data_last_x
        if prev_last is None or high >= float(prev_last) - 1e-12:
            return True
        prev_first = self._last_rendered_data_first_x
        first = self._data.first_x
        if first is not None and prev_first is not None:
            # If the rolling buffer's left edge advances through (or completely
            # past) this viewport, old displayed samples have expired and the
            # fixed history window must be refreshed once, possibly to blank.
            if float(first) > float(prev_first) + 1e-12 and float(prev_first) <= high:
                return True
        return False

    def _flush_pending_manual_x_sync(self, force: bool = False) -> None:
        pending = self._pending_shared_x_range
        if pending is None or self.view_combo.currentText() != "Stacked":
            return
        now = time.perf_counter()
        if not force and self._last_manual_x_sync_at > 0.0:
            if now - self._last_manual_x_sync_at < 1.0 / self.MANUAL_STACKED_SYNC_HZ:
                return
        low, high, source_plot = pending
        self._pending_shared_x_range = None
        self._last_manual_x_sync_at = now
        self._set_shared_x_range(float(low), float(high), source_plot=source_plot)

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
            self._last_follow_right = None
            self._follow_latest(force=True)

    def _export_data(self) -> None:
        if not self._data.has_data:
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
                # Stream chunked raw data directly to CSV. This avoids materializing
                # one huge full-buffer array when the capture has run for a long time.
                for x, values in self._data.iter_rows(channel_ids):
                    row = [f"{float(x):.12g}"]
                    row.extend("" if value is None else f"{float(value):.12g}" for value in values)
                    writer.writerow(row)
            self.log_requested.emit(
                f"Scope export: {self._data.sample_count} sample(s), {len(channel_ids)} channel(s) -> {path}"
            )
        except Exception as exc:
            self.log_requested.emit(f"Scope export ERROR: {exc}")

    def _start(self) -> None:
        try:
            specs = self.channel_table.specs() if self._source == "HSS" else []
            if self._source == "HSS" and not specs:
                raise ValueError("至少添加一个 Scope 成员")
            # A Start begins a fresh acquisition session. Pause is the operation
            # used to retain/analyse the current capture; pressing Start again
            # intentionally clears the old raw buffer and statistics first.
            self._clear_buffered_data(log_message=False)
            self._need_fit = True
            self.start_requested.emit(self._source, specs, self.sample_hz_spin.value())
            self.log_requested.emit("Scope: new acquisition session; previous buffered data cleared")
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
            + (" | resumed existing capture" if compatible_resume and self._data.has_data else "")
        )

    def append_samples(self, times, values, actual_hz: float, x_is_time: bool) -> None:
        self._x_is_time = bool(x_is_time)
        self._data.append(times, values, x_is_time)
        self._latest_data_arrival_at = time.perf_counter()
        self._latest_data_x = self._data.last_x
        if actual_hz > 0:
            self._latest_actual_hz = float(actual_hz)
        # Do not redraw pyqtgraph for every acquisition chunk. The render timer
        # consumes only the newest state at the selected 1..60 FPS, while every
        # sample remains in ScopeDataStore and contributes to statistics/export.
        self._render_dirty = True
        self._curve_data_pending = True

    def _view_changed(self, _view: str) -> None:
        # Rebuild the presentation graph once, then align the retained capture just
        # like an explicit View All.  This makes Overlay <-> Stacked deterministic
        # and prevents a previous mode's zoom from leaking into the new layout.
        self._rebuild_plots()
        if self._data.has_data:
            self._align_full_buffer()

    def _disconnect_plot_signals(self) -> None:
        # Explicitly break every Python/Qt signal connection before scheduling old
        # PlotWidgets for deletion.  Stacked mode creates many linked ViewBoxes;
        # relying on deleteLater() alone can leave old linked plots alive until the
        # event loop catches up, so repeated Stacked <-> Overlay switches used to
        # accumulate callbacks and eventually freeze the GUI.
        for signal, slot in self._plot_signal_connections:
            try:
                signal.disconnect(slot)
            except Exception:
                pass
        self._plot_signal_connections = []
        for proxy in self._mouse_proxies:
            try:
                disconnect = getattr(proxy, "disconnect", None)
                if callable(disconnect):
                    disconnect()
            except Exception:
                pass
        self._mouse_proxies = []

    def _clear_plot_layout(self) -> None:
        self._disconnect_plot_signals()

        # Defensive cleanup for projects opened from older versions which may
        # still have pyqtgraph XLink state. V0.3.10 itself no longer creates it.
        for plot in list(self._plots):
            try:
                plot.setXLink(None)
            except Exception:
                try:
                    plot.getPlotItem().vb.setXLink(None)
                except Exception:
                    pass
            try:
                plot.clear()
            except Exception:
                pass
            try:
                plot.hide()
            except Exception:
                pass

        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                try:
                    widget.setParent(None)
                    widget.close()
                except Exception:
                    pass
                widget.deleteLater()

        self._plots = []
        self._curves = {}
        self._curve_colors = {}
        self._plot_channel_ids = {}
        self._hover_plot = None
        self._hover_scene_pos = None
        self._x_lines = {"X1": [], "X2": []}
        self._y_lines = {"Y1": None, "Y2": None}
        if hasattr(self, "hover_vline"):
            self.hover_vline.hide()
        if hasattr(self, "hover_label"):
            self.hover_label.hide()

    def _rebuild_plots(self) -> None:
        if not hasattr(self, "plot_layout") or self._rebuilding_plots:
            return

        # Plot reconstruction must not silently reset a retained capture to the
        # new ViewBox default 0..1 range. Keep the user's current X window; a
        # View-mode switch can explicitly request View All afterwards.
        previous_x_range = self._current_visible_x_range() if self._plots else None
        self._rebuilding_plots = True
        timer_was_active = self._render_timer.isActive() if hasattr(self, "_render_timer") else False
        if timer_was_active:
            self._render_timer.stop()
        self.plot_host.setUpdatesEnabled(False)
        try:
            self._clear_plot_layout()
            all_ids = self.channel_table.ordered_channel_ids()
            visible_set = set(self.channel_table.visible_channel_ids())
            names = self.channel_table.channel_names()
            if not all_ids:
                empty = QLabel("没有 Scope 波形通道")
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.plot_layout.addWidget(empty)
            elif self.view_combo.currentText() == "Overlay":
                plot = self._new_plot(None, track_x_range=True)
                self.plot_layout.addWidget(plot, 1)
                self._plots.append(plot)
                self._plot_channel_ids[id(plot)] = None
                plot.addLegend(offset=(8, 8))
                for i, cid in enumerate(all_ids):
                    color = QColor(self.channel_table.channel_color(cid))
                    self._curve_colors[cid] = color
                    # PlotCurveItem is lighter than PlotDataItem for pure
                    # oscilloscope lines (no scatter/data-mapping machinery).
                    curve = pg.PlotCurveItem(pen=pg.mkPen(color, width=1.2))
                    plot.addItem(curve)
                    try:
                        plot.getPlotItem().legend.addItem(curve, names.get(cid, str(cid)))
                    except Exception:
                        pass
                    curve.setVisible(cid in visible_set)
                    self._curves[cid] = curve
                self._update_overlay_selection_style()
            else:
                for i, cid in enumerate(all_ids):
                    # Every Stacked plot owns an X-range listener, but there is no
                    # pyqtgraph XLink. Manual pan/zoom is propagated once by our
                    # guarded synchronizer; live-follow uses the same path. This
                    # avoids linked-ViewBox callback cascades with 3+ channels.
                    plot = self._new_plot(cid, track_x_range=True)
                    plot.setLabel("left", names.get(cid, str(cid)))
                    color = QColor(self.channel_table.channel_color(cid))
                    self._curve_colors[cid] = color
                    curve = pg.PlotCurveItem(pen=pg.mkPen(color, width=1.2))
                    plot.addItem(curve)
                    self._curves[cid] = curve
                    self._plots.append(plot)
                    self._plot_channel_ids[id(plot)] = cid
                    self.plot_layout.addWidget(plot, 1)
                    plot.setVisible(cid in visible_set)

            self._install_cursor_lines()
            self._update_axis_labels()
            # Repaint exactly once after the new display graph is complete. Data
            # acquisition may continue in the worker while this GUI rebuild runs.
            self._render_dirty = True
        finally:
            self.plot_host.setUpdatesEnabled(True)
            self.plot_host.update()
            self._rebuilding_plots = False
            if timer_was_active:
                self._render_timer.start()

        # Restore the previous X window before materializing the new curves.
        # Without this ordering, the fresh pyqtgraph ViewBox is 0..1, so the
        # first curve build contains only 0..1 s; later fitting the axis wider
        # leaves the curve data itself truncated until another refresh arrives.
        if previous_x_range is not None and self._data.has_data:
            try:
                self._set_shared_x_range(float(previous_x_range[0]), float(previous_x_range[1]))
            except Exception:
                pass
        self._view_dirty = True
        self._force_curve_redraw = True
        self._render_dirty = True
        self._curve_data_pending = True
        self._interaction_cache_active = False
        self._interaction_cache_range = None
        # Populate the new curves once immediately. Subsequent updates return to
        # the configured FPS timer.
        self._render_if_dirty()

    def _remember_connection(self, signal, slot) -> None:
        signal.connect(slot)
        self._plot_signal_connections.append((signal, slot))

    def _new_plot(self, channel_id: int | None, track_x_range: bool = False) -> pg.PlotWidget:
        plot = ScopePlotWidget()
        plot.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.setMouseEnabled(x=True, y=True)
        plot_item = plot.getPlotItem()
        plot_item.setClipToView(True)
        # ScopeDataStore already performs phase-stable display decimation.  Do
        # not ask pyqtgraph to auto-downsample the same data a second time; the
        # auto factor changes as the ViewBox scrolls and can make the waveform
        # appear to "breathe" or move back and forth.
        plot_item.setDownsampling(ds=1, auto=False, mode="peak")
        if hasattr(plot_item, "setMenuEnabled"):
            plot_item.setMenuEnabled(False)
        if hasattr(plot_item, "hideButtons"):
            plot_item.hideButtons()
        vb = plot_item.vb
        if hasattr(vb, "setMenuEnabled"):
            vb.setMenuEnabled(False)
        if hasattr(vb, "disableAutoRange"):
            vb.disableAutoRange()

        if track_x_range and hasattr(vb, "sigXRangeChanged"):
            range_slot = lambda _vb, rng, p=plot: self._x_range_changed(p, rng)
            self._remember_connection(vb.sigXRangeChanged, range_slot)

        command_slot = lambda command, p=plot: self._plot_key_command(command, p)
        self._remember_connection(plot.command_requested, command_slot)
        self._remember_connection(plot.mouse_left, self._hide_hover)
        self._remember_connection(plot.left_drag_started, self._manual_plot_drag_started)
        self._remember_connection(plot.left_drag_finished, self._manual_plot_drag_finished)

        scene = plot.scene()
        click_slot = lambda ev, p=plot, cid=channel_id: self._plot_clicked(ev, p, cid)
        self._remember_connection(scene.sigMouseClicked, click_slot)

        proxy = pg.SignalProxy(
            scene.sigMouseMoved,
            rateLimit=60,
            slot=lambda args, p=plot, cid=channel_id: self._mouse_moved(args[0], p, cid),
        )
        self._mouse_proxies.append(proxy)
        return plot

    def _table_key_command(self, command: str) -> None:
        # J-Scope-style shortcuts work immediately after selecting a row; the
        # plot does not need an extra click to steal keyboard focus.
        self._apply_channel_key_command(command, self.channel_table.selected_channel_id())

    def _channel_visibility_changed(self, channel_id) -> None:
        """Show/Hide is presentation-only and never rebuilds/clears capture data."""
        cid = int(channel_id) if channel_id is not None else None
        if cid is None:
            return
        visible = cid in set(self.channel_table.visible_channel_ids())
        if self.view_combo.currentText() == "Overlay":
            curve = self._curves.get(cid)
            if curve is not None:
                curve.setVisible(visible)
        else:
            for plot in self._plots:
                if self._plot_channel_ids.get(id(plot)) == cid:
                    plot.setVisible(visible)
                    break
        self._update_overlay_selection_style()
        self._force_curve_redraw = True
        self._render_dirty = True
        self._refresh_hover_probe()

    def _channel_color_changed(self, channel_id) -> None:
        cid = int(channel_id) if channel_id is not None else None
        if cid is None:
            return
        color = QColor(self.channel_table.channel_color(cid))
        self._curve_colors[cid] = color
        self._update_overlay_selection_style()
        curve = self._curves.get(cid)
        if curve is not None and self.view_combo.currentText() != "Overlay":
            try:
                curve.setPen(pg.mkPen(color, width=1.2))
            except Exception:
                pass
        self._force_curve_redraw = True
        self._render_dirty = True

    def _apply_channel_key_command(self, command: str, channel_id: int | None) -> None:
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
            self.channel_table.set_gain_offset(
                channel_id, offset=offset + step if command == "offset_up" else offset - step
            )

    def _plot_key_command(self, command: str, plot: pg.PlotWidget) -> None:
        channel_id = self._plot_channel_ids.get(id(plot))
        if channel_id is None:
            channel_id = self.channel_table.selected_channel_id()
        self._apply_channel_key_command(command, channel_id)

    def _display_transform_changed(self, channel_id) -> None:
        # Gain/Offset changes the visible curve even when Follow is off and no
        # new raw sample falls inside the current historical window.
        self._force_curve_redraw = True
        self._render_dirty = True
        self._refresh_hover_probe()

    def _update_overlay_selection_style(self) -> None:
        """Draw the selected Overlay channel last / on top.

        Selection is an analysis operation, not a data transform.  The chosen
        channel gets a higher Z value and a slightly thicker pen while all raw
        values, Gain/Offset and exports remain unchanged.
        """
        if self.view_combo.currentText() != "Overlay":
            return
        selected = self.channel_table.selected_channel_id()
        for order, (cid, curve) in enumerate(self._curves.items()):
            color = self._curve_colors.get(cid, QColor(self.channel_table.channel_color(cid)))
            is_selected = selected is not None and int(cid) == int(selected)
            try:
                curve.setZValue(1000 if is_selected else order)
                curve.setPen(pg.mkPen(color, width=2.4 if is_selected else 1.1))
            except Exception:
                pass

    def _selected_channel_changed(self, channel_id) -> None:
        self._update_overlay_selection_style()
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
        if not self._data.has_data:
            self._hide_hover()
            return
        vb = plot.getPlotItem().vb
        try:
            if not vb.sceneBoundingRect().contains(scene_pos):
                return
            point = vb.mapSceneToView(scene_pos)
            x_value = float(point.x())
            local_plot = plot.mapFromScene(scene_pos)
            local_host = plot.mapTo(self.plot_host, local_plot)
        except Exception:
            return

        self._hover_plot = plot
        self._hover_scene_pos = scene_pos
        self._hover_x = x_value
        self._show_hover_at_host_pos(int(local_host.x()), int(local_host.y()), x_value)

    def _show_hover_at_host_pos(self, host_x: int, host_y: int, x_value: float) -> None:
        # Pixel-space line: it follows the mouse rather than a data X coordinate,
        # so live scrolling cannot leave old InfiniteLine paint artifacts behind.
        x_line = min(max(0, int(host_x)), max(0, self.plot_host.width() - 1))
        self.hover_vline.setGeometry(x_line, 0, 1, max(1, self.plot_host.height()))
        self.hover_vline.raise_()
        self.hover_vline.show()

        self._update_hover_tooltip(x_value)
        try:
            self.hover_label.adjustSize()
            x = min(max(4, x_line + 14), max(4, self.plot_host.width() - self.hover_label.width() - 4))
            y = min(max(4, int(host_y) + 14), max(4, self.plot_host.height() - self.hover_label.height() - 4))
            self.hover_label.move(x, y)
            self.hover_label.raise_()
            self.hover_label.show()
        except Exception:
            pass

    def _refresh_hover_probe(self) -> None:
        """Refresh the sample under a stationary mouse after the X window scrolls."""
        plot = self._hover_plot
        scene_pos = self._hover_scene_pos
        if plot is None or scene_pos is None or not self._data.has_data:
            return
        try:
            vb = plot.getPlotItem().vb
            if not vb.sceneBoundingRect().contains(scene_pos):
                self._hide_hover()
                return
            point = vb.mapSceneToView(scene_pos)
            x_value = float(point.x())
            local_plot = plot.mapFromScene(scene_pos)
            local_host = plot.mapTo(self.plot_host, local_plot)
        except Exception:
            self._hide_hover()
            return
        self._hover_x = x_value
        self._show_hover_at_host_pos(int(local_host.x()), int(local_host.y()), x_value)

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
        self._hover_plot = None
        self._hover_scene_pos = None
        if hasattr(self, "hover_vline"):
            self.hover_vline.hide()
        if hasattr(self, "hover_label"):
            self.hover_label.hide()

    def _clear_buffered_data(self, log_message: bool = True) -> None:
        self._data.clear()
        self._last_rendered_data_first_x = None
        self._last_rendered_data_last_x = None
        self._view_dirty = True
        self._force_curve_redraw = True
        self._curve_data_pending = False
        self._interaction_cache_active = False
        self._interaction_cache_range = None
        self.channel_table.update_statistics({})
        for curve in self._curves.values():
            curve.setData([], [])
        self._hover_x = None
        self._hide_hover()
        self._need_fit = True
        self.actual_label.setText("Actual: -")
        self._update_cursor_label()
        if log_message:
            self.log_requested.emit("Scope: buffered data and statistics cleared")

    def _update_axis_labels(self) -> None:
        label = "Time" if self._x_is_time else "Sample Index"
        units = "s" if self._x_is_time else ""
        for plot in self._plots:
            plot.setLabel("bottom", label, units=units)

    def _display_point_limit(self) -> int:
        # Render roughly two points per horizontal pixel.  This is enough to
        # preserve waveform shape while avoiding a fixed 10k points * channel *
        # FPS cost on small plot areas.  ScopeDataStore keeps the complete raw
        # buffer; this limit affects drawing only.
        if not self._plots:
            return 2000
        try:
            width = max(320, int(self._plots[0].viewport().width()))
        except Exception:
            width = 1000
        return max(800, min(12000, width * 2))

    def _current_visible_x_range(self) -> tuple[float, float] | None:
        """Return the X window currently visible to the user.

        Rendering only this window is a major performance rule. A 30 s raw
        buffer must not force every 0.5 s zoomed view to rebuild/decimate all
        30 s worth of samples on every frame.
        """
        if not self._plots:
            return None
        try:
            low, high = self._plots[0].getPlotItem().vb.viewRange()[0]
            low = float(low)
            high = float(high)
            if math.isfinite(low) and math.isfinite(high) and high > low:
                return low, high
        except Exception:
            pass
        return self._full_buffer_x_range()

    def _update_curves(self, skip_follow: bool = False) -> None:
        # Move/fit the viewport *before* selecting display points. Older builds
        # generated curve data for the old X window and then moved the ViewBox,
        # so the frame briefly displayed the wrong slice and looked as if the
        # waveform jumped or lost points.
        follow_moved = False
        if self._need_fit and self._data.has_data:
            self._fit_all(capture_follow_span=False)
            self._need_fit = False
            if self.follow_latest_check.isChecked():
                self._follow_x_span = float(self._data.seconds) if self._x_is_time else max(1.0, float(self._data.sample_count))
                follow_moved = self._follow_latest(force=True, smooth=False)
        elif (not skip_follow) and self._sampling and self.follow_latest_check.isChecked() and self._data.has_data:
            follow_moved = self._follow_latest(force=False, smooth=True)

        display_limit = self._display_point_limit()
        visible_x = self._current_visible_x_range()
        for cid, curve in self._curves.items():
            x, y = self._data.curve(cid, display_limit=display_limit, x_range=visible_x)
            gain, offset = self.channel_table.gain_offset(cid)
            if abs(gain - 1.0) <= 1e-15 and abs(offset) <= 1e-15:
                display_y = y
            else:
                display_y = y * gain + offset
            curve.setData(x, display_y)

        # Table statistics are useful but need not repaint at 60 FPS. The raw
        # statistics are updated for every acquired sample in ScopeDataStore; this
        # merely limits the expensive QTableWidget text refresh to 10 Hz.
        now = time.perf_counter()
        if now - self._last_stats_refresh_at >= 1.0 / self.STATS_REFRESH_MAX_HZ:
            self.channel_table.update_statistics(self._data.stats_snapshot())
            self._last_stats_refresh_at = now

        # A stationary mouse only needs a new time/value readout when the X
        # viewport itself moved. Ordinary curve redraws do not change the sample
        # underneath the cursor.
        if follow_moved:
            self._refresh_hover_probe()

    @staticmethod
    def _ranges_close(current, low: float, high: float) -> bool:
        try:
            c0, c1 = float(current[0]), float(current[1])
        except Exception:
            return False
        scale = max(1.0, abs(low), abs(high), abs(high - low))
        tol = scale * 1e-10
        return abs(c0 - low) <= tol and abs(c1 - high) <= tol

    def _set_shared_x_range(self, low: float, high: float, source_plot: pg.PlotWidget | None = None) -> None:
        """Apply one X range to the active plots without pyqtgraph XLink.

        In Overlay there is only one plot. In Stacked mode each ViewBox is
        independent; this routine performs a one-way guarded synchronization.
        Signals emitted by follower ViewBoxes return immediately because
        ``_syncing_x_range`` is set, so there is no reciprocal update chain.
        """
        if not self._plots or not (math.isfinite(low) and math.isfinite(high)) or high <= low:
            return
        targets = self._plots if self.view_combo.currentText() == "Stacked" else self._plots[:1]
        self._syncing_x_range = True
        batch_repaint = len(targets) > 1
        if batch_repaint:
            self.plot_host.setUpdatesEnabled(False)
        try:
            for plot in targets:
                if source_plot is not None and plot is source_plot:
                    continue
                try:
                    vb = plot.getPlotItem().vb
                    current = vb.viewRange()[0]
                    if self._ranges_close(current, low, high):
                        continue
                    plot.setXRange(low, high, padding=0)
                except Exception:
                    continue
        finally:
            if batch_repaint:
                self.plot_host.setUpdatesEnabled(True)
                self.plot_host.update()
            self._syncing_x_range = False

    def _interaction_display_point_limit(self) -> int:
        """Small but visually stable full-buffer cache used only while panning."""
        if not self._plots:
            return 1800
        try:
            width = max(320, int(self._plots[0].viewport().width()))
        except Exception:
            width = 1000
        # Roughly 1.5 points/pixel for the *whole retained buffer*.  This keeps
        # ViewBox transforms light even for 60/120 s captures and several lanes.
        return max(700, min(5000, int(width * 1.5)))

    def _prepare_interaction_cache(self) -> None:
        """Materialize a lightweight full-buffer snapshot before mouse pan.

        The cache deliberately covers the complete retained history so the user
        can drag anywhere inside the current Buffer without forcing a new
        ScopeDataStore.curve()/downsample()/setData() cycle mid-gesture.  Exact
        viewport detail is restored once the button is released.
        """
        if not self._data.has_data or not self._curves:
            self._interaction_cache_active = False
            self._interaction_cache_range = None
            return
        x_range = self._full_buffer_x_range()
        if x_range is None:
            return
        limit = self._interaction_display_point_limit()
        # One batched repaint for all channels rather than one repaint per curve.
        self.plot_host.setUpdatesEnabled(False)
        try:
            for cid, curve in self._curves.items():
                x, y = self._data.curve(cid, display_limit=limit, x_range=x_range)
                gain, offset = self.channel_table.gain_offset(cid)
                if abs(gain - 1.0) <= 1e-15 and abs(offset) <= 1e-15:
                    display_y = y
                else:
                    display_y = y * gain + offset
                curve.setData(x, display_y)
        finally:
            self.plot_host.setUpdatesEnabled(True)
            self.plot_host.update()
        self._interaction_cache_active = True
        self._interaction_cache_range = x_range
        self._curve_data_pending = False
        self._force_curve_redraw = False
        self._view_dirty = False
        self._last_curve_refresh_at = time.perf_counter()

    def _manual_plot_drag_started(self) -> None:
        # Disable Follow first, then freeze a lightweight full-history snapshot.
        # After this one preparation step the drag path does no curve setData(),
        # no table updates and no hover lookup; pyqtgraph only moves ViewBoxes.
        if self.follow_latest_check.isChecked():
            self.follow_latest_check.setChecked(False)
            self.log_requested.emit("Scope: live follow disabled by left-button drag")
        self._hide_hover()
        self._prepare_interaction_cache()
        self._user_dragging = True

    def _manual_plot_drag_finished(self) -> None:
        self._user_dragging = False
        self._flush_pending_manual_x_sync(force=True)
        self._interaction_cache_active = False
        self._interaction_cache_range = None
        # Restore exact high-detail samples only once, for the final viewport.
        self._view_dirty = True
        self._force_curve_redraw = True
        self._render_dirty = True
        self._curve_data_pending = True

    def _x_range_changed(self, plot: pg.PlotWidget, x_range) -> None:
        """Remember manual X zoom and synchronize Stacked plots once.

        Programmatic follow/fit ranges and follower updates are ignored via the
        two guards. A genuine user pan/zoom becomes authoritative and is copied
        to the other Stacked plots without any ViewBox XLink relationship.
        """
        if self._applying_follow_range or self._syncing_x_range or self._rebuilding_plots:
            return
        try:
            low, high = float(x_range[0]), float(x_range[1])
        except Exception:
            return
        span = high - low
        if not (math.isfinite(span) and span > 1e-12):
            return
        self._follow_x_span = span
        self._last_follow_span = None
        # During a drag the interaction cache already contains the retained
        # history.  Do not mark the curves dirty on every mouse pixel; doing so
        # would immediately defeat the cache and recreate the old stutter.
        if not self._user_dragging:
            self._view_dirty = True
            self._render_dirty = True
        if self.view_combo.currentText() == "Stacked":
            if self._user_dragging:
                # Do not synchronously fan every mouse-move range event into all
                # follower ViewBoxes. The render clock copies at most ~30 Hz and
                # release forces the final exact range, which feels much lighter.
                self._pending_shared_x_range = (low, high, plot)
                self._flush_pending_manual_x_sync(force=False)
            else:
                self._set_shared_x_range(low, high, source_plot=plot)

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
        if self._data.sample_count >= 2 and self._data.first_x is not None and self._data.last_x is not None:
            span = float(self._data.last_x) - float(self._data.first_x)
            if math.isfinite(span) and span > 1e-12:
                return span
        return float(self._data.seconds) if self._x_is_time else 1.0

    def _follow_latest_toggled(self, checked: bool) -> None:
        # Single source of truth for live scrolling. Enabling it captures the
        # current user-visible X width; it does not fit/reset X or Y.
        self._last_follow_right = None
        self._last_follow_span = None
        self._last_follow_scroll_at = 0.0
        if checked:
            self._follow_x_span = self._current_x_span()
            if self._data.has_data:
                self._follow_latest(force=True)

    def _follow_scroll_hz(self) -> float:
        """Return an adaptive X-scroll rate independent of acquisition Hz.

        Overlay has one ViewBox, so it can follow up to the selected GUI FPS.
        Stacked must update every visible ViewBox; keep the total range-write
        budget bounded so adding channels does not multiply GUI work without
        limit. Example: 60 FPS + 3 Stacked channels -> min(60, 90/3)=30 Hz.
        """
        fps = float(self._fps_value())
        if self.view_combo.currentText() != "Stacked":
            return max(1.0, min(60.0, fps))
        plot_count = max(1, len(self._plots))
        budget_rate = self.FOLLOW_STACKED_VIEWBOX_BUDGET_HZ / float(plot_count)
        return max(1.0, min(fps, budget_rate))

    def _follow_latest(self, force: bool = False, smooth: bool = True) -> bool:
        """Scroll the X viewport toward the newest sample.

        Follow scrolling is intentionally slower than curve FPS. Updating three
        or more independent Stacked ViewBoxes at the full GUI FPS can be much
        more expensive than drawing the curves themselves on Windows/Qt. The
        scroll rate is therefore adaptive: Overlay follows up to GUI FPS, while
        Stacked shares a bounded ViewBox-update budget across visible channels.
        This keeps motion substantially smoother than V0.3.11's fixed 12 Hz
        without returning to the old unbounded range-update load.
        """
        if not self._plots or not self._data.has_data or self._data.last_x is None:
            return False

        now = time.perf_counter()
        if not force and self._last_follow_scroll_at > 0.0:
            follow_hz = self._follow_scroll_hz()
            if now - self._last_follow_scroll_at < 1.0 / follow_hz:
                return False

        last_x = float(self._data.last_x)
        # Interpolate the visual right edge between bursty worker deliveries.
        # The actual curve still ends at the newest real sample; only the ViewBox
        # translation is predicted a few milliseconds ahead, capped tightly so
        # the display never runs noticeably in front of acquisition.
        visual_right = last_x
        if smooth and self._x_is_time and self._sampling and self._latest_data_arrival_at > 0.0:
            elapsed = max(0.0, now - self._latest_data_arrival_at)
            hz = self._latest_actual_hz if self._latest_actual_hz > 1.0 else float(self.sample_hz_spin.value())
            one_sample = 1.0 / max(1.0, hz)
            lead_cap = max(2.0 * one_sample, min(0.040, 2.0 / max(1.0, float(self._fps_value()))))
            visual_right = last_x + min(elapsed, lead_cap)

        span = self._current_x_span()
        if span is None or not math.isfinite(span) or span <= 1e-12:
            span = float(self._data.seconds) if self._x_is_time else 1.0

        # Also skip sub-pixel movements. The time throttle above prevents event
        # storms; this pixel threshold avoids range writes that cannot alter a
        # single visible screen column.
        try:
            width_px = max(1, int(self._plots[0].viewport().width()))
        except Exception:
            width_px = 1000
        min_visible_delta = max(span / width_px * 0.75, 1e-12)
        span_changed = self._last_follow_span is None or abs(span - self._last_follow_span) > max(1e-12, span * 1e-6)
        if (
            not force
            and not span_changed
            and self._last_follow_right is not None
            and abs(visual_right - self._last_follow_right) < min_visible_delta
        ):
            return False

        left = visual_right - span
        right = visual_right
        if right <= left:
            right = left + (1e-6 if self._x_is_time else 1.0)

        self._applying_follow_range = True
        try:
            self._set_shared_x_range(left, right)
            self._last_follow_right = right
            self._last_follow_span = span
            self._last_follow_scroll_at = now
        finally:
            self._applying_follow_range = False
        return True

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
        if not self._data.has_data or self._data.first_x is None or self._data.last_x is None:
            return None
        left = float(self._data.first_x)
        right = float(self._data.last_x)
        if not (math.isfinite(left) and math.isfinite(right)):
            return None
        if right <= left:
            half = 0.5e-3 if self._x_is_time else 0.5
            return left - half, right + half
        return left, right

    def _channel_display_extrema(self, channel_id: int) -> tuple[float, float] | None:
        extrema = self._data.buffer_extrema(int(channel_id))
        if extrema is None:
            return None
        raw_min, raw_max = extrema
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
            # Keep every Stacked ViewBox independent. Fit the shared X range via
            # our guarded synchronizer rather than pyqtgraph XLink.
            for plot in self._plots:
                vb = plot.getPlotItem().vb
                if hasattr(vb, "disableAutoRange"):
                    vb.disableAutoRange()
            self._set_shared_x_range(x_left, x_right)

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
        # A one-shot fit is now authoritative; the next live-follow frame starts
        # from this exact aligned state rather than an older cached right edge.
        self._last_follow_right = x_right
        self._last_follow_span = x_right - x_left

    def _align_full_buffer(self) -> None:
        # Fit the ViewBox first, then rebuild display samples for that new X
        # range. Doing it in the opposite order produced the characteristic
        # "axis is 0..6 s but waveform only exists in 0..1 s" bug after a View
        # switch/rebuild.
        self._fit_all(capture_follow_span=True)
        self._view_dirty = True
        self._force_curve_redraw = True
        self._render_dirty = True
        self._render_if_dirty()
        self._refresh_hover_probe()

    def view_all(self) -> None:
        self._align_full_buffer()

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
