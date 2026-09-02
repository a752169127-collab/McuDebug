from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import re
from typing import Iterable, Mapping, Sequence

from core.datatype import get_type_info


PARAMETER_LIST = "list"
PARAMETER_RANGE = "range"
COMBINATION_CARTESIAN = "cartesian"
COMBINATION_ZIP = "zip"
MAX_GENERATED_CASES = 10000

STEP_SET = "SET"
STEP_WAIT = "WAIT"
STEP_WAIT_UNTIL = "WAIT_UNTIL"
STEP_WAIT_STABLE = "WAIT_STABLE"
STEP_SAMPLE = "SAMPLE"
STEP_MANUAL_INPUT = "MANUAL_INPUT"
STEP_CALCULATE = "CALCULATE"
STEP_ASSERT = "ASSERT"
STEP_SAVE_RESULT = "SAVE_RESULT"
SUPPORTED_STEPS = (
    STEP_SET,
    STEP_WAIT,
    STEP_WAIT_UNTIL,
    STEP_WAIT_STABLE,
    STEP_SAMPLE,
    STEP_MANUAL_INPUT,
    STEP_CALCULATE,
    STEP_ASSERT,
    STEP_SAVE_RESULT,
)

_TOKEN_RE = re.compile(r"^\$\{([^{}]+)\}$")


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    source: str
    values: tuple[object, ...] = ()
    start: float | int | None = None
    end: float | int | None = None
    step: float | int | None = None


@dataclass(frozen=True)
class AutomationVariableSpec:
    row_id: int
    name: str
    address: int
    type_name: str
    enabled: bool = True

    @property
    def size(self) -> int:
        return get_type_info(self.type_name).size


def parse_list_values(text: str) -> tuple[object, ...]:
    """Parse a UI list such as ``5000, 6000, CPAP`` without eval()."""
    result: list[object] = []
    for item in str(text).replace("\n", ",").split(","):
        value = item.strip()
        if not value:
            continue
        result.append(_coerce_scalar(value))
    if not result:
        raise ValueError("List parameter requires at least one value")
    return tuple(result)


def _coerce_scalar(text: str) -> object:
    raw = str(text).strip()
    low = raw.casefold()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        if re.fullmatch(r"[-+]?\d+", raw):
            return int(raw, 10)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", raw):
            return float(raw)
    except ValueError:
        pass
    return raw


def expand_parameter(spec: ParameterSpec) -> tuple[object, ...]:
    name = str(spec.name).strip()
    if not name:
        raise ValueError("Parameter name is empty")
    source = str(spec.source).strip().casefold()
    if source == PARAMETER_LIST:
        if not spec.values:
            raise ValueError(f"Parameter '{name}' has no list values")
        return tuple(spec.values)
    if source != PARAMETER_RANGE:
        raise ValueError(f"Unsupported parameter source: {spec.source}")
    if spec.start is None or spec.end is None or spec.step is None:
        raise ValueError(f"Range parameter '{name}' requires start/end/step")
    start = float(spec.start)
    end = float(spec.end)
    step = float(spec.step)
    if not all(math.isfinite(v) for v in (start, end, step)) or step == 0:
        raise ValueError(f"Invalid range for parameter '{name}'")
    if (end - start) * step < 0:
        raise ValueError(f"Range step for '{name}' points away from end")

    values: list[object] = []
    value = start
    epsilon = max(1e-12, abs(step) * 1e-9)
    compare = (lambda x: x <= end + epsilon) if step > 0 else (lambda x: x >= end - epsilon)
    while compare(value):
        if len(values) >= MAX_GENERATED_CASES:
            raise ValueError(f"Range parameter '{name}' exceeds {MAX_GENERATED_CASES} values")
        rounded = round(value, 12)
        if all(float(v).is_integer() for v in (start, end, step)):
            values.append(int(round(rounded)))
        else:
            values.append(rounded)
        value += step
    if not values:
        raise ValueError(f"Range parameter '{name}' generated no values")
    return tuple(values)


def generate_cases(parameters: Sequence[ParameterSpec], mode: str = COMBINATION_CARTESIAN) -> list[dict[str, object]]:
    specs = list(parameters)
    if not specs:
        return [{}]
    names = [str(spec.name).strip() for spec in specs]
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValueError("Parameter names must be unique")
    expanded = [expand_parameter(spec) for spec in specs]
    mode = str(mode).strip().casefold()

    if mode == COMBINATION_ZIP:
        lengths = {len(v) for v in expanded}
        if len(lengths) != 1:
            raise ValueError("Zip combination requires all parameters to have the same number of values")
        total = next(iter(lengths))
        if total > MAX_GENERATED_CASES:
            raise ValueError(f"Generated case count exceeds {MAX_GENERATED_CASES}")
        return [dict(zip(names, (values[i] for values in expanded))) for i in range(total)]

    if mode != COMBINATION_CARTESIAN:
        raise ValueError(f"Unsupported combination mode: {mode}")

    total = 1
    for values in expanded:
        total *= len(values)
        if total > MAX_GENERATED_CASES:
            raise ValueError(f"Generated case count exceeds {MAX_GENERATED_CASES}")

    cases: list[dict[str, object]] = [{}]
    for name, values in zip(names, expanded):
        next_cases: list[dict[str, object]] = []
        for case in cases:
            for value in values:
                item = dict(case)
                item[name] = value
                next_cases.append(item)
        cases = next_cases
    return cases


def resolve_reference(reference: str, context: Mapping[str, object]) -> object:
    text = str(reference).strip()
    match = _TOKEN_RE.fullmatch(text)
    key = match.group(1).strip() if match else text
    if key not in context:
        raise KeyError(f"Unknown test value: {key}")
    return context[key]


def render_value_text(expression: object, context: Mapping[str, object]) -> str:
    """Resolve one SET value without exposing Python/YAML expression execution.

    An exact ``${Name}`` token references a Parameter/measurement value. Everything
    else is treated as a literal string suitable for the existing datatype encoder.
    """
    if isinstance(expression, (int, float)) and not isinstance(expression, bool):
        return str(expression)
    text = str(expression).strip()
    match = _TOKEN_RE.fullmatch(text)
    if match:
        value = resolve_reference(text, context)
        if isinstance(value, bool):
            return "1" if value else "0"
        return str(value)
    return text


class RunningMoments:
    def __init__(self) -> None:
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.minimum = math.inf
        self.maximum = -math.inf

    def add(self, value: float | int) -> None:
        x = float(value)
        if not math.isfinite(x):
            return
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (x - self.mean)
        self.minimum = min(self.minimum, x)
        self.maximum = max(self.maximum, x)

    def snapshot(self) -> dict[str, float | int | None]:
        if self.count <= 0:
            return {"count": 0, "avg": None, "min": None, "max": None, "std": None}
        variance = self.m2 / self.count
        return {
            "count": self.count,
            "avg": self.mean,
            "min": self.minimum,
            "max": self.maximum,
            "std": math.sqrt(max(0.0, variance)),
        }


class SampleAccumulator:
    def __init__(self, names: Iterable[str]) -> None:
        self._stats = {str(name): RunningMoments() for name in names}

    def add(self, values: Mapping[str, float | int]) -> None:
        for name, stats in self._stats.items():
            if name in values:
                stats.add(values[name])

    def snapshot(self) -> dict[str, dict[str, float | int | None]]:
        return {name: stats.snapshot() for name, stats in self._stats.items()}

    def flatten(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for name, stats in self.snapshot().items():
            for metric, value in stats.items():
                result[f"{name}.{metric}"] = value
        return result


class StableDetector:
    """Windowed steady-state detector for one or more MCU signals.

    Each signal uses a Max-Min threshold. ``window_s`` defines the measurement
    window and ``hold_s`` requires the complete set of conditions to remain true
    continuously before the detector reports stable.
    """

    def __init__(
        self,
        thresholds: Mapping[str, float],
        *,
        window_s: float,
        hold_s: float = 0.0,
    ) -> None:
        if not thresholds:
            raise ValueError("StableDetector requires at least one signal")
        self.thresholds = {str(k): abs(float(v)) for k, v in thresholds.items()}
        self.window_s = float(window_s)
        self.hold_s = max(0.0, float(hold_s))
        if self.window_s <= 0 or not math.isfinite(self.window_s):
            raise ValueError("Stable window must be > 0")
        if not all(math.isfinite(v) for v in self.thresholds.values()):
            raise ValueError("Stable thresholds must be finite")
        self._samples = {name: deque() for name in self.thresholds}
        self._stable_since: float | None = None

    def add(self, now_s: float, values: Mapping[str, float | int]) -> bool:
        now = float(now_s)
        for name, queue in self._samples.items():
            if name not in values:
                self._stable_since = None
                return False
            value = float(values[name])
            if not math.isfinite(value):
                self._stable_since = None
                return False
            queue.append((now, value))
            cutoff = now - self.window_s
            while len(queue) > 1 and queue[1][0] <= cutoff:
                queue.popleft()

        stable_now = True
        for name, queue in self._samples.items():
            # A window is valid only after it spans the requested duration. The
            # small 5% allowance avoids timer-jitter turning 2.000 s into 1.999 s.
            if len(queue) < 2 or now - queue[0][0] < self.window_s * 0.95:
                stable_now = False
                break
            values_only = [item[1] for item in queue]
            if max(values_only) - min(values_only) > self.thresholds[name]:
                stable_now = False
                break

        if not stable_now:
            self._stable_since = None
            return False
        if self._stable_since is None:
            self._stable_since = now
        return now - self._stable_since >= self.hold_s

    def spreads(self) -> dict[str, float | None]:
        result: dict[str, float | None] = {}
        for name, queue in self._samples.items():
            if not queue:
                result[name] = None
                continue
            values = [item[1] for item in queue]
            result[name] = max(values) - min(values)
        return result


def calculate_value(left: object, operation: str, right: object | None = None) -> float:
    a = float(left)
    op = str(operation).strip().casefold()
    if op in ("abs", "absolute"):
        return abs(a)
    if right is None:
        raise ValueError(f"Operation '{operation}' requires a right value")
    b = float(right)
    if op in ("+", "add"):
        return a + b
    if op in ("-", "subtract"):
        return a - b
    if op in ("*", "multiply"):
        return a * b
    if op in ("/", "divide"):
        if b == 0:
            raise ZeroDivisionError("Division by zero")
        return a / b
    if op in ("error", "difference"):
        return a - b
    if op in ("percent_error", "%error"):
        if b == 0:
            raise ZeroDivisionError("Percent error reference is zero")
        return (a - b) / b * 100.0
    raise ValueError(f"Unsupported calculation operation: {operation}")


def evaluate_assert(actual: object, operator: str, expected_a: object, expected_b: object | None = None) -> bool:
    a = float(actual)
    op = str(operator).strip().casefold()
    b = float(expected_a)
    if op in ("<", "lt"):
        return a < b
    if op in ("<=", "le"):
        return a <= b
    if op in (">", "gt"):
        return a > b
    if op in (">=", "ge"):
        return a >= b
    if op in ("==", "eq"):
        return a == b
    if op in ("!=", "ne"):
        return a != b
    if op in ("between", "range"):
        if expected_b is None:
            raise ValueError("Between assertion requires lower and upper values")
        c = float(expected_b)
        low, high = sorted((b, c))
        return low <= a <= high
    raise ValueError(f"Unsupported assert operator: {operator}")
