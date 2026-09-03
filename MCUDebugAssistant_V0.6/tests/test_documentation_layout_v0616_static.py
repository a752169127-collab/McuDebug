from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_root_is_not_filled_with_release_reports():
    assert not list(ROOT.glob("RELEASE_REPORT_V*.md"))
    for name in ["README.md", "START_HERE_FOR_NEW_AI.md", "AGENTS.md", "SKILL.md", "CHANGELOG.md"]:
        assert (ROOT / name).is_file()


def test_documentation_subtrees_and_indexes_exist():
    required = [
        "docs/README.md",
        "docs/releases/README.md",
        "docs/releases/RELEASE_REPORT_V0.6.16.md",
        "docs/state/PROJECT_STATE.yaml",
        "docs/state/LATEST_HANDOFF.md",
        "docs/state/ISSUE_LEDGER.md",
        "docs/state/TEST_STATUS.md",
        "docs/state/VERSION_HISTORY.md",
        "docs/architecture/ADR.md",
        "docs/architecture/ARCHITECTURE.md",
        "docs/architecture/PROJECT_CONTEXT.md",
        "docs/architecture/KNOWN_PITFALLS.md",
        "docs/development/WORKFLOW.md",
        "docs/development/AUTO_UPDATE_CHECKLIST.md",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel


def test_manifest_points_to_existing_canonical_docs():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    current = manifest["current_context_version"]
    assert current.startswith("V0.6.")
    assert (ROOT / "docs" / "releases" / f"RELEASE_REPORT_{current}.md").is_file()
    for key in ["entrypoint", "agent_process", "project_skill", "workflow", "docs_index", "current_state", "latest_handoff", "release_index"]:
        assert (ROOT / manifest[key]).is_file(), (key, manifest[key])


def test_active_entry_docs_use_new_paths_and_do_not_request_full_release_history():
    start = (ROOT / "START_HERE_FOR_NEW_AI.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/state/PROJECT_STATE.yaml" in start
    assert "docs/releases/README.md" in start
    assert "不要默认读取全部历史 Release Report" in start
    assert "docs/development/WORKFLOW.md" in start
    assert "docs/state/PROJECT_STATE.yaml" in agents
    assert "docs/releases/README.md" in agents


def test_ui_title_tracks_manifest_current_version():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    text = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
    assert f"MCU Debug Assistant {manifest['current_context_version']}" in text
