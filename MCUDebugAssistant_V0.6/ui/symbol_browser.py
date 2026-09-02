from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTreeView,
    QVBoxLayout,
)

from symbols.elf_parser import ElfSymbol


ROLE_SEARCH = int(Qt.ItemDataRole.UserRole) + 1
ROLE_ADDABLE = int(Qt.ItemDataRole.UserRole) + 2
ROLE_SYMBOL = int(Qt.ItemDataRole.UserRole) + 3


class _SymbolFilterProxy(QSortFilterProxyModel):
    """Filter an already-built tree instead of rebuilding widgets per keypress."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._needle = ""
        self._addable_only = True
        self.setRecursiveFilteringEnabled(True)
        self.setAutoAcceptChildRows(False)
        self.setDynamicSortFilter(True)

    def set_needle(self, text: str) -> None:
        value = text.strip().lower()
        if value == self._needle:
            return
        self._needle = value
        self.invalidateFilter()

    def set_addable_only(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._addable_only:
            return
        self._addable_only = enabled
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # noqa: N802 (Qt API)
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        search = str(index.data(ROLE_SEARCH) or "").lower()
        addable = bool(index.data(ROLE_ADDABLE))
        if self._needle and self._needle not in search:
            return False
        if self._addable_only and not addable:
            return False
        return True


class SymbolBrowserDialog(QDialog):
    COL_NAME = 0
    COL_TYPE = 1
    COL_SIZE = 2
    COL_ADDRESS = 3
    COL_SELECT = 4
    HEADERS = ["Name", "Type", "Size", "Address", "Select"]

    def __init__(
        self,
        symbols: list[ElfSymbol] | tuple[ElfSymbol, ...],
        parent=None,
        source_path: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Symbols")
        self.resize(1180, 720)
        self._symbols = list(symbols)
        self._source_path = source_path
        self._check_items: list[tuple[QStandardItem, ElfSymbol]] = []

        layout = QVBoxLayout(self)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("变量 / 结构体成员，例如 BlowerParamsObj、m_PosSpeed")
        filter_row.addWidget(self.search_edit, 1)

        self.addable_only = QCheckBox("只显示可加入 Watch 的成员")
        self.addable_only.setChecked(True)
        filter_row.addWidget(self.addable_only)

        self.count_label = QLabel()
        filter_row.addWidget(self.count_label)
        layout.addLayout(filter_row)

        self.model = QStandardItemModel(0, len(self.HEADERS), self)
        self.model.setHorizontalHeaderLabels(self.HEADERS)
        self._build_tree()

        self.proxy = _SymbolFilterProxy(self)
        self.proxy.setSourceModel(self.model)

        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSortingEnabled(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setAnimated(False)
        header = self.tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        self.tree.setColumnWidth(self.COL_NAME, 430)
        self.tree.setColumnWidth(self.COL_TYPE, 280)
        self.tree.setColumnWidth(self.COL_SIZE, 80)
        self.tree.setColumnWidth(self.COL_ADDRESS, 130)
        self.tree.setColumnWidth(self.COL_SELECT, 70)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tree, 1)

        note = QLabel(
            "AXF/ELF 的 DWARF 结构体/数组成员按层级显示；勾选 Select 后按 OK 加入 Watch。"
            "搜索使用模型过滤，不会在每次按键时重建整张表。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._expand_timer = QTimer(self)
        self._expand_timer.setSingleShot(True)
        self._expand_timer.setInterval(70)
        self._expand_timer.timeout.connect(self.tree.expandAll)
        self._filter_was_empty = True

        self.search_edit.textChanged.connect(self._filter_changed)
        self.addable_only.toggled.connect(self._filter_changed)
        self.tree.doubleClicked.connect(self._double_clicked)
        self._filter_changed()
        self.search_edit.setFocus()

    @staticmethod
    def _parent_path(name: str) -> str | None:
        dot = name.rfind(".")
        bracket = name.rfind("[")
        if dot < 0 and bracket < 0:
            return None
        if dot > bracket:
            return name[:dot]
        # Only treat the final [index] as a hierarchy level.
        close = name.find("]", bracket)
        if close == len(name) - 1:
            return name[:bracket]
        return name[:dot] if dot >= 0 else None

    @classmethod
    def _leaf_label(cls, path: str, parent: str | None) -> str:
        if not parent:
            return path
        if path.startswith(parent + "."):
            return path[len(parent) + 1:]
        if path.startswith(parent + "["):
            return path[len(parent):]
        return path

    def _build_tree(self) -> None:
        # Prefer DWARF container descriptions over raw ELF records with the same
        # name/address, then construct any synthetic intermediate array nodes.
        by_name: dict[str, ElfSymbol] = {}
        for sym in self._symbols:
            old = by_name.get(sym.name)
            if old is None:
                by_name[sym.name] = sym
            elif old.kind != "container" and sym.kind == "container":
                by_name[sym.name] = sym
            elif old.source == "ELF symbol" and sym.source != "ELF symbol":
                by_name[sym.name] = sym

        paths: set[str] = set(by_name)
        for name in list(paths):
            p = self._parent_path(name)
            while p:
                paths.add(p)
                p = self._parent_path(p)

        def depth(path: str) -> int:
            n = 0
            p = self._parent_path(path)
            while p:
                n += 1
                p = self._parent_path(p)
            return n

        file_text = str(Path(self._source_path)) if self._source_path else "AXF / ELF"
        file_name = QStandardItem(file_text)
        file_name.setEditable(False)
        file_name.setData(file_text.lower(), ROLE_SEARCH)
        file_name.setData(False, ROLE_ADDABLE)
        file_row = [file_name] + [QStandardItem("") for _ in range(len(self.HEADERS) - 1)]
        self.model.appendRow(file_row)

        rows: dict[str, list[QStandardItem]] = {}
        for path in sorted(paths, key=lambda x: (depth(x), x.lower())):
            parent_path = self._parent_path(path)
            parent_item = rows[parent_path][0] if parent_path in rows else file_name
            sym = by_name.get(path)
            label = self._leaf_label(path, parent_path)

            type_text = sym.type_name if sym and sym.type_name else ""
            size_text = str(sym.size) if sym and sym.size else ""
            addr_text = f"0x{sym.address:08X}" if sym and sym.address >= 0 else ""
            addable = bool(sym and sym.addable)
            scope = sym.scope if sym else ""
            section = sym.section if sym else ""
            source = sym.source if sym else ""
            search_text = f"{path} {type_text} {scope} {section} {source}".lower()

            name_item = QStandardItem(label)
            name_item.setEditable(False)
            name_item.setData(search_text, ROLE_SEARCH)
            name_item.setData(addable, ROLE_ADDABLE)
            if sym is not None:
                name_item.setData(sym, ROLE_SYMBOL)

            type_item = QStandardItem(type_text)
            size_item = QStandardItem(size_text)
            addr_item = QStandardItem(addr_text)
            select_item = QStandardItem("")
            for item in (type_item, size_item, addr_item, select_item):
                item.setEditable(False)

            if addable and sym is not None:
                select_item.setCheckable(True)
                select_item.setCheckState(Qt.CheckState.Unchecked)
                self._check_items.append((select_item, sym))

            row = [name_item, type_item, size_item, addr_item, select_item]
            parent_item.appendRow(row)
            rows[path] = row

        self.tree_root_name = file_name

    def _filter_changed(self, *_args) -> None:
        needle = self.search_edit.text()
        self.proxy.set_addable_only(self.addable_only.isChecked())
        self.proxy.set_needle(needle)

        # Counting a few thousand lightweight symbol records is cheap; unlike the
        # old QTableWidget implementation this does not allocate any row widgets.
        low = needle.strip().lower()
        visible = 0
        for sym in self._symbols:
            if self.addable_only.isChecked() and not sym.addable:
                continue
            hay = f"{sym.name} {sym.type_name or ''} {sym.scope} {sym.section} {sym.source}".lower()
            if low and low not in hay:
                continue
            visible += 1
        self.count_label.setText(f"{visible} / {len(self._symbols)}")

        if low:
            # Expanding thousands of filtered tree indexes on every key event can
            # itself cause visible typing lag. Filter immediately, then coalesce
            # expansion until the user pauses briefly.
            self._expand_timer.start()
            self._filter_was_empty = False
        elif not self._filter_was_empty:
            self._expand_timer.stop()
            self.tree.collapseAll()
            # Keep the file root open so top-level variables are visible.
            root_proxy = self.proxy.mapFromSource(self.model.indexFromItem(self.tree_root_name))
            if root_proxy.isValid():
                self.tree.expand(root_proxy)
            self._filter_was_empty = True

    def _double_clicked(self, proxy_index) -> None:
        if not proxy_index.isValid():
            return
        source_index = self.proxy.mapToSource(proxy_index)
        name_index = self.model.index(source_index.row(), self.COL_NAME, source_index.parent())
        addable = bool(name_index.data(ROLE_ADDABLE))
        if addable:
            select_index = self.model.index(source_index.row(), self.COL_SELECT, source_index.parent())
            item = self.model.itemFromIndex(select_index)
            if item is not None and item.isCheckable():
                item.setCheckState(
                    Qt.CheckState.Unchecked
                    if item.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
        else:
            self.tree.setExpanded(proxy_index, not self.tree.isExpanded(proxy_index))

    def selected_symbols(self) -> list[ElfSymbol]:
        return [
            sym for item, sym in self._check_items
            if item.checkState() == Qt.CheckState.Checked
        ]
