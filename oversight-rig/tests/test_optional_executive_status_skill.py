from __future__ import annotations

from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PACK_ROOT / "skills" / "city-executive-status"

EXPECTED_SKILL_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    "assets/executive-status.env.example",
    "assets/orders/request-status-updates.toml",
    "assets/orders/sync-status-brief.toml",
    "assets/status-input-template.md",
    "references/configuration.md",
    "scripts/executive_status_sync.py",
    "scripts/request_status_updates.py",
    "tests/test_end_to_end.py",
    "tests/test_executive_status_sync.py",
    "tests/test_request_status_updates.py",
    "tests/test_skill_package.py",
}
MACHINE_HOME_PREFIX = "/".join(("", "home", ""))


def test_pack_ships_complete_executive_status_skill() -> None:
    packaged_files = {
        path.relative_to(SKILL_ROOT).as_posix()
        for path in SKILL_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }

    assert packaged_files == EXPECTED_SKILL_FILES


def test_executive_status_examples_are_not_active_pack_orders() -> None:
    active_orders = {path.name for path in (PACK_ROOT / "orders").glob("*.toml")}

    assert active_orders == {
        "escalate-rollups.toml",
        "patrol-project-leads.toml",
    }
    assert (SKILL_ROOT / "assets/orders/request-status-updates.toml").is_file()
    assert (SKILL_ROOT / "assets/orders/sync-status-brief.toml").is_file()


def test_packaged_skill_contains_no_machine_specific_home_paths() -> None:
    offending_files = []
    for path in SKILL_ROOT.rglob("*"):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and MACHINE_HOME_PREFIX in path.read_text(encoding="utf-8")
        ):
            offending_files.append(path.relative_to(SKILL_ROOT).as_posix())

    assert offending_files == []
