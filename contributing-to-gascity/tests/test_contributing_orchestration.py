from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
UMBRELLA = SKILLS / "orchestrate-contribution" / "SKILL.md"
ENTRY = SKILLS / "start-contribution" / "SKILL.md"


class OrchestrationSkillExistsTests(unittest.TestCase):
    """The mayor-mode umbrella and the contributor entry router both exist as
    skills — the two map-level skills the lifecycle is split across."""

    def test_umbrella_skill_exists(self) -> None:
        self.assertTrue(
            UMBRELLA.is_file(),
            "orchestrate-contribution/SKILL.md (the mayor umbrella) must exist",
        )

    def test_entry_router_skill_exists(self) -> None:
        self.assertTrue(
            ENTRY.is_file(),
            "start-contribution/SKILL.md (the GATE 0 entry router) must exist",
        )


class UmbrellaWalksTheFourGatesTests(unittest.TestCase):
    """The umbrella's whole job is to walk GATE 0 -> find-work/write-issue ->
    plan -> fine-tune, pausing at each of the four human gates."""

    def test_umbrella_names_all_four_gates(self) -> None:
        text = UMBRELLA.read_text(encoding="utf-8")
        for gate in ("GATE 0", "GATE 1", "GATE 2", "GATE 3"):
            self.assertIn(gate, text, f"umbrella must name {gate}")

    def test_umbrella_dispatches_the_per_step_formulas(self) -> None:
        text = UMBRELLA.read_text(encoding="utf-8")
        for formula in (
            "mol-contributing-find-work",
            "mol-contributing-plan-implementation",
            "mol-contributing-fine-tune",
        ):
            self.assertIn(formula, text, f"umbrella must dispatch {formula}")


class UmbrellaSingleSourceOfTruthTests(unittest.TestCase):
    """The umbrella REUSES start-contribution's GATE 0 branch logic rather than
    restating it — the entry skill stays the single source of truth for the map."""

    def test_umbrella_references_the_entry_skill(self) -> None:
        text = UMBRELLA.read_text(encoding="utf-8")
        self.assertIn(
            "start-contribution",
            text,
            "umbrella must reference the start-contribution entry skill",
        )

    def test_umbrella_states_it_does_not_restate_the_branch_logic(self) -> None:
        text = UMBRELLA.read_text(encoding="utf-8")
        self.assertIn(
            "restating",
            text,
            "umbrella must state it reuses GATE 0 branch logic rather than restating it",
        )


class UmbrellaStopGuardTests(unittest.TestCase):
    """Load-bearing safety contract: the mayor loop never auto-pushes, never
    opens a PR, and never auto-implements — gates 2/3 and the final stop hold."""

    def test_umbrella_declares_the_no_push_no_pr_no_implement_guards(self) -> None:
        text = UMBRELLA.read_text(encoding="utf-8")
        self.assertIn("gh pr create", text, "umbrella must name the no-PR guard")
        self.assertIn("auto-push", text, "umbrella must name the no-push guard")
        self.assertIn(
            "auto-implement",
            text,
            "umbrella must name the no-auto-implement guard",
        )


if __name__ == "__main__":
    unittest.main()
