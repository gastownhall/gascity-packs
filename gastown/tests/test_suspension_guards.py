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
        stub.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p=Path(os.environ['GUARD_FIXTURE']); a=sys.argv[1:]
with (p/'calls').open('a') as f: f.write(json.dumps(a)+'\\n')
if a==['session','list','--state=all','--json']:
 if (p/'session-fail').exists(): sys.exit(1)
 print((p/'sessions').read_text())
elif a==['rig','list','--json']:
 if (p/'rig-fail').exists(): sys.exit(1)
 print((p/'rigs').read_text())
elif a[:2]==['bd','list']: print('[]')
elif a[:2] in (['bd','close'],['bd','create'],['session','nudge'],['runtime','drain-ack'],['session','kill']): pass
else: sys.exit('unexpected gc command '+repr(a))
""")
        stub.chmod(0o755)
        self.session = {"id":"s1", "name":"alpha/witness", "agent_name":"alpha/witness",
                        "template":"alpha/gastown.witness", "rig":"alpha", "state":"asleep"}
        self.roster(False)
        self.sessions([self.session])

    def roster(self, suspended):
        (self.root / "rigs").write_text(json.dumps({"ok":True,"rigs":[
            {"name":"city","hq":True,"suspended":False},
            {"name":"alpha","hq":False,"suspended":suspended}]}))

    def sessions(self, rows):
        (self.root / "sessions").write_text(json.dumps({"sessions":rows}))

    def run_guard(self, code):
        self.log.write_text("")
        result = subprocess.run(["bash", "-c", 'set -euo pipefail\ntarget="alpha/witness"\nrequester_endpoint="deacon/"\n' + code],
                                env=self.env, text=True, capture_output=True, timeout=10)
        calls = [json.loads(x) for x in self.log.read_text().splitlines()]
        self.assertEqual(result.returncode, 0, result.stderr)
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
            for failure in ("rig-fail", "session-fail"):
                flag = self.root / failure
                flag.touch()
                self.assert_no_target_action(self.run_guard(code))
                flag.unlink()

    def test_identifiable_hq_remains_eligible(self):
        self.sessions([{"id":"s1", "name":"gastown.dog", "agent_name":"gastown.dog", "template":"gastown.dog"}])
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

if __name__ == "__main__":
    unittest.main(verbosity=2)
