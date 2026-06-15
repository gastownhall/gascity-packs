from __future__ import annotations

import pathlib
import tomllib
import unittest


class LazyJJJediRoutingTests(unittest.TestCase):
    def test_jedi_is_polecat_style_pool_worker(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        data = tomllib.loads((root / "pack.toml").read_text(encoding="utf-8"))
        sessions = {
            session["template"]: session
            for session in data.get("named_session", [])
        }
        agent = tomllib.loads(
            (root / "agents" / "jedi" / "agent.toml").read_text(encoding="utf-8")
        )

        self.assertNotIn("jedi", sessions)
        self.assertEqual(agent["scope"], "rig")
        self.assertEqual(agent["formula"], "mol-polecat-lazyjj-work")
        self.assertEqual(agent["min_active_sessions"], 0)
        self.assertEqual(agent["max_active_sessions"], 5)

    def test_jedi_prompt_uses_gc_hook_for_pool_work(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        prompt = (root / "agents" / "jedi" / "prompt.template.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("gc hook", prompt)
        self.assertNotIn("{{ .WorkQuery }}", prompt)

    def test_formula_rejects_mismatched_recovery_workspace(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        formula = (root / "formulas" / "mol-polecat-lazyjj-work.toml").read_text(
            encoding="utf-8"
        )

        self.assertIn('RECORDED_WORKSPACE_DIR" != "$WORKSPACE_DIR"', formula)
        self.assertIn(
            "this session is in $WORKSPACE_DIR",
            formula,
        )
        self.assertIn("exit 1", formula)

    def test_tasksmith_does_not_claim_pre_start_seeds_work(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        prompt = (root / "agents" / "tasksmith" / "prompt.template.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("pre_start", prompt)
        self.assertIn("does not seed the initial `jj` change", prompt)
        self.assertNotIn("LAZYJJ_WORK_TITLE", prompt)
        self.assertNotIn("--description-file", prompt)

    def test_jedi_final_steps_do_not_auto_drain(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        prompt = (root / "agents" / "jedi" / "prompt.template.md").read_text(
            encoding="utf-8"
        )
        worker = (
            root
            / "agents"
            / "jedi"
            / "template-fragments"
            / "gc-role-worker.template.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Do not run `gc runtime drain-ack`", prompt)
        self.assertNotIn("gc runtime drain-ack && exit", prompt)
        self.assertNotIn("gc runtime drain-ack\n", worker)
        self.assertIn("stop without running", worker)


if __name__ == "__main__":
    unittest.main()
