from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "gascity/roles/assets/scripts/p0_notice.py"


class NoticeControlPlaneTests(unittest.TestCase):
    def run_notice(self, *args: str, index: pathlib.Path | None, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ | {"PATH": "/nonexistent"} | (extra_env or {})
        if index is not None:
            env["GC_P0_NOTICE_INDEX"] = str(index)
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, env=env)

    def fake_gc(self, directory: pathlib.Path, program: str) -> tuple[pathlib.Path, pathlib.Path]:
        fake_bin = directory / "bin"
        fake_bin.mkdir()
        calls = directory / "calls"
        command = fake_bin / "gc"
        command.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$GC_P0_CALLS\"\n" + program)
        command.chmod(0o755)
        return fake_bin, calls

    def test_invalid_arguments_are_rejected_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_notice("send", "--to-role", "bad role", "--work-ref", "gp-1",
                "--state-fingerprint", "head", "--subject", "x", "--message", "x",
                index=pathlib.Path(directory) / "index.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid role", result.stderr)

    def test_ack_nonrecipient_does_not_mutate_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = pathlib.Path(directory) / "index.json"
            nid = "a" * 24
            index.write_text(json.dumps({"schema_version": 1, "notices": {nid: {
                "recipient_role": "gastown.mayor", "disposition": "accepted"}}}))
            result = self.run_notice("ack", nid, "--disposition", "accepted", index=index,
                extra_env={"GC_CANONICAL_ROLE": "gastown.witness"})
            record = json.loads(index.read_text())["notices"][nid]
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("processed_at", record)

    def test_ack_rejects_a_spoofed_actor_role_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = pathlib.Path(directory) / "index.json"
            nid = "a" * 24
            index.write_text(json.dumps({"schema_version": 1, "notices": {nid: {
                "recipient_role": "gastown.mayor", "disposition": "accepted", "mail_id": "mail-1"}}}))
            result = self.run_notice("ack", nid, "--actor-role", "gastown.mayor",
                "--disposition", "dismissed", index=index)
            record = json.loads(index.read_text())["notices"][nid]
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("processed_at", record)

    def test_default_index_is_scoped_to_the_city_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            city = pathlib.Path(directory) / "city"
            result = self.run_notice("send", "--to-role", "gastown.mayor", "--work-ref", "gp-1",
                "--state-fingerprint", "head", "--subject", "x", "--message", "x",
                index=None,
                extra_env={"GC_CITY": str(city)})
            self.assertNotEqual(result.returncode, 0)  # PATH contains no gc, but the scoped cache is created first.
            self.assertTrue((city / ".gc" / "runtime" / "p0-notices.json").is_file())

    def test_accepted_but_unprocessed_notice_remains_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = pathlib.Path(directory) / "index.json"
            nid = "f" * 24
            index.write_text(json.dumps({"schema_version": 1, "notices": {nid: {
                "recipient_role": "gastown.mayor", "work_reference": "gp-1",
                "state_fingerprint": "head", "disposition": "accepted",
                "occurrence_count": 1}}}))
            # Use the script's deterministic id so the second send reaches the
            # existing durable receipt rather than attempting a new gc process.
            import hashlib
            nid = hashlib.sha256(b"gastown.mayor\0gp-1\0head").hexdigest()[:24]
            record = json.loads(index.read_text())["notices"].pop("f" * 24)
            index.write_text(json.dumps({"schema_version": 1, "notices": {nid: record}}))
            result = self.run_notice("send", "--to-role", "gastown.mayor", "--work-ref", "gp-1",
                "--state-fingerprint", "head", "--subject", "x", "--message", "x", index=index)
            record = json.loads(index.read_text())["notices"][nid]
        self.assertEqual(result.returncode, 0)
        self.assertEqual(record["occurrence_count"], 2)

    def test_ack_requires_a_durable_mail_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = pathlib.Path(directory) / "index.json"
            nid = "a" * 24
            index.write_text(json.dumps({"schema_version": 1, "notices": {nid: {
                "recipient_role": "gastown.mayor", "disposition": "accepted"}}}))
            result = self.run_notice("ack", nid, "--disposition", "accepted", index=index,
                extra_env={"GC_CANONICAL_ROLE": "gastown.mayor"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("no durable mail receipt", result.stderr)

    def test_send_captures_messages_receipt_and_acknowledges_it_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            fake_bin, calls = self.fake_gc(root, """
case \"$1 $2\" in
  b?*) printf '[]\\n' ;;
  \"mail send\") printf '%s\\n' '{"messages":[{"id":"mail-123"}],"count":1}' ;;
  \"mail read\"|\"mail archive\") : ;;
  *) echo "unexpected: $*" >&2; exit 2 ;;
esac
""")
            env = {"PATH": f"{fake_bin}:/usr/bin:/bin", "GC_P0_CALLS": str(calls)}
            sent = self.run_notice("send", "--to-role", "gastown.mayor", "--work-ref", "gp-1",
                "--state-fingerprint", "head", "--subject", "x", "--message", "x", index=root / "index.json", extra_env=env)
            nid = json.loads(sent.stdout)["notice_id"]
            acked = self.run_notice("ack", nid, "--disposition", "accepted", index=root / "index.json",
                extra_env=env | {"GC_CANONICAL_ROLE": "gastown.mayor"})
            record = json.loads((root / "index.json").read_text())["notices"][nid]
            logged_calls = calls.read_text().splitlines()
        self.assertEqual(sent.returncode, 0, sent.stderr + sent.stdout + repr(logged_calls))
        self.assertEqual(acked.returncode, 0, acked.stderr)
        self.assertEqual(record["mail_id"], "mail-123")
        self.assertIn("processed_at", record)
        self.assertEqual(logged_calls, [
            "b" + "d query --json --all title=notice:" + nid,
            "mail send gastown.mayor --notify --json -s [notice:" + nid + "] x -m x",
            "mail read mail-123",
            "mail archive mail-123",
        ])

    def test_send_refuses_accepted_state_without_a_durable_receipt_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            fake_bin, calls = self.fake_gc(root, """
case \"$1 $2\" in
  b?*) printf '[]\\n' ;;
  \"mail send\") printf '%s\\n' '{"messages":[{}],"count":1}' ;;
esac
""")
            result = self.run_notice("send", "--to-role", "gastown.mayor", "--work-ref", "gp-1",
                "--state-fingerprint", "head", "--subject", "x", "--message", "x", index=root / "index.json",
                extra_env={"PATH": f"{fake_bin}:/usr/bin:/bin", "GC_P0_CALLS": str(calls)})
            nid = json.loads(result.stdout)["notice_id"]
            record = json.loads((root / "index.json").read_text())["notices"][nid]
        self.assertEqual(result.returncode, 1)
        self.assertEqual(record["disposition"], "undeliverable")
        self.assertNotIn("accepted_at", record)

    def test_reconcile_reads_configured_roles_without_waking_or_releasing_held_roles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            index = root / "index.json"
            stale = "2000-01-01T00:00:00Z"
            index.write_text(json.dumps({"schema_version": 1, "notices": {
                "active": {"recipient_role": "gastown.mayor", "queued_at": stale, "disposition": "sending"},
                "dormant": {"recipient_role": "gascity-packs/gastown.witness", "queued_at": stale, "disposition": "sending"},
                "held": {"recipient_role": "gascity-packs/gastown.refinery", "queued_at": stale, "disposition": "sending"},
                "quarantined": {"recipient_role": "gascity-packs/gastown.polecat", "queued_at": stale, "disposition": "sending"},
                "retired": {"recipient_role": "retired.role", "queued_at": stale, "disposition": "sending"},
                "unknown": {"recipient_role": "unknown.role", "queued_at": stale, "disposition": "sending"},
            }}))
            fake_bin, calls = self.fake_gc(root, """
case \"$1 $2 $3\" in
  \"agent list --json\") printf '%s\\n' '{"agents":[
    {"qualified_name":"gastown.mayor","suspended":false},
    {"qualified_name":"gascity-packs/gastown.witness","suspended":false},
    {"qualified_name":"gascity-packs/gastown.refinery","suspended":true},
    {"qualified_name":"gascity-packs/gastown.polecat","state":"quarantined"},
    {"qualified_name":"successor.role","suspended":false}
  ]}' ;;
  \"mail send human\") printf '%s\\n' '{"messages":[{"id":"human-1"}],"count":1}' ;;
  *) echo "unexpected: $*" >&2; exit 2 ;;
esac
""")
            env = {"PATH": f"{fake_bin}:/usr/bin:/bin", "GC_P0_CALLS": str(calls)}
            first = self.run_notice("reconcile", index=index, extra_env=env)
            second = self.run_notice("reconcile", index=index, extra_env=env)
            records = json.loads(index.read_text())["notices"]
            logged_calls = calls.read_text().splitlines()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        for nid in ("active", "dormant", "held", "quarantined"):
            self.assertEqual(records[nid]["disposition"], "sending")
        for nid in ("retired", "unknown"):
            self.assertEqual(records[nid]["disposition"], "escalated")
            self.assertEqual(logged_calls.count(
                f"mail send human --notify --json -s [notice:{nid}] role unavailable -m {records[nid]['recipient_role']}",
            ), 1)
        self.assertTrue(all(not call.startswith("session wake") for call in logged_calls))
        self.assertNotIn("resolve-role", "\n".join(logged_calls))

    def test_reconcile_does_not_escalate_when_read_only_role_lookup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            index = root / "index.json"
            index.write_text(json.dumps({"schema_version": 1, "notices": {
                "unknown": {"recipient_role": "unknown.role", "queued_at": "2000-01-01T00:00:00Z", "disposition": "sending"},
            }}))
            fake_bin, calls = self.fake_gc(root, """
case \"$1 $2 $3\" in
  \"agent list --json\") exit 1 ;;
  *) echo "unexpected: $*" >&2; exit 2 ;;
esac
""")
            result = self.run_notice("reconcile", index=index,
                extra_env={"PATH": f"{fake_bin}:/usr/bin:/bin", "GC_P0_CALLS": str(calls)})
            record = json.loads(index.read_text())["notices"]["unknown"]
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record["disposition"], "sending")
        self.assertIn("routability_error", record)
        logged_calls = calls.read_text().splitlines() if calls.exists() else []
        self.assertFalse(any(call.startswith("mail send human") for call in logged_calls))

    def test_failed_human_escalation_remains_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            index = root / "index.json"
            index.write_text(json.dumps({"schema_version": 1, "notices": {
                "gone": {"recipient_role": "retired.role", "queued_at": "2000-01-01T00:00:00Z", "disposition": "sending"},
            }}))
            fake_bin, calls = self.fake_gc(root, """
case \"$1 $2 $3\" in
  \"agent list --json\") printf '%s\\n' '{"agents":[]}' ;;
  \"mail send human\")
    if [ -f "$GC_P0_RETRY" ]; then printf '%s\\n' '{"messages":[{"id":"human-1"}],"count":1}'; else touch "$GC_P0_RETRY"; exit 1; fi ;;
  *) exit 2 ;;
esac
""")
            env = {"PATH": f"{fake_bin}:/usr/bin:/bin", "GC_P0_CALLS": str(calls), "GC_P0_RETRY": str(root / "retry")}
            self.assertEqual(self.run_notice("reconcile", index=index, extra_env=env).returncode, 0)
            after_failure = json.loads(index.read_text())["notices"]["gone"]
            self.assertEqual(after_failure["disposition"], "sending")
            self.assertIn("escalation_error", after_failure)
            self.assertEqual(self.run_notice("reconcile", index=index, extra_env=env).returncode, 0)
            record = json.loads(index.read_text())["notices"]["gone"]
            logged_calls = calls.read_text().splitlines()
        self.assertEqual(record["disposition"], "escalated", repr(logged_calls) + repr(record))

    def test_reconcile_prunes_old_processed_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = pathlib.Path(directory) / "index.json"
            nid = "a" * 24
            index.write_text(json.dumps({"schema_version": 1, "notices": {nid: {
                "processed_at": "2000-01-01T00:00:00Z", "disposition": "accepted"}}}))
            result = self.run_notice("reconcile", "--retention-seconds", "1", index=index)
            records = json.loads(index.read_text())["notices"]
        self.assertEqual(result.returncode, 0)
        self.assertEqual(records, {})

    def test_contract_files_describe_bounded_durable_policy(self) -> None:
        command = (ROOT / "gascity/commands/notice/command.toml").read_text()
        order = (ROOT / "gascity/roles/orders/p0-notice-reconcile.toml").read_text()
        prompt = (ROOT / "gascity/roles/template-fragments/p0-control-plane.template.md").read_text()
        self.assertIn("p0_notice.py", command)
        self.assertIn("--limit 50", order)
        self.assertIn("five minutes", prompt)
        self.assertIn("durable completion, handoff, review,", prompt)

    def test_implementation_uses_atomic_locked_argument_vector_io(self) -> None:
        source = SCRIPT.read_text()
        self.assertIn("fcntl.LOCK_EX", source)
        self.assertIn("os.replace", source)
        self.assertIn("shell=False", source)
        self.assertIn("0o640", source)
        self.assertIn("occurrence_count", source)
        self.assertIn("processed_at", source)
        self.assertIn("recover_mail_id", source)
        self.assertIn("title=notice:", source)
        self.assertIn('subprocess.run(args,', source)
        self.assertIn('["gc", "agent", "list", "--json"]', source)
        self.assertNotIn('"session", "wake"', source)
        self.assertNotIn("resolve-role", source)


if __name__ == "__main__":
    unittest.main()
