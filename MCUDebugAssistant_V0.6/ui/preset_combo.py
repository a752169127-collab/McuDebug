from __future__ import annotations

import re
from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox


class IntPresetComboBox(QComboBox):
    """Editable engineering preset selector with a QSpinBox-like integer API.

    The drop-down exposes only common engineering values while the editable line
    still accepts any integer inside ``minimum..maximum``.  Keeping ``value()`` /
    ``setValue()`` / ``valueChanged`` lets existing Watch/Scope/Memory code switch
    away from +/- spin boxes without changing acquisition semantics.
    """

    valueChanged = Signal(int)

    _NUMBER_RE = re.compile(r"[-+]?\d+")

    def __init__(
        self,
        presets: Iterable[int],
        *,
        value: int,
        minimum: int,
        maximum: int,
        suffix: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._minimum = int(minimum)
        self._maximum = max(self._minimum, int(maximum))
        self._suffix = str(suffix)
        self._last_value = self._clamp(int(value))

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        seen: set[int] = set()
        for raw in presets:
            item = self._clamp(int(raw))
            if item in seen:
                continue
            seen.add(item)
            self.addItem(self._format(item), item)

        self.activated.connect(lambda *_: self._commit_editor_value())
        if self.lineEdit() is not None:
            self.lineEdit().editingFinished.connect(self._commit_editor_value)

        # Initialize without emitting a synthetic valueChanged during construction.
        self._set_display_value(self._last_value)

    def minimum(self) -> int:
        return self._minimum

    def maximum(self) -> int:
        return self._maximum

    def value(self) -> int:
        parsed = self._parse(self.currentText())
        if parsed is None:
            return int(self._last_value)
        return self._clamp(parsed)

    def setValue(self, value: int) -> None:
        normalized = self._clamp(int(value))
        changed = normalized != self._last_value
        self._last_value = normalized
        self._set_display_value(normalized)
        if changed:
            self.valueChanged.emit(normalized)

    def _clamp(self, value: int) -> int:
        return max(self._minimum, min(self._maximum, int(value)))

    def _format(self, value: int) -> str:
        suffix = self._suffix.strip()
        return f"{int(value)} {suffix}" if suffix else str(int(value))

    def _parse(self, text: str) -> int | None:
        match = self._NUMBER_RE.search(str(text))
        if match is None:
            return None
        try:
            return int(match.group(0))
        except Exception:
            return None

    def _set_display_value(self, value: int) -> None:
        target_data = int(value)
        index = self.findData(target_data)
        self.blockSignals(True)
        try:
            if index >= 0:
                self.setCurrentIndex(index)
            else:
                self.setEditText(self._format(target_data))
        finally:
            self.blockSignals(False)

    def _commit_editor_value(self) -> None:
        parsed = self._parse(self.currentText())
        normalized = self._last_value if parsed is None else self._clamp(parsed)
        changed = normalized != self._last_value
        self._last_value = normalized
        self._set_display_value(normalized)
        if changed:
            self.valueChanged.emit(normalized)
