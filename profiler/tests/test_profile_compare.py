from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import profile_compare as compare
import profile_report as report


def run_report(total_m, wait_a, wait_b, active_a, active_b, extra_titles=()):
    """Hand-build a minimal gc.profile.report.v1 payload."""
    steps = [
        {"id": "s1", "title": "plan the work", "wait_m": wait_a, "active_m": active_a},
        {"id": "s2", "title": "validate the plan", "wait_m": wait_b, "active_m": active_b},
    ] + [{"id": t, "title": t, "wait_m": 0.0, "active_m": 1.0} for t in extra_titles]
    return {
        "schema": report.SCHEMA, "root": "r",
        "total_m": total_m,
        "totals": {"steps": len(steps), "dispatch_wait_m": wait_a + wait_b,
                   "sessions": 2, "session_time_m": 40.0},
        "steps": steps,
    }


def write_city(base, captures):
    city = pathlib.Path(base)
    for root, payload in captures.items():
        d = city / ".gc" / "runtime" / "profiles" / root
        d.mkdir(parents=True, exist_ok=True)
        (d / "report.json").write_text(json.dumps(payload), encoding="utf-8")
    return city


def run_cli(city, a, b):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "profile_compare.py"), a, b, "--city", str(city)],
        capture_output=True, text=True)


class LoadTests(unittest.TestCase):
    def test_a_missing_report_names_the_command_that_makes_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                compare.load_report(tmp, "ga-nope")
            self.assertIn("run: gc profiler report ga-nope --json", str(ctx.exception))

    def test_cli_reports_the_missing_capture_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(tmp, {"ga-a": run_report(100.0, 1.0, 2.0, 10.0, 20.0)})
            proc = run_cli(city, "ga-a", "ga-b")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("ga-b", proc.stderr)
            self.assertIn("--json", proc.stderr)

    def test_a_corrupt_report_is_not_silently_treated_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(tmp, {"ga-a": run_report(100.0, 1.0, 2.0, 10.0, 20.0)})
            d = city / ".gc" / "runtime" / "profiles" / "ga-b"
            d.mkdir(parents=True)
            (d / "report.json").write_text("{ truncated", encoding="utf-8")
            proc = run_cli(city, "ga-a", "ga-b")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("JSONDecodeError", proc.stderr)


class CompareOutputTests(unittest.TestCase):
    def test_totals_and_matching_step_deltas_are_printed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(tmp, {
                "ga-a": run_report(100.0, 1.0, 2.0, 10.0, 20.0),
                "ga-b": run_report(130.0, 4.0, 2.0, 10.0, 26.0),
            })
            proc = run_cli(city, "ga-a", "ga-b")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertRegex(out, r"total wall \(m\)\s+100\.0\s+130\.0\s+\+30\.0")
            self.assertRegex(out, r"dispatch wait \(m\)\s+3\.0\s+6\.0\s+\+3\.0")
            # plan: wait +3.0, active unchanged; validate: wait flat, active +6.0.
            self.assertRegex(out, r"plan the work\s+\+3\.0")
            self.assertRegex(out, r"validate the plan\s+\+0\.0\s+\+6\.0")

    def test_deltas_below_the_noise_threshold_are_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(tmp, {
                "ga-a": run_report(100.0, 1.0, 2.0, 10.0, 20.0),
                "ga-b": run_report(100.0, 1.01, 2.0, 10.0, 20.0),
            })
            proc = run_cli(city, "ga-a", "ga-b")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("plan the work", proc.stdout)

    def test_steps_present_in_only_one_run_are_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(tmp, {
                "ga-a": run_report(100.0, 1.0, 2.0, 10.0, 20.0, extra_titles=("only-a",)),
                "ga-b": run_report(100.0, 1.0, 2.0, 10.0, 20.0,
                                   extra_titles=("only-b1", "only-b2")),
            })
            proc = run_cli(city, "ga-a", "ga-b")
            self.assertIn("only in A: 1 steps", proc.stdout)
            self.assertIn("only in B: 2 steps", proc.stdout)

    def test_an_in_flight_run_compares_without_inventing_a_total(self) -> None:
        # An unclosed run has total_m None; the delta must read as unknown.
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(tmp, {
                "ga-a": run_report(100.0, 1.0, 2.0, 10.0, 20.0),
                "ga-b": run_report(None, 1.0, 2.0, 10.0, None),
            })
            proc = run_cli(city, "ga-a", "ga-b")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertRegex(proc.stdout, r"total wall \(m\)\s+100\.0\s+—\s+—")

    def test_comparing_a_run_with_itself_is_all_zeroes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_report(100.0, 1.0, 2.0, 10.0, 20.0)
            city = write_city(tmp, {"ga-a": payload, "ga-b": payload})
            proc = run_cli(city, "ga-a", "ga-b")
            self.assertRegex(proc.stdout, r"total wall \(m\)\s+100\.0\s+100\.0\s+\+0\.0")
            self.assertNotIn("plan the work", proc.stdout)
            self.assertNotIn("only in", proc.stdout)


class RoundTripTests(unittest.TestCase):
    """compare consumes exactly what report --json writes."""

    def test_report_json_from_two_captures_compares(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        from test_profile_report import closed_run_beads, session_beads

        with tempfile.TemporaryDirectory() as tmp:
            city = pathlib.Path(tmp)
            for root, shift in (("ga-a", "10:35:00"), ("ga-b", "10:45:00")):
                beads = closed_run_beads()
                beads[0]["id"] = root
                for b in beads[1:]:
                    if (b.get("metadata") or {}).get("gc.root_bead_id"):
                        b["metadata"]["gc.root_bead_id"] = root
                beads[1]["closed_at"] = f"2026-07-01T{shift}Z"
                cap = city / ".gc" / "runtime" / "profiles" / root
                cap.mkdir(parents=True)
                (cap / "beads.json").write_text(json.dumps(beads), encoding="utf-8")
                (cap / "session-beads.json").write_text(json.dumps(session_beads()),
                                                        encoding="utf-8")
                (cap / "manifest.json").write_text("{}", encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, str(SCRIPTS / "profile_report.py"), root,
                     "--capture", str(cap), "--json"], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)

            proc = run_cli(city, "ga-a", "ga-b")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("total wall (m)", proc.stdout)
            self.assertRegex(proc.stdout, r"plan the work\s+\+0\.0\s+\+10\.0")


if __name__ == "__main__":
    unittest.main()
