from __future__ import annotations

import json
import math
import time
from pathlib import Path

from PySide6.QtCore import Qt, QStringListModel, Signal, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QCompleter,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.memory_browser import SymbolIndex
from core.test_automation import (
    AutomationVariableSpec,
    COMBINATION_CARTESIAN,
    COMBINATION_ZIP,
    PARAMETER_LIST,
    PARAMETER_RANGE,
    STEP_ASSERT,
    STEP_CALCULATE,
    STEP_MANUAL_INPUT,
    STEP_SAMPLE,
    STEP_SAVE_RESULT,
    STEP_SET,
    STEP_WAIT,
    STEP_WAIT_UNTIL,
    STEP_WAIT_STABLE,
    SUPPORTED_STEPS,
    ParameterSpec,
    SampleAccumulator,
    StableDetector,
    calculate_value,
    evaluate_assert,
    generate_cases,
    parse_list_values,
    render_value_text,
    resolve_reference,
)


STEP_LABELS = {
    STEP_SET: "Set Variable",
    STEP_WAIT: "Wait",
    STEP_WAIT_UNTIL: "Wait Until",
    STEP_WAIT_STABLE: "Wait Stable",
    STEP_SAMPLE: "Sample / Statistics",
    STEP_MANUAL_INPUT: "Manual Input",
    STEP_CALCULATE: "Calculate",
    STEP_ASSERT: "Assert",
    STEP_SAVE_RESULT: "Save Result",
}

# V0.6.3 keeps the no-code editor intentionally small.  The three V0.6.0
# advanced nodes remain executable for saved-plan compatibility, but they are
# no longer offered when creating a new step.
EDITOR_STEP_KINDS = (
    STEP_SET,
    STEP_WAIT,
    STEP_WAIT_STABLE,
    STEP_SAMPLE,
    STEP_MANUAL_INPUT,
    STEP_SAVE_RESULT,
)


class SymbolLineEdit(QLineEdit):
    def __init__(self, symbols: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(self._completer)
        self.set_symbols(symbols or [])

    def set_symbols(self, symbols: list[str]) -> None:
        self._model.setStringList(list(symbols))


class ParameterDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Parameter")
        self.setMinimumWidth(460)
        data = dict(data or {})
        form = QFormLayout(self)
        self.name_edit = QLineEdit(str(data.get("name", "RPM")))
        self.source_combo = QComboBox()
        self.source_combo.addItem("List", PARAMETER_LIST)
        self.source_combo.addItem("Range", PARAMETER_RANGE)
        self.values_edit = QLineEdit(str(data.get("values", "5000, 6000, 7000")))
        self.start_spin = QDoubleSpinBox()
        self.end_spin = QDoubleSpinBox()
        self.step_spin = QDoubleSpinBox()
        for spin in (self.start_spin, self.end_spin, self.step_spin):
            spin.setRange(-1e12, 1e12)
            spin.setDecimals(6)
        self.start_spin.setValue(float(data.get("start", 5000)))
        self.end_spin.setValue(float(data.get("end", 30000)))
        self.step_spin.setValue(float(data.get("step", 1000)))
        source = str(data.get("source", PARAMETER_LIST))
        idx = self.source_combo.findData(source)
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)
        self.source_combo.currentIndexChanged.connect(self._update_visibility)
        form.addRow("Name", self.name_edit)
        form.addRow("Source", self.source_combo)
        form.addRow("List Values", self.values_edit)
        form.addRow("Range Start", self.start_spin)
        form.addRow("Range End", self.end_spin)
        form.addRow("Range Step", self.step_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._update_visibility()

    def _update_visibility(self) -> None:
        is_list = self.source_combo.currentData() == PARAMETER_LIST
        self.values_edit.setEnabled(is_list)
        for spin in (self.start_spin, self.end_spin, self.step_spin):
            spin.setEnabled(not is_list)

    def value(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "source": self.source_combo.currentData(),
            "values": self.values_edit.text().strip(),
            "start": self.start_spin.value(),
            "end": self.end_spin.value(),
            "step": self.step_spin.value(),
        }


class StepDialog(QDialog):
    def __init__(self, symbols: list[str], parent=None, data: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workflow Step")
        self.resize(620, 520)
        self._symbols = symbols
        self._data = dict(data or {})
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Step Type"))
        self.kind_combo = QComboBox()
        wanted = self._data.get("kind", STEP_SET)
        kinds = list(EDITOR_STEP_KINDS)
        if wanted in SUPPORTED_STEPS and wanted not in kinds:
            # A V0.6.0 saved plan can still be opened/edited without silently
            # converting its legacy advanced node to SET. New plans do not show it.
            kinds.append(wanted)
        for kind in kinds:
            label = STEP_LABELS[kind]
            if kind not in EDITOR_STEP_KINDS:
                label = f"{label} (legacy)"
            self.kind_combo.addItem(label, kind)
        idx = self.kind_combo.findData(wanted)
        if idx >= 0:
            self.kind_combo.setCurrentIndex(idx)
        top.addWidget(self.kind_combo, 1)
        layout.addLayout(top)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        layout.addWidget(self.body, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_checked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.kind_combo.currentIndexChanged.connect(self._build_body)
        self._build_body()

    @staticmethod
    def _clear_layout(layout) -> None:
        """Destroy a dynamic form recursively before rebuilding the step editor.

        V0.6.0 removed only top-level widgets. QFormLayout/QHBoxLayout items were
        left alive, so changing Step Type stacked old labels/editors on top of the
        new form and produced the apparent "garbled font" shown by the user.
        """
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            widget = item.widget()
            if child_layout is not None:
                StepDialog._clear_layout(child_layout)
                child_layout.deleteLater()
            elif widget is not None:
                widget.deleteLater()

    def _clear_body(self) -> None:
        self._clear_layout(self.body_layout)

    def _symbol_edit(self, text: str = "") -> SymbolLineEdit:
        edit = SymbolLineEdit(self._symbols)
        edit.setText(text)
        edit.setPlaceholderText("AXF/DWARF symbol, e.g. Blower.TargetRpm")
        return edit

    @staticmethod
    def _positive_spin(value: float, suffix: str = " s", maximum: float = 3600.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.01, maximum)
        spin.setDecimals(3)
        spin.setValue(float(value))
        spin.setSuffix(suffix)
        return spin

    def _build_body(self) -> None:
        self._clear_body()
        kind = self.kind_combo.currentData()
        data = self._data if self._data.get("kind") == kind else {}
        if kind == STEP_SET:
            form = QFormLayout()
            self.var_edit = self._symbol_edit(str(data.get("variable", "")))
            self.value_edit = QLineEdit(str(data.get("value", "${RPM}")))
            self.value_edit.setPlaceholderText("Literal or ${ParameterName}")
            form.addRow("MCU Variable", self.var_edit)
            form.addRow("Value", self.value_edit)
            self.body_layout.addLayout(form)
        elif kind == STEP_WAIT:
            form = QFormLayout()
            self.duration_spin = self._positive_spin(float(data.get("duration_s", 1.0)))
            form.addRow("Duration", self.duration_spin)
            self.body_layout.addLayout(form)
        elif kind == STEP_WAIT_UNTIL:
            form = QFormLayout()
            self.until_var_edit = self._symbol_edit(str(data.get("variable", "")))
            self.until_op_combo = QComboBox()
            for op in ("<", "<=", ">", ">=", "==", "!=", "between"):
                self.until_op_combo.addItem(op, op)
            ix = self.until_op_combo.findData(str(data.get("operator", "==")))
            if ix >= 0:
                self.until_op_combo.setCurrentIndex(ix)
            self.until_expected_a = QLineEdit(str(data.get("expected_a", "1")))
            self.until_expected_b = QLineEdit(str(data.get("expected_b", "")))
            self.until_interval_spin = QSpinBox()
            self.until_interval_spin.setRange(20, 5000)
            self.until_interval_spin.setValue(int(data.get("interval_ms", 100)))
            self.until_interval_spin.setSuffix(" ms")
            self.until_timeout_spin = self._positive_spin(float(data.get("timeout_s", 10.0)), maximum=86400.0)
            self.until_timeout_action = QComboBox()
            self.until_timeout_action.addItem("Continue + mark TIMEOUT", "continue")
            self.until_timeout_action.addItem("Skip current case", "skip")
            self.until_timeout_action.addItem("Stop run", "stop")
            ix = self.until_timeout_action.findData(str(data.get("on_timeout", "continue")))
            if ix >= 0:
                self.until_timeout_action.setCurrentIndex(ix)
            form.addRow("MCU Variable", self.until_var_edit)
            form.addRow("Operator", self.until_op_combo)
            form.addRow("Expected A", self.until_expected_a)
            form.addRow("Expected B (between)", self.until_expected_b)
            form.addRow("Polling", self.until_interval_spin)
            form.addRow("Timeout", self.until_timeout_spin)
            form.addRow("On Timeout", self.until_timeout_action)
            self.body_layout.addLayout(form)
        elif kind == STEP_WAIT_STABLE:
            self.stable_table = QTableWidget(0, 2)
            self.stable_table.setHorizontalHeaderLabels(["Signal", "Max-Min Threshold"])
            self.stable_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.stable_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            bar = QHBoxLayout()
            add = QPushButton("+ Signal")
            remove = QPushButton("Remove")
            add.clicked.connect(lambda: self._add_stable_row("", 0.2))
            remove.clicked.connect(lambda: self.stable_table.removeRow(self.stable_table.currentRow()) if self.stable_table.currentRow() >= 0 else None)
            bar.addWidget(add)
            bar.addWidget(remove)
            bar.addStretch(1)
            self.body_layout.addWidget(self.stable_table, 1)
            self.body_layout.addLayout(bar)
            conditions = data.get("conditions") or [{"variable": "", "threshold": 0.2}]
            for item in conditions:
                self._add_stable_row(str(item.get("variable", "")), float(item.get("threshold", 0.2)))
            form = QFormLayout()
            self.window_spin = self._positive_spin(float(data.get("window_s", 2.0)))
            self.hold_spin = self._positive_spin(max(0.01, float(data.get("hold_s", 1.0))))
            self.timeout_spin = self._positive_spin(float(data.get("timeout_s", 10.0)), maximum=86400.0)
            self.interval_spin = QSpinBox()
            self.interval_spin.setRange(20, 5000)
            self.interval_spin.setValue(int(data.get("interval_ms", 100)))
            self.interval_spin.setSuffix(" ms")
            self.timeout_action_combo = QComboBox()
            self.timeout_action_combo.addItem("Continue + mark TIMEOUT", "continue")
            self.timeout_action_combo.addItem("Skip current case", "skip")
            self.timeout_action_combo.addItem("Stop run", "stop")
            ix = self.timeout_action_combo.findData(str(data.get("on_timeout", "continue")))
            if ix >= 0:
                self.timeout_action_combo.setCurrentIndex(ix)
            form.addRow("Window", self.window_spin)
            form.addRow("Hold", self.hold_spin)
            form.addRow("Polling", self.interval_spin)
            form.addRow("Timeout", self.timeout_spin)
            form.addRow("On Timeout", self.timeout_action_combo)
            self.body_layout.addLayout(form)
        elif kind == STEP_SAMPLE:
            self.sample_table = QTableWidget(0, 1)
            self.sample_table.setHorizontalHeaderLabels(["Signal"])
            self.sample_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            bar = QHBoxLayout()
            add = QPushButton("+ Signal")
            remove = QPushButton("Remove")
            add.clicked.connect(lambda: self._add_symbol_row(self.sample_table, ""))
            remove.clicked.connect(lambda: self.sample_table.removeRow(self.sample_table.currentRow()) if self.sample_table.currentRow() >= 0 else None)
            bar.addWidget(add)
            bar.addWidget(remove)
            bar.addStretch(1)
            self.body_layout.addWidget(self.sample_table, 1)
            self.body_layout.addLayout(bar)
            variables = data.get("variables") or [""]
            for name in variables:
                self._add_symbol_row(self.sample_table, str(name))
            form = QFormLayout()
            self.sample_duration_spin = self._positive_spin(float(data.get("duration_s", 3.0)))
            self.sample_interval_spin = QSpinBox()
            self.sample_interval_spin.setRange(20, 5000)
            self.sample_interval_spin.setValue(int(data.get("interval_ms", 100)))
            self.sample_interval_spin.setSuffix(" ms")
            statistics = {str(item).casefold() for item in (data.get("statistics") or ["avg", "min", "max"])}
            stats_row = QHBoxLayout()
            self.sample_stat_checks = {}
            for metric, label in (("avg", "Avg"), ("min", "Min"), ("max", "Max"), ("std", "Std")):
                check = QCheckBox(label)
                check.setChecked(metric in statistics)
                self.sample_stat_checks[metric] = check
                stats_row.addWidget(check)
            stats_row.addStretch(1)
            form.addRow("Duration", self.sample_duration_spin)
            form.addRow("Polling", self.sample_interval_spin)
            form.addRow("Result Statistics", stats_row)
            self.body_layout.addLayout(form)
        elif kind == STEP_MANUAL_INPUT:
            self.input_table = QTableWidget(0, 2)
            self.input_table.setHorizontalHeaderLabels(["Field Name", "Unit"])
            self.input_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.input_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            bar = QHBoxLayout()
            add = QPushButton("+ Field")
            remove = QPushButton("Remove")
            add.clicked.connect(lambda: self._add_input_row("", ""))
            remove.clicked.connect(lambda: self.input_table.removeRow(self.input_table.currentRow()) if self.input_table.currentRow() >= 0 else None)
            bar.addWidget(add)
            bar.addWidget(remove)
            bar.addStretch(1)
            self.body_layout.addWidget(self.input_table, 1)
            self.body_layout.addLayout(bar)
            fields = data.get("fields") or [
                {"name": "ExternalPressure", "unit": "cmH2O"},
                {"name": "ExternalFlow", "unit": "L/min"},
            ]
            for item in fields:
                self._add_input_row(str(item.get("name", "")), str(item.get("unit", "")))
        elif kind == STEP_CALCULATE:
            form = QFormLayout()
            self.output_edit = QLineEdit(str(data.get("output", "PressureError")))
            self.left_edit = QLineEdit(str(data.get("left", "Pressure.avg")))
            self.operation_combo = QComboBox()
            for label, op in (("A - B", "-"), ("A + B", "+"), ("A × B", "*"), ("A / B", "/"), ("Percent Error", "percent_error"), ("Absolute A", "abs")):
                self.operation_combo.addItem(label, op)
            ix = self.operation_combo.findData(str(data.get("operation", "-")))
            if ix >= 0:
                self.operation_combo.setCurrentIndex(ix)
            self.right_edit = QLineEdit(str(data.get("right", "ExternalPressure")))
            form.addRow("Output Name", self.output_edit)
            form.addRow("A (result key or ${Parameter})", self.left_edit)
            form.addRow("Operation", self.operation_combo)
            form.addRow("B", self.right_edit)
            self.body_layout.addLayout(form)
        elif kind == STEP_ASSERT:
            form = QFormLayout()
            self.assert_ref_edit = QLineEdit(str(data.get("reference", "PressureError")))
            self.assert_op_combo = QComboBox()
            for op in ("<", "<=", ">", ">=", "==", "!=", "between"):
                self.assert_op_combo.addItem(op, op)
            ix = self.assert_op_combo.findData(str(data.get("operator", "<=")))
            if ix >= 0:
                self.assert_op_combo.setCurrentIndex(ix)
            self.expected_a_edit = QLineEdit(str(data.get("expected_a", "0.5")))
            self.expected_b_edit = QLineEdit(str(data.get("expected_b", "")))
            form.addRow("Result Key", self.assert_ref_edit)
            form.addRow("Operator", self.assert_op_combo)
            form.addRow("Expected A", self.expected_a_edit)
            form.addRow("Expected B (between)", self.expected_b_edit)
            self.body_layout.addLayout(form)
        else:
            self.body_layout.addWidget(QLabel("Save the current case result. The case is also saved automatically at workflow end."))
            self.body_layout.addStretch(1)

    def _add_symbol_row(self, table: QTableWidget, name: str) -> None:
        row = table.rowCount()
        table.insertRow(row)
        table.setCellWidget(row, 0, self._symbol_edit(name))

    def _add_stable_row(self, name: str, threshold: float) -> None:
        row = self.stable_table.rowCount()
        self.stable_table.insertRow(row)
        self.stable_table.setCellWidget(row, 0, self._symbol_edit(name))
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 1e12)
        spin.setDecimals(6)
        spin.setValue(float(threshold))
        self.stable_table.setCellWidget(row, 1, spin)

    def _add_input_row(self, name: str, unit: str) -> None:
        row = self.input_table.rowCount()
        self.input_table.insertRow(row)
        self.input_table.setItem(row, 0, QTableWidgetItem(name))
        self.input_table.setItem(row, 1, QTableWidgetItem(unit))

    def _accept_checked(self) -> None:
        try:
            self.value()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid step", str(exc))
            return
        self.accept()

    def value(self) -> dict:
        kind = self.kind_combo.currentData()
        result: dict = {"kind": kind}
        if kind == STEP_SET:
            variable = self.var_edit.text().strip()
            if not variable:
                raise ValueError("SET variable is empty")
            result.update(variable=variable, value=self.value_edit.text().strip())
        elif kind == STEP_WAIT:
            result["duration_s"] = self.duration_spin.value()
        elif kind == STEP_WAIT_UNTIL:
            variable = self.until_var_edit.text().strip()
            if not variable:
                raise ValueError("WAIT UNTIL variable is empty")
            result.update(
                variable=variable,
                operator=self.until_op_combo.currentData(),
                expected_a=self.until_expected_a.text().strip(),
                expected_b=self.until_expected_b.text().strip(),
                interval_ms=self.until_interval_spin.value(),
                timeout_s=self.until_timeout_spin.value(),
                on_timeout=self.until_timeout_action.currentData(),
            )
        elif kind == STEP_WAIT_STABLE:
            conditions = []
            for row in range(self.stable_table.rowCount()):
                edit = self.stable_table.cellWidget(row, 0)
                spin = self.stable_table.cellWidget(row, 1)
                name = edit.text().strip() if isinstance(edit, QLineEdit) else ""
                if name:
                    conditions.append({"variable": name, "threshold": float(spin.value())})
            if not conditions:
                raise ValueError("WAIT STABLE requires at least one signal")
            result.update(
                conditions=conditions,
                window_s=self.window_spin.value(),
                hold_s=self.hold_spin.value(),
                timeout_s=self.timeout_spin.value(),
                interval_ms=self.interval_spin.value(),
                on_timeout=self.timeout_action_combo.currentData(),
            )
        elif kind == STEP_SAMPLE:
            variables = []
            for row in range(self.sample_table.rowCount()):
                edit = self.sample_table.cellWidget(row, 0)
                name = edit.text().strip() if isinstance(edit, QLineEdit) else ""
                if name:
                    variables.append(name)
            if not variables:
                raise ValueError("SAMPLE requires at least one signal")
            statistics = [metric for metric, check in self.sample_stat_checks.items() if check.isChecked()]
            if not statistics:
                raise ValueError("SAMPLE requires at least one result statistic")
            result.update(
                variables=variables,
                duration_s=self.sample_duration_spin.value(),
                interval_ms=self.sample_interval_spin.value(),
                statistics=statistics,
            )
        elif kind == STEP_MANUAL_INPUT:
            fields = []
            for row in range(self.input_table.rowCount()):
                name_item = self.input_table.item(row, 0)
                unit_item = self.input_table.item(row, 1)
                name = name_item.text().strip() if name_item else ""
                if name:
                    fields.append({"name": name, "unit": unit_item.text().strip() if unit_item else ""})
            if not fields:
                raise ValueError("MANUAL INPUT requires at least one field")
            result["fields"] = fields
        elif kind == STEP_CALCULATE:
            output = self.output_edit.text().strip()
            left = self.left_edit.text().strip()
            if not output or not left:
                raise ValueError("CALCULATE output and A cannot be empty")
            result.update(output=output, left=left, operation=self.operation_combo.currentData(), right=self.right_edit.text().strip())
        elif kind == STEP_ASSERT:
            ref = self.assert_ref_edit.text().strip()
            if not ref:
                raise ValueError("ASSERT result key is empty")
            result.update(
                reference=ref,
                operator=self.assert_op_combo.currentData(),
                expected_a=self.expected_a_edit.text().strip(),
                expected_b=self.expected_b_edit.text().strip(),
            )
        return result


class ManualInputDialog(QDialog):
    ACTION_CONFIRM = "confirm"
    ACTION_SKIP = "skip"
    ACTION_STOP = "stop"

    def __init__(self, fields: list[dict], context: dict[str, object], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("External / Manual Measurement")
        self.setMinimumWidth(460)
        self.action = self.ACTION_STOP
        layout = QVBoxLayout(self)
        info = QLabel("Enter the external instrument values, then confirm to continue to the next workflow step.")
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        self._edits: dict[str, QLineEdit] = {}
        for item in fields:
            name = str(item.get("name", "")).strip()
            unit = str(item.get("unit", "")).strip()
            edit = QLineEdit()
            edit.setPlaceholderText("numeric value")
            self._edits[name] = edit
            form.addRow(f"{name} ({unit})" if unit else name, edit)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        confirm = QPushButton("Confirm / Next")
        skip = QPushButton("Skip Case")
        stop = QPushButton("Stop Run")
        confirm.clicked.connect(self._confirm)
        skip.clicked.connect(self._skip)
        stop.clicked.connect(self._stop)
        buttons.addWidget(stop)
        buttons.addWidget(skip)
        buttons.addStretch(1)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

    def _confirm(self) -> None:
        try:
            self.values()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid measurement", str(exc))
            return
        self.action = self.ACTION_CONFIRM
        self.accept()

    def _skip(self) -> None:
        self.action = self.ACTION_SKIP
        self.accept()

    def _stop(self) -> None:
        self.action = self.ACTION_STOP
        self.reject()

    def values(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for name, edit in self._edits.items():
            text = edit.text().strip()
            if not text:
                raise ValueError(f"{name} is empty")
            value = float(text)
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            values[name] = value
        return values


class TestAutomationPage(QWidget):
    snapshot_requested = Signal(int, object)
    write_requested = Signal(int, object, str, str)
    run_state_changed = Signal(bool)
    log_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connected = False
        self._symbols = SymbolIndex()
        self._symbol_names: list[str] = []
        self._steps: list[dict] = []
        self._request_id = 0
        self._running = False
        self._run_serial = 0
        self._cases: list[dict[str, object]] = []
        self._case_index = -1
        self._step_index = 0
        self._context: dict[str, object] = {}
        self._case_output_keys: list[str] = []
        self._case_status = "PASS"
        self._case_saved = False
        self._pending_kind = ""
        self._pending_request = 0
        self._operation: dict | None = None
        self._results: list[dict[str, object]] = []
        self._result_columns: list[str] = ["Case", "Status"]
        self._build_ui()
        self._install_default_plan()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.plan_name_edit = QLineEdit("Steady-state Calibration Sweep")
        self.plan_name_edit.setMinimumWidth(260)
        open_btn = QPushButton("Open Plan")
        save_btn = QPushButton("Save Plan")
        preview_btn = QPushButton("Preview Cases")
        self.run_btn = QPushButton("Run All")
        self.stop_btn = QPushButton("Stop")
        open_btn.clicked.connect(self._open_plan)
        save_btn.clicked.connect(self._save_plan)
        preview_btn.clicked.connect(self._preview_cases)
        self.run_btn.clicked.connect(self._run_all)
        self.stop_btn.clicked.connect(self.stop_run)
        toolbar.addWidget(QLabel("Plan"))
        toolbar.addWidget(self.plan_name_edit, 1)
        toolbar.addWidget(open_btn)
        toolbar.addWidget(save_btn)
        toolbar.addWidget(preview_btn)
        toolbar.addWidget(self.run_btn)
        toolbar.addWidget(self.stop_btn)
        root.addLayout(toolbar)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._build_parameter_group())
        split.addWidget(self._build_workflow_group())
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 2)

        self.lower_tabs = QTabWidget()
        self.lower_tabs.addTab(self._build_runtime_page(), "Run")
        self.lower_tabs.addTab(self._build_results_page(), "Results")
        root.addWidget(self.lower_tabs, 2)
        self._update_run_buttons()

    def _build_parameter_group(self) -> QWidget:
        box = QGroupBox("Parameter Matrix")
        layout = QVBoxLayout(box)
        self.parameter_table = QTableWidget(0, 3)
        self.parameter_table.setHorizontalHeaderLabels(["Name", "Source", "Values / Range"])
        self.parameter_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.parameter_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.parameter_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.parameter_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.parameter_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.parameter_table.doubleClicked.connect(self._edit_parameter)
        layout.addWidget(self.parameter_table, 1)
        bar = QHBoxLayout()
        add = QPushButton("+ Parameter")
        edit = QPushButton("Edit")
        remove = QPushButton("Remove")
        add.clicked.connect(self._add_parameter)
        edit.clicked.connect(self._edit_parameter)
        remove.clicked.connect(self._remove_parameter)
        bar.addWidget(add)
        bar.addWidget(edit)
        bar.addWidget(remove)
        bar.addStretch(1)
        layout.addLayout(bar)
        form = QFormLayout()
        self.combination_combo = QComboBox()
        self.combination_combo.addItem("Cartesian Product (all combinations)", COMBINATION_CARTESIAN)
        self.combination_combo.addItem("Zip (row-by-row)", COMBINATION_ZIP)
        self.combination_combo.currentIndexChanged.connect(self._update_case_count)
        self.case_count_label = QLabel("1 case")
        form.addRow("Combination", self.combination_combo)
        form.addRow("Generated", self.case_count_label)
        layout.addLayout(form)
        return box

    def _build_workflow_group(self) -> QWidget:
        box = QGroupBox("Workflow")
        layout = QVBoxLayout(box)
        self.step_table = QTableWidget(0, 3)
        self.step_table.setHorizontalHeaderLabels(["#", "Step", "Summary"])
        self.step_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.step_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.step_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.step_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.step_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.step_table.doubleClicked.connect(self._edit_step)
        layout.addWidget(self.step_table, 1)
        bar = QHBoxLayout()
        add = QPushButton("+ Step")
        edit = QPushButton("Edit")
        remove = QPushButton("Remove")
        up = QPushButton("↑")
        down = QPushButton("↓")
        add.clicked.connect(self._add_step)
        edit.clicked.connect(self._edit_step)
        remove.clicked.connect(self._remove_step)
        up.clicked.connect(lambda: self._move_step(-1))
        down.clicked.connect(lambda: self._move_step(1))
        for button in (add, edit, remove, up, down):
            bar.addWidget(button)
        bar.addStretch(1)
        layout.addLayout(bar)
        return box

    def _build_runtime_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.run_case_label = QLabel("Idle")
        self.run_step_label = QLabel("No active step")
        self.run_detail_label = QLabel("")
        self.run_detail_label.setWordWrap(True)
        layout.addWidget(self.run_case_label)
        layout.addWidget(self.run_step_label)
        layout.addWidget(self.run_detail_label)
        self.runtime_table = QTableWidget(0, 2)
        self.runtime_table.setHorizontalHeaderLabels(["Value", "Current"])
        self.runtime_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.runtime_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.runtime_table, 1)
        return page

    def _build_results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        bar = QHBoxLayout()
        self.copy_results_btn = QPushButton("Copy Results")
        self.clear_results_btn = QPushButton("Clear Results")
        self.copy_results_btn.setToolTip("Copy the complete result table as tab-separated text for direct paste into Excel.")
        self.clear_results_btn.setToolTip("Clear all accumulated Test Automation results.")
        self.copy_results_btn.clicked.connect(self._copy_results_to_clipboard)
        self.clear_results_btn.clicked.connect(self._clear_results)
        bar.addWidget(self.copy_results_btn)
        bar.addWidget(self.clear_results_btn)
        bar.addStretch(1)
        layout.addLayout(bar)
        self.results_table = QTableWidget(0, len(self._result_columns))
        self.results_table.setHorizontalHeaderLabels(self._result_columns)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.results_table)
        return page

    # ---------- Symbols / connection ----------
    def set_symbols(self, symbols) -> None:
        self._symbols = SymbolIndex(symbols)
        self._symbol_names = [item.name for item in self._symbols.preferred_symbols() if item.type_name]

    def clear_symbols(self) -> None:
        self._symbols = SymbolIndex()
        self._symbol_names = []

    def set_connected(self, connected: bool) -> None:
        self._connected = bool(connected)
        self._update_run_buttons()

    # ---------- Plan editing ----------
    def _install_default_plan(self) -> None:
        self._set_parameter_rows([
            {"name": "RPM", "source": PARAMETER_RANGE, "values": "", "start": 5000, "end": 30000, "step": 1000},
        ])
        self._steps = [
            {"kind": STEP_SET, "variable": "Blower.TargetRpm", "value": "${RPM}"},
            {"kind": STEP_WAIT_STABLE, "conditions": [
                {"variable": "Pressure", "threshold": 0.2},
                {"variable": "Flow", "threshold": 0.5},
            ], "window_s": 2.0, "hold_s": 1.0, "timeout_s": 10.0, "interval_ms": 100, "on_timeout": "continue"},
            {"kind": STEP_SAMPLE, "variables": ["Pressure", "Flow"], "duration_s": 3.0, "interval_ms": 100, "statistics": ["avg", "min", "max"]},
            {"kind": STEP_MANUAL_INPUT, "fields": [
                {"name": "ExternalPressure", "unit": "cmH2O"},
                {"name": "ExternalFlow", "unit": "L/min"},
            ]},
            {"kind": STEP_SAVE_RESULT},
        ]
        self._refresh_steps()
        self._update_case_count()

    def _parameter_rows(self) -> list[dict]:
        rows: list[dict] = []
        for row in range(self.parameter_table.rowCount()):
            item = self.parameter_table.item(row, 0)
            data = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(data, dict):
                rows.append(dict(data))
        return rows

    def _set_parameter_rows(self, rows: list[dict]) -> None:
        self.parameter_table.setRowCount(0)
        for data in rows:
            self._append_parameter_row(data)
        self._update_case_count()

    def _append_parameter_row(self, data: dict) -> None:
        row = self.parameter_table.rowCount()
        self.parameter_table.insertRow(row)
        name_item = QTableWidgetItem(str(data.get("name", "")))
        name_item.setData(Qt.ItemDataRole.UserRole, dict(data))
        self.parameter_table.setItem(row, 0, name_item)
        source = str(data.get("source", PARAMETER_LIST))
        self.parameter_table.setItem(row, 1, QTableWidgetItem("List" if source == PARAMETER_LIST else "Range"))
        if source == PARAMETER_LIST:
            summary = str(data.get("values", ""))
        else:
            summary = f"{data.get('start', 0):g} → {data.get('end', 0):g} / step {data.get('step', 1):g}"
        self.parameter_table.setItem(row, 2, QTableWidgetItem(summary))

    def _add_parameter(self) -> None:
        dialog = ParameterDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._append_parameter_row(dialog.value())
            self._update_case_count()

    def _edit_parameter(self, *_args) -> None:
        row = self.parameter_table.currentRow()
        if row < 0:
            return
        item = self.parameter_table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item else {}
        dialog = ParameterDialog(self, data if isinstance(data, dict) else {})
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        rows = self._parameter_rows()
        rows[row] = dialog.value()
        self._set_parameter_rows(rows)

    def _remove_parameter(self) -> None:
        row = self.parameter_table.currentRow()
        if row >= 0:
            self.parameter_table.removeRow(row)
            self._update_case_count()

    def _add_step(self) -> None:
        dialog = StepDialog(self._symbol_names, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._steps.append(dialog.value())
            self._refresh_steps(select=len(self._steps) - 1)

    def _edit_step(self, *_args) -> None:
        row = self.step_table.currentRow()
        if not 0 <= row < len(self._steps):
            return
        dialog = StepDialog(self._symbol_names, self, self._steps[row])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._steps[row] = dialog.value()
            self._refresh_steps(select=row)

    def _remove_step(self) -> None:
        row = self.step_table.currentRow()
        if 0 <= row < len(self._steps):
            del self._steps[row]
            self._refresh_steps(select=min(row, len(self._steps) - 1))

    def _move_step(self, delta: int) -> None:
        row = self.step_table.currentRow()
        other = row + int(delta)
        if not 0 <= row < len(self._steps) or not 0 <= other < len(self._steps):
            return
        self._steps[row], self._steps[other] = self._steps[other], self._steps[row]
        self._refresh_steps(select=other)

    def _refresh_steps(self, select: int | None = None) -> None:
        self.step_table.setRowCount(len(self._steps))
        for row, step in enumerate(self._steps):
            self.step_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.step_table.setItem(row, 1, QTableWidgetItem(STEP_LABELS.get(step.get("kind"), str(step.get("kind")))))
            self.step_table.setItem(row, 2, QTableWidgetItem(self._step_summary(step)))
        if select is not None and 0 <= select < len(self._steps):
            self.step_table.selectRow(select)

    @staticmethod
    def _step_summary(step: dict) -> str:
        kind = step.get("kind")
        if kind == STEP_SET:
            return f"{step.get('variable', '')} = {step.get('value', '')}"
        if kind == STEP_WAIT:
            return f"{step.get('duration_s', 0):g} s"
        if kind == STEP_WAIT_UNTIL:
            return f"{step.get('variable', '')} {step.get('operator', '')} {step.get('expected_a', '')} | timeout {step.get('timeout_s', 0):g}s"
        if kind == STEP_WAIT_STABLE:
            names = ", ".join(str(item.get("variable", "")) for item in step.get("conditions", []))
            return f"{names} | window {step.get('window_s', 0):g}s | timeout {step.get('timeout_s', 0):g}s"
        if kind == STEP_SAMPLE:
            stats = "/".join(str(item).upper() for item in (step.get("statistics") or ["avg", "min", "max"]))
            return f"{', '.join(step.get('variables', []))} | {step.get('duration_s', 0):g}s | {stats}"
        if kind == STEP_MANUAL_INPUT:
            return ", ".join(str(item.get("name", "")) for item in step.get("fields", []))
        if kind == STEP_CALCULATE:
            return f"{step.get('output', '')} = {step.get('left', '')} {step.get('operation', '')} {step.get('right', '')}"
        if kind == STEP_ASSERT:
            return f"{step.get('reference', '')} {step.get('operator', '')} {step.get('expected_a', '')}"
        return "Save current case result"

    def _parameter_specs(self) -> list[ParameterSpec]:
        specs: list[ParameterSpec] = []
        for row in self._parameter_rows():
            source = str(row.get("source", PARAMETER_LIST))
            if source == PARAMETER_LIST:
                specs.append(ParameterSpec(str(row.get("name", "")), source, parse_list_values(str(row.get("values", "")))))
            else:
                specs.append(ParameterSpec(
                    str(row.get("name", "")), source,
                    start=float(row.get("start", 0)), end=float(row.get("end", 0)), step=float(row.get("step", 1)),
                ))
        return specs

    def _generate_cases(self) -> list[dict[str, object]]:
        return generate_cases(self._parameter_specs(), self.combination_combo.currentData())

    def _update_case_count(self) -> None:
        try:
            count = len(self._generate_cases())
            self.case_count_label.setText(f"{count} case{'s' if count != 1 else ''}")
            self.case_count_label.setToolTip("")
        except Exception as exc:
            self.case_count_label.setText("Invalid matrix")
            self.case_count_label.setToolTip(str(exc))

    def _preview_cases(self) -> None:
        try:
            cases = self._generate_cases()
        except Exception as exc:
            QMessageBox.warning(self, "Parameter Matrix", str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Generated Cases ({len(cases)})")
        dialog.resize(720, 500)
        layout = QVBoxLayout(dialog)
        names = [spec.name for spec in self._parameter_specs()]
        table = QTableWidget(len(cases), len(names) + 1)
        table.setHorizontalHeaderLabels(["#", *names])
        for row, case in enumerate(cases):
            table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            for col, name in enumerate(names, 1):
                table.setItem(row, col, QTableWidgetItem(str(case.get(name, ""))))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    # ---------- Persistence ----------
    def plan_state(self) -> dict:
        return {
            "schema": 1,
            "name": self.plan_name_edit.text().strip(),
            "combination": self.combination_combo.currentData(),
            "parameters": self._parameter_rows(),
            "steps": [dict(step) for step in self._steps],
        }

    def load_plan_state(self, data: dict) -> None:
        if not isinstance(data, dict):
            raise ValueError("Invalid Test Automation plan")
        self.plan_name_edit.setText(str(data.get("name", "Test Plan")))
        combo = str(data.get("combination", COMBINATION_CARTESIAN))
        idx = self.combination_combo.findData(combo)
        if idx >= 0:
            self.combination_combo.setCurrentIndex(idx)
        self._set_parameter_rows(list(data.get("parameters", [])))
        steps = list(data.get("steps", []))
        self._steps = [dict(step) for step in steps if isinstance(step, dict) and step.get("kind") in SUPPORTED_STEPS]
        self._refresh_steps()
        self._update_case_count()

    def settings_state(self) -> dict:
        return {"plan": self.plan_state()}

    def load_settings_state(self, data: dict) -> None:
        plan = data.get("plan") if isinstance(data, dict) else None
        if isinstance(plan, dict):
            self.load_plan_state(plan)

    def _open_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Test Plan", "", "Test Plan (*.json);;All Files (*)")
        if not path:
            return
        try:
            self.load_plan_state(json.loads(Path(path).read_text(encoding="utf-8")))
            self.log_requested.emit(f"Test plan loaded: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Open plan failed", str(exc))

    def _save_plan(self) -> None:
        default = (self.plan_name_edit.text().strip() or "test_plan").replace(" ", "_") + ".json"
        path, _ = QFileDialog.getSaveFileName(self, "Save Test Plan", default, "Test Plan (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self.plan_state(), ensure_ascii=False, indent=2), encoding="utf-8")
            self.log_requested.emit(f"Test plan saved: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save plan failed", str(exc))

    # ---------- Execution ----------
    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _run_all(self) -> None:
        if self._running:
            return
        if not self._connected:
            QMessageBox.warning(self, "Test Automation", "Connect the target before running a test plan.")
            return
        if not self._symbol_names:
            QMessageBox.warning(self, "Test Automation", "Load AXF/ELF symbols before running a symbol-based test plan.")
            return
        if not self._steps:
            QMessageBox.warning(self, "Test Automation", "Workflow has no steps.")
            return
        try:
            self._cases = self._generate_cases()
            self._validate_workflow_symbols()
        except Exception as exc:
            QMessageBox.warning(self, "Test Automation", str(exc))
            return
        self._running = True
        self.lower_tabs.setCurrentIndex(0)
        self._run_serial += 1
        self._case_index = -1
        # V0.6.3 result history is intentionally cumulative across runs.
        # Users clear it explicitly from the Results tab when they want a fresh table.
        self.run_state_changed.emit(True)
        self.log_requested.emit(f"TEST RUN START: {self.plan_name_edit.text().strip()} | {len(self._cases)} cases")
        self._update_run_buttons()
        QTimer.singleShot(0, self._start_next_case)

    def stop_run(self) -> None:
        if not self._running:
            return
        self._running = False
        self._run_serial += 1
        self._pending_kind = ""
        self._pending_request = 0
        self._operation = None
        self.run_state_changed.emit(False)
        self.run_case_label.setText("Stopped")
        self.run_step_label.setText("No active step")
        self.run_detail_label.setText("")
        self._update_run_buttons()
        self.log_requested.emit("TEST RUN STOP")

    def _update_run_buttons(self) -> None:
        self.run_btn.setEnabled(self._connected and not self._running)
        self.stop_btn.setEnabled(self._running)
        if hasattr(self, "copy_results_btn"):
            self.copy_results_btn.setEnabled(bool(self._results))
        if hasattr(self, "clear_results_btn"):
            self.clear_results_btn.setEnabled(bool(self._results) and not self._running)

    def _start_next_case(self) -> None:
        if not self._running:
            return
        self._case_index += 1
        if self._case_index >= len(self._cases):
            self._running = False
            self.run_state_changed.emit(False)
            self.run_case_label.setText(f"Completed {len(self._cases)} cases")
            self.run_step_label.setText("Done — see Results")
            self.run_detail_label.setText("")
            self.runtime_table.setRowCount(0)
            self.lower_tabs.setCurrentIndex(1)
            self._update_run_buttons()
            self.log_requested.emit(f"TEST RUN COMPLETE: {len(self._cases)} cases")
            return
        case = dict(self._cases[self._case_index])
        self._context = dict(case)
        self._case_output_keys = list(case.keys())
        self._case_status = "PASS"
        self._case_saved = False
        self._step_index = 0
        self._operation = None
        self.run_case_label.setText(f"Case {self._case_index + 1} / {len(self._cases)} | " + ", ".join(f"{k}={v}" for k, v in case.items()))
        self._refresh_runtime_table()
        self._advance()

    def _advance(self) -> None:
        if not self._running:
            return
        if self._step_index >= len(self._steps):
            self._finish_case(self._case_status)
            return
        step = self._steps[self._step_index]
        kind = step.get("kind")
        self.step_table.selectRow(self._step_index)
        self.run_step_label.setText(f"Step {self._step_index + 1}: {STEP_LABELS.get(kind, kind)}")
        self.run_detail_label.setText(self._step_summary(step))
        try:
            if kind == STEP_SET:
                self._execute_set(step)
            elif kind == STEP_WAIT:
                serial = self._run_serial
                delay_ms = max(1, int(float(step.get("duration_s", 0)) * 1000))
                QTimer.singleShot(delay_ms, lambda s=serial: self._complete_timed_step(s))
            elif kind == STEP_WAIT_UNTIL:
                self._execute_wait_until(step)
            elif kind == STEP_WAIT_STABLE:
                self._execute_wait_stable(step)
            elif kind == STEP_SAMPLE:
                self._execute_sample(step)
            elif kind == STEP_MANUAL_INPUT:
                self._execute_manual_input(step)
            elif kind == STEP_CALCULATE:
                self._execute_calculate(step)
                self._complete_step()
            elif kind == STEP_ASSERT:
                self._execute_assert(step)
                self._complete_step()
            elif kind == STEP_SAVE_RESULT:
                self._save_current_case_snapshot()
                self._complete_step()
            else:
                raise ValueError(f"Unsupported workflow step: {kind}")
        except Exception as exc:
            self._fail_run(f"Step {self._step_index + 1} failed: {exc}")

    def _complete_timed_step(self, serial: int) -> None:
        if self._running and serial == self._run_serial:
            self._complete_step()

    def _complete_step(self) -> None:
        if not self._running:
            return
        self._step_index += 1
        self._operation = None
        self._refresh_runtime_table()
        QTimer.singleShot(0, self._advance)

    def _execute_set(self, step: dict) -> None:
        resolved = self._resolve_symbol(str(step.get("variable", "")))
        value_text = render_value_text(step.get("value", ""), self._context)
        request_id = self._next_request_id()
        self._pending_kind = "set"
        self._pending_request = request_id
        self._operation = {"variable": resolved.name, "value_text": value_text}
        self.write_requested.emit(request_id, resolved.base_address, resolved.type_name, value_text)

    def _execute_wait_until(self, step: dict) -> None:
        resolved = self._resolve_symbol(str(step.get("variable", "")))
        specs = self._make_specs([resolved.name])
        self._operation = {
            "mode": "until",
            "specs": specs,
            "variable": resolved.name,
            "operator": str(step.get("operator", "==")),
            "expected_a": step.get("expected_a", "1"),
            "expected_b": step.get("expected_b", ""),
            "started": time.monotonic(),
            "timeout_s": float(step.get("timeout_s", 10.0)),
            "interval_ms": int(step.get("interval_ms", 100)),
            "on_timeout": str(step.get("on_timeout", "continue")),
        }
        self._request_operation_snapshot()

    def _execute_wait_stable(self, step: dict) -> None:
        thresholds: dict[str, float] = {}
        names: list[str] = []
        for item in step.get("conditions", []):
            resolved = self._resolve_symbol(str(item.get("variable", "")))
            names.append(resolved.name)
            thresholds[resolved.name] = float(item.get("threshold", 0))
        specs = self._make_specs(names)
        now = time.monotonic()
        self._operation = {
            "mode": "stable",
            "specs": specs,
            "detector": StableDetector(thresholds, window_s=float(step.get("window_s", 2.0)), hold_s=float(step.get("hold_s", 1.0))),
            "started": now,
            "timeout_s": float(step.get("timeout_s", 10.0)),
            "interval_ms": int(step.get("interval_ms", 100)),
            "on_timeout": str(step.get("on_timeout", "continue")),
        }
        self._request_operation_snapshot()

    def _execute_sample(self, step: dict) -> None:
        names = [self._resolve_symbol(str(name)).name for name in step.get("variables", [])]
        specs = self._make_specs(names)
        self._operation = {
            "mode": "sample",
            "specs": specs,
            "accumulator": SampleAccumulator(names),
            "started": time.monotonic(),
            "duration_s": float(step.get("duration_s", 3.0)),
            "interval_ms": int(step.get("interval_ms", 100)),
            "statistics": [str(metric).casefold() for metric in (step.get("statistics") or ["avg", "min", "max"]) if str(metric).casefold() in {"avg", "min", "max", "std"}],
        }
        self._request_operation_snapshot()

    def _execute_manual_input(self, step: dict) -> None:
        dialog = ManualInputDialog(list(step.get("fields", [])), self._context, self)
        dialog.exec()
        if dialog.action == ManualInputDialog.ACTION_CONFIRM:
            values = dialog.values()
            self._context.update(values)
            for key in values:
                self._register_case_output(key)
            self._complete_step()
        elif dialog.action == ManualInputDialog.ACTION_SKIP:
            self._finish_case("SKIP")
        else:
            self.stop_run()

    def _operand(self, text: object) -> object:
        raw = str(text).strip()
        if not raw:
            raise ValueError("Calculation/assert operand is empty")
        if raw.startswith("${") and raw.endswith("}"):
            return resolve_reference(raw, self._context)
        if raw in self._context:
            return self._context[raw]
        try:
            return float(raw)
        except ValueError as exc:
            raise KeyError(f"Unknown result/parameter key: {raw}") from exc

    def _execute_calculate(self, step: dict) -> None:
        left = self._operand(step.get("left", ""))
        operation = str(step.get("operation", "-"))
        right = None if operation == "abs" else self._operand(step.get("right", ""))
        value = calculate_value(left, operation, right)
        output = str(step.get("output", "Result"))
        self._context[output] = value
        self._register_case_output(output)

    def _execute_assert(self, step: dict) -> None:
        ref = str(step.get("reference", "")).strip()
        actual = self._operand(ref)
        expected_a = self._operand(step.get("expected_a", ""))
        operator = str(step.get("operator", "<="))
        expected_b = self._operand(step.get("expected_b", "")) if operator == "between" else None
        passed = evaluate_assert(actual, operator, expected_a, expected_b)
        assert_key = f"ASSERT {ref}"
        self._context[assert_key] = "PASS" if passed else "FAIL"
        self._register_case_output(assert_key)
        if not passed:
            self._case_status = "FAIL"

    def _request_operation_snapshot(self) -> None:
        if not self._running or not self._operation:
            return
        request_id = self._next_request_id()
        self._pending_kind = str(self._operation.get("mode", "snapshot"))
        self._pending_request = request_id
        self.snapshot_requested.emit(request_id, self._operation["specs"])

    def handle_write_done(self, request_id: int, ok: bool, result, error: str) -> None:
        if not self._running or request_id != self._pending_request or self._pending_kind != "set":
            return
        self._pending_request = 0
        self._pending_kind = ""
        if not ok:
            self._fail_run(f"SET write failed: {error}")
            return
        variable = str((self._operation or {}).get("variable", ""))
        self._context[f"SET {variable}"] = result.get("value") if isinstance(result, dict) else "OK"
        self._complete_step()

    def handle_snapshot_done(self, request_id: int, ok: bool, rows, error: str) -> None:
        if not self._running or request_id != self._pending_request or self._pending_kind not in ("until", "stable", "sample"):
            return
        self._pending_request = 0
        mode = self._pending_kind
        self._pending_kind = ""
        if not ok:
            self._fail_run(f"Automation read failed: {error}")
            return
        values = {str(row.get("name")): row.get("value") for row in rows if isinstance(row, dict)}
        now = time.monotonic()
        if not self._operation:
            return
        if mode == "until":
            variable = str(self._operation["variable"])
            if variable not in values:
                self._fail_run(f"WAIT UNTIL snapshot missing {variable}")
                return
            self._context[f"{variable}.current"] = values[variable]
            elapsed = now - float(self._operation["started"])
            try:
                expected_a = self._operand(self._operation["expected_a"])
                operator = str(self._operation["operator"])
                expected_b = self._operand(self._operation["expected_b"]) if operator == "between" else None
                matched = evaluate_assert(values[variable], operator, expected_a, expected_b)
            except Exception as exc:
                self._fail_run(f"WAIT UNTIL condition error: {exc}")
                return
            self.run_detail_label.setText(f"{variable}={values[variable]} | elapsed={elapsed:.2f}s")
            self._refresh_runtime_table()
            if matched:
                self._context["WaitUntilTime"] = elapsed
                self._complete_step()
                return
            if elapsed >= float(self._operation["timeout_s"]):
                self._context["WaitUntilStatus"] = "TIMEOUT"
                self._case_status = "TIMEOUT" if self._case_status == "PASS" else self._case_status
                action = str(self._operation.get("on_timeout", "continue"))
                if action == "continue":
                    self._complete_step()
                elif action == "skip":
                    self._finish_case("TIMEOUT")
                else:
                    self._fail_run("WAIT UNTIL timeout")
                return
            self._schedule_next_snapshot(int(self._operation["interval_ms"]))
        elif mode == "stable":
            detector: StableDetector = self._operation["detector"]
            stable = detector.add(now, values)
            spreads = detector.spreads()
            for name, value in values.items():
                self._context[f"{name}.current"] = value
            for name, spread in spreads.items():
                self._context[f"{name}.stable_spread"] = spread
            elapsed = now - float(self._operation["started"])
            self.run_detail_label.setText(
                " | ".join(f"{name} Δ={spread:.6g}" if spread is not None else f"{name} Δ=-" for name, spread in spreads.items())
                + f" | elapsed={elapsed:.2f}s"
            )
            self._refresh_runtime_table()
            if stable:
                self._context["StableTime"] = elapsed
                self._complete_step()
                return
            if elapsed >= float(self._operation["timeout_s"]):
                self._context["StableStatus"] = "TIMEOUT"
                self._case_status = "TIMEOUT" if self._case_status == "PASS" else self._case_status
                action = str(self._operation.get("on_timeout", "continue"))
                if action == "continue":
                    self._complete_step()
                elif action == "skip":
                    self._finish_case("TIMEOUT")
                else:
                    self._fail_run("WAIT STABLE timeout")
                return
            self._schedule_next_snapshot(int(self._operation["interval_ms"]))
        else:
            accumulator: SampleAccumulator = self._operation["accumulator"]
            accumulator.add(values)
            elapsed = now - float(self._operation["started"])
            self.run_detail_label.setText(f"Sampling {elapsed:.2f} / {float(self._operation['duration_s']):.2f} s")
            if elapsed >= float(self._operation["duration_s"]):
                all_stats = accumulator.flatten()
                self._context.update(all_stats)
                statistics = self._operation.get("statistics") or ["avg", "min", "max"]
                for name in (spec.name for spec in self._operation.get("specs", [])):
                    for metric in statistics:
                        self._register_case_output(f"{name}.{metric}")
                self._complete_step()
                return
            self._schedule_next_snapshot(int(self._operation["interval_ms"]))

    def _schedule_next_snapshot(self, interval_ms: int) -> None:
        serial = self._run_serial
        QTimer.singleShot(max(20, int(interval_ms)), lambda s=serial: self._snapshot_timer(s))

    def _snapshot_timer(self, serial: int) -> None:
        if self._running and serial == self._run_serial and self._operation and not self._pending_request:
            self._request_operation_snapshot()

    def _resolve_symbol(self, name: str):
        text = str(name).strip()
        resolved = self._symbols.exact_name(text)
        if resolved is None:
            raise ValueError(f"Symbol not found: {text}")
        if not resolved.type_name:
            raise ValueError(f"Symbol has no scalar datatype: {resolved.name}")
        return resolved

    def _make_specs(self, names: list[str]) -> list[AutomationVariableSpec]:
        specs: list[AutomationVariableSpec] = []
        seen: set[str] = set()
        for name in names:
            resolved = self._resolve_symbol(name)
            if resolved.name.casefold() in seen:
                continue
            seen.add(resolved.name.casefold())
            specs.append(AutomationVariableSpec(len(specs) + 1, resolved.name, resolved.base_address, resolved.type_name, True))
        return specs

    def _validate_workflow_symbols(self) -> None:
        for index, step in enumerate(self._steps, 1):
            kind = step.get("kind")
            names: list[str] = []
            if kind == STEP_SET:
                names = [str(step.get("variable", ""))]
            elif kind == STEP_WAIT_UNTIL:
                names = [str(step.get("variable", ""))]
            elif kind == STEP_WAIT_STABLE:
                names = [str(item.get("variable", "")) for item in step.get("conditions", [])]
            elif kind == STEP_SAMPLE:
                names = [str(item) for item in step.get("variables", [])]
            for name in names:
                try:
                    self._resolve_symbol(name)
                except Exception as exc:
                    raise ValueError(f"Step {index}: {exc}") from exc

    def _fail_run(self, message: str) -> None:
        self.log_requested.emit(f"TEST ERROR: {message}")
        QMessageBox.critical(self, "Test Automation", message)
        self.stop_run()

    def _register_case_output(self, key: str) -> None:
        name = str(key)
        if name and name not in self._case_output_keys:
            self._case_output_keys.append(name)

    def _save_current_case_snapshot(self) -> None:
        # The final case record is still written at workflow completion. This
        # marker exists so a no-code workflow can explicitly communicate intent.
        self._context["SaveResult"] = "OK"

    def _finish_case(self, status: str) -> None:
        if not self._running:
            return
        record: dict[str, object] = {"Case": self._case_index + 1, "Status": status}
        for key in self._case_output_keys:
            value = self._context.get(key, "")
            if isinstance(value, (str, int, float, bool)) or value is None:
                record[str(key)] = value
        self._append_result(record)
        self.log_requested.emit(f"TEST CASE {self._case_index + 1}: {status}")
        serial = self._run_serial
        QTimer.singleShot(0, lambda s=serial: self._next_case_timer(s))

    def _next_case_timer(self, serial: int) -> None:
        if self._running and serial == self._run_serial:
            self._start_next_case()

    def _append_result(self, record: dict[str, object]) -> None:
        self._results.append(dict(record))
        for key in record:
            if key not in self._result_columns:
                self._result_columns.append(key)
        self.results_table.setColumnCount(len(self._result_columns))
        self.results_table.setHorizontalHeaderLabels(self._result_columns)
        self.results_table.setRowCount(len(self._results))
        row = len(self._results) - 1
        for col, key in enumerate(self._result_columns):
            value = record.get(key, "")
            if isinstance(value, float):
                text = f"{value:.9g}"
            else:
                text = str(value)
            self.results_table.setItem(row, col, QTableWidgetItem(text))
        self.results_table.scrollToBottom()
        self._update_run_buttons()

    def _refresh_runtime_table(self) -> None:
        items = sorted(self._context.items(), key=lambda item: item[0].casefold())
        self.runtime_table.setRowCount(len(items))
        for row, (key, value) in enumerate(items):
            self.runtime_table.setItem(row, 0, QTableWidgetItem(str(key)))
            if isinstance(value, float):
                text = f"{value:.9g}"
            else:
                text = str(value)
            self.runtime_table.setItem(row, 1, QTableWidgetItem(text))

    @staticmethod
    def _format_result_value(value: object) -> str:
        if isinstance(value, float):
            return f"{value:.9g}"
        if value is None:
            return ""
        return str(value)

    def _copy_results_to_clipboard(self) -> None:
        if not self._results:
            QMessageBox.information(self, "Copy Results", "No test results to copy.")
            return
        lines = ["\t".join(self._result_columns)]
        for record in self._results:
            lines.append("\t".join(self._format_result_value(record.get(key, "")) for key in self._result_columns))
        QApplication.clipboard().setText("\n".join(lines))
        self.log_requested.emit(f"Test results copied to clipboard: {len(self._results)} rows")

    def _clear_results(self) -> None:
        if not self._results:
            return
        answer = QMessageBox.question(
            self,
            "Clear Results",
            "Clear all accumulated test results?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._results.clear()
        self._result_columns = ["Case", "Status"]
        self.results_table.clearContents()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(len(self._result_columns))
        self.results_table.setHorizontalHeaderLabels(self._result_columns)
        self._update_run_buttons()
        self.log_requested.emit("Test results cleared")
