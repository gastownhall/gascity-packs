from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "gstack/skills/gstack-lite/scripts/delivery_snapshot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("delivery_snapshot", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metrics(**overrides):
    value = {
        "schema_version": "gc.delivery/v1",
        "authorized_at": "2026-08-05T10:00:00Z",
        "started_at": "2026-08-05T10:01:00Z",
        "durations_seconds": {
            "queue": 60,
            "implementation": 120,
            "checks_ci": 30,
            "review_repair": 40,
            "deploy_canary": 50,
            "total_wall": 300,
        },
        "retries": 1,
        "repairs": 2,
        "human_interventions": 0,
        "model_lanes": ["sol-fast", "claude-review"],
        "source_head": "1234567",
        "terminal_revision": "7654321",
        "outcome": "shipped",
    }
    value.update(overrides)
    return value


def bead(bead_id, issue_type="feature", ephemeral=False, value=None):
    return {
        "id": bead_id,
        "issue_type": issue_type,
        "status": "closed",
        "closed_at": "2026-08-05T10:05:00Z",
        "ephemeral": ephemeral,
        "metadata": {"gc.delivery.metrics": metrics() if value is None else value},
    }


def test_excludes_ephemeral_and_control_plane_churn() -> None:
    module = load_module()
    result = module.delivery_snapshot(
        [bead("product"), bead("wisp", ephemeral=True), bead("message", issue_type="message")]
    )

    assert result["deliveries"] == 1
    assert result["outcomes"] == {"shipped": 1}


def test_missing_fields_are_reported_as_coverage_not_errors() -> None:
    module = load_module()
    incomplete = metrics()
    incomplete.pop("terminal_revision")
    result = module.delivery_snapshot([bead("complete"), bead("incomplete", value=incomplete)])

    assert result["coverage"]["records_total"] == 2
    assert result["coverage"]["records_complete"] == 1
    assert result["coverage"]["records_complete_percent"] == 50.0
    assert result["coverage"]["fields"]["terminal_revision"] == {
        "present": 1,
        "total": 2,
        "percent": 50.0,
    }


def test_rollup_math_is_deterministic() -> None:
    module = load_module()
    second = metrics(
        durations_seconds={
            "queue": 20,
            "implementation": 80,
            "checks_ci": 10,
            "review_repair": 20,
            "deploy_canary": 20,
            "total_wall": 150,
        },
        retries=0,
        repairs=1,
        human_interventions=1,
        model_lanes=["sol-fast"],
        outcome="failed",
    )
    result = module.delivery_snapshot([bead("one"), bead("two", value=second)])

    assert result["durations_seconds"]["total_wall"] == {"total": 450.0, "mean": 225.0}
    assert result["durations_seconds"]["queue"] == {"total": 80.0, "mean": 40.0}
    assert result["retries"] == 1
    assert result["repairs"] == 3
    assert result["human_interventions"] == 1
    assert result["model_lanes"] == {"claude-review": 1, "sol-fast": 2}
    assert result["outcomes"] == {"failed": 1, "shipped": 1}


def test_rolls_up_repository_defined_risk_and_deployment_fields() -> None:
    module = load_module()
    first = metrics(
        repository_lane="fixture-only",
        risk_reasons=["no production target"],
        review_rounds=1,
        deployment_attempts=1,
        deployment_failures=0,
        rollback=False,
        canary_outcome="passed",
    )
    second = metrics(
        repository_lane="external-api",
        risk_reasons=["third-party contract"],
        review_rounds=2,
        deployment_attempts=2,
        deployment_failures=1,
        rollback=True,
        canary_outcome="failed",
    )

    result = module.delivery_snapshot([bead("one", value=first), bead("two", value=second)])

    assert result["repository_lanes"] == {"external-api": 1, "fixture-only": 1}
    assert result["review_rounds"] == 3
    assert result["deployment_attempts"] == 3
    assert result["deployment_failures"] == 1
    assert result["rollbacks"] == 1
    assert result["canary_outcomes"] == {"failed": 1, "passed": 1}


def test_health_snapshot_keeps_warnings_separate_from_launch_blocking() -> None:
    module = load_module()
    result = module.health_snapshot(
        {
            "ok": True,
            "passed": 2,
            "warned": 1,
            "failed": 0,
            "blocking_failed": 0,
            "fixed": 0,
            "results": [
                {"name": "binary", "status": "ok", "severity": "blocking", "message": "ok"},
                {
                    "name": "provider",
                    "status": "warning",
                    "severity": "advisory",
                    "message": "not explicit",
                },
            ],
        }
    )

    assert result["launch_blocked"] is False
    assert result["warnings"] == [
        {
            "name": "provider",
            "status": "warning",
            "severity": "advisory",
            "message": "not explicit",
        }
    ]
