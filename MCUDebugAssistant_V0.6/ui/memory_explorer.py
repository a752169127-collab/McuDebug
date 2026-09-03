from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QItemSelectionModel, QModelIndex, QRect, QTimer, Qt, Signal
from PySide6.QtGui import (
    QActionGroup,
    QFontDatabase,
    QKeySequence,
    QPainter,
    QPalette,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from core.datatype import decode_value, encode_value, format_value, get_type_info, supported_types
from ui.preset_combo import IntPresetComboBox
from core.memory_browser import (
    ADDRESS_SPACE_SIZE,
    BYTES_PER_ROW,
    DEFAULT_RAM_BASE,
    DISPLAY_TYPES,
    SEPARATOR_BYTES,
    TEXT_ENCODINGS,
    SymbolIndex,
    decode_text,
    display_unit_size,
    display_value_chars,
    encode_text_input,
    format_display_value,
    format_hex_block,
    parse_address,
    plan_read_window,
    plan_symbol_read_window,
    text_edit_unit_size,
    update_navigation_history,
    symbol_display_type,
)


_DISPLAY_LABELS = {
    "byte": "Byte (Hex)",
    "int8": "Int8",
    "uint8": "UInt8",
    "int16": "Int16",
    "uint16": "UInt16",
    "int32": "Int32",
    "uint32": "UInt32",
    "int64": "Int64",
    "uint64": "UInt64",
    "float": "Float",
    "double": "Double",
}


class NavigationHistoryComboBox(QComboBox):
    """Editable address field whose activation is scoped to its own history popup.

    QComboBox can emit ``activated(int)`` from Enter even while a separate
    QCompleter attached to its line edit is accepting a Symbol candidate. That
    made a stale MRU row run *after* the correct Symbol completion and replace
    it (for example with an old ``__lit__...`` entry). Only forward activation
    when the combo's own history popup was actually opened by the user.
    """

    history_activated = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._history_popup_session = False
        self.activated.connect(self._forward_history_activation)

    def showPopup(self) -> None:  # noqa: N802
        self._history_popup_session = True
        super().showPopup()

    def hidePopup(self) -> None:  # noqa: N802
        super().hidePopup()
        # QComboBox may emit activated() while closing the popup. Clear on the
        # next event-loop turn so a genuine history selection still forwards,
        # while a cancelled popup cannot poison the next Symbol Enter.
        QTimer.singleShot(0, self._clear_history_popup_session)

    def _clear_history_popup_session(self) -> None:
        self._history_popup_session = False

    def _forward_history_activation(self, index: int) -> None:
        if not self._history_popup_session:
            return
        self._history_popup_session = False
        self.history_activated.emit(int(index))


class HexMemoryView(QAbstractScrollArea):
    """Virtual 32-bit MCU memory viewer with CE-style direct editing.

    Reads remain visible-window based and all target access is delegated to the
    J-Link owner worker. Editing emits write requests only; the MainWindow/worker
    remains the single owner of actual WriteMemEx calls.
    """

    read_requested = Signal(object, int)  # address, size
    write_requested = Signal(object, object)  # address, bytes
    edit_requested = Signal(object, str, object)  # address, type_name, current raw bytes
    text_edit_requested = Signal(object, str, object)  # address, encoding, current raw bytes
    add_watch_requested = Signal(str, object, str)  # name, address, type_name
    add_scope_requested = Signal(str, object, str)  # name, address, type_name
    selection_changed = Signal(str)

    TOTAL_ROWS = ADDRESS_SPACE_SIZE // BYTES_PER_ROW

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        self._font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.viewport().setFont(self._font)
        self._display_type = "byte"
        self._encoding = "ASCII"
        self._separator_bytes = 4
        self._show_symbols = True
        self._show_symbol_offsets = True
        self._show_changes = True
        # Symbol column auto-fits to the longest visible Symbol by default so
        # users can read full member paths without manually dragging the divider.
        # A manual drag temporarily switches to fixed width; double-clicking the
        # divider returns to auto-fit. This is presentation-only and never causes
        # symbol reparse or target I/O.
        self._symbol_width_px: int | None = None
        self._symbol_auto_fit = True
        self._auto_symbol_width_cache_key = None
        self._auto_symbol_width_cache_value: int | None = None
        self._resizing_symbol_column = False
        self._symbol_index = SymbolIndex()
        self._connected = False

        # Selection is byte-range aware so mouse drag/Shift-click can copy a
        # contiguous memory block instead of only one displayed cell.
        self._selected_address: int | None = None
        self._selection_area = "value"  # value | text | row
        self._selection_anchor_address: int | None = None
        self._selection_anchor_size = 1
        self._selection_focus_address: int | None = None
        self._selection_focus_size = 1
        self._drag_selecting = False

        self._block_start = 0
        self._block_data = b""
        self._changed_addresses: set[int] = set()

        # CE-like byte editing: first hex nibble is shown immediately in the
        # selected cell, the second nibble emits a one-byte write and advances.
        self._hex_nibble = ""
        self._hex_nibble_address: int | None = None

        # Non-byte typed views use a lightweight in-cell QLineEdit. The editor
        # exists once and is repositioned; no table widgets are created per byte.
        self._inline_editor = QLineEdit(self.viewport())
        self._inline_editor.setFont(self._font)
        self._inline_editor.hide()
        self._inline_editor.installEventFilter(self)
        self._inline_editor.returnPressed.connect(self._commit_inline_editor)
        self._inline_edit_address: int | None = None
        self._inline_edit_type: str | None = None
        self._inline_committing = False

        self._read_timer = QTimer(self)
        self._read_timer.setSingleShot(True)
        self._read_timer.setInterval(35)
        self._read_timer.timeout.connect(self._request_visible_now)
        self._force_next_read = False

        self.verticalScrollBar().valueChanged.connect(self._on_vertical_scroll)
        self.horizontalScrollBar().valueChanged.connect(self._on_horizontal_scroll)

        self._goto_shortcut = QShortcut(QKeySequence("Ctrl+G"), self)
        self._goto_shortcut.activated.connect(self._prompt_goto)
        self._refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self._refresh_shortcut.activated.connect(lambda: self.refresh(force=True))
        self._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self._copy_shortcut.activated.connect(self._copy_selected)
        self._paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        self._paste_shortcut.activated.connect(self._paste_selected)

        self._update_scrollbars()
        # Always start the virtual view at the Cortex-M SRAM base. This happens
        # before connection, so the first connected read is immediately useful.
        self.goto_address(DEFAULT_RAM_BASE)

    # ---------- public state ----------
    def set_connected(self, connected: bool, *, refresh: bool = True) -> None:
        self._connected = bool(connected)
        if self._connected and refresh:
            self.refresh(force=True)
        elif not self._connected:
            self._read_timer.stop()
            self._cancel_inline_editor()

    def set_symbols(self, symbols) -> None:
        self._symbol_index = SymbolIndex(symbols)
        self._auto_symbol_width_cache_key = None
        self._auto_symbol_width_cache_value = None
        self._update_scrollbars()
        self.viewport().update()

    def clear_symbols(self) -> None:
        self._symbol_index = SymbolIndex()
        self._auto_symbol_width_cache_key = None
        self._auto_symbol_width_cache_value = None
        self._update_scrollbars()
        self.viewport().update()

    def settings_state(self) -> dict:
        return {
            "display_type": self._display_type,
            "encoding": self._encoding,
            "separator_bytes": self._separator_bytes,
            "show_symbols": self._show_symbols,
            "show_symbol_offsets": self._show_symbol_offsets,
            "show_changes": self._show_changes,
            "symbol_width_px": self._symbol_width_px,
            "symbol_auto_fit": self._symbol_auto_fit,
            "symbol_width_mode": "auto" if self._symbol_auto_fit else "manual",
        }

    def load_settings_state(self, state: dict) -> None:
        display_type = str(state.get("display_type", "byte"))
        encoding = str(state.get("encoding", "ASCII"))
        separator = int(state.get("separator_bytes", 4) or 4)
        if display_type in DISPLAY_TYPES:
            self._display_type = display_type
        if encoding in TEXT_ENCODINGS:
            self._encoding = encoding
        if separator in SEPARATOR_BYTES:
            self._separator_bytes = separator
        self._show_symbols = bool(state.get("show_symbols", True))
        self._show_symbol_offsets = bool(state.get("show_symbol_offsets", True))
        self._show_changes = bool(state.get("show_changes", True))
        saved_symbol_width = state.get("symbol_width_px")
        try:
            self._symbol_width_px = int(saved_symbol_width) if saved_symbol_width is not None else None
        except (TypeError, ValueError):
            self._symbol_width_px = None
        # V0.6.8 introduces an explicit width mode. Older versions persisted
        # only ``symbol_auto_fit`` and could leave an installation permanently
        # stuck in a narrow manual width. Absence of the new mode is therefore
        # migrated to AUTO so full visible Symbol names are shown immediately.
        width_mode = str(state.get("symbol_width_mode", "")).strip().lower()
        if width_mode in {"auto", "manual"}:
            self._symbol_auto_fit = width_mode == "auto"
        else:
            self._symbol_auto_fit = True
        self._update_scrollbars()
        self.viewport().update()

    def goto_address(self, address: int) -> None:
        address = max(0, min(0xFFFFFFFF, int(address)))
        row = address // BYTES_PER_ROW
        max_row = max(0, self.TOTAL_ROWS - self._visible_rows())
        self.verticalScrollBar().setValue(min(row, max_row))
        self._set_single_selection(address, 1, "value")
        self._emit_selection_status()
        self.refresh(force=not self._contains_address(address))
        self.viewport().update()

    def refresh(self, *, force: bool = False) -> None:
        if not self._connected:
            return
        self._force_next_read = self._force_next_read or force
        self._read_timer.start()

    def set_block(self, address: int, data: bytes) -> None:
        address = int(address)
        data = bytes(data)
        old_start = self._block_start
        old_data = self._block_data
        old_end = old_start + len(old_data)

        changed: set[int] = set()
        for offset, value in enumerate(data):
            absolute = address + offset
            if old_start <= absolute < old_end:
                old_value = old_data[absolute - old_start]
                if old_value != value:
                    changed.add(absolute)
        self._changed_addresses = changed
        self._block_start = address
        self._block_data = data
        self.viewport().update()
        self._emit_selection_status()

    def patch_bytes(self, address: int, data: bytes) -> None:
        if not self._block_data:
            return
        address = int(address)
        payload = bytes(data)
        start = self._block_start
        end = start + len(self._block_data)
        if address >= end or address + len(payload) <= start:
            return
        mutable = bytearray(self._block_data)
        for i, value in enumerate(payload):
            absolute = address + i
            if start <= absolute < end:
                index = absolute - start
                if mutable[index] != value:
                    self._changed_addresses.add(absolute)
                mutable[index] = value
        self._block_data = bytes(mutable)
        self.viewport().update()
        self._emit_selection_status()

    # ---------- geometry / read planning ----------
    def _metrics(self):
        return self.viewport().fontMetrics()

    def _char_width(self) -> int:
        return max(7, self._metrics().horizontalAdvance("0"))

    def _row_height(self) -> int:
        return self._metrics().height() + 6

    def _visible_rows(self) -> int:
        return max(1, self.viewport().height() // self._row_height() - 1)

    def _auto_symbol_width(self) -> int:
        """Width needed for full Symbols in the current visible rows.

        The calculation is bounded by visible row count only and uses the local
        SymbolIndex; it never reads target memory. A sane cap prevents one very
        long debug name from making the Hex/Text panes unusable.
        """
        cw = self._char_width()
        minimum = cw * 12
        default = cw * 32
        maximum = cw * 120
        if not self._show_symbols or not self._symbol_index:
            return default
        first_row = self.verticalScrollBar().value()
        rows = self._visible_rows()
        key = (first_row, rows, self._show_symbol_offsets, id(self._symbol_index), cw)
        if key == self._auto_symbol_width_cache_key and self._auto_symbol_width_cache_value is not None:
            return self._auto_symbol_width_cache_value
        fm = self._metrics()
        widest = 0
        for row in range(rows):
            address = (first_row + row) * BYTES_PER_ROW
            if address >= ADDRESS_SPACE_SIZE:
                break
            text = self._row_symbol_text(address)
            if text:
                widest = max(widest, fm.horizontalAdvance(text) + cw * 2)
        value = default if widest <= 0 else max(minimum, min(maximum, widest))
        self._auto_symbol_width_cache_key = key
        self._auto_symbol_width_cache_value = value
        return value

    def _column_geometry(self) -> tuple[int, int, int, int, int, int, int]:
        cw = self._char_width()
        hscroll = self.horizontalScrollBar().value()
        address_x = 6 - hscroll
        address_w = cw * 11
        # Symbol stays a single aligned column, but unlike the V0.5.1 fixed
        # width it can now be resized like a real table column. Long names are
        # still elided inside the chosen width and never paint over Hex values.
        default_symbol_w = cw * 32
        min_symbol_w = cw * 12
        max_symbol_w = cw * 120
        if self._symbol_auto_fit:
            configured_symbol_w = self._auto_symbol_width()
        else:
            configured_symbol_w = default_symbol_w if self._symbol_width_px is None else int(self._symbol_width_px)
        symbol_w = max(min_symbol_w, min(max_symbol_w, configured_symbol_w)) if self._show_symbols else 0
        symbol_x = address_x + address_w
        values_x = symbol_x + symbol_w

        unit = display_unit_size(self._display_type)
        chars = display_value_chars(self._display_type)
        groups = BYTES_PER_ROW // unit
        value_w = 0
        for group in range(groups):
            offset = group * unit
            if offset > 0 and offset % self._separator_bytes == 0:
                value_w += cw
            value_w += cw * (chars + 1)
        text_x = values_x + value_w + cw * 2
        text_w = cw * 24
        total_w = text_x + text_w + cw + hscroll
        return address_x, address_w, symbol_x, symbol_w, values_x, text_x, total_w

    def _update_scrollbars(self) -> None:
        visible = self._visible_rows()
        max_row = max(0, self.TOTAL_ROWS - visible)
        vbar = self.verticalScrollBar()
        current = min(vbar.value(), max_row)
        vbar.setRange(0, max_row)
        vbar.setPageStep(visible)
        vbar.setSingleStep(1)
        vbar.setValue(current)

        *_, total_w = self._column_geometry()
        hbar = self.horizontalScrollBar()
        hbar.setRange(0, max(0, total_w - self.viewport().width()))
        hbar.setPageStep(max(1, self.viewport().width()))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._cancel_inline_editor()
        self._update_scrollbars()
        self.refresh(force=False)

    def _on_horizontal_scroll(self, _value: int) -> None:
        self._cancel_inline_editor()
        self.viewport().update()

    def _on_vertical_scroll(self, _value: int) -> None:
        self._cancel_inline_editor()
        self.viewport().update()
        if not self._visible_range_cached():
            self.refresh(force=False)

    def _visible_range_cached(self) -> bool:
        first = self.verticalScrollBar().value() * BYTES_PER_ROW
        end = min(ADDRESS_SPACE_SIZE, first + self._visible_rows() * BYTES_PER_ROW)
        return bool(self._block_data) and self._block_start <= first and self._block_start + len(self._block_data) >= end

    def _contains_address(self, address: int) -> bool:
        return self._block_start <= address < self._block_start + len(self._block_data)

    def _request_visible_now(self) -> None:
        if not self._connected:
            return
        first_row = self.verticalScrollBar().value()
        window = plan_read_window(first_row, self._visible_rows())
        cached = (
            self._block_data
            and self._block_start <= window.address
            and self._block_start + len(self._block_data) >= window.address + window.size
        )
        force = self._force_next_read
        self._force_next_read = False
        if cached and not force:
            return
        self.read_requested.emit(window.address, window.size)

    # ---------- cache / selection helpers ----------
    def _byte_at(self, address: int) -> int | None:
        index = int(address) - self._block_start
        if 0 <= index < len(self._block_data):
            return self._block_data[index]
        return None

    def _raw_at(self, address: int, size: int) -> bytes | None:
        index = int(address) - self._block_start
        if index < 0 or index + size > len(self._block_data):
            return None
        return self._block_data[index:index + size]

    def _value_cells(self, row_address: int):
        cw = self._char_width()
        _, _, _, _, x, _, _ = self._column_geometry()
        unit = display_unit_size(self._display_type)
        chars = display_value_chars(self._display_type)
        groups = BYTES_PER_ROW // unit
        for group in range(groups):
            offset = group * unit
            if offset > 0 and offset % self._separator_bytes == 0:
                x += cw
            width = cw * (chars + 1)
            yield row_address + offset, unit, x, width
            x += width

    def _set_single_selection(self, address: int, size: int, area: str) -> None:
        address = max(0, min(0xFFFFFFFF, int(address)))
        size = max(1, int(size))
        self._selected_address = address
        self._selection_area = area
        self._selection_anchor_address = address
        self._selection_anchor_size = size
        self._selection_focus_address = address
        self._selection_focus_size = size
        self._hex_nibble = ""
        self._hex_nibble_address = None

    def _extend_selection(self, address: int, size: int, area: str) -> None:
        if self._selection_anchor_address is None or area != self._selection_area:
            self._set_single_selection(address, size, area)
            return
        self._selection_focus_address = int(address)
        self._selection_focus_size = max(1, int(size))
        self._selected_address = int(address)
        self._hex_nibble = ""
        self._hex_nibble_address = None

    def _selected_range(self) -> tuple[int, int] | None:
        if self._selection_anchor_address is None or self._selection_focus_address is None:
            return None
        a0 = self._selection_anchor_address
        a1 = a0 + self._selection_anchor_size
        b0 = self._selection_focus_address
        b1 = b0 + self._selection_focus_size
        return min(a0, b0), max(a1, b1)

    def _range_intersects_selection(self, start: int, size: int) -> bool:
        selected = self._selected_range()
        if selected is None:
            return False
        end = start + size
        return start < selected[1] and end > selected[0]

    def _row_symbol_text(self, row_address: int) -> str:
        if not self._show_symbols or not self._symbol_index:
            return ""
        exact = self._symbol_index.exact(row_address)
        if exact is not None:
            return exact.name
        starts = self._symbol_index.starts_in_range(row_address, row_address + BYTES_PER_ROW, limit=1)
        if starts:
            sym = starts[0]
            off = sym.base_address - row_address
            return f"+0x{off:02X}  {sym.name}"
        if self._show_symbol_offsets:
            return self._symbol_index.describe(row_address, show_offset=True)
        return ""

    # ---------- paint ----------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self.viewport())
        painter.setFont(self._font)
        palette = self.palette()
        rect = self.viewport().rect()
        painter.fillRect(rect, palette.brush(QPalette.ColorRole.Base))

        row_h = self._row_height()
        fm = self._metrics()
        cw = self._char_width()
        address_x, address_w, symbol_x, symbol_w, values_x, text_x, _ = self._column_geometry()
        baseline_offset = (row_h + fm.ascent() - fm.descent()) // 2

        header_rect = QRect(0, 0, rect.width(), row_h)
        painter.fillRect(header_rect, palette.brush(QPalette.ColorRole.AlternateBase))
        painter.setPen(palette.color(QPalette.ColorRole.Text))
        painter.drawText(address_x, baseline_offset, "Address")
        if self._show_symbols:
            painter.drawText(symbol_x + 2, baseline_offset, "Symbol")
        for addr, _unit, x, _width in self._value_cells(0):
            painter.drawText(x, baseline_offset, f"+{addr:02X}")
        painter.drawText(text_x, baseline_offset, f"Text ({self._encoding})")

        # Subtle fixed column separators make the Symbol field read like a true
        # aligned column rather than free text painted over the hex area.
        separator_pen = palette.color(QPalette.ColorRole.Mid)
        painter.setPen(separator_pen)
        painter.drawLine(address_x + address_w - 3, 0, address_x + address_w - 3, rect.height())
        if self._show_symbols:
            painter.drawLine(symbol_x + symbol_w - 3, 0, symbol_x + symbol_w - 3, rect.height())
        painter.drawLine(text_x - cw, 0, text_x - cw, rect.height())

        first_row = self.verticalScrollBar().value()
        rows = self._visible_rows()
        selected_brush = palette.brush(QPalette.ColorRole.Highlight)
        selected_pen = palette.color(QPalette.ColorRole.HighlightedText)
        changed_color = palette.color(QPalette.ColorRole.Link)
        changed_color.setAlpha(55)
        address_color = palette.color(QPalette.ColorRole.PlaceholderText)
        symbol_color = palette.color(QPalette.ColorRole.Link)
        value_color = palette.color(QPalette.ColorRole.Text)

        for i in range(rows):
            row_index = first_row + i
            row_address = row_index * BYTES_PER_ROW
            if row_address >= ADDRESS_SPACE_SIZE:
                break
            y = (i + 1) * row_h
            if i % 2:
                painter.fillRect(QRect(0, y, rect.width(), row_h), palette.brush(QPalette.ColorRole.AlternateBase))

            painter.setPen(address_color)
            painter.drawText(address_x, y + baseline_offset, f"{row_address:08X}")

            if self._show_symbols:
                symbol_text = self._row_symbol_text(row_address)
                if symbol_text:
                    symbol_rect = QRect(symbol_x + 2, y, max(0, symbol_w - 8), row_h)
                    elided = fm.elidedText(symbol_text, Qt.TextElideMode.ElideRight, symbol_rect.width())
                    painter.setPen(symbol_color)
                    painter.drawText(
                        symbol_rect,
                        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                        elided,
                    )

            for cell_address, cell_size, x, width in self._value_cells(row_address):
                raw = self._raw_at(cell_address, cell_size)
                cell_rect = QRect(x - 2, y + 1, width, row_h - 2)
                selected = self._selection_area == "value" and self._range_intersects_selection(cell_address, cell_size)
                changed = any((cell_address + off) in self._changed_addresses for off in range(cell_size))
                if selected:
                    painter.fillRect(cell_rect, selected_brush)
                    painter.setPen(selected_pen)
                else:
                    if changed and self._show_changes:
                        painter.fillRect(cell_rect, changed_color)
                    painter.setPen(value_color)

                if (
                    self._display_type == "byte"
                    and self._hex_nibble
                    and self._hex_nibble_address == cell_address
                ):
                    text = f"{self._hex_nibble}_"
                else:
                    text = "?" if raw is None else format_display_value(raw, self._display_type)
                painter.drawText(x, y + baseline_offset, text)

            row_raw = self._raw_at(row_address, BYTES_PER_ROW)
            text = "." * BYTES_PER_ROW if row_raw is None else decode_text(row_raw, self._encoding)
            text_unit = text_edit_unit_size(self._encoding)
            if self._selection_area == "text":
                selected = self._selected_range()
                if selected is not None:
                    sel_start = max(selected[0], row_address)
                    sel_end = min(selected[1], row_address + BYTES_PER_ROW)
                    if sel_start < sel_end:
                        col0 = max(0, (sel_start - row_address) // text_unit)
                        col1 = max(col0 + 1, (sel_end - row_address + text_unit - 1) // text_unit)
                        painter.fillRect(
                            QRect(text_x + col0 * cw - 1, y + 1, max(cw, (col1 - col0) * cw), row_h - 2),
                            selected_brush,
                        )

            painter.setPen(value_color)
            painter.save()
            painter.setClipRect(QRect(text_x, y, max(0, rect.width() - text_x), row_h))
            painter.drawText(text_x, y + baseline_offset, text)
            painter.restore()

        painter.end()

    def _symbol_resize_hit(self, x: int) -> bool:
        if not self._show_symbols:
            return False
        _address_x, _address_w, symbol_x, symbol_w, _values_x, _text_x, _total_w = self._column_geometry()
        divider_x = symbol_x + symbol_w - 3
        return abs(int(x) - divider_x) <= 5

    def _resize_symbol_column_to(self, x: int) -> None:
        if not self._show_symbols:
            return
        cw = self._char_width()
        _address_x, _address_w, symbol_x, _symbol_w, _values_x, _text_x, _total_w = self._column_geometry()
        width = int(x) - symbol_x + 3
        self._symbol_auto_fit = False
        self._symbol_width_px = max(cw * 12, min(cw * 120, width))
        self._cancel_inline_editor()
        self._update_scrollbars()
        self.viewport().update()

    # ---------- hit testing / interaction ----------
    def _hit_test_position(self, x: int, y: int) -> tuple[int, int, str] | None:
        row_h = self._row_height()
        if y < row_h:
            return None
        row_in_view = (y // row_h) - 1
        if row_in_view < 0 or row_in_view >= self._visible_rows():
            return None
        row_address = (self.verticalScrollBar().value() + row_in_view) * BYTES_PER_ROW
        if row_address >= ADDRESS_SPACE_SIZE:
            return None

        address_x, address_w, symbol_x, symbol_w, values_x, text_x, _ = self._column_geometry()
        for address, size, cell_x, width in self._value_cells(row_address):
            if cell_x - 2 <= x < cell_x + width:
                return min(0xFFFFFFFF, address), size, "value"

        cw = self._char_width()
        if x >= text_x:
            unit = text_edit_unit_size(self._encoding)
            col = max(0, (x - text_x) // cw)
            byte_offset = int(col) * unit
            if byte_offset < BYTES_PER_ROW:
                return min(0xFFFFFFFF, row_address + byte_offset), min(unit, BYTES_PER_ROW - byte_offset), "text"

        if address_x <= x < values_x:
            return row_address, 1, "row"
        return None

    def _address_from_position(self, x: int, y: int) -> int | None:
        hit = self._hit_test_position(x, y)
        return None if hit is None else hit[0]

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            x = int(event.position().x())
            if self._symbol_resize_hit(x):
                self._resizing_symbol_column = True
                self._drag_selecting = False
                self._cancel_inline_editor()
                self.viewport().setCursor(Qt.CursorShape.SizeHorCursor)
                event.accept()
                return
            hit = self._hit_test_position(x, int(event.position().y()))
            if hit is not None:
                address, size, area = hit
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self._extend_selection(address, size, area)
                else:
                    self._set_single_selection(address, size, area)
                self._drag_selecting = area in {"value", "text"}
                self._cancel_inline_editor()
                self._emit_selection_status()
                self.viewport().update()
                self.setFocus()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        x = int(event.position().x())
        if self._resizing_symbol_column and event.buttons() & Qt.MouseButton.LeftButton:
            self._resize_symbol_column_to(x)
            self.viewport().setCursor(Qt.CursorShape.SizeHorCursor)
            event.accept()
            return
        if self._symbol_resize_hit(x):
            self.viewport().setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.viewport().unsetCursor()
        if self._drag_selecting and event.buttons() & Qt.MouseButton.LeftButton:
            hit = self._hit_test_position(x, int(event.position().y()))
            if hit is not None:
                address, size, area = hit
                if area == self._selection_area:
                    self._extend_selection(address, size, area)
                    self._emit_selection_status()
                    self.viewport().update()
                    event.accept()
                    return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._resizing_symbol_column:
                self._resizing_symbol_column = False
                if self._symbol_resize_hit(int(event.position().x())):
                    self.viewport().setCursor(Qt.CursorShape.SizeHorCursor)
                else:
                    self.viewport().unsetCursor()
                event.accept()
                return
            self._drag_selecting = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._symbol_resize_hit(int(event.position().x())):
                # Double-clicking the divider returns to automatic full-name fit.
                self._symbol_width_px = None
                self._symbol_auto_fit = True
                self._update_scrollbars()
                self.viewport().update()
                event.accept()
                return
            hit = self._hit_test_position(int(event.position().x()), int(event.position().y()))
            if hit is not None:
                address, size, area = hit
                self._set_single_selection(address, size, area)
                if area == "text":
                    self._edit_text_selected()
                elif area == "value":
                    self._edit_selected()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._selected_address is None:
            super().keyPressEvent(event)
            return

        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Escape:
            self._hex_nibble = ""
            self._hex_nibble_address = None
            self._cancel_inline_editor()
            self.viewport().update()
            event.accept()
            return
        if key == Qt.Key.Key_F2:
            if self._selection_area == "text":
                self._edit_text_selected()
            elif self._selection_area == "value":
                self._start_inline_value_edit()
            event.accept()
            return

        step = text_edit_unit_size(self._encoding) if self._selection_area == "text" else display_unit_size(self._display_type)
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            delta = 0
            if key == Qt.Key.Key_Left:
                delta = -step
            elif key == Qt.Key.Key_Right:
                delta = step
            elif key == Qt.Key.Key_Up:
                delta = -BYTES_PER_ROW
            elif key == Qt.Key.Key_Down:
                delta = BYTES_PER_ROW
            target = max(0, min(0xFFFFFFFF, self._selected_address + delta))
            size = step if self._selection_area in {"value", "text"} else 1
            if mods & Qt.KeyboardModifier.ShiftModifier:
                self._extend_selection(target, size, self._selection_area)
            else:
                self._set_single_selection(target, size, self._selection_area)
            self._ensure_selected_visible()
            self._emit_selection_status()
            self.viewport().update()
            event.accept()
            return

        text = event.text()
        plain_mods = mods & ~(Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.KeypadModifier)
        if text and not plain_mods:
            if self._selection_area == "text" and text.isprintable():
                self._write_text_payload(text)
                event.accept()
                return
            if self._selection_area == "value":
                if self._display_type == "byte" and text.upper() in "0123456789ABCDEF":
                    self._handle_hex_nibble(text.upper())
                    event.accept()
                    return
                if text in "+-0123456789.xXeEabcdefABCDEF":
                    self._start_inline_value_edit(initial_text=text)
                    event.accept()
                    return

        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        hit = self._hit_test_position(event.pos().x(), event.pos().y())
        if hit is not None:
            address, size, area = hit
            selected = self._selected_range()
            if selected is None or not (selected[0] <= address < selected[1]) or area != self._selection_area:
                self._set_single_selection(address, size, area)
            self._emit_selection_status()
            self.viewport().update()

        menu = QMenu(self)
        edit_action = menu.addAction("编辑 / 双击")
        edit_action.setEnabled(self._selected_address is not None and self._connected and self._selection_area in {"value", "text"})
        edit_action.triggered.connect(self._edit_current_area)

        goto_action = menu.addAction("转到地址\tCtrl+G")
        goto_action.triggered.connect(self._prompt_goto)

        menu.addSeparator()
        copy_action = menu.addAction("复制选中内容\tCtrl+C")
        copy_action.setEnabled(self._selected_address is not None)
        copy_action.triggered.connect(self._copy_selected)
        copy_hex_action = menu.addAction("复制内存块 (Hex)")
        copy_hex_action.setEnabled(self._selected_range() is not None)
        copy_hex_action.triggered.connect(self._copy_block_hex)
        copy_text_action = menu.addAction("复制内存块为文本")
        copy_text_action.setEnabled(self._selected_range() is not None)
        copy_text_action.triggered.connect(self._copy_block_text)
        paste_action = menu.addAction("从剪贴板写入\tCtrl+V")
        paste_action.setEnabled(self._selected_address is not None and self._connected and self._selection_area in {"value", "text"})
        paste_action.triggered.connect(self._paste_selected)
        copy_addr_action = menu.addAction("复制地址")
        copy_addr_action.setEnabled(self._selected_address is not None)
        copy_addr_action.triggered.connect(self._copy_selected_address)

        menu.addSeparator()
        display_menu = menu.addMenu("显示类型")
        display_group = QActionGroup(display_menu)
        display_group.setExclusive(True)
        for type_name in DISPLAY_TYPES:
            action = display_menu.addAction(_DISPLAY_LABELS[type_name])
            action.setCheckable(True)
            action.setChecked(type_name == self._display_type)
            action.setData(type_name)
            display_group.addAction(action)
            action.triggered.connect(lambda _checked=False, t=type_name: self._set_display_type(t))

        encoding_menu = menu.addMenu("文本编码")
        encoding_group = QActionGroup(encoding_menu)
        encoding_group.setExclusive(True)
        for encoding in TEXT_ENCODINGS:
            action = encoding_menu.addAction(encoding)
            action.setCheckable(True)
            action.setChecked(encoding == self._encoding)
            encoding_group.addAction(action)
            action.triggered.connect(lambda _checked=False, e=encoding: self._set_encoding(e))

        separator_menu = menu.addMenu("分隔符")
        separator_group = QActionGroup(separator_menu)
        separator_group.setExclusive(True)
        for size in SEPARATOR_BYTES:
            action = separator_menu.addAction(f"每 {size} Byte")
            action.setCheckable(True)
            action.setChecked(size == self._separator_bytes)
            separator_group.addAction(action)
            action.triggered.connect(lambda _checked=False, s=size: self._set_separator(s))

        menu.addSeparator()
        show_symbols = menu.addAction("显示符号")
        show_symbols.setCheckable(True)
        show_symbols.setChecked(self._show_symbols)
        show_symbols.toggled.connect(self._set_show_symbols)

        show_offsets = menu.addAction("显示符号偏移")
        show_offsets.setCheckable(True)
        show_offsets.setChecked(self._show_symbol_offsets)
        show_offsets.setEnabled(self._show_symbols)
        show_offsets.toggled.connect(self._set_show_symbol_offsets)

        show_changes = menu.addAction("显示变化")
        show_changes.setCheckable(True)
        show_changes.setChecked(self._show_changes)
        show_changes.toggled.connect(self._set_show_changes)

        menu.addSeparator()
        add_watch = menu.addAction("Add to Watch")
        add_watch.setEnabled(self._selected_address is not None)
        add_watch.triggered.connect(self._add_selected_to_watch)
        add_scope = menu.addAction("Add to Scope")
        add_scope.setEnabled(self._selected_address is not None)
        add_scope.triggered.connect(self._add_selected_to_scope)
        refresh_action = menu.addAction("刷新\tF5")
        refresh_action.setEnabled(self._connected)
        refresh_action.triggered.connect(lambda: self.refresh(force=True))
        menu.exec(event.globalPos())

    # ---------- editing ----------
    def _edit_current_area(self) -> None:
        if self._selection_area == "text":
            self._edit_text_selected()
        elif self._selection_area == "value":
            self._edit_selected()

    def _selected_type_and_raw(self) -> tuple[int, str, bytes] | None:
        if self._selected_address is None:
            return None
        type_name = "uint8" if self._display_type == "byte" else self._display_type
        size = get_type_info(type_name).size
        address = self._selected_address - (self._selected_address % size)
        raw = self._raw_at(address, size)
        if raw is None:
            return None
        self._selected_address = address
        return address, type_name, raw

    def _edit_selected(self) -> None:
        selected = self._selected_type_and_raw()
        if selected is None:
            return
        address, type_name, raw = selected
        self.edit_requested.emit(address, type_name, raw)

    def _edit_text_selected(self) -> None:
        if self._selected_address is None:
            return
        unit = text_edit_unit_size(self._encoding)
        raw = self._raw_at(self._selected_address, unit)
        if raw is None:
            return
        self.text_edit_requested.emit(self._selected_address, self._encoding, raw)

    def _handle_hex_nibble(self, nibble: str) -> None:
        if not self._connected or self._selected_address is None:
            return
        address = self._selected_address
        if self._hex_nibble_address != address:
            self._hex_nibble = ""
        self._hex_nibble_address = address
        if not self._hex_nibble:
            self._hex_nibble = nibble
            self._emit_selection_status(extra=f"hex edit: {nibble}_")
            self.viewport().update()
            return
        payload = bytes([int(self._hex_nibble + nibble, 16)])
        self._hex_nibble = ""
        self._hex_nibble_address = None
        self.write_requested.emit(address, payload)
        self._advance_selection(len(payload), area="value", size=1)

    def _start_inline_value_edit(self, initial_text: str | None = None) -> None:
        if not self._connected:
            return
        selected = self._selected_type_and_raw()
        if selected is None:
            return
        address, type_name, raw = selected
        rect = self._value_cell_rect(address)
        if rect is None:
            return
        try:
            value = decode_value(raw, type_name)
            current = format_value(value, type_name)
        except Exception:
            current = raw.hex(" ").upper()
        self._inline_edit_address = address
        self._inline_edit_type = type_name
        self._inline_editor.setGeometry(rect.adjusted(-2, 0, 2, 0))
        self._inline_editor.setText(current if initial_text is None else initial_text)
        self._inline_editor.show()
        self._inline_editor.raise_()
        self._inline_editor.setFocus(Qt.FocusReason.ShortcutFocusReason)
        if initial_text is None:
            self._inline_editor.selectAll()
        else:
            self._inline_editor.setCursorPosition(len(self._inline_editor.text()))

    def _value_cell_rect(self, address: int) -> QRect | None:
        row_h = self._row_height()
        row = int(address) // BYTES_PER_ROW
        first = self.verticalScrollBar().value()
        rel = row - first
        if rel < 0 or rel >= self._visible_rows():
            return None
        row_address = row * BYTES_PER_ROW
        y = (rel + 1) * row_h + 1
        for cell_address, _size, x, width in self._value_cells(row_address):
            if cell_address == address:
                return QRect(x - 2, y, width, row_h - 2)
        return None

    def _commit_inline_editor(self) -> None:
        if self._inline_committing or self._inline_edit_address is None or self._inline_edit_type is None:
            return
        self._inline_committing = True
        try:
            data = encode_value(self._inline_editor.text(), self._inline_edit_type)
        except Exception as exc:
            self.selection_changed.emit(str(exc))
            self._inline_committing = False
            return
        address = self._inline_edit_address
        size = len(data)
        self._cancel_inline_editor()
        self.write_requested.emit(address, data)
        self._advance_selection(size, area="value", size=max(1, size))
        self._inline_committing = False

    def _cancel_inline_editor(self) -> None:
        if self._inline_editor.isVisible():
            self._inline_editor.hide()
        self._inline_edit_address = None
        self._inline_edit_type = None

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self._inline_editor:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self._cancel_inline_editor()
                self.setFocus()
                return True
            if event.type() == QEvent.Type.FocusOut and not self._inline_committing:
                QTimer.singleShot(0, self._cancel_inline_editor)
        return super().eventFilter(watched, event)

    def _write_text_payload(self, text: str) -> None:
        if not self._connected or self._selected_address is None:
            return
        try:
            data = encode_text_input(text, self._encoding)
        except Exception as exc:
            self.selection_changed.emit(str(exc))
            return
        if not data:
            return
        address = self._selected_address
        self.write_requested.emit(address, data)
        self._advance_selection(len(data), area="text", size=text_edit_unit_size(self._encoding))

    def _advance_selection(self, byte_count: int, *, area: str, size: int) -> None:
        if self._selected_address is None:
            return
        address = max(0, min(0xFFFFFFFF, self._selected_address + max(1, int(byte_count))))
        self._set_single_selection(address, size, area)
        self._ensure_selected_visible()
        self._emit_selection_status()
        self.viewport().update()

    def _ensure_selected_visible(self) -> None:
        if self._selected_address is None:
            return
        row = self._selected_address // BYTES_PER_ROW
        first = self.verticalScrollBar().value()
        rows = self._visible_rows()
        if row < first:
            self.verticalScrollBar().setValue(row)
        elif row >= first + rows:
            self.verticalScrollBar().setValue(max(0, row - rows + 1))

    # ---------- clipboard ----------
    def _selected_raw_range(self) -> tuple[int, bytes] | None:
        selected = self._selected_range()
        if selected is None:
            return None
        start, end = selected
        raw = self._raw_at(start, end - start)
        if raw is None:
            self.selection_changed.emit("Selected memory range is not loaded; press F5 first")
            return None
        return start, raw

    def _copy_selected(self) -> None:
        selected_range = self._selected_range()
        if selected_range is None:
            return
        if selected_range[1] - selected_range[0] > max(1, self._selection_focus_size):
            if self._selection_area == "text":
                self._copy_block_text()
            else:
                self._copy_block_hex()
            return
        if self._selection_area == "text":
            self._copy_block_text()
            return
        selected = self._selected_type_and_raw()
        if selected is None:
            return
        _address, type_name, raw = selected
        text = format_display_value(raw, "byte" if type_name == "uint8" and self._display_type == "byte" else type_name)
        QApplication.clipboard().setText(text)

    def _copy_block_hex(self) -> None:
        selected = self._selected_raw_range()
        if selected is None:
            return
        _start, raw = selected
        QApplication.clipboard().setText(format_hex_block(raw))

    def _copy_block_text(self) -> None:
        selected = self._selected_raw_range()
        if selected is None:
            return
        _start, raw = selected
        QApplication.clipboard().setText(decode_text(raw, self._encoding))

    def _paste_selected(self) -> None:
        if not self._connected or self._selected_address is None:
            return
        text = QApplication.clipboard().text()
        if not text:
            return
        try:
            if self._selection_area == "text":
                data = encode_text_input(text, self._encoding)
            else:
                compact = text.strip()
                tokens = [t for t in re.split(r"[\s,;]+", compact) if t]
                if tokens and all(re.fullmatch(r"(?:0x)?[0-9A-Fa-f]{2}", t) for t in tokens):
                    data = bytes(int(t, 16) for t in (tok[2:] if tok.lower().startswith("0x") else tok for tok in tokens))
                else:
                    type_name = "uint8" if self._display_type == "byte" else self._display_type
                    data = encode_value(compact, type_name)
        except Exception as exc:
            self.selection_changed.emit(str(exc))
            return
        if not data:
            return
        address = self._selected_address
        self.write_requested.emit(address, data)
        area = self._selection_area if self._selection_area in {"value", "text"} else "value"
        size = text_edit_unit_size(self._encoding) if area == "text" else display_unit_size(self._display_type)
        self._advance_selection(len(data), area=area, size=size)

    def _copy_selected_address(self) -> None:
        if self._selected_address is not None:
            QApplication.clipboard().setText(f"0x{self._selected_address:08X}")

    # ---------- menu options ----------
    def set_display_type(self, type_name: str) -> None:
        """Apply a typed Memory view without coupling callers to menu internals."""
        self._set_display_type(type_name)

    def _set_display_type(self, type_name: str) -> None:
        if type_name not in DISPLAY_TYPES:
            return
        self._display_type = type_name
        self._cancel_inline_editor()
        if self._selected_address is not None and self._selection_area == "value":
            unit = display_unit_size(type_name)
            address = self._selected_address - self._selected_address % unit
            self._set_single_selection(address, unit, "value")
        self._update_scrollbars()
        self._emit_selection_status()
        self.viewport().update()

    def _set_encoding(self, encoding: str) -> None:
        if encoding in TEXT_ENCODINGS:
            self._encoding = encoding
            if self._selected_address is not None and self._selection_area == "text":
                unit = text_edit_unit_size(encoding)
                self._set_single_selection(self._selected_address, unit, "text")
            self.viewport().update()

    def _set_separator(self, size: int) -> None:
        if size in SEPARATOR_BYTES:
            self._separator_bytes = size
            self._update_scrollbars()
            self.viewport().update()

    def _set_show_symbols(self, enabled: bool) -> None:
        self._show_symbols = bool(enabled)
        if not self._show_symbols:
            self._resizing_symbol_column = False
            self.viewport().unsetCursor()
        self._update_scrollbars()
        self.viewport().update()

    def _set_show_symbol_offsets(self, enabled: bool) -> None:
        self._show_symbol_offsets = bool(enabled)
        self._auto_symbol_width_cache_key = None
        self._auto_symbol_width_cache_value = None
        self._update_scrollbars()
        self.viewport().update()

    def _set_show_changes(self, enabled: bool) -> None:
        self._show_changes = bool(enabled)
        self.viewport().update()

    def _prompt_goto(self) -> None:
        current = self._selected_address
        if current is None:
            current = self.verticalScrollBar().value() * BYTES_PER_ROW
        text, ok = QInputDialog.getText(self, "转到地址", "Address", text=f"0x{current:08X}")
        if not ok:
            return
        try:
            self.goto_address(parse_address(text))
        except Exception as exc:
            self.selection_changed.emit(str(exc))

    def _add_selected_to_watch(self) -> None:
        if self._selected_address is None:
            return
        address = self._selected_address
        exact = self._symbol_index.exact(address)
        resolved = exact or self._symbol_index.resolve(address)
        name = resolved.name if resolved is not None and resolved.base_address == address else f"Memory_{address:08X}"
        if resolved is not None and resolved.base_address == address and resolved.type_name in supported_types():
            type_name = str(resolved.type_name)
        else:
            type_name = "uint8" if self._display_type == "byte" else self._display_type
        self.add_watch_requested.emit(name, address, type_name)

    def _add_selected_to_scope(self) -> None:
        if self._selected_address is None:
            return
        address = self._selected_address
        exact = self._symbol_index.exact(address)
        resolved = exact or self._symbol_index.resolve(address)
        name = resolved.name if resolved is not None and resolved.base_address == address else f"Memory_{address:08X}"
        if resolved is not None and resolved.base_address == address and resolved.type_name in supported_types():
            type_name = str(resolved.type_name)
        else:
            type_name = "uint8" if self._display_type == "byte" else self._display_type
        self.add_scope_requested.emit(name, address, type_name)

    def _emit_selection_status(self, *, extra: str = "") -> None:
        if self._selected_address is None:
            self.selection_changed.emit("")
            return
        address = self._selected_address
        symbol = self._symbol_index.describe(address, show_offset=True) if self._symbol_index else ""
        selected_range = self._selected_range()
        range_text = ""
        if selected_range is not None and selected_range[1] - selected_range[0] > 1:
            range_text = f" | selected {selected_range[1] - selected_range[0]} B"

        if self._selection_area == "text":
            unit = text_edit_unit_size(self._encoding)
            raw = self._raw_at(address, unit)
            value_text = "text: not loaded" if raw is None else f"text({self._encoding}): {decode_text(raw, self._encoding)} | raw {raw.hex(' ').upper()}"
        else:
            selected = self._selected_type_and_raw()
            if selected is None:
                value_text = "not loaded"
            else:
                _addr, type_name, raw = selected
                try:
                    value = decode_value(raw, type_name)
                    value_text = f"{type_name}: {format_value(value, type_name)} | raw {raw.hex(' ').upper()}"
                except Exception:
                    value_text = raw.hex(" ").upper()
        prefix = f"0x{address:08X}"
        if symbol:
            prefix += f" | {symbol}"
        if extra:
            value_text += f" | {extra}"
        self.selection_changed.emit(f"{prefix}{range_text} | {value_text}")


class SymbolMemoryView(QWidget):
    """Typed AXF/DWARF neighborhood view over one bounded raw-memory block.

    Unlike the Raw/Hex view, rows are real scalar Symbols/members and each row is
    decoded with its own DWARF type/size. The target is still read once as a block;
    rendering ten or one hundred members never becomes ten or one hundred J-Link
    reads. This is intentionally a flat first version: full paths preserve struct
    and array context (``obj.bias[0]``..``[3]``) without inventing hierarchy.
    """

    read_requested = Signal(object, int)
    write_requested = Signal(object, object)
    edit_requested = Signal(object, str, object)
    add_watch_requested = Signal(str, object, str)
    add_scope_requested = Signal(str, object, str)
    selection_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connected = False
        self._anchor_address = DEFAULT_RAM_BASE
        self._symbol_index = SymbolIndex()
        self._block_start = 0
        self._block_data = b""
        # A symbol navigation may need one intentional center-on-anchor after
        # the next block arrives. Normal/manual/auto refreshes must preserve
        # the user's current viewport instead of snapping back to the anchor.
        self._focus_anchor_on_next_block = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeView(self)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.doubleClicked.connect(self._double_clicked)
        # CE-style selection semantics: a Symbol navigation highlights its target,
        # but clicking empty viewport space explicitly clears that selection/current
        # row. Refresh then respects the cleared state instead of resurrecting it.
        self.tree.viewport().installEventFilter(self)
        layout.addWidget(self.tree, 1)

        self._model = QStandardItemModel(0, 4, self)
        self._model.setHorizontalHeaderLabels(["Address", "Symbol", "Type", "Value"])
        self.tree.setModel(self._model)
        self.tree.selectionModel().currentRowChanged.connect(self._current_row_changed)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(70)
        self.tree.setColumnWidth(0, 110)
        self.tree.setColumnWidth(1, 520)
        self.tree.setColumnWidth(2, 110)
        self.tree.setColumnWidth(3, 180)

    def set_connected(self, connected: bool) -> None:
        self._connected = bool(connected)

    def set_symbols(self, symbols) -> None:
        self._symbol_index = SymbolIndex(symbols)
        self._rebuild_model(preserve_view=True)

    def clear_symbols(self) -> None:
        self._symbol_index = SymbolIndex()
        self._focus_anchor_on_next_block = False
        self._rebuild_model(preserve_view=False)

    def goto_address(self, address: int) -> None:
        self._anchor_address = max(0, min(0xFFFFFFFF, int(address)))
        # Navigation may center the requested symbol once. Refresh is a data
        # update only and must never reuse this anchor to control scrolling.
        self._focus_anchor_on_next_block = True
        if self._contains_address(self._anchor_address):
            self._rebuild_model(preserve_view=False, focus_anchor=True)
            self._focus_anchor_on_next_block = False
            return
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> None:
        if not self._connected:
            return
        window = plan_symbol_read_window(self._anchor_address)
        cached = (
            bool(self._block_data)
            and self._block_start <= window.address
            and self._block_start + len(self._block_data) >= window.address + window.size
        )
        if cached and not force:
            # The local model is already current. In particular, do not rebuild
            # just because a timer fired: rebuilding used to reset scroll/current
            # selection and made Symbols View jump back to the navigation anchor.
            return
        self.read_requested.emit(window.address, window.size)

    def set_block(self, address: int, data: bytes) -> None:
        self._block_start = int(address)
        self._block_data = bytes(data)
        focus_anchor = self._focus_anchor_on_next_block
        self._focus_anchor_on_next_block = False
        self._rebuild_model(preserve_view=not focus_anchor, focus_anchor=focus_anchor)

    def patch_bytes(self, address: int, data: bytes) -> None:
        if not self._block_data:
            return
        payload = bytes(data)
        start = self._block_start
        end = start + len(self._block_data)
        if int(address) >= end or int(address) + len(payload) <= start:
            return
        mutable = bytearray(self._block_data)
        for i, value in enumerate(payload):
            absolute = int(address) + i
            if start <= absolute < end:
                mutable[absolute - start] = value
        self._block_data = bytes(mutable)
        self._rebuild_model(preserve_view=True)

    def _contains_address(self, address: int) -> bool:
        return bool(self._block_data) and self._block_start <= int(address) < self._block_start + len(self._block_data)

    def _raw_at(self, address: int, size: int) -> bytes | None:
        index = int(address) - self._block_start
        if index < 0 or index + int(size) > len(self._block_data):
            return None
        return self._block_data[index:index + int(size)]

    def _fit_symbol_column(self) -> None:
        fm = self.tree.fontMetrics()
        width = fm.horizontalAdvance("Symbol") + 28
        for row in range(self._model.rowCount()):
            width = max(width, fm.horizontalAdvance(str(self._model.index(row, 1).data() or "")) + 28)
        # Full paths are the point of this view. A generous cap keeps pathological
        # template/debug names from consuming the entire screen; horizontal scroll
        # remains available beyond the viewport.
        self.tree.setColumnWidth(1, min(max(width, 360), 1000))
        self.tree.setColumnWidth(0, 110)
        self.tree.setColumnWidth(2, 110)
        self.tree.setColumnWidth(3, 180)

    def _rebuild_model(self, *, preserve_view: bool = True, focus_anchor: bool = False) -> None:
        # Model rebuilds are local presentation work. Preserve the user's
        # viewport/current selection across refreshes; only an explicit symbol
        # navigation may center the anchor once.
        vscroll = self.tree.verticalScrollBar().value() if preserve_view else 0
        hscroll = self.tree.horizontalScrollBar().value() if preserve_view else 0
        selected_name = ""
        if preserve_view:
            # Preserve only a *real selected row*, not merely QTreeView's current
            # index. clearSelection() does not necessarily clear currentIndex(), and
            # using currentIndex() here caused a cleared navigation highlight to be
            # resurrected on the next Auto Refresh.
            selected_rows = self.tree.selectionModel().selectedRows()
            if selected_rows:
                symbol = self._symbol_for_row(selected_rows[0].row())
                selected_name = symbol.name if symbol is not None else ""

        self._model.removeRows(0, self._model.rowCount())
        if not self._symbol_index or not self._block_data:
            return

        start = self._block_start
        end = start + len(self._block_data)
        rows = self._symbol_index.scalar_starts_in_range(start, end, limit=512)
        anchor_row = -1
        nearest_distance: int | None = None
        row_by_name: dict[str, int] = {}
        for symbol in rows:
            display_type = symbol_display_type(symbol.type_name)
            if display_type is None:
                continue
            size = get_type_info(display_type).size
            raw = self._raw_at(symbol.base_address, size)
            value_text = "?"
            if raw is not None:
                try:
                    value_text = format_display_value(raw, display_type)
                except Exception:
                    value_text = "?"

            address_item = QStandardItem(f"0x{symbol.base_address:08X}")
            symbol_item = QStandardItem(symbol.name)
            type_item = QStandardItem(display_type)
            value_item = QStandardItem(value_text)
            for item in (address_item, symbol_item, type_item, value_item):
                item.setEditable(False)
            address_item.setData(symbol.name, Qt.ItemDataRole.UserRole)
            model_row = self._model.rowCount()
            self._model.appendRow([address_item, symbol_item, type_item, value_item])
            row_by_name[symbol.name] = model_row

            if symbol.base_address <= self._anchor_address < symbol.base_address + size:
                anchor_row = model_row
                nearest_distance = 0
            elif nearest_distance != 0:
                distance = abs(symbol.base_address - self._anchor_address)
                if nearest_distance is None or distance < nearest_distance:
                    nearest_distance = distance
                    anchor_row = model_row

        self._fit_symbol_column()

        if focus_anchor and 0 <= anchor_row < self._model.rowCount():
            # Explicit Symbol navigation is the one place where we intentionally
            # center *and* highlight the destination so the user can immediately
            # see which typed member was resolved. This is one-shot navigation
            # presentation only; refresh never scrolls back to this anchor.
            index = self._model.index(anchor_row, 0)
            self.tree.setCurrentIndex(index)
            self.tree.selectionModel().select(
                index,
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            self.tree.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
            return

        if preserve_view:
            # Restore an actually selected row if it still exists. If the user
            # cleared selection by clicking empty space, keep it cleared. Restore
            # scroll positions last so selection restoration cannot move viewport.
            row = row_by_name.get(selected_name, -1)
            if 0 <= row < self._model.rowCount():
                index = self._model.index(row, 0)
                self.tree.setCurrentIndex(index)
                self.tree.selectionModel().select(
                    index,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
            else:
                self.tree.clearSelection()
                self.tree.setCurrentIndex(QModelIndex())
            self.tree.verticalScrollBar().setValue(vscroll)
            self.tree.horizontalScrollBar().setValue(hscroll)

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.tree.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            # A click on empty space means "nothing selected". Keep normal row
            # clicks untouched so they select that row. This also clears the
            # current index because QTreeView can retain currentIndex() even after
            # clearSelection(), which would otherwise be restored on refresh.
            position = event.position().toPoint()
            if not self.tree.indexAt(position).isValid():
                self.tree.clearSelection()
                self.tree.setCurrentIndex(QModelIndex())
        return super().eventFilter(watched, event)

    def _symbol_for_row(self, row: int):
        if row < 0 or row >= self._model.rowCount():
            return None
        item = self._model.item(row, 0)
        name = str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""
        return self._symbol_index.exact_name(name) if name else None

    def _current_symbol(self):
        index = self.tree.currentIndex()
        return self._symbol_for_row(index.row()) if index.isValid() else None

    def _current_row_changed(self, current, _previous) -> None:
        if not current.isValid():
            return
        symbol = self._symbol_for_row(current.row())
        if symbol is None:
            return
        display_type = symbol_display_type(symbol.type_name)
        if display_type is None:
            return
        size = get_type_info(display_type).size
        raw = self._raw_at(symbol.base_address, size)
        value_text = "?" if raw is None else format_display_value(raw, display_type)
        raw_text = "" if raw is None else raw.hex(" ").upper()
        self.selection_changed.emit(
            f"0x{symbol.base_address:08X} | {symbol.name} | {display_type}: {value_text} | raw {raw_text}"
        )

    def _double_clicked(self, index) -> None:
        symbol = self._symbol_for_row(index.row()) if index.isValid() else None
        if symbol is None:
            return
        display_type = symbol_display_type(symbol.type_name)
        if display_type is None:
            return
        size = get_type_info(display_type).size
        raw = self._raw_at(symbol.base_address, size)
        if raw is not None:
            self.edit_requested.emit(symbol.base_address, display_type, raw)

    def _show_context_menu(self, pos) -> None:
        index = self.tree.indexAt(pos)
        if index.isValid():
            self.tree.setCurrentIndex(index)
        symbol = self._current_symbol()
        if symbol is None:
            return
        display_type = symbol_display_type(symbol.type_name)
        if display_type is None:
            return
        menu = QMenu(self.tree)
        edit_action = menu.addAction("Edit Value")
        add_watch_action = menu.addAction("Add to Watch")
        add_scope_action = menu.addAction("Add to Scope")
        copy_symbol_action = menu.addAction("Copy Symbol")
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is edit_action:
            size = get_type_info(display_type).size
            raw = self._raw_at(symbol.base_address, size)
            if raw is not None:
                self.edit_requested.emit(symbol.base_address, display_type, raw)
        elif chosen is add_watch_action:
            self.add_watch_requested.emit(symbol.name, symbol.base_address, display_type)
        elif chosen is add_scope_action:
            self.add_scope_requested.emit(symbol.name, symbol.base_address, display_type)
        elif chosen is copy_symbol_action:
            QApplication.clipboard().setText(symbol.name)


class MemoryExplorerPage(QWidget):
    read_requested = Signal(object, int)
    write_requested = Signal(object, object)
    add_watch_requested = Signal(str, object, str)
    add_scope_requested = Signal(str, object, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connected = False
        self._current_address = DEFAULT_RAM_BASE
        self._last_navigation_kind = "address"  # address | symbol

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Address / Symbol"))
        self._symbol_index = SymbolIndex()
        # Editable combo keeps the original Address/Symbol editor footprint but
        # adds a CE-like drop-down containing only successful navigation queries.
        # Symbol completion remains a separate AXF-backed QCompleter on the line
        # edit, so opening history never rebuilds/filter-scans the symbol model.
        self._navigation_history: list[str] = []
        self._selected_history_query: str | None = None
        self.address_combo = NavigationHistoryComboBox()
        self.address_combo.setEditable(True)
        self.address_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.address_combo.setMinimumWidth(320)
        self.address_combo.setMaximumWidth(520)
        self.address_combo.setToolTip("输入地址或 Symbol；右侧下拉箭头显示历史查询、类型与地址")

        # History is a tiny MRU model, deliberately separate from the large AXF
        # completion model. The editor keeps the same footprint; only the popup
        # expands to show Query / Type / Address like the symbol completion list.
        self._history_model = QStandardItemModel(0, 3, self)
        self._history_model.setHorizontalHeaderLabels(["History", "Type", "Address"])
        history_popup = QTreeView()
        self._history_popup = history_popup
        history_popup.setRootIsDecorated(False)
        history_popup.setAlternatingRowColors(True)
        history_popup.setUniformRowHeights(True)
        history_popup.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        history_popup.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        history_popup.installEventFilter(self)
        history_popup.setMinimumWidth(620)
        history_popup.setMinimumHeight(180)
        history_popup.setMaximumHeight(360)
        history_popup.setColumnWidth(0, 330)
        history_popup.setColumnWidth(1, 120)
        history_popup.setColumnWidth(2, 130)
        history_popup.header().setStretchLastSection(False)
        history_popup.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.address_combo.setModel(self._history_model)
        self.address_combo.setView(history_popup)
        self.address_combo.setModelColumn(0)
        self.address_edit = self.address_combo.lineEdit()
        self.address_edit.setText(f"0x{DEFAULT_RAM_BASE:08X}")
        self.address_edit.setPlaceholderText(
            "0x20000000 或变量/成员，例如 BlowerParamsObj.m_PosSpeed、buffer[1]"
        )
        self.address_edit.returnPressed.connect(self._address_return_pressed)
        self.address_edit.textEdited.connect(self._history_editor_text_edited)
        self.address_combo.history_activated.connect(self._history_activated)
        toolbar.addWidget(self.address_combo)
        self.delete_history_btn = QPushButton("Delete History")
        self.delete_history_btn.setToolTip("删除当前选择/当前查询对应的单条历史；不改变当前 Memory 地址")
        self.delete_history_btn.setEnabled(False)
        self.delete_history_btn.clicked.connect(self._delete_selected_history)
        toolbar.addWidget(self.delete_history_btn)

        self.clear_history_btn = QPushButton("Clear History")
        self.clear_history_btn.setToolTip("清空全部 Memory Address / Symbol 查询历史")
        self.clear_history_btn.clicked.connect(self._clear_navigation_history)
        toolbar.addWidget(self.clear_history_btn)

        # Build the symbol rows only when AXF/ELF changes. QCompleter filters the
        # existing model locally while typing, so there is no per-key row rebuild
        # and absolutely no J-Link traffic on the search path.
        self._symbol_completion_model = QStandardItemModel(0, 3, self)
        self._symbol_completion_model.setHorizontalHeaderLabels(["Symbol", "Type", "Address"])
        self._symbol_completer = QCompleter(self._symbol_completion_model, self)
        self._symbol_completer.setCompletionColumn(0)
        self._symbol_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._symbol_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._symbol_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._symbol_completer.setMaxVisibleItems(14)
        completion_popup = QTreeView()
        self._completion_popup = completion_popup
        completion_popup.setRootIsDecorated(False)
        completion_popup.setAlternatingRowColors(True)
        completion_popup.setUniformRowHeights(True)
        completion_popup.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        completion_popup.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # QCompleter computes popup geometry from the custom QTreeView's row
        # size hint. On Windows/Qt styles the first completion can arrive while
        # that hint is still effectively header-only, producing the exact user
        # symptom where Symbol/Type/Address headers are visible but a real
        # matching symbol (for example MaxRpm) is clipped out. Keep a stable
        # CE/Watch-like popup viewport instead of letting a short query collapse
        # the tree to header height. This is geometry-only: filtering remains the
        # already-built local completion model and never touches J-Link.
        completion_popup.setMinimumHeight(240)
        completion_popup.setMaximumHeight(420)
        completion_popup.setMinimumWidth(660)
        completion_popup.setColumnWidth(0, 400)
        completion_popup.setColumnWidth(1, 130)
        completion_popup.setColumnWidth(2, 120)
        completion_popup.header().setStretchLastSection(False)
        completion_popup.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._symbol_completer.setPopup(completion_popup)
        self._symbol_completer.activated[str].connect(self._symbol_completion_activated)
        self.address_edit.setCompleter(self._symbol_completer)

        self.go_btn = QPushButton("Go")
        self.go_btn.clicked.connect(self._goto)
        toolbar.addWidget(self.go_btn)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(lambda: self._active_view().refresh(force=True))
        toolbar.addWidget(self.refresh_btn)

        self.auto_check = QCheckBox("Auto Refresh")
        self.auto_check.toggled.connect(self._auto_toggled)
        toolbar.addWidget(self.auto_check)
        self.auto_interval = IntPresetComboBox(
            [100, 200, 500, 1000, 2000, 5000],
            value=1000,
            minimum=100,
            maximum=10000,
            suffix="ms",
        )
        self.auto_interval.setToolTip(
            "Memory auto-refresh presets; type a custom 100..10000 ms interval when needed"
        )
        self.auto_interval.valueChanged.connect(self._auto_interval_changed)
        toolbar.addWidget(self.auto_interval)

        toolbar.addWidget(QLabel("View"))
        self.view_mode_combo = QComboBox(self)
        self.view_mode_combo.addItem("Auto", "auto")
        self.view_mode_combo.addItem("Raw", "raw")
        self.view_mode_combo.addItem("Symbols", "symbols")
        self.view_mode_combo.setToolTip(
            "Auto: Symbol navigation uses typed Symbol rows; raw-address navigation uses the CE-style Raw view"
        )
        self.view_mode_combo.currentIndexChanged.connect(self._view_mode_changed)
        toolbar.addWidget(self.view_mode_combo)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # Keep ``self.view`` as the Raw/Hex view for compatibility with existing
        # callers/tests. The stack adds a typed semantic view without changing the
        # single J-Link read/write ownership model.
        self.view = HexMemoryView(self)
        self.symbol_view = SymbolMemoryView(self)
        for memory_view in (self.view, self.symbol_view):
            memory_view.read_requested.connect(self.read_requested.emit)
            memory_view.write_requested.connect(self.write_requested.emit)
            memory_view.edit_requested.connect(self._edit_requested)
            memory_view.add_watch_requested.connect(self.add_watch_requested.emit)
            memory_view.add_scope_requested.connect(self.add_scope_requested.emit)
            memory_view.selection_changed.connect(self._selection_changed)
        self.view.text_edit_requested.connect(self._text_edit_requested)

        self.view_stack = QStackedWidget(self)
        self.view_stack.addWidget(self.view)
        self.view_stack.addWidget(self.symbol_view)
        layout.addWidget(self.view_stack, 1)
        self._apply_view_mode(refresh=False)

        self.status_label = QLabel(
            "单击选择；拖动/Shift 选择内存块；Byte 视图直接键入两个十六进制字符即可写入；"
            "Text 区可直接键入文本；双击弹窗编辑；Ctrl+C/Ctrl+V；Address / Symbol 可输入地址、变量、"
            "结构体成员或数组成员（如 buffer[1]），输入时本地过滤，回车跳转；Symbol 跳转会自动采用其标量类型；成功查询会记入带 Type/Address 的下拉历史；选择历史项后可用 Delete History 单独删除，也可 Clear History 全清；F5 刷新，Ctrl+G 跳转。"
        )
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status_label)

        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(lambda: self._active_view().refresh(force=True))
        self._update_enabled()

    def set_connected(self, connected: bool) -> None:
        self._connected = bool(connected)
        # Set passive connection state on both renderers, then issue at most one
        # visible read from the active mode.
        self.view.set_connected(connected, refresh=False)
        self.symbol_view.set_connected(connected)
        if self._connected:
            self._active_view().refresh(force=True)
        self._update_enabled()
        self._auto_toggled(self.auto_check.isChecked())

    def set_symbols(self, symbols) -> None:
        # Materialize once because both the address-bar lookup and Hex overlay
        # consume the same AXF/DWARF records. Rebuilding occurs only on AXF load.
        records = tuple(symbols)
        self._symbol_index = SymbolIndex(records)
        self.view.set_symbols(records)
        self.symbol_view.set_symbols(records)
        self._rebuild_symbol_completion_model()
        # Type/address columns in the small MRU popup are resolved from the
        # latest AXF/DWARF index, so a reloaded image never leaves stale types.
        self._sync_navigation_history_combo()

    def clear_symbols(self) -> None:
        self._symbol_index = SymbolIndex()
        self._install_symbol_completion_model(())
        self.view.clear_symbols()
        self.symbol_view.clear_symbols()
        self._apply_view_mode(refresh=False)
        self._sync_navigation_history_combo()

    def set_block(self, address: int, data: bytes) -> None:
        # One worker block read feeds both renderers. The inactive renderer only
        # updates local cache/model and never initiates target I/O.
        self.view.set_block(address, data)
        self.symbol_view.set_block(address, data)

    def patch_bytes(self, address: int, data: bytes) -> None:
        self.view.patch_bytes(address, data)
        self.symbol_view.patch_bytes(address, data)

    def goto_address(self, address: int, *, display_text: str | None = None) -> None:
        address = int(address)
        self._current_address = address
        shown = str(display_text).strip() if display_text is not None else f"0x{address:08X}"
        self.address_combo.setEditText(shown)
        self._apply_view_mode(refresh=False)
        self._active_view().goto_address(address)

    def open_symbol_location(self, name: str, address: int, type_name: str = "") -> None:
        """Open a Watch/Scope symbol in the most useful Memory renderer.

        An exact AXF/DWARF name+address uses the semantic Symbols view in Auto
        mode. Manually named rows still open the raw address without guessing a
        Symbol identity. This is presentation/navigation only; target I/O remains
        delegated to the existing active Memory view and single J-Link worker.
        """
        address = max(0, min(0xFFFFFFFF, int(address)))
        clean_name = str(name).strip()
        symbol = self._symbol_index.exact_name(clean_name) if clean_name and self._symbol_index else None
        if symbol is not None and int(symbol.base_address) == address:
            self._goto_symbol(symbol, remember=False)
            return

        display_type = symbol_display_type(type_name)
        if display_type is not None:
            self.view.set_display_type(display_type)
        self._last_navigation_kind = "address"
        self.goto_address(address, display_text=f"0x{address:08X}")
        if clean_name:
            self.status_label.setText(f"{clean_name} → 0x{address:08X} | {type_name or 'unknown'}")

    def settings_state(self) -> dict:
        state = self.view.settings_state()
        state.update(
            {
                "auto_refresh": self.auto_check.isChecked(),
                "auto_interval_ms": self.auto_interval.value(),
                "navigation_history": list(self._navigation_history),
                "view_mode": str(self.view_mode_combo.currentData() or "auto"),
            }
        )
        return state

    def load_settings_state(self, state: dict) -> None:
        if not isinstance(state, dict):
            return
        self.view.load_settings_state(state)
        view_mode = str(state.get("view_mode", "auto") or "auto").strip().lower()
        mode_index = self.view_mode_combo.findData(view_mode)
        if mode_index >= 0:
            self.view_mode_combo.blockSignals(True)
            self.view_mode_combo.setCurrentIndex(mode_index)
            self.view_mode_combo.blockSignals(False)
        saved_history = state.get("navigation_history", [])
        if isinstance(saved_history, (list, tuple)):
            self._navigation_history = []
            # Rebuild through the same MRU helper so stale duplicate/blank entries
            # from future/older settings cannot pollute the drop-down. Reverse the
            # saved MRU list because each update inserts at the front.
            for item in reversed(saved_history[:50]):
                self._navigation_history = update_navigation_history(
                    self._navigation_history, str(item), max_items=50
                )
            self._selected_history_query = None
            self._sync_navigation_history_combo()
            self._update_delete_history_button()
        # V0.5.1 intentionally does not restore a stale previous address. Every
        # new application session starts at the MCU SRAM base for a useful first
        # view; navigation history is restored independently for quick reuse.
        self.goto_address(DEFAULT_RAM_BASE)
        self.auto_interval.setValue(int(state.get("auto_interval_ms", 1000) or 1000))
        self.auto_check.setChecked(bool(state.get("auto_refresh", False)))

    def _goto(self) -> None:
        # Go is deterministic: it resolves exactly what is in the editor.
        # Choosing a completion is handled only by QCompleter.activated.
        self._navigate_query(self.address_edit.text(), allow_completion_fallback=False)

    def _address_return_pressed(self) -> None:
        """Handle raw/exact editor Enter without competing with QCompleter.

        When the Symbol completion popup is visible, QCompleter owns Enter and
        emits the exact selected Symbol through ``activated[str]``. We deliberately
        do nothing here so QComboBox history/current-index state cannot run a
        second navigation afterwards. If no completion popup is active, Enter
        resolves the editor text as an exact Symbol or raw address only.
        """
        popup = self._symbol_completer.popup()
        if popup is not None and popup.isVisible():
            return
        self._navigate_query(self.address_edit.text(), allow_completion_fallback=False)

    def _navigate_query(self, query: str, *, allow_completion_fallback: bool = False) -> None:
        text = str(query).strip()
        if not text:
            self.status_label.setText("Address / Symbol is empty")
            return

        # Exact Symbol/member names always win. Symbol navigation preserves the
        # full human-readable path in the editor; raw numeric navigation alone
        # is canonicalized to 0xXXXXXXXX.
        symbol = self._symbol_index.exact_name(text) if self._symbol_index else None
        if symbol is not None:
            self._goto_symbol(symbol, remember=True)
            return

        # ``allow_completion_fallback`` is retained only for source compatibility
        # with older callers. V0.6.8 intentionally never guesses a candidate from
        # popup/current-index state; QCompleter.activated is the single completion
        # commit path.
        _ = allow_completion_fallback

        try:
            address = parse_address(text)
        except Exception as address_error:
            if re.fullmatch(r"(?:0[xX])?[0-9A-Fa-f]+", text):
                self.status_label.setText(str(address_error))
            elif self._symbol_index:
                self.status_label.setText(f"Symbol not found: {text}")
            else:
                self.status_label.setText("No AXF/ELF symbols loaded")
            return

        canonical = f"0x{address:08X}"
        self._last_navigation_kind = "address"
        self._remember_navigation_query(canonical)
        self.goto_address(address, display_text=canonical)

    def eventFilter(self, watched, event):  # noqa: N802
        # Delete remains a keyboard shortcut for the highlighted history row; the
        # primary single-item removal UX is the persistent Delete History button,
        # because a context menu inside a QComboBox popup can disappear on Windows.
        if watched is self._history_popup and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                index = self._history_popup.currentIndex()
                if index.isValid():
                    self._delete_history_row(index.row())
                    event.accept()
                    return True
        return super().eventFilter(watched, event)

    def _history_metadata(self, query: str) -> tuple[str, str]:
        """Resolve display-only history metadata without target I/O."""
        text = str(query).strip()
        if not text:
            return "", ""
        try:
            address = parse_address(text)
        except ValueError:
            symbol = self._symbol_index.exact_name(text)
            if symbol is None:
                return "", ""
            return symbol.type_name or symbol.kind or "", f"0x{symbol.base_address:08X}"

        resolved = self._symbol_index.exact(address) if self._symbol_index else None
        type_text = (resolved.type_name or resolved.kind or "") if resolved is not None else ""
        return type_text, f"0x{address:08X}"

    def _sync_navigation_history_combo(self) -> None:
        current_text = self.address_edit.text()
        self.address_combo.blockSignals(True)
        try:
            self._history_model.removeRows(0, self._history_model.rowCount())
            for query in self._navigation_history:
                type_text, address_text = self._history_metadata(query)
                row = [
                    QStandardItem(query),
                    QStandardItem(type_text),
                    QStandardItem(address_text),
                ]
                for item in row:
                    item.setEditable(False)
                self._history_model.appendRow(row)
            self.address_combo.setCurrentIndex(-1)
            self.address_combo.setEditText(current_text)
            self._auto_fit_popup_columns(self._history_popup, self._history_model, symbol_column=0)
        finally:
            self.address_combo.blockSignals(False)

    def _remember_navigation_query(self, query: str) -> None:
        self._navigation_history = update_navigation_history(
            self._navigation_history, query, max_items=50
        )
        # A newly typed successful query becomes the active history item. This
        # lets the visible Delete History button remove it immediately without
        # requiring the history popup to stay open.
        self._selected_history_query = str(query).strip() or None
        self._sync_navigation_history_combo()
        self._update_delete_history_button()

    def _update_delete_history_button(self) -> None:
        selected = str(self._selected_history_query or "").strip()
        exists = bool(selected) and any(
            str(item).strip().casefold() == selected.casefold()
            for item in self._navigation_history
        )
        self.delete_history_btn.setEnabled(exists)

    def _history_editor_text_edited(self, text: str) -> None:
        # Typing after a history selection must not leave a hidden stale delete
        # target. Enable single-delete only when the editor currently matches an
        # existing history entry; the list is bounded to 50 so this is trivial.
        key = str(text).strip().casefold()
        self._selected_history_query = next(
            (item for item in self._navigation_history if str(item).strip().casefold() == key),
            None,
        ) if key else None
        self._update_delete_history_button()

    def _clear_navigation_history(self) -> None:
        current_text = self.address_edit.text()
        self._navigation_history.clear()
        self._selected_history_query = None
        self._sync_navigation_history_combo()
        self._update_delete_history_button()
        self.address_combo.setEditText(current_text)
        self.status_label.setText("Address / Symbol history cleared")

    def _delete_selected_history(self) -> None:
        query = str(self._selected_history_query or "").strip()
        if not query:
            self.status_label.setText("Select a history item first")
            return
        current_text = self.address_edit.text()
        key = query.casefold()
        self._navigation_history = [
            value for value in self._navigation_history
            if str(value).strip().casefold() != key
        ]
        self._selected_history_query = None
        self._sync_navigation_history_combo()
        self._update_delete_history_button()
        self.address_combo.setEditText(current_text)
        self.status_label.setText(f"History removed: {query}")

    def _delete_history_row(self, row: int) -> None:
        if row < 0 or row >= self._history_model.rowCount():
            return
        item = self._history_model.item(row, 0)
        query = item.text().strip() if item is not None else ""
        if not query:
            return
        current_text = self.address_edit.text()
        key = query.casefold()
        self._navigation_history = [
            value for value in self._navigation_history
            if str(value).strip().casefold() != key
        ]
        if str(self._selected_history_query or "").strip().casefold() == key:
            self._selected_history_query = None
        self._sync_navigation_history_combo()
        self._update_delete_history_button()
        self.address_combo.setEditText(current_text)
        self.status_label.setText(f"History removed: {query}")

    def _show_history_context_menu(self, pos) -> None:
        index = self._history_popup.indexAt(pos)
        if not index.isValid():
            return
        self._history_popup.setCurrentIndex(index)
        menu = QMenu(self._history_popup)
        delete_action = menu.addAction("Delete This History")
        chosen = menu.exec(self._history_popup.viewport().mapToGlobal(pos))
        if chosen is delete_action:
            self._delete_history_row(index.row())

    def _history_activated(self, index: int) -> None:
        # History selection is navigation-only: it must NOT reinsert/move the
        # selected entry in the history list. Keeping order stable makes the
        # dropdown predictable and also gives the visible Delete History button
        # a deterministic item to remove after the popup closes.
        if index < 0 or index >= self._history_model.rowCount():
            return
        item = self._history_model.item(index, 0)
        query = item.text().strip() if item is not None else ""
        if not query:
            return
        self._selected_history_query = query
        self._update_delete_history_button()

        symbol = self._symbol_index.exact_name(query) if self._symbol_index else None
        if symbol is not None:
            self._goto_symbol(symbol, remember=False)
            return
        try:
            address = parse_address(query)
        except ValueError:
            self.status_label.setText(f"History target unavailable: {query}")
            return
        self._last_navigation_kind = "address"
        self.goto_address(address, display_text=f"0x{address:08X}")

    def _auto_fit_popup_columns(self, view: QTreeView, model: QStandardItemModel, *, symbol_column: int = 0) -> None:
        """Fit Symbol/Type/Address popups to full names without per-key work."""
        fm = view.fontMetrics()
        widths = [0] * model.columnCount()
        for col in range(model.columnCount()):
            header = str(model.headerData(col, Qt.Orientation.Horizontal) or "")
            widths[col] = fm.horizontalAdvance(header) + 28
        for row in range(model.rowCount()):
            for col in range(model.columnCount()):
                text = str(model.index(row, col).data() or "")
                widths[col] = max(widths[col], fm.horizontalAdvance(text) + 28)
        if widths:
            # Full Symbol names are prioritized; cap only pathological DWARF names.
            widths[symbol_column] = min(max(widths[symbol_column], 330), 900)
        if len(widths) > 1:
            widths[1] = min(max(widths[1], 100), 180)
        if len(widths) > 2:
            widths[2] = min(max(widths[2], 120), 160)
        total = 36
        for col, width in enumerate(widths):
            view.setColumnWidth(col, width)
            total += width
        view.setMinimumWidth(min(max(total, 620), 1240))

    def _rebuild_symbol_completion_model(self) -> None:
        self._install_symbol_completion_model(self._symbol_index.preferred_symbols())

    def _install_symbol_completion_model(self, symbols) -> None:
        # Build off-view, then swap the complete model once. This avoids thousands
        # of incremental popup invalidations during AXF auto-load while retaining
        # a model-backed, allocation-free-per-keystroke completion path.
        model = QStandardItemModel(0, 3, self)
        model.setHorizontalHeaderLabels(["Symbol", "Type", "Address"])
        for symbol in symbols:
            name_item = QStandardItem(symbol.name)
            type_item = QStandardItem(symbol.type_name or symbol.kind or "")
            address_item = QStandardItem(f"0x{symbol.base_address:08X}")
            for item in (name_item, type_item, address_item):
                item.setEditable(False)
            model.appendRow([name_item, type_item, address_item])
        old_model = self._symbol_completion_model
        self._symbol_completion_model = model
        self._symbol_completer.setModel(model)
        self._auto_fit_popup_columns(self._completion_popup, model, symbol_column=0)
        if old_model is not model:
            old_model.deleteLater()

    def _symbol_completion_activated(self, symbol_name: str) -> None:
        symbol = self._symbol_index.exact_name(symbol_name)
        if symbol is not None:
            self._goto_symbol(symbol, remember=True)

    def _goto_symbol(self, symbol, *, remember: bool = False) -> None:
        if remember:
            self._remember_navigation_query(symbol.name)
        self._last_navigation_kind = "symbol"
        # Exact scalar symbols carry a normalized AXF/DWARF type. Adopt that
        # type immediately so the first Memory frame at the destination is
        # interpreted correctly (e.g. uint8 -> UInt8 instead of Byte/Hex).
        display_type = symbol_display_type(symbol.type_name)
        if display_type is not None:
            self.view.set_display_type(display_type)
        self.goto_address(symbol.base_address, display_text=symbol.name)
        type_text = symbol.type_name or symbol.kind or "unknown"
        self.status_label.setText(
            f"{symbol.name} → 0x{symbol.base_address:08X} | {type_text} | {symbol.size} B"
        )

    def _active_view(self):
        return self.symbol_view if self.view_stack.currentWidget() is self.symbol_view else self.view

    def _effective_view_mode(self) -> str:
        requested = str(self.view_mode_combo.currentData() or "auto")
        if requested in {"raw", "symbols"}:
            return requested
        # Auto is deliberately stable rather than heuristically flipping while
        # scrolling: Symbol/name navigation opens semantic typed rows; explicit
        # numeric-address navigation keeps the classic CE-style raw memory view.
        return "symbols" if self._last_navigation_kind == "symbol" and bool(self._symbol_index) else "raw"

    def _apply_view_mode(self, *, refresh: bool = True) -> None:
        mode = self._effective_view_mode()
        target = self.symbol_view if mode == "symbols" else self.view
        self.view_stack.setCurrentWidget(target)
        if refresh and self._connected:
            target.goto_address(self._current_address)

    def _view_mode_changed(self, _index: int) -> None:
        self._apply_view_mode(refresh=True)

    def _selection_changed(self, text: str) -> None:
        if text:
            self.status_label.setText(text)

    def _edit_requested(self, address: int, type_name: str, raw: bytes) -> None:
        try:
            value = decode_value(raw, type_name)
            current = format_value(value, type_name)
        except Exception:
            current = raw.hex(" ").upper()
        text, ok = QInputDialog.getText(
            self,
            "Edit memory",
            f"0x{address:08X} ({type_name})",
            text=current,
        )
        if not ok:
            return
        try:
            data = encode_value(text, type_name)
        except Exception as exc:
            self.status_label.setText(str(exc))
            return
        # Clicking OK in this edit dialog is the confirmation. Do not show a
        # second confirmation message box; CE-style direct editing must stay fast.
        self.write_requested.emit(address, data)

    def _text_edit_requested(self, address: int, encoding: str, raw: bytes) -> None:
        current = decode_text(raw, encoding)
        if current == ".":
            current = ""
        text, ok = QInputDialog.getText(
            self,
            "Edit memory text",
            f"0x{address:08X} ({encoding}) — 可输入多个字符",
            text=current,
        )
        if not ok:
            return
        try:
            data = encode_text_input(text, encoding)
        except Exception as exc:
            self.status_label.setText(str(exc))
            return
        if data:
            self.write_requested.emit(address, data)

    def _auto_toggled(self, enabled: bool) -> None:
        if enabled and self._connected:
            self._auto_timer.start(self.auto_interval.value())
        else:
            self._auto_timer.stop()

    def _auto_interval_changed(self, value: int) -> None:
        if self._auto_timer.isActive():
            self._auto_timer.start(value)

    def _update_enabled(self) -> None:
        self.go_btn.setEnabled(True)
        self.refresh_btn.setEnabled(self._connected)
        self.auto_check.setEnabled(self._connected)
        self.auto_interval.setEnabled(self._connected)
