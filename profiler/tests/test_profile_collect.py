from __future__ import annotations

import gzip
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import profile_collect as collect

ROOT = "ga-root"

FAKE_GC = """#!/bin/sh
# Stand-in for gc. Only `gc bd list` is exercised; the rig store and the city
# store are told apart by --include-infra.
if [ "$1" != bd ]; then
  echo "unexpected gc invocation: $*" >&2
  exit 2
fi
case "$*" in
  *--include-infra*) cat "$FAKE_BD_CITY" ;;
  *) cat "$FAKE_BD_RIG" ;;
esac
"""


def bead(bid, **kw):
    b = {"id": bid, "title": kw.pop("title", bid), "issue_type": kw.pop("issue_type", "task")}
    b.update(kw)
    return b


class ClosureTests(unittest.TestCase):
    """closure() is the pure heart of collect: which beads belong to this run."""

    def test_unknown_root_is_a_hard_error(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            collect.closure([bead("ga-other")], ROOT)
        self.assertIn("not found in rig store", str(ctx.exception))

    def test_a_lone_root_closes_over_itself(self) -> None:
        self.assertEqual([b["id"] for b in collect.closure([bead(ROOT)], ROOT)], [ROOT])

    def test_linkage_metadata_pulls_children_in(self) -> None:
        beads = [
            bead(ROOT),
            bead("ga-s1", metadata={"gc.root_bead_id": ROOT}),
            bead("ga-s2", metadata={"gc.parent_bead_id": "ga-s1"}),
            bead("ga-unrelated", metadata={"gc.root_bead_id": "ga-somebody-else"}),
        ]
        got = {b["id"] for b in collect.closure(beads, ROOT)}
        self.assertEqual(got, {ROOT, "ga-s1", "ga-s2"})

    def test_launch_convoy_survives_only_in_the_runtime_var(self) -> None:
        # gc.input_convoy_id is repointed mid-run, so the launch convoy is
        # reachable only through gc.var.convoy_id. This is the collector bug the
        # PR's own reference validation caught; keep it caught.
        beads = [
            bead(ROOT, metadata={"gc.input_convoy_id": "ga-late-convoy"}),
            bead("ga-launch-member", metadata={"gc.var.convoy_id": ROOT}),
        ]
        got = {b["id"] for b in collect.closure(beads, ROOT)}
        self.assertIn("ga-launch-member", got)

    def test_dependency_edges_are_followed_in_both_directions(self) -> None:
        beads = [
            bead(ROOT, dependencies=[{"depends_on_id": "ga-downstream"}]),
            bead("ga-downstream"),
            bead("ga-upstream", dependencies=[{"depends_on_id": ROOT}]),
            bead("ga-island"),
        ]
        got = {b["id"] for b in collect.closure(beads, ROOT)}
        self.assertEqual(got, {ROOT, "ga-downstream", "ga-upstream"})

    def test_closure_runs_to_fixpoint_regardless_of_input_order(self) -> None:
        # A chain listed backwards must still resolve fully.
        beads = [
            bead("ga-s3", metadata={"gc.parent_bead_id": "ga-s2"}),
            bead("ga-s2", metadata={"gc.parent_bead_id": "ga-s1"}),
            bead("ga-s1", metadata={"gc.root_bead_id": ROOT}),
            bead(ROOT),
        ]
        got = {b["id"] for b in collect.closure(beads, ROOT)}
        self.assertEqual(got, {ROOT, "ga-s1", "ga-s2", "ga-s3"})

    def test_beads_missing_metadata_and_dependencies_are_skipped_cleanly(self) -> None:
        beads = [bead(ROOT), bead("ga-x", metadata=None, dependencies=None)]
        self.assertEqual([b["id"] for b in collect.closure(beads, ROOT)], [ROOT])

    def test_closure_order_is_deterministic(self) -> None:
        # beads.json is hashed in the manifest, so set-iteration order will not do.
        beads = [bead(ROOT), bead("ga-b", metadata={"gc.root_bead_id": ROOT}),
                 bead("ga-a", metadata={"gc.root_bead_id": ROOT})]
        ids = [b["id"] for b in collect.closure(beads, ROOT)]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(ids, [b["id"] for b in collect.closure(list(reversed(beads)), ROOT)])


class SlugTests(unittest.TestCase):
    def test_claude_code_slug_replaces_slashes_and_dots(self) -> None:
        self.assertEqual(collect.project_slug("/home/u/work.git"), "-home-u-work-git")

    def test_slug_candidates_cover_the_private_tmp_alias(self) -> None:
        cands = collect.slug_candidates("/tmp/rig")
        self.assertIn("-tmp-rig", cands)
        self.assertIn("-private-tmp-rig", cands)

    def test_no_work_dir_resolves_no_transcript(self) -> None:
        self.assertEqual(collect.find_transcript("", "key"), (None, None))


# session_key comes from bead metadata, which the profiler does not author. Before this
# was constrained it was concatenated straight into a path, so a crafted key could read
# any .jsonl on the machine INTO the capture — and captures get shared.
class SessionKeyContainmentTests(unittest.TestCase):
    def test_a_uuid_shaped_key_is_accepted(self) -> None:
        self.assertTrue(collect.SAFE_SESSION_KEY.match("0b9f4c2e-7a11-4d3b-9f21-2c8e5a6d1234"))

    def test_traversal_and_absolute_keys_are_rejected(self) -> None:
        for hostile in (
            "../../../../etc/hosts",
            "..",
            "/etc/hosts",
            "a/b",
            "a\\b",
            "key with spaces",
            "key\x00",
            "",
        ):
            self.assertFalse(
                collect.SAFE_SESSION_KEY.match(hostile),
                f"{hostile!r} must not be accepted as a session key",
            )

    def test_contained_path_keeps_a_normal_join(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            os.makedirs(os.path.join(base, "slug"))
            got = collect.contained_path(base, "slug", "abc.jsonl")
            self.assertEqual(got, os.path.join(os.path.realpath(base), "slug", "abc.jsonl"))

    def test_contained_path_refuses_escapes(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            self.assertIsNone(collect.contained_path(base, "..", "outside.jsonl"))
            # An ABSOLUTE component makes os.path.join discard base entirely.
            self.assertIsNone(collect.contained_path(base, "/etc", "hosts.jsonl"))

    def test_contained_path_refuses_a_symlink_pointing_out(self) -> None:
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as outside:
            target = os.path.join(outside, "secret.jsonl")
            with open(target, "w") as f:
                f.write("{}\n")
            os.symlink(outside, os.path.join(base, "slug"))
            # The join looks contained; only resolving symlinks reveals it is not.
            self.assertIsNone(collect.contained_path(base, "slug", "secret.jsonl"))

    def test_find_transcript_does_not_read_through_a_hostile_key(self) -> None:
        # HOME is redirected so this is hermetic AND so the slug directory really exists:
        # traversal through a MISSING component fails on Linux regardless of the guard, so a
        # test against a non-existent slug dir would pass even on the vulnerable join.
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as outside:
            secret = os.path.join(outside, "stolen.jsonl")
            with open(secret, "w") as f:
                f.write('{"secret":true}\n')
            work_dir = "/tmp/rig"
            slug = collect.project_slug(work_dir)
            slug_dir = os.path.join(home, ".claude", "projects", slug)
            os.makedirs(slug_dir)
            # The exact traversal from the slug dir to the planted file, minus the suffix
            # find_transcript appends. Computed, not counted — a wrong depth is how this
            # test silently stopped exercising anything the first time.
            key = os.path.relpath(secret[: -len(".jsonl")], slug_dir)

            prior = os.environ.get("HOME")
            os.environ["HOME"] = home
            try:
                # Sanity: the traversal genuinely resolves to the planted file, so a failure
                # below means the guard declined it rather than the path being unreachable.
                self.assertTrue(
                    os.path.exists(os.path.join(slug_dir, key + ".jsonl")),
                    "fixture is wrong: the traversal target must exist for this test to bite",
                )
                path, method = collect.find_transcript(work_dir, key)
            finally:
                if prior is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = prior
            self.assertIsNone(path, f"session_key traversal resolved to {path}")
            self.assertIsNone(method)


class CollectEndToEndTests(unittest.TestCase):
    """A real collect run against a fixture rig + city, with gc stubbed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(cls.tmp.name)
        cls.home = base / "home"
        cls.rig = base / "rig"
        cls.city = base / "city"
        cls.out = base / "capture"
        for d in (cls.home, cls.rig, cls.city / ".gc", base / "bin"):
            d.mkdir(parents=True, exist_ok=True)

        rig_beads = [
            bead(ROOT, title="build from requirements", issue_type="workflow",
                 created_at="2026-07-01T10:00:00Z", closed_at="2026-07-01T12:00:00Z",
                 metadata={"gc.var.rig_name": "product", "gc.formula": "build-from-requirements",
                           "gc.graphv2_root_key": "k1"}),
            bead("ga-s1", title="plan the work",
                 created_at="2026-07-01T10:00:00Z", started_at="2026-07-01T10:05:00Z",
                 closed_at="2026-07-01T10:35:00Z",
                 metadata={"gc.root_bead_id": ROOT, "gc.step_id": "plan"}),
            bead("ga-nope", title="another run's step",
                 created_at="2026-07-01T10:00:00Z",
                 metadata={"gc.root_bead_id": "ga-somebody-else"}),
        ]
        # Two sessions: one resolvable by session_key, one that cannot be resolved.
        city_beads = [
            bead("ga-sess1", issue_type="session", labels=["agent:product/run-operator-1"],
                 created_at="2026-07-01T10:04:00Z", closed_at="2026-07-01T10:36:00Z",
                 metadata={"work_dir": str(cls.rig), "session_key": "abc123"}),
            bead("ga-sess2", issue_type="session", labels=["agent:product/planner-1"],
                 created_at="2026-07-01T10:10:00Z", closed_at="2026-07-01T10:20:00Z",
                 metadata={}),
            bead("ga-nudge1", issue_type="nudge", labels=["agent:product/run-operator-1"],
                 created_at="2026-07-01T10:05:00Z"),
            bead("ga-other-rig", issue_type="session", labels=["agent:platform/run-operator-1"],
                 created_at="2026-07-01T10:05:00Z"),
            bead("ga-out-of-window", issue_type="session",
                 labels=["agent:product/run-operator-2"],
                 created_at="2026-06-01T10:05:00Z"),
        ]
        (base / "rig-beads.json").write_text(json.dumps(rig_beads), encoding="utf-8")
        (base / "city-beads.json").write_text(json.dumps(city_beads), encoding="utf-8")

        gc_stub = base / "bin" / "gc"
        gc_stub.write_text(FAKE_GC, encoding="utf-8")
        gc_stub.chmod(0o755)

        (cls.city / ".gc" / "events.jsonl").write_text("\n".join([
            json.dumps({"ts": "2026-07-01T10:05:00Z", "subject": "ga-s1", "type": "bead.started"}),
            json.dumps({"ts": "2026-07-01T10:06:00Z", "session_id": "ga-sess1", "type": "session.woke"}),
            json.dumps({"ts": "2026-07-01T10:07:00Z", "subject": "ga-nope", "type": "bead.updated"}),
            json.dumps({"ts": "2026-06-01T10:07:00Z", "subject": "ga-s1", "type": "bead.created"}),
            "{ this is not json",
        ]) + "\n", encoding="utf-8")

        (cls.city / ".gc" / "usage.jsonl").write_text("\n".join([
            json.dumps({"kind": "model", "run_id": ROOT, "step_id": "plan",
                        "input_tokens": 1000, "output_tokens": 200,
                        "cost_usd_estimate": 0.5, "idempotency_key": "k1"}),
            json.dumps({"kind": "compute", "session_id": "ga-sess1", "wall_seconds": 60.0,
                        "idempotency_key": "k2"}),
            json.dumps({"kind": "model", "run_id": "ga-somebody-else", "input_tokens": 9,
                        "idempotency_key": "k3"}),
            "{ not json either",
        ]) + "\n", encoding="utf-8")

        (cls.city / "packs.lock").write_text("profiler = 0.1.0\n", encoding="utf-8")

        transcript_dir = cls.home / ".claude" / "projects" / collect.project_slug(str(cls.rig))
        transcript_dir.mkdir(parents=True)
        (transcript_dir / "abc123.jsonl").write_text(
            json.dumps({"type": "assistant", "uuid": "u1"}) + "\n", encoding="utf-8")

        subprocess.run(["git", "init", "-q", str(cls.rig)], check=True)
        (cls.rig / "README.md").write_text("rig\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(cls.rig), "add", "."], check=True)
        subprocess.run(["git", "-C", str(cls.rig), "-c", "user.email=t@example.com",
                        "-c", "user.name=T", "commit", "-q", "-m", "seed"], check=True)

        env = {
            "PATH": f"{base / 'bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "HOME": str(cls.home),
            "FAKE_BD_RIG": str(base / "rig-beads.json"),
            "FAKE_BD_CITY": str(base / "city-beads.json"),
        }
        cls.proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "profile_collect.py"), ROOT,
             "--rig", str(cls.rig), "--city", str(cls.city), "--out", str(cls.out)],
            capture_output=True, text=True, env=env)
        cls.manifest = json.loads((cls.out / "manifest.json").read_text(encoding="utf-8")) \
            if (cls.out / "manifest.json").exists() else {}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_collect_succeeds(self) -> None:
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertIn("capture:", self.proc.stdout)

    def test_manifest_declares_its_schema_and_window(self) -> None:
        self.assertEqual(self.manifest["schema"], "gc.profile.capture.v1")
        self.assertEqual(self.manifest["root"], ROOT)
        # 2 min of margin either side of the root's own span.
        self.assertTrue(self.manifest["window"]["start"].startswith("2026-07-01T09:58:00"))
        self.assertTrue(self.manifest["window"]["end"].startswith("2026-07-01T12:02:00"))

    def test_bead_closure_excludes_other_runs(self) -> None:
        beads = json.loads((self.out / "beads.json").read_text(encoding="utf-8"))
        self.assertEqual([b["id"] for b in beads], [ROOT, "ga-s1"])
        self.assertEqual(self.manifest["sources"]["beads"], {"count": 2, "store_total": 3})

    def test_session_beads_are_filtered_by_rig_and_window(self) -> None:
        sessions = json.loads((self.out / "session-beads.json").read_text(encoding="utf-8"))
        ids = [b["id"] for b in sessions]
        self.assertEqual(sorted(ids), ["ga-nudge1", "ga-sess1", "ga-sess2"])
        self.assertNotIn("ga-other-rig", ids, "another rig's sessions are not this run's")
        self.assertNotIn("ga-out-of-window", ids)
        self.assertEqual(self.manifest["sources"]["session_beads"],
                         {"count": 3, "sessions": 2})

    def test_event_slice_keeps_only_this_runs_subjects_in_window(self) -> None:
        with gzip.open(self.out / "events.window.jsonl.gz", "rt") as f:
            events = [json.loads(l) for l in f if l.strip()]
        self.assertEqual([e["type"] for e in events], ["bead.started", "session.woke"])
        self.assertEqual(self.manifest["sources"]["events"]["count"], 2)

    def test_usage_slice_keeps_only_this_runs_facts(self) -> None:
        lines = (self.out / "usage.window.jsonl").read_text(encoding="utf-8").splitlines()
        keys = [json.loads(l)["idempotency_key"] for l in lines if l.strip()]
        self.assertEqual(keys, ["k1", "k2"], "another run's facts must not be captured")
        self.assertEqual(self.manifest["sources"]["usage"], {"count": 2})

    def test_transcripts_resolve_by_session_key_and_gaps_are_disclosed(self) -> None:
        self.assertEqual(self.manifest["sources"]["transcripts"]["found"], 1)
        self.assertEqual(self.manifest["sources"]["transcripts"]["by"], {"session_key": 1})
        self.assertEqual(self.manifest["sources"]["transcripts"]["missing"], ["ga-sess2"])
        with gzip.open(self.out / "transcripts" / "ga-sess1.jsonl.gz", "rt") as f:
            self.assertIn("assistant", f.read())
        self.assertTrue(any("transcripts unresolved" in g for g in self.manifest["gaps"]))

    def test_formula_provenance_and_git_are_captured(self) -> None:
        prov = json.loads((self.out / "formula-provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(prov["formula"], "build-from-requirements")
        self.assertEqual(prov["graphv2_root_key"], "k1")
        self.assertEqual(prov["packs_lock"], "profiler = 0.1.0\n")
        self.assertEqual(self.manifest["sources"]["git"]["commits"], 1)

    def test_every_captured_file_is_hashed(self) -> None:
        files = self.manifest["files"]
        self.assertIn("beads.json", files)
        self.assertNotIn("manifest.json", files, "the manifest cannot hash itself")
        for name, meta in files.items():
            self.assertTrue(meta["hash"].startswith("sha256:"), name)
            self.assertEqual(meta["bytes"], (self.out / name).stat().st_size, name)

    def test_the_capture_reports_cleanly(self) -> None:
        # The point of collect: report must be able to read what it wrote.
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "profile_report.py"), ROOT,
             "--capture", str(self.out)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("total: 120.0m", proc.stdout)
        self.assertIn("plan the work", proc.stdout)
        self.assertIn("tokens: in 1000 out 200", proc.stdout)
        self.assertIn("runtime wall: 60.0s", proc.stdout)
        self.assertIn("est cost: $0.5000", proc.stdout)


class CollectFailureTests(unittest.TestCase):
    def test_no_city_is_a_usage_error(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "profile_collect.py"), ROOT],
            capture_output=True, text=True,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no city", proc.stderr)

    def test_missing_optional_sources_are_gaps_not_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            rig, city, out, home, binder = (base / "rig", base / "city", base / "out",
                                            base / "home", base / "bin")
            for d in (rig, city / ".gc", home, binder):
                d.mkdir(parents=True)
            (base / "beads.json").write_text(json.dumps([
                bead(ROOT, created_at="2026-07-01T10:00:00Z")]), encoding="utf-8")
            (base / "empty.json").write_text("[]", encoding="utf-8")
            gc_stub = binder / "gc"
            gc_stub.write_text(FAKE_GC, encoding="utf-8")
            gc_stub.chmod(0o755)
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "profile_collect.py"), ROOT,
                 "--rig", str(rig), "--city", str(city), "--out", str(out)],
                capture_output=True, text=True,
                env={"PATH": f"{binder}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                     "HOME": str(home),
                     "FAKE_BD_RIG": str(base / "beads.json"),
                     "FAKE_BD_CITY": str(base / "empty.json")})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            gaps = manifest["gaps"]
            self.assertTrue(any("root not closed" in g for g in gaps), gaps)
            self.assertTrue(any("events log missing" in g for g in gaps), gaps)
            self.assertTrue(any("usage.jsonl not found" in g for g in gaps), gaps)
            # No usage file means report says the dimension is missing, not zero.
            self.assertFalse((out / "usage.window.jsonl").exists())

    def test_a_bd_failure_surfaces_rather_than_writing_a_hollow_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            rig, city, binder = base / "rig", base / "city", base / "bin"
            for d in (rig, city / ".gc", binder):
                d.mkdir(parents=True)
            gc_stub = binder / "gc"
            gc_stub.write_text("#!/bin/sh\necho 'store is locked' >&2\nexit 1\n", encoding="utf-8")
            gc_stub.chmod(0o755)
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "profile_collect.py"), ROOT,
                 "--rig", str(rig), "--city", str(city), "--out", str(base / "out")],
                capture_output=True, text=True,
                env={"PATH": f"{binder}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                     "HOME": str(base)})
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("store is locked", proc.stderr)


if __name__ == "__main__":
    unittest.main()
