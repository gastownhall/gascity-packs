"""Pin the commit contract on every pack prompt that overrides do-work's `implement`.

do-work's close-source-anchor step fails closed with
missing-implementation-commit when the source-anchor worktree has no
implementation commit. A formula that extends do-work and swaps in its own
`implement` prompt inherits that check, so a prompt that never tells the
implementer to commit fails every drain item even when the code is right
(observed for gstack in the gc v1.5.0 RC build gate).

Only overrides whose `implement` step does the implementation itself are
listed. bmad and superpowers also override `implement`, but as the parent of
child steps that carry the commit instruction, so this contract does not apply
to their `implement` prompt verbatim.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FRAGMENTS = (
    "read `work_dir` from the source anchor",
    'cd "$worktree"',
    "focused commit",
    "commit hash",
    "leave the source anchor open",
)


SINGLE_STEP_IMPLEMENT_FORMULAS = (
    "gstack/formulas/gstack-work.formula.toml",
    "compound-engineering/formulas/compound-work.formula.toml",
)


def implement_overrides() -> dict[Path, Path]:
    """Formula file -> the implement prompt it substitutes into do-work."""
    overrides: dict[Path, Path] = {}
    for rel in SINGLE_STEP_IMPLEMENT_FORMULAS:
        formula = REPO_ROOT / rel
        data = tomllib.loads(formula.read_text(encoding="utf-8"))
        if "do-work" not in (data.get("extends") or []):
            raise AssertionError(f"{rel} no longer extends do-work")
        prompts = [
            step["description_file"]
            for step in data.get("steps") or []
            if step.get("id") == "implement" and step.get("description_file")
        ]
        if len(prompts) != 1:
            raise AssertionError(f"{rel} has no single `implement` override prompt")
        overrides[formula] = (formula.parent / prompts[0]).resolve()
    return overrides


class DoWorkImplementOverrideTests(unittest.TestCase):

    def test_overrides_require_a_focused_worktree_commit(self) -> None:
        for formula, prompt in implement_overrides().items():
            text = prompt.read_text(encoding="utf-8").lower()
            for fragment in REQUIRED_FRAGMENTS:
                with self.subTest(formula=str(formula.relative_to(REPO_ROOT)), fragment=fragment):
                    self.assertIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
