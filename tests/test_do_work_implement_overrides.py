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

# Only an explicit instruction to commit satisfies these; asking to record a
# "focused commit hash" does not make the implementer create the commit.
COMMIT_INSTRUCTION_FRAGMENTS = (
    "make a focused commit in the worktree",
    "`git commit`",
)

# Prompts that still only ask for a commit hash. Removed by the follow-up PR
# "fix(packs): tell compound and bmad implementers to commit".
MISSING_COMMIT_INSTRUCTION = frozenset(
    {"compound-engineering/formulas/compound-work.formula.toml"}
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
            rel = formula.relative_to(REPO_ROOT).as_posix()
            text = prompt.read_text(encoding="utf-8").lower()
            fragments = REQUIRED_FRAGMENTS
            if rel not in MISSING_COMMIT_INSTRUCTION:
                fragments += COMMIT_INSTRUCTION_FRAGMENTS
            for fragment in fragments:
                with self.subTest(formula=rel, fragment=fragment):
                    self.assertIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
