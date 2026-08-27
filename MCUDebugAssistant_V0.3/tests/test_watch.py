from core.watch import MemoryReadPlanner, RunningStats, WatchVariableSpec


def test_running_stats():
    s = RunningStats()
    for value in (1, 2, 3, 4):
        s.add(value)
    count, mean, minimum, maximum = s.snapshot()
    assert count == 4
    assert mean == 2.5
    assert minimum == 1
    assert maximum == 4
    s.clear()
    assert s.snapshot() == (0, None, None, None)


def test_read_planner_merges_nearby():
    planner = MemoryReadPlanner(max_gap_bytes=8, max_block_bytes=64)
    variables = [
        WatchVariableSpec(1, "a", 0x20000000, "float"),
        WatchVariableSpec(2, "b", 0x20000004, "uint32"),
        WatchVariableSpec(3, "c", 0x20000100, "uint16"),
    ]
    blocks = planner.plan(variables)
    assert len(blocks) == 2
    assert blocks[0].address == 0x20000000
    assert blocks[0].size == 8
    assert [v.name for v in blocks[0].variables] == ["a", "b"]
    assert blocks[1].address == 0x20000100


def test_read_planner_overlap():
    planner = MemoryReadPlanner(max_gap_bytes=0, max_block_bytes=64)
    variables = [
        WatchVariableSpec(1, "a", 0x20000000, "uint32"),
        WatchVariableSpec(2, "b", 0x20000002, "uint16"),
    ]
    blocks = planner.plan(variables)
    assert len(blocks) == 1
    assert blocks[0].size == 4
