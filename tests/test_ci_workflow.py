import json
import os
import subprocess
import sys
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


def test_runtime_herdr_core_runs_gc_conformance_against_a_pinned_gc() -> None:
    workflow = yaml.safe_load(
        REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")
    )
    steps = {step.get("name"): step for step in workflow["jobs"]["runtime-herdr-core"]["steps"]}
    step = steps.get("RPP conformance against fake-hc")
    assert step is not None, f"runtime-herdr-core lost its conformance step; steps: {sorted(steps)}"
    assert "continue-on-error" not in step, "conformance must block merges"
    pin = step.get("env", {}).get("GASCITY_PIN", "")
    assert len(pin) == 40 and all(c in "0123456789abcdef" for c in pin), "gc is pinned to a full commit SHA"
    active = [
        line.strip()
        for line in step["run"].splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert 'go install "github.com/gastownhall/gascity/cmd/gc@${GASCITY_PIN}"' in active
    runs = [line for line in active if line.startswith("tests/conformance.sh")]
    assert runs == ["tests/conformance.sh --json", "tests/conformance.sh --json --default-root"], runs
    assert not any("||" in line for line in active), "a conformance failure must fail the job"


def test_runtime_herdr_core_runs_gcs_unwelded_launch_contract_at_the_conformance_pin() -> None:
    workflow = yaml.safe_load(
        REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")
    )
    steps = {step.get("name"): step for step in workflow["jobs"]["runtime-herdr-core"]["steps"]}
    step = steps.get("gc un-welded launch contract against fake-hc")
    assert step is not None, f"runtime-herdr-core lost its contract step; steps: {sorted(steps)}"
    assert "continue-on-error" not in step, "the contract must block merges"
    conformance = steps["RPP conformance against fake-hc"]
    assert step["env"]["GASCITY_PIN"] == conformance["env"]["GASCITY_PIN"], "contract and conformance use one gc pin"
    active = [line.strip() for line in step["run"].splitlines() if line.strip() and not line.strip().startswith("#")]
    assert active == ["PYTHON=python tests/gccontract/run.sh"], active
    assert REPO_ROOT.joinpath("runtime-herdr-core", "tests", "gccontract", "unwelded_test.go.in").is_file()


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



def test_runtime_herdr_core_guards_infrastructure_argv_drift_at_the_conformance_pin() -> None:
    workflow = yaml.safe_load(
        REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")
    )
    steps = {step.get("name"): step for step in workflow["jobs"]["runtime-herdr-core"]["steps"]}
    step = steps.get("Infrastructure argv matches the pinned gc")
    assert step is not None, f"runtime-herdr-core lost its drift guard; steps: {sorted(steps)}"
    assert "continue-on-error" not in step and "if" not in step, "the drift guard must block merges on every leg"
    conformance = steps["RPP conformance against fake-hc"]
    assert step["env"]["GASCITY_PIN"] == conformance["env"]["GASCITY_PIN"], "guard and conformance use one gc pin"
    active = [
        line.strip()
        for line in step["run"].splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert any('github.com/gastownhall/gascity@${GASCITY_PIN}' in line for line in active)
    assert any(
        line.startswith("python tests/infra_argv_drift.py ")
        and line.endswith('/internal/runtime/proctable/infrastructure_argv.go"')
        for line in active
    ), active
    assert not any("||" in line for line in active), "drift must fail the job"


def test_runtime_herdr_core_runs_its_op_import_guard_on_the_newest_python() -> None:
    # What an op imports can change with the interpreter (CPython 3.14's
    # typing.NamedTuple imports ast), and the matrix legs run 3.9 and 3.12.
    workflow = yaml.safe_load(
        REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["runtime-herdr-core"]["steps"]
    names = [step.get("name") for step in steps]
    setup = "Set up the newest Python"
    guard = "Op import guard on the newest Python"
    assert setup in names and guard in names, f"runtime-herdr-core lost its newest-Python guard; steps: {names}"
    assert names.index(setup) + 2 == names.index(guard) == len(names) - 1, (
        "the newest Python is set up last, so every other step keeps the leg's own Python"
    )
    newest = steps[names.index(setup)]["with"]["python-version"]
    assert newest.startswith("3.14."), newest
    for name in (setup, guard):
        step = steps[names.index(name)]
        assert step.get("if") == "matrix.target == '3.12'", f"{name!r} runs once, on the 3.12 leg"
        assert "continue-on-error" not in step, f"{name!r} must block merges"
    # The whole command, so "|| true" or a "-k" filter cannot switch it off.
    assert steps[-1]["run"].strip() == "python -m pytest tests/unit/test_op_imports.py -q", steps[-1]["run"]


# --- runtime-herdr-core live tier -------------------------------------------------

LIVE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "runtime-herdr-core-live.yml"
LIVE_DIR = REPO_ROOT / "runtime-herdr-core" / "tests" / "live"


def _live() -> dict:
    return yaml.safe_load(LIVE_WORKFLOW.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True.
    return workflow.get("on", workflow.get(True))


def _active(run: str) -> list:
    return [line.strip() for line in run.splitlines() if line.strip() and not line.strip().startswith("#")]


def _live_steps() -> dict:
    return {step.get("name"): step for step in _live()["jobs"]["live"]["steps"]}


def test_live_tier_runs_nightly_on_demand_and_only_on_its_own_pull_requests() -> None:
    triggers = _triggers(_live())
    assert set(triggers) == {"schedule", "workflow_dispatch", "pull_request"}, sorted(triggers)
    assert triggers["schedule"] and all("cron" in entry for entry in triggers["schedule"])
    assert sorted(triggers["pull_request"]["paths"]) == [
        ".github/workflows/runtime-herdr-core-live.yml",
        "runtime-herdr-core/tests/live/**",
    ]
    assert "paths-ignore" not in triggers["pull_request"]


def test_live_tier_permissions_are_read_only_and_it_uses_no_secrets() -> None:
    workflow = _live()
    assert workflow["permissions"] == {"contents": "read"}
    for job_id, job in workflow["jobs"].items():
        assert "permissions" not in job, f"{job_id} widens the token's permissions"
    text = LIVE_WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text and "pull_request_target" not in text
    assert "GITHUB_TOKEN" not in text
    checkout = _live_steps()["Check out repository"]
    assert checkout["with"]["persist-credentials"] is False


def test_live_tier_pins_every_action_and_gc() -> None:
    workflow = _live()
    for step in workflow["jobs"]["live"]["steps"]:
        uses = step.get("uses")
        if uses:
            ref = uses.split("@", 1)[1]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), f"{uses} is not pinned to a commit"
    pin = workflow["jobs"]["live"]["env"]["GASCITY_PIN"]
    ci = yaml.safe_load(REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8"))
    conformance = {s.get("name"): s for s in ci["jobs"]["runtime-herdr-core"]["steps"]}["RPP conformance against fake-hc"]
    assert pin == conformance["env"]["GASCITY_PIN"], "the live tier and the fake-hc conformance use one gc pin"
    build = _active(_live_steps()["Build gc at the pinned gascity commit"]["run"])
    assert 'go install "github.com/gastownhall/gascity/cmd/gc@${GASCITY_PIN}"' in build


def test_live_tier_fetches_hc_only_through_the_pinned_sha256() -> None:
    pin = json.loads(REPO_ROOT.joinpath("runtime-herdr-core", "assets", "hc-pin.json").read_text(encoding="utf-8"))
    sha = pin["targets"]["linux-x86_64"]["sha256"]
    assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)
    steps = _live_steps()
    fetch = _active(steps["Fetch the pinned herdr-core"]["run"])
    assert fetch[0] == 'hc="$(python tests/live/fetch_hc.py "$RUNNER_TEMP/herdr-core")"', fetch
    text = LIVE_WORKFLOW.read_text(encoding="utf-8")
    for needle in ("curl", "wget", pin["releases"], "sha256sum"):
        assert needle not in text, f"the live tier must fetch hc only through fetch_hc.py (found {needle!r})"


def test_live_tier_runs_both_lanes_and_fails_loudly() -> None:
    job = _live()["jobs"]["live"]
    assert job["strategy"]["matrix"]["lane"] == ["plain", "systemd"]
    assert job["strategy"]["fail-fast"] is False
    assert job["env"]["GC_HC_LIVE"] == "1" and job["env"]["GC_HC_LIVE_LANE"] == "${{ matrix.lane }}"
    assert isinstance(job.get("timeout-minutes"), int)
    assert job["runs-on"] == "ubuntu-24.04"
    text = LIVE_WORKFLOW.read_text(encoding="utf-8")
    assert "continue-on-error" not in text, "a live failure must show as a failure"
    steps = _live_steps()
    manager = steps["Start a systemd user manager"]
    assert manager["if"] == "matrix.lane == 'systemd'"
    lines = _active(manager["run"])
    # A failing enable-linger must reach the summary-and-exit branch, not end
    # the step under bash -e before the job summary says why.
    linger = [line for line in lines if "loginctl" in line]
    assert linger == ['if ! sudo loginctl enable-linger "$USER"; then'], linger
    assert 'state="enable-linger failed"' in lines
    assert "GITHUB_STEP_SUMMARY" in manager["run"] and "exit 1" in lines
    suites = _active(steps["Live suites"]["run"])
    assert suites == ["python -m pytest tests/live -v -rs -p no:cacheprovider"], suites


def test_live_tier_runs_never_cancel_each_other_across_triggers() -> None:
    concurrency = _live()["concurrency"]
    assert "github.event_name" in concurrency["group"], "a dispatch must not cancel a nightly run, nor the reverse"
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"


def test_live_tier_is_not_part_of_the_blocking_ci() -> None:
    ci = yaml.safe_load(REPO_ROOT.joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8"))
    for job in ci["jobs"].values():
        for step in job["steps"]:
            assert "tests/live" not in step.get("run", ""), "the live tier runs only in its own workflow"


def _refusal_env(tmp_path: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in {"GITHUB_ACTIONS", "GC_HC_LIVE_THROWAWAY_HOST"}}
    env["HOME"] = str(tmp_path)
    return env


def test_live_tier_refuses_outside_ci(tmp_path: Path) -> None:
    env = _refusal_env(tmp_path)
    fetched = subprocess.run(
        [sys.executable, str(LIVE_DIR / "fetch_hc.py"), str(tmp_path / "hc")],
        env=env, capture_output=True, text=True, timeout=60, check=False,
    )
    assert fetched.returncode == 2 and "refuses to run" in fetched.stderr, fetched.stderr
    assert not (tmp_path / "hc").exists()
    env["GC_HC_LIVE"] = "1"
    suites = subprocess.run(
        [sys.executable, "-m", "pytest", str(LIVE_DIR), "-q", "-p", "no:cacheprovider"],
        cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    assert suites.returncode == 2, suites.stdout + suites.stderr
    assert "refuses to run" in suites.stdout + suites.stderr
