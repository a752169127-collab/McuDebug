from core.test_automation import (
    COMBINATION_CARTESIAN,
    COMBINATION_ZIP,
    PARAMETER_LIST,
    PARAMETER_RANGE,
    ParameterSpec,
    SampleAccumulator,
    StableDetector,
    calculate_value,
    evaluate_assert,
    generate_cases,
    parse_list_values,
    render_value_text,
)


def test_parse_list_values_coerces_numbers_and_strings():
    assert parse_list_values("5000, 6000, CPAP, true") == (5000, 6000, "CPAP", True)


def test_cartesian_parameter_matrix():
    params = [
        ParameterSpec("RPM", PARAMETER_LIST, (5000, 10000)),
        ParameterSpec("Mode", PARAMETER_LIST, ("CPAP", "PSV")),
    ]
    assert generate_cases(params, COMBINATION_CARTESIAN) == [
        {"RPM": 5000, "Mode": "CPAP"},
        {"RPM": 5000, "Mode": "PSV"},
        {"RPM": 10000, "Mode": "CPAP"},
        {"RPM": 10000, "Mode": "PSV"},
    ]


def test_zip_parameter_matrix():
    params = [
        ParameterSpec("RPM", PARAMETER_RANGE, start=5000, end=7000, step=1000),
        ParameterSpec("Target", PARAMETER_LIST, (5, 10, 15)),
    ]
    assert generate_cases(params, COMBINATION_ZIP) == [
        {"RPM": 5000, "Target": 5},
        {"RPM": 6000, "Target": 10},
        {"RPM": 7000, "Target": 15},
    ]


def test_set_parameter_token_is_resolved_without_eval():
    assert render_value_text("${RPM}", {"RPM": 12345}) == "12345"
    assert render_value_text("1000", {"RPM": 12345}) == "1000"


def test_sample_accumulator_statistics():
    acc = SampleAccumulator(["Pressure", "Flow"])
    acc.add({"Pressure": 10.0, "Flow": 20.0})
    acc.add({"Pressure": 12.0, "Flow": 24.0})
    flat = acc.flatten()
    assert flat["Pressure.avg"] == 11.0
    assert flat["Pressure.min"] == 10.0
    assert flat["Pressure.max"] == 12.0
    assert flat["Flow.avg"] == 22.0
    assert flat["Pressure.std"] == 1.0


def test_stable_detector_requires_window_and_hold():
    detector = StableDetector({"Pressure": 0.2, "Flow": 0.5}, window_s=1.0, hold_s=0.5)
    assert detector.add(0.0, {"Pressure": 10.00, "Flow": 20.0}) is False
    assert detector.add(0.5, {"Pressure": 10.05, "Flow": 20.1}) is False
    # Window is now full, hold timer starts.
    assert detector.add(1.0, {"Pressure": 10.08, "Flow": 20.2}) is False
    assert detector.add(1.5, {"Pressure": 10.07, "Flow": 20.1}) is True


def test_stable_detector_resets_hold_on_large_spread():
    detector = StableDetector({"Pressure": 0.2}, window_s=1.0, hold_s=0.5)
    detector.add(0.0, {"Pressure": 10.0})
    detector.add(1.0, {"Pressure": 10.1})
    assert detector.add(1.3, {"Pressure": 10.5}) is False
    assert detector.add(2.4, {"Pressure": 10.52}) is False
    assert detector.add(2.9, {"Pressure": 10.51}) is True


def test_calculate_and_assert_helpers():
    assert round(calculate_value(12.3, "-", 12.5), 6) == -0.2
    assert round(calculate_value(12.0, "percent_error", 10.0), 6) == 20.0
    assert evaluate_assert(0.2, "<=", 0.5)
    assert evaluate_assert(10, "between", 9, 11)
