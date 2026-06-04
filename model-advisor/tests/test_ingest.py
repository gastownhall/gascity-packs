"""Tests for the model-advisor outcome harvester + capture hook.

These tests own the *telemetry write side* contract (bead bh-e39): the
``capture-invocation.sh`` Stop/SubagentStop hook and ``modeladvisor/ingest.py``
(the quality harvester).  The engine/store/config are sibling beads.

To stay runnable *before* the sibling engine/store land — the package
``__init__`` eagerly re-exports them, so a plain ``import modeladvisor.ingest``
would raise until they exist — we load ``modeladvisor/ingest.py`` as a
**standalone module** via importlib, registering it in ``sys.modules`` before
executing it (so its own ``@dataclass`` decorators resolve).  ``ingest.py`` then
loads ``modeladvisor.config`` directly via its own degraded-import path, so this
suite is hermetic regardless of sibling timing.  Once the engine/store land,
``import modeladvisor.ingest`` would also work; this loader keeps the tests green
either way.

Nothing here touches live ``/Users/jayse/Code/.beads`` or ``.gc``: every test
operates on JSONL fixtures created under ``tmp_path``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PACK_DIR = Path(__file__).resolve().parents[1]
INGEST_PATH = PACK_DIR / "modeladvisor" / "ingest.py"
HOOK_PATH = PACK_DIR / "hooks" / "capture-invocation.sh"


def _load_ingest_module():
    """Load ingest.py standalone, bypassing the package __init__ re-exports."""
    spec = importlib.util.spec_from_file_location("mad_ingest_under_test", INGEST_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mad_ingest_under_test"] = mod  # register BEFORE exec (dataclasses)
    spec.loader.exec_module(mod)
    return mod


ingest = _load_ingest_module()


# --------------------------------------------------------------------------- #
# Fixtures                                                                      #
# --------------------------------------------------------------------------- #


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A throwaway project root with a .beads/telemetry dir (never live state)."""
    tel = tmp_path / ".beads" / "telemetry"
    tel.mkdir(parents=True)
    return tmp_path


def _inv_path(project: Path) -> Path:
    return project / ".beads" / "telemetry" / "invocations.jsonl"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _dispatch(
    *,
    bead_id: str = "",
    session_id: str = "",
    provider: str = "claude",
    agent: str = "polecat",
    shape: str = "implement",
    tier_id: str = "sonnet",
) -> dict:
    return {
        "schema_version": "advisor.v1",
        "kind": "dispatch",
        "ts": "2026-06-03T10:00:00Z",
        "bead_id": bead_id,
        "session_id": session_id,
        "provider": provider,
        "agent": agent,
        "shape": shape,
        "tier_id": tier_id,
        "model": "claude-sonnet-4-5",
        "cell_key": f"{provider}::{agent}::{shape}::{tier_id}",
    }


def _bead(
    *,
    bead_id: str,
    status: str = "closed",
    metadata: dict | None = None,
    labels: list[str] | None = None,
) -> dict:
    b: dict = {"id": bead_id, "status": status}
    if metadata is not None:
        b["metadata"] = metadata
    if labels is not None:
        b["labels"] = labels
    return b


def _event(event_type: str, bead: dict) -> dict:
    return {"type": event_type, "ts": "2026-06-03T10:30:00Z", "payload": {"bead": bead}}


def _read_quality(project: Path) -> list[dict]:
    out = []
    for line in open(_inv_path(project), encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d.get("kind") == "quality":
            out.append(d)
    return out


# --------------------------------------------------------------------------- #
# (1) bead.closed + gc.outcome=pass  ->  q=1 quality record joined to dispatch  #
# --------------------------------------------------------------------------- #


def test_close_pass_emits_q1_joined_to_dispatch(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-100", session_id="sess-A")])

    events = project / "events.jsonl"
    _write_jsonl(
        events,
        [
            _event(
                "bead.closed",
                _bead(
                    bead_id="bh-100",
                    status="closed",
                    metadata={"gc.outcome": "pass", "session_id": "sess-A"},
                ),
            )
        ],
    )

    res = ingest.harvest(project_root=project, events_path=events)

    assert res.written == 1
    qrecs = _read_quality(project)
    assert len(qrecs) == 1
    q = qrecs[0]
    # schema + join correctness (DESIGN §5.2)
    assert q["schema_version"] == "advisor.v1"
    assert q["kind"] == "quality"
    assert q["bead_id"] == "bh-100"
    assert q["cell_key"] == "claude::polecat::implement::sonnet"  # from the dispatch
    assert q["q"] == 1
    assert q["channel"] == "close"
    assert q["weight"] == 1.0  # w_close
    assert q["signal"] == "pass"
    assert q["n_dep"] == 1
    # the join + schema fields the engine reads
    assert set(q) >= {
        "schema_version", "kind", "ts", "bead_id", "cell_key",
        "q", "channel", "weight", "signal", "n_dep",
    }


def test_bare_close_without_outcome_is_still_q1(project: Path):
    """A clean close with no gc.outcome metadata is a success (DESIGN §4.1)."""
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-101", session_id="s1")])
    events = project / "events.jsonl"
    _write_jsonl(
        events,
        [_event("bead.closed", _bead(bead_id="bh-101", status="closed",
                                     metadata={"session_id": "s1"}))],
    )
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 1
    q = _read_quality(project)[0]
    assert q["q"] == 1 and q["signal"] == "closed" and q["channel"] == "close"


# --------------------------------------------------------------------------- #
# (2) reopen  ->  q=0                                                           #
# --------------------------------------------------------------------------- #


def test_reopen_emits_q0(project: Path):
    inv = _inv_path(project)
    # dispatch joined by session_id (reopened bead carries no dispatch bead_id key)
    _write_jsonl(inv, [_dispatch(bead_id="", session_id="sess-B",
                                 agent="refinery", shape="review", tier_id="opus")])
    events = project / "events.jsonl"
    _write_jsonl(
        events,
        [
            _event(
                "Reopened",
                _bead(bead_id="bh-200", status="open",
                      metadata={"session_id": "sess-B"}),
            )
        ],
    )
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 1
    q = _read_quality(project)[0]
    assert q["q"] == 0
    assert q["channel"] == "close"
    assert q["signal"] == "reopened"
    assert q["cell_key"] == "claude::refinery::review::opus"  # joined by session_id


def test_failure_class_hard_and_outcome_fail_are_q0(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [
        _dispatch(bead_id="bh-300", session_id="s3"),
        _dispatch(bead_id="bh-301", session_id="s4", shape="lookup", tier_id="haiku"),
    ])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.closed", _bead(bead_id="bh-300", status="closed",
                                    metadata={"gc.outcome": "fail", "session_id": "s3"})),
        _event("bead.closed", _bead(bead_id="bh-301", status="closed",
                                    metadata={"gc.failure_class": "hard", "session_id": "s4"})),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 2
    by_cell = {q["cell_key"]: q for q in _read_quality(project)}
    assert by_cell["claude::polecat::implement::sonnet"]["q"] == 0
    assert by_cell["claude::polecat::implement::sonnet"]["signal"] == "fail"
    assert by_cell["claude::polecat::lookup::haiku"]["q"] == 0
    assert by_cell["claude::polecat::lookup::haiku"]["signal"] == "failure_class:hard"


def test_escalation_label_is_q0(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-400", session_id="s5")])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.updated", _bead(bead_id="bh-400", status="open",
                                     metadata={"session_id": "s5"},
                                     labels=["health:failing", "agent:gastown.polecat"])),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 1
    q = _read_quality(project)[0]
    assert q["q"] == 0 and q["signal"] == "escalated"


# --------------------------------------------------------------------------- #
# Dropped signals: transient failure, blocked review, still-open bead          #
# --------------------------------------------------------------------------- #


def test_transient_failure_is_dropped(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-500", session_id="s6")])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.closed", _bead(bead_id="bh-500", status="closed",
                                    metadata={"gc.outcome": "fail",
                                              "gc.failure_class": "transient",
                                              "session_id": "s6"})),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 0  # transient is not a quality signal (DESIGN §4.1)
    assert res.skipped == 1
    assert _read_quality(project) == []


def test_blocked_review_is_dropped(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-510", session_id="s7")])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.closed", _bead(bead_id="bh-510", status="closed",
                                    metadata={"gc.verdict": "blocked", "session_id": "s7"})),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 0 and res.skipped == 1


def test_open_bead_no_verdict_is_skipped(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-520", session_id="s8")])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.updated", _bead(bead_id="bh-520", status="in_progress",
                                     metadata={"session_id": "s8"})),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 0 and res.skipped == 1


# --------------------------------------------------------------------------- #
# Attribution: a closure with no recorded dispatch is dropped (DESIGN §4.4)     #
# --------------------------------------------------------------------------- #


def test_unjoined_closure_is_dropped_and_reported(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-100", session_id="sess-A")])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.closed", _bead(bead_id="bh-NOPE", status="closed",
                                    metadata={"gc.outcome": "pass",
                                              "session_id": "sess-UNKNOWN"})),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 0
    assert res.records == []
    assert "bh-NOPE" in res.unjoined


# --------------------------------------------------------------------------- #
# (3) channel-weight precedence: eval > review > close; highest fidelity wins   #
# --------------------------------------------------------------------------- #


def test_channel_precedence_eval_beats_review_beats_close(project: Path):
    """One dispatch with eval+review+close-able metadata yields ONE eval obs."""
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-600", session_id="s9")])
    events = project / "events.jsonl"
    # The same bead carries an eval verdict, a review verdict, AND is closed.
    # Highest fidelity (eval) must win; weight = w_eval = 5.
    _write_jsonl(events, [
        _event("bead.closed", _bead(bead_id="bh-600", status="closed",
                                    metadata={"gc.eval_verdict": "pass",
                                              "gc.verdict": "fail",
                                              "gc.outcome": "pass",
                                              "session_id": "s9"})),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 1
    q = _read_quality(project)[0]
    assert q["channel"] == "eval"
    assert q["weight"] == 5.0  # w_eval
    assert q["q"] == 1
    assert q["signal"] == "eval:pass"


def test_review_beats_close_weight_3(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-610", session_id="s10")])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.closed", _bead(bead_id="bh-610", status="closed",
                                    metadata={"gc.verdict": "pass_with_findings",
                                              "session_id": "s10"})),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    q = _read_quality(project)[0]
    assert q["channel"] == "review"
    assert q["weight"] == 3.0  # w_review
    assert q["q"] == 1  # pass_with_findings -> 1 (DESIGN §4.2)
    assert q["signal"] == "review:pass_with_findings"


def test_dedup_collapses_close_then_reopen_to_one_negative(project: Path):
    """Two events on the same cell (close, then reopen) collapse to one obs.

    On a fidelity tie (both 'close'), the negative (reopen) wins — a reopen after
    a close must not be masked by the close (DESIGN §4.4 conservative precedence).
    """
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-700", session_id="s11")])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.closed", _bead(bead_id="bh-700", status="closed",
                                    metadata={"gc.outcome": "pass", "session_id": "s11"})),
        _event("Reopened", _bead(bead_id="bh-700", status="open",
                                 metadata={"session_id": "s11"})),
    ])
    res = ingest.harvest(project_root=project, events_path=events)
    assert res.written == 1  # collapsed to a single observation for the cell
    q = _read_quality(project)[0]
    assert q["q"] == 0
    assert q["signal"] == "reopened"


# --------------------------------------------------------------------------- #
# bd-show mode (explicit bead objects) + write=False                           #
# --------------------------------------------------------------------------- #


def test_beads_iterable_mode_and_dry_run(project: Path):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-800", session_id="s12")])
    bead = _bead(bead_id="bh-800", status="closed",
                 metadata={"gc.outcome": "pass", "session_id": "s12"})
    # write=False must NOT append to invocations.jsonl
    res = ingest.harvest(project_root=project, beads=[bead], write=False)
    assert len(res.records) == 1
    assert res.written == 0
    assert _read_quality(project) == []  # nothing appended
    assert res.records[0]["q"] == 1


def test_fetch_via_cli_parses_array(monkeypatch, project: Path):
    """bd-show mode parses the JSON *array* that `gc bd show --json` emits."""
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-900", session_id="s13")])

    class _Proc:
        returncode = 0
        stdout = json.dumps([
            {"id": "bh-900", "status": "closed",
             "metadata": {"gc.outcome": "pass", "session_id": "s13"}}
        ])
        stderr = ""

    monkeypatch.setattr(ingest.subprocess, "run", lambda *a, **k: _Proc())
    res = ingest.harvest(project_root=project, bead_ids=["bh-900"], use_cli=True)
    assert res.written == 1
    assert _read_quality(project)[0]["q"] == 1


# --------------------------------------------------------------------------- #
# Robustness: malformed JSONL lines and missing files don't crash harvest      #
# --------------------------------------------------------------------------- #


def test_malformed_lines_and_missing_events_are_tolerated(project: Path):
    inv = _inv_path(project)
    with open(inv, "w", encoding="utf-8") as fh:
        fh.write("not json\n")
        fh.write(json.dumps(_dispatch(bead_id="bh-a", session_id="sa")) + "\n")
        fh.write("\n")
        fh.write("{ broken\n")
    # events path points at a non-existent file -> degrades to no closures.
    res = ingest.harvest(project_root=project,
                         events_path=project / "does-not-exist.jsonl")
    assert res.written == 0  # no closures, but no crash
    assert res.records == []


# --------------------------------------------------------------------------- #
# CLI entry: python -m modeladvisor.ingest behaviour via main()                #
# --------------------------------------------------------------------------- #


def test_cli_main_dry_run_json(project: Path, capsys):
    inv = _inv_path(project)
    _write_jsonl(inv, [_dispatch(bead_id="bh-c", session_id="sc")])
    events = project / "events.jsonl"
    _write_jsonl(events, [
        _event("bead.closed", _bead(bead_id="bh-c", status="closed",
                                    metadata={"gc.outcome": "pass", "session_id": "sc"})),
    ])
    rc = ingest.main([
        "--project-root", str(project),
        "--events", str(events),
        "--dry-run", "--json",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert len(payload) == 1 and payload[0]["q"] == 1
    # dry-run must not write
    assert _read_quality(project) == []


# --------------------------------------------------------------------------- #
# The capture hook: well-formed Stop payload -> dispatch record; exit 0 always  #
# --------------------------------------------------------------------------- #


def _run_hook(payload: str, env_extra: dict, cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra)
    # Ensure a sane PATH for jq/date/python3 inside the hook.
    env["PATH"] = (
        "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:"
        + env.get("PATH", "")
    )
    return subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=payload,
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
    )


@pytest.fixture()
def hook_project(tmp_path: Path) -> Path:
    (tmp_path / ".beads").mkdir(parents=True)
    return tmp_path


def test_hook_emits_wellformed_dispatch_from_stop_payload(hook_project: Path):
    payload = json.dumps({
        "hook_event_name": "Stop",
        "session_id": "bh-vt5",
        "cwd": str(hook_project),
    })
    proc = _run_hook(
        payload,
        {
            "GC_TEMPLATE": "whiskeyshop/gastown.polecat#3",
            "GC_AGENT_MODEL": "claude-opus-4-8",
            "GC_PROVIDER": "claude",
        },
        hook_project,
    )
    assert proc.returncode == 0
    inv = _inv_path(hook_project)
    assert inv.exists()
    rec = json.loads(open(inv).readline())
    assert rec["kind"] == "dispatch"
    assert rec["schema_version"] == "advisor.v1"
    assert rec["session_id"] == "bh-vt5"
    assert rec["provider"] == "claude"
    assert rec["agent"] == "polecat"  # base name derived from GC_TEMPLATE
    assert rec["agent_instance"] == "whiskeyshop/gastown.polecat#3"
    assert rec["rig"] == "whiskeyshop"
    assert rec["model"] == "claude-opus-4-8"
    # cell_key well-formed with unknown placeholders for shape/tier (engine fills)
    assert rec["cell_key"] == "claude::polecat::unknown::unknown"
    assert rec["source"] == "hook:Stop"


def test_hook_parses_tokens_and_model_from_transcript(hook_project: Path, tmp_path: Path):
    transcript = tmp_path / "transcript.jsonl"
    with open(transcript, "w") as fh:
        fh.write(json.dumps({"type": "assistant", "message": {
            "model": "claude-sonnet-4-5",
            "usage": {"input_tokens": 100, "output_tokens": 40,
                      "cache_read_input_tokens": 10}}}) + "\n")
        fh.write(json.dumps({"type": "assistant", "message": {
            "model": "claude-sonnet-4-5",
            "usage": {"input_tokens": 200, "output_tokens": 60,
                      "cache_creation_input_tokens": 5}}}) + "\n")
    payload = json.dumps({
        "hook_event_name": "SubagentStop",
        "session_id": "s-trans",
        "transcript_path": str(transcript),
        "cwd": str(hook_project),
    })
    proc = _run_hook(payload, {"GC_TEMPLATE": "gastown.polecat", "GC_PROVIDER": "claude"},
                     hook_project)
    assert proc.returncode == 0
    rec = json.loads(open(_inv_path(hook_project)).readline())
    assert rec["model"] == "claude-sonnet-4-5"  # parsed from transcript
    assert rec["tok_in"] == 315  # 100+10+200+5
    assert rec["tok_out"] == 100  # 40+60
    assert rec["source"] == "hook:SubagentStop"


def test_hook_exits_zero_on_empty_and_malformed_payload(hook_project: Path):
    inv = _inv_path(hook_project)
    # Empty payload: env-only record, exit 0.
    proc = _run_hook("", {"GC_TEMPLATE": "gastown.deacon", "GC_PROVIDER": "claude"},
                     hook_project)
    assert proc.returncode == 0
    assert inv.exists()  # still emits a (degraded) record
    first = json.loads(open(inv).readline())
    assert first["agent"] == "deacon" and first["kind"] == "dispatch"

    # Malformed (non-JSON) payload: must still exit 0 and not crash.
    proc2 = _run_hook("}{ this is not json", {"GC_PROVIDER": "claude"}, hook_project)
    assert proc2.returncode == 0


def test_hook_escape_hatch_writes_nothing(hook_project: Path):
    proc = _run_hook(
        json.dumps({"hook_event_name": "Stop", "session_id": "x", "cwd": str(hook_project)}),
        {"MODEL_ADVISOR_DISABLE_CAPTURE": "1", "GC_PROVIDER": "claude"},
        hook_project,
    )
    assert proc.returncode == 0
    assert not _inv_path(hook_project).exists()  # no write under the escape hatch


def test_hook_no_beads_dir_is_noop(tmp_path: Path):
    """With no .beads anywhere up the tree, the hook emits nothing and exits 0."""
    sub = tmp_path / "nested" / "deep"
    sub.mkdir(parents=True)
    proc = _run_hook(
        json.dumps({"hook_event_name": "Stop", "session_id": "x", "cwd": str(sub)}),
        {"GC_PROVIDER": "claude"},
        sub,
    )
    assert proc.returncode == 0
    assert not (tmp_path / ".beads").exists()
