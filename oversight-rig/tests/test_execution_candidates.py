"""Tests for the Project Lead's durable execution-intent selector."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

BD_TAIL = ["b" + "d"]
SCRIPT = (
    Path(__file__).parents[1] / "assets" / "scripts" / "select-execution-candidates.py"
)
spec = importlib.util.spec_from_file_location("execution_candidates", SCRIPT)
assert spec and spec.loader
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)

RIG = "alpha"


def bead(
    bead_id: str,
    *,
    status: str = "open",
    metadata: dict[str, Any] | None = None,
    notes: str = "",
    description: str = "",
    labels: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": bead_id,
        "status": status,
        "metadata": metadata or {},
        "notes": notes,
        "description": description,
        "labels": labels or [],
    }


def root(
    root_id: str = "root-1",
    *,
    status: str = "in_progress",
    rig: str = RIG,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    defaults = {
        "gc.root_store_ref": f"rig:{rig}",
        "gc.kind": "workflow",
        "gc.formula_name": "mol-example",
        "gc.formula_contract": "graph.v2",
    }
    if metadata:
        defaults.update(metadata)
    return bead(root_id, status=status, metadata=defaults)


def fake_queries(
    monkeypatch: pytest.MonkeyPatch,
    ready: list[dict[str, Any]],
    rollups: list[dict[str, Any]] | None = None,
    roots: dict[str, list[dict[str, Any]]] | None = None,
) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []
    roots = roots or {}

    def query(*args: str) -> list[dict[str, Any]]:
        calls.append(args)
        if args[0] == "ready":
            key = args[args.index("--metadata-field") + 1]
            return [item for item in ready if key in item.get("metadata", {})]
        if args[0] == "list":
            return rollups or []
        assert args[0] == "show"
        assert args[1:3] == ("--rig", RIG)
        return roots[args[3]]

    monkeypatch.setattr(selector, "command_json", query)
    return calls


def test_plain_ready_backlog_is_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_queries(monkeypatch, [bead("backlog")])
    assert selector.select(RIG, 7)["candidates"] == []
    assert calls[0] == (
        "ready",
        "--rig",
        RIG,
        "--metadata-field",
        "gc.routed_to",
        "--json",
        "--limit",
        "8",
    )
    assert all(call[0] in {"ready", "list", "show"} for call in calls)


def test_large_uncommitted_backlog_does_not_exhaust_intent_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backlog = [bead(f"backlog-{index}") for index in range(100)]
    routed = bead("routed", metadata={"gc.routed_to": "alpha/polecat"})
    fake_queries(monkeypatch, [*backlog, routed])
    assert selector.select(RIG, 1)["candidates"] == [
        {"id": "routed", "classification": "routed", "route": "alpha/polecat"}
    ]


def test_existing_valid_route_is_preserved_as_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routed = bead("routed", metadata={"gc.routed_to": "alpha/polecat"})
    fake_queries(monkeypatch, [routed])
    assert selector.select(RIG, 7)["candidates"] == [
        {"id": "routed", "classification": "routed", "route": "alpha/polecat"}
    ]


def test_existing_rig_local_route_is_preserved_as_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routed = bead("warrant", metadata={"gc.routed_to": "gastown.dog"})
    fake_queries(monkeypatch, [routed], roots={"warrant": [routed]})
    assert selector.select(RIG, 7)["candidates"] == [
        {"id": "warrant", "classification": "routed", "route": "gastown.dog"}
    ]


def test_unproven_bare_route_from_federated_ready_is_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foreign = bead("foreign", metadata={"gc.routed_to": "beta.worker"})
    fake_queries(monkeypatch, [foreign], roots={"foreign": []})
    assert selector.select(RIG, 7)["candidates"] == []


def test_cleared_route_is_absent_without_suppressing_other_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleared = bead("direct-handoff", metadata={"gc.routed_to": ""})
    routed = bead("routed", metadata={"gc.routed_to": "alpha/polecat"})
    fake_queries(monkeypatch, [cleared, routed])
    assert selector.select(RIG, 7)["candidates"] == [
        {"id": "routed", "classification": "routed", "route": "alpha/polecat"}
    ]


@pytest.mark.parametrize(
    "route", ["beta/polecat", "alpha/", " alpha/polecat", "alpha/pole cat"]
)
def test_invalid_or_foreign_routes_are_excluded(
    monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    fake_queries(monkeypatch, [bead("bad-route", metadata={"gc.routed_to": route})])
    with pytest.raises(selector.SelectorError):
        selector.select(RIG, 7)


def test_live_formula_member_is_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    member = bead(
        "step",
        metadata={
            "gc.root_bead_id": "root-1",
            "gc.root_store_ref": "rig:alpha",
            "gc.routed_to": "alpha/core.control-dispatcher",
        },
    )
    fake_queries(monkeypatch, [member], roots={"root-1": [root()]})
    assert selector.select(RIG, 7)["candidates"] == [
        {
            "id": "step",
            "classification": "formula-routed",
            "route": "alpha/core.control-dispatcher",
        }
    ]


def test_formula_member_without_existing_route_is_not_dispatched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member = bead(
        "step", metadata={"gc.root_bead_id": "root-1", "gc.root_store_ref": "rig:alpha"}
    )
    fake_queries(monkeypatch, [member], roots={"root-1": [root()]})
    outcome = selector.select(RIG, 7)
    assert outcome["candidates"] == []
    assert outcome["anomalies"] == [
        {"id": "step", "reason": "live-formula-missing-route"}
    ]


@pytest.mark.parametrize(
    "roots",
    [
        {"root-1": [root(status="closed")]},
        {"root-1": []},
        {"root-1": [root(rig="beta")]},
        {"root-1": [root(metadata={"gc.kind": "task", "gc.formula_contract": ""})]},
        {"root-1": [root(), root()]},
    ],
)
def test_invalid_or_closed_formula_roots_fail_closed(
    monkeypatch: pytest.MonkeyPatch, roots: dict[str, list[dict[str, Any]]]
) -> None:
    member = bead(
        "step",
        metadata={
            "gc.root_bead_id": "root-1",
            "gc.root_store_ref": "rig:alpha",
            "gc.routed_to": "alpha/polecat",
        },
    )
    fake_queries(monkeypatch, [member], roots=roots)
    if len(roots["root-1"]) != 1:
        with pytest.raises(selector.SelectorError):
            selector.select(RIG, 7)
    else:
        assert selector.select(RIG, 7)["candidates"] == []


@pytest.mark.parametrize(
    "candidate,rollups",
    [
        (
            bead(
                "blocked", status="blocked", metadata={"gc.routed_to": "alpha/polecat"}
            ),
            [],
        ),
        (
            bead(
                "deferred",
                status="deferred",
                metadata={"gc.routed_to": "alpha/polecat"},
            ),
            [],
        ),
        (
            bead(
                "human-note",
                metadata={"gc.routed_to": "alpha/polecat"},
                notes="needs decision from owner",
            ),
            [],
        ),
        (
            bead(
                "human-description",
                metadata={"gc.routed_to": "alpha/polecat"},
                description="Blocked: needs-api from owner",
            ),
            [],
        ),
        (
            bead(
                "human-tier",
                metadata={"gc.routed_to": "alpha/polecat", "gc.tier": "needs-api"},
            ),
            [],
        ),
        (
            bead("escalated", metadata={"gc.routed_to": "alpha/polecat"}),
            [bead("rollup", labels=["rollup", "severity:escalate", "ref:escalated"])],
        ),
        (
            bead("human-route", metadata={"gc.routed_to": "human"}),
            [],
        ),
    ],
)
def test_non_dispatchable_or_human_gated_work_is_excluded(
    monkeypatch: pytest.MonkeyPatch,
    candidate: dict[str, Any],
    rollups: list[dict[str, Any]],
) -> None:
    fake_queries(monkeypatch, [candidate], rollups=rollups)
    assert selector.select(RIG, 7)["candidates"] == []


def test_malformed_metadata_in_intent_query_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed = {"id": "bad", "status": "open", "metadata": []}

    def query(*args: str) -> list[dict[str, Any]]:
        return [malformed] if args[0] == "ready" else []

    monkeypatch.setattr(selector, "command_json", query)
    with pytest.raises(selector.SelectorError):
        selector.select(RIG, 7)


def test_query_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fails(*_args: str) -> list[dict[str, Any]]:
        raise selector.SelectorError("query failed")

    monkeypatch.setattr(selector, "command_json", fails)
    with pytest.raises(selector.SelectorError):
        selector.select(RIG, 7)


def test_foreign_root_reference_is_excluded_without_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = fake_queries(
        monkeypatch,
        [
            bead(
                "foreign",
                metadata={"gc.root_bead_id": "root-1", "gc.root_store_ref": "rig:beta"},
            )
        ],
    )
    with pytest.raises(selector.SelectorError):
        selector.select(RIG, 7)
    assert all(call[0] != "show" for call in calls)


def test_escalation_rollup_overflow_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rollups = [
        bead("rollup-1", labels=["rollup", "severity:escalate", "ref:one"]),
        bead("rollup-2", labels=["rollup", "severity:escalate", "ref:two"]),
    ]
    fake_queries(monkeypatch, [], rollups=rollups)
    with pytest.raises(selector.SelectorError):
        selector.select(RIG, 1)


def test_row_bound_and_duplicate_candidate_ids_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = {"gc.routed_to": "alpha/polecat"}
    fake_queries(monkeypatch, [bead("one", metadata=route), bead("two", metadata=route)])
    with pytest.raises(selector.SelectorError):
        selector.select(RIG, 1)

    fake_queries(
        monkeypatch,
        [bead("same", metadata=route), bead("same", metadata=route)],
    )
    with pytest.raises(selector.SelectorError):
        selector.select(RIG, 7)


def test_bd_show_object_json_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown = root()
    completed = subprocess.CompletedProcess(
        ["gc"], 0, stdout=json.dumps(shown), stderr=""
    )
    monkeypatch.setattr(selector.subprocess, "run", lambda *_args, **_kwargs: completed)
    assert selector.command_json("show", "--rig", RIG, "root-1", "--json") == [shown]


def test_non_show_object_json_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = subprocess.CompletedProcess(
        ["gc"], 0, stdout=json.dumps(bead("unexpected")), stderr=""
    )
    monkeypatch.setattr(selector.subprocess, "run", lambda *_args, **_kwargs: completed)
    with pytest.raises(selector.SelectorError):
        selector.command_json("ready", "--rig", RIG, "--json")


def test_malformed_json_and_timeout_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed = subprocess.CompletedProcess(["gc"], 0, stdout="{", stderr="")
    monkeypatch.setattr(selector.subprocess, "run", lambda *_args, **_kwargs: malformed)
    with pytest.raises(selector.SelectorError):
        selector.command_json("ready", "--rig", RIG, "--json")

    def timeout(*_args: Any, **_kwargs: Any) -> None:
        raise subprocess.TimeoutExpired("gc", 10)

    monkeypatch.setattr(selector.subprocess, "run", timeout)
    with pytest.raises(selector.SelectorError):
        selector.command_json("ready", "--rig", RIG, "--json")


def test_conflicting_run_chain_metadata_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member = bead(
        "step",
        metadata={
            "workflow_id": "root-a",
            "gc.root_bead_id": "root-b",
            "gc.routed_to": "alpha/polecat",
        },
    )
    fake_queries(monkeypatch, [member])
    with pytest.raises(selector.SelectorError):
        selector.select(RIG, 7)


def test_arbitrary_tree_metadata_does_not_establish_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descendant = bead(
        "child", metadata={"parent_id": "root-1", "gc.parent_bead_id": "root-1"}
    )
    fake_queries(monkeypatch, [descendant])
    assert selector.select(RIG, 7)["candidates"] == []


def write_fake_gc(
    tmp_path: Path,
    ready: list[dict[str, Any]],
    rollups: list[dict[str, Any]],
    roots: dict[str, list[dict[str, Any]]],
) -> Path:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"ready": ready, "rollups": rollups, "roots": roots}))
    fake = tmp_path / "gc"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "pathlib.Path(os.environ['GC_FAKE_CALLS']).open('a').write(json.dumps(args) + '\\n')\n"
        "data = json.loads(pathlib.Path(os.environ['GC_FAKE_FIXTURE']).read_text())\n"
        "if args[0] == 'ready':\n"
        "    key = args[args.index('--metadata-field') + 1]\n"
        "    print(json.dumps([item for item in data['ready'] if key in item.get('metadata', {})]))\n"
        "elif args[:2] == ['b' + 'd', 'list']: print(json.dumps(data['rollups']))\n"
        "elif args[:2] == ['b' + 'd', 'show']: print(json.dumps(data['roots'].get(args[4], [])))\n"
        "else: sys.exit(8)\n"
    )
    fake.chmod(0o755)
    return fixture


def test_cli_uses_only_bounded_readonly_gc_queries(tmp_path: Path) -> None:
    ready = [bead("routed", metadata={"gc.routed_to": "alpha/polecat"})]
    fixture = write_fake_gc(tmp_path, ready, [], {})
    calls_file = tmp_path / "calls.jsonl"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GC_FAKE_FIXTURE": str(fixture),
        "GC_FAKE_CALLS": str(calls_file),
    }
    completed = subprocess.run(
        ["python3", str(SCRIPT), "--rig", RIG, "--json", "--max-rows", "7"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {
        "schema_version": 1,
        "candidates": [
            {"id": "routed", "classification": "routed", "route": "alpha/polecat"}
        ],
        "anomalies": [],
    }
    calls = [json.loads(line) for line in calls_file.read_text().splitlines()]
    expected_ready_calls = [
        [
            "ready",
            "--rig",
            RIG,
            "--metadata-field",
            key,
            "--json",
            "--limit",
            "8",
        ]
        for key in selector.INTENT_METADATA_KEYS
    ]
    assert calls == [
        *expected_ready_calls,
        [
            *BD_TAIL,
            "list",
            "--rig",
            RIG,
            "--label",
            "rollup",
            "--label",
            "severity:escalate",
            "--status",
            "open",
            "--json",
            "--limit",
            "8",
        ],
    ]
    assert all(
        call[0] == "ready" or call[:2] in [[*BD_TAIL, "list"], [*BD_TAIL, "show"]]
        for call in calls
    )


def test_cli_command_failure_returns_an_empty_safe_envelope(tmp_path: Path) -> None:
    fake = tmp_path / "gc"
    fake.write_text("#!/bin/sh\nexit 1\n")
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    completed = subprocess.run(
        ["python3", str(SCRIPT), "--rig", RIG, "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout) == {
        "schema_version": 1,
        "candidates": [],
        "anomalies": [],
    }
