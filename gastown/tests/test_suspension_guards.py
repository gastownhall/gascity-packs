#!/usr/bin/env python3
"""Offline execution of the suspension gates prescribed by patrol formulas."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import tomllib

ROOT = Path(__file__).resolve().parents[2]
SHUTDOWN = tomllib.loads((ROOT / "gastown/formulas/mol-shutdown-dance.toml").read_text())
DEACON = tomllib.loads((ROOT / "gastown/formulas/mol-deacon-patrol.toml").read_text())

def blocks(formula, step):
    text = next(s["description"] for s in formula["steps"] if s["id"] == step)
    return re.findall(r"```bash\n(.*?)\n```", text, re.S)

def guarded(formula, step):
    return [b for b in blocks(formula, step) if "# BEGIN RECOVERY_TARGET_GUARD" in b]

class SuspensionGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / "calls"
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                        GUARD_FIXTURE=str(self.root), GC_BEAD_ID="warrant-1")
        stub = self.root / "gc"
        stub.write_text("""#!/bin/bash
# NUL-delimited argv records keep this offline stub cheap and preserve argument bytes.
printf '%s\\0' "$@" >> "$GUARD_FIXTURE/calls"
printf '\\0' >> "$GUARD_FIXTURE/calls"
if [ "$*" = 'session list --state=all --json' ]; then
 [ ! -e "$GUARD_FIXTURE/session-fail" ] || exit 1
 printf '%s\\n' "$(< "$GUARD_FIXTURE/sessions")"
elif [ "$*" = 'rig list --json' ]; then
 [ ! -e "$GUARD_FIXTURE/rig-fail" ] || exit 1
 printf '%s\\n' "$(< "$GUARD_FIXTURE/rigs")"
elif [ "$1 $2" = 'bd list' ]; then
 printf '[]\\n'
else
 case "$1 $2" in
  'bd close'|'bd create'|'session nudge'|'runtime drain-ack'|'session kill') ;;
  *) printf 'unexpected gc command: %s\\n' "$*" >&2; exit 1 ;;
 esac
fi
""")
        stub.chmod(0o755)
        self.session = {"id":"s1", "name":"alpha/witness", "agent_name":"alpha/witness",
                        "template":"alpha/gastown.witness", "rig":"alpha", "state":"asleep", "closed":False}
        self.roster(False)
        self.sessions([self.session])

    def roster(self, suspended):
        (self.root / "rigs").write_text(json.dumps({"ok":True,"rigs":[
            {"name":"city","hq":True,"suspended":False},
            {"name":"alpha","hq":False,"suspended":suspended}]}))

    def sessions(self, rows):
        (self.root / "sessions").write_text(json.dumps({"ok":True,"sessions":rows}))

    def run_guard(self, code, expected_status=0):
        self.log.write_text("")
        result = subprocess.run(["bash", "-c", 'set -euo pipefail\ntarget="alpha/witness"\nrequester_endpoint="deacon/"\n' + code],
                                env=self.env, text=True, capture_output=True, timeout=10)
        calls = [[arg.decode() for arg in row.split(b"\0")]
                 for row in self.log.read_bytes().split(b"\0\0") if row]
        self.assertEqual(result.returncode, expected_status, result.stderr)
        return calls

    def assert_no_target_action(self, calls):
        self.assertFalse(any(c[:2] == ["session","kill"] or
                             (c[:2] == ["session","nudge"] and c[2] != "deacon/") for c in calls), calls)
        self.assertFalse(any(c[:2] in (["rig","resume"],["bd","create"]) for c in calls), calls)

    def test_receipt_suspended_closes_and_drains_without_target_action(self):
        self.roster(True)
        calls = self.run_guard(guarded(SHUTDOWN, "receive-warrant")[0])
        self.assert_no_target_action(calls)
        self.assertTrue(any(c[:2] == ["bd","close"] and "NO_ACTION" in c[-1] for c in calls))
        self.assertEqual(calls[-1], ["runtime","drain-ack"])

    def test_active_control_reaches_kill(self):
        calls = self.run_guard(guarded(SHUTDOWN, "execute")[0])
        self.assertEqual(calls[-1], ["session","kill","alpha/witness"])

    def test_suspension_between_receipt_and_kill_stops_execution(self):
        receipt = guarded(SHUTDOWN, "receive-warrant")[0]
        execute = guarded(SHUTDOWN, "execute")[0]
        change = "printf '%s' '{\"ok\":true,\"rigs\":[{\"name\":\"alpha\",\"suspended\":true}]}' > \"$GUARD_FIXTURE/rigs\"\n"
        calls = self.run_guard(receipt + "\n" + change + execute)
        self.assert_no_target_action(calls)
        self.assertEqual(calls[-1], ["runtime","drain-ack"])
        self.assertEqual(sum(c == ["rig","list","--json"] for c in calls), 2)

    def test_unknown_and_failed_reads_stop_both_shutdown_gates(self):
        for step in ("receive-warrant", "execute"):
            code = guarded(SHUTDOWN, step)[0]
            for raw in ('{}', 'not-json', '{"ok":true,"rigs":[]}',
                        '{"ok":true,"rigs":[{"name":"alpha"}]}',
                        '{"ok":true,"rigs":[{"name":"alpha","suspended":"false"}]}',
                        '{"ok":true,"rigs":[{"name":"alpha","suspended":false},{"name":"alpha","suspended":false}]}'):
                with self.subTest(step=step, rigs=raw):
                    (self.root / "rigs").write_text(raw)
                    self.assert_no_target_action(self.run_guard(code))
            self.roster(False)
            for rows in ([], [self.session, self.session], [{"id":"s1","name":"alpha/witness"}],
                         [dict(self.session, agent_name="beta/witness")], [dict(self.session, rig=5)]):
                with self.subTest(step=step, sessions=rows):
                    self.sessions(rows)
                    self.assert_no_target_action(self.run_guard(code))
            self.sessions([self.session])
            for ok in (None, False, "true", 1, []):
                with self.subTest(step=step, ok=ok):
                    envelope = {"sessions":[self.session]}
                    if ok is not None:
                        envelope["ok"] = ok
                    (self.root / "sessions").write_text(json.dumps(envelope))
                    self.assert_no_target_action(self.run_guard(code))
            for field, values in (("closed", (None, "false", 0, [], True)),
                                  ("state", (None, False, 0, [], "", "unknown", "closed"))):
                for value in values:
                    row = dict(self.session)
                    if value is None:
                        row.pop(field)
                    else:
                        row[field] = value
                    with self.subTest(step=step, field=field, value=value):
                        self.sessions([row])
                        self.assert_no_target_action(self.run_guard(code))
            # A known closed historical alias does not shadow a distinct live row.
            historical = dict(self.session, id="old-s1", state="closed", closed=True)
            self.sessions([historical, self.session])
            calls = self.run_guard(code)
            if step == "execute":
                self.assertEqual(calls[-1], ["session","kill","alpha/witness"])
            else:
                self.assertEqual(calls, [["session","list","--state=all","--json"],
                                         ["rig","list","--json"]])
            # Unknown matching status is unresolved even beside a valid live row.
            self.sessions([dict(historical, closed="true"), self.session])
            self.assert_no_target_action(self.run_guard(code))
            self.sessions([self.session])
            for failure in ("rig-fail", "session-fail"):
                flag = self.root / failure
                flag.touch()
                self.assert_no_target_action(self.run_guard(code))
                flag.unlink()

    def test_identifiable_hq_remains_eligible(self):
        self.sessions([{"id":"s1", "name":"gastown.dog", "agent_name":"gastown.dog", "template":"gastown.dog", "state":"active", "closed":False}])
        code = guarded(SHUTDOWN, "execute")[0]
        calls = self.run_guard('target="s1"\n' + code)
        self.assertEqual(calls[-1], ["session","kill","s1"])

    def test_deacon_nudges_and_warrants_require_current_active_scope(self):
        for step in ("health-scan", "queue-starvation-check", "utility-agent-health"):
            for code in guarded(DEACON, step):
                # Replace only the illustrative target placeholders, never guard logic.
                code = code.replace('TARGET_SESSION="<session>"', 'TARGET_SESSION="alpha/witness"')
                pre = 'STALLED_SESSION="alpha/witness"\nSTUCK_SESSION="alpha/witness"\nASSIGNED=2\nduration=1h\n'
                for suspended in (False, True):
                    self.roster(suspended)
                    calls = self.run_guard(pre + code)
                    action_kinds = (["bd","list"],) if "QUEUE_SESSIONS=" in code else (["session","nudge"],["bd","create"])
                    actions = [c for c in calls if c[:2] in action_kinds]
                    self.assertEqual(bool(actions), not suspended, (step, calls))
                (self.root / "rigs").write_text('{"ok":true,"rigs":[]}')
                self.assert_no_target_action(self.run_guard(pre + code))
                self.roster(False)
                # Every deacon action and assessment rejects missing/malformed status.
                for field, value in (("closed", None), ("closed", "false"),
                                     ("state", None), ("state", 5)):
                    row = dict(self.session)
                    if value is None:
                        row.pop(field)
                    else:
                        row[field] = value
                    self.sessions([row])
                    calls = self.run_guard(pre + code)
                    self.assert_no_target_action(calls)
                    self.assertFalse(any(c[:2] == ["bd","list"] for c in calls))
                for ok in (None, False, "true"):
                    envelope = {"sessions":[self.session]}
                    if ok is not None:
                        envelope["ok"] = ok
                    (self.root / "sessions").write_text(json.dumps(envelope))
                    calls = self.run_guard(pre + code, expected_status=1 if "QUEUE_SESSIONS=" in code else 0)
                    self.assert_no_target_action(calls)
                    self.assertFalse(any(c[:2] == ["bd","list"] for c in calls))
                historical = dict(self.session, id="old-s1", closed=True, state="closed")
                self.sessions([historical, self.session])
                calls = self.run_guard(pre + code)
                actions = [c for c in calls if c[:2] in action_kinds]
                self.assertTrue(actions, (step, calls))
                self.sessions([self.session])
        # Several queue candidates share exactly one native session and rig read.
        beta = dict(self.session, id="s2", name="beta/witness", agent_name="beta/witness",
                    template="beta/gastown.witness", rig="beta")
        gamma = dict(self.session, id="s3", name="gamma/witness", agent_name="gamma/witness",
                     template="gamma/gastown.witness", rig="gamma")
        self.sessions([historical, self.session, beta, gamma])
        (self.root / "rigs").write_text(json.dumps({"ok":True,"rigs":[
            {"name":"alpha","suspended":False}, {"name":"beta","suspended":False},
            {"name":"gamma","suspended":True}]}))
        queue = guarded(DEACON, "queue-starvation-check")[0]
        calls = self.run_guard(queue)
        self.assertEqual(sum(c == ["session","list","--state=all","--json"] for c in calls), 1)
        self.assertEqual(sum(c == ["rig","list","--json"] for c in calls), 1)
        queries = [c for c in calls if c[:2] == ["bd","list"]]
        self.assertEqual(len(queries), 4, queries)
        self.assertEqual({a for c in queries for a in c if a.startswith("--assignee=")},
                         {"--assignee=alpha/witness", "--assignee=beta/witness"})
        # Two live rows for one identity are ambiguous and omitted from assessment.
        self.sessions([self.session, dict(self.session, id="s4"), beta])
        queries = [c for c in self.run_guard(queue) if c[:2] == ["bd","list"]]
        self.assertEqual(len(queries), 2)
        self.assertTrue(all("--assignee=beta/witness" in c for c in queries))

    def stable_sessions(self, rows, **envelope):
        payload = {"_cache_age_s": 0.25, "sessions": rows}
        payload.update(envelope)
        (self.root / "sessions").write_text(json.dumps(payload))

    def stable_row(self, **changes):
        # Exact CLI SessionView fields from Gas City v1.5.1 decode_sessions.go.
        row = {"id": "s1", "template": "alpha/gastown.witness", "state": "asleep",
               "reason": "", "title": "", "alias": "alpha/witness",
               "session_name": "alpha--gastown__witness", "work_dir": "",
               "created_at": "2026-11-11T00:00:00Z", "last_active": "2026-11-11T00:00:00Z",
               "attached": False, "running": False, "last_output": ""}
        row.update(changes)
        return row

    def test_stable_api_and_local_controls_at_every_action(self):
        cases = [(SHUTDOWN, step, code) for step in ("receive-warrant", "execute")
                 for code in guarded(SHUTDOWN, step)]
        cases += [(DEACON, step, code) for step in
                  ("health-scan", "queue-starvation-check", "utility-agent-health")
                  for code in guarded(DEACON, step)]
        for formula, step, code in cases:
            code = code.replace('TARGET_SESSION="<session>"', 'TARGET_SESSION="alpha/witness"')
            pre = 'STALLED_SESSION="alpha/witness"\nSTUCK_SESSION="alpha/witness"\nASSIGNED=2\nduration=1h\n'
            is_queue = "QUEUE_SESSIONS=" in code
            for shape in ("api", "local"):
                live = self.stable_row() if shape == "api" else self.session
                old = dict(live, id="old-s1", state="closed" if shape == "api" else "")
                if shape == "local":
                    old["closed"] = True
                for suspended in (False, True):
                    with self.subTest(step=step, shape=shape, suspended=suspended):
                        self.roster(suspended)
                        if shape == "api":
                            self.stable_sessions([old, live])
                        else:
                            self.sessions([old, live])
                        calls = self.run_guard(pre + code)
                        actions = [c for c in calls if c[:2] in
                                   (["bd", "list"], ["session", "kill"], ["bd", "create"])
                                   or c[:2] == ["session", "nudge"] and c[2] != "deacon/"]
                        if formula is SHUTDOWN and step == "receive-warrant":
                            self.assertEqual(any(c[:2] == ["runtime", "drain-ack"] for c in calls), suspended)
                        else:
                            self.assertEqual(bool(actions), not suspended, calls)
                        if is_queue:
                            self.assertEqual(sum(c == ["session", "list", "--state=all", "--json"] for c in calls), 1)
                            self.assertEqual(sum(c == ["rig", "list", "--json"] for c in calls), 1)
                            if not suspended:
                                expected = "alpha--gastown__witness" if shape == "api" else "alpha/witness"
                                self.assertTrue(all("--assignee=" + expected in c for c in actions))
        self.roster(False)
        # The named runtime identity, alias and physical id are wire identities.
        for changes, identity in (({}, "alpha--gastown__witness"),
                                  ({"session_name": ""}, "alpha/witness"),
                                  ({"session_name": "", "alias": ""}, "s1")):
            self.stable_sessions([self.stable_row(**changes)])
            calls = self.run_guard(guarded(DEACON, "queue-starvation-check")[0])
            queries = [c for c in calls if c[:2] == ["bd", "list"]]
            self.assertEqual(len(queries), 2)
            self.assertTrue(all("--assignee=" + identity in c for c in queries))

    def test_stable_api_malformed_envelopes_rows_and_hq_scope(self):
        execute = guarded(SHUTDOWN, "execute")[0]
        queue = guarded(DEACON, "queue-starvation-check")[0]
        good = self.stable_row()
        bad_envelopes = [{"sessions": [good]}, {"_cache_age_s": 0, "sessions": {}},
                         {"_cache_age_s": 0, "sessions": [good], "error": {"message": "failed"}}]
        bad_envelopes += [{"_cache_age_s": age, "sessions": [good]}
                          for age in (-1, None, "0", True, [], {})]
        bad_envelopes += [{"_cache_age_s": 0, "sessions": [good], "ok": ok}
                          for ok in (False, None, "true", 1)]
        for code in (execute, queue):
            for payload in bad_envelopes:
                with self.subTest(payload=payload, queue=code == queue):
                    (self.root / "sessions").write_text(json.dumps(payload))
                    calls = self.run_guard(code, expected_status=1 if code == queue else 0)
                    self.assert_no_target_action(calls)
                    self.assertFalse(any(c[:2] == ["bd", "list"] for c in calls))
            for bad in ({"state": "unknown"}, {"state": ""}, {"state": None},
                        {"closed": False}, {"closed": "false"}, {"template": ""},
                        {"template": "alpha/"}, {"alias": "beta/witness"},
                        {"session_name": []}):
                self.stable_sessions([self.stable_row(**bad)])
                calls = self.run_guard(code)
                self.assert_no_target_action(calls)
                self.assertFalse(any(c[:2] == ["bd", "list"] for c in calls))
            # A malformed matching historical row keeps even a healthy match unresolved.
            self.stable_sessions([good, self.stable_row(id="old-s1", state="")])
            self.assert_no_target_action(self.run_guard(code))
            # Two open rows sharing runtime identity are ambiguous at assessment and actions.
            self.stable_sessions([good, self.stable_row(id="other-s1")])
            calls = self.run_guard(code)
            self.assert_no_target_action(calls)
            self.assertFalse(any(c[:2] == ["bd", "list"] for c in calls))
        hq = self.stable_row(template="gastown.dog", alias="gastown.dog", session_name="gastown__dog")
        for rigs, allowed in (([{"name": "city", "hq": True, "suspended": False}], True),
                              ([{"name": "city", "hq": True, "suspended": True}], False),
                              ([{"name": "city", "suspended": False}], False),
                              ([{"name": "city", "hq": True, "suspended": False},
                                {"name": "other", "hq": True, "suspended": False}], False)):
            (self.root / "rigs").write_text(json.dumps({"ok": True, "rigs": rigs}))
            self.stable_sessions([hq])
            calls = self.run_guard('target="s1"\n' + execute)
            self.assertEqual(any(c[:2] == ["session", "kill"] for c in calls), allowed)
        # A slash-bearing alias cannot turn a city template into rig proof.
        self.roster(False)
        self.stable_sessions([dict(hq, alias="alpha/witness")])
        self.assert_no_target_action(self.run_guard('target="s1"\n' + execute))
        self.stable_sessions([dict(hq, rig="alpha")])
        self.assert_no_target_action(self.run_guard('target="s1"\n' + execute))

if __name__ == "__main__":
    unittest.main(verbosity=2)
