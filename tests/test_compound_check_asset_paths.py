"""compound-engineering resolves its ralph check gates from pack assets.

`.gc/scripts/checks/` is not populated in a running city, so a formula check
written as `.gc/scripts/checks/<name>.sh` either fails with a hard
`control_dispatch_error` or, when a rig carries a symlinked copy, is
quarantined as "symlink target outside containment". gc resolves the
documented `../assets/scripts/checks/<name>.sh` form at parse time to the
highest-priority formula layer that ships the script (gascity#3834).
compound-engineering ships no check scripts of its own: it imports gascity
(`[imports.gc] source = "../gascity"`), and the gascity layer provides them.
"""

from __future__ import annotations

import os
import tomllib
import unittest
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = REPO_ROOT / "compound-engineering"
GASCITY_CHECKS = REPO_ROOT / "gascity" / "assets" / "scripts" / "checks"
LAYER_PREFIX = "../assets/scripts/checks/"


def walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def check_paths(formula: Path) -> list[str]:
    data = tomllib.loads(formula.read_text(encoding="utf-8"))
    return [
        node["check"]["path"]
        for node in walk(data)
        if isinstance(node.get("check"), dict) and "path" in node["check"]
    ]


class CompoundCheckAssetPathTests(unittest.TestCase):

    def test_pack_imports_gascity_which_ships_the_checks(self) -> None:
        pack = tomllib.loads((PACK / "pack.toml").read_text(encoding="utf-8"))
        sources = [imp.get("source") for imp in (pack.get("imports") or {}).values()]
        self.assertIn("../gascity", sources)
        self.assertFalse((PACK / "assets" / "scripts" / "checks").exists(),
                         "a compound copy of a gascity check would shadow it")

    def test_formula_checks_are_layer_resolved_gascity_assets(self) -> None:
        seen: set[str] = set()
        for formula in sorted((PACK / "formulas").glob("*.formula.toml")):
            text = formula.read_text(encoding="utf-8")
            with self.subTest(formula=formula.name):
                self.assertNotIn(".gc/scripts/checks/", text)
            for path in check_paths(formula):
                with self.subTest(formula=formula.name, path=path):
                    self.assertTrue(path.startswith(LAYER_PREFIX), f"{path!r} is not {LAYER_PREFIX}<name>")
                    script = GASCITY_CHECKS / path.removeprefix(LAYER_PREFIX)
                    self.assertTrue(script.is_file(), f"gascity ships no {script.name}")
                    self.assertTrue(os.access(script, os.X_OK), f"{script} must be executable")
                    seen.add(script.name)
        self.assertEqual(
            seen,
            {"build-artifact-valid.sh", "design-review-approved.sh", "implementation-review-approved.sh"},
        )

    def test_prompts_do_not_send_agents_to_launcher_local_scripts(self) -> None:
        surfaces = [
            path
            for sub_dir in ("assets", "agents", "formulas", "skills")
            if (PACK / sub_dir).is_dir()
            for path in sorted((PACK / sub_dir).rglob("*"))
            if path.is_file() and path.suffix in {".md", ".toml", ".sh", ".py"}
        ]
        self.assertTrue(surfaces)
        for path in surfaces:
            with self.subTest(asset=str(path.relative_to(PACK))):
                self.assertNotIn(".gc/scripts", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
