from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import create_beads_from_tasks as script


def sample_tasks() -> str:
    return """---
plan_slug: demo
phase: tasks
rig: backend
rig_root: /repo
artifact_root: /repo/.gc/plans
requirements_file: /repo/.gc/plans/demo/requirements.md
design_file: /repo/.gc/plans/demo/design.md
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
epics:
  - key: foundation
    title: Build planning foundation
    description: Group foundational work.
    acceptance_criteria:
      - Foundation work is tracked.
beads:
  - key: schema
    title: Add schema
    type: task
    priority: 2
    description: |
      Add the schema.
    acceptance_criteria:
      - Schema is documented.
    dependencies: []
    epic: foundation
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
```
"""


class CreateBeadsFromTasksTests(unittest.TestCase):
    def test_parse_plan_validates_and_orders_dependencies(self) -> None:
        plan = script.parse_plan(script.extract_payload(sample_tasks()))

        ordered = script.topo_order(plan.items)

        self.assertEqual([item.key for item in ordered], ["foundation", "schema", "docs"])
        self.assertEqual(plan.target_rig, "backend")
        self.assertEqual(plan.beads[0].formula, "mol-polecat-lazyjj-work")

    def test_duplicate_keys_fail_validation(self) -> None:
        text = sample_tasks().replace("key: docs", "key: schema")

        with self.assertRaises(script.PlanError):
            script.parse_plan(script.extract_payload(text))

    def test_unknown_dependency_fails_validation(self) -> None:
        text = sample_tasks().replace("- schema", "- missing")

        with self.assertRaises(script.PlanError):
            script.parse_plan(script.extract_payload(text))

    def test_dry_run_prints_gc_bd_commands_and_does_not_modify_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            original = sample_tasks()
            path.write_text(original, encoding="utf-8")

            with mock.patch("builtins.print") as mocked_print:
                code = script.create_from_tasks(path, city="/city", dry_run=True, force=False)

            self.assertEqual(code, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            printed = "\n".join(str(call.args[0]) for call in mocked_print.call_args_list)
            self.assertIn("gc bd --city /city --rig backend create --json", printed)
            self.assertIn("gc bd --city /city --rig backend dep add '<docs>' '<schema>'", printed)

    def test_create_updates_created_beads_section(self) -> None:
        outputs = {
            "Build planning foundation": {"id": "BACK-1"},
            "Add schema": {"id": "BACK-2"},
            "Document workflow": {"id": "BACK-3"},
        }

        def fake_run(cmd, text=None, capture_output=None, check=None):
            joined = " ".join(cmd)
            if " dep list " in joined:
                return subprocess_result("[]")
            if " dep add " in joined:
                return subprocess_result("")
            if " show " in joined:
                return subprocess_result("{}")
            for title, payload in outputs.items():
                if title in cmd:
                    return subprocess_result(json.dumps(payload))
            return subprocess_result("", returncode=1, stderr="unexpected command")

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(sample_tasks(), encoding="utf-8")

            with mock.patch("subprocess.run", side_effect=fake_run):
                code = script.create_from_tasks(path, city=None, dry_run=False, force=False)

            self.assertEqual(code, 0)
            text = path.read_text(encoding="utf-8")
            self.assertIn("status: created", text)
            self.assertIn("| foundation | BACK-1 | Build planning foundation |", text)
            self.assertIn("| schema | BACK-2 | Add schema |", text)
            self.assertIn("| docs | BACK-3 | Document workflow |", text)

    def test_create_records_lazyjj_formula_metadata(self) -> None:
        seen_metadata: list[dict[str, str]] = []

        def fake_run(cmd, text=None, capture_output=None, check=None):
            if "--metadata" in cmd:
                seen_metadata.append(json.loads(cmd[cmd.index("--metadata") + 1]))
            if " dep list " in " ".join(cmd):
                return subprocess_result("[]")
            if " dep add " in " ".join(cmd):
                return subprocess_result("")
            if "Build planning foundation" in cmd:
                return subprocess_result('{"id":"BACK-1"}')
            if "Add schema" in cmd:
                return subprocess_result('{"id":"BACK-2"}')
            if "Document workflow" in cmd:
                return subprocess_result('{"id":"BACK-3"}')
            return subprocess_result("", returncode=1, stderr="unexpected command")

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(sample_tasks(), encoding="utf-8")

            with mock.patch("subprocess.run", side_effect=fake_run):
                script.create_from_tasks(path, city=None, dry_run=False, force=False)

        schema_metadata = next(meta for meta in seen_metadata if meta["gc.plan.key"] == "schema")
        self.assertEqual(schema_metadata["lazyjj.work_formula"], "mol-polecat-lazyjj-work")

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

            with mock.patch("subprocess.run", side_effect=fake_successful_gc_bd):
                script.create_from_tasks(path, city=None, dry_run=False, force=False)

            text = path.read_text(encoding="utf-8")
            self.assertIn("created_at: '2026-05-10T00:00:00Z'", text)

    def test_existing_mapping_is_reused_after_validation(self) -> None:
        text = sample_tasks() + """
## Created Beads

| Key | Bead ID | Title |
|---|---|---|
| foundation | BACK-1 | Build planning foundation |
"""
        seen: list[list[str]] = []

        def fake_run(cmd, text=None, capture_output=None, check=None):
            seen.append(cmd)
            joined = " ".join(cmd)
            if " show BACK-1 --json" in joined:
                return subprocess_result('{"id":"BACK-1"}')
            if " dep list " in joined:
                return subprocess_result("[]")
            if " dep add " in joined:
                return subprocess_result("")
            if "Add schema" in cmd:
                return subprocess_result('{"id":"BACK-2"}')
            if "Document workflow" in cmd:
                return subprocess_result('{"id":"BACK-3"}')
            return subprocess_result("", returncode=1, stderr="unexpected command")

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tasks.md"
            path.write_text(text, encoding="utf-8")

            with mock.patch("subprocess.run", side_effect=fake_run):
                script.create_from_tasks(path, city=None, dry_run=False, force=False)

        create_titles = [cmd[6] for cmd in seen if len(cmd) > 6 and cmd[4] == "create"]
        self.assertNotIn("Build planning foundation", create_titles)

    def test_partial_failure_records_successful_mappings(self) -> None:
        def fake_run(cmd, text=None, capture_output=None, check=None):
            if "Build planning foundation" in cmd:
                return subprocess_result('{"id":"BACK-1"}')
            if "Add schema" in cmd:
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
            self.assertIn("| foundation | BACK-1 | Build planning foundation |", text)


def subprocess_result(stdout: str, returncode: int = 0, stderr: str = ""):
    return mock.Mock(returncode=returncode, stdout=stdout, stderr=stderr)


def fake_successful_gc_bd(cmd, text=None, capture_output=None, check=None):
    joined = " ".join(cmd)
    if " dep list " in joined:
        return subprocess_result("[]")
    if " dep add " in joined:
        return subprocess_result("")
    if " show " in joined:
        return subprocess_result("{}")
    if "Build planning foundation" in cmd:
        return subprocess_result('{"id":"BACK-1"}')
    if "Add schema" in cmd:
        return subprocess_result('{"id":"BACK-2"}')
    if "Document workflow" in cmd:
        return subprocess_result('{"id":"BACK-3"}')
    return subprocess_result("", returncode=1, stderr="unexpected command")


if __name__ == "__main__":
    unittest.main()
