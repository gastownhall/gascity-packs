from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "commands" / "workspace" / "run.sh"


class WorkspaceScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "rig"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Workspace Tests")
        (self.root / "README").write_text("base\n")
        self.git("add", "README")
        self.git("commit", "-qm", "base")
        self.oid = self.git("rev-parse", "HEAD").stdout.strip()
        self.bin = pathlib.Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.data = pathlib.Path(self.tmp.name) / "gc.json"
        self.data.write_text(json.dumps({
            "step": {"id": "step-1", "metadata": {"gc.root_bead_id": "root-1"}},
            "root": {"id": "root-1", "metadata": {"gc.input_convoy_id": "convoy-1"}},
            "convoy": {"id": "convoy-1", "parent_convoy_id": "implementation-1", "metadata": {}},
            "owner": {"id": "implementation-1", "parent_convoy_id": "", "metadata": {}},
        }))
        stub = self.bin / "gc"
        stub.write_text("""#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:3] == ["bd", "list"] and sys.argv[3:] == ["--all", "--json", "--limit=0"]:
    data = json.load(open(os.environ["GC_STUB_DATA"], encoding="utf-8"))
    values = []
    for value in data.values():
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if isinstance(candidate, dict) and "id" in candidate and candidate not in values:
                values.append(candidate)
    print(json.dumps(values, separators=(",", ":")))
    raise SystemExit(0)
if sys.argv[1:3] != ["bd", "show"] or len(sys.argv) != 5 or sys.argv[4] != "--json":  # gc-bd-argv-tail: fake gc receives wrapper argv tail
    print("malformed gc invocation", file=sys.stderr)
    raise SystemExit(2)
ident = sys.argv[3]
data = json.load(open(os.environ["GC_STUB_DATA"], encoding="utf-8"))
value = next((bead for bead in data.values() if (isinstance(bead, dict) and bead.get("id") == ident) or (isinstance(bead, list) and any(isinstance(item, dict) and item.get("id") == ident for item in bead))), None)
if value is None:
    value = data.get(ident)
if value is None:
    print(json.dumps([]))
elif isinstance(value, dict) and "_raw" in value:
    print(value["_raw"])
else:
    print(json.dumps(value, separators=(",", ":")))
""")
        stub.chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, check=True)

    def run_ws(
        self,
        action: str,
        step: str = "step-1",
        ref: str | None = None,
        *,
        workspace_parent: pathlib.Path | None = None,
        use_rig_root: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        args = [str(SCRIPT), action, "--step-id", step]
        if action == "prepare":
            args += ["--input-ref", ref or self.oid]
            if workspace_parent is not None:
                args += ["--workspace-parent", str(workspace_parent)]
        env = os.environ.copy()
        env.update({"GC_STUB_DATA": str(self.data), "PATH": f"{self.bin}:{env['PATH']}"})
        env.pop("GC_WORK_DIR", None)
        env.pop("GC_RIG_ROOT", None)
        env["GC_RIG_ROOT" if use_rig_root else "GC_WORK_DIR"] = str(self.root)
        return subprocess.run(args, cwd=self.tmp.name, env=env, text=True, capture_output=True)

    def payload(self, result: subprocess.CompletedProcess[str]) -> dict[str, str]:
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertIsInstance(value, dict)
        return value

    def prepare(self, step: str = "step-1", ref: str | None = None) -> dict[str, str]:
        return self.payload(self.run_ws("prepare", step, ref))

    def assert_compact(self, value: dict[str, str], *, output: bool = False, anchor: str = "convoy-1") -> None:
        expected = {"worktree_path", "input_oid", "phase", "source_anchor_id"}
        if output:
            expected.add("output_oid")
        self.assertEqual(set(value), expected)
        self.assertEqual(value["source_anchor_id"], anchor)

    def state_path(self) -> pathlib.Path:
        git_dir = pathlib.Path(self.git("rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip())
        return next((git_dir / "gc-workspace-state").rglob("*.json"))

    def assert_failed_unchanged(self, action: str, state: pathlib.Path) -> subprocess.CompletedProcess[str]:
        before = state.read_bytes()
        result = self.run_ws(action)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state.read_bytes(), before)
        return result

    def test_separate_anchor_captures_and_replays_exact_oid(self):
        first = self.prepare()
        self.assert_compact(first)
        self.assertEqual(first["input_oid"], self.oid)
        replay = self.prepare()
        self.assertEqual(replay["worktree_path"], first["worktree_path"])
        self.assertEqual(replay["input_oid"], self.oid)
        self.assertEqual(set(replay), {"worktree_path", "input_oid", "phase", "source_anchor_id"})

    def test_agent_rig_root_prepares_workspace_without_work_dir(self):
        prepared = self.payload(self.run_ws("prepare", use_rig_root=True))
        self.assert_compact(prepared)
        self.assertEqual(prepared["input_oid"], self.oid)

    def test_multiple_anchors_do_not_claim_common_base(self):
        data = json.loads(self.data.read_text())
        data.update({
            "step-2": {"id": "step-2", "metadata": {"gc.root_bead_id": "root-2"}},
            "root-2": {"id": "root-2", "metadata": {"gc.input_convoy_id": "convoy-2"}},
            "convoy-2": {"id": "convoy-2", "parent_convoy_id": "implementation-2", "metadata": {}},
            "owner-2": {"id": "implementation-2", "parent_convoy_id": "", "metadata": {}},
        })
        self.data.write_text(json.dumps(data))
        first = self.prepare()
        (self.root / "README").write_text("second\n")
        self.git("commit", "-qam", "second")
        second = self.prepare("step-2", self.git("rev-parse", "HEAD").stdout.strip())
        self.assertNotEqual(first["input_oid"], second["input_oid"])
        self.assertNotEqual(first["worktree_path"], second["worktree_path"])

    def test_scheduling_dependency_does_not_change_input_oid(self):
        data = json.loads(self.data.read_text())
        data["step"]["metadata"]["gc.scheduling_dependency"] = "other-step"
        self.data.write_text(json.dumps(data))
        self.assertEqual(self.prepare()["input_oid"], self.oid)

    def test_same_session_assets_remain_legacy_without_script_wiring(self):
        result = self.run_ws("checkpoint")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown action", result.stderr)

    def test_multiple_results_do_not_create_integration_or_canonical_state(self):
        data = json.loads(self.data.read_text())
        data.update({
            "step-2": {"id": "step-2", "metadata": {"gc.root_bead_id": "root-2"}},
            "root-2": {"id": "root-2", "metadata": {"gc.input_convoy_id": "convoy-2"}},
            "convoy-2": {"id": "convoy-2", "parent_convoy_id": "implementation-2", "metadata": {}},
            "owner-2": {"id": "implementation-2", "parent_convoy_id": "", "metadata": {}},
        })
        self.data.write_text(json.dumps(data))
        first = self.prepare()
        second = self.prepare("step-2")
        first_result = self.payload(self.run_ws("record-result"))
        second_result = self.payload(self.run_ws("record-result", "step-2"))
        self.assertEqual(first_result["output_oid"], first["input_oid"])
        self.assertEqual(second_result["output_oid"], second["input_oid"])
        states = list((self.root / ".git" / "gc-workspace-state").rglob("*.json"))
        self.assertEqual(len(states), 2)
        self.assertFalse((self.root / ".git" / "gc-workspace-state" / "state.json").exists())

    def test_review_and_fix_actions_are_side_effect_free_rejections(self):
        self.prepare()
        state = next((self.root / ".git" / "gc-workspace-state").rglob("*.json"))
        before = state.read_bytes()
        for action in ("review", "fix"):
            result = self.run_ws(action)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(state.read_bytes(), before)

    def test_publish_and_pr_actions_never_call_remote_operations(self):
        self.prepare()
        state = next((self.root / ".git" / "gc-workspace-state").rglob("*.json"))
        before = state.read_bytes()
        for action in ("publish", "pr"):
            result = self.run_ws(action)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown action", result.stderr)
        self.assertEqual(state.read_bytes(), before)

    def test_new_workflow_root_with_same_parent_convoy_reuses_workspace(self):
        first = self.prepare()
        self.payload(self.run_ws("record-result"))
        data = json.loads(self.data.read_text())
        data.update({
            "step-2": {"id": "step-2", "metadata": {"gc.root_bead_id": "root-2"}},
            "root-2": {"id": "root-2", "metadata": {
                "gc.input_convoy_id": "unit-2",
                "gc.drain_member_id": "member-2",
            }},
            "unit-2": {"id": "unit-2", "metadata": {
                "gc.synthetic_kind": "drain-unit-convoy",
                "gc.drain_member_id": "member-2",
            }},
            "member-2": {"id": "member-2", "parent_convoy_id": "implementation-1", "metadata": {}},
        })
        self.data.write_text(json.dumps(data))
        second = self.prepare("step-2", first["input_oid"])
        self.assertEqual(first["worktree_path"], second["worktree_path"])
        self.assertEqual(second["source_anchor_id"], "member-2")

    def test_next_owner_item_uses_recorded_output_not_launch_base(self):
        first = self.prepare()
        worktree = pathlib.Path(first["worktree_path"])
        (worktree / "README").write_text("first\n")
        subprocess.run(["git", "add", "README"], cwd=worktree, check=True)
        subprocess.run(["git", "commit", "-qm", "first"], cwd=worktree, check=True)
        output = self.payload(self.run_ws("record-result"))["output_oid"]
        data = json.loads(self.data.read_text())
        data.update({
            "step-2": {"id": "step-2", "metadata": {"gc.root_bead_id": "root-2"}},
            "root-2": {"id": "root-2", "metadata": {"gc.input_convoy_id": "member-2"}},
            "member-2": {"id": "member-2", "parent_convoy_id": "implementation-1", "metadata": {}},
        })
        self.data.write_text(json.dumps(data))
        second = self.prepare("step-2", self.oid)
        self.assertEqual(second["input_oid"], output)
        self.assertEqual(pathlib.Path(second["worktree_path"]) / "README", worktree / "README")

    def test_cleanup_if_complete_retains_until_all_direct_members_pass(self):
        prepared = self.prepare()
        self.payload(self.run_ws("record-result"))
        data = json.loads(self.data.read_text())
        data["convoy"].update({"status": "closed", "metadata": {"gc.outcome": "pass"}})
        data["member-2"] = {"id": "member-2", "parent_convoy_id": "implementation-1", "status": "open", "metadata": {}}
        self.data.write_text(json.dumps(data))
        retained = self.payload(self.run_ws("cleanup-if-complete"))
        self.assertEqual(retained["cleanup"], "retained")
        self.assertTrue(pathlib.Path(prepared["worktree_path"]).is_dir())
        data["member-2"].update({"status": "closed", "metadata": {"gc.outcome": "pass"}})
        self.data.write_text(json.dumps(data))
        removed = self.payload(self.run_ws("cleanup-if-complete"))
        self.assertEqual(removed["cleanup"], "removed")
        self.assertFalse(pathlib.Path(prepared["worktree_path"]).exists())

    def test_cleanup_if_complete_fails_closed_on_malformed_member_list(self):
        self.prepare()
        self.payload(self.run_ws("record-result"))
        data = json.loads(self.data.read_text())
        data["malformed-member"] = {"id": "bad", "parent_convoy_id": 7, "metadata": {}}
        self.data.write_text(json.dumps(data))
        result = self.run_ws("cleanup-if-complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.state_path().exists())
    def test_cleanup_if_complete_rejects_missing_state_with_live_worktree(self):
        prepared = self.prepare()
        self.payload(self.run_ws("record-result"))
        self.state_path().unlink()
        result = self.run_ws("cleanup-if-complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(pathlib.Path(prepared["worktree_path"]).is_dir())

    def test_cleanup_if_complete_rejects_duplicate_direct_member_ids(self):
        prepared = self.prepare()
        self.payload(self.run_ws("record-result"))
        data = json.loads(self.data.read_text())
        member = {"id": "convoy-1", "parent_convoy_id": "implementation-1", "status": "closed", "metadata": {"gc.outcome": "pass"}}
        data["convoy"] = [member, {**member, "title": "duplicate"}]
        self.data.write_text(json.dumps(data))
        result = self.run_ws("cleanup-if-complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.state_path().exists())
        self.assertTrue(pathlib.Path(prepared["worktree_path"]).is_dir())

    def test_cleanup_if_complete_rejects_malformed_direct_member_id(self):
        prepared = self.prepare()
        self.payload(self.run_ws("record-result"))
        data = json.loads(self.data.read_text())
        data["convoy"].update({"id": "", "status": "closed", "metadata": {"gc.outcome": "pass"}})
        self.data.write_text(json.dumps(data))
        result = self.run_ws("cleanup-if-complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.state_path().exists())
        self.assertTrue(pathlib.Path(prepared["worktree_path"]).is_dir())

    def test_nested_parent_convoy_is_epic_owner_and_does_not_collide(self):
        data = json.loads(self.data.read_text())
        data["convoy"]["parent_convoy_id"] = "epic-1"
        data["owner"] = {"id": "epic-1", "parent_convoy_id": "implementation-1", "metadata": {}}
        data["implementation"] = {"id": "implementation-1", "parent_convoy_id": "", "metadata": {}}
        self.data.write_text(json.dumps(data))
        epic = self.prepare()
        self.payload(self.run_ws("record-result"))

        data = json.loads(self.data.read_text())
        data.update({
            "step-2": {"id": "step-2", "metadata": {"gc.root_bead_id": "root-2"}},
            "root-2": {"id": "root-2", "metadata": {
                "gc.input_convoy_id": "unit-2", "gc.drain_member_id": "member-2",
            }},
            "unit-2": {"id": "unit-2", "metadata": {
                "gc.synthetic_kind": "drain-unit-convoy", "gc.drain_member_id": "member-2",
            }},
            "member-2": {"id": "member-2", "parent_convoy_id": "epic-1", "metadata": {}},
            "step-3": {"id": "step-3", "metadata": {"gc.root_bead_id": "root-3"}},
            "root-3": {"id": "root-3", "metadata": {
                "gc.input_convoy_id": "unit-3", "gc.drain_member_id": "member-3",
            }},
            "unit-3": {"id": "unit-3", "metadata": {
                "gc.synthetic_kind": "drain-unit-convoy", "gc.drain_member_id": "member-3",
            }},
            "member-3": {"id": "member-3", "parent_convoy_id": "implementation-1", "metadata": {}},
        })
        self.data.write_text(json.dumps(data))
        next_epic = self.prepare("step-2", epic["input_oid"])
        convoy = self.prepare("step-3", epic["input_oid"])
        self.assertEqual(next_epic["worktree_path"], epic["worktree_path"])
        self.assertNotEqual(convoy["worktree_path"], epic["worktree_path"])

    def test_missing_or_malformed_parent_convoy_fails_closed(self):
        for value in (None, 7):
            with self.subTest(parent_convoy_id=value):
                data = json.loads(self.data.read_text())
                if value is None:
                    data["convoy"].pop("parent_convoy_id", None)
                else:
                    data["convoy"]["parent_convoy_id"] = value
                self.data.write_text(json.dumps(data))
                result = self.run_ws("prepare")
                self.assertNotEqual(result.returncode, 0)


    def test_recorded_host_mismatch_fails_closed(self):
        self.prepare()
        state_path = next((self.root / ".git" / "gc-workspace-state").rglob("*.json"))
        state = json.loads(state_path.read_text())
        state["host_id"] = "foreign-host"
        state_path.write_text(json.dumps(state))
        before = state_path.read_bytes()
        result = self.run_ws("path")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state_path.read_bytes(), before)

    def test_cleanup_removes_completed_workspace_and_state(self):
        prepared = self.prepare()
        state_path = self.state_path()
        self.payload(self.run_ws("record-result"))
        result = self.run_ws("cleanup")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(state_path.exists())
        self.assertFalse(pathlib.Path(prepared["worktree_path"]).exists())
        repeated = self.run_ws("cleanup")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)

    def test_cleanup_retains_incomplete_workspace(self):
        prepared = self.prepare()
        state_path = self.state_path()
        before = state_path.read_bytes()
        result = self.run_ws("cleanup")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertTrue(pathlib.Path(prepared["worktree_path"]).is_dir())

    def test_exact_preparing_partial_resumes(self):
        prepared = self.prepare()
        state_path = next((self.root / ".git" / "gc-workspace-state").rglob("*.json"))
        state = json.loads(state_path.read_text())
        state["phase"] = "preparing"
        state_path.write_text(json.dumps(state))
        resumed = self.prepare()
        self.assertEqual(resumed["phase"], "entry")
        self.assertEqual(resumed["input_oid"], prepared["input_oid"])
        self.assertEqual(resumed["worktree_path"], prepared["worktree_path"])

    def test_unknown_state_fails_without_mutation(self):
        prepared = self.prepare()
        worktree = pathlib.Path(prepared["worktree_path"])
        (worktree / "dirty").write_text("x\n")
        dirty_result = self.run_ws("verify-entry")
        self.assertNotEqual(dirty_result.returncode, 0)
        state_path = next((self.root / ".git" / "gc-workspace-state").rglob("*.json"))
        state = json.loads(state_path.read_text())
        state["phase"] = "mystery"
        state_path.write_text(json.dumps(state))
        before = state_path.read_bytes()
        result = self.run_ws("path")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state_path.read_bytes(), before)

    def test_repository_layouts_ordinary_control_and_true_bare(self):
        ordinary = self.prepare()
        self.assert_compact(ordinary)

        seed = pathlib.Path(self.tmp.name) / "seed.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(self.root), str(seed)], check=True)
        control = pathlib.Path(self.tmp.name) / "control"
        control.mkdir()
        subprocess.run(["git", "clone", "-q", "--bare", str(self.root), str(control / ".git")], check=True)
        self.root = control
        self.oid = subprocess.run(
            ["git", "--git-dir", str(control / ".git"), "rev-parse", "HEAD"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        controlled = self.payload(self.run_ws("prepare"))
        self.assert_compact(controlled)

        self.root = seed
        self.oid = subprocess.run(
            ["git", "--git-dir", str(seed), "rev-parse", "HEAD"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        rejected = self.run_ws("prepare")
        self.assertNotEqual(rejected.returncode, 0)
        parent = pathlib.Path(self.tmp.name) / "bare-worktrees"
        bare = self.payload(self.run_ws("prepare", workspace_parent=parent))
        self.assert_compact(bare)
        self.assertEqual(pathlib.Path(bare["worktree_path"]).parent, parent.resolve())

    def test_synthetic_anchor_and_lookup_shapes_fail_closed(self):
        data = json.loads(self.data.read_text())
        data["root"]["metadata"]["gc.drain_member_id"] = "member-1"
        data["convoy"] = {"id": "convoy-1", "metadata": {"gc.synthetic_kind": "drain-unit-convoy", "gc.drain_member_id": "member-1"}}
        data["member"] = {"id": "member-1", "parent_convoy_id": "implementation-1", "metadata": {}}
        self.data.write_text(json.dumps(data))
        synthetic = self.prepare()
        self.assert_compact(synthetic, anchor="member-1")
        result = self.payload(self.run_ws("record-result"))
        self.assert_compact(result, output=True, anchor="member-1")

        for bad in (
            [],
            [data["step"], data["step"]],
            {"_raw": "not-json"},
            7,
        ):
            with self.subTest(shape=bad):
                bad_data = dict(data)
                bad_data["step"] = bad
                self.data.write_text(json.dumps(bad_data))
                failure = self.run_ws("path")
                self.assertNotEqual(failure.returncode, 0)
        data["step"] = [data["step"]]
        self.data.write_text(json.dumps(data))
        one = self.payload(self.run_ws("result"))
        self.assertEqual(one["source_anchor_id"], "member-1")

    def test_dirty_tracked_untracked_and_operation_markers_fail_without_state_mutation(self):
        prepared = self.prepare()
        worktree = pathlib.Path(prepared["worktree_path"])
        state = self.state_path()
        (worktree / "README").write_text("tracked dirty\n")
        self.assert_failed_unchanged("verify-entry", state)
        subprocess.run(["git", "checkout", "--", "README"], cwd=worktree, check=True)
        (worktree / "untracked").write_text("dirty\n")
        self.assert_failed_unchanged("verify-entry", state)
        (worktree / "untracked").unlink()
        git_dir = pathlib.Path(subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-dir"], cwd=worktree,
            text=True, capture_output=True, check=True,
        ).stdout.strip())
        for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG"):
            with self.subTest(marker=marker):
                (git_dir / marker).write_text(self.oid + "\n")
                self.assert_failed_unchanged("verify-entry", state)
                (git_dir / marker).unlink()

    def test_dirty_submodule_is_rejected_without_state_mutation(self):
        child = pathlib.Path(self.tmp.name) / "child"
        child.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=child, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=child, check=True)
        subprocess.run(["git", "config", "user.name", "Workspace Tests"], cwd=child, check=True)
        (child / "file").write_text("one\n")
        subprocess.run(["git", "add", "file"], cwd=child, check=True)
        subprocess.run(["git", "commit", "-qm", "child"], cwd=child, check=True)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(child), "child")
        self.git("commit", "-qm", "submodule")
        self.oid = self.git("rev-parse", "HEAD").stdout.strip()
        prepared = self.prepare()
        worktree = pathlib.Path(prepared["worktree_path"])
        subprocess.run(["git", "-c", "protocol.file.allow=always", "submodule", "update", "--init"], cwd=worktree, check=True, capture_output=True)
        (worktree / "child" / "file").write_text("dirty\n")
        self.assert_failed_unchanged("verify-entry", self.state_path())

    def test_symlink_path_escape_and_held_lock_fail_closed(self):
        prepared = self.prepare()
        worktree = pathlib.Path(prepared["worktree_path"])
        state = self.state_path()
        before = state.read_bytes()
        lock = pathlib.Path(str(state) + ".lock")
        lock.mkdir()
        (lock / "owner.json").write_text(json.dumps({"pid": os.getpid(), "host": os.uname().nodename, "created": 0}))
        locked = self.run_ws("path")
        self.assertNotEqual(locked.returncode, 0)
        self.assertEqual(state.read_bytes(), before)
        (lock / "owner.json").unlink()
        lock.rmdir()

        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=self.root, check=True)
        target = pathlib.Path(self.tmp.name) / "escape"
        target.mkdir()
        worktree.symlink_to(target, target_is_directory=True)
        escaped = self.run_ws("path")
        self.assertNotEqual(escaped.returncode, 0)
        self.assertEqual(state.read_bytes(), before)

    def test_record_result_no_change_linear_and_non_linear_history(self):
        no_change = self.prepare()
        unchanged = self.payload(self.run_ws("record-result"))
        self.assert_compact(unchanged, output=True)
        self.assertEqual(unchanged["output_oid"], no_change["input_oid"])
        authoritative = self.payload(self.run_ws("result"))
        self.assertEqual(authoritative["source_anchor_id"], "convoy-1")

        data = json.loads(self.data.read_text())
        data.update({
            "step-2": {"id": "step-2", "metadata": {"gc.root_bead_id": "root-2"}},
            "root-2": {"id": "root-2", "metadata": {"gc.input_convoy_id": "convoy-2"}},
            "convoy-2": {"id": "convoy-2", "parent_convoy_id": "implementation-2", "metadata": {}},
            "owner-2": {"id": "implementation-2", "parent_convoy_id": "", "metadata": {}},
            "step-3": {"id": "step-3", "metadata": {"gc.root_bead_id": "root-3"}},
            "root-3": {"id": "root-3", "metadata": {"gc.input_convoy_id": "convoy-3"}},
            "convoy-3": {"id": "convoy-3", "parent_convoy_id": "implementation-3", "metadata": {}},
            "owner-3": {"id": "implementation-3", "parent_convoy_id": "", "metadata": {}},
        })
        self.data.write_text(json.dumps(data))
        linear = self.prepare("step-2")
        linear_wt = pathlib.Path(linear["worktree_path"])
        (linear_wt / "linear").write_text("commit\n")
        subprocess.run(["git", "add", "linear"], cwd=linear_wt, check=True)
        subprocess.run(["git", "commit", "-qm", "linear"], cwd=linear_wt, check=True)
        linear_result = self.payload(self.run_ws("record-result", "step-2"))
        self.assert_compact(linear_result, output=True, anchor="convoy-2")
        self.assertNotEqual(linear_result["output_oid"], linear["input_oid"])

        merged = self.prepare("step-3")
        merge_wt = pathlib.Path(merged["worktree_path"])
        subprocess.run(["git", "checkout", "-qb", "side"], cwd=merge_wt, check=True)
        (merge_wt / "side").write_text("side\n")
        subprocess.run(["git", "add", "side"], cwd=merge_wt, check=True)
        subprocess.run(["git", "commit", "-qm", "side"], cwd=merge_wt, check=True)
        side_oid = subprocess.run(["git", "rev-parse", "HEAD"], cwd=merge_wt, text=True, capture_output=True, check=True).stdout.strip()
        subprocess.run(["git", "checkout", "--detach", merged["input_oid"]], cwd=merge_wt, check=True, capture_output=True)
        (merge_wt / "main").write_text("main\n")
        subprocess.run(["git", "add", "main"], cwd=merge_wt, check=True)
        subprocess.run(["git", "commit", "-qm", "main"], cwd=merge_wt, check=True)
        subprocess.run(["git", "merge", "--no-ff", "-qm", "merge", side_oid], cwd=merge_wt, check=True)
        state3 = next(path for path in (self.root / ".git" / "gc-workspace-state").rglob("*.json") if json.loads(path.read_text())["source_anchor_id"] == "convoy-3")
        before = state3.read_bytes()
        rejected = self.run_ws("record-result", "step-3")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(state3.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
