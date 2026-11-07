"""Pins GH#536: the project-lead prompt's rig-scoped dispatch examples must
name formulas that a city with the recommended packs can actually run, with
variable names those formulas actually accept.

`mol-decompose` was never shipped by any pack in this repository — including
the one the docs blamed it on (`gastown`, which ships no formulas at all) —
so a project lead following the example got "formula not found". The
existing `mol-pr-from-issue` example in the same block had its own,
unrelated bug: it passed `--var issue=<N>`, but that formula only accepts
`--var issue_number=<N>` (no alias).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = Path(__file__).resolve().parents[1]
PROMPT = PACK_ROOT / "agents" / "project-lead" / "prompt.template.md"


def test_the_prompt_never_names_the_nonexistent_mol_decompose_formula() -> None:
    text = PROMPT.read_text()
    assert "mol-decompose" not in text, (
        "mol-decompose is not shipped by any pack in this repository; "
        "the dispatch example must not tell a project lead to launch it"
    )


def test_the_prompt_mol_pr_from_issue_example_uses_the_real_variable_name() -> None:
    text = PROMPT.read_text()
    assert "--on mol-pr-from-issue" in text
    # The formula only declares `issue_number`; `issue` has no alias.
    assert "--var issue=" not in text
    assert re.search(r"--on mol-pr-from-issue --var issue_number=", text)


def test_every_formula_the_prompt_dispatches_to_actually_ships_somewhere() -> None:
    text = PROMPT.read_text()
    referenced = set(re.findall(r"--on ([a-zA-Z][\w-]*)", text))
    # The planning formula line uses a placeholder, not a concrete name.
    referenced.discard("<planning-formula>")
    assert referenced, "expected to find at least one --on formula reference"

    shipped = {
        p.stem.removesuffix(".formula")
        for p in REPO_ROOT.glob("*/formulas/*.formula.toml")
    }
    missing = referenced - shipped
    assert not missing, f"prompt dispatches to formulas no pack ships: {missing}"


def test_the_prompt_names_a_real_planning_formula_for_every_methodology_pack() -> None:
    text = PROMPT.read_text()
    for pack, formula in (
        ("compound-engineering", "compound-planning"),
        ("superpowers", "superpowers-planning"),
        ("bmad", "bmad-planning"),
        ("gstack", "gstack-planning"),
    ):
        assert formula in text, f"prompt no longer names {formula}"
        assert (REPO_ROOT / pack / "formulas" / f"{formula}.formula.toml").is_file(), (
            f"{formula} is named in the prompt but {pack} does not ship it"
        )


def test_the_readme_and_pack_toml_blame_real_packs_not_the_formula_less_gastown() -> None:
    # "gastown" legitimately appears elsewhere in these files (e.g. "drop-in
    # pack for existing gastown-style cities") — only the dispatch-formula
    # attribution itself is wrong, since the gastown pack ships no formulas.
    for relpath in ("README.md", "pack.toml"):
        text = (PACK_ROOT / relpath).read_text()
        assert "mol-decompose" not in text
        assert "build-from-decompose" in text
        assert "mol-pr-from-issue" in text
        assert "supplied by a workflow pack (e.g. `gastown`)" not in text
        assert "supplied by a workflow/formula\n# pack (e.g. gastown)" not in text
