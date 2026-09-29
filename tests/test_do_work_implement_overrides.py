"""Pin the commit contract on every pack prompt that implements do-work's `implement`.

do-work's close-source-anchor step fails closed with
missing-implementation-commit when the source-anchor worktree has no
implementation commit. A formula that extends do-work and swaps in its own
`implement` prompt inherits that check, so a prompt that never tells the
implementer to commit fails every drain item even when the code is right
(observed for gstack in the gc v1.5.0 RC build gate).

Each entry names the step whose prompt does the implementation itself: the
`implement` override for compound-engineering and the `implement-story` child
of bmad's `implement` loop. superpowers commits in its
record-item-result child step and is covered by its own tests.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FRAGMENTS = (
    "read `work_dir` from the source anchor",
    'cd "$worktree"',
    # Only an explicit instruction to commit satisfies these two; asking to
    # record a "focused commit hash" does not make the implementer commit.
    "make a focused commit in the worktree",
    "`git commit`",
    "commit hash",
    "leave the source anchor open",
)

IMPLEMENTING_STEPS = (
    ("compound-engineering/formulas/compound-work.formula.toml", "implement"),
    ("bmad/formulas/bmad-story-development.formula.toml", "implement-story"),
)

# Steps that may commit follow-up fixes in the same worktree, possibly from a
# different session than the implementer: they must resolve and stay in the
# source-anchor worktree and never commit in the launcher checkout.
FIX_STEPS = (("bmad/formulas/bmad-story-development.formula.toml", "apply-story-findings"),)

FIX_STEP_FRAGMENTS = (
    "read `work_dir` from the source anchor",
    'cd "$worktree"',
    "do not edit, test, or commit in the launcher checkout",
    "`git commit`",
    "commit only when `git status --porcelain` shows changes",
    "never use `git commit --allow-empty`",
)


def iter_steps(steps: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for step in steps:
        yield step
        yield from iter_steps(step.get("children") or [])


def step_prompts(step_refs: tuple[tuple[str, str], ...]) -> dict[str, Path]:
    """Formula file -> the prompt of the named step in that formula."""
    prompts: dict[str, Path] = {}
    for rel, step_id in step_refs:
        formula = REPO_ROOT / rel
        data = tomllib.loads(formula.read_text(encoding="utf-8"))
        if "do-work" not in (data.get("extends") or []):
            raise AssertionError(f"{rel} no longer extends do-work")
        files = [
            step["description_file"]
            for step in iter_steps(data.get("steps") or [])
            if step.get("id") == step_id and step.get("description_file")
        ]
        if len(files) != 1:
            raise AssertionError(f"{rel} has no single {step_id!r} step prompt")
        prompts[rel] = (formula.parent / files[0]).resolve()
    return prompts


class DoWorkImplementOverrideTests(unittest.TestCase):

    def assert_prompts_contain(self, step_refs: tuple[tuple[str, str], ...], fragments: tuple[str, ...]) -> None:
        for rel, prompt in step_prompts(step_refs).items():
            text = " ".join(prompt.read_text(encoding="utf-8").lower().split())
            for fragment in fragments:
                with self.subTest(formula=rel, prompt=prompt.name, fragment=fragment):
                    self.assertIn(fragment, text)

    def test_implementing_prompts_require_a_focused_worktree_commit(self) -> None:
        self.assert_prompts_contain(IMPLEMENTING_STEPS, REQUIRED_FRAGMENTS)

    def test_fix_prompts_commit_only_real_changes_in_the_worktree(self) -> None:
        self.assert_prompts_contain(FIX_STEPS, FIX_STEP_FRAGMENTS)


if __name__ == "__main__":
    unittest.main()
