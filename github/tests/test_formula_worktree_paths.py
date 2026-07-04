from __future__ import annotations

import pathlib
import unittest


PACKS_ROOT = pathlib.Path(__file__).resolve().parents[2]


class FormulaWorktreePathTests(unittest.TestCase):
    def test_issue_fix_formulas_create_worktrees_under_gc_context(self) -> None:
        formula_paths = [
            (PACKS_ROOT / "github" / "formulas" / "mol-github-fix-issue.formula.toml", True),
            (PACKS_ROOT / "discord" / "formulas" / "mol-discord-fix-issue.formula.toml", True),
        ]

        for formula_path, removes_worktree in formula_paths:
            with self.subTest(formula=str(formula_path.relative_to(PACKS_ROOT))):
                text = formula_path.read_text(encoding="utf-8")
                self.assertIn('WORKTREE_ROOT="$(pwd)/.gc/worktrees"', text)
                self.assertIn('mkdir -p "$WORKTREE_ROOT"', text)
                self.assertIn('WORKTREE_PATH="$WORKTREE_ROOT/{{issue}}"', text)
                if removes_worktree:
                    self.assertIn('GIT_COMMON_DIR=$(git -C "$WORKTREE" rev-parse --git-common-dir)', text)
                    self.assertIn('CLEANUP_CWD=$(dirname "$GIT_COMMON_DIR")', text)
                    self.assertIn('git --git-dir="$GIT_COMMON_DIR" worktree remove "$WORKTREE" --force', text)
                self.assertNotIn("$(pwd)/worktrees", text)


if __name__ == "__main__":
    unittest.main()
