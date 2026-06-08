from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "assets" / "scripts"))

import create_beads_from_tasks as script


def sample_tasks() -> str:
    return """---
plan_slug: demo
phase: tasks
rig: backend
rig_root: /repo
artifact_root: /repo/plans
requirements_file: /repo/plans/demo/requirements.md
implementation_plan_file: /repo/plans/demo/implementation-plan.md
status: approved
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---
# Task Plan: Demo

## Bead Creation Payload

```yaml
target_rig: backend
labels:
  - plan:demo
convoys:
  - key: implementation
    title: Implement demo
    description: Group implementation work.
    target: feature/demo
    metadata:
      gc.plan.phase: implementation
    beads:
      - key: schema
        title: Add schema
        type: task
        priority: 2
        description: |
          Add the schema.
        acceptance_criteria:
          - Schema is documented.
        files:
          - internal/schema.go
        verification:
          - go test ./internal/...
      - key: docs
        title: Document workflow
        type: docs
        priority: 3
        description: |
          Document the workflow.
        acceptance_criteria:
          - Docs explain usage.
        dependencies:
          - schema
  - key: release
    title: Release docs
    description: Group release work.
    dependencies:
      - implementation
    beads:
      - key: announce
        title: Announce release
        type: task
        priority: 3
        description: Announce the release.
        acceptance_criteria:
          - Announcement is drafted.
```
"""


class CreateBeadsFromTasksTests(unittest.TestCase):
    def test_sample_tasks_use_implementation_plan_front_matter(self) -> None:
        text = sample_tasks()

        self.assertIn("implementation_plan_file:", text)
        self.assertIn("implementation-plan.md", text)
        self.assertNotIn("design_file:", text)
        self.assertNotIn("design.md", text)

    def test_parse_plan_validates_convoys_and_orders_runnables(self) -> None:
        plan = script.parse_plan(script.extract_payload(sample_tasks()))

        ordered = script.topo_order(plan.runnables)

        self.assertEqual([item.key for item in ordered], ["schema", "docs", "announce"])
        self.assertEqual([convoy.key for convoy in plan.convoys], ["implementation", "release"])
        self.assertEqual(plan.target_rig, "backend")

    def test_legacy_epics_fail_validation(self) -> None:
        text = sample_tasks().replace("convoys:", "epics:")

        with self.assertRaisesRegex(script.PlanError, "epics"):
            script.parse_plan(script.extract_payload(text))

    def test_duplicate_keys_fail_validation(self) -> None:
        text = sample_tasks().replace("key: docs", "key: schema")

        with self.assertRaises(script.PlanError):
            script.parse_plan(script.extract_payload(text))

    def test_unknown_dependency_fails_validation(self) -> None:
        text = sample_tasks().replace("- schema", "- missing")

        with self.assertRaises(script.PlanError):
            script.parse_plan(script.extract_payload(text))

    def test_test_issue_type_fails_validation(self) -> None:
        text = sample_tasks().replace("type: docs", "type: test")

        with self.assertRaisesRegex(script.PlanError, "unsupported type 'test'"):
            script.parse_plan(script.extract_payload(text))

    def test_empty_convoy_fails_validation(self) -> None:
        text = sample_tasks().replace(
            "    beads:\n"
            "      - key: schema\n"
            "        title: Add schema\n"
            "        type: task\n"
            "        priority: 2\n"
            "        description: |\n"
            "          Add the schema.\n"
            "        acceptance_criteria:\n"
            "          - Schema is documented.\n"
            "        files:\n"
            "          - internal/schema.go\n"
            "        verification:\n"
            "          - go test ./internal/...\n"
            "      - key: docs\n"
            "        title: Document workflow\n"
            "        type: docs\n"
            "        priority: 3\n"
            "        description: |\n"
            "          Document the workflow.\n"
            "        acceptance_criteria:\n"
            "          - Docs explain usage.\n"
            "        dependencies:\n"
            "          - schema\n",
            "",
        )

        with self.assertRaisesRegex(script.PlanError, "implementation"):
            script.parse_plan(script.extract_payload(text))

    def test_convoy_dependency_expands_to_runnable_edges(self) -> None:
        plan = script.parse_plan(script.extract_payload(sample_tasks()))
        edges = script.expanded_dependency_edges(plan)

        self.assertIn(("docs", "schema"), edges)
        self.assertIn(("announce", "docs"), edges)
        self.assertNotIn(("implementation", "schema"), edges)

    def test_nested_convoy_membership_links_only_immediate_children(self) -> None:
        text = sample_tasks().replace(
            "    beads:\n      - key: schema",
            "    convoys:\n"
            "      - key: nested\n"
            "        title: Nested work\n"
            "        description: Nested implementation group.\n"
            "        convoys:\n"
            "          - key: deeper\n"
            "            title: Deeper work\n"
            "            description: Deeper implementation group.\n"
            "            beads:\n"
            "              - key: nested-task\n"
            "                title: Do nested task\n"
            "                type: task\n"
            "                priority: 2\n"
            "                description: Implement nested work.\n"
            "                acceptance_criteria:\n"
            "                  - Nested work is done.\n"
            "    beads:\n"
            "      - key: schema",
        )
        plan = script.parse_plan(script.extract_payload(text))
        convoys = {convoy.key: convoy for convoy in plan.convoys}

        self.assertEqual(convoys["implementation"].convoy_keys, ["nested"])
        self.assertEqual(convoys["nested"].convoy_keys, ["deeper"])

    def test_metadata_normalizes_legacy_work_option_keys(self) -> None:
        text = sample_tasks().replace(
            "        priority: 2\n"
            "        description: |\n",
            """        priority: 2
        metadata:
          gc.model: opus
          gc.reasoning: high
          gc.effort: medium
          opt_model: sonnet
          opt_effort: low
        description: |
""",
            1,
        )

        plan = script.parse_plan(script.extract_payload(text))
        schema = next(item for item in plan.runnables if item.key == "schema")

        self.assertEqual(schema.metadata["opt_model"], "sonnet")
        self.assertEqual(schema.metadata["opt_effort"], "low")
        self.assertNotIn("gc.model", schema.metadata)
        self.assertNotIn("gc.reasoning", schema.metadata)
        self.assertNotIn("gc.effort", schema.metadata)

    def test_dry_run_prints_gc_commands_and_does_not_modify_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            original = sample_tasks()
            path.write_text(original, encoding="utf-8")

            with mock.patch("builtins.print") as mocked_print:
                code = script.create_from_tasks(path, city="/city", dry_run=True, force=False)

            self.assertEqual(code, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            printed = "\n".join(str(call.args[0]) for call in mocked_print.call_args_list)
            self.assertIn("gc bd --city /city --rig backend create --json 'Add schema'", printed)
            self.assertIn(
                "gc convoy --city /city --rig backend create --json --target feature/demo 'Implement demo' '<schema>'",
                printed,
            )
            self.assertIn("gc bd --city /city --rig backend update '<implementation>' --metadata", printed)
            self.assertNotIn("gc convoy --city /city --rig backend add '<implementation>' '<schema>'", printed)
            self.assertIn("gc convoy --city /city --rig backend add '<implementation>' '<docs>'", printed)
            self.assertIn("gc bd --city /city --rig backend dep add '<announce>' '<docs>'", printed)

    def test_create_updates_created_mapping_for_convoys_and_beads(self) -> None:
        def fake_run(cmd, text=None, capture_output=None, check=None):
            joined = " ".join(cmd)
            if " dep list " in joined:
                return subprocess_result("[]")
            if " dep add " in joined:
                return subprocess_result("")
            if " show " in joined:
                return subprocess_result("{}")
            if cmd[:2] == ["gc", "convoy"] and "add" in cmd:
                return subprocess_result("{}")
            if " update " in joined:
                return subprocess_result("{}")
            if cmd[:2] == ["gc", "convoy"] and "Implement demo" in cmd:
                return subprocess_result(json.dumps({"id": "CONV-1"}))
            if cmd[:2] == ["gc", "convoy"] and "Release docs" in cmd:
                return subprocess_result(json.dumps({"id": "CONV-2"}))
            if "Add schema" in cmd:
                return subprocess_result(json.dumps({"id": "BACK-1"}))
            if "Document workflow" in cmd:
                return subprocess_result(json.dumps({"id": "BACK-2"}))
            if "Announce release" in cmd:
                return subprocess_result(json.dumps({"id": "BACK-3"}))
            return subprocess_result("", returncode=1, stderr=f"unexpected command: {joined}")

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(sample_tasks(), encoding="utf-8")

            with mock.patch("subprocess.run", side_effect=fake_run):
                code = script.create_from_tasks(path, city=None, dry_run=False, force=False)

            self.assertEqual(code, 0)
            text = path.read_text(encoding="utf-8")
            self.assertIn("status: created", text)
            self.assertIn("| implementation | convoy | CONV-1 | Implement demo |", text)
            self.assertIn("| release | convoy | CONV-2 | Release docs |", text)
            self.assertIn("| schema | bead | BACK-1 | Add schema |", text)
            self.assertIn("| docs | bead | BACK-2 | Document workflow |", text)
            self.assertIn("| announce | bead | BACK-3 | Announce release |", text)

    def test_created_status_refuses_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(sample_tasks().replace("status: approved", "status: created"), encoding="utf-8")

            with self.assertRaises(script.PlanError):
                script.create_from_tasks(path, city=None, dry_run=False, force=False)

    def test_front_matter_timestamps_remain_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(sample_tasks(), encoding="utf-8")

            with mock.patch("subprocess.run", side_effect=fake_successful_gc):
                script.create_from_tasks(path, city=None, dry_run=False, force=False)

            text = path.read_text(encoding="utf-8")
            self.assertIn("created_at: '2026-05-10T00:00:00Z'", text)

    def test_existing_mapping_is_reused_after_validation(self) -> None:
        text = sample_tasks() + """
## Created Beads

| Key | Kind | Bead ID | Title |
|---|---|---|---|
| schema | bead | BACK-1 | Add schema |
"""
        seen: list[list[str]] = []

        def fake_run(cmd, text=None, capture_output=None, check=None):
            seen.append(cmd)
            joined = " ".join(cmd)
            if " show BACK-1 --json" in joined:
                return subprocess_result('{"id":"BACK-1"}')
            return fake_successful_gc(cmd, text=text, capture_output=capture_output, check=check)

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(text, encoding="utf-8")

            with mock.patch("subprocess.run", side_effect=fake_run):
                script.create_from_tasks(path, city=None, dry_run=False, force=False)

        create_titles = [cmd[6] for cmd in seen if len(cmd) > 6 and cmd[0:2] == ["gc", "bd"] and cmd[4] == "create"]
        self.assertNotIn("Add schema", create_titles)

    def test_existing_convoy_mapping_retries_metadata_update(self) -> None:
        text = sample_tasks() + """
## Created Beads

| Key | Kind | Bead ID | Title |
|---|---|---|---|
| implementation | convoy | CONV-1 | Implement demo |
"""
        seen: list[list[str]] = []

        def fake_run(cmd, text=None, capture_output=None, check=None):
            seen.append(cmd)
            joined = " ".join(cmd)
            if " show CONV-1 --json" in joined:
                return subprocess_result('{"id":"CONV-1","issue_type":"convoy"}')
            return fake_successful_gc(cmd, text=text, capture_output=capture_output, check=check)

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(text, encoding="utf-8")

            with mock.patch("subprocess.run", side_effect=fake_run):
                script.create_from_tasks(path, city=None, dry_run=False, force=False)

        metadata_updates = [
            cmd
            for cmd in seen
            if len(cmd) > 6 and cmd[:2] == ["gc", "bd"] and cmd[4:7] == ["update", "CONV-1", "--metadata"]
        ]
        self.assertEqual(len(metadata_updates), 1)
        self.assertIn('"gc.plan.kind": "convoy"', metadata_updates[0][7])

    def test_create_output_parser_accepts_pretty_json(self) -> None:
        output = "created issue\n{\n  \"id\": \"BACK-1\",\n  \"title\": \"Add schema\"\n}\n"

        self.assertEqual(script.parse_create_output(output), "BACK-1")

    def test_dependency_exists_accepts_real_bd_json_shape(self) -> None:
        runner = script.Runner(city=None, rig="backend", dry_run=False)
        seen: list[list[str]] = []

        def fake_run(stdout: str):
            def run(cmd, text=None, capture_output=None, check=None):
                seen.append(cmd)
                return subprocess_result(stdout)

            return run

        with mock.patch("subprocess.run", side_effect=fake_run('[{"id":"BACK-1","dependency_type":"blocks"}]')):
            self.assertTrue(script.dependency_exists(runner, "BACK-2", "BACK-1"))

        with mock.patch("subprocess.run", side_effect=fake_run('[{"id":"BACK-1","dependency_type":"tracks"}]')):
            self.assertFalse(script.dependency_exists(runner, "BACK-2", "BACK-1"))
        self.assertNotIn("--direction=up", [arg for cmd in seen for arg in cmd])

    def test_partial_failure_records_successful_mappings(self) -> None:
        def fake_run(cmd, text=None, capture_output=None, check=None):
            if "Add schema" in cmd:
                return subprocess_result('{"id":"BACK-1"}')
            if "Document workflow" in cmd:
                return subprocess_result("", returncode=1, stderr="boom")
            return subprocess_result("[]")

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(sample_tasks(), encoding="utf-8")

            with mock.patch("subprocess.run", side_effect=fake_run):
                with self.assertRaises(script.PlanError):
                    script.create_from_tasks(path, city=None, dry_run=False, force=False)

            text = path.read_text(encoding="utf-8")
            self.assertIn("status: partial", text)
            self.assertIn("| schema | bead | BACK-1 | Add schema |", text)

    def test_resume_reuses_seeded_convoy_membership(self) -> None:
        created_section = """
## Created Beads

| Key | Kind | Bead ID | Title |
|---|---|---|---|
| implementation | convoy | CONV-1 | Implement demo |
| release | convoy | CONV-2 | Release docs |
| schema | bead | BACK-1 | Add schema |
| docs | bead | BACK-2 | Document workflow |
| announce | bead | BACK-3 | Announce release |
"""

        def collect_convoy_adds(markdown: str) -> list[list[str]]:
            seen: list[list[str]] = []

            def fake_run(cmd, text=None, capture_output=None, check=None):
                seen.append(cmd)
                return fake_successful_gc(cmd, text=text, capture_output=capture_output, check=check)

            with tempfile.TemporaryDirectory() as tmp:
                path = pathlib.Path(tmp) / "tasks.md"
                path.write_text(markdown, encoding="utf-8")

                with mock.patch("subprocess.run", side_effect=fake_run):
                    script.create_from_tasks(path, city=None, dry_run=False, force=False)

            return [cmd for cmd in seen if cmd[:2] == ["gc", "convoy"] and "add" in cmd]

        fresh_adds = collect_convoy_adds(sample_tasks())
        resume_adds = collect_convoy_adds(sample_tasks().replace("status: approved", "status: partial") + created_section)

        self.assertEqual(resume_adds, fresh_adds)
        self.assertNotIn(["gc", "convoy", "--rig", "backend", "add", "CONV-1", "BACK-1"], resume_adds)

    def test_resume_skips_existing_non_seed_convoy_membership(self) -> None:
        created_section = """
## Created Beads

| Key | Kind | Bead ID | Title |
|---|---|---|---|
| implementation | convoy | CONV-1 | Implement demo |
| release | convoy | CONV-2 | Release docs |
| schema | bead | BACK-1 | Add schema |
| docs | bead | BACK-2 | Document workflow |
| announce | bead | BACK-3 | Announce release |
"""
        seen: list[list[str]] = []

        def fake_run(cmd, text=None, capture_output=None, check=None):
            seen.append(cmd)
            joined = " ".join(cmd)
            if " dep list CONV-1 " in f" {joined} " and "--type tracks" in joined:
                return subprocess_result('[{"id":"BACK-2","dependency_type":"tracks"}]')
            return fake_successful_gc(cmd, text=text, capture_output=capture_output, check=check)

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(
                sample_tasks().replace("status: approved", "status: partial") + created_section,
                encoding="utf-8",
            )

            with mock.patch("subprocess.run", side_effect=fake_run):
                script.create_from_tasks(path, city=None, dry_run=False, force=False)

        add_commands = [cmd for cmd in seen if cmd[:2] == ["gc", "convoy"] and "add" in cmd]
        self.assertNotIn(["gc", "convoy", "--rig", "backend", "add", "CONV-1", "BACK-2"], add_commands)


def subprocess_result(stdout: str, returncode: int = 0, stderr: str = ""):
    return mock.Mock(returncode=returncode, stdout=stdout, stderr=stderr)


def fake_successful_gc(cmd, text=None, capture_output=None, check=None):
    joined = " ".join(cmd)
    if " dep list " in joined:
        return subprocess_result("[]")
    if " dep add " in joined:
        return subprocess_result("")
    if " show " in joined:
        return subprocess_result("{}")
    if cmd[:2] == ["gc", "convoy"] and "add" in cmd:
        return subprocess_result("{}")
    if " update " in joined:
        return subprocess_result("{}")
    if cmd[:2] == ["gc", "convoy"] and "Implement demo" in cmd:
        return subprocess_result('{"id":"CONV-1"}')
    if cmd[:2] == ["gc", "convoy"] and "Release docs" in cmd:
        return subprocess_result('{"id":"CONV-2"}')
    if "Add schema" in cmd:
        return subprocess_result('{"id":"BACK-1"}')
    if "Document workflow" in cmd:
        return subprocess_result('{"id":"BACK-2"}')
    if "Announce release" in cmd:
        return subprocess_result('{"id":"BACK-3"}')
    return subprocess_result("", returncode=1, stderr=f"unexpected command: {joined}")


if __name__ == "__main__":
    unittest.main()
