from __future__ import annotations

import json
from dataclasses import dataclass, field

from PySide6.QtCore import QPersistentModelIndex, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLineEdit,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
)

from core.datatype import supported_types
from core.watch import RunningStats, WatchVariableSpec


class SetValueDelegate(QStyledItemDelegate):
    """Commit Set Value on Enter *or* when a modified editor loses focus.

    A QTable delegate normally commits the model on focus-out, but the old product
    behavior only emitted the target write from ``returnPressed``. That meant a
    user could type a Set Value, click another cell, see the edit committed in the
    table, yet never write it to the MCU. Track actual user edits and use the same
    write path for Enter and focus-out.
    """

    commit_requested = Signal(int)

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            persistent_index = QPersistentModelIndex(index)
            editor.setProperty("watch_set_value_dirty", False)

            def mark_dirty(_text: str) -> None:
                editor.setProperty("watch_set_value_dirty", True)

            def commit_if_dirty() -> None:
                if not bool(editor.property("watch_set_value_dirty")):
                    return
                # Clear first so Return -> editingFinished cannot queue the same
                # write twice. commitData updates the QTableWidgetItem before the
                # deferred write request reads its text.
                editor.setProperty("watch_set_value_dirty", False)
                self.commitData.emit(editor)
                row = persistent_index.row()
                if row >= 0:
                    QTimer.singleShot(0, lambda r=row: self.commit_requested.emit(r))

            editor.textEdited.connect(mark_dirty)
            editor.returnPressed.connect(commit_if_dirty)
            editor.editingFinished.connect(commit_if_dirty)
        return editor


@dataclass
class WatchRowState:
    row_id: int
    stats: RunningStats = field(default_factory=RunningStats)
    current_value: float | int | None = None


class WatchTable(QTableWidget):
    definition_changed = Signal()
    write_requested = Signal(int)  # row_id

    COL_ENABLE = 0
    COL_NAME = 1
    COL_ADDRESS = 2
    COL_TYPE = 3
    COL_CURRENT = 4
    COL_SET = 5
    COL_AVG = 6
    COL_MIN = 7
    COL_MAX = 8

    HEADERS = [
        "Enable",
        "Name",
        "Address",
        "Type",
        "Current",
        "Set Value",
        "Average",
        "Min",
        "Max",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

        header = self.horizontalHeader()
        # Do NOT use ResizeToContents for live data columns. With Current/Avg/Min/Max
        # changing many times per second, Qt would repeatedly measure text and relayout
        # the whole header. Interactive/fixed widths keep Watch repaint cost predictable.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_SET, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(self.COL_ENABLE, 64)
        self.setColumnWidth(self.COL_ADDRESS, 116)
        self.setColumnWidth(self.COL_TYPE, 100)
        self.setColumnWidth(self.COL_CURRENT, 120)
        self.setColumnWidth(self.COL_AVG, 120)
        self.setColumnWidth(self.COL_MIN, 120)
        self.setColumnWidth(self.COL_MAX, 120)
        self.setWordWrap(False)
        self.verticalHeader().setDefaultSectionSize(24)

        self._next_row_id = 1
        self._states: dict[int, WatchRowState] = {}

        self._set_value_delegate = SetValueDelegate(self)
        self._set_value_delegate.commit_requested.connect(self._on_set_value_commit)
        self.setItemDelegateForColumn(self.COL_SET, self._set_value_delegate)

        self.itemChanged.connect(self._on_item_changed)

    def add_variable(
        self,
        name: str = "Value1",
        address: str = "0x20000000",
        type_name: str = "float",
        enabled: bool = True,
    ) -> int:
        row = self.rowCount()
        self.insertRow(row)
        row_id = self._next_row_id
        self._next_row_id += 1
        self._states[row_id] = WatchRowState(row_id=row_id)

        enable_item = QTableWidgetItem()
        enable_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        enable_item.setCheckState(
            Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        )
        enable_item.setData(Qt.ItemDataRole.UserRole, row_id)
        self.setItem(row, self.COL_ENABLE, enable_item)

        self.setItem(row, self.COL_NAME, QTableWidgetItem(name))
        self.setItem(row, self.COL_ADDRESS, QTableWidgetItem(address))

        combo = QComboBox(self)
        combo.addItems(supported_types())
        combo.setCurrentText(type_name if type_name in supported_types() else "float")
        combo.currentTextChanged.connect(lambda _text: self.definition_changed.emit())
        self.setCellWidget(row, self.COL_TYPE, combo)

        for col in (self.COL_CURRENT, self.COL_AVG, self.COL_MIN, self.COL_MAX):
            item = QTableWidgetItem("-")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row, col, item)

        self.setItem(row, self.COL_SET, QTableWidgetItem(""))
        return row_id

    def remove_selected(self) -> int:
        """Remove all selected Watch rows and return the number removed.

        Extended row selection means Shift/Ctrl can select multiple variables.
        Rows are removed from bottom to top so table indexes remain valid.
        """
        rows = sorted(
            {index.row() for index in self.selectionModel().selectedRows()},
            reverse=True,
        )
        if not rows and self.currentRow() >= 0:
            rows = [self.currentRow()]
        if not rows:
            return 0

        for row in rows:
            row_id = self.row_id_at(row)
            self.removeRow(row)
            if row_id is not None:
                self._states.pop(row_id, None)

        self.definition_changed.emit()
        return len(rows)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Delete:
            self.remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def row_id_at(self, row: int) -> int | None:
        item = self.item(row, self.COL_ENABLE)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def selected_row_id(self) -> int | None:
        return self.row_id_at(self.currentRow()) if self.currentRow() >= 0 else None

    def contains_variable(self, name: str, address: int) -> bool:
        target_name = name.strip()
        target_address = int(address)
        for row in range(self.rowCount()):
            name_item = self.item(row, self.COL_NAME)
            addr_item = self.item(row, self.COL_ADDRESS)
            if name_item is None or addr_item is None:
                continue
            if name_item.text().strip() != target_name:
                continue
            try:
                existing_address = int(addr_item.text().strip(), 0)
            except ValueError:
                continue
            if existing_address == target_address:
                return True
        return False

    def rebind_symbols(self, symbols) -> dict[str, int]:
        """Rebind Watch rows to a newly parsed AXF/ELF symbol set by exact name.

        A unique symbol name is rebound directly. If the AXF contains duplicate
        names (usually file-local/static objects), the old address is accepted
        only when it still identifies exactly one candidate. Otherwise the row
        is removed rather than silently binding it to the wrong object.
        """
        by_name: dict[str, list] = {}
        for sym in symbols:
            if not getattr(sym, "addable", False):
                continue
            by_name.setdefault(str(sym.name), []).append(sym)

        summary = {
            "updated": 0,
            "unchanged": 0,
            "type_updated": 0,
            "removed_missing": 0,
            "removed_ambiguous": 0,
        }
        rows_to_remove: list[tuple[int, str, str]] = []

        blocked = self.blockSignals(True)
        try:
            for row in range(self.rowCount()):
                row_id = self.row_id_at(row)
                name_item = self.item(row, self.COL_NAME)
                addr_item = self.item(row, self.COL_ADDRESS)
                combo = self.cellWidget(row, self.COL_TYPE)
                if row_id is None or name_item is None or addr_item is None or not isinstance(combo, QComboBox):
                    continue

                name = name_item.text().strip()
                candidates = by_name.get(name, [])
                if not candidates:
                    rows_to_remove.append((row, name, "missing"))
                    continue

                old_address = None
                try:
                    old_address = int(addr_item.text().strip(), 0)
                except ValueError:
                    pass

                if len(candidates) == 1:
                    sym = candidates[0]
                else:
                    same_address = [s for s in candidates if old_address is not None and int(s.address) == old_address]
                    if len(same_address) == 1:
                        sym = same_address[0]
                    else:
                        rows_to_remove.append((row, name, "ambiguous"))
                        continue

                new_address = int(sym.address)
                old_type = combo.currentText()
                new_type = sym.type_name if sym.type_name in supported_types() else old_type
                address_changed = old_address != new_address
                type_changed = new_type != old_type

                addr_item.setText(f"0x{new_address:08X}")
                if type_changed:
                    combo.setCurrentText(new_type)
                    summary["type_updated"] += 1

                # A reload represents a new symbol binding / firmware image.
                # Do not mix old samples with the newly bound object.
                state = self._states.setdefault(row_id, WatchRowState(row_id=row_id))
                state.current_value = None
                state.stats.clear()
                for col in (self.COL_CURRENT, self.COL_AVG, self.COL_MIN, self.COL_MAX):
                    item = self.item(row, col)
                    if item is not None:
                        item.setText("-")

                if address_changed or type_changed:
                    summary["updated"] += 1
                else:
                    summary["unchanged"] += 1

            for row, _name, reason in sorted(rows_to_remove, key=lambda x: x[0], reverse=True):
                row_id = self.row_id_at(row)
                self.removeRow(row)
                if row_id is not None:
                    self._states.pop(row_id, None)
                if reason == "missing":
                    summary["removed_missing"] += 1
                else:
                    summary["removed_ambiguous"] += 1
        finally:
            self.blockSignals(blocked)

        self.definition_changed.emit()
        return summary

    def specs(self) -> list[WatchVariableSpec]:
        result: list[WatchVariableSpec] = []
        for row in range(self.rowCount()):
            row_id = self.row_id_at(row)
            if row_id is None:
                continue
            name_item = self.item(row, self.COL_NAME)
            addr_item = self.item(row, self.COL_ADDRESS)
            combo = self.cellWidget(row, self.COL_TYPE)
            if name_item is None or addr_item is None or not isinstance(combo, QComboBox):
                continue
            name = name_item.text().strip() or f"Value{row + 1}"
            address_text = addr_item.text().strip()
            if not address_text:
                raise ValueError(f"Watch '{name}' address is empty")
            try:
                address = int(address_text, 0)
            except ValueError as exc:
                raise ValueError(f"Watch '{name}' has invalid address: {address_text}") from exc
            if not 0 <= address <= 0xFFFFFFFF:
                raise ValueError(f"Watch '{name}' address is outside 32-bit range")
            enabled = self.item(row, self.COL_ENABLE).checkState() == Qt.CheckState.Checked
            result.append(
                WatchVariableSpec(
                    row_id=row_id,
                    name=name,
                    address=address,
                    type_name=combo.currentText(),
                    enabled=enabled,
                )
            )
        return result

    def set_sample(self, row_id: int, value: float | int, formatted: str) -> None:
        row = self._row_for_id(row_id)
        if row < 0:
            return
        state = self._states.setdefault(row_id, WatchRowState(row_id=row_id))
        state.current_value = value
        state.stats.add(value)
        blocked = self.blockSignals(True)
        try:
            self.item(row, self.COL_CURRENT).setText(formatted)
            _, avg, minimum, maximum = state.stats.snapshot()
            self.item(row, self.COL_AVG).setText(self._format_stat(avg))
            self.item(row, self.COL_MIN).setText(self._format_stat(minimum))
            self.item(row, self.COL_MAX).setText(self._format_stat(maximum))
        finally:
            self.blockSignals(blocked)

    def apply_snapshot(self, samples) -> None:
        """Apply one throttled worker snapshot in a single GUI update batch.

        The J-Link worker has already accumulated every sample into Mean/Min/Max.
        This method only paints the newest display state, so intermediate acquisition
        frames never flood the Qt event queue.
        """
        if not samples:
            return

        # Build the row lookup once. The old per-value path scanned the whole table
        # for each row_id, which becomes O(N^2) as the Watch list grows.
        row_by_id = {
            row_id: row
            for row in range(self.rowCount())
            if (row_id := self.row_id_at(row)) is not None
        }

        blocked = self.blockSignals(True)
        updates_were_enabled = self.updatesEnabled()
        if updates_were_enabled:
            self.setUpdatesEnabled(False)
        try:
            for sample in samples:
                row_id = int(sample["row_id"])
                row = row_by_id.get(row_id, -1)
                if row < 0:
                    continue

                value = sample.get("value")
                state = self._states.setdefault(row_id, WatchRowState(row_id=row_id))
                state.current_value = value

                count = int(sample.get("count") or 0)
                avg = sample.get("average")
                minimum = sample.get("minimum")
                maximum = sample.get("maximum")
                if count <= 0 or avg is None:
                    state.stats.clear()
                else:
                    # Mirror the worker's authoritative statistics locally so the
                    # existing Copy Average action remains O(1) and needs no round trip.
                    state.stats.count = count
                    state.stats.mean = float(avg)
                    state.stats.minimum = float(minimum) if minimum is not None else float(avg)
                    state.stats.maximum = float(maximum) if maximum is not None else float(avg)

                self._set_item_text_if_changed(
                    row, self.COL_CURRENT, str(sample.get("formatted", "-"))
                )
                self._set_item_text_if_changed(row, self.COL_AVG, self._format_stat(avg))
                self._set_item_text_if_changed(row, self.COL_MIN, self._format_stat(minimum))
                self._set_item_text_if_changed(row, self.COL_MAX, self._format_stat(maximum))
        finally:
            if updates_were_enabled:
                self.setUpdatesEnabled(True)
            self.blockSignals(blocked)

    def _set_item_text_if_changed(self, row: int, col: int, text: str) -> None:
        item = self.item(row, col)
        if item is not None and item.text() != text:
            item.setText(text)

    def set_current_only(self, row_id: int, value: float | int, formatted: str) -> None:
        row = self._row_for_id(row_id)
        if row < 0:
            return
        state = self._states.setdefault(row_id, WatchRowState(row_id=row_id))
        state.current_value = value
        blocked = self.blockSignals(True)
        try:
            self.item(row, self.COL_CURRENT).setText(formatted)
        finally:
            self.blockSignals(blocked)

    def clear_statistics(self) -> None:
        for state in self._states.values():
            state.stats.clear()
        blocked = self.blockSignals(True)
        try:
            for row in range(self.rowCount()):
                for col in (self.COL_AVG, self.COL_MIN, self.COL_MAX):
                    item = self.item(row, col)
                    if item is not None:
                        item.setText("-")
        finally:
            self.blockSignals(blocked)

    def write_request(self, row_id: int) -> tuple[WatchVariableSpec, str]:
        specs = {v.row_id: v for v in self.specs()}
        if row_id not in specs:
            raise ValueError("Watch row is invalid")
        row = self._row_for_id(row_id)
        if row < 0:
            raise ValueError("Watch row no longer exists")
        value_item = self.item(row, self.COL_SET)
        value_text = value_item.text().strip() if value_item else ""
        if not value_text:
            raise ValueError("Set Value is empty")
        return specs[row_id], value_text

    def current_write_request(self) -> tuple[WatchVariableSpec, str]:
        row_id = self.selected_row_id()
        if row_id is None:
            raise ValueError("Select a Watch row first")
        return self.write_request(row_id)

    def average_snapshot(self) -> list[tuple[str, float | None]]:
        rows: list[tuple[str, float | None]] = []
        for row in range(self.rowCount()):
            row_id = self.row_id_at(row)
            if row_id is None:
                continue
            name_item = self.item(row, self.COL_NAME)
            name = name_item.text().strip() if name_item else f"Value{row+1}"
            state = self._states.get(row_id)
            avg = state.stats.snapshot()[1] if state is not None else None
            rows.append((name, avg))
        return rows

    def to_json(self) -> str:
        data = []
        for row in range(self.rowCount()):
            row_id = self.row_id_at(row)
            combo = self.cellWidget(row, self.COL_TYPE)
            data.append(
                {
                    "name": self.item(row, self.COL_NAME).text() if self.item(row, self.COL_NAME) else "",
                    "address": self.item(row, self.COL_ADDRESS).text() if self.item(row, self.COL_ADDRESS) else "",
                    "type": combo.currentText() if isinstance(combo, QComboBox) else "float",
                    "enabled": self.item(row, self.COL_ENABLE).checkState() == Qt.CheckState.Checked,
                }
            )
        return json.dumps(data, ensure_ascii=False)

    def load_json(self, text: str) -> None:
        self.setRowCount(0)
        self._states.clear()
        self._next_row_id = 1
        if not text.strip():
            return
        data = json.loads(text)
        if not isinstance(data, list):
            return
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            self.add_variable(
                name=str(item.get("name") or f"Value{i+1}"),
                address=str(item.get("address") or "0x20000000"),
                type_name=str(item.get("type") or "float"),
                enabled=bool(item.get("enabled", True)),
            )

    def set_definition_editable(self, editable: bool) -> None:
        for row in range(self.rowCount()):
            for col in (self.COL_NAME, self.COL_ADDRESS):
                item = self.item(row, col)
                if item is None:
                    continue
                flags = item.flags()
                if editable:
                    item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)
            # Set Value deliberately remains editable while sampling so control
            # parameters can be adjusted without stopping Watch acquisition.
            combo = self.cellWidget(row, self.COL_TYPE)
            if isinstance(combo, QComboBox):
                combo.setEnabled(editable)

    def _on_set_value_commit(self, row: int) -> None:
        row_id = self.row_id_at(row)
        if row_id is not None:
            self.write_requested.emit(row_id)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() in (self.COL_ENABLE, self.COL_NAME, self.COL_ADDRESS):
            self.definition_changed.emit()

    def _row_for_id(self, row_id: int) -> int:
        for row in range(self.rowCount()):
            if self.row_id_at(row) == row_id:
                return row
        return -1

    @staticmethod
    def _format_stat(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:.9g}"
