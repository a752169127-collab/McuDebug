from pathlib import Path


def test_worker_write_path_does_not_read_back_verify():
    source = (Path(__file__).resolve().parents[1] / "debugger" / "jlink_worker.py").read_text(encoding="utf-8")
    start = source.index("def write_typed")
    end = source.index("def read_memory_block", start)
    body = source[start:end]
    assert "write_memory(" in body
    assert "write_and_verify(" not in body
    assert "read_memory(" not in body


def test_release_ui_no_longer_claims_write_verify():
    source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "Write + Verify" not in source
    assert "VERIFY=OK" not in source
    assert "Write to target memory and verify?" not in source
