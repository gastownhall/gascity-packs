import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_order_scope_regression_runs_with_installed_gc() -> None:
    workflow = yaml.safe_load(
        REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]
    assert "check" in jobs, f"no job 'check' in CI; found: {sorted(jobs)}"
    steps = jobs["check"]["steps"]
    step_name = "Lint and exercise shared role prompt composition"
    matching = [step for step in steps if step.get("name") == step_name]
    assert matching, (
        f"no step named {step_name!r} in CI job 'check'; "
        f"found: {[step.get('name') for step in steps]}"
    )

    invocation = (
        'GC_TEST_BIN="$GC_BIN" python3 -m pytest '
        "oversight-rig/tests/test_order_scopes.py -q"
    )
    # Look at the step's *active* lines, not the raw block: a commented-out or
    # `|| true`-suffixed invocation still contains the substring while no
    # longer running, or no longer able to fail the job.
    active = [
        line.strip()
        for line in matching[0]["run"].splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    running = [line for line in active if line.startswith(invocation)]
    assert running, (
        f"{step_name!r} does not run the order-scope regression "
        f"(absent or commented out); active lines: {active}"
    )
    assert not any("||" in line for line in running), (
        "the order-scope regression is short-circuited, so a failure cannot "
        f"fail the job: {running}"
    )


def test_runtime_herdr_core_job_is_blocking_on_its_python_floor() -> None:
    workflow = yaml.safe_load(
        REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"].get("runtime-herdr-core")
    assert job is not None, f"no runtime-herdr-core job in CI; found: {sorted(workflow['jobs'])}"
    assert "continue-on-error" not in job, "the runtime-herdr-core job must block merges"
    targets = sorted(entry["target"] for entry in job["strategy"]["matrix"]["include"])
    assert targets == ["3.12", "3.9"], f"runtime-herdr-core must run on 3.9 and 3.12, got {targets}"
    runs = {step.get("name"): step for step in job["steps"]}
    for name, needle in [
        ("mypy --strict", "python -m mypy --config-file mypy.ini"),
        ("Unit tests", "python -m pytest tests/unit"),
    ]:
        assert name in runs, f"runtime-herdr-core lost its {name!r} step"
        assert needle in runs[name]["run"], f"{name!r} no longer runs {needle!r}"
        assert "continue-on-error" not in runs[name], f"{name!r} must block merges"

    check = {step.get("name"): step for step in workflow["jobs"]["check"]["steps"]}
    shared = check["Run Python pack tests"]["run"].split()
    assert "runtime-herdr-core/tests/unit" in shared, "the shared pytest step must run runtime-herdr-core"


def test_runtime_herdr_core_has_a_merge_blocking_aggregator() -> None:
    # A ruleset can require one stable check name; matrix legs are named per
    # Python version. The aggregator must run even when a leg fails or is
    # cancelled (a skipped required check can count as passing), and fail
    # unless every leg succeeded.
    workflow = yaml.safe_load(
        REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]
    aggregators = [
        (job_id, job)
        for job_id, job in jobs.items()
        if "runtime-herdr-core" in (job.get("needs") or [])
    ]
    assert len(aggregators) == 1, f"want one job that needs runtime-herdr-core, found {[a for a, _ in aggregators]}"
    job_id, job = aggregators[0]
    assert job.get("name") == "runtime-herdr-core", "the ruleset requires the check by this name"
    assert str(job.get("if", "")).replace("${{", "").replace("}}", "").strip() == "always()"
    assert "continue-on-error" not in job
    checks = " ".join(step.get("run", "") for step in job["steps"])
    assert "needs.runtime-herdr-core.result" in json.dumps(job) and "success" in checks
    for name in ("runtime-herdr-core", job_id):
        assert isinstance(jobs[name].get("timeout-minutes"), int), f"{name} needs timeout-minutes"
    check_needs = jobs["check"].get("needs") or []
    assert "runtime-herdr-core" not in check_needs and job_id not in check_needs, "never gate through Check"


def test_runtime_herdr_core_is_in_the_lint_loop() -> None:
    workflow = yaml.safe_load(
        REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")
    )
    steps = {step.get("name"): step for step in workflow["jobs"]["check"]["steps"]}
    loop = steps["Lint and exercise shared role prompt composition"]["run"]
    packs = loop.split("for pack in", 1)[1].split("; do", 1)[0].replace("\\", " ").split()
    assert "runtime-herdr-core" in packs, f"gc lint loop: {packs}"

