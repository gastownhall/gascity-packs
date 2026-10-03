#!/usr/bin/env python3
"""Produce bounded Gstack Lite delivery and operational-health snapshots."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence


SCHEMA_VERSION = "gc.delivery/v1"
METRICS_KEY = "gc.delivery.metrics"
PRODUCT_TYPES = frozenset({"bug", "feature", "task", "chore"})
DURATION_FIELDS = (
    "queue",
    "implementation",
    "checks_ci",
    "review_repair",
    "deploy_canary",
    "total_wall",
)
REQUIRED_FIELDS = (
    "schema_version",
    "authorized_at",
    "started_at",
    "durations_seconds.queue",
    "durations_seconds.implementation",
    "durations_seconds.checks_ci",
    "durations_seconds.review_repair",
    "durations_seconds.deploy_canary",
    "durations_seconds.total_wall",
    "retries",
    "repairs",
    "human_interventions",
    "model_lanes",
    "source_head",
    "terminal_revision",
    "outcome",
)


def _run_json(command: Sequence[str]) -> Any:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return json.loads(completed.stdout)


def _read_json(path: Path | None, command: Sequence[str]) -> Any:
    if path is None:
        return _run_json(command)
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _metrics(bead: dict[str, Any]) -> dict[str, Any] | None:
    value = bead.get("metadata", {}).get(METRICS_KEY)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _is_delivery(bead: dict[str, Any]) -> bool:
    """Select explicitly instrumented, durable, terminal product work only."""
    if bead.get("ephemeral") or bead.get("wisp_type"):
        return False
    if bead.get("issue_type") not in PRODUCT_TYPES:
        return False
    if bead.get("status") != "closed" or not bead.get("closed_at"):
        return False
    return METRICS_KEY in bead.get("metadata", {})


def _get_path(value: dict[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def delivery_snapshot(beads: Sequence[dict[str, Any]]) -> dict[str, Any]:
    candidates = [bead for bead in beads if _is_delivery(bead)]
    field_present = Counter({field: 0 for field in REQUIRED_FIELDS})
    durations = Counter({field: 0.0 for field in DURATION_FIELDS})
    outcomes: Counter[str] = Counter()
    lanes: Counter[str] = Counter()
    repository_lanes: Counter[str] = Counter()
    canary_outcomes: Counter[str] = Counter()
    totals = Counter(
        retries=0,
        repairs=0,
        human_interventions=0,
        review_rounds=0,
        deployment_attempts=0,
        deployment_failures=0,
        rollbacks=0,
    )
    complete_records = 0

    for bead in candidates:
        metrics = _metrics(bead)
        if metrics is None:
            continue
        record_complete = True
        for field in REQUIRED_FIELDS:
            present = _get_path(metrics, field) is not None
            field_present[field] += int(present)
            record_complete = record_complete and present
        complete_records += int(record_complete)

        for field in DURATION_FIELDS:
            value = _get_path(metrics, f"durations_seconds.{field}")
            if _valid_number(value):
                durations[field] += float(value)
        for field in ("retries", "repairs", "human_interventions"):
            value = metrics.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                totals[field] += value
        if isinstance(metrics.get("outcome"), str):
            outcomes[metrics["outcome"]] += 1
        if isinstance(metrics.get("model_lanes"), list):
            lanes.update(lane for lane in metrics["model_lanes"] if isinstance(lane, str))
        if isinstance(metrics.get("repository_lane"), str):
            repository_lanes[metrics["repository_lane"]] += 1
        if isinstance(metrics.get("canary_outcome"), str):
            canary_outcomes[metrics["canary_outcome"]] += 1
        for field in ("review_rounds", "deployment_attempts", "deployment_failures"):
            value = metrics.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                totals[field] += value
        if metrics.get("rollback") is True:
            totals["rollbacks"] += 1

    count = len(candidates)
    coverage = {
        "records_complete": complete_records,
        "records_total": count,
        "records_complete_percent": round(100 * complete_records / count, 2) if count else 0.0,
        "fields": {
            field: {
                "present": field_present[field],
                "total": count,
                "percent": round(100 * field_present[field] / count, 2) if count else 0.0,
            }
            for field in REQUIRED_FIELDS
        },
    }
    duration_rollup = {
        field: {
            "total": round(durations[field], 3),
            "mean": round(durations[field] / count, 3) if count else 0.0,
        }
        for field in DURATION_FIELDS
    }
    return {
        "schema_version": "gc.delivery.snapshot/v1",
        "selection": {
            "explicit_metrics_key": METRICS_KEY,
            "product_issue_types": sorted(PRODUCT_TYPES),
            "terminal_status": "closed",
            "ephemeral_excluded": True,
        },
        "deliveries": count,
        "coverage": coverage,
        "durations_seconds": duration_rollup,
        "retries": totals["retries"],
        "repairs": totals["repairs"],
        "human_interventions": totals["human_interventions"],
        "outcomes": dict(sorted(outcomes.items())),
        "model_lanes": dict(sorted(lanes.items())),
        "repository_lanes": dict(sorted(repository_lanes.items())),
        "review_rounds": totals["review_rounds"],
        "deployment_attempts": totals["deployment_attempts"],
        "deployment_failures": totals["deployment_failures"],
        "rollbacks": totals["rollbacks"],
        "canary_outcomes": dict(sorted(canary_outcomes.items())),
    }


def health_snapshot(doctor: dict[str, Any]) -> dict[str, Any]:
    warnings = [
        {
            key: result[key]
            for key in ("name", "status", "severity", "message", "fix_hint")
            if key in result
        }
        for result in doctor.get("results", [])
        if result.get("status") != "ok"
    ]
    blocking_failed = int(doctor.get("blocking_failed", 0))
    return {
        "schema_version": "gc.health.snapshot/v1",
        "ok": bool(doctor.get("ok", False)),
        "launch_blocked": blocking_failed > 0,
        "counts": {
            key: int(doctor.get(key, 0))
            for key in ("passed", "warned", "failed", "blocking_failed", "fixed")
        },
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    delivery = subparsers.add_parser("delivery", help="summarize durable product deliveries")
    delivery.add_argument("--beads-json", type=Path, help="fixture/export; defaults to gc bd list")
    health = subparsers.add_parser("health", help="summarize gc doctor operational health")
    health.add_argument("--doctor-json", type=Path, help="fixture/export; defaults to gc doctor")
    snapshot = subparsers.add_parser("snapshot", help="emit separate delivery and health snapshots")
    snapshot.add_argument("--beads-json", type=Path)
    snapshot.add_argument("--doctor-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result: dict[str, Any]
        if args.command == "delivery":
            beads = _read_json(args.beads_json, ("gc", "bd", "list", "--all", "--json", "--limit", "0"))
            result = delivery_snapshot(beads)
        elif args.command == "health":
            doctor = _read_json(args.doctor_json, ("gc", "doctor", "--json"))
            result = health_snapshot(doctor)
        else:
            beads = _read_json(args.beads_json, ("gc", "bd", "list", "--all", "--json", "--limit", "0"))
            doctor = _read_json(args.doctor_json, ("gc", "doctor", "--json"))
            result = {
                "delivery": delivery_snapshot(beads),
                "health": health_snapshot(doctor),
            }
    except (OSError, ValueError, RuntimeError) as error:
        print(f"delivery_snapshot: {error}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
