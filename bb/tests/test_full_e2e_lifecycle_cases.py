"""Process guards use fresh child fixtures; these are not BB/GC E2E results."""

import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from full_e2e_lifecycle_cases import (CASE_DEPENDENCIES, LifecycleCases, canonical_entry_token, canonical_executable_prefix, children, inspect_process, signal_verified,
                                     verify_one_prompt, verify_systemd_manager, visible_failure_fragment)
from live_lifecycle import LifecycleFailure
from live_assertions import AcceptanceFailure


class RetainedProcessGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bb-live-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.sentinel = self.root / "retained-evidence.txt"
        self.sentinel.write_text("untouched\n")
        self.required = {"BB_DATA_DIR": str(self.root / "bb-data"), "GC_HOME": str(self.root / "gc-home")}
        self.process = subprocess.Popen([str(Path(sys.executable).resolve()), "-c", "import time; print('READY', flush=True); time.sleep(300)"],
            env={**os.environ, **self.required}, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.addCleanup(self.cleanup_child)
        self.assertEqual(self.process.stdout.readline(), b"READY\n")

    def cleanup_child(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=3)
        self.process.stdout.close()

    def identity(self):
        return inspect_process(self.process.pid, self.required, command_contains="time.sleep(300)", parent=os.getpid())

    def test_exact_child_is_signaled_and_its_state_files_survive(self):
        identity = self.identity()
        self.assertEqual(identity["parent_pid"], os.getpid())
        self.assertIn(self.process.pid, children(os.getpid()))
        signal_verified(identity, self.required, command_contains="time.sleep(300)", parent=os.getpid())
        self.assertLess(self.process.wait(timeout=3), 0)
        self.assertEqual(self.sentinel.read_text(), "untouched\n")

    def test_changed_birth_identity_does_not_signal_a_live_child(self):
        identity = self.identity()
        identity["birth"] = "another-process-generation"
        with self.assertRaisesRegex(LifecycleFailure, "changed or stale"):
            signal_verified(identity, self.required)
        self.assertIsNone(self.process.poll())

    def test_wrong_state_parent_or_command_is_rejected(self):
        for kwargs in ({"required_env": {**self.required, "GC_HOME": str(self.root / "other")}},
                       {"parent": 1}, {"command_contains": "unrelated-service-command"}):
            args = {"required_env": self.required, "parent": os.getpid(), "command_contains": "time.sleep(300)"}
            args.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(LifecycleFailure):
                inspect_process(self.process.pid, **args)
        self.assertIsNone(self.process.poll())

    def test_self_or_unspecified_scope_cannot_be_a_target(self):
        with self.assertRaisesRegex(LifecycleFailure, "non-self"):
            inspect_process(os.getpid(), self.required)
        with self.assertRaisesRegex(LifecycleFailure, "isolated environment"):
            inspect_process(self.process.pid, {})

    def test_missing_advisory_runtime_record_uses_actual_isolated_process_without_recreating_record(self):
        script = self.root / "bb-app-fixture.py"
        script.write_text("import time; print('READY', flush=True); time.sleep(300)\n")
        child = subprocess.Popen([sys.executable, str(script)], env={**os.environ, **self.required}, stdout=subprocess.PIPE)
        try:
            self.assertEqual(child.stdout.readline(), b"READY\n")
            cases = LifecycleCases.__new__(LifecycleCases)
            cases.runner = SimpleNamespace(env=self.required, manifest={"appPid": child.pid,
                "commands": {"app": str(script)}})
            identity, env = cases.app_identity()
            self.assertEqual(identity["pid"], child.pid)
            self.assertEqual(env, {"BB_DATA_DIR": self.required["BB_DATA_DIR"]})
            self.assertFalse((Path(self.required["BB_DATA_DIR"]) / "bb-app-runtime.json").exists())
            cases.runner.env = {**self.required, "BB_DATA_DIR": str(self.root / "unrelated")}
            with self.assertRaisesRegex(LifecycleFailure, "environment"):
                cases.app_identity()
            self.assertIsNone(child.poll())
        finally:
            child.kill(); child.wait(timeout=3); child.stdout.close()

    def test_bridge_uses_gc_state_and_verified_host_when_bb_scrubs_data_dir(self):
        env = {**os.environ, "BB_DATA_DIR": str(self.root / "bb-data"),
               "GC_BB_CONFIG": str(self.root / "config/bb.json"), "XDG_STATE_HOME": str(self.root / "state")}
        bridge = self.root / "bb-provider-bridge-worker.mjs"
        bridge.write_text("import time; time.sleep(300)\n")
        host = subprocess.Popen([sys.executable, "-c",
            "import os, subprocess, sys; env=dict(os.environ); env.pop('BB_DATA_DIR', None); "
            "child=subprocess.Popen([sys.executable, sys.argv[1]], env=env); "
            "print(child.pid, flush=True); child.wait()", str(bridge)],
            env=env, stdout=subprocess.PIPE, text=True)
        bridge_pid = int(host.stdout.readline())
        try:
            owner_path = Path(env["XDG_STATE_HOME"]) / "gascity/bb/sessions" / (hashlib.sha256(b"thread").hexdigest() + ".json.lock/owner.json")
            owner_path.parent.mkdir(parents=True)
            owner_path.write_text(json.dumps({"hostname": socket.gethostname(), "pid": bridge_pid, "token": "test-owner"}))
            cases = LifecycleCases.__new__(LifecycleCases)
            cases.runner = SimpleNamespace(env=env)
            cases.bb_child = Mock(side_effect=lambda kind: (
                inspect_process(host.pid, {"BB_DATA_DIR": cases.runner.env["BB_DATA_DIR"]}), {}, "", {}))
            conversation = {"harness": SimpleNamespace(thread_id="thread")}
            identity, required = cases.bridge_identity(conversation)
            self.assertEqual(identity["pid"], bridge_pid)
            self.assertEqual(identity["parent_pid"], host.pid)
            self.assertEqual(required, {key: env[key] for key in ("GC_BB_CONFIG", "XDG_STATE_HOME")})
            for key in (*required, "BB_DATA_DIR"):
                cases.runner.env = {**env, key: str(self.root / "different")}
                with self.subTest(key=key), self.assertRaises((LifecycleFailure, FileNotFoundError)):
                    cases.bridge_identity(conversation)
            cases.runner.env = env
            cases.bb_child.side_effect = None
            cases.bb_child.return_value = ({"pid": self.process.pid}, {}, "", {})
            with self.assertRaises(LifecycleFailure):
                cases.bridge_identity(conversation)
        finally:
            os.kill(bridge_pid, 9)
            host.wait(timeout=3)
            host.stdout.close()


class LinuxProcessInspectionRaceTests(unittest.TestCase):
    def inspect(self, missing_file, error, *, command="owned-worker", state="S",
                environ=b"GC_HOME=/tmp/owned-gc\0", uid=None, parent=123455, stat_sequence=None):
        uid = os.getuid() if uid is None else uid
        observed = SimpleNamespace(returncode=0, stdout=f"123456 {parent} {uid} Sat Sep 19 12:00:00 2026 {command}\n")
        fields = [state, *(["0"] * 18), "90069604"]
        with patch("full_e2e_lifecycle_cases.sys.platform", "linux"), \
             patch("full_e2e_lifecycle_cases.subprocess.run", return_value=observed), \
             patch.object(Path, "read_bytes", return_value=environ,
                          side_effect=error if missing_file == "environ" else None), \
             patch.object(Path, "read_text", return_value="123456 (owned-worker) " + " ".join(fields),
                          side_effect=error if missing_file == "stat" else stat_sequence):
            return inspect_process(123456, {"GC_HOME": "/tmp/owned-gc"},
                                   command_contains="owned-worker", parent=123455)

    def test_kernel_zombie_is_exited_before_defunct_command_or_empty_environment_checks(self):
        for changed in ({"command": "[node] <defunct>"}, {"environ": b""}):
            with self.subTest(changed=changed), self.assertRaises(ProcessLookupError):
                self.inspect(None, None, state="Z", **changed)

    def test_zombie_does_not_bypass_pid_owner_or_parent_validation(self):
        for changed in ({"uid": os.getuid() + 1}, {"parent": 999999}):
            with self.subTest(changed=changed), self.assertRaises(LifecycleFailure):
                self.inspect(None, None, state="Z", command="[node] <defunct>", environ=b"", **changed)

    def test_zombie_environment_permission_denial_is_not_read_as_a_live_permission_failure(self):
        with self.assertRaises(ProcessLookupError):
            self.inspect("environ", PermissionError(errno.EACCES, "zombie environment unavailable"), state="Z")

    def test_transition_to_zombie_during_environment_read_requires_same_birth(self):
        def proc_stat(state, birth):
            return "123456 (owned-worker) " + " ".join([state, *(["0"] * 18), birth])
        for error in (None, PermissionError(errno.EACCES, "zombie environment unavailable")):
            with self.subTest(error=error), self.assertRaises(ProcessLookupError):
                self.inspect("environ", error, environ=b"", stat_sequence=[proc_stat("S", "100"), proc_stat("Z", "100")])
        with self.assertRaisesRegex(LifecycleFailure, "changed"):
            self.inspect("environ", PermissionError(errno.EACCES, "denied"),
                         stat_sequence=[proc_stat("S", "100"), proc_stat("Z", "200")])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux /proc zombie contract")
    def test_real_owned_unreaped_child_is_classified_as_exited(self):
        with tempfile.TemporaryDirectory(prefix="bb-zombie-fixture-") as root:
            required = {"BB_E2E_ZOMBIE_FIXTURE": root}
            child = subprocess.Popen([sys.executable, "-c", "import sys; print('READY', flush=True); sys.stdin.read(1)"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, env={**os.environ, **required})
            try:
                self.assertEqual(child.stdout.readline(), b"READY\n")
                inspect_process(child.pid, required, command_contains="sys.stdin.read(1)", parent=os.getpid())
                child.stdin.close()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    state = (Path("/proc") / str(child.pid) / "stat").read_text().rsplit(")", 1)[1].split()[0]
                    if state == "Z":
                        break
                    time.sleep(.01)
                else:
                    self.fail("Owned child did not become an unreaped zombie")
                with self.assertRaises(ProcessLookupError):
                    inspect_process(child.pid, required, command_contains="sys.stdin.read(1)", parent=os.getpid())
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
                child.stdout.close()
                if not child.stdin.closed:
                    child.stdin.close()

    def test_exit_between_ps_and_either_proc_read_is_process_lookup_error(self):
        for name in ("environ", "stat"):
            with self.subTest(name=name), self.assertRaises(ProcessLookupError):
                self.inspect(name, FileNotFoundError(errno.ENOENT, "process exited", f"/proc/123456/{name}"))

    def test_permission_and_other_proc_io_errors_remain_fail_closed(self):
        for name in ("environ", "stat"):
            for error in (PermissionError(errno.EACCES, "permission denied"), OSError(errno.EIO, "read failed")):
                with self.subTest(name=name, errno=error.errno), self.assertRaises(type(error)) as caught:
                    self.inspect(name, error)
                self.assertIs(caught.exception, error)

    def test_await_exit_accepts_only_a_disappeared_process(self):
        cases = LifecycleCases.__new__(LifecycleCases)
        cases.fault = SimpleNamespace(poll=lambda label, predicate: self.assertTrue(predicate()))
        with patch("full_e2e_lifecycle_cases.inspect_process", side_effect=ProcessLookupError(123456)):
            cases.await_exit({"pid": 123456, "birth": "90069604"}, {"GC_HOME": "/tmp/owned-gc"})
        with patch("full_e2e_lifecycle_cases.inspect_process", side_effect=PermissionError(errno.EACCES, "denied")), \
             self.assertRaises(PermissionError):
            cases.await_exit({"pid": 123456, "birth": "90069604"}, {"GC_HOME": "/tmp/owned-gc"})

    def test_disappearance_during_signal_revalidation_never_sends_a_signal(self):
        with patch("full_e2e_lifecycle_cases.sys.platform", "darwin"), \
             patch("full_e2e_lifecycle_cases.inspect_process", side_effect=ProcessLookupError(123456)), \
             patch("full_e2e_lifecycle_cases.os.kill") as kill:
            with self.assertRaises(ProcessLookupError):
                signal_verified({"pid": 123456, "birth": "90069604"}, {"GC_HOME": "/tmp/owned-gc"})
            kill.assert_not_called()


class SystemdManagerGuardTests(unittest.TestCase):
    def test_manager_discovery_accepts_direct_scope_and_rejects_unknown_manager(self):
        cases = LifecycleCases.__new__(LifecycleCases)
        cases.guard = Mock()
        cases.runner = SimpleNamespace(env={"GC_HOME": "/tmp/fixture/gc-home"}, command=Mock())
        identity = {"pid": 123456, "uid": os.getuid()}
        for group in ("/", f"/user.slice/user-{os.getuid()}.slice/session-42.scope"):
            with self.subTest(group=group), patch("full_e2e_lifecycle_cases.sys.platform", "linux"), \
                 patch("full_e2e_lifecycle_cases.inspect_process", return_value=identity), \
                 patch.object(Path, "stat", return_value=SimpleNamespace(st_uid=os.getuid())), \
                 patch.object(Path, "read_text", return_value="0::" + group):
                self.assertIsNone(cases.gc_manager(identity, "/unused"))
        with patch("full_e2e_lifecycle_cases.sys.platform", "linux"), \
             patch("full_e2e_lifecycle_cases.inspect_process", return_value=identity), \
             patch.object(Path, "stat", return_value=SimpleNamespace(st_uid=os.getuid())), \
             patch.object(Path, "read_text", return_value="0::/system.slice/unrelated.service"), \
             self.assertRaises(LifecycleFailure):
            cases.gc_manager(identity, "/unused")
        cases.runner.command.assert_not_called()
        with patch("full_e2e_lifecycle_cases.inspect_process", return_value={**identity, "birth": "changed"}), \
             self.assertRaisesRegex(LifecycleFailure, "identity changed"):
            cases.gc_manager(identity, "/unused")

    def test_mac_direct_pid_has_no_launchd_owner_and_managed_pid_fails_closed(self):
        cases = LifecycleCases.__new__(LifecycleCases)
        cases.guard = Mock()
        cases.runner = SimpleNamespace(env={"GC_HOME": "/tmp/fixture/gc-home"}, command=Mock(return_value="PID Status Label\n- 0 other\n"))
        identity = {"pid": 123456, "uid": os.getuid()}
        with patch("full_e2e_lifecycle_cases.sys.platform", "darwin"), \
             patch("full_e2e_lifecycle_cases.inspect_process", return_value=identity):
            self.assertIsNone(cases.gc_manager(identity, "/unused"))
            cases.runner.command.return_value = "PID Status Label\n123456 0 owned-gc-service\n"
            with self.assertRaisesRegex(LifecycleFailure, "launchd-managed"):
                cases.gc_manager(identity, "/unused")

    def fixture(self, root):
        binary = root / "gc"
        binary.write_text("isolated executable")
        unit = "gascity-supervisor-gc-home-fixture.service"
        group = f"/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice/{unit}"
        fragment = f'[Service]\nExecStart={binary} supervisor run\nEnvironment=GC_HOME="{root / "gc-home"}"\nEnvironment=GC_SUPERVISOR_PRESERVE_SESSIONS_ON_SIGNAL="1"\n'
        properties = {"Id": unit, "MainPID": "123456", "ActiveState": "active", "ControlGroup": group,
                      "KillMode": "process", "Restart": "always", "DropInPaths": "", "FragmentPath": str(root / unit),
                      "ExecStart": f"{{ path={binary} ; argv[]={binary} supervisor run ; ignore_errors=no ; }}"}
        args = dict(unit=unit, pid=123456, gc_home=root / "gc-home", binary=binary,
                    fragment=fragment, uid=os.getuid(), cgroup=group)
        return properties, args

    def test_exact_unit_requires_owned_home_command_and_preserving_manager_settings(self):
        with tempfile.TemporaryDirectory(prefix="bb-manager-guard-") as name:
            properties, args = self.fixture(Path(name).resolve())
            self.assertEqual(verify_systemd_manager(properties, **args)["unit"], args["unit"])
            for key, value in (("Id", "production.service"), ("MainPID", "555"), ("ControlGroup", "/other"),
                               ("ActiveState", "inactive"), ("KillMode", "control-group"), ("Restart", "no"),
                               ("DropInPaths", "/unreviewed/override.conf"), ("ExecStart", "{ path=/other ; argv[]=/other supervisor run ; }")):
                with self.subTest(key=key), self.assertRaises(LifecycleFailure):
                    verify_systemd_manager({**properties, key: value}, **args)
            for changed in (args["fragment"].replace(str(args["gc_home"]), "/home/person/.gc"),
                            args["fragment"].replace('SIGNAL="1"', 'SIGNAL="0"'),
                            args["fragment"] + "EnvironmentFile=/unreviewed\n"):
                with self.subTest(fragment=changed), self.assertRaises(LifecycleFailure):
                    verify_systemd_manager(properties, **{**args, "fragment": changed})

    def test_foreign_user_cgroup_and_command_suffix_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="bb-manager-guard-") as name:
            properties, args = self.fixture(Path(name).resolve())
            with self.assertRaises(LifecycleFailure):
                verify_systemd_manager(properties, **{**args, "uid": os.getuid() + 1})
            with self.assertRaises(LifecycleFailure):
                verify_systemd_manager(properties, **{**args, "cgroup": "/another/user/unit"})
            with self.assertRaises(LifecycleFailure):
                verify_systemd_manager({**properties, "ExecStart": properties["ExecStart"].replace("supervisor run ;", "supervisor run --extra ;")}, **args)

    def lifecycle_fixture(self, root):
        binary = root / "gc"
        binary.write_bytes(b"test candidate")
        manager = {"unit": "gascity-supervisor-gc-home-fixture.service", "main_pid": 123456,
                   "control_group": "/fixture", "fragment_sha256": "same", "executable": str(binary)}
        cases = LifecycleCases.__new__(LifecycleCases)
        cases.runner = SimpleNamespace(root=root, manifest={"commands": {"gc": str(binary)},
            "gcBinarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "gcCommit": "abcdef1234567890",
            "versions": {"gc": "candidate"}}, command=Mock(return_value=""), recall=Mock(return_value={"recalled": True}))
        artifacts = root / "artifacts"
        artifacts.mkdir()
        cases.evidence_dir = Mock(return_value=artifacts)
        cases.conversation = Mock(return_value={})
        cases.native_pane = Mock(return_value={"pane_pid": 99})
        target, replacement = {"pid": 123456}, {"pid": 123457}
        cases.gc_identity = Mock(side_effect=[(target, {"GC_HOME": str(root)}, "gc supervisor run"),
                                              (replacement, {"GC_HOME": str(root)}, "gc supervisor run")])
        cases.gc_manager = Mock(side_effect=lambda identity, binary: {**manager, "main_pid": identity["pid"]})
        cases.systemd_properties = Mock(return_value={"ActiveState": "inactive", "MainPID": "0"})
        cases.verify_running_executable = Mock()
        cases.await_exit = Mock()
        cases.fault = SimpleNamespace(poll=lambda label, predicate: predicate(),
            read_gc=Mock(return_value={"startup": {"ready": True}, "version": "candidate", "build_id": "abcdef123456"}))
        return cases, manager

    def test_controller_crash_uses_manager_restart_without_competing_bare_start(self):
        with tempfile.TemporaryDirectory(prefix="bb-manager-action-") as name:
            cases, _ = self.lifecycle_fixture(Path(name).resolve())
            with patch("full_e2e_lifecycle_cases.signal_verified") as signal:
                cases.gc_replace(False)
            signal.assert_called_once()
            self.assertFalse(any("start" in call.args for call in cases.runner.command.call_args_list))

    def test_binary_replacement_stops_only_verified_unit_before_direct_copy_start(self):
        with tempfile.TemporaryDirectory(prefix="bb-manager-action-") as name:
            cases, manager = self.lifecycle_fixture(Path(name).resolve())
            with patch("full_e2e_lifecycle_cases.signal_verified") as signal:
                cases.gc_replace(True)
            signal.assert_not_called()
            calls = [call.args for call in cases.runner.command.call_args_list]
            self.assertEqual(calls[0], ("systemctl", "--user", "stop", manager["unit"]))
            self.assertEqual(calls[1][0:2], ("env", "GC_SUPERVISOR_PRESERVE_SESSIONS_ON_SIGNAL=1"))
            self.assertEqual(calls[1][-2:], ("supervisor", "start"))
            self.assertNotEqual(str(calls[1][2]), cases.runner.manifest["commands"]["gc"])
            cases.verify_running_executable.assert_called_once()

    def test_direct_supervisor_remains_supported_for_crash_and_binary_replacement(self):
        for graceful in (False, True):
            with self.subTest(graceful=graceful), tempfile.TemporaryDirectory(prefix="bb-direct-action-") as name:
                cases, _ = self.lifecycle_fixture(Path(name).resolve())
                cases.gc_manager.side_effect = None
                cases.gc_manager.return_value = None
                with patch("full_e2e_lifecycle_cases.signal_verified") as signal:
                    cases.gc_replace(graceful)
                self.assertEqual(signal.call_args.kwargs["graceful"], graceful)
                calls = [call.args for call in cases.runner.command.call_args_list]
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][-2:], ("supervisor", "start"))
                self.assertNotIn("systemctl", calls[0])
                if graceful:
                    self.assertNotEqual(str(calls[0][2]), cases.runner.manifest["commands"]["gc"])

    def test_changed_manager_identity_cannot_signal_or_stop_a_service(self):
        with tempfile.TemporaryDirectory(prefix="bb-manager-action-") as name:
            cases, manager = self.lifecycle_fixture(Path(name).resolve())
            cases.gc_manager.side_effect = [manager, {**manager, "fragment_sha256": "changed"}]
            with patch("full_e2e_lifecycle_cases.signal_verified") as signal, self.assertRaisesRegex(LifecycleFailure, "changed"):
                cases.gc_replace(True)
            signal.assert_not_called()
            cases.runner.command.assert_not_called()


class LifecycleEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.prompt = "Remember exact full\nmultiline prompt"
        self.forwarded = "BB context\n" + self.prompt
        self.receipt = {"turn": {"baselineMessageIds": [], "messageDigest": hashlib.sha256(self.forwarded.encode()).hexdigest()}}
        self.frame = {"schema_version": "session.structured.v1", "history": {"tail_state": {"activity": "idle"}},
                      "structured_messages": [{"id": "one", "role": "user", "status": "final", "user_prompt": {"text": self.forwarded}}]}

    def test_recovery_requires_one_complete_independent_user_prompt(self):
        self.assertEqual(verify_one_prompt(self.frame, self.receipt, self.prompt)["gc_user_message_id"], "one")
        duplicate = copy.deepcopy(self.frame)
        duplicate["structured_messages"].append({**duplicate["structured_messages"][0], "id": "duplicate"})
        with self.assertRaisesRegex((LifecycleFailure, AcceptanceFailure), "duplicated|exactly one"):
            verify_one_prompt(duplicate, self.receipt, self.prompt)

    def test_failed_bridge_needs_real_failure_and_cannot_also_claim_success(self):
        events = [{"type": "turn/completed", "data": {"status": "failed", "error": {"message": "Provider bridge exited unexpectedly"}}}]
        self.assertEqual(visible_failure_fragment(events), "Provider bridge exited unexpectedly")
        self.assertIsNone(visible_failure_fragment([{"type": "turn/started"}]))
        with self.assertRaisesRegex(LifecycleFailure, "unexpectedly published success"):
            visible_failure_fragment([{"type": "turn/completed", "data": {"status": "completed"}}])
        with self.assertRaisesRegex(LifecycleFailure, "unexpectedly published success"):
            visible_failure_fragment(events + [{"type": "turn/completed", "data": {"status": "completed"}}])

    def test_all_lifecycle_cases_declare_the_verified_native_conversation_prerequisite(self):
        self.assertEqual(len(CASE_DEPENDENCIES), 6)
        self.assertTrue(all(dependencies == ("native.personal",) for dependencies in CASE_DEPENDENCIES.values()))

    def test_gc_identity_resolves_executable_alias_but_preserves_observed_command_for_signaling(self):
        with tempfile.TemporaryDirectory(prefix="bb-process-path-") as name:
            root = Path(name).resolve()
            binary = root / "gc-real"
            binary.write_text("owned fixture executable")
            alias = root / "gc-alias"
            alias.symlink_to(binary)
            observed = str(alias) + " supervisor run"
            self.assertEqual(canonical_executable_prefix(observed, binary, "supervisor", "run"), observed)
            self.assertEqual(canonical_entry_token(str(binary) + " " + str(alias) + " --data-dir owned", binary), str(binary))
            for wrong in (str(alias) + " supervisor stop", str(alias) + " city run", "relative-gc supervisor run"):
                with self.assertRaises(LifecycleFailure):
                    canonical_executable_prefix(wrong, binary, "supervisor", "run")
            other = root / "other-gc"
            other.write_text("another fixture executable")
            with self.assertRaises(LifecycleFailure):
                canonical_executable_prefix(str(other) + " supervisor run", binary, "supervisor", "run")


if __name__ == "__main__":
    unittest.main()
