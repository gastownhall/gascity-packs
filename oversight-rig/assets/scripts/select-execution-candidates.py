#!/usr/bin/env python3
"""Safely select Project Lead candidates with existing durable execution intent.

The selector is read-only. It uses bounded public ``gc ready`` and ``gc bd list/show`` queries
and returns only each candidate's ID, classification, and exact existing route.
READY is a prerequisite for scheduling, not permission to run backlog work.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from typing import Any

DEFAULT_MAX_ROWS = 50
COMMAND_TIMEOUT_SECONDS = 10
MAX_OUTPUT_BYTES = 1_000_000
MAX_JSON_DEPTH = 32
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
ROUTE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+$")
LIVE_ROOT_STATUSES = {"open", "in_progress"}
KNOWN_STATUSES = LIVE_ROOT_STATUSES | {"blocked", "deferred", "closed"}
RUN_CHAIN_KEYS = ("workflow_id", "molecule_id", "gc.root_bead_id")
INTENT_METADATA_KEYS = ("gc.routed_to", *RUN_CHAIN_KEYS)


class SelectorError(RuntimeError):
    """A query or payload cannot safely authorize dispatch."""


def valid_identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and IDENTIFIER_RE.fullmatch(value) else None


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SelectorError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def check_json_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise SelectorError("JSON exceeds maximum nesting depth")
    if isinstance(value, Mapping):
        for child in value.values():
            check_json_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            check_json_depth(child, depth + 1)


def command_json(*args: str) -> list[dict[str, Any]]:
    """Run one bounded public read-only gc query and validate its JSON."""
    command = ["gc", *args] if args and args[0] == "ready" else ["gc", "bd", *args]
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise SelectorError(f"could not run gc query safely: {exc}") from exc
    if (
        len(result.stdout.encode()) > MAX_OUTPUT_BYTES
        or len(result.stderr.encode()) > MAX_OUTPUT_BYTES
    ):
        raise SelectorError("gc query output exceeded selector bound")
    if result.returncode:
        raise SelectorError(f"{' '.join(command)} failed")
    try:
        payload = json.loads(
            result.stdout,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                SelectorError(f"invalid JSON constant {value}")
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SelectorError("gc query returned malformed JSON") from exc
    check_json_depth(payload)
    if isinstance(payload, dict):
        if not args or args[0] != "show":
            raise SelectorError("gc query returned an unexpected JSON schema")
        payload = [payload]
    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise SelectorError("gc query returned an unexpected JSON schema")
    return payload


def metadata(bead: Mapping[str, Any]) -> Mapping[str, Any]:
    value = bead.get("metadata", {})
    if not isinstance(value, Mapping):
        raise SelectorError("bead metadata is not an object")
    return value


def nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value or value.strip() != value:
        return None
    return value


def validate_bead(bead: Mapping[str, Any]) -> None:
    if valid_identifier(bead.get("id")) is None:
        raise SelectorError("bead has no valid id")
    if bead.get("status") not in KNOWN_STATUSES:
        raise SelectorError("bead has an invalid status")
    metadata(bead)
    for field in ("notes", "description"):
        value = bead.get(field)
        if value is not None and not isinstance(value, str):
            raise SelectorError(f"bead {field} is not text")


def bare_route_is_proven_local(
    bead: Mapping[str, Any], route: str, rig: str
) -> bool:
    bead_id = valid_identifier(bead.get("id"))
    assert bead_id is not None  # validate_bead ran first
    try:
        rows = command_json("show", "--rig", rig, bead_id, "--json")
    except SelectorError:
        return False
    if len(rows) != 1:
        return False
    local = rows[0]
    validate_bead(local)
    return (
        local.get("id") == bead_id
        and local.get("status") == bead.get("status")
        and metadata(local).get("gc.routed_to") == route
    )


def existing_route(bead: Mapping[str, Any], rig: str) -> str | None:
    bead_metadata = metadata(bead)
    if "gc.routed_to" not in bead_metadata:
        return None
    raw_route = bead_metadata["gc.routed_to"]
    if raw_route == "":
        return None
    route = nonempty_string(raw_route)
    if route is None:
        raise SelectorError("bead has an invalid gc.routed_to")
    if valid_identifier(route) is not None:
        return route if bare_route_is_proven_local(bead, route, rig) else None
    if route.startswith(f"{rig}/") and ROUTE_RE.fullmatch(route):
        return route
    raise SelectorError("bead has an invalid or foreign gc.routed_to")


def is_human_gated(bead: Mapping[str, Any], escalate_refs: set[str]) -> bool:
    bead_id = valid_identifier(bead.get("id"))
    assert bead_id is not None  # validate_bead ran first
    if bead_id in escalate_refs:
        return True
    tier = metadata(bead).get("gc.tier", "")
    if tier is not None and not isinstance(tier, str):
        raise SelectorError("gc.tier is not text")
    route = metadata(bead).get("gc.routed_to")
    if route == "human":
        return True
    text = " ".join(
        (bead.get("notes") or "", bead.get("description") or "", tier or "")
    ).lower()
    return "needs decision" in text or "needs-api" in text


def valid_live_formula_root(root: Mapping[str, Any], root_id: str, rig: str) -> bool:
    validate_bead(root)
    if root.get("id") != root_id or root.get("status") not in LIVE_ROOT_STATUSES:
        return False
    root_metadata = metadata(root)
    root_store = root_metadata.get("gc.root_store_ref")
    if root_store is not None and root_store != f"rig:{rig}":
        return False
    graph_workflow = (
        root_metadata.get("gc.kind") == "workflow"
        or root_metadata.get("gc.formula_contract") == "graph.v2"
    )
    legacy_formula = (
        root.get("issue_type") == "molecule" or root_metadata.get("gc.kind") == "wisp"
    )
    return graph_workflow or legacy_formula


def formula_root_id(bead: Mapping[str, Any], rig: str) -> str | None:
    """Resolve the documented run-chain fields without arbitrary-tree inference."""
    bead_metadata = metadata(bead)
    present = [key for key in RUN_CHAIN_KEYS if key in bead_metadata]
    if not present:
        return None
    values = [valid_identifier(bead_metadata[key]) for key in present]
    if any(value is None for value in values) or len(set(values)) != 1:
        raise SelectorError(
            "formula member has ambiguous or malformed run-chain metadata"
        )
    store = bead_metadata.get("gc.root_store_ref")
    if store is not None and store != f"rig:{rig}":
        raise SelectorError("formula member has a foreign root store")
    return values[0]


def has_live_formula_intent(bead: Mapping[str, Any], rig: str) -> bool:
    root_id = formula_root_id(bead, rig)
    if root_id is None:
        return False
    roots = command_json("show", "--rig", rig, root_id, "--json")
    if len(roots) != 1:
        raise SelectorError("root lookup did not return exactly one bead")
    return valid_live_formula_root(roots[0], root_id, rig)


def select(rig: str, max_rows: int) -> dict[str, Any]:
    """Return a safe candidate/anomaly envelope. Uncertainty raises ``SelectorError``."""
    if valid_identifier(rig) is None or max_rows < 1:
        raise SelectorError("invalid selector arguments")
    # ``ready`` delegates dependency and deferred/blocked handling to Beads.
    # Query only durable-intent metadata keys so unrelated backlog cannot exhaust
    # the safety bound. Each public query remains independently bounded; the
    # deduplicated union is bounded again before any scheduling decision.
    ready_by_id: dict[str, dict[str, Any]] = {}
    for intent_key in INTENT_METADATA_KEYS:
        rows = command_json(
            "ready",
            "--rig",
            rig,
            "--metadata-field",
            intent_key,
            "--json",
            "--limit",
            str(max_rows + 1),
        )
        if len(rows) > max_rows:
            raise SelectorError("public query exceeded selector row bound")
        query_ids: set[str] = set()
        for bead in rows:
            validate_bead(bead)
            bead_id = bead["id"]
            if bead_id in query_ids:
                raise SelectorError("ready query returned a duplicate bead id")
            query_ids.add(bead_id)
            prior = ready_by_id.get(bead_id)
            if prior is not None and prior != bead:
                raise SelectorError("ready queries returned conflicting bead data")
            ready_by_id[bead_id] = bead
    if len(ready_by_id) > max_rows:
        raise SelectorError("public query exceeded selector row bound")
    ready = list(ready_by_id.values())
    escalates = command_json(
        "list",
        "--rig",
        rig,
        "--label",
        "rollup",
        "--label",
        "severity:escalate",
        "--status",
        "open",
        "--json",
        "--limit",
        str(max_rows + 1),
    )
    if len(escalates) > max_rows:
        raise SelectorError("public query exceeded selector row bound")
    escalate_refs: set[str] = set()
    seen_rollup_ids: set[str] = set()
    for rollup in escalates:
        validate_bead(rollup)
        rollup_id = rollup["id"]
        if rollup_id in seen_rollup_ids:
            raise SelectorError("rollup query returned a duplicate bead id")
        seen_rollup_ids.add(rollup_id)
        labels = rollup.get("labels")
        if not isinstance(labels, list) or not all(
            isinstance(label, str) for label in labels
        ):
            raise SelectorError("rollup labels are not an array of strings")
        for label in labels:
            if label.startswith("ref:"):
                reference = valid_identifier(label[4:])
                if reference is None:
                    raise SelectorError("rollup has a malformed ref label")
                escalate_refs.add(reference)

    candidates: list[dict[str, str]] = []
    anomalies: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for bead in ready:
        validate_bead(bead)
        bead_id = bead["id"]
        if bead_id in seen_ids:
            raise SelectorError("ready query returned a duplicate bead id")
        seen_ids.add(bead_id)
        if bead.get("status") != "open" or is_human_gated(bead, escalate_refs):
            continue
        route = existing_route(bead, rig)
        formula_declared = any(key in metadata(bead) for key in RUN_CHAIN_KEYS)
        formula_member = has_live_formula_intent(bead, rig)
        if formula_declared and not formula_member:
            continue
        # A formula member without an existing route is controller-owned
        # anomalous state. Recognizing its root never authorizes choosing a
        # worker route, so it is deliberately not returned as a candidate.
        if route is None:
            if formula_member:
                anomalies.append(
                    {"id": bead_id, "reason": "live-formula-missing-route"}
                )
            continue
        candidates.append(
            {
                "id": bead_id,
                "classification": "formula-routed" if formula_member else "routed",
                "route": route,
            }
        )
    return {"schema_version": 1, "candidates": candidates, "anomalies": anomalies}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rig", required=True)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument("--json", action="store_true", help="required output format")
    args = parser.parse_args(argv)
    if not args.json:
        return 2
    try:
        print(json.dumps(select(args.rig, args.max_rows), sort_keys=True))
    except SelectorError as exc:
        print(f"execution candidate selection failed closed: {exc}", file=sys.stderr)
        print(
            json.dumps(
                {"schema_version": 1, "candidates": [], "anomalies": []}, sort_keys=True
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
