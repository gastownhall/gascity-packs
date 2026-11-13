"""nudge-project-leads.sh against a fake `gc`: which sessions it selects, how it
calls `gc session nudge`, and that a failure never reads as success."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


PACK_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PACK_ROOT / "assets" / "scripts" / "nudge-project-leads.sh"
MESSAGE = "Triage tick: read your brief, survey your rig, write rollups."

FAKE_GC = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_LOG"
if [[ "$1 $2" == "session list" ]]; then
  cat "$FAKE_LIST"
  exit "${FAKE_LIST_RC:-0}"
fi
if [[ "$1 $2" == "session nudge" ]]; then
  for bad in ${FAKE_FAIL_IDS:-}; do
    if [[ "$3" == "$bad" ]]; then echo "session $3 not running" >&2; exit 1; fi
  done
  exit 0
fi
echo "fake gc: unexpected call: $*" >&2
exit 2
"""


def bash_binaries() -> list[str]:
    found, seen = [], set()
    for candidate in ("/bin/bash", shutil.which("bash")):
        if candidate and os.access(candidate, os.X_OK) and os.path.realpath(candidate) not in seen:
            seen.add(os.path.realpath(candidate))
            found.append(candidate)
    return found


@pytest.fixture(params=bash_binaries())
def run(request, tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gc = bindir / "gc"
    gc.write_text(FAKE_GC)
    gc.chmod(0o755)
    log = tmp_path / "gc.log"
    listing = tmp_path / "list.json"

    def _run(payload, list_rc=0, fail_ids=()):
        listing.write_text(payload if isinstance(payload, str) else json.dumps(payload))
        env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}", FAKE_LOG=str(log),
                   FAKE_LIST=str(listing), FAKE_LIST_RC=str(list_rc), FAKE_FAIL_IDS=" ".join(fail_ids))
        proc = subprocess.run([request.param, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
        calls = log.read_text().splitlines() if log.exists() else []
        log.unlink(missing_ok=True)
        nudged = [c.split(" ", 3)[2] for c in calls if c.startswith("session nudge ")]
        return proc, calls, nudged

    return _run


def session(sid, template, state="active", closed=False):
    return {"id": sid, "template": template, "state": state, "closed": closed}


def envelope(*sessions):
    return {"schema_version": "1", "filters": {}, "sessions": list(sessions), "summary": {}}


def test_selects_rig_scoped_project_leads_under_any_binding(run):
    proc, calls, nudged = run(envelope(
        session("s1", "alpha/oversight.project-lead"),
        session("s2", "beta/oversight-rig.project-lead"),
        session("s3", "project-lead"),
        session("s4", "alpha/oversight.project-lead", state="suspended"),
        session("s5", "alpha/oversight.project-lead", closed=True),
        session("s6", "alpha/gastown.polecat"),
        session("s7", "alpha/notproject-lead"),
        session("s8", "alpha/oversight.project-lead-helper"),
        session("s9", ""),
        {"id": "s10", "state": "active"},
    ))
    assert proc.returncode == 0, proc.stderr
    assert nudged == ["s1", "s2", "s3"]
    assert "nudged 3 of 3" in proc.stdout


def test_message_is_positional_not_a_flag(run):
    proc, calls, _ = run(envelope(session("s1", "alpha/oversight.project-lead")))
    assert proc.returncode == 0, proc.stderr
    assert "session list --json" in calls   # without --json gc prints a table
    assert f"session nudge s1 {MESSAGE}" in calls
    assert not any("--message" in c for c in calls)


def test_accepts_the_api_envelope_whose_rows_have_no_closed_field(run):
    rows = [{"id": "s1", "template": "alpha/oversight.project-lead", "state": "active"}]
    proc, _, nudged = run({"_cache_age_s": 3, "sessions": rows})
    assert proc.returncode == 0, proc.stderr
    assert nudged == ["s1"]


def test_script_uses_no_bash4_only_constructs():
    # macOS ships bash 3.2 as /bin/bash; the old script died there on mapfile.
    import re
    text = SCRIPT.read_text()
    for pattern in (r"\bmapfile\b", r"\breadarray\b", r"\bdeclare\s+-A\b", r"\$\{[^}]*(,,|\^\^)\}"):
        assert not re.search(pattern, text), pattern


def test_accepts_the_older_bare_array_listing(run):
    proc, _, nudged = run([session("s1", "alpha/oversight.project-lead")])
    assert proc.returncode == 0, proc.stderr
    assert nudged == ["s1"]


def test_no_project_lead_is_success_and_nudges_nothing(run):
    proc, _, nudged = run(envelope(session("s6", "alpha/gastown.polecat")))
    assert proc.returncode == 0, proc.stderr
    assert nudged == []
    assert "no active project-lead sessions" in proc.stdout


@pytest.mark.parametrize("payload, list_rc", [
    (envelope(session("s1", "alpha/oversight.project-lead")), 1),   # gc itself failed
    ("gc: store_slow: all providers failed", 0),                   # not JSON
    ("", 0),                                                         # empty output, exit 0
    ("  \n", 0),                                                    # whitespace only
    ({"schema_version": "1", "summary": {}}, 0),                    # envelope without sessions
    ('"a string"', 0),                                               # neither array nor object
])
def test_an_unreadable_listing_fails_instead_of_reading_as_empty(run, payload, list_rc):
    proc, _, nudged = run(payload, list_rc=list_rc)
    assert proc.returncode == 1
    assert nudged == []
    assert "no active project-lead sessions" not in proc.stdout


def test_one_failed_nudge_fails_the_run_after_trying_every_session(run):
    proc, _, nudged = run(envelope(session("s1", "a/o.project-lead"), session("s2", "b/o.project-lead")),
                          fail_ids=["s1"])
    assert proc.returncode == 1
    assert nudged == ["s1", "s2"]
    assert "nudge failed for s1: session s1 not running" in proc.stderr
    assert "nudged 1 of 2" in proc.stdout


def test_every_nudge_failing_is_not_success(run):
    proc, _, _ = run(envelope(session("s1", "a/o.project-lead")), fail_ids=["s1"])
    assert proc.returncode == 1
    assert "nudged 0 of 1" in proc.stdout
