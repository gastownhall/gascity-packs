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

    def test_formula_prefers_jjw_hook_workspace_env(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        formula = (root / "formulas" / "mol-polecat-lazyjj-work.toml").read_text(
            encoding="utf-8"
        )

        self.assertIn("WORKSPACE_DIR=${JJW_PATH:-}", formula)
        self.assertIn("WORKSPACE_NAME=${JJW_NAME:-}", formula)
        self.assertIn("session preserves them", formula)
        self.assertIn("Always persist the result to the bead", formula)

    def test_jedi_workspace_path_matches_jjw_config_contract(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        agent = tomllib.loads(
            (root / "agents" / "jedi" / "agent.toml").read_text(encoding="utf-8")
        )
        jjw_setup = (
            root.parent / "jjw" / "assets" / "scripts" / "workspace-setup.sh"
        ).read_text(encoding="utf-8")

        self.assertIn(".gc/workspaces/{{.Rig}}/jedi/{{.AgentBase}}", agent["work_dir"])
        self.assertIn("CONFIGURED_WORKSPACE_DIR=$(read_config_workspace_dir", jjw_setup)
        self.assertIn("refusing to create workspace outside jjw config", jjw_setup)
        self.assertIn("update agent work_dir or GC_JJW_WORKSPACE_DIR", jjw_setup)

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

    def test_role_worker_template_path_exists_for_lint(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        worker = root / "agents" / "jedi" / "gc-role-worker.template.md"

        self.assertTrue(worker.exists())
        self.assertIn(
            '{{ template "gc-role-worker" . }}',
            worker.read_text(encoding="utf-8"),
        )

    def test_submit_records_concrete_stack_head(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        formula = (root / "formulas" / "mol-polecat-lazyjj-work.toml").read_text(
            encoding="utf-8"
        )

        self.assertIn("STACK_HEAD=$(jj log -r", formula)
        self.assertIn("--set-metadata lazyjj_stack_head", formula)
        self.assertIn("Stack head: $STACK_HEAD", formula)
        self.assertIn("mol-lazyjj-cross-workspace-sync", formula)

    def test_prompts_describe_single_bead_live_test_path(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        tasksmith = (root / "agents" / "tasksmith" / "prompt.template.md").read_text(
            encoding="utf-8"
        )
        jedi = (root / "agents" / "jedi" / "prompt.template.md").read_text(
            encoding="utf-8"
        )
        runner = (root / "agents" / "runner" / "prompt.template.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Canonical idea-to-live-test path", readme)
        self.assertIn("one focused implementation bead", tasksmith)
        self.assertIn("Do not explode routine pack work", tasksmith)
        self.assertIn("one coherent implementation bead", jedi)
        self.assertIn("lazyjj_stack_head", runner)
        self.assertIn("mol-lazyjj-cross-workspace-sync", runner)


if __name__ == "__main__":
    unittest.main()
