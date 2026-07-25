from __future__ import annotations

import json
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import profile_report as report

ROOT = "ga-root"


def bead(bid, **kw):
    b = {"id": bid, "title": kw.pop("title", bid), "issue_type": kw.pop("issue_type", "task")}
    b.update(kw)
    return b


def closed_run_beads():
    """A two-step run: plan (5m wait, 30m active) then validate (15m wait, 30m active)."""
    return [
        bead(ROOT, title="build from requirements", issue_type="workflow",
             created_at="2026-07-01T10:00:00Z", closed_at="2026-07-01T12:00:00Z"),
        bead("ga-s1", title="plan the work",
             created_at="2026-07-01T10:00:00Z", started_at="2026-07-01T10:05:00Z",
             closed_at="2026-07-01T10:35:00Z",
             metadata={"gc.step_id": "plan", "gc.root_bead_id": ROOT}),
        bead("ga-s2", title="validate the plan",
             created_at="2026-07-01T10:00:00Z", started_at="2026-07-01T10:50:00Z",
             closed_at="2026-07-01T11:20:00Z",
             metadata={"gc.step_id": "validate", "gc.root_bead_id": ROOT},
             dependencies=[{"depends_on_id": "ga-s1", "type": "blocks"}]),
        bead("ga-c1", title="convoy", issue_type="convoy",
             created_at="2026-07-01T10:00:00Z", closed_at="2026-07-01T11:00:00Z"),
    ]


def session_beads():
    return [
        bead("ga-sess1", issue_type="session", labels=["agent:product/run-operator-1"],
             created_at="2026-07-01T10:04:00Z", closed_at="2026-07-01T10:36:00Z"),
        bead("ga-nudge1", issue_type="nudge", labels=["agent:product/run-operator-1"],
             created_at="2026-07-01T10:04:00Z"),
    ]


def fact(**kw):
    f = {"kind": "model", "run_id": ROOT}
    f.update(kw)
    return f


USAGE_FACTS = [
    fact(step_id="plan", input_tokens=1000, output_tokens=200, cache_read_tokens=50,
         cache_creation_tokens=10, cost_usd_estimate=0.5, idempotency_key="k1"),
    # Same idempotency key: a legitimate re-emit that must not double-count.
    fact(step_id="plan", input_tokens=1000, output_tokens=200, cache_read_tokens=50,
         cache_creation_tokens=10, cost_usd_estimate=0.5, idempotency_key="k1"),
    fact(step_id="validate", input_tokens=400, output_tokens=100, unpriced=True,
         idempotency_key="k2"),
    fact(step_id="", input_tokens=10, output_tokens=5, cost_usd_estimate=0.01,
         idempotency_key="k3"),
    {"kind": "compute", "run_id": ROOT, "wall_seconds": 120.5, "idempotency_key": "k4"},
]


def write_capture(tmp, beads, sessions, usage_lines=None, manifest=None):
    cap = pathlib.Path(tmp)
    (cap / "beads.json").write_text(json.dumps(beads), encoding="utf-8")
    (cap / "session-beads.json").write_text(json.dumps(sessions), encoding="utf-8")
    (cap / "manifest.json").write_text(json.dumps(manifest or {"schema": "gc.profile.capture.v1"}),
                                       encoding="utf-8")
    if usage_lines is not None:
        (cap / "usage.window.jsonl").write_text("".join(l + "\n" for l in usage_lines),
                                                encoding="utf-8")
    return cap


class ClosedRunReportTests(unittest.TestCase):
    """The happy path: a finished run, no usage sink."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.r = report.analyze(ROOT, closed_run_beads(), session_beads())

    def test_totals_are_derived_from_the_bead_graph(self) -> None:
        self.assertEqual(self.r["total_m"], 120.0)
        self.assertFalse(self.r["in_flight"])
        self.assertEqual(self.r["totals"], {
            "steps": 2, "dispatch_wait_m": 20.0, "sessions": 1, "session_time_m": 32.0})

    def test_dispatch_wait_starts_at_the_blockers_close_not_the_beads_creation(self) -> None:
        by_id = {s["id"]: s for s in self.r["steps"]}
        self.assertEqual(by_id["ga-s1"]["wait_m"], 5.0)
        self.assertEqual(by_id["ga-s1"]["active_m"], 30.0)
        # ga-s2 was created at 10:00 but only became ready when ga-s1 closed at 10:35.
        self.assertEqual(by_id["ga-s2"]["ready"], "2026-07-01T10:35:00Z")
        self.assertEqual(by_id["ga-s2"]["wait_m"], 15.0)

    def test_convoys_and_the_root_are_not_steps(self) -> None:
        self.assertEqual([s["id"] for s in self.r["steps"]], ["ga-s1", "ga-s2"])

    def test_session_role_is_stripped_of_its_ordinal(self) -> None:
        self.assertEqual(self.r["sessions"], [{
            "id": "ga-sess1", "role": "run-operator",
            "created": "2026-07-01T10:04:00Z", "closed": "2026-07-01T10:36:00Z",
            "duration_m": 32.0}])

    def test_findings_are_tagged_by_fixable_layer(self) -> None:
        layers = [f["layer"] for f in self.r["findings"]]
        self.assertIn("platform+config", layers)
        self.assertIn("formula", layers)

    def test_text_render_reports_the_window_and_both_steps(self) -> None:
        text = report.render_text(self.r)
        self.assertIn("2026-07-01T10:00:00Z -> 2026-07-01T12:00:00Z", text)
        self.assertIn("total: 120.0m", text)
        self.assertIn("plan the work", text)
        self.assertIn("validate the plan", text)
        self.assertNotIn("None", text)

    def test_html_render_is_self_contained_and_escapes_titles(self) -> None:
        beads = closed_run_beads()
        beads[1]["title"] = "plan <script>x</script>"
        html = report.render_html(report.analyze(ROOT, beads, session_beads()))
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("total wall clock", html)
        # No external fetches: the page must carry its own styles.
        self.assertNotIn("<link", html)
        self.assertNotIn("src=", html)


class InFlightRootTests(unittest.TestCase):
    """Regression: an unclosed root used to raise TypeError in --html because
    window.end was None. It must render, and read as in flight."""

    @classmethod
    def setUpClass(cls) -> None:
        beads = closed_run_beads()
        del beads[0]["closed_at"]          # root still running
        del beads[2]["closed_at"]          # ga-s2 started, not closed
        cls.beads = beads
        sessions = session_beads()
        del sessions[0]["closed_at"]       # its session is still open too
        cls.sessions = sessions
        cls.r = report.analyze(ROOT, beads, sessions)

    def test_run_is_flagged_in_flight_with_no_total(self) -> None:
        self.assertTrue(self.r["in_flight"])
        self.assertIsNone(self.r["total_m"])
        self.assertIsNone(self.r["window"]["end"])

    def test_window_end_is_anchored_on_the_latest_observed_timestamp(self) -> None:
        # Latest timestamp in the capture is ga-s2's start at 10:50 — not wall
        # clock, so re-rendering the same capture later cannot move the axis.
        self.assertEqual(self.r["window"]["end_effective"], "2026-07-01T10:50:00Z")
        self.assertEqual(self.r["elapsed_m"], 50.0)

    def test_the_running_step_is_kept_with_an_unknown_active_time(self) -> None:
        by_id = {s["id"]: s for s in self.r["steps"]}
        self.assertIn("ga-s2", by_id, "a started-but-unclosed step must still appear")
        self.assertTrue(by_id["ga-s2"]["in_flight"])
        self.assertIsNone(by_id["ga-s2"]["active_m"])
        self.assertIsNone(by_id["ga-s2"]["lifecycle_m"])
        self.assertEqual(by_id["ga-s2"]["wait_m"], 15.0)
        self.assertFalse(by_id["ga-s1"]["in_flight"])

    def test_html_renders_instead_of_raising(self) -> None:
        html = report.render_html(self.r)
        self.assertIn("run still in flight", html)
        self.assertIn("in flight, latest observed 2026-07-01T10:50:00Z", html)
        self.assertNotIn("None", html)

    def test_html_draws_the_running_step_and_the_open_session(self) -> None:
        html = report.render_html(self.r)
        self.assertIn('class="run"', html)
        self.assertIn("still running", html)
        self.assertIn("run-operator open", html)

    def test_text_render_says_in_flight_rather_than_none(self) -> None:
        text = report.render_text(self.r)
        self.assertIn("IN FLIGHT", text)
        self.assertIn("elapsed: 50.0m", text)
        self.assertIn("running", text)
        self.assertNotIn("None", text)

    def test_a_run_with_nothing_finished_yet_still_renders(self) -> None:
        # The degenerate case: root just created, one step started, no closes.
        beads = [b for b in self.beads if b["id"] in (ROOT, "ga-s2")]
        r = report.analyze(ROOT, beads, [])
        self.assertEqual(r["totals"]["steps"], 1)
        self.assertEqual(r["window"]["end_effective"], "2026-07-01T10:50:00Z")
        self.assertIn("IN FLIGHT", report.render_text(r))
        self.assertIn("run still in flight", report.render_html(r))

    def test_a_root_alone_renders_a_zero_width_window(self) -> None:
        r = report.analyze(ROOT, [self.beads[0]], [])
        self.assertEqual(r["totals"]["steps"], 0)
        self.assertEqual(r["elapsed_m"], 0.0)
        self.assertIn("run still in flight", report.render_html(r))


class UsageRollupTests(unittest.TestCase):
    """The README promised a token/cost rollup. These pin what it computes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        lines = [json.dumps(f) for f in USAGE_FACTS] + ["{not json", "", "  "]
        write_capture(cls.tmp.name, closed_run_beads(), session_beads(), usage_lines=lines)
        facts, malformed = report.read_usage(cls.tmp.name)
        cls.r = report.analyze(ROOT, closed_run_beads(), session_beads(), facts, malformed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_facts_are_deduped_on_idempotency_key(self) -> None:
        # 5 lines in, one a re-emit of k1.
        self.assertEqual(self.r["usage"]["facts"], 4)
        self.assertEqual(self.r["usage"]["run"]["model_facts"], 3)

    def test_malformed_lines_are_counted_not_fatal(self) -> None:
        self.assertEqual(self.r["usage"]["malformed_lines"], 1)

    def test_run_totals_match_gc_costs_semantics(self) -> None:
        self.assertEqual(self.r["usage"]["run"], {
            "model_facts": 3, "compute_facts": 1, "unpriced_facts": 1,
            "input_tokens": 1410, "output_tokens": 305,
            "cache_read_tokens": 50, "cache_creation_tokens": 10,
            "wall_s": 120.5, "cost_usd": 0.51})

    def test_unpriced_facts_keep_their_tokens_but_not_a_cost(self) -> None:
        # 0.51 = 0.5 (plan) + 0.01 (unattributed); the unpriced validate fact
        # contributes tokens only. Treating it as free would give 0.51 too, so
        # assert the flag as well.
        self.assertEqual(self.r["usage"]["run"]["unpriced_facts"], 1)
        validate = next(s for s in self.r["steps"] if s["id"] == "ga-s2")
        self.assertEqual(validate["usage"]["cost_usd"], 0.0)
        self.assertEqual(validate["usage"]["input_tokens"], 400)
        self.assertEqual(validate["usage"]["unpriced_facts"], 1)

    def test_per_step_attribution_joins_through_gc_step_id(self) -> None:
        plan = next(s for s in self.r["steps"] if s["id"] == "ga-s1")
        self.assertEqual(plan["step_key"], "plan")
        self.assertEqual(plan["usage"]["input_tokens"], 1000)
        self.assertEqual(plan["usage"]["output_tokens"], 200)
        self.assertEqual(plan["usage"]["cost_usd"], 0.5)
        self.assertEqual(plan["usage"]["model_facts"], 1)

    def test_facts_without_a_step_id_stay_run_level(self) -> None:
        un = self.r["usage"]["unattributed"]
        self.assertEqual(un["model_facts"], 1)
        self.assertEqual(un["input_tokens"], 10)
        self.assertEqual(un["compute_facts"], 1)
        self.assertEqual(un["wall_s"], 120.5)

    def test_an_ambiguous_step_id_is_disclosed_not_double_counted(self) -> None:
        beads = closed_run_beads()
        beads[2]["metadata"]["gc.step_id"] = "plan"  # two beads, same formula step
        r = report.analyze(ROOT, beads, session_beads(),
                           [fact(step_id="plan", input_tokens=99, cost_usd_estimate=1.0,
                                 idempotency_key="kx")], 0)
        self.assertEqual(r["usage"]["ambiguous_step_ids"], ["plan"])
        self.assertEqual(sum(s["usage"]["input_tokens"] for s in r["steps"]), 0)
        self.assertEqual(r["usage"]["run"]["input_tokens"], 99)
        self.assertEqual(r["usage"]["unattributed"]["input_tokens"], 99)

    def test_notes_name_every_caveat_on_the_total(self) -> None:
        notes = " | ".join(report.usage_notes(self.r["usage"]))
        self.assertIn("no pricing", notes)
        self.assertIn("no captured step", notes)
        self.assertIn("malformed", notes)
        self.assertIn("list-price estimate", notes)

    def test_text_render_shows_tokens_cost_and_per_step_cost(self) -> None:
        text = report.render_text(self.r)
        self.assertIn("tokens: in 1410 out 305", text)
        self.assertIn("est cost: $0.5100", text)
        self.assertIn("runtime wall: 120.5s", text)
        self.assertIn("cost by step (top 10)", text)
        self.assertRegex(text, r"plan the work\s+\$\s*0\.5000")
        self.assertIn("note: 1 model fact(s) had no pricing", text)

    def test_html_render_shows_the_cost_tiles_and_columns(self) -> None:
        html = report.render_html(self.r)
        self.assertIn("Tokens and cost", html)
        self.assertIn("$0.5100", html)
        self.assertIn(">1715<", html)  # 1410 in + 305 out
        self.assertIn("Est USD", html)
        self.assertIn("no pricing", html)

    def test_malformed_json_objects_that_are_not_dicts_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_capture(tmp, closed_run_beads(), session_beads(),
                          usage_lines=["[1,2,3]", '"nope"', json.dumps(USAGE_FACTS[0])])
            facts, malformed = report.read_usage(tmp)
            self.assertEqual(malformed, 2)
            self.assertEqual(len(facts), 1)

    def test_non_numeric_token_fields_do_not_crash_the_rollup(self) -> None:
        r = report.analyze(ROOT, closed_run_beads(), session_beads(),
                           [fact(step_id="plan", input_tokens="lots",
                                 cost_usd_estimate=None, idempotency_key="kz")], 0)
        self.assertEqual(r["usage"]["run"]["input_tokens"], 0)
        self.assertEqual(r["usage"]["run"]["cost_usd"], 0.0)

    def test_unknown_fact_kinds_are_ignored_by_the_totals(self) -> None:
        r = report.analyze(ROOT, closed_run_beads(), session_beads(),
                           [{"kind": "future-thing", "run_id": ROOT, "input_tokens": 5}], 0)
        self.assertEqual(r["usage"]["facts"], 1)
        self.assertEqual(r["usage"]["run"]["model_facts"], 0)
        self.assertEqual(r["usage"]["run"]["input_tokens"], 0)


class MissingUsageTests(unittest.TestCase):
    def test_a_capture_without_a_usage_file_reports_the_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_capture(tmp, closed_run_beads(), session_beads())
            facts, malformed = report.read_usage(tmp)
            self.assertIsNone(facts)
            self.assertEqual(malformed, 0)
            r = report.analyze(ROOT, closed_run_beads(), session_beads(), facts, malformed)
            self.assertFalse(r["usage"]["present"])
            self.assertIn("usage sink disabled", r["usage"]["reason"])
            self.assertIn("tokens/cost: not captured", report.render_text(r))
            self.assertIn("Not captured", report.render_html(r))

    def test_an_empty_usage_file_is_present_but_zeroed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_capture(tmp, closed_run_beads(), session_beads(), usage_lines=[])
            facts, malformed = report.read_usage(tmp)
            self.assertEqual(facts, [])
            r = report.analyze(ROOT, closed_run_beads(), session_beads(), facts, malformed)
            self.assertTrue(r["usage"]["present"])
            self.assertEqual(r["usage"]["run"]["model_facts"], 0)
            self.assertIn("no usage fact resolved to a captured step", report.render_text(r))


class MalformedCaptureTests(unittest.TestCase):
    def test_an_unknown_root_id_fails_loudly(self) -> None:
        with self.assertRaises(KeyError):
            report.analyze("ga-nope", closed_run_beads(), session_beads())

    def test_a_root_with_an_unparsable_created_at_is_rejected_by_html(self) -> None:
        beads = closed_run_beads()
        beads[0]["created_at"] = "not-a-timestamp"
        r = report.analyze(ROOT, beads, session_beads())
        self.assertIsNone(r["total_m"])
        with self.assertRaises(SystemExit) as ctx:
            report.render_html(r)
        self.assertIn("no parsable created_at", str(ctx.exception))

    def test_beads_missing_optional_fields_are_tolerated(self) -> None:
        beads = [
            bead(ROOT, created_at="2026-07-01T10:00:00Z", closed_at="2026-07-01T10:30:00Z"),
            bead("ga-bare"),                                    # no timestamps at all
            bead("ga-open", created_at="2026-07-01T10:00:00Z"),  # created only
        ]
        r = report.analyze(ROOT, beads, [])
        self.assertEqual(r["totals"]["steps"], 0, "steps with no span are not reported")
        self.assertEqual(r["total_m"], 30.0)

    def test_session_beads_without_an_agent_label_get_a_placeholder_role(self) -> None:
        r = report.analyze(ROOT, closed_run_beads(), [
            bead("ga-sessx", issue_type="session", created_at="2026-07-01T10:00:00Z",
                 closed_at="2026-07-01T10:10:00Z")])
        self.assertEqual(r["sessions"][0]["role"], "?")


class CliTests(unittest.TestCase):
    def test_missing_capture_dir_exits_with_a_hint(self) -> None:
        import subprocess
        script = pathlib.Path(report.__file__)
        proc = subprocess.run([sys.executable, str(script), ROOT, "--capture", "/nonexistent-cap"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("run collect first", proc.stderr)

    def test_json_and_html_are_written_into_the_capture(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            write_capture(tmp, closed_run_beads(), session_beads(),
                          usage_lines=[json.dumps(f) for f in USAGE_FACTS])
            proc = subprocess.run(
                [sys.executable, str(pathlib.Path(report.__file__)), ROOT,
                 "--capture", tmp, "--json", "--html"],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads((pathlib.Path(tmp) / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(data["schema"], "gc.profile.report.v1")
            self.assertEqual(data["usage"]["run"]["cost_usd"], 0.51)
            html = (pathlib.Path(tmp) / "report.html").read_text(encoding="utf-8")
            self.assertIn("gc.profile.report.v1", html)
            # The summary line still prints when writing files.
            self.assertIn("profile report ga-root", proc.stdout)
            self.assertIsNotNone(re.search(r"wrote .*report\.json", proc.stdout))


if __name__ == "__main__":
    unittest.main()
