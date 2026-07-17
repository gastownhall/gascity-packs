from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from scripts import gascity_pack_inference_gate


SUPPORTED_PACK_NIGHTLY_WORKFLOW = (
    gascity_pack_inference_gate.REPO_ROOT / ".github" / "workflows" / "supported-pack-nightly.yml"
)


def supported_pack_nightly_document() -> dict:
    document = yaml.safe_load(SUPPORTED_PACK_NIGHTLY_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def supported_pack_nightly_step_script(name: str) -> str:
    for job in supported_pack_nightly_document()["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == name:
                script = step.get("run")
                assert isinstance(script, str), f"workflow step {name!r} does not have a run script"
                return script
    raise AssertionError(f"workflow step {name!r} was not found")


def run_workflow_script(script: str, tmp_path: Path, **env_overrides: str) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    github_output = tmp_path / "github-output"
    github_output.unlink(missing_ok=True)
    env = os.environ.copy()
    env.update(env_overrides)
    env["GITHUB_OUTPUT"] = str(github_output)
    result = subprocess.run(
        ["bash", "-e", "-u", "-o", "pipefail", "-c", script],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    outputs: dict[str, str] = {}
    if github_output.is_file():
        for line in github_output.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            assert separator, f"invalid GITHUB_OUTPUT line: {line!r}"
            outputs[key] = value
    return result, outputs


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def create_ref_resolution_remote(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(source)], check=True)
    run_git(source, "config", "user.name", "Nightly Test")
    run_git(source, "config", "user.email", "nightly@example.invalid")

    fixture = source / "fixture.txt"
    fixture.write_text("one\n", encoding="utf-8")
    run_git(source, "add", "fixture.txt")
    run_git(source, "commit", "-q", "-m", "first")
    first = run_git(source, "rev-parse", "HEAD")
    run_git(source, "tag", "v1.2.0")
    run_git(source, "branch", "feature/ref-resolution", first)

    fixture.write_text("two\n", encoding="utf-8")
    run_git(source, "commit", "-q", "-am", "second")
    unadvertised = run_git(source, "rev-parse", "HEAD")

    fixture.write_text("three\n", encoding="utf-8")
    run_git(source, "commit", "-q", "-am", "stable")
    v2_stable = run_git(source, "rev-parse", "HEAD")
    run_git(source, "tag", "-a", "v2.0.0", "-m", "stable v2")

    fixture.write_text("four\n", encoding="utf-8")
    run_git(source, "commit", "-q", "-am", "stable without tag prefix")
    stable = run_git(source, "rev-parse", "HEAD")
    run_git(source, "tag", "2.1.0")

    fixture.write_text("release candidate\n", encoding="utf-8")
    run_git(source, "commit", "-q", "-am", "release candidate")
    main = run_git(source, "rev-parse", "HEAD")
    run_git(source, "tag", "v3.0.0-rc.1")

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(source), str(remote)], check=True)
    return remote, {
        "first": first,
        "unadvertised": unadvertised,
        "v2_stable": v2_stable,
        "stable": stable,
        "main": main,
    }


def gate_workspace(root: Path) -> gascity_pack_inference_gate.GateWorkspace:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=root,
        city_dir=root / "city",
        rig_dir=root / "fixture",
        gc_home=root / "gc-home",
        runtime_dir=root / "runtime",
        claude_config_dir=root / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    workspace.city_dir.mkdir()
    workspace.rig_dir.mkdir()
    return workspace


def closed_bead(
    bead_id: str,
    *,
    root: str = "",
    kind: str = "",
    outcome: str = "pass",
    metadata: dict | None = None,
) -> dict:
    values = dict(metadata or {})
    values.update({key: value for key, value in (("gc.root_bead_id", root), ("gc.kind", kind)) if value})
    values["gc.outcome"] = outcome
    return {"id": bead_id, "status": "closed", "metadata": values}


def lineage_drain(bead_id: str, root_id: str, nested_id: str, *, root_key: str = "item_root_id") -> dict:
    manifest = {
        "version": 1,
        "rows": [
            {
                "member_id": f"{nested_id}-member",
                root_key: nested_id,
                "status": "succeeded",
                "outcome_kind": "pass",
            }
        ],
    }
    return closed_bead(
        bead_id,
        root=root_id,
        kind="drain",
        metadata={
            "gc.drain_count": "1",
            "gc.drain_state": "succeeded",
            "gc.drain_manifest.v1": json.dumps(manifest),
        },
    )


def test_write_gate_workspace_observes_isolated_claude_projects(tmp_path) -> None:
    pack_source = tmp_path / "repo" / "gascity"
    roles_source = pack_source / "roles"
    pack_source.mkdir(parents=True)
    roles_source.mkdir()

    workspace = gascity_pack_inference_gate.write_gate_workspace(
        tmp_path / "gate",
        pack_source=pack_source,
        roles_source=roles_source,
        city_name="inference-city",
        rig_name="fixture",
    )

    city_config = tomllib.loads(
        (workspace.city_dir / "city.toml").read_text(encoding="utf-8")
    )

    assert city_config["daemon"]["observe_paths"] == [
        str(workspace.claude_config_dir / "projects")
    ]


def test_write_gate_workspace_uses_city_and_rig_scope_imports(tmp_path) -> None:
    pack_source = tmp_path / "repo" / "gascity"
    roles_source = pack_source / "roles"
    pack_source.mkdir(parents=True)
    roles_source.mkdir()

    workspace = gascity_pack_inference_gate.write_gate_workspace(
        tmp_path / "gate",
        pack_source=pack_source,
        roles_source=roles_source,
        city_name="inference-city",
        rig_name="fixture",
    )

    city_toml = (workspace.city_dir / "city.toml").read_text(encoding="utf-8")
    pack_toml = (workspace.city_dir / "pack.toml").read_text(encoding="utf-8")
    site_toml = (workspace.city_dir / ".gc" / "site.toml").read_text(encoding="utf-8")

    assert '[workspace]\nprovider = "claude"\n' in city_toml
    assert "includes =" not in city_toml
    assert "[workspace.env]" in city_toml
    assert f"HOME = \"{workspace.gc_home}\"" in city_toml
    assert 'PYTHONDONTWRITEBYTECODE = "1"' in city_toml
    assert '[providers.claude]\nbase = "builtin:claude"\n' in city_toml
    assert "args_append" not in city_toml
    assert "accept_startup_dialogs" not in city_toml
    assert "[beads]" not in city_toml
    assert 'provider = "file"' not in city_toml
    assert "[session]\n" in city_toml
    assert "provider = \"tmux\"" not in city_toml
    assert "socket =" not in city_toml
    assert 'startup_timeout = "3m"' in city_toml
    assert 'progress_stall_timeout = "10m"' in city_toml
    assert "[[rigs]]" in city_toml
    assert 'name = "fixture"' in city_toml
    assert "[rigs.imports.gc]" in city_toml
    assert f'source = "{roles_source}"' in city_toml
    assert 'workspace_name = "inference-city"' in site_toml
    assert "[[rig]]" in site_toml
    assert 'name = "fixture"' in site_toml
    assert f'path = "{workspace.rig_dir}"' in site_toml

    assert '[pack]\nname = "gascity-pack-inference-gate"\nschema = 2\n' in pack_toml
    assert "[imports.core]" in pack_toml
    assert "[imports.maintenance]" not in pack_toml
    assert "[imports.bd]" in pack_toml
    assert "[imports.gc]" in pack_toml
    assert f'source = "{pack_source}"' in pack_toml

    assert not (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_SUBJECT_PATH).exists()
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir)
    subject = subject_path.read_text(encoding="utf-8")
    assert "shell=True" in subject
    assert "destination" in subject

    slugger = (workspace.rig_dir / "slugger.py").read_text(encoding="utf-8")
    slugger_test = (workspace.rig_dir / "tests" / "test_slugger.py").read_text(encoding="utf-8")
    assert "NotImplementedError" in slugger
    assert "slugify" in slugger_test
    assert "Hello, World!" in slugger_test


def test_write_gate_workspace_materializes_pack_check_scripts(tmp_path) -> None:
    pack_source = tmp_path / "repo" / "gascity"
    roles_source = pack_source / "roles"
    checks_source = pack_source / "assets" / "scripts" / "checks"
    schemas_source = pack_source / "schemas" / "build"
    checks_source.mkdir(parents=True)
    schemas_source.mkdir(parents=True)
    roles_source.mkdir()

    check_script = checks_source / "build-artifact-valid.sh"
    check_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    check_script.chmod(0o755)
    validator = pack_source / "assets" / "scripts" / "validate_build_artifact.py"
    validator.write_text("print('ok')\n", encoding="utf-8")
    provenance_verifier = (
        pack_source / "assets" / "scripts" / "verify_implementation_provenance.py"
    )
    provenance_verifier.write_text("print('verified')\n", encoding="utf-8")
    schema = schemas_source / "requirements.v1.yaml"
    schema.write_text("schema_id: gc.build.requirements.v1\n", encoding="utf-8")

    workspace = gascity_pack_inference_gate.write_gate_workspace(
        tmp_path / "gate",
        pack_source=pack_source,
        roles_source=roles_source,
        city_name="inference-city",
        rig_name="fixture",
    )

    materialized_check = workspace.rig_dir / ".gc" / "scripts" / "checks" / "build-artifact-valid.sh"
    materialized_validator = workspace.rig_dir / ".gc" / "scripts" / "validate_build_artifact.py"
    materialized_provenance_verifier = (
        workspace.rig_dir / ".gc" / "scripts" / "verify_implementation_provenance.py"
    )
    materialized_schema = workspace.rig_dir / "schemas" / "build" / "requirements.v1.yaml"

    assert materialized_check.read_text(encoding="utf-8") == "#!/usr/bin/env bash\nexit 0\n"
    assert os.access(materialized_check, os.X_OK)
    assert materialized_validator.read_text(encoding="utf-8") == "print('ok')\n"
    assert materialized_provenance_verifier.read_text(encoding="utf-8") == "print('verified')\n"
    assert materialized_schema.read_text(encoding="utf-8") == "schema_id: gc.build.requirements.v1\n"


def test_materialize_pack_check_scripts_rejects_missing_runtime_helper(tmp_path) -> None:
    pack_source = tmp_path / "gascity"
    checks_source = pack_source / "assets" / "scripts" / "checks"
    checks_source.mkdir(parents=True)
    (checks_source / "build-artifact-valid.sh").write_text(
        "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
    )
    (pack_source / "assets" / "scripts" / "validate_build_artifact.py").write_text(
        "print('ok')\n", encoding="utf-8"
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="verify_implementation_provenance.py",
    ):
        gascity_pack_inference_gate.materialize_pack_check_scripts(
            pack_source,
            tmp_path / "fixture",
        )


def test_write_gate_workspace_imports_selected_pack_and_shared_validator(tmp_path) -> None:
    pack_source = tmp_path / "repo" / "superpowers"
    roles_source = tmp_path / "repo" / "gascity" / "roles"
    validator_source = tmp_path / "repo" / "gascity"
    checks_source = validator_source / "assets" / "scripts" / "checks"
    checks_source.mkdir(parents=True)
    roles_source.mkdir(parents=True)
    pack_source.mkdir(parents=True)

    check_script = checks_source / "build-artifact-valid.sh"
    check_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    validator = validator_source / "assets" / "scripts" / "validate_build_artifact.py"
    validator.write_text("print('shared-validator')\n", encoding="utf-8")
    provenance_verifier = (
        validator_source / "assets" / "scripts" / "verify_implementation_provenance.py"
    )
    provenance_verifier.write_text("print('shared-verifier')\n", encoding="utf-8")

    workspace = gascity_pack_inference_gate.write_gate_workspace(
        tmp_path / "gate",
        pack_source=pack_source,
        roles_source=roles_source,
        validator_source=validator_source,
        pack_binding="superpowers",
        pack_name="superpowers",
        city_name="superpowers-inference-city",
        rig_name="fixture",
    )

    city_toml = (workspace.city_dir / "city.toml").read_text(encoding="utf-8")
    pack_toml = (workspace.city_dir / "pack.toml").read_text(encoding="utf-8")

    assert '[pack]\nname = "superpowers-pack-inference-gate"\nschema = 2\n' in pack_toml
    assert "[imports.superpowers]" in pack_toml
    assert f'source = "{pack_source}"' in pack_toml
    assert "[rigs.imports.gc]" in city_toml
    assert f'source = "{roles_source}"' in city_toml
    assert "[rigs.imports.superpowers]" in city_toml
    assert f'source = "{pack_source}"' in city_toml
    assert (
        workspace.rig_dir / ".gc" / "scripts" / "validate_build_artifact.py"
    ).read_text(encoding="utf-8") == "print('shared-validator')\n"
    assert (
        workspace.rig_dir / ".gc" / "scripts" / "verify_implementation_provenance.py"
    ).read_text(encoding="utf-8") == "print('shared-verifier')\n"


def test_write_gate_workspace_wires_gastown_city_and_rig_imports(tmp_path) -> None:
    pack_source = tmp_path / "repo" / "gastown"
    roles_source = tmp_path / "repo" / "gascity" / "roles"
    pack_source.mkdir(parents=True)
    roles_source.mkdir(parents=True)

    workspace = gascity_pack_inference_gate.write_gate_workspace(
        tmp_path / "gate",
        pack_source=pack_source,
        roles_source=roles_source,
        pack_binding="gastown",
        pack_name="gastown",
        gastown=True,
        city_name="gastown-inference-city",
        rig_name="fixture",
    )

    city_toml = (workspace.city_dir / "city.toml").read_text(encoding="utf-8")
    pack_toml = (workspace.city_dir / "pack.toml").read_text(encoding="utf-8")

    assert 'global_fragments = ["command-glossary", "operational-awareness"]' in city_toml
    assert "[defaults.rig.imports.gastown]" not in city_toml
    assert "[rigs.imports.gastown]" in city_toml
    assert f'source = "{pack_source}"' in city_toml
    assert "[rigs.imports.gc]" not in city_toml
    assert "[imports.gastown]" in pack_toml
    assert f'source = "{pack_source}"' in pack_toml


def test_build_gate_env_uses_nightly_ollama_auth_shape(tmp_path) -> None:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=tmp_path,
        city_dir=tmp_path / "city",
        rig_dir=tmp_path / "fixture",
        gc_home=tmp_path / "gc-home",
        runtime_dir=tmp_path / "runtime",
        claude_config_dir=tmp_path / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    workspace.gc_home.mkdir(parents=True)

    env = gascity_pack_inference_gate.build_gate_env(
        "/usr/bin/gc",
        workspace,
        inherited={
            "PATH": "/usr/bin",
            "HOME": str(tmp_path / "home"),
            "OLLAMA_API_KEY": "ollama-secret",
        },
    )

    assert env["ANTHROPIC_BASE_URL"] == "https://ollama.com"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "ollama-secret"
    assert env["HOME"] == str(tmp_path / "home")
    assert "ANTHROPIC_API_KEY" not in env
    assert "GC_SESSION" not in env
    assert "GC_BEADS" not in env
    assert "GC_DOLT" not in env
    assert env["DOLT_ROOT_PATH"] == str(workspace.gc_home)
    dolt_config = json.loads((workspace.gc_home / ".dolt" / "config_global.json").read_text(encoding="utf-8"))
    assert dolt_config["user.email"] == "gascity-pack-gate@example.invalid"


def test_supported_pack_nightly_workflow_uses_tier_c_ollama_shape_and_pack_matrix() -> None:
    workflow = SUPPORTED_PACK_NIGHTLY_WORKFLOW.read_text(encoding="utf-8")

    assert "name: Supported Pack Nightly" in workflow
    assert "\n  schedule:" in workflow
    assert "\n  pull_request:" not in workflow
    assert "\n  push:" not in workflow
    assert 'default: main' in workflow
    assert "description: \"Supported pack or group to exercise for manual subset checks.\"" in workflow
    assert "description: \"Inference gate to run for manual subset checks.\"" in workflow
    assert "name: Select gates and validate timeout" in workflow
    assert "id: subset" in workflow
    assert "SELECTED_GATES: ${{ needs.resolve-nightly-inputs.outputs.selected_gates }}" in workflow
    assert "MATRIX_PACK: ${{ matrix.pack }}" in workflow
    assert "MATRIX_GATE: ${{ matrix.gate }}" in workflow
    assert "github.event.inputs.pack == matrix.pack" not in workflow
    assert "github.event.inputs.gate == matrix.gate" not in workflow
    assert "run_gate=true" in workflow
    assert "if: steps.subset.outputs.run_gate == 'true'" in workflow
    assert "if: always() && steps.subset.outputs.run_gate == 'true'" in workflow
    assert "max-parallel: 1" in workflow
    document = supported_pack_nightly_document()
    for job_name in ("resolve-nightly-inputs", "static-contracts", "inference"):
        assert document["jobs"][job_name]["runs-on"] == "ubuntu-24.04"
    assert "blacksmith-" not in workflow
    assert "GATE_TIMEOUT: ${{ needs.resolve-nightly-inputs.outputs.gate_timeout || matrix.gate_timeout }}" in workflow
    assert '--timeout "$GATE_TIMEOUT"' in workflow
    assert 'DOLT_VERSION: "2.1.7"' in workflow
    assert 'BD_VERSION: "v1.1.0"' in workflow
    assert 'go-version: "1.26.5"' in workflow
    assert "name: Verify Beads compatibility" in workflow
    assert "github.com/steveyegge/beads" in workflow
    assert "resolve-nightly-inputs:" in workflow
    assert "needs: [resolve-nightly-inputs, static-contracts]" in workflow
    assert "needs.resolve-nightly-inputs.outputs.runtime_ref" in workflow
    assert "needs.resolve-nightly-inputs.outputs.setup_ref" in workflow
    assert 'GASCITY_REMOTE: https://github.com/gastownhall/gascity.git' in workflow
    assert "ANTHROPIC_BASE_URL: https://ollama.com" in workflow
    assert "ANTHROPIC_API_KEY: ${{ secrets.OLLAMA_API_KEY }}" in workflow
    assert "ANTHROPIC_AUTH_TOKEN: ${{ secrets.OLLAMA_API_KEY }}" in workflow
    assert "OLLAMA_API_KEY: ${{ secrets.OLLAMA_API_KEY }}" in workflow
    expected_entries = (
        ("gascity", "review", "30m"),
        ("gascity", "build-basic", "90m"),
        ("superpowers", "review", "45m"),
        ("superpowers", "build", "100m"),
        ("compound-engineering", "review", "45m"),
        ("compound-engineering", "build", "100m"),
        ("gstack", "review", "60m"),
        ("gstack", "build", "130m"),
        ("bmad", "review", "45m"),
        ("bmad", "build", "100m"),
        ("gastown", "gastown-orchestration", "110m"),
    )
    for pack, gate, gate_timeout in expected_entries:
        assert f"- pack: {pack}" in workflow
        assert f"gate: {gate}" in workflow
        assert f"gate_timeout: {gate_timeout}" in workflow
    assert '--pack "${{ matrix.pack }}"' in workflow
    assert '--gate "${{ matrix.gate }}"' in workflow
    assert "name: supported-pack-nightly-${{ matrix.pack }}-${{ matrix.gate }}" in workflow
    assert "include-hidden-files: true" in workflow


def test_supported_pack_nightly_static_contracts_cover_flow_regression_suites() -> None:
    document = supported_pack_nightly_document()
    static_steps = document["jobs"]["static-contracts"]["steps"]
    test_step = next(step for step in static_steps if step.get("name") == "Run supported-pack contract tests")

    assert test_step["run"].split() == [
        "python3",
        "-m",
        "pytest",
        "tests/test_gascity_pack_inference_gate.py",
        "gascity/tests/test_formula_assets.py",
        "gascity/tests/test_derived_pack_compatibility.py",
        "gascity/tests/test_validators.py",
        "-q",
    ]


def test_supported_pack_nightly_excludes_volatile_database_telemetry_from_diagnostics() -> None:
    document = supported_pack_nightly_document()
    upload = next(
        step
        for step in document["jobs"]["inference"]["steps"]
        if step.get("name") == "Upload inference gate diagnostics"
    )

    assert upload["with"]["path"].splitlines() == [
        "${{ runner.temp }}/supported-pack-nightly/${{ matrix.pack }}",
        "!${{ runner.temp }}/supported-pack-nightly/${{ matrix.pack }}/gc-home/.dolt/eventsData/**",
        "!${{ runner.temp }}/supported-pack-nightly/${{ matrix.pack }}/**/.beads/eventsData/**",
    ]


def test_supported_pack_nightly_primes_diagnostics_before_setup_and_fails_closed_if_missing(
    tmp_path,
) -> None:
    steps = supported_pack_nightly_document()["jobs"]["inference"]["steps"]
    checkout_index = next(
        index for index, step in enumerate(steps) if step.get("name") == "Check out gascity-packs"
    )
    diagnostics_dir = "$RUNNER_TEMP/supported-pack-nightly/$MATRIX_PACK"
    selected_row_guard = "steps.subset.outputs.run_gate == 'true'"
    primes_diagnostics = any(
        step.get("if") == selected_row_guard
        and isinstance((script := step.get("run")), str)
        and diagnostics_dir in script
        and re.search(r"\bmkdir\s+-p\b", script)
        and any(
            "run-context.txt" in line
            and (re.search(r"\btouch\b", line) or ">" in line or re.search(r"\btee\b", line))
            for line in script.splitlines()
        )
        for step in steps[:checkout_index]
    )
    upload = next(step for step in steps if step.get("name") == "Upload inference gate diagnostics")

    violations = []
    if not primes_diagnostics:
        violations.append(
            "selected inference rows must create the diagnostics directory and run-context.txt "
            "before checking out gascity-packs"
        )
    if upload["with"].get("if-no-files-found") != "error":
        violations.append("diagnostics upload must set if-no-files-found: error")

    assert not violations, "\n" + "\n".join(violations)

    initialize = next(
        step for step in steps if step.get("name") == "Initialize inference diagnostics"
    )
    result, _ = run_workflow_script(
        initialize["run"],
        tmp_path,
        RUNNER_TEMP=str(tmp_path),
        GITHUB_RUN_ID="123",
        GITHUB_RUN_ATTEMPT="2",
        MATRIX_PACK="gascity",
        MATRIX_GATE="build-basic",
        RUNTIME_REF="runtime-sha",
        SETUP_REF="setup-sha",
        PACK_REF="pack-sha",
    )
    assert result.returncode == 0, result.stderr
    assert (
        tmp_path / "supported-pack-nightly" / "gascity" / "run-context.txt"
    ).read_text(encoding="utf-8") == (
        "run_id=123\n"
        "run_attempt=2\n"
        "pack=gascity\n"
        "gate=build-basic\n"
        "runtime_ref=runtime-sha\n"
        "setup_ref=setup-sha\n"
        "pack_ref=pack-sha\n"
    )

    step_by_name = {step.get("name"): step for step in steps}
    prepare_name = "Prepare inference gate workdir"
    restore_name = "Restore inference run context"
    lifecycle_names = (
        "Initialize inference diagnostics",
        "Validate Ollama Claude configuration",
        prepare_name,
        "Run supported-pack nightly inference gate",
        restore_name,
        "Upload inference gate diagnostics",
    )
    lifecycle_violations = [
        f"workflow is missing explicit step {name!r}"
        for name in lifecycle_names
        if name not in step_by_name
    ]
    if not lifecycle_violations:
        positions = {
            step.get("name"): index
            for index, step in enumerate(steps)
            if step.get("name") in lifecycle_names
        }
        if [positions[name] for name in lifecycle_names] != sorted(
            positions[name] for name in lifecycle_names
        ):
            lifecycle_violations.append(
                "workflow lifecycle must order Initialize < setup < Prepare < Run < Restore < Upload"
            )
    prepare = step_by_name.get(prepare_name)
    restore = step_by_name.get(restore_name)
    if prepare is not None and prepare.get("if") != selected_row_guard:
        lifecycle_violations.append("Prepare must run only for selected inference rows")
    if restore is not None and restore.get("if") != f"always() && {selected_row_guard}":
        lifecycle_violations.append("Restore must use always() for selected inference rows")

    assert not lifecycle_violations, "\n" + "\n".join(lifecycle_violations)
    assert prepare is not None and restore is not None

    lifecycle_env = {
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "2",
        "MATRIX_PACK": "gascity",
        "MATRIX_GATE": "build-basic",
        "RUNTIME_REF": "runtime-sha",
        "SETUP_REF": "setup-sha",
        "PACK_REF": "pack-sha",
    }
    prepare_result, _ = run_workflow_script(prepare["run"], tmp_path, **lifecycle_env)
    assert prepare_result.returncode == 0, prepare_result.stderr

    gate_workdir = tmp_path / "supported-pack-nightly" / "gascity"
    assert not gate_workdir.exists() or not any(gate_workdir.iterdir()), (
        "Prepare must leave the exact inference gate workdir absent or empty"
    )

    gate_workdir.mkdir(parents=True, exist_ok=True)
    gate_output = gate_workdir / "gate-output.txt"
    gate_output.write_text("simulated gate diagnostics\n", encoding="utf-8")

    restore_result, _ = run_workflow_script(restore["run"], tmp_path, **lifecycle_env)
    assert restore_result.returncode == 0, restore_result.stderr
    assert gate_output.read_text(encoding="utf-8") == "simulated gate diagnostics\n"
    assert (gate_workdir / "run-context.txt").read_text(encoding="utf-8") == (
        "run_id=123\n"
        "run_attempt=2\n"
        "pack=gascity\n"
        "gate=build-basic\n"
        "runtime_ref=runtime-sha\n"
        "setup_ref=setup-sha\n"
        "pack_ref=pack-sha\n"
    )


@pytest.mark.parametrize(
    ("selected_pack", "selected_gate", "expected"),
    (
        ("gascity", "build", {"gascity:build-basic"}),
        (
            "all-supported",
            "build",
            {
                "gascity:build-basic",
                "superpowers:build",
                "compound-engineering:build",
                "gstack:build",
                "bmad:build",
            },
        ),
        (
            "methodology",
            "all",
            {
                "superpowers:review",
                "superpowers:build",
                "compound-engineering:review",
                "compound-engineering:build",
                "gstack:review",
                "gstack:build",
                "bmad:review",
                "bmad:build",
            },
        ),
        (
            "",
            "",
            {
                "gascity:review",
                "gascity:build-basic",
                "superpowers:review",
                "superpowers:build",
                "compound-engineering:review",
                "compound-engineering:build",
                "gstack:review",
                "gstack:build",
                "bmad:review",
                "bmad:build",
                "gastown:gastown-orchestration",
            },
        ),
    ),
)
def test_supported_pack_nightly_selects_manual_matrix_rows(
    tmp_path, selected_pack: str, selected_gate: str, expected: set[str]
) -> None:
    document = supported_pack_nightly_document()
    result, outputs = run_workflow_script(
        supported_pack_nightly_step_script("Select gates and validate timeout"),
        tmp_path,
        INPUT_PACK=selected_pack,
        INPUT_GATE=selected_gate,
        INPUT_TIMEOUT="",
        SUPPORTED_PACK_GATES=document["env"]["SUPPORTED_PACK_GATES"],
    )

    assert result.returncode == 0, result.stderr
    assert set(outputs["selected_gates"].split(",")) == expected
    assert outputs["gate_timeout"] == ""
    assert outputs["job_timeout_minutes"] == ""

    selected_rows: set[str] = set()
    subset_script = supported_pack_nightly_step_script("Decide manual subset")
    for entry in document["jobs"]["inference"]["strategy"]["matrix"]["include"]:
        result, subset_outputs = run_workflow_script(
            subset_script,
            tmp_path,
            SELECTED_GATES=outputs["selected_gates"],
            MATRIX_PACK=entry["pack"],
            MATRIX_GATE=entry["gate"],
        )
        assert result.returncode == 0, result.stderr
        if subset_outputs["run_gate"] == "true":
            selected_rows.add(f"{entry['pack']}:{entry['gate']}")
    assert selected_rows == expected


@pytest.mark.parametrize(
    ("selected_pack", "selected_gate"),
    (
        ("gascity", "gastown-orchestration"),
        ("methodology", "build-basic"),
        ("superpowers", "build-basic"),
        ("gastown", "review"),
    ),
)
def test_supported_pack_nightly_rejects_empty_manual_selections(
    tmp_path, selected_pack: str, selected_gate: str
) -> None:
    document = supported_pack_nightly_document()
    result, _ = run_workflow_script(
        supported_pack_nightly_step_script("Select gates and validate timeout"),
        tmp_path,
        INPUT_PACK=selected_pack,
        INPUT_GATE=selected_gate,
        INPUT_TIMEOUT="",
        SUPPORTED_PACK_GATES=document["env"]["SUPPORTED_PACK_GATES"],
    )

    assert result.returncode != 0
    assert "selects no supported pack gates" in result.stderr


@pytest.mark.parametrize(
    ("timeout_override", "expected_outer_minutes"),
    (
        ("90m", "120"),
        ("1.5h", "120"),
        ("30", "31"),
        ("330m", "360"),
    ),
)
def test_supported_pack_nightly_bounds_manual_timeout(
    tmp_path, timeout_override: str, expected_outer_minutes: str
) -> None:
    document = supported_pack_nightly_document()
    result, outputs = run_workflow_script(
        supported_pack_nightly_step_script("Select gates and validate timeout"),
        tmp_path,
        INPUT_PACK="gascity",
        INPUT_GATE="review",
        INPUT_TIMEOUT=timeout_override,
        SUPPORTED_PACK_GATES=document["env"]["SUPPORTED_PACK_GATES"],
    )

    assert result.returncode == 0, result.stderr
    assert outputs["gate_timeout"] == timeout_override
    assert outputs["job_timeout_minutes"] == expected_outer_minutes


@pytest.mark.parametrize("timeout_override", ("-1m", "0s", "331m", "5.6h", "soon"))
def test_supported_pack_nightly_rejects_invalid_manual_timeout(tmp_path, timeout_override: str) -> None:
    document = supported_pack_nightly_document()
    result, _ = run_workflow_script(
        supported_pack_nightly_step_script("Select gates and validate timeout"),
        tmp_path,
        INPUT_PACK="gascity",
        INPUT_GATE="review",
        INPUT_TIMEOUT=timeout_override,
        SUPPORTED_PACK_GATES=document["env"]["SUPPORTED_PACK_GATES"],
    )

    assert result.returncode != 0
    assert "Invalid timeout override" in result.stderr


def test_supported_pack_nightly_resolves_remote_refs_to_commit_shas(tmp_path) -> None:
    resolver = supported_pack_nightly_step_script("Resolve immutable refs")
    remote, refs = create_ref_resolution_remote(tmp_path)
    common_env = {
        "GASCITY_REMOTE": str(remote),
        "PACK_REMOTE": str(remote),
        "DEFAULT_PACK_SHA": refs["main"],
    }

    result, outputs = run_workflow_script(
        resolver,
        tmp_path,
        REQUESTED_RUNTIME_REF="latest",
        REQUESTED_SETUP_REF="feature/ref-resolution",
        REQUESTED_PACK_REF="v1.2.0",
        **common_env,
    )
    assert result.returncode == 0, result.stderr
    assert outputs["runtime_ref"] == refs["stable"]
    assert outputs["setup_ref"] == refs["first"]
    assert outputs["pack_ref"] == refs["first"]

    result, outputs = run_workflow_script(
        resolver,
        tmp_path,
        REQUESTED_RUNTIME_REF=refs["unadvertised"],
        REQUESTED_SETUP_REF="v2.0.0",
        REQUESTED_PACK_REF="",
        **common_env,
    )
    assert result.returncode == 0, result.stderr
    assert outputs["runtime_ref"] == refs["unadvertised"]
    assert outputs["setup_ref"] == refs["v2_stable"]
    assert outputs["pack_ref"] == refs["main"]

    result, outputs = run_workflow_script(
        resolver,
        tmp_path,
        REQUESTED_RUNTIME_REF="main",
        REQUESTED_SETUP_REF="main",
        REQUESTED_PACK_REF="main",
        **common_env,
    )
    assert result.returncode == 0, result.stderr
    assert outputs == {
        "runtime_ref": refs["main"],
        "setup_ref": refs["main"],
        "pack_ref": refs["main"],
    }

    result, outputs = run_workflow_script(
        resolver,
        tmp_path,
        REQUESTED_RUNTIME_REF="main",
        REQUESTED_SETUP_REF="missing/ref",
        REQUESTED_PACK_REF="main",
        **common_env,
    )
    assert result.returncode != 0
    assert outputs == {}
    assert "Could not resolve Gas City setup ref" in result.stderr

    result, outputs = run_workflow_script(
        resolver,
        tmp_path,
        REQUESTED_RUNTIME_REF="f" * 40,
        REQUESTED_SETUP_REF="main",
        REQUESTED_PACK_REF="main",
        **common_env,
    )
    assert result.returncode != 0
    assert outputs == {}
    assert "Could not resolve Gas City runtime ref" in result.stderr

    result, outputs = run_workflow_script(
        resolver,
        tmp_path,
        REQUESTED_RUNTIME_REF="main",
        REQUESTED_SETUP_REF="latest",
        REQUESTED_PACK_REF="v9.9.9",
        **common_env,
    )
    assert result.returncode != 0
    assert outputs == {}
    assert "Could not resolve Gas City setup ref" in result.stderr


def test_supported_pack_nightly_consumes_only_resolved_refs_and_timeout() -> None:
    document = supported_pack_nightly_document()
    workflow = SUPPORTED_PACK_NIGHTLY_WORKFLOW.read_text(encoding="utf-8")
    jobs = document["jobs"]
    resolver = jobs["resolve-nightly-inputs"]
    matrix_entries = jobs["inference"]["strategy"]["matrix"]["include"]
    expected_matrix = {f"{entry['pack']}:{entry['gate']}" for entry in matrix_entries}

    assert set(document["env"]["SUPPORTED_PACK_GATES"].split()) == expected_matrix
    assert jobs["static-contracts"]["needs"] == "resolve-nightly-inputs"
    assert jobs["inference"]["needs"] == ["resolve-nightly-inputs", "static-contracts"]
    assert resolver["outputs"]["pack_ref"] == "${{ steps.refs.outputs.pack_ref }}"
    assert resolver["outputs"]["runtime_ref"] == "${{ steps.refs.outputs.runtime_ref }}"
    assert resolver["outputs"]["setup_ref"] == "${{ steps.refs.outputs.setup_ref }}"
    assert jobs["inference"]["timeout-minutes"] == (
        "${{ fromJSON(needs.resolve-nightly-inputs.outputs.job_timeout_minutes || '0') || matrix.timeout_minutes }}"
    )
    assert workflow.count("ref: ${{ needs.resolve-nightly-inputs.outputs.pack_ref }}") == 2
    assert "ref: ${{ needs.resolve-nightly-inputs.outputs.setup_ref }}" in workflow
    assert "GASCITY_REF: ${{ needs.resolve-nightly-inputs.outputs.runtime_ref }}" in workflow
    assert "GATE_TIMEOUT: ${{ needs.resolve-nightly-inputs.outputs.gate_timeout || matrix.gate_timeout }}" in workflow
    assert "ref: ${{ github.event.inputs.pack_ref || github.ref }}" not in workflow
    assert "printf '%s\\n' \"$requested\"" not in supported_pack_nightly_step_script("Resolve immutable refs")


def test_dispatch_inference_workflow_is_manual_or_external_only() -> None:
    workflow = (gascity_pack_inference_gate.REPO_ROOT / ".github" / "workflows" / "gascity-pack-inference.yml").read_text(
        encoding="utf-8"
    )

    assert "repository_dispatch:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "\n  schedule:" not in workflow
    assert "\n  pull_request:" not in workflow
    assert "\n  push:" not in workflow
    assert "runs-on: blacksmith-32vcpu-ubuntu-2404" in workflow
    assert 'DOLT_VERSION: "2.1.0"' in workflow
    assert "ANTHROPIC_API_KEY: ${{ secrets.OLLAMA_API_KEY }}" in workflow
    assert "include-hidden-files: true" in workflow


def test_ci_workflows_use_blacksmith_runner_labels() -> None:
    expected = {
        ".github/workflows/ci.yml": "runs-on: blacksmith-32vcpu-ubuntu-2404",
        ".github/workflows/codeql.yml": "runs-on: blacksmith-32vcpu-ubuntu-2404",
        ".github/workflows/pack-release-compatibility.yml": "runs-on: blacksmith-32vcpu-ubuntu-2404",
    }

    for relative_path, marker in expected.items():
        workflow = (gascity_pack_inference_gate.REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert marker in workflow


def test_readme_includes_blacksmith_sponsor_badge() -> None:
    readme = (gascity_pack_inference_gate.REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_lines = {line.strip() for line in readme.splitlines()}

    assert "## Sponsors" in readme
    assert '<a href="https://blacksmith.sh/">' in readme_lines
    assert "docs/images/blacksmith-powered.png" in readme
    assert (gascity_pack_inference_gate.REPO_ROOT / "docs" / "images" / "blacksmith-powered.png").is_file()


def test_build_gate_env_exposes_host_pytest_to_isolated_runtime(tmp_path) -> None:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=tmp_path,
        city_dir=tmp_path / "city",
        rig_dir=tmp_path / "fixture",
        gc_home=tmp_path / "gc-home",
        runtime_dir=tmp_path / "runtime",
        claude_config_dir=tmp_path / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    workspace.gc_home.mkdir(parents=True)
    existing_pythonpath = str(tmp_path / "existing-pythonpath")

    env = gascity_pack_inference_gate.build_gate_env(
        "/usr/bin/gc",
        workspace,
        inherited={
            "PATH": "/usr/bin",
            "HOME": str(tmp_path / "home"),
            "OLLAMA_API_KEY": "ollama-secret",
            "PYTHONPATH": existing_pythonpath,
        },
    )

    pytest_root = Path(pytest.__file__).resolve().parent.parent
    pythonpath_parts = env["PYTHONPATH"].split(os.pathsep)
    assert pythonpath_parts[0] == existing_pythonpath
    assert str(pytest_root) in pythonpath_parts


def test_seed_claude_project_state_writes_home_and_config_state(tmp_path) -> None:
    home = tmp_path / "home"
    config_dir = tmp_path / "claude-config"
    city_dir = tmp_path / "city"
    rig_dir = tmp_path / "rig"
    city_dir.mkdir()
    rig_dir.mkdir()

    gascity_pack_inference_gate.seed_claude_project_state(
        home=home,
        config_dir=config_dir,
        project_paths=[city_dir, rig_dir],
    )

    for state_path in (home / ".claude.json", config_dir / ".claude.json"):
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["hasCompletedOnboarding"] is True
        assert data["theme"] == "light"
        for project in (city_dir.resolve(), rig_dir.resolve()):
            entry = data["projects"][str(project)]
            assert entry["hasCompletedProjectOnboarding"] is True
            assert entry["hasTrustDialogAccepted"] is True
            assert entry["projectOnboardingSeenCount"] == 1


def test_find_unique_bead_by_title_rejects_missing_or_ambiguous() -> None:
    beads = [
        {"id": "bd-1", "title": "other", "status": "open"},
        {"id": "bd-2", "title": "gate title", "status": "open"},
    ]

    assert gascity_pack_inference_gate.find_unique_bead_by_title(beads, "gate title")["id"] == "bd-2"
    assert gascity_pack_inference_gate.find_unique_bead_by_title(beads, "missing") is None
    assert gascity_pack_inference_gate.find_unique_bead_by_title(beads + [beads[1]], "gate title") is None


def test_extract_sling_root_id_searches_nested_json() -> None:
    output = """
    warning: ignored line
    {"dispatch": {"root_bead_id": "rv-123", "nested": [{"id": "other"}]}}
    """

    assert gascity_pack_inference_gate.extract_sling_root_id(output) == "rv-123"
    assert gascity_pack_inference_gate.extract_sling_root_id("not json") is None


def test_launch_review_formula_uses_absolute_rig_artifact_paths(tmp_path) -> None:
    root = tmp_path / "gate with spaces"
    root.mkdir()
    workspace = gate_workspace(root)
    fake_gc = tmp_path / "gc"
    args_path = tmp_path / "gc-args.txt"
    fake_gc.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$@" > {shlex.quote(str(args_path))}
printf '{{"root_bead_id":"fi-root"}}\\n'
""",
        encoding="utf-8",
    )
    fake_gc.chmod(0o755)

    root_id = gascity_pack_inference_gate.launch_review_formula(
        str(fake_gc),
        workspace,
        env={},
        pack_spec=gascity_pack_inference_gate.PACK_SPECS["gascity"],
    )

    assert root_id == "fi-root"
    args = args_path.read_text(encoding="utf-8").splitlines()
    subject_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_SUBJECT_PATH).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    assert f"subject_path={subject_path}" in args
    assert f"report_path={report_path}" in args
    assert f"subject_path={gascity_pack_inference_gate.REVIEW_SUBJECT_PATH}" not in args
    assert f"report_path={gascity_pack_inference_gate.REVIEW_REPORT_PATH}" not in args


def test_launch_build_formula_uses_absolute_rig_artifact_root(
    tmp_path, monkeypatch
) -> None:
    root = tmp_path / "gate with spaces"
    root.mkdir()
    workspace = gate_workspace(root)
    fake_gc = tmp_path / "gc"
    args_path = tmp_path / "gc-args.txt"
    fake_gc.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$@" > {shlex.quote(str(args_path))}
printf '{{"root_bead_id":"fi-root"}}\\n'
""",
        encoding="utf-8",
    )
    fake_gc.chmod(0o755)
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "resolve_workflow_root_id",
        lambda *args, candidate_id, **kwargs: candidate_id,
    )

    root_id = gascity_pack_inference_gate.launch_build_formula(
        str(fake_gc),
        workspace,
        env={},
        pack_spec=gascity_pack_inference_gate.PACK_SPECS["gascity"],
    )

    assert root_id == "fi-root"
    args = args_path.read_text(encoding="utf-8").splitlines()
    artifact_root = (
        workspace.rig_dir
        / gascity_pack_inference_gate.build_artifact_root(
            gascity_pack_inference_gate.PACK_SPECS["gascity"]
        )
    ).resolve()
    assert f"artifact_root={artifact_root}" in args
    assert (
        f"artifact_root={gascity_pack_inference_gate.BUILD_ARTIFACT_ROOT}"
        not in args
    )


def test_run_build_gate_passes_complete_bead_snapshot_to_artifact_validation(
    tmp_path,
    monkeypatch,
) -> None:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=tmp_path,
        city_dir=tmp_path / "city",
        rig_dir=tmp_path / "fixture",
        gc_home=tmp_path / "gc-home",
        runtime_dir=tmp_path / "runtime",
        claude_config_dir=tmp_path / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    pack_spec = gascity_pack_inference_gate.PACK_SPECS["superpowers"]
    root_bead = {"id": "fi-root", "metadata": {}}
    beads = [{"id": "fi-source"}, {"id": "fi-review-control"}]
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "git_output",
        lambda *args, **kwargs: "a" * 40,
    )
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "launch_build_formula",
        lambda *args, **kwargs: "fi-root",
    )
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "wait_for_workflow_pass",
        lambda *args, **kwargs: root_bead,
    )
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "list_beads",
        lambda *args, **kwargs: beads,
    )
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "build_basic_source_id",
        lambda value: "fi-source",
    )
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "implementation_convoy_member_ids",
        lambda *args, **kwargs: ["fi-member"],
    )

    def capture_artifact_validation(bead, **kwargs) -> None:
        observed["root_bead"] = bead
        observed.update(kwargs)

    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "validate_build_basic_artifacts",
        capture_artifact_validation,
    )
    for function_name in (
        "validate_build_basic_source_provenance",
        "validate_build_basic_result",
        "validate_required_routes",
    ):
        monkeypatch.setattr(
            gascity_pack_inference_gate,
            function_name,
            lambda *args, **kwargs: None,
        )

    gascity_pack_inference_gate.run_build_gate(
        "/usr/bin/gc",
        workspace,
        env={},
        pack_spec=pack_spec,
        timeout=60,
        poll_interval=1,
    )

    assert observed["root_bead"] is root_bead
    assert observed["beads"] is beads
    assert observed["pack_spec"] is pack_spec
    assert observed["expected_artifact_root"] == (
        workspace.rig_dir / gascity_pack_inference_gate.build_artifact_root(pack_spec)
    )


def test_list_beads_uses_gc_bd_list_when_file_store_absent(tmp_path) -> None:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=tmp_path,
        city_dir=tmp_path / "city",
        rig_dir=tmp_path / "fixture",
        gc_home=tmp_path / "gc-home",
        runtime_dir=tmp_path / "runtime",
        claude_config_dir=tmp_path / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    workspace.city_dir.mkdir()
    workspace.rig_dir.mkdir()
    fake_gc = tmp_path / "gc"
    args_path = tmp_path / "gc-args.txt"
    fake_gc.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$@" > {shlex.quote(str(args_path))}
printf 'warning: noisy config refresh\\n' >&2
printf '[{{"id":"fi-1","title":"root","status":"open"}}]\\n'
""",
        encoding="utf-8",
    )
    fake_gc.chmod(0o755)

    beads = gascity_pack_inference_gate.list_beads(str(fake_gc), workspace, env={})

    assert beads == [{"id": "fi-1", "title": "root", "status": "open"}]
    assert args_path.read_text(encoding="utf-8").splitlines()[-4:] == ["--all", "--json", "--limit", "1000"]


def test_list_beads_falls_back_to_city_event_log_when_live_list_is_empty(tmp_path) -> None:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=tmp_path,
        city_dir=tmp_path / "city",
        rig_dir=tmp_path / "fixture",
        gc_home=tmp_path / "gc-home",
        runtime_dir=tmp_path / "runtime",
        claude_config_dir=tmp_path / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    (workspace.city_dir / ".gc").mkdir(parents=True)
    workspace.rig_dir.mkdir()
    fake_gc = tmp_path / "gc"
    fake_gc.write_text("#!/bin/sh\nprintf '[]\\n'\n", encoding="utf-8")
    fake_gc.chmod(0o755)

    event = {
        "type": "bead.updated",
        "payload": {
            "bead": {
                "id": "fi-dk42",
                "title": "Write review report",
                "status": "closed",
                "metadata": {
                    "gc.run_target": "gc.implementation-reviewer",
                    "gc.routed_to": "fixture/gc.implementation-reviewer",
                },
            }
        },
    }
    (workspace.city_dir / ".gc" / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    beads = gascity_pack_inference_gate.list_beads(str(fake_gc), workspace, env={})

    assert beads == [event["payload"]["bead"]]
    gascity_pack_inference_gate.validate_required_routes(
        beads,
        ["gc.implementation-reviewer"],
        context="replayed review gate",
    )


def test_list_beads_falls_back_to_current_city_event_log_shape(tmp_path) -> None:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=tmp_path,
        city_dir=tmp_path / "city",
        rig_dir=tmp_path / "fixture",
        gc_home=tmp_path / "gc-home",
        runtime_dir=tmp_path / "runtime",
        claude_config_dir=tmp_path / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    (workspace.city_dir / ".gc").mkdir(parents=True)
    workspace.rig_dir.mkdir()
    fake_gc = tmp_path / "gc"
    fake_gc.write_text("#!/bin/sh\nprintf '[]\\n'\n", encoding="utf-8")
    fake_gc.chmod(0o755)

    event = {
        "type": "bead.closed",
        "payload": {
            "id": "fi-dk42",
            "title": "Write review report",
            "status": "closed",
            "metadata": {
                "gc.run_target": "gc.implementation-reviewer",
                "gc.routed_to": "fixture/gc.implementation-reviewer",
            },
        },
    }
    (workspace.city_dir / ".gc" / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    beads = gascity_pack_inference_gate.list_beads(str(fake_gc), workspace, env={})

    assert beads == [event["payload"]]
    gascity_pack_inference_gate.validate_required_routes(
        beads,
        ["gc.implementation-reviewer"],
        context="replayed current event gate",
    )


def test_list_beads_merges_event_route_history_when_live_list_is_incomplete(tmp_path) -> None:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=tmp_path,
        city_dir=tmp_path / "city",
        rig_dir=tmp_path / "fixture",
        gc_home=tmp_path / "gc-home",
        runtime_dir=tmp_path / "runtime",
        claude_config_dir=tmp_path / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    (workspace.city_dir / ".gc").mkdir(parents=True)
    workspace.rig_dir.mkdir()
    fake_gc = tmp_path / "gc"
    fake_gc.write_text(
        """#!/bin/sh
printf '[{"id":"fi-hm7i","title":"Write review report","assignee":"fixture--control-dispatcher"}]\n'
""",
        encoding="utf-8",
    )
    fake_gc.chmod(0o755)

    event = {
        "type": "bead.updated",
        "payload": {
            "bead": {
                "id": "fi-glhz",
                "title": "Write review report",
                "status": "closed",
                "metadata": {
                    "gc.run_target": "gc.implementation-reviewer",
                    "gc.routed_to": "fixture/gc.implementation-reviewer",
                },
            }
        },
    }
    (workspace.city_dir / ".gc" / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    beads = gascity_pack_inference_gate.list_beads(str(fake_gc), workspace, env={})

    assert beads[0]["id"] == "fi-hm7i"
    assert beads[1]["id"] == "__gc_event_route_history__"
    assert gascity_pack_inference_gate.find_unique_bead_by_title(beads, "Write review report")["id"] == "fi-hm7i"
    gascity_pack_inference_gate.validate_required_routes(
        beads,
        ["gc.implementation-reviewer"],
        context="review gate with live list",
    )


def test_wait_for_workflow_pass_uses_bd_show_for_closed_root(tmp_path) -> None:
    workspace = gascity_pack_inference_gate.GateWorkspace(
        root=tmp_path,
        city_dir=tmp_path / "city",
        rig_dir=tmp_path / "fixture",
        gc_home=tmp_path / "gc-home",
        runtime_dir=tmp_path / "runtime",
        claude_config_dir=tmp_path / "gc-home" / ".claude",
        city_name="inference-city",
        rig_name="fixture",
    )
    workspace.city_dir.mkdir()
    workspace.rig_dir.mkdir()
    fake_gc = tmp_path / "gc"
    args_path = tmp_path / "gc-args.txt"
    fake_gc.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$*" >> {shlex.quote(str(args_path))}
case "$*" in
  *"bd show fi-root --json"*) # gc-bd-argv-tail: fake gc receives the wrapper's argv tail
    printf '[{{"id":"fi-root","title":"root","status":"closed","metadata":{{"gc.outcome":"pass"}}}}]\\n'
    ;;
  *"bd list --all --json --limit 1000"*) # gc-bd-argv-tail: fake gc receives the wrapper's argv tail
    printf '[{{"id":"fi-finalize","title":"Finalize workflow","status":"closed","metadata":{{"gc.root_bead_id":"fi-root","gc.kind":"workflow-finalize","gc.outcome":"pass"}}}}]\\n'
    ;;
  *)
    printf '{{}}\\n'
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_gc.chmod(0o755)

    bead = gascity_pack_inference_gate.wait_for_workflow_pass(
        str(fake_gc),
        workspace,
        "fi-root",
        env={},
        timeout=5,
        poll_interval=0,
    )

    assert bead["id"] == "fi-root"
    assert "bd show fi-root --json" in args_path.read_text(encoding="utf-8")  # gc-bd-argv-tail


def test_wait_for_workflow_pass_rejects_failed_logical_control(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    fake_gc = tmp_path / "gc"
    fake_gc.write_text(
        """#!/bin/sh
case "$*" in
  *"bd show fi-root --json"*) # gc-bd-argv-tail: fake gc receives the wrapper's argv tail
    printf '[{"id":"fi-root","title":"root","status":"closed","metadata":{"gc.outcome":"pass"}}]\n'
    ;;
  *"bd list --all --json --limit 1000"*) # gc-bd-argv-tail: fake gc receives the wrapper's argv tail
    printf '[{"id":"fi-review","title":"Review implementation","status":"closed","metadata":{"gc.root_bead_id":"fi-root","gc.kind":"ralph","gc.outcome":"fail","gc.step_ref":"build.review"}},{"id":"fi-finalize","status":"closed","metadata":{"gc.root_bead_id":"fi-root","gc.kind":"workflow-finalize","gc.outcome":"pass"}}]\n'
    ;;
  *)
    printf '{}\n'
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_gc.chmod(0o755)

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="logical workflow control failed.*fi-review.*build.review",
    ):
        gascity_pack_inference_gate.wait_for_workflow_pass(
            str(fake_gc),
            workspace,
            "fi-root",
            env={},
            timeout=5,
            poll_interval=0,
        )


@pytest.mark.parametrize("failed_outcome", ["fail", "", "blocked"])
def test_wait_for_workflow_pass_fails_fast_while_root_is_open(
    tmp_path, monkeypatch, failed_outcome
) -> None:
    workspace = gate_workspace(tmp_path)
    root = {"id": "fi-root", "status": "in_progress", "metadata": {}}
    failed_control = {
        "id": "fi-review",
        "title": "Review implementation",
        "status": "closed",
        "metadata": {
            "gc.root_bead_id": "fi-root",
            "gc.kind": "ralph",
            "gc.step_ref": "build.review",
        },
    }
    if failed_outcome:
        failed_control["metadata"]["gc.outcome"] = failed_outcome
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "show_bead",
        lambda *args, **kwargs: root,
    )
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "list_beads",
        lambda *args, **kwargs: [failed_control],
    )
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "collect_diagnostics",
        lambda *args, **kwargs: "diagnostics",
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="workflow fi-root cannot pass.*fi-review.*build.review",
    ):
        gascity_pack_inference_gate.wait_for_workflow_pass(
            "gc",
            workspace,
            "fi-root",
            env={},
            timeout=0.05,
            poll_interval=0.001,
        )


def test_wait_for_workflow_pass_rejects_failed_nested_implementation_control(
    tmp_path, monkeypatch
) -> None:
    workspace = gate_workspace(tmp_path)
    root = closed_bead(
        "fi-root",
        kind="workflow",
        metadata={"gc.build.implementation_convoy_id": "fi-implementation"},
    )
    beads = complete_nested_workflow_lineage()
    beads.extend(
        [
            lineage_drain(
                "fi-nested-drain",
                "fi-nested",
                "fi-leaf-workflow",
                root_key="outcome_bead_id",
            ),
            closed_bead("fi-leaf-workflow", kind="workflow"),
            closed_bead(
                "fi-member-implement",
                root="fi-leaf-workflow",
                kind="ralph",
                outcome="fail",
                metadata={"gc.step_ref": "do-work.implement"},
            ),
            closed_bead("fi-member-finalize", root="fi-leaf-workflow", kind="workflow-finalize"),
        ]
    )
    monkeypatch.setattr(gascity_pack_inference_gate, "show_bead", lambda *args, **kwargs: root)
    monkeypatch.setattr(gascity_pack_inference_gate, "list_beads", lambda *args, **kwargs: beads)
    monkeypatch.setattr(gascity_pack_inference_gate, "collect_diagnostics", lambda *args, **kwargs: "diagnostics")

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="logical workflow control failed.*fi-member-implement.*do-work.implement",
    ):
        gascity_pack_inference_gate.wait_for_workflow_pass(
            "gc",
            workspace,
            "fi-root",
            env={},
            timeout=5,
            poll_interval=0,
        )


def provider_log_snapshot(*entries: dict, path: str = "/tmp/provider-session.jsonl") -> str:
    return json.dumps(
        {
            "schema_version": "1",
            "transcript_path": path,
            "entries": list(entries),
        }
    )


def provider_assistant_entry(
    text: str,
    *,
    uuid: str,
    model: str = "<synthetic>",
) -> dict:
    content = [{"type": "text", "text": text}]
    return {
        "uuid": uuid,
        "type": "assistant",
        "role": "assistant",
        "blocks": content,
        "message": {"model": model, "role": "assistant", "content": content},
    }


def workflow_claim(session_identity: str, *, root: str = "fi-root") -> dict:
    return {
        "id": "fi-work",
        "status": "in_progress",
        "assignee": session_identity,
        "metadata": {"gc.root_bead_id": root, "gc.kind": "ralph"},
    }


TERMINAL_TOOL_USE_ERROR = (
    "API Error: 400 {\"error\":{\"message\":"
    "\"tool_use block missing required 'name' field\"}}"
)
WEEKLY_PROVIDER_QUOTA_ERROR = (
    "API Error: Request rejected (429) · you (nightly-test) have reached your "
    "weekly usage limit, add extra usage: https://example.invalid/settings"
)
CLAUDE_FALLBACK_WORK_DIR = Path(
    "/home/runner/work/_temp/supported-pack-nightly/superpowers/fixture/"
    "fi-34t-prepare-build-context"
)
CLAUDE_FALLBACK_PROJECT_SLUG = (
    "-home-runner-work--temp-supported-pack-nightly-superpowers-fixture-"
    "fi-34t-prepare-build-context"
)
CLAUDE_FALLBACK_SESSION_STARTED_AT = "2026-07-16T22:49:18Z"


def raw_claude_project_dir(
    workspace: gascity_pack_inference_gate.GateWorkspace,
) -> Path:
    project_dir = (
        workspace.claude_config_dir
        / "projects"
        / CLAUDE_FALLBACK_PROJECT_SLUG
    )
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def write_raw_claude_transcript(
    workspace: gascity_pack_inference_gate.GateWorkspace,
    *,
    conversation_id: str,
    cwd: Path,
    timestamp: str,
    text: str = WEEKLY_PROVIDER_QUOTA_ERROR,
    model: str = "<synthetic>",
    project_slug: str = CLAUDE_FALLBACK_PROJECT_SLUG,
) -> Path:
    entry = provider_assistant_entry(
        text,
        uuid=f"{conversation_id}-tip",
        model=model,
    )
    entry.update(
        {
            "timestamp": timestamp,
            "cwd": str(cwd),
            "sessionId": conversation_id,
        }
    )
    project_dir = workspace.claude_config_dir / "projects" / project_slug
    project_dir.mkdir(parents=True, exist_ok=True)
    transcript = project_dir / f"{conversation_id}.jsonl"
    transcript.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return transcript


def write_raw_claude_entries(
    workspace: gascity_pack_inference_gate.GateWorkspace,
    *,
    conversation_id: str,
    entries: list[dict],
    project_slug: str = CLAUDE_FALLBACK_PROJECT_SLUG,
) -> Path:
    project_dir = workspace.claude_config_dir / "projects" / project_slug
    project_dir.mkdir(parents=True, exist_ok=True)
    transcript = project_dir / f"{conversation_id}.jsonl"
    transcript.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return transcript


def raw_claude_entry(
    *,
    conversation_id: str,
    entry_id: str,
    timestamp: str,
    text: str,
    model: str,
    parent_id: str = "",
    cwd: Path = CLAUDE_FALLBACK_WORK_DIR,
) -> dict:
    entry = provider_assistant_entry(text, uuid=entry_id, model=model)
    entry.update(
        {
            "parentUuid": parent_id,
            "timestamp": timestamp,
            "cwd": str(cwd),
            "sessionId": conversation_id,
        }
    )
    return entry


def default_raw_claude_tip(
    workspace: gascity_pack_inference_gate.GateWorkspace,
    *,
    cache,
):
    session = {
        "id": "spig-a4b",
        "template": "fixture/gc.run-operator",
        "state": "active",
        "work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
    }
    return gascity_pack_inference_gate.raw_claude_session_log_tip(
        workspace,
        session,
        {
            "id": "spig-a4b",
            "issue_type": "session",
            "created_at": CLAUDE_FALLBACK_SESSION_STARTED_AT,
            "metadata": {
                "provider": "claude",
                "template": "fixture/gc.run-operator",
                "gc.work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
                "work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
            },
        },
        sessions=[session],
        cache=cache,
    )


def configure_raw_claude_fallback_watchdog(tmp_path, monkeypatch):
    workspace = gate_workspace(tmp_path)
    commands: list[list[str]] = []
    session = {
        "id": "spig-a4b",
        "session_name": "gc__run-operator-spig-a4b",
        "template": "fixture/gc.run-operator",
        "state": "active",
        "last_active": "2020-01-01T00:00:00Z",
        "attached": False,
        "work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
    }
    session_bead = {
        "id": "spig-a4b",
        "issue_type": "session",
        "created_at": CLAUDE_FALLBACK_SESSION_STARTED_AT,
        "metadata": {
            "provider": "claude",
            "template": "fixture/gc.run-operator",
            "gc.trigger_bead_id": "fi-work",
            "gc.trigger_bead_store_ref": "rig:fixture",
            "gc.work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
            "work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
            "creation_complete_at": CLAUDE_FALLBACK_SESSION_STARTED_AT,
        },
    }
    beads = [
        {
            "id": "fi-work",
            "status": "open",
            "metadata": {
                "gc.root_bead_id": "fi-root",
                "gc.root_store_ref": "rig:fixture",
                "gc.routed_to": "fixture/gc.run-operator",
            },
        }
    ]

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        if "session" in argv:
            operation = argv[argv.index("session") + 1]
            if operation == "list":
                return json.dumps({"_cache_age_s": 0.25, "sessions": [session]})
            if operation == "logs":
                raise subprocess.CalledProcessError(
                    1,
                    argv,
                    stderr="no session file found",
                )
            if operation == "reset":
                return '{"status":"reset_requested"}\n'
        if "bd" in argv and argv[argv.index("bd") + 1] == "show":
            return json.dumps([session_bead])
        raise AssertionError(f"unexpected command: {argv!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)

    def recover() -> None:
        gascity_pack_inference_gate.recover_terminal_provider_sessions(
            "gc",
            workspace,
            env={},
            beads=beads,
            root_id="fi-root",
            resets={},
            now=0.0,
        )

    return workspace, commands, recover


def configure_claimed_raw_claude_watchdog(tmp_path, monkeypatch):
    workspace = gate_workspace(tmp_path)
    commands: list[list[str]] = []
    session_name = "gc__run-operator-spig-a4b"
    session = {
        "id": "spig-a4b",
        "session_name": session_name,
        "template": "fixture/gc.run-operator",
        "state": "active",
        "last_active": "2020-01-01T00:00:00Z",
        "attached": False,
        "work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
    }
    session_bead = {
        "id": "spig-a4b",
        "issue_type": "session",
        "created_at": CLAUDE_FALLBACK_SESSION_STARTED_AT,
        "metadata": {
            "provider": "claude",
            "template": "fixture/gc.run-operator",
            "gc.work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
            "work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
        },
    }
    claim = workflow_claim(session_name)
    cache_age = [0.25]

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        if "session" in argv:
            operation = argv[argv.index("session") + 1]
            if operation == "list":
                return json.dumps(
                    {"_cache_age_s": cache_age[0], "sessions": [session]}
                )
            if operation == "logs":
                raise subprocess.CalledProcessError(
                    1,
                    argv,
                    stderr="no session file found",
                )
            if operation == "reset":
                return '{"status":"reset_requested"}\n'
        if "bd" in argv and argv[argv.index("bd") + 1] == "show":
            return json.dumps([session_bead])
        raise AssertionError(f"unexpected command: {argv!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)

    def recover(*, resets, now: float, cache) -> None:
        gascity_pack_inference_gate.recover_terminal_provider_sessions(
            "gc",
            workspace,
            env={},
            beads=[claim],
            root_id="fi-root",
            resets=resets,
            now=now,
            raw_claude_cache=cache,
        )

    return workspace, commands, cache_age, recover


def test_provider_log_tip_classifies_weekly_quota_as_fatal() -> None:
    tip = gascity_pack_inference_gate.provider_log_tip(
        provider_log_snapshot(
            provider_assistant_entry(WEEKLY_PROVIDER_QUOTA_ERROR, uuid="quota-error")
        )
    )

    assert tip is not None
    assert tip.fatal_error == "provider_quota_exhausted"


def test_provider_log_tip_leaves_generic_synthetic_429_nonfatal() -> None:
    tip = gascity_pack_inference_gate.provider_log_tip(
        provider_log_snapshot(
            provider_assistant_entry(
                "API Error: Request rejected (429) · provider is temporarily rate limited",
                uuid="transient-rate-limit",
            )
        )
    )

    assert tip is not None
    assert tip.fatal_error == ""
    assert not tip.terminal_error


@pytest.mark.parametrize(
    ("status", "error_class"),
    (
        (401, "provider_authentication_failed"),
        (403, "provider_authorization_failed"),
    ),
)
def test_provider_log_tip_classifies_terminal_provider_http_status(
    status, error_class
) -> None:
    tip = gascity_pack_inference_gate.provider_log_tip(
        provider_log_snapshot(
            provider_assistant_entry(
                f"API Error: Request rejected ({status}) · provider request failed",
                uuid=f"http-{status}",
            )
        )
    )

    assert tip is not None
    assert tip.fatal_error == error_class


def test_session_bead_snapshot_falls_back_to_city_event_log(tmp_path, monkeypatch) -> None:
    workspace = gate_workspace(tmp_path)
    event_path = workspace.city_dir / ".gc" / "events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_text(
        json.dumps(
            {
                "type": "bead.updated",
                "payload": {
                    "id": "spig-a5x",
                    "title": "fixture/gc.run-operator-1",
                    "issue_type": "session",
                    "metadata": {
                        "provider": "claude",
                        "template": "fixture/gc.run-operator",
                        "gc.trigger_bead_id": "fi-work",
                        "gc.trigger_bead_store_ref": "rig:fixture",
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "run_checked",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, ["gc", "bd", "show"])
        ),
    )

    bead = gascity_pack_inference_gate.session_bead_snapshot(
        "gc", workspace, "spig-a5x", env={}
    )

    assert bead is not None
    assert bead["metadata"]["gc.trigger_bead_id"] == "fi-work"


def test_terminal_provider_watchdog_reads_event_log_once_per_scan(
    tmp_path, monkeypatch
) -> None:
    workspace = gate_workspace(tmp_path)
    session_ids = ("spig-first", "spig-second")
    commands: list[list[str]] = []
    event_log_reads = 0

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        if "session" in argv:
            operation = argv[argv.index("session") + 1]
            if operation == "list":
                return json.dumps(
                    {
                        "sessions": [
                            {
                                "id": session_id,
                                "session_name": f"gc__run-operator-{session_id}",
                                "template": "fixture/gc.run-operator",
                                "state": "active",
                                "last_active": "2020-01-01T00:00:00Z",
                                "attached": False,
                            }
                            for session_id in session_ids
                        ]
                    }
                )
            if operation == "logs":
                session_id = argv[argv.index("logs") + 1]
                return provider_log_snapshot(
                    provider_assistant_entry(
                        "Provider request completed normally.",
                        uuid=f"progress-{session_id}",
                        model="claude-sonnet",
                    )
                )
        if "bd" in argv and argv[argv.index("bd") + 1] == "show":
            raise subprocess.CalledProcessError(1, argv)
        raise AssertionError(f"unexpected command: {argv!r}")

    def list_beads_from_event_log(_workspace):
        nonlocal event_log_reads
        event_log_reads += 1
        return [
            {
                "id": session_id,
                "issue_type": "session",
                "metadata": {
                    "provider": "claude",
                    "template": "fixture/gc.run-operator",
                    "gc.trigger_bead_id": f"fi-work-{index}",
                    "gc.trigger_bead_store_ref": "rig:fixture",
                },
            }
            for index, session_id in enumerate(session_ids, start=1)
        ]

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "list_beads_from_event_log",
        list_beads_from_event_log,
    )

    gascity_pack_inference_gate.recover_terminal_provider_sessions(
        "gc",
        workspace,
        env={},
        beads=[
            {
                "id": f"fi-work-{index}",
                "status": "open",
                "metadata": {
                    "gc.root_bead_id": "fi-root",
                    "gc.root_store_ref": "rig:fixture",
                    "gc.routed_to": "fixture/gc.run-operator",
                },
            }
            for index in range(1, 3)
        ],
        root_id="fi-root",
        resets={},
        now=0.0,
    )

    assert event_log_reads == 1
    inspected_sessions = {
        command[command.index("logs") + 1]
        for command in commands
        if "logs" in command
    }
    assert inspected_sessions == set(session_ids)


def test_terminal_provider_watchdog_ignores_unreadable_event_log_fallback(
    tmp_path, monkeypatch, capsys
) -> None:
    workspace = gate_workspace(tmp_path)
    commands: list[list[str]] = []

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        if "session" in argv:
            operation = argv[argv.index("session") + 1]
            if operation == "list":
                return json.dumps(
                    {
                        "sessions": [
                            {
                                "id": "spig-unreadable",
                                "session_name": "gc__run-operator-spig-unreadable",
                                "template": "fixture/gc.run-operator",
                                "state": "active",
                                "last_active": "2020-01-01T00:00:00Z",
                                "attached": False,
                            }
                        ]
                    }
                )
            if operation == "logs":
                raise AssertionError(
                    "session transcript must not be inspected without ownership evidence"
                )
        if "bd" in argv and argv[argv.index("bd") + 1] == "show":
            raise subprocess.CalledProcessError(1, argv)
        raise AssertionError(f"unexpected command: {argv!r}")

    def unreadable_event_log(_workspace):
        raise OSError("event log unavailable")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "list_beads_from_event_log",
        unreadable_event_log,
    )

    gascity_pack_inference_gate.recover_terminal_provider_sessions(
        "gc",
        workspace,
        env={},
        beads=[
            {
                "id": "fi-work",
                "status": "open",
                "metadata": {
                    "gc.root_bead_id": "fi-root",
                    "gc.root_store_ref": "rig:fixture",
                    "gc.routed_to": "fixture/gc.run-operator",
                },
            }
        ],
        root_id="fi-root",
        resets={},
        now=0.0,
    )

    assert "event log unavailable" in capsys.readouterr().err
    assert not any("logs" in command for command in commands)


def test_terminal_provider_watchdog_fails_preclaim_weekly_quota(
    tmp_path, monkeypatch
) -> None:
    workspace = gate_workspace(tmp_path)
    commands: list[list[str]] = []

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        if "session" in argv:
            operation = argv[argv.index("session") + 1]
            if operation == "list":
                return json.dumps(
                    {
                        "_cache_age_s": 0.25,
                        "sessions": [
                            {
                                "id": "spig-a5x",
                                "session_name": "gc__run-operator-spig-a5x",
                                "template": "fixture/gc.run-operator",
                                "state": "active",
                                "last_active": "2020-01-01T00:00:00Z",
                                "attached": False,
                            }
                        ],
                    }
                )
            if operation == "logs":
                return provider_log_snapshot(
                    provider_assistant_entry(WEEKLY_PROVIDER_QUOTA_ERROR, uuid="quota-error")
                )
        if "bd" in argv and argv[argv.index("bd") + 1] == "show":
            return json.dumps(
                [
                    {
                        "id": "spig-a5x",
                        "issue_type": "session",
                        "metadata": {
                            "provider": "claude",
                            "template": "fixture/gc.run-operator",
                            "gc.trigger_bead_id": "fi-work",
                            "gc.trigger_bead_store_ref": "rig:fixture",
                        },
                    }
                ]
            )
        raise AssertionError(f"unexpected command: {argv!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="spig-a5x.*provider_quota_exhausted",
    ):
        gascity_pack_inference_gate.recover_terminal_provider_sessions(
            "gc",
            workspace,
            env={},
            beads=[
                {
                    "id": "fi-work",
                    "status": "open",
                    "metadata": {
                        "gc.root_bead_id": "fi-root",
                        "gc.root_store_ref": "rig:fixture",
                        "gc.routed_to": "fixture/gc.run-operator",
                    },
                }
            ],
            root_id="fi-root",
            resets={},
            now=0.0,
        )

    session_bead_command = next(command for command in commands if "bd" in command)
    assert "--rig" not in session_bead_command
    assert not any("reset" in command for command in commands)


def test_terminal_provider_watchdog_falls_back_to_raw_claude_transcript(
    tmp_path, monkeypatch
) -> None:
    workspace, commands, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    transcript = write_raw_claude_transcript(
        workspace,
        conversation_id="8c52cefd-dbf8-47c1-ba1a-cc9f46380216",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp="2026-07-16T22:52:36.070Z",
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="spig-a4b.*provider_quota_exhausted",
    ):
        recover()

    assert "--temp" in str(transcript.parent)
    assert "_temp" in str(CLAUDE_FALLBACK_WORK_DIR)
    assert any("logs" in command for command in commands)
    assert not any("reset" in command for command in commands)


def test_terminal_provider_watchdog_rejects_raw_claude_transcript_for_other_cwd(
    tmp_path, monkeypatch
) -> None:
    workspace, commands, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    write_raw_claude_transcript(
        workspace,
        conversation_id="unrelated-conversation",
        cwd=Path("/home/runner/work/_temp/another-workflow/fixture/fi-other"),
        timestamp="2026-07-16T22:52:36.070Z",
    )

    recover()

    assert not any("reset" in command for command in commands)


def test_terminal_provider_watchdog_rejects_malformed_and_unreadable_raw_transcripts(
    tmp_path, monkeypatch
) -> None:
    workspace, commands, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    project_dir = raw_claude_project_dir(workspace)
    (project_dir / "malformed.jsonl").write_text("{not-json\n", encoding="utf-8")
    unreadable = project_dir / "unreadable.jsonl"
    unreadable.write_text("{}\n", encoding="utf-8")
    unreadable.chmod(0)

    recover()

    assert not any("reset" in command for command in commands)


def test_terminal_provider_watchdog_rejects_raw_transcript_older_than_session(
    tmp_path, monkeypatch
) -> None:
    workspace, commands, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    write_raw_claude_transcript(
        workspace,
        conversation_id="old-conversation",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp="2026-07-16T22:49:17.999Z",
    )

    recover()

    assert not any("reset" in command for command in commands)


def test_terminal_provider_watchdog_rejects_ambiguous_newest_raw_transcripts(
    tmp_path, monkeypatch
) -> None:
    workspace, commands, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    for conversation_id in ("newest-first", "newest-second"):
        write_raw_claude_transcript(
            workspace,
            conversation_id=conversation_id,
            cwd=CLAUDE_FALLBACK_WORK_DIR,
            timestamp="2026-07-16T22:52:36.070Z",
        )

    recover()

    assert not any("reset" in command for command in commands)


def test_terminal_provider_watchdog_leaves_raw_transient_429_nonfatal(
    tmp_path, monkeypatch
) -> None:
    workspace, commands, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    write_raw_claude_transcript(
        workspace,
        conversation_id="transient-rate-limit",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp="2026-07-16T22:52:36.070Z",
        text="API Error: Request rejected (429) · provider is temporarily rate limited",
    )

    recover()

    assert not any("reset" in command for command in commands)


@pytest.mark.parametrize(
    ("sibling_state", "sibling_closed"),
    (
        ("active", False),
        ("awake", False),
        ("start-pending", False),
        ("creating", False),
        ("draining", False),
        ("asleep", False),
        ("closed", True),
    ),
)
def test_raw_claude_safety_handles_same_work_dir_session_lifecycle(
    tmp_path, monkeypatch, sibling_state, sibling_closed
) -> None:
    workspace = gate_workspace(tmp_path)
    commands: list[list[str]] = []
    session_ids = ("spig-first", "spig-second")
    sessions = [
        {
            "id": session_id,
            "session_name": f"gc__run-operator-{session_id}",
            "template": "fixture/gc.run-operator",
            "state": "active" if index == 0 else sibling_state,
            "closed": False if index == 0 else sibling_closed,
            "last_active": "2020-01-01T00:00:00Z",
            "attached": False,
            "work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
        }
        for index, session_id in enumerate(session_ids)
    ]
    session_beads = {
        session_id: {
            "id": session_id,
            "issue_type": "session",
            "created_at": CLAUDE_FALLBACK_SESSION_STARTED_AT,
            "metadata": {
                "provider": "claude",
                "template": "fixture/gc.run-operator",
                "gc.trigger_bead_id": f"fi-work-{index}",
                "gc.trigger_bead_store_ref": "rig:fixture",
                "gc.work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
                "work_dir": str(CLAUDE_FALLBACK_WORK_DIR),
            },
        }
        for index, session_id in enumerate(session_ids, start=1)
    }
    beads = [
        {
            "id": f"fi-work-{index}",
            "status": "open",
            "metadata": {
                "gc.root_bead_id": "fi-root",
                "gc.root_store_ref": "rig:fixture",
                "gc.routed_to": "fixture/gc.run-operator",
            },
        }
        for index in range(1, 3)
    ]

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        if "session" in argv:
            operation = argv[argv.index("session") + 1]
            if operation == "list":
                return json.dumps({"_cache_age_s": 0.25, "sessions": sessions})
            if operation == "logs":
                raise subprocess.CalledProcessError(1, argv)
            if operation == "reset":
                return '{"status":"reset_requested"}\n'
        if "bd" in argv and argv[argv.index("bd") + 1] == "show":
            session_id = argv[argv.index("show") + 1]
            return json.dumps([session_beads[session_id]])
        raise AssertionError(f"unexpected command: {argv!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)
    write_raw_claude_transcript(
        workspace,
        conversation_id="shared-work-dir-quota",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp="2026-07-16T22:52:36.070Z",
    )

    def recover() -> None:
        gascity_pack_inference_gate.recover_terminal_provider_sessions(
            "gc",
            workspace,
            env={},
            beads=beads,
            root_id="fi-root",
            resets={},
            now=0.0,
        )

    if sibling_closed:
        with pytest.raises(
            gascity_pack_inference_gate.GateError,
            match="spig-first.*provider_quota_exhausted",
        ):
            recover()
    else:
        recover()

    assert not any("reset" in command for command in commands)


def test_raw_claude_safety_uses_active_dag_tip_not_last_appended_branch(
    tmp_path, monkeypatch
) -> None:
    workspace, commands, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    conversation_id = "forked-conversation"
    root = {
        "uuid": "root-prompt",
        "parentUuid": "",
        "type": "user",
        "timestamp": "2026-07-16T22:50:00.000Z",
        "cwd": str(CLAUDE_FALLBACK_WORK_DIR),
        "sessionId": conversation_id,
        "message": {"role": "user", "content": "continue"},
    }
    healthy_active_tip = raw_claude_entry(
        conversation_id=conversation_id,
        entry_id="healthy-active-tip",
        parent_id="root-prompt",
        timestamp="2026-07-16T22:52:00.000Z",
        text="Current work completed normally.",
        model="claude-sonnet",
    )
    abandoned_quota_tip = raw_claude_entry(
        conversation_id=conversation_id,
        entry_id="abandoned-quota-tip",
        parent_id="root-prompt",
        timestamp="2026-07-16T22:51:00.000Z",
        text=WEEKLY_PROVIDER_QUOTA_ERROR,
        model="<synthetic>",
    )
    write_raw_claude_entries(
        workspace,
        conversation_id=conversation_id,
        entries=[root, healthy_active_tip, abandoned_quota_tip],
    )

    recover()

    assert not any("reset" in command for command in commands)


def test_raw_claude_safety_reset_rejects_preexisting_different_path(
    tmp_path, monkeypatch
) -> None:
    workspace, _, _, recover = configure_claimed_raw_claude_watchdog(
        tmp_path,
        monkeypatch,
    )
    reset_boundary = datetime.now(timezone.utc)
    write_raw_claude_transcript(
        workspace,
        conversation_id="source-terminal",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp=(reset_boundary - timedelta(minutes=2)).isoformat(),
        text=TERMINAL_TOOL_USE_ERROR,
    )
    resets = {}
    cache = {}

    recover(resets=resets, now=0.0, cache=cache)
    write_raw_claude_transcript(
        workspace,
        conversation_id="preexisting-healthy",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp=(reset_boundary - timedelta(seconds=1)).isoformat(),
        text="Healthy conversation that already existed before reset.",
        model="claude-sonnet",
    )
    recover(resets=resets, now=1.0, cache=cache)

    assert resets["spig-a4b"].recovery_evidence == ""


def test_raw_claude_safety_reset_accepts_conversation_started_after_reset(
    tmp_path, monkeypatch
) -> None:
    workspace, _, _, recover = configure_claimed_raw_claude_watchdog(
        tmp_path,
        monkeypatch,
    )
    source_started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    write_raw_claude_transcript(
        workspace,
        conversation_id="source-terminal",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp=source_started_at.isoformat(),
        text=TERMINAL_TOOL_USE_ERROR,
    )
    resets = {}
    cache = {}

    recover(resets=resets, now=0.0, cache=cache)
    fresh = write_raw_claude_transcript(
        workspace,
        conversation_id="post-reset-healthy",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp=datetime.now(timezone.utc).isoformat(),
        text="Healthy progress produced after reset.",
        model="claude-sonnet",
    )
    recover(resets=resets, now=1.0, cache=cache)

    assert resets["spig-a4b"].recovery_evidence == (
        f"fresh provider transcript {fresh} at post-reset-healthy-tip"
    )


def test_raw_claude_safety_stale_session_cache_disables_reset_fallback(
    tmp_path, monkeypatch
) -> None:
    workspace, _, cache_age, recover = configure_claimed_raw_claude_watchdog(
        tmp_path,
        monkeypatch,
    )
    write_raw_claude_transcript(
        workspace,
        conversation_id="source-terminal",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp=(datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
        text=TERMINAL_TOOL_USE_ERROR,
    )
    resets = {}
    cache = {}

    recover(resets=resets, now=0.0, cache=cache)
    write_raw_claude_transcript(
        workspace,
        conversation_id="fresh-but-unproven",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp=datetime.now(timezone.utc).isoformat(),
        text="Healthy progress seen only through a stale session listing.",
        model="claude-sonnet",
    )
    cache_age[0] = gascity_pack_inference_gate.TERMINAL_PROVIDER_MAX_SESSION_CACHE_AGE + 1
    recover(resets=resets, now=1.0, cache=cache)

    assert resets["spig-a4b"].recovery_evidence == ""


def test_raw_claude_safety_persistent_cache_invalidates_when_file_becomes_unreadable(
    tmp_path,
) -> None:
    workspace = gate_workspace(tmp_path)
    transcript = write_raw_claude_transcript(
        workspace,
        conversation_id="cached-quota",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp="2026-07-16T22:52:36.070Z",
    )
    cache = {}
    initial = default_raw_claude_tip(workspace, cache=cache)
    assert initial is not None
    assert initial.fatal_error == "provider_quota_exhausted"

    transcript.chmod(0)
    try:
        assert default_raw_claude_tip(workspace, cache=cache) is None
    finally:
        transcript.chmod(0o600)


def test_raw_claude_safety_persistent_cache_invalidates_on_append(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    transcript = write_raw_claude_transcript(
        workspace,
        conversation_id="cached-conversation",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp="2026-07-16T22:52:00.000Z",
        text="Healthy initial response.",
        model="claude-sonnet",
    )
    cache = {}
    initial = default_raw_claude_tip(workspace, cache=cache)
    assert initial is not None
    assert initial.fatal_error == ""

    appended_quota = raw_claude_entry(
        conversation_id="cached-conversation",
        entry_id="appended-quota-tip",
        parent_id="cached-conversation-tip",
        timestamp="2026-07-16T22:53:00.000Z",
        text=WEEKLY_PROVIDER_QUOTA_ERROR,
        model="<synthetic>",
    )
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(appended_quota) + "\n")

    updated = default_raw_claude_tip(workspace, cache=cache)
    assert updated is not None
    assert updated.entry_id == "appended-quota-tip"
    assert updated.fatal_error == "provider_quota_exhausted"


def test_raw_claude_safety_torn_other_project_does_not_veto_valid_target(
    tmp_path, monkeypatch
) -> None:
    workspace, _, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    write_raw_claude_transcript(
        workspace,
        conversation_id="target-quota",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp="2026-07-16T22:52:00.000Z",
    )
    unrelated = write_raw_claude_transcript(
        workspace,
        conversation_id="unrelated-torn",
        cwd=Path("/home/runner/work/_temp/unrelated/fixture/fi-other"),
        timestamp="2026-07-16T22:53:00.000Z",
        project_slug="unrelated-project",
    )
    with unrelated.open("a", encoding="utf-8") as handle:
        handle.write('{"type":"assistant"')

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="spig-a4b.*provider_quota_exhausted",
    ):
        recover()


def test_raw_claude_safety_torn_newer_target_conversation_fails_closed(
    tmp_path, monkeypatch
) -> None:
    workspace, commands, recover = configure_raw_claude_fallback_watchdog(
        tmp_path,
        monkeypatch,
    )
    write_raw_claude_transcript(
        workspace,
        conversation_id="older-target-quota",
        cwd=CLAUDE_FALLBACK_WORK_DIR,
        timestamp="2026-07-16T22:52:00.000Z",
    )
    conversation_id = "newer-target-torn"
    prefix = {
        "uuid": "newer-target-root",
        "parentUuid": "",
        "type": "user",
        "timestamp": "2026-07-16T22:53:00.000Z",
        "cwd": str(CLAUDE_FALLBACK_WORK_DIR),
        "sessionId": conversation_id,
        "message": {"role": "user", "content": "continue"},
    }
    torn = raw_claude_project_dir(workspace) / f"{conversation_id}.jsonl"
    torn.write_text(
        json.dumps(prefix) + '\n{"type":"assistant"',
        encoding="utf-8",
    )

    recover()

    assert not any("reset" in command for command in commands)


@pytest.mark.parametrize(
    "case",
    (
        {"trigger_id": "fi-other-work", "root_id": "fi-other-root"},
        {"trigger_store": "rig:other"},
        {"trigger_status": "closed"},
        {"session_provider": "other"},
        {"session_template": "fixture/gc.other"},
        {"trigger_route": "fixture/gc.other"},
    ),
    ids=(
        "other-workflow",
        "other-store",
        "closed-trigger",
        "other-provider",
        "other-template",
        "other-route",
    ),
)
def test_terminal_provider_watchdog_ignores_unrelated_preclaim_weekly_quota(
    tmp_path, monkeypatch, case
) -> None:
    workspace = gate_workspace(tmp_path)
    commands: list[list[str]] = []
    session_template = case.get("session_template", "fixture/gc.run-operator")
    trigger_id = case.get("trigger_id", "fi-work")
    session_metadata = {
        "provider": case.get("session_provider", "claude"),
        "template": session_template,
        "gc.trigger_bead_id": trigger_id,
        "gc.trigger_bead_store_ref": case.get("trigger_store", "rig:fixture"),
    }
    beads = [
        {
            "id": trigger_id,
            "status": case.get("trigger_status", "open"),
            "metadata": {
                "gc.root_bead_id": case.get("root_id", "fi-root"),
                "gc.root_store_ref": "rig:fixture",
                "gc.routed_to": case.get("trigger_route", "fixture/gc.run-operator"),
            },
        }
    ]

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        if "session" in argv:
            operation = argv[argv.index("session") + 1]
            if operation == "list":
                return json.dumps(
                    {
                        "sessions": [
                            {
                                "id": "spig-unrelated",
                                "session_name": "gc__run-operator-spig-unrelated",
                                "template": "fixture/gc.run-operator",
                                "state": "active",
                                "last_active": "2020-01-01T00:00:00Z",
                                "attached": False,
                            }
                        ]
                    }
                )
            if operation == "logs":
                raise AssertionError("unrelated session transcript must not be inspected")
        if "bd" in argv and argv[argv.index("bd") + 1] == "show":
            return json.dumps(
                [
                    {
                        "id": "spig-unrelated",
                        "issue_type": "session",
                        "metadata": session_metadata,
                    }
                ]
            )
        raise AssertionError(f"unexpected command: {argv!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)

    gascity_pack_inference_gate.recover_terminal_provider_sessions(
        "gc",
        workspace,
        env={},
        beads=beads,
        root_id="fi-root",
        resets={},
        now=0.0,
    )

    assert any("bd" in command and "spig-unrelated" in command for command in commands)
    assert not any("logs" in command or "reset" in command for command in commands)


def exercise_terminal_provider_watchdog(
    tmp_path,
    monkeypatch,
    *,
    sessions: list[dict],
    beads: list[dict],
    logs: str,
    timeout: float = 1,
) -> tuple[gascity_pack_inference_gate.GateWorkspace, list[list[str]]]:
    workspace = gate_workspace(tmp_path)
    root = {"id": "fi-root", "status": "in_progress", "metadata": {}}
    commands: list[list[str]] = []
    clock = [0.0]

    monkeypatch.setattr(gascity_pack_inference_gate, "show_bead", lambda *args, **kwargs: root)
    monkeypatch.setattr(gascity_pack_inference_gate, "list_beads", lambda *args, **kwargs: beads)
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "collect_diagnostics",
        lambda *args, **kwargs: "diagnostics",
    )
    monkeypatch.setattr(gascity_pack_inference_gate.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        gascity_pack_inference_gate.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        if "session" in argv:
            operation = argv[argv.index("session") + 1]
            if operation == "list":
                return json.dumps({"sessions": sessions})
            if operation == "logs":
                return logs
            if operation == "reset":
                return '{"status":"reset_requested"}\n'
        if "bd" in argv and argv[argv.index("bd") + 1] == "show":
            session_id = argv[argv.index("show") + 1]
            return json.dumps([{"id": session_id, "metadata": {}}])
        raise AssertionError(f"unexpected command: {argv!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)

    with pytest.raises(gascity_pack_inference_gate.GateError, match="timed out"):
        gascity_pack_inference_gate.wait_for_workflow_pass(
            "gc",
            workspace,
            "fi-root",
            env={},
            timeout=timeout,
            poll_interval=1,
        )
    return workspace, commands


def test_wait_for_workflow_pass_resets_terminal_provider_error_observation_once(
    tmp_path, monkeypatch
) -> None:
    session_name = "gc__implementation-worker-gpig-2y5"
    workspace, commands = exercise_terminal_provider_watchdog(
        tmp_path,
        monkeypatch,
        sessions=[
            {
                "id": "gpig-2y5",
                "session_name": session_name,
                "state": "active",
                "last_active": "2020-01-01T00:00:00Z",
            }
        ],
        beads=[workflow_claim(session_name)],
        logs=provider_log_snapshot(
            provider_assistant_entry(TERMINAL_TOOL_USE_ERROR, uuid="provider-error-1")
        ),
        timeout=3,
    )

    reset_commands = [command for command in commands if "reset" in command]
    assert reset_commands == [
        [
            "gc",
            "--city",
            str(workspace.city_dir),
            "session",
            "reset",
            "gpig-2y5",
            "--json",
        ]
    ]


def test_wait_for_workflow_pass_leaves_benign_stale_active_session_untouched(
    tmp_path, monkeypatch
) -> None:
    session_name = "gc__implementation-worker-gpig-benign"
    _, commands = exercise_terminal_provider_watchdog(
        tmp_path,
        monkeypatch,
        sessions=[
            {
                "id": "gpig-benign",
                "session_name": session_name,
                "state": "active",
                "last_active": "2020-01-01T00:00:00Z",
            }
        ],
        beads=[workflow_claim(session_name)],
        logs=provider_log_snapshot(
            provider_assistant_entry(TERMINAL_TOOL_USE_ERROR, uuid="old-provider-error"),
            provider_assistant_entry(
                "Implementation is still running normally.",
                uuid="healthy-progress",
                model="kimi-k2.5",
            ),
        ),
    )

    assert any("logs" in command and "gpig-benign" in command for command in commands)
    assert not any("reset" in command for command in commands)


def test_wait_for_workflow_pass_does_not_reset_terminal_error_without_workflow_claim(
    tmp_path, monkeypatch
) -> None:
    _, commands = exercise_terminal_provider_watchdog(
        tmp_path,
        monkeypatch,
        sessions=[
            {
                "id": "gpig-unrelated",
                "session_name": "gc__implementation-worker-gpig-unrelated",
                "state": "active",
                "last_active": "2020-01-01T00:00:00Z",
            }
        ],
        beads=[],
        logs=provider_log_snapshot(
            provider_assistant_entry(TERMINAL_TOOL_USE_ERROR, uuid="unrelated-error")
        ),
    )

    assert not any("reset" in command for command in commands)


@pytest.mark.parametrize("claim_case", ("shared-template", "stale-session-name"))
def test_wait_for_workflow_pass_does_not_reset_for_sibling_session_claim(
    tmp_path, monkeypatch, claim_case
) -> None:
    session = {
        "id": "gpig-poisoned",
        "session_name": "gc__implementation-worker-gpig-poisoned",
        "template": "fixture/gc.implementation-worker",
        "state": "active",
        "last_active": "2020-01-01T00:00:00Z",
    }
    claim = workflow_claim(
        "fixture/gc.implementation-worker"
        if claim_case == "shared-template"
        else "gc__implementation-worker-gpig-sibling"
    )
    if claim_case == "stale-session-name":
        claim["metadata"]["gc.session_name"] = session["session_name"]

    _, commands = exercise_terminal_provider_watchdog(
        tmp_path,
        monkeypatch,
        sessions=[session],
        beads=[claim],
        logs=provider_log_snapshot(
            provider_assistant_entry(TERMINAL_TOOL_USE_ERROR, uuid="poisoned-error")
        ),
    )

    assert not any("reset" in command for command in commands)


def test_terminal_provider_recovery_fails_when_fresh_reset_does_not_recover(
    tmp_path, monkeypatch
) -> None:
    workspace = gate_workspace(tmp_path)
    commands: list[list[str]] = []

    def run_checked(command, **kwargs):
        argv = list(command)
        commands.append(argv)
        operation = argv[argv.index("session") + 1]
        if operation == "list":
            return json.dumps({"sessions": []})
        if operation == "logs":
            return provider_log_snapshot(
                provider_assistant_entry(TERMINAL_TOOL_USE_ERROR, uuid="source-error"),
                path="/tmp/source-provider-session.jsonl",
            )
        raise AssertionError(f"unexpected command: {argv!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)
    resets = {
        "gpig-2y5": gascity_pack_inference_gate.TerminalProviderReset(
            requested_at=0.0,
            source_transcript_path="/tmp/source-provider-session.jsonl",
            claim_ids=("fi-work",),
            session_identities=("gc__implementation-worker-gpig-2y5",),
        )
    }

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="gpig-2y5.*did not produce fresh provider progress.*state=missing",
    ):
        gascity_pack_inference_gate.recover_terminal_provider_sessions(
            "gc",
            workspace,
            env={},
            beads=[workflow_claim("gc__implementation-worker-gpig-2y5")],
            root_id="fi-root",
            resets=resets,
            now=gascity_pack_inference_gate.TERMINAL_PROVIDER_RECOVERY_TIMEOUT,
        )

    assert not any("reset" in command for command in commands)


def test_terminal_provider_recovery_accepts_fresh_provider_transcript(
    tmp_path, monkeypatch
) -> None:
    workspace = gate_workspace(tmp_path)

    def run_checked(command, **kwargs):
        operation = list(command)[list(command).index("session") + 1]
        if operation == "list":
            return json.dumps({"sessions": []})
        if operation == "logs":
            return provider_log_snapshot(
                provider_assistant_entry(
                    "I resumed the claimed implementation work.",
                    uuid="fresh-progress",
                    model="kimi-k2.5",
                ),
                path="/tmp/fresh-provider-session.jsonl",
            )
        raise AssertionError(f"unexpected command: {list(command)!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)
    reset = gascity_pack_inference_gate.TerminalProviderReset(
        requested_at=0.0,
        source_transcript_path="/tmp/source-provider-session.jsonl",
        claim_ids=("fi-work",),
        session_identities=("gc__implementation-worker-gpig-2y5",),
    )

    gascity_pack_inference_gate.recover_terminal_provider_sessions(
        "gc",
        workspace,
        env={},
        beads=[workflow_claim("gc__implementation-worker-gpig-2y5")],
        root_id="fi-root",
        resets={"gpig-2y5": reset},
        now=gascity_pack_inference_gate.TERMINAL_PROVIDER_RECOVERY_TIMEOUT,
    )

    assert reset.recovery_evidence == (
        "fresh provider transcript /tmp/fresh-provider-session.jsonl at fresh-progress"
    )


def test_terminal_provider_recovery_rejects_same_error_in_fresh_conversation(
    tmp_path, monkeypatch
) -> None:
    workspace = gate_workspace(tmp_path)

    def run_checked(command, **kwargs):
        operation = list(command)[list(command).index("session") + 1]
        if operation == "list":
            return json.dumps({"sessions": []})
        if operation == "logs":
            return provider_log_snapshot(
                provider_assistant_entry(TERMINAL_TOOL_USE_ERROR, uuid="fresh-error"),
                path="/tmp/fresh-provider-session.jsonl",
            )
        raise AssertionError(f"unexpected command: {list(command)!r}")

    monkeypatch.setattr(gascity_pack_inference_gate, "run_checked", run_checked)
    reset = gascity_pack_inference_gate.TerminalProviderReset(
        requested_at=0.0,
        source_transcript_path="/tmp/source-provider-session.jsonl",
        claim_ids=("fi-work",),
        session_identities=("gc__implementation-worker-gpig-2y5",),
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="gpig-2y5.*same terminal provider error.*fresh conversation",
    ):
        gascity_pack_inference_gate.recover_terminal_provider_sessions(
            "gc",
            workspace,
            env={},
            beads=[workflow_claim("gc__implementation-worker-gpig-2y5")],
            root_id="fi-root",
            resets={"gpig-2y5": reset},
            now=1.0,
        )


def test_reconcile_terminal_provider_resets_fails_fresh_weekly_quota_immediately(
    tmp_path, monkeypatch
) -> None:
    workspace = gate_workspace(tmp_path)
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "session_log_tip",
        lambda *args, **kwargs: gascity_pack_inference_gate.ProviderLogTip(
            transcript_path="/tmp/fresh-provider-session.jsonl",
            entry_id="fresh-quota-error",
            synthetic=True,
            terminal_error=False,
            fatal_error="provider_quota_exhausted",
        ),
    )
    reset = gascity_pack_inference_gate.TerminalProviderReset(
        requested_at=0.0,
        source_transcript_path="/tmp/source-provider-session.jsonl",
        claim_ids=("fi-work",),
        session_identities=("gc__implementation-worker-gpig-2y5",),
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="gpig-2y5.*provider_quota_exhausted",
    ):
        gascity_pack_inference_gate.reconcile_terminal_provider_resets(
            "gc",
            workspace,
            env={},
            beads=[workflow_claim("gc__implementation-worker-gpig-2y5")],
            workflow_roots={"fi-root"},
            sessions_by_id={"gpig-2y5": {"state": "active"}},
            resets={"gpig-2y5": reset},
            now=1.0,
        )


def test_workflow_lineage_root_ids_includes_wired_drain_item_root() -> None:
    drain = {
        "id": "fi-drain",
        "status": "open",
        "metadata": {
            "gc.kind": "drain",
            "gc.root_bead_id": "fi-root",
            "gc.drain_manifest.v1": json.dumps(
                {
                    "version": 1,
                    "rows": [
                        {
                            "item_root_id": "fi-nested",
                            "status": "wired",
                        }
                    ],
                }
            ),
        },
    }

    assert gascity_pack_inference_gate.workflow_lineage_root_ids(
        [drain, workflow_claim("worker", root="fi-nested")],
        "fi-root",
    ) == {"fi-root", "fi-nested"}


def complete_nested_workflow_lineage() -> list[dict]:
    return [
        closed_bead("fi-root-finalize", root="fi-root", kind="workflow-finalize"),
        lineage_drain("fi-root-drain", "fi-root", "fi-nested"),
        closed_bead("fi-nested", kind="workflow"),
        closed_bead("fi-nested-control", root="fi-nested", kind="ralph"),
        closed_bead("fi-nested-finalize", root="fi-nested", kind="workflow-finalize"),
    ]


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        ("missing-root", r"fi-nested.*exactly one"),
        ("duplicate-root", r"fi-nested.*exactly one"),
        ("open-root", r"fi-nested.*closed/pass"),
        ("failed-root", r"fi-nested.*closed/pass"),
        ("stale-root", r"fi-nested.*stale failure"),
        ("blocked-status-root", r"fi-nested.*stale failure.*gc.build.status"),
        ("missing-finalizer", r"fi-nested.*workflow-finalize"),
        ("open-control", r"fi-nested-control.*closed/pass"),
        ("unset-control-outcome", r"fi-nested-control.*closed/pass"),
        ("failed-control", r"fi-nested-control.*closed/pass"),
        ("stale-control", r"fi-nested-control.*stale failure"),
    ),
)
def test_validate_workflow_lineage_rejects_incomplete_nested_state(case, expected) -> None:
    beads = complete_nested_workflow_lineage()
    nested = next(bead for bead in beads if bead["id"] == "fi-nested")
    control = next(bead for bead in beads if bead["id"] == "fi-nested-control")
    if case == "missing-root":
        beads.remove(nested)
    elif case == "duplicate-root":
        beads.append(dict(nested))
    elif case == "open-root":
        nested["status"] = "open"
    elif case == "failed-root":
        nested["metadata"]["gc.outcome"] = "fail"
    elif case == "stale-root":
        nested["metadata"]["gc.failure_class"] = "old failure"
    elif case == "blocked-status-root":
        nested["metadata"]["gc.build.status"] = "blocked"
    elif case == "missing-finalizer":
        beads[:] = [bead for bead in beads if bead["id"] != "fi-nested-finalize"]
    elif case == "open-control":
        control["status"] = "open"
    elif case == "unset-control-outcome":
        del control["metadata"]["gc.outcome"]
    elif case == "failed-control":
        control["metadata"]["gc.outcome"] = "fail"
    else:
        control["metadata"]["gc.blocked_reason"] = "old blocker"

    with pytest.raises(gascity_pack_inference_gate.GateError, match=expected):
        gascity_pack_inference_gate.validate_workflow_lineage(beads, "fi-root")


def test_validate_workflow_lineage_ignores_unrelated_incomplete_workflow() -> None:
    beads = complete_nested_workflow_lineage()
    beads.extend(
        [
            closed_bead("fi-unrelated", kind="workflow", outcome="fail"),
            closed_bead("fi-unrelated-control", root="fi-unrelated", kind="ralph", outcome="fail"),
        ]
    )

    gascity_pack_inference_gate.validate_workflow_lineage(beads, "fi-root")


@pytest.mark.parametrize(
    "row",
    (42, {"member_id": "fi-member"}),
    ids=("non-mapping", "missing-workflow-root"),
)
def test_validate_workflow_lineage_rejects_malformed_manifest_rows(row) -> None:
    beads = complete_nested_workflow_lineage()
    drain = next(bead for bead in beads if bead["id"] == "fi-root-drain")
    drain["metadata"]["gc.drain_manifest.v1"] = json.dumps({"version": 1, "rows": [row]})

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"fi-root-drain.*manifest row 0.*item_root_id.*outcome_bead_id",
    ):
        gascity_pack_inference_gate.validate_workflow_lineage(beads, "fi-root")


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        ("missing-manifest", r"fi-root-drain.*manifest"),
        ("missing-count", r"fi-root-drain.*drain_count"),
        ("invalid-count", r"fi-root-drain.*drain_count"),
        ("count-mismatch", r"fi-root-drain.*drain_count.*manifest"),
        ("failed-state", r"fi-root-drain.*drain_state=succeeded"),
        ("failed-row", r"fi-root-drain.*manifest row 0.*status=succeeded"),
        ("failed-outcome", r"fi-root-drain.*manifest row 0.*outcome_kind=pass"),
    ),
)
def test_validate_workflow_lineage_rejects_incomplete_drain_evidence(case, expected) -> None:
    beads = complete_nested_workflow_lineage()
    drain = next(bead for bead in beads if bead["id"] == "fi-root-drain")
    manifest = json.loads(drain["metadata"]["gc.drain_manifest.v1"])
    if case == "missing-manifest":
        del drain["metadata"]["gc.drain_manifest.v1"]
    elif case == "missing-count":
        del drain["metadata"]["gc.drain_count"]
    elif case == "invalid-count":
        drain["metadata"]["gc.drain_count"] = "not-a-count"
    elif case == "count-mismatch":
        drain["metadata"]["gc.drain_count"] = "2"
    elif case == "failed-state":
        drain["metadata"]["gc.drain_state"] = "failed"
    elif case == "failed-row":
        manifest["rows"][0]["status"] = "failed"
    else:
        manifest["rows"][0]["outcome_kind"] = "fail"
    if case not in ("missing-manifest", "failed-state"):
        drain["metadata"]["gc.drain_manifest.v1"] = json.dumps(manifest)

    with pytest.raises(gascity_pack_inference_gate.GateError, match=expected):
        gascity_pack_inference_gate.validate_workflow_lineage(beads, "fi-root")


def test_wait_for_workflow_pass_waits_for_non_attempt_finalizer(tmp_path, monkeypatch) -> None:
    workspace = gate_workspace(tmp_path)
    root = {"id": "fi-root", "status": "closed", "metadata": {"gc.outcome": "pass"}}
    snapshots = [
        [
            {
                "id": "fi-finalize-attempt",
                "status": "closed",
                "metadata": {
                    "gc.root_bead_id": "fi-root",
                    "gc.kind": "workflow-finalize",
                    "gc.attempt": "1",
                    "gc.outcome": "fail",
                },
            }
        ],
        [
            {
                "id": "fi-finalize",
                "status": "open",
                "metadata": {
                    "gc.root_bead_id": "fi-root",
                    "gc.kind": "workflow-finalize",
                },
            }
        ],
        [
            {
                "id": "fi-finalize",
                "status": "closed",
                "metadata": {
                    "gc.root_bead_id": "fi-root",
                    "gc.kind": "workflow-finalize",
                    "gc.outcome": "pass",
                },
            }
        ],
    ]
    observed: list[list[dict]] = []

    monkeypatch.setattr(gascity_pack_inference_gate, "show_bead", lambda *args, **kwargs: root)

    def list_beads(*args, **kwargs):
        snapshot = snapshots[min(len(observed), len(snapshots) - 1)]
        observed.append(snapshot)
        return snapshot

    monkeypatch.setattr(gascity_pack_inference_gate, "list_beads", list_beads)

    bead = gascity_pack_inference_gate.wait_for_workflow_pass(
        "gc",
        workspace,
        "fi-root",
        env={},
        timeout=5,
        poll_interval=0,
    )

    assert bead == root
    assert len(observed) == 3


def test_wait_for_workflow_pass_rejects_failed_finalizer(tmp_path, monkeypatch) -> None:
    workspace = gate_workspace(tmp_path)
    root = {"id": "fi-root", "status": "closed", "metadata": {"gc.outcome": "pass"}}
    finalizer = {
        "id": "fi-finalize",
        "title": "Finalize workflow",
        "status": "closed",
        "metadata": {
            "gc.root_bead_id": "fi-root",
            "gc.kind": "workflow-finalize",
            "gc.outcome": "fail",
        },
    }
    monkeypatch.setattr(gascity_pack_inference_gate, "show_bead", lambda *args, **kwargs: root)
    monkeypatch.setattr(gascity_pack_inference_gate, "list_beads", lambda *args, **kwargs: [finalizer])
    monkeypatch.setattr(gascity_pack_inference_gate, "collect_diagnostics", lambda *args, **kwargs: "diagnostics")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="logical workflow control failed.*fi-finalize"):
        gascity_pack_inference_gate.wait_for_workflow_pass(
            "gc",
            workspace,
            "fi-root",
            env={},
            timeout=5,
            poll_interval=0,
        )


def test_wait_for_workflow_pass_rejects_truthful_blocked_build(tmp_path, monkeypatch) -> None:
    workspace = gate_workspace(tmp_path)
    root = {
        "id": "fi-root",
        "status": "closed",
        "metadata": {
            "gc.outcome": "fail",
            "gc.build.status": "blocked",
            "gc.build.finalize_status": "failed",
            "gc.build.finalize_outcome": "failure",
        },
    }
    monkeypatch.setattr(gascity_pack_inference_gate, "show_bead", lambda *args, **kwargs: root)
    monkeypatch.setattr(gascity_pack_inference_gate, "list_beads", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        gascity_pack_inference_gate,
        "collect_diagnostics",
        lambda *args, **kwargs: "diagnostics",
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"closed with gc\.outcome='fail'.*want 'pass'",
    ):
        gascity_pack_inference_gate.wait_for_workflow_pass(
            "gc",
            workspace,
            "fi-root",
            env={},
            timeout=5,
            poll_interval=0,
        )


@pytest.mark.parametrize(
    ("marker", "value"),
    (
        ("gc.blocked_reason", "stale failure state"),
        ("gc.failure_class", "stale failure state"),
        ("gc.build.status", "blocked"),
        ("gc.build.status", "ready"),
        ("gc.build.finalize_status", "failed"),
        ("gc.build.finalize_outcome", "failure"),
        ("gc.build.repair_status", "blocked"),
        ("gc.build.repair_status", "repairable"),
        ("gc.build.repair_status", "exhausted"),
        ("gc.restart.entrypoint", "build-from-review"),
        ("gc.restart.reason", "review_changes_required"),
    ),
)
def test_wait_for_workflow_pass_rejects_stale_root_failure_marker(
    tmp_path, monkeypatch, marker: str, value: str
) -> None:
    workspace = gate_workspace(tmp_path)
    root = {
        "id": "fi-root",
        "status": "closed",
        "metadata": {"gc.outcome": "pass", marker: value},
    }
    finalizer = {
        "id": "fi-finalize",
        "status": "closed",
        "metadata": {
            "gc.root_bead_id": "fi-root",
            "gc.kind": "workflow-finalize",
            "gc.outcome": "pass",
        },
    }
    monkeypatch.setattr(gascity_pack_inference_gate, "show_bead", lambda *args, **kwargs: root)
    monkeypatch.setattr(gascity_pack_inference_gate, "list_beads", lambda *args, **kwargs: [finalizer])
    monkeypatch.setattr(gascity_pack_inference_gate, "collect_diagnostics", lambda *args, **kwargs: "diagnostics")

    with pytest.raises(gascity_pack_inference_gate.GateError, match=marker):
        gascity_pack_inference_gate.wait_for_workflow_pass(
            "gc",
            workspace,
            "fi-root",
            env={},
            timeout=5,
            poll_interval=0,
        )


def test_validate_review_report_requires_blocking_base_gascity_report(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        review_artifact_traced_to_subject(subject_path, status="changes_required"),
        encoding="utf-8",
    )

    gascity_pack_inference_gate.validate_review_report(
        {"metadata": {"gc.var.report_path": str(report_path)}},
        workspace,
        env={},
        pack_spec=gascity_pack_inference_gate.PACK_SPECS["gascity"],
    )


def test_validate_review_report_rejects_stale_additional_absolute_upstream(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    stale_path = (workspace.rig_dir / "stale-review-input.md").resolve()
    stale_path.write_text("original review input\n", encoding="utf-8")
    stale_digest = hashlib.sha256(stale_path.read_bytes()).hexdigest()
    stale_path.write_text("changed review input\n", encoding="utf-8")
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = review_artifact_traced_to_subject(subject_path, status="changes_required").replace(
        "  coverage:\n",
        f"    - path: {stale_path}\n      hash: sha256:{stale_digest}\n  coverage:\n",
        1,
    )
    report_path.write_text(report, encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="valid expected review artifact"):
        gascity_pack_inference_gate.validate_review_report(
            {"metadata": {"gc.var.report_path": str(report_path)}},
            workspace,
            env={},
            pack_spec=gascity_pack_inference_gate.PACK_SPECS["gascity"],
        )


def test_validate_review_report_accepts_exact_methodology_adapter_report(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    internal_path = (workspace.rig_dir / ".gc" / "internal" / "review-report.md").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    internal_path.parent.mkdir(parents=True)
    report = review_artifact_traced_to_subject(subject_path, status="approved")
    report_path.write_text(report, encoding="utf-8")
    internal_path.write_text(report, encoding="utf-8")
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["superpowers"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    gascity_pack_inference_gate.validate_review_report(
        {
            "metadata": {
                "gc.var.report_path": str(report_path),
                "gc.build.code_review_report_path": str(internal_path),
                "gc.build.review_subject_path": str(subject_path),
            }
        },
        workspace,
        env={},
        pack_spec=pack_spec,
    )


def test_validate_review_report_rejects_internal_alias_to_adapter(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        review_artifact_traced_to_subject(subject_path, status="changes_required"),
        encoding="utf-8",
    )
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["compound-engineering"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="must be distinct"):
        gascity_pack_inference_gate.validate_review_report(
            {
                "metadata": {
                    "gc.var.report_path": str(report_path),
                    "gc.build.code_review_report_path": str(report_path),
                    "gc.build.review_subject_path": str(subject_path),
                }
            },
            workspace,
            env={},
            pack_spec=pack_spec,
        )


def test_validate_review_report_rejects_internal_hardlink_to_adapter(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    internal_path = (workspace.rig_dir / ".gc" / "internal" / "review-report.md").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    internal_path.parent.mkdir(parents=True)
    report_path.write_text(
        review_artifact_traced_to_subject(subject_path, status="changes_required"),
        encoding="utf-8",
    )
    os.link(report_path, internal_path)
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["compound-engineering"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="must be distinct"):
        gascity_pack_inference_gate.validate_review_report(
            {
                "metadata": {
                    "gc.var.report_path": str(report_path),
                    "gc.build.code_review_report_path": str(internal_path),
                    "gc.build.review_subject_path": str(subject_path),
                }
            },
            workspace,
            env={},
            pack_spec=pack_spec,
        )


def test_validate_review_report_rejects_internal_path_outside_rig(tmp_path) -> None:
    gate_root = tmp_path / "gate"
    gate_root.mkdir()
    workspace = gate_workspace(gate_root)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    internal_path = (tmp_path / "outside" / "review-report.md").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    internal_path.parent.mkdir(parents=True)
    report = review_artifact_traced_to_subject(subject_path, status="changes_required")
    report_path.write_text(report, encoding="utf-8")
    internal_path.write_text(report, encoding="utf-8")
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["gstack"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="inside the nightly rig"):
        gascity_pack_inference_gate.validate_review_report(
            {
                "metadata": {
                    "gc.var.report_path": str(report_path),
                    "gc.build.code_review_report_path": str(internal_path),
                    "gc.build.review_subject_path": str(subject_path),
                }
            },
            workspace,
            env={},
            pack_spec=pack_spec,
        )


def test_require_canonical_review_subject_trace_rejects_relative_path(tmp_path) -> None:
    subject_path = tmp_path / "review-subject.diff"
    subject_path.write_text("diff --git a/a.py b/a.py\n", encoding="utf-8")
    report_path = tmp_path / "review-report.md"
    report = review_artifact_traced_to_subject(
        subject_path.resolve(), status="changes_required"
    ).replace(
        f"    - path: {subject_path.resolve()}\n",
        f"    - path: {subject_path.name}\n",
        1,
    )
    report_path.write_text(report, encoding="utf-8")

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="canonical review subject digest",
    ):
        gascity_pack_inference_gate.require_canonical_review_subject_trace(
            report_path, subject_path.resolve()
        )


def test_validate_review_report_rejects_invalid_internal_methodology_report(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    internal_path = (workspace.rig_dir / ".gc" / "internal" / "review-report.md").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    internal_path.parent.mkdir(parents=True)
    report_path.write_text(
        review_artifact_traced_to_subject(subject_path, status="changes_required"),
        encoding="utf-8",
    )
    internal_path.write_text("# Freeform internal review\n", encoding="utf-8")
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["compound-engineering"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="internal review report"):
        gascity_pack_inference_gate.validate_review_report(
            {
                "metadata": {
                    "gc.var.report_path": str(report_path),
                    "gc.build.code_review_report_path": str(internal_path),
                    "gc.build.review_subject_path": str(subject_path),
                }
            },
            workspace,
            env={},
            pack_spec=pack_spec,
        )


def test_validate_review_report_rejects_adapter_that_differs_from_internal_report(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    internal_path = (workspace.rig_dir / ".gc" / "internal" / "review-report.md").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    internal_path.parent.mkdir(parents=True)
    report = review_artifact_traced_to_subject(subject_path, status="changes_required")
    internal_path.write_text(report, encoding="utf-8")
    report_path.write_text(report + "\nAdapter-only rewrite.\n", encoding="utf-8")
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["gstack"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="byte-identical"):
        gascity_pack_inference_gate.validate_review_report(
            {
                "metadata": {
                    "gc.var.report_path": str(report_path),
                    "gc.build.code_review_report_path": str(internal_path),
                    "gc.build.review_subject_path": str(subject_path),
                }
            },
            workspace,
            env={},
            pack_spec=pack_spec,
        )


def test_validate_review_report_rejects_fake_canonical_subject_hash(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    subject_path = gascity_pack_inference_gate.write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    internal_path = (workspace.rig_dir / ".gc" / "internal" / "review-report.md").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    internal_path.parent.mkdir(parents=True)
    report = review_artifact_traced_to_subject(
        subject_path,
        status="changes_required",
        hash_value="literal:not-the-subject-digest",
    )
    report_path.write_text(report, encoding="utf-8")
    internal_path.write_text(report, encoding="utf-8")
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["bmad"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="canonical review subject digest"):
        gascity_pack_inference_gate.validate_review_report(
            {
                "metadata": {
                    "gc.var.report_path": str(report_path),
                    "gc.build.code_review_report_path": str(internal_path),
                    "gc.build.review_subject_path": str(subject_path),
                }
            },
            workspace,
            env={},
            pack_spec=pack_spec,
        )


def test_validate_review_report_rejects_relative_root_report_path(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    work_dir = workspace.rig_dir / "fi-3ph-write-review-report"
    report_path = work_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH
    report_path.parent.mkdir(parents=True)
    report_path.write_text(valid_review_artifact(status="changes_required"), encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="gc.var.report_path.*absolute"):
        gascity_pack_inference_gate.validate_review_report(
            {
                "metadata": {
                    "gc.work_dir": str(work_dir),
                    "gc.var.report_path": str(gascity_pack_inference_gate.REVIEW_REPORT_PATH),
                }
            },
            workspace,
            env={},
            pack_spec=gascity_pack_inference_gate.PACK_SPECS["gascity"],
        )


def test_validate_review_report_rejects_root_path_different_from_adapter_request(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    internal_path = (workspace.rig_dir / ".gc" / "internal" / "review-report.md").resolve()
    internal_path.parent.mkdir(parents=True)
    internal_path.write_text(valid_review_artifact(status="changes_required"), encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="does not match requested adapter report"):
        gascity_pack_inference_gate.validate_review_report(
            {"metadata": {"gc.var.report_path": str(internal_path)}},
            workspace,
            env={},
            pack_spec=gascity_pack_inference_gate.PACK_SPECS["gascity"],
        )


def test_validate_review_report_rejects_internal_metadata_report(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    requested_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    internal_path = workspace.rig_dir / ".gc" / "inference-gate" / "artifacts" / "implementation-review.md"
    internal_path.parent.mkdir(parents=True)
    internal_path.write_text(valid_review_artifact(status="approved"), encoding="utf-8")
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["superpowers"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="requested review report.*missing"):
        gascity_pack_inference_gate.validate_review_report(
            {
                "metadata": {
                    "gc.var.report_path": str(requested_path),
                    "gc.build.code_review_report_path": str(internal_path),
                }
            },
            workspace,
            env={},
            pack_spec=pack_spec,
        )


def test_validate_review_report_rejects_methodology_fallback(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    requested_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    fallback_path = workspace.rig_dir / ".gc" / "inference-gate" / "artifacts" / "review-fix-summary.md"
    fallback_path.parent.mkdir(parents=True)
    fallback_path.write_text(valid_review_artifact(status="approved"), encoding="utf-8")
    pack_spec = replace(
        gascity_pack_inference_gate.PACK_SPECS["superpowers"],
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="requested review report.*missing"):
        gascity_pack_inference_gate.validate_review_report(
            {"metadata": {"gc.var.report_path": str(requested_path)}},
            workspace,
            env={},
            pack_spec=pack_spec,
        )


def test_validate_review_report_rejects_approved_base_gascity_report(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    report_path = (workspace.rig_dir / gascity_pack_inference_gate.REVIEW_REPORT_PATH).resolve()
    report_path.parent.mkdir(parents=True)
    report_path.write_text(valid_review_artifact(status="approved"), encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="valid expected review artifact"):
        gascity_pack_inference_gate.validate_review_report(
            {"metadata": {"gc.var.report_path": str(report_path)}},
            workspace,
            env={},
            pack_spec=gascity_pack_inference_gate.PACK_SPECS["gascity"],
        )


def test_expand_gate_selection_supports_build_basic_and_all() -> None:
    assert gascity_pack_inference_gate.expand_gate_selection("review") == ["review"]
    assert gascity_pack_inference_gate.expand_gate_selection("build") == ["build-basic"]
    assert gascity_pack_inference_gate.expand_gate_selection("build-basic") == ["build-basic"]
    assert gascity_pack_inference_gate.expand_gate_selection("all") == ["review", "build-basic"]


def test_expand_gate_selection_is_pack_specific() -> None:
    superpowers = gascity_pack_inference_gate.PACK_SPECS["superpowers"]
    gastown = gascity_pack_inference_gate.PACK_SPECS["gastown"]

    assert gascity_pack_inference_gate.expand_gate_selection("all", superpowers) == ["review", "build"]
    assert gascity_pack_inference_gate.expand_gate_selection("build", superpowers) == ["build"]
    with pytest.raises(ValueError, match="build-basic"):
        gascity_pack_inference_gate.expand_gate_selection("build-basic", superpowers)

    assert gascity_pack_inference_gate.expand_gate_selection("all", gastown) == ["gastown-orchestration"]
    with pytest.raises(ValueError, match="review"):
        gascity_pack_inference_gate.expand_gate_selection("review", gastown)


def test_expand_pack_selection_supports_supported_pack_groups() -> None:
    assert gascity_pack_inference_gate.expand_pack_selection("methodology") == list(
        gascity_pack_inference_gate.METHODOLOGY_PACKS
    )
    assert gascity_pack_inference_gate.expand_pack_selection("all-supported") == list(
        gascity_pack_inference_gate.PACK_SPECS.keys()
    )


def test_pack_specs_cover_supported_formula_entrypoints() -> None:
    for pack_name in gascity_pack_inference_gate.METHODOLOGY_PACKS:
        spec = gascity_pack_inference_gate.PACK_SPECS[pack_name]
        assert (spec.source / "pack.toml").is_file()
        assert spec.review_formula
        assert spec.build_formula
        assert (spec.source / "formulas" / f"{spec.review_formula}.formula.toml").is_file()
        assert (spec.source / "formulas" / f"{spec.build_formula}.formula.toml").is_file()

    gastown = gascity_pack_inference_gate.PACK_SPECS["gastown"]
    assert gastown.gastown is True
    for formula in gastown.setup_formulas:
        assert (gastown.source / "formulas" / f"{formula}.toml").is_file()


def test_supported_step_formulas_do_not_combine_expand_and_check() -> None:
    formula_roots = [
        gascity_pack_inference_gate.REPO_ROOT / pack_name / "formulas"
        for pack_name in (
            "gascity",
            *gascity_pack_inference_gate.METHODOLOGY_PACKS,
        )
    ]
    offenders: list[str] = []
    for formula_root in formula_roots:
        for path in sorted(formula_root.glob("*.toml")):
            text = path.read_text(encoding="utf-8")
            for block in re.split(r"(?m)^\[\[steps\]\]\s*$", text)[1:]:
                step_id_match = re.search(r'(?m)^id\s*=\s*"([^"]+)"', block)
                step_id = step_id_match.group(1) if step_id_match else "<unknown>"
                if re.search(r"(?m)^expand\s*=", block) and re.search(r"(?m)^\[steps\.check\]\s*$", block):
                    offenders.append(f"{path.relative_to(gascity_pack_inference_gate.REPO_ROOT)}:{step_id}")

    assert offenders == []


def test_validate_required_routes_accepts_metadata_and_prefixed_assignees() -> None:
    beads = [
        {"metadata": {"gc.run_target": "superpowers.brainstorming"}},
        {"assignee": "fixture/superpowers.implementer"},
        {"metadata": {"custom.run_target": ["gstack.qa-lead"]}},
        {"metadata": {"gc.execution_routed_to": "fixture/gc.implementation-reviewer"}},
    ]

    gascity_pack_inference_gate.validate_required_routes(
        beads,
        [
            "superpowers.brainstorming",
            "superpowers.implementer",
            "gstack.qa-lead",
            "gc.implementation-reviewer",
        ],
        context="route test",
    )


def test_validate_required_routes_rejects_missing_expected_agent() -> None:
    with pytest.raises(gascity_pack_inference_gate.GateError, match="missing.agent"):
        gascity_pack_inference_gate.validate_required_routes(
            [{"metadata": {"gc.run_target": "superpowers.brainstorming"}}],
            ["missing.agent"],
            context="route test",
        )


def test_gastown_session_matching_accepts_bound_and_unbound_identities() -> None:
    sessions = [
        {"name": "mayor"},
        {"agent_id": "gastown.deacon"},
        {"session": "boot"},
        {"agent": "fixture/gastown.witness"},
    ]

    assert gascity_pack_inference_gate.missing_session_agents(
        sessions,
        gascity_pack_inference_gate.GASTOWN_ALWAYS_ON_AGENTS,
    ) == []
    assert gascity_pack_inference_gate.missing_session_agents(sessions, ["refinery"]) == ["refinery"]


def test_gastown_review_assignment_is_review_only() -> None:
    description = gascity_pack_inference_gate.gastown_review_assignment_description()

    assert "Do not execute the" in description
    assert "the subject of the review" in description


def test_require_gastown_review_report_checks_structured_notes() -> None:
    gascity_pack_inference_gate.require_gastown_review_report(
        {
            "notes": """\
## Summary
The review leg completed.

## Findings
Refinery is on demand and should not be required as an active startup session.

## Recommendation
Check its configured formula and named-session surface instead.
"""
        }
    )


def test_validate_gastown_orchestration_contract_accepts_current_pack() -> None:
    gascity_pack_inference_gate.validate_gastown_orchestration_contract(
        gascity_pack_inference_gate.PACK_SPECS["gastown"].source
    )


def test_validate_gastown_orchestration_contract_rejects_missing_build_handoff(tmp_path) -> None:
    formulas = tmp_path / "gastown" / "formulas"
    formulas.mkdir(parents=True)
    for formula_name, fragments in gascity_pack_inference_gate.all_gastown_formula_contracts().items():
        text = "\n".join(fragments)
        if formula_name == "mol-polecat-work":
            text = text.replace("--assignee=\"$REFINERY_TARGET\"", "")
        (formulas / f"{formula_name}.toml").write_text(text, encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="mol-polecat-work"):
        gascity_pack_inference_gate.validate_gastown_orchestration_contract(tmp_path / "gastown")


def test_validate_gastown_orchestration_contract_rejects_missing_refinery_false_completion_guard(tmp_path) -> None:
    formulas = tmp_path / "gastown" / "formulas"
    formulas.mkdir(parents=True)
    for formula_name, fragments in gascity_pack_inference_gate.all_gastown_formula_contracts().items():
        text = "\n".join(fragments)
        if formula_name == "mol-refinery-patrol":
            text = text.replace("branch_has_real_change", "")
        (formulas / f"{formula_name}.toml").write_text(text, encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="mol-refinery-patrol"):
        gascity_pack_inference_gate.validate_gastown_orchestration_contract(tmp_path / "gastown")


def test_validate_methodology_flow_contracts_accept_current_packs() -> None:
    for pack_name in gascity_pack_inference_gate.METHODOLOGY_PACKS:
        gascity_pack_inference_gate.validate_methodology_flow_contract(
            gascity_pack_inference_gate.PACK_SPECS[pack_name]
        )


def test_validate_methodology_flow_contract_rejects_missing_specialist_review_lane(tmp_path) -> None:
    spec = gascity_pack_inference_gate.PACK_SPECS["superpowers"]
    pack_source = tmp_path / "superpowers"
    shutil.copytree(spec.source / "formulas", pack_source / "formulas")
    review_expansion = pack_source / "formulas" / "superpowers-code-review.formula.toml"
    review_expansion.write_text(
        review_expansion.read_text(encoding="utf-8").replace(
            "superpowers.code-quality-reviewer",
            "superpowers.code-reviewer",
        ),
        encoding="utf-8",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="superpowers.code-quality-reviewer"):
        gascity_pack_inference_gate.validate_methodology_flow_contract(
            replace(spec, source=pack_source)
        )


def test_validate_methodology_flow_contract_rejects_missing_source_bound_requirements_sink(
    tmp_path,
) -> None:
    spec = gascity_pack_inference_gate.PACK_SPECS["superpowers"]
    pack_source = tmp_path / "superpowers"
    shutil.copytree(spec.source / "formulas", pack_source / "formulas")
    expansion = pack_source / "formulas" / "superpowers-brainstorming.formula.toml"
    expansion.write_text(
        expansion.read_text(encoding="utf-8").replace(
            "build-requirements-source-valid.sh",
            "build-artifact-valid.sh",
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match="superpowers-brainstorming.*terminal.*build-requirements-source-valid",
    ):
        gascity_pack_inference_gate.validate_methodology_flow_contract(
            replace(spec, source=pack_source)
        )


def test_validate_methodology_flow_contract_rejects_missing_gstack_release_readiness(tmp_path) -> None:
    spec = gascity_pack_inference_gate.PACK_SPECS["gstack"]
    pack_source = tmp_path / "gstack"
    shutil.copytree(spec.source / "formulas", pack_source / "formulas")
    build_formula = pack_source / "formulas" / "gstack-build.formula.toml"
    build_formula.write_text(
        build_formula.read_text(encoding="utf-8").replace('id = "release-readiness"', 'id = "release-check"'),
        encoding="utf-8",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="release-readiness"):
        gascity_pack_inference_gate.validate_methodology_flow_contract(
            replace(spec, source=pack_source)
        )


def test_gastown_build_workflow_contract_covers_orchestration_roles() -> None:
    contracts = gascity_pack_inference_gate.GASTOWN_BUILD_WORKFLOW_CONTRACTS

    assert set(contracts) == {
        "mol-polecat-work",
        "mol-refinery-patrol",
        "mol-witness-patrol",
        "mol-deacon-patrol",
        "mol-idea-to-plan",
    }
    assert "gc session wake \"$REFINERY_TARGET\"" in contracts["mol-polecat-work"]
    assert 'git worktree add --detach "$MERGE_WT" "origin/$TARGET"' in contracts["mol-refinery-patrol"]
    assert 'gc bd close "$WORK" --reason "Merged to $TARGET at $MERGED_SHORT"' in contracts["mol-refinery-patrol"]
    assert "gc bd close $WORK --reason \"Pull request ready: $PR_URL\"" in contracts["mol-refinery-patrol"]
    assert "FAIL-SAFE: empty liveness map" in contracts["mol-witness-patrol"]
    assert "gc bd create --type=task --label=warrant" in contracts["mol-deacon-patrol"]
    assert "gc bd dep add" in contracts["mol-idea-to-plan"]


def test_build_basic_work_item_targets_code_and_pytest() -> None:
    text = gascity_pack_inference_gate.build_basic_work_item()

    assert text.splitlines()[0] == gascity_pack_inference_gate.BUILD_SOURCE_TITLE
    assert "slugger.py" in text
    assert "pytest -q" in text
    assert "PYTHONDONTWRITEBYTECODE=1" in text
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in text
    assert "Do not change tests" in text


def test_build_basic_proof_command_leaves_no_python_cache_artifacts(tmp_path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "slugger.py").write_text(
        "def slugify(value: str) -> str:\n    return value.lower()\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_slugger.py").write_text(
        "from slugger import slugify\n\n"
        "def test_slugify():\n"
        "    assert slugify('HELLO') == 'hello'\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    generated = [
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
    ]
    assert generated == []
    assert not (tmp_path / ".pytest_cache").exists()


def test_build_basic_source_id_requires_one_exact_launcher_source() -> None:
    source = {"id": "fi-source", "title": gascity_pack_inference_gate.BUILD_SOURCE_TITLE}

    assert gascity_pack_inference_gate.build_basic_source_id([source]) == "fi-source"

    with pytest.raises(gascity_pack_inference_gate.GateError, match="exactly one.*source"):
        gascity_pack_inference_gate.build_basic_source_id([])
    with pytest.raises(gascity_pack_inference_gate.GateError, match="exactly one.*source"):
        gascity_pack_inference_gate.build_basic_source_id(
            [source, {"id": "fi-other", "title": gascity_pack_inference_gate.BUILD_SOURCE_TITLE}]
        )


@pytest.mark.parametrize(
    ("source_entries", "expected"),
    (
        ([], r"fi-source.*exactly one identity"),
        (
            [
                {"path": "beads/fi-source", "hash": "bead:fi-source"},
                {"path": "beads/fi-source", "hash": "bead:fi-source"},
            ],
            r"fi-source.*exactly one identity",
        ),
        (
            [{"path": "beads/fi-source", "hash": "bead:fi-other"}],
            r"fi-source.*exactly one identity",
        ),
    ),
)
def test_validate_build_basic_source_provenance_rejects_unbound_requirements(
    tmp_path, source_entries, expected
) -> None:
    requirements_path = tmp_path / "requirements.md"
    artifact = valid_build_artifact("gc.build.requirements.v1")
    rendered_entries = "".join(
        f"    - path: {entry['path']}\n      hash: {entry['hash']}\n"
        for entry in source_entries
    )
    requirements_path.write_text(
        artifact.replace("  upstream:\n", "  upstream:\n" + rendered_entries, 1),
        encoding="utf-8",
    )
    root = {"metadata": {"gc.build.requirements_path": str(requirements_path)}}

    with pytest.raises(gascity_pack_inference_gate.GateError, match=expected):
        gascity_pack_inference_gate.validate_build_basic_source_provenance(
            root,
            source_id="fi-source",
            rig_dir=tmp_path,
        )


def test_validate_build_basic_source_provenance_accepts_exact_source_trace(tmp_path) -> None:
    requirements_path = tmp_path / "requirements.md"
    artifact = valid_build_artifact("gc.build.requirements.v1")
    requirements_path.write_text(
        artifact.replace(
            "  upstream:\n",
            "  upstream:\n"
            "    - path: beads/fi-source\n"
            "      hash: bead:fi-source\n",
            1,
        ),
        encoding="utf-8",
    )
    root = {"metadata": {"gc.build.requirements_path": str(requirements_path)}}

    gascity_pack_inference_gate.validate_build_basic_source_provenance(
        root,
        source_id="fi-source",
        rig_dir=tmp_path,
    )


def valid_convoy_status_payload() -> dict:
    return {
        "schema_version": "1",
        "convoy": {"id": "fi-implementation", "status": "closed"},
        "progress": {"closed": 2, "total": 2},
        "children": [
            {"id": "fi-one", "status": "closed", "type": "task"},
            {"id": "fi-two", "status": "closed", "type": "task"},
        ],
    }


def test_implementation_convoy_member_ids_queries_exact_root_convoy(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    fake_gc = tmp_path / "gc"
    args_path = tmp_path / "gc-args.txt"
    payload = json.dumps(valid_convoy_status_payload(), separators=(",", ":"))
    fake_gc.write_text(
        f"""#!/bin/sh
printf '%s\n' "$*" > {shlex.quote(str(args_path))}
printf '%s\n' {shlex.quote(payload)}
""",
        encoding="utf-8",
    )
    fake_gc.chmod(0o755)
    root = closed_bead(
        "fi-root",
        kind="workflow",
        metadata={"gc.build.implementation_convoy_id": "fi-implementation"},
    )

    member_ids = gascity_pack_inference_gate.implementation_convoy_member_ids(
        str(fake_gc), workspace, root, env={}
    )

    assert member_ids == ["fi-one", "fi-two"]
    assert "convoy status fi-implementation --json" in args_path.read_text(encoding="utf-8")


def test_implementation_convoy_member_ids_rejects_missing_root_convoy_id(tmp_path) -> None:
    workspace = gate_workspace(tmp_path)
    root = closed_bead("fi-root", kind="workflow")

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"missing gc\.build\.implementation_convoy_id",
    ):
        gascity_pack_inference_gate.implementation_convoy_member_ids(
            "gc", workspace, root, env={}
        )


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        ("wrong-convoy", "different convoy"),
        ("open-convoy", "status=closed"),
        ("duplicate-child", "unique child ids"),
        ("malformed-child", "non-empty id"),
        ("open-child", "child fi-one.*closed"),
        ("dangling-child", "dangling"),
        ("dangling-progress", "dangling"),
        ("wrong-total", "progress.total"),
        ("wrong-closed", "progress.closed"),
    ),
)
def test_convoy_status_member_ids_rejects_inconsistent_payload(case, expected) -> None:
    payload = json.loads(json.dumps(valid_convoy_status_payload()))
    if case == "wrong-convoy":
        payload["convoy"]["id"] = "fi-other"
    elif case == "open-convoy":
        payload["convoy"]["status"] = "open"
    elif case == "duplicate-child":
        payload["children"][1]["id"] = "fi-one"
    elif case == "malformed-child":
        del payload["children"][1]["id"]
    elif case == "open-child":
        payload["children"][0]["status"] = "open"
    elif case == "dangling-child":
        payload["children"][0]["dangling_track"] = True
    elif case == "dangling-progress":
        payload["progress"]["dangling_tracks"] = 1
    elif case == "wrong-total":
        payload["progress"]["total"] = 3
    else:
        payload["progress"]["closed"] = 1

    with pytest.raises(gascity_pack_inference_gate.GateError, match=expected):
        gascity_pack_inference_gate.convoy_status_member_ids(payload, "fi-implementation")


def implementation_summary_text(workflow_id: str, upstream: list[dict[str, str]] | None = None) -> str:
    front_matter = {
        "schema": "gc.build.implementation-summary.v1",
        "workflow": {"id": workflow_id, "formula": "do-work"},
        "methodology": {"pack": "gascity", "name": "build-basic"},
        "producer": {"formula": "do-work", "stage": "implement", "attempt": 1},
        "status": "approved",
        "trace": {"upstream": upstream or [], "coverage": []},
    }
    body = "\n".join(
        f"## {heading}\n\nCovered.\n"
        for heading in ("Summary", "Intended Behavior", "Changed Files", "Verification", "Remaining Risks")
    )
    return f"---\n{yaml.safe_dump(front_matter, sort_keys=False)}---\n\n{body}"


PASSING_SLUGGER = """\
import re


def slugify(value: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", value.lower()))
"""
WRONG_SLUGGER = "def slugify(value: str) -> str:\n    return 'wrong'\n"


def set_member_provenance(bead: dict, *, worktree: Path, summary: Path, commit: str) -> None:
    bead["metadata"].update(
        {
            "work_dir": str(worktree),
            "gc.implementation.work_dir": str(worktree),
            "gc.implementation.worktree_path": str(worktree),
            "gc.build.implementation_worktree_path": str(worktree),
            "gc.implementation.commit": commit,
            "gc.implementation.summary_path": str(summary),
        }
    )


def build_basic_result_fixture(tmp_path: Path, *, implemented: bool = True) -> dict:
    rig_dir = tmp_path / "fixture"
    gascity_pack_inference_gate.write_build_basic_fixture(rig_dir)
    gascity_pack_inference_gate.initialize_rig_git(rig_dir, env=os.environ)
    launcher_commit = run_git(rig_dir, "rev-parse", "HEAD")

    member_records: dict[str, dict] = {}
    member_beads: list[dict] = []
    workflow_beads: list[dict] = []
    for member_id in ("fi-one", "fi-two"):
        worktree = rig_dir / "worktrees" / member_id
        run_git(rig_dir, "worktree", "add", "-q", "--detach", str(worktree), "HEAD")
        if implemented:
            (worktree / "slugger.py").write_text(PASSING_SLUGGER, encoding="utf-8")
        summary = worktree / "implementation-summary.md"
        summary.write_text(
            implementation_summary_text(
                f"{member_id}-workflow",
                [{"path": f"beads/{member_id}", "hash": f"bead:{member_id}"}],
            ),
            encoding="utf-8",
        )
        run_git(worktree, "add", "slugger.py", "implementation-summary.md")
        run_git(worktree, "commit", "-q", "-m", f"implement {member_id}")
        commit = run_git(worktree, "rev-parse", "HEAD")
        bead = closed_bead(member_id)
        set_member_provenance(bead, worktree=worktree, summary=summary, commit=commit)
        member_records[member_id] = {
            "bead": bead,
            "worktree": worktree,
            "summary": summary,
            "commit": commit,
        }
        member_beads.append(bead)
        workflow_beads.append(
            closed_bead(
                f"{member_id}-workflow",
                kind="workflow",
                metadata={
                    "gc.drain_control_id": "fi-drain",
                    "gc.drain_member_id": member_id,
                },
            )
        )

    drain_manifest = json.dumps(
        {
            "version": 1,
            "rows": [
                {
                    "member_id": member_id,
                    "item_root_id": f"{member_id}-workflow",
                    "outcome_bead_id": f"{member_id}-workflow",
                    "status": "succeeded",
                    "outcome_kind": "pass",
                }
                for member_id in member_records
            ],
        }
    )
    root_summary = rig_dir / ".gc" / "inference-gate" / "build-basic" / "implementation-summary.md"
    root_summary.parent.mkdir(parents=True)
    root_summary.write_text(
        implementation_summary_text(
            "fi-root",
            [
                {
                    "path": str(record["summary"]),
                    "hash": f"sha256:{hashlib.sha256(record['summary'].read_bytes()).hexdigest()}",
                }
                for record in member_records.values()
            ],
        ),
        encoding="utf-8",
    )
    root = closed_bead(
        "fi-root",
        kind="workflow",
        metadata={
            "gc.build.implementation_convoy_id": "fi-implementation",
            "gc.build.implementation_summary_path": str(root_summary),
        },
    )
    drain = closed_bead(
        "fi-drain",
        root="fi-root",
        kind="drain",
        metadata={
            "gc.drain_parent_convoy_id": "fi-implementation",
            "gc.drain_count": str(len(member_records)),
            "gc.drain_state": "succeeded",
            "gc.drain_manifest.v1": drain_manifest,
        },
    )
    return {
        "rig_dir": rig_dir,
        "launcher_commit": launcher_commit,
        "root": root,
        "root_summary": root_summary,
        "members": member_records,
        "expected_member_ids": list(member_records),
        "beads": [root, drain, *workflow_beads, *member_beads],
    }


def test_build_basic_implementation_members_matches_convoy_and_manifest(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)

    members = gascity_pack_inference_gate.build_basic_implementation_members(
        fixture["root"], fixture["beads"], fixture["expected_member_ids"]
    )

    assert members == [("fi-one", "fi-one-workflow"), ("fi-two", "fi-two-workflow")]


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        ("expected-mismatch", "convoy children.*manifest members"),
        ("duplicate-expected", "convoy child ids.*unique"),
        ("duplicate-row", "manifest member ids.*unique"),
        ("duplicate-workflow", "workflow root ids.*unique"),
        ("swapped-workflow", "gc.drain_member_id.*manifest member"),
        ("missing-workflow", "workflow root fi-two-workflow.*exactly once"),
        ("wrong-control", "gc.drain_control_id.*implementation drain"),
        ("malformed-row", "row 0"),
        ("failed-row", "status=succeeded"),
        ("failed-outcome", "outcome_kind=pass"),
        ("count", "gc.drain_count"),
        ("state", "gc.drain_state=succeeded"),
    ),
)
def test_build_basic_implementation_members_rejects_inconsistent_evidence(tmp_path, case, expected) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    drain = next(bead for bead in fixture["beads"] if bead["id"] == "fi-drain")
    manifest = json.loads(drain["metadata"]["gc.drain_manifest.v1"])
    expected_ids = list(fixture["expected_member_ids"])
    if case == "expected-mismatch":
        expected_ids[-1] = "fi-other"
    elif case == "duplicate-expected":
        expected_ids[-1] = expected_ids[0]
    elif case == "duplicate-row":
        manifest["rows"][-1]["member_id"] = manifest["rows"][0]["member_id"]
    elif case == "duplicate-workflow":
        manifest["rows"][-1]["item_root_id"] = manifest["rows"][0]["item_root_id"]
        manifest["rows"][-1]["outcome_bead_id"] = manifest["rows"][0]["outcome_bead_id"]
    elif case == "swapped-workflow":
        first_root = manifest["rows"][0]["item_root_id"]
        second_root = manifest["rows"][1]["item_root_id"]
        for key in ("item_root_id", "outcome_bead_id"):
            manifest["rows"][0][key] = second_root
            manifest["rows"][1][key] = first_root
    elif case == "missing-workflow":
        fixture["beads"] = [bead for bead in fixture["beads"] if bead["id"] != "fi-two-workflow"]
    elif case == "wrong-control":
        workflow = next(bead for bead in fixture["beads"] if bead["id"] == "fi-two-workflow")
        workflow["metadata"]["gc.drain_control_id"] = "fi-other-drain"
    elif case == "malformed-row":
        del manifest["rows"][0]["member_id"]
    elif case == "failed-row":
        manifest["rows"][0]["status"] = "failed"
    elif case == "failed-outcome":
        manifest["rows"][0]["outcome_kind"] = "fail"
    elif case == "count":
        drain["metadata"]["gc.drain_count"] = "1"
    else:
        drain["metadata"]["gc.drain_state"] = "failed"
    drain["metadata"]["gc.drain_manifest.v1"] = json.dumps(manifest)

    with pytest.raises(gascity_pack_inference_gate.GateError, match=expected):
        gascity_pack_inference_gate.build_basic_implementation_members(
            fixture["root"], fixture["beads"], expected_ids
        )


def validate_build_basic_fixture(fixture: dict) -> list[Path]:
    return gascity_pack_inference_gate.validate_build_basic_result(
        fixture["rig_dir"],
        fixture["beads"],
        root_bead=fixture["root"],
        expected_member_ids=fixture["expected_member_ids"],
        launcher_commit=fixture["launcher_commit"],
        env={},
        timeout=30,
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )


def test_validate_build_basic_result_accepts_every_member_with_commit_bound_provenance(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)

    selected = validate_build_basic_fixture(fixture)

    assert selected == [record["worktree"] for record in fixture["members"].values()]


def test_validate_build_basic_result_resolves_member_summary_repo_relative_sha(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    member = fixture["members"]["fi-two"]
    worktree = member["worktree"]
    old_summary = member["summary"]
    nested_summary = worktree / "artifacts" / "implementation-summary.md"
    nested_summary.parent.mkdir()
    nested_summary.write_text(
        implementation_summary_text(
            "fi-two-workflow",
            [
                {"path": "beads/fi-two", "hash": "bead:fi-two"},
                {
                    "path": "slugger.py",
                    "hash": f"sha256:{hashlib.sha256((worktree / 'slugger.py').read_bytes()).hexdigest()}",
                },
            ],
        ),
        encoding="utf-8",
    )
    run_git(worktree, "add", "artifacts/implementation-summary.md")
    run_git(worktree, "commit", "-q", "-m", "record nested implementation summary")
    commit = run_git(worktree, "rev-parse", "HEAD")
    member["bead"]["metadata"]["gc.implementation.summary_path"] = str(nested_summary)
    member["bead"]["metadata"]["gc.implementation.commit"] = commit

    root_summary = fixture["root_summary"]
    old_digest = f"sha256:{hashlib.sha256(old_summary.read_bytes()).hexdigest()}"
    new_digest = f"sha256:{hashlib.sha256(nested_summary.read_bytes()).hexdigest()}"
    root_summary.write_text(
        root_summary.read_text(encoding="utf-8")
        .replace(str(old_summary), str(nested_summary))
        .replace(old_digest, new_digest),
        encoding="utf-8",
    )

    selected = validate_build_basic_fixture(fixture)

    assert selected == [record["worktree"] for record in fixture["members"].values()]


def test_validate_build_basic_result_rejects_shared_commit_across_distinct_member_worktrees(
    tmp_path,
) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    one, two = (fixture["members"][member_id] for member_id in ("fi-one", "fi-two"))
    two_summary = two["summary"].read_bytes()

    run_git(two["worktree"], "reset", "--hard", one["commit"])
    two["summary"].write_bytes(two_summary)
    two["bead"]["metadata"]["gc.implementation.commit"] = one["commit"]

    assert one["worktree"] != two["worktree"]
    assert run_git(one["worktree"], "rev-parse", "HEAD") == run_git(
        two["worktree"], "rev-parse", "HEAD"
    )
    with pytest.raises(gascity_pack_inference_gate.GateError, match="commits must be distinct"):
        validate_build_basic_fixture(fixture)


def test_validate_build_basic_result_rejects_launcher_only_false_pass(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path, implemented=False)
    (fixture["rig_dir"] / "slugger.py").write_text(PASSING_SLUGGER, encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="fi-one.*NotImplementedError"):
        validate_build_basic_fixture(fixture)


@pytest.mark.parametrize(
    "metadata_key",
    ("work_dir", "gc.implementation.commit", "gc.implementation.summary_path"),
)
def test_validate_build_basic_result_rejects_missing_per_member_provenance(tmp_path, metadata_key) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    del fixture["members"]["fi-two"]["bead"]["metadata"][metadata_key]

    with pytest.raises(gascity_pack_inference_gate.GateError, match=rf"fi-two.*{re.escape(metadata_key)}"):
        validate_build_basic_fixture(fixture)


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        ("explicit-worktree", r"fi-two.*worktree_path.*work_dir"),
        ("commit", r"fi-two.*commit.*HEAD"),
        ("dirty-slugger", r"fi-two.*slugger.py.*recorded commit"),
        ("dirty-tests", r"fi-two.*tests/test_slugger.py.*recorded commit"),
        ("summary-outside", r"fi-two.*summary.*worktree"),
        ("invalid-summary", r"fi-two.*summary.*validation"),
    ),
)
def test_validate_build_basic_result_rejects_mismatched_member_provenance(tmp_path, case, expected) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    one, two = (fixture["members"][member_id] for member_id in ("fi-one", "fi-two"))
    if case == "explicit-worktree":
        two["bead"]["metadata"]["gc.implementation.worktree_path"] = str(one["worktree"])
    elif case == "commit":
        two["bead"]["metadata"]["gc.implementation.commit"] = one["commit"]
    elif case.startswith("dirty-"):
        relative_path = "slugger.py" if case == "dirty-slugger" else "tests/test_slugger.py"
        path = two["worktree"] / relative_path
        path.write_bytes(path.read_bytes() + b"\n# uncommitted product change\n")
    elif case == "summary-outside":
        two["bead"]["metadata"]["gc.implementation.summary_path"] = str(one["summary"])
    else:
        two["summary"].write_text("not a build artifact\n", encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match=expected):
        validate_build_basic_fixture(fixture)


@pytest.mark.parametrize(
    ("parent", "path_member", "expected_member", "expected_error"),
    (
        ("worktrees", "fi-member", "fi-member", None),
        ("lanes", "fi-member", "fi-member", r"fi-member.*worktrees/fi-member"),
        ("worktrees", "fi-one", "fi-other", r"fi-other.*worktrees/fi-other"),
    ),
    ids=("nested-prepare-path", "wrong-parent", "swapped-member"),
)
def test_authoritative_member_worktree_enforces_runtime_suffix(
    tmp_path, parent, path_member, expected_member, expected_error
) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    worktree = fixture["rig_dir"] / "fi-prepare-item-worktree" / parent / path_member
    run_git(fixture["rig_dir"], "worktree", "add", "-q", "--detach", str(worktree), "HEAD")
    member = closed_bead(path_member, metadata={"work_dir": str(worktree)})

    def validate():
        return gascity_pack_inference_gate.authoritative_member_worktree(
            member,
            expected_member,
            fixture["rig_dir"].resolve(),
            gascity_pack_inference_gate.git_common_dir(fixture["rig_dir"], context="test launcher"),
        )

    if expected_error:
        with pytest.raises(gascity_pack_inference_gate.GateError, match=expected_error):
            validate()
    else:
        assert validate() == worktree.resolve()


def test_validate_build_basic_result_rejects_worktree_from_unrelated_repository(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    unrelated = fixture["rig_dir"] / "worktrees" / "unrelated-repository"
    gascity_pack_inference_gate.write_build_basic_fixture(unrelated)
    gascity_pack_inference_gate.initialize_rig_git(unrelated, env=os.environ)
    (unrelated / "slugger.py").write_text(PASSING_SLUGGER, encoding="utf-8")
    summary = unrelated / "implementation-summary.md"
    summary.write_text(implementation_summary_text("fi-two-workflow"), encoding="utf-8")
    run_git(unrelated, "add", "slugger.py", "implementation-summary.md")
    run_git(unrelated, "commit", "-q", "-m", "unrelated implementation")
    commit = run_git(unrelated, "rev-parse", "HEAD")
    set_member_provenance(
        fixture["members"]["fi-two"]["bead"],
        worktree=unrelated,
        summary=summary,
        commit=commit,
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="not linked.*launcher"):
        validate_build_basic_fixture(fixture)


def test_validate_build_basic_result_rejects_linked_worktree_outside_rig(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    outside = tmp_path / "outside-linked"
    run_git(fixture["rig_dir"], "worktree", "add", "-q", "--detach", str(outside), "HEAD")
    (outside / "slugger.py").write_text(PASSING_SLUGGER, encoding="utf-8")
    summary = outside / "implementation-summary.md"
    summary.write_text(implementation_summary_text("fi-two-workflow"), encoding="utf-8")
    run_git(outside, "add", "slugger.py", "implementation-summary.md")
    run_git(outside, "commit", "-q", "-m", "outside implementation")
    set_member_provenance(
        fixture["members"]["fi-two"]["bead"],
        worktree=outside,
        summary=summary,
        commit=run_git(outside, "rev-parse", "HEAD"),
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="inside launcher rig"):
        validate_build_basic_fixture(fixture)


def test_validate_build_basic_result_runs_pytest_in_every_member_worktree(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    two = fixture["members"]["fi-two"]
    (two["worktree"] / "slugger.py").write_text(WRONG_SLUGGER, encoding="utf-8")
    run_git(two["worktree"], "add", "slugger.py")
    run_git(two["worktree"], "commit", "-q", "-m", "break second member implementation")
    two["bead"]["metadata"]["gc.implementation.commit"] = run_git(
        two["worktree"], "rev-parse", "HEAD"
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="fi-two.*pytest failed"):
        validate_build_basic_fixture(fixture)


def test_validate_build_basic_result_rejects_abbreviated_member_commit(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    two = fixture["members"]["fi-two"]
    two["bead"]["metadata"]["gc.implementation.commit"] = two["commit"][:7]

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"fi-two.*full worktree HEAD",
    ):
        validate_build_basic_fixture(fixture)


def test_validate_build_basic_result_rejects_committed_weakened_tests(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    two = fixture["members"]["fi-two"]
    (two["worktree"] / "slugger.py").write_text(WRONG_SLUGGER, encoding="utf-8")
    (two["worktree"] / "tests" / "test_slugger.py").write_text(
        "from slugger import slugify\n\n\ndef test_weakened_oracle():\n    assert slugify('Gas City') == 'wrong'\n",
        encoding="utf-8",
    )
    run_git(two["worktree"], "add", "slugger.py", "tests/test_slugger.py")
    run_git(two["worktree"], "commit", "-q", "-m", "weaken implementation oracle")
    two["bead"]["metadata"]["gc.implementation.commit"] = run_git(
        two["worktree"], "rev-parse", "HEAD"
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"fi-two.*tests/test_slugger.py.*launcher baseline",
    ):
        validate_build_basic_fixture(fixture)


def test_launcher_baseline_tests_rejects_advanced_launcher_head(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    rig_dir = fixture["rig_dir"]
    baseline_commit = run_git(rig_dir, "rev-parse", "HEAD")
    test_path = rig_dir / "tests" / "test_slugger.py"
    test_path.write_text("def test_weakened():\n    assert True\n", encoding="utf-8")
    run_git(rig_dir, "add", "tests/test_slugger.py")
    run_git(rig_dir, "commit", "-q", "-m", "weaken launcher tests")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="launcher HEAD changed after launch"):
        gascity_pack_inference_gate.launcher_baseline_tests(rig_dir, baseline_commit)


def test_validate_build_basic_result_ignores_untracked_pytest_xfail_hook(tmp_path) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    two = fixture["members"]["fi-two"]
    (two["worktree"] / "slugger.py").write_text(WRONG_SLUGGER, encoding="utf-8")
    run_git(two["worktree"], "add", "slugger.py")
    run_git(two["worktree"], "commit", "-q", "-m", "break committed implementation")
    two["bead"]["metadata"]["gc.implementation.commit"] = run_git(
        two["worktree"], "rev-parse", "HEAD"
    )
    (two["worktree"] / "conftest.py").write_text(
        """\
import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.xfail(reason="mask committed failure"))
""",
        encoding="utf-8",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match="fi-two.*pytest failed"):
        validate_build_basic_fixture(fixture)


def test_validate_build_basic_result_ignores_ancestor_pytest_xfail_hook(tmp_path, monkeypatch) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    two = fixture["members"]["fi-two"]
    (two["worktree"] / "slugger.py").write_text(WRONG_SLUGGER, encoding="utf-8")
    run_git(two["worktree"], "add", "slugger.py")
    run_git(two["worktree"], "commit", "-q", "-m", "break committed implementation")
    two["bead"]["metadata"]["gc.implementation.commit"] = run_git(
        two["worktree"], "rev-parse", "HEAD"
    )

    hostile_parent = tmp_path / "hostile-pytest-parent"
    hostile_parent.mkdir()
    (hostile_parent / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (hostile_parent / "conftest.py").write_text(
        """\
import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.xfail(reason="mask committed failure"))
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(gascity_pack_inference_gate.tempfile, "tempdir", str(hostile_parent))

    with pytest.raises(gascity_pack_inference_gate.GateError, match="fi-two.*pytest failed"):
        validate_build_basic_fixture(fixture)


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    (
        ("id: fi-two-workflow", "id: fi-other-workflow", r"fi-two.*workflow.id.*fi-two-workflow"),
        ("path: beads/fi-two", "path: beads/fi-other", r"fi-two.*beads/fi-two"),
        ("hash: bead:fi-two", "hash: bead:fi-other", r"fi-two.*bead:fi-two"),
        (
            "  - path: beads/fi-two\n    hash: bead:fi-two",
            "  - path: beads/fi-two\n    hash: bead:fi-two\n"
            "  - path: beads/fi-two\n    hash: bead:fi-two",
            r"fi-two.*beads/fi-two.*bead:fi-two",
        ),
    ),
)
def test_validate_build_basic_result_binds_member_summary_identity(tmp_path, old, new, expected) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    two = fixture["members"]["fi-two"]
    old_bytes = two["summary"].read_bytes()
    two["summary"].write_text(old_bytes.decode("utf-8").replace(old, new, 1), encoding="utf-8")
    old_digest = f"sha256:{hashlib.sha256(old_bytes).hexdigest()}"
    new_digest = f"sha256:{hashlib.sha256(two['summary'].read_bytes()).hexdigest()}"
    root_summary = fixture["root_summary"]
    root_summary.write_text(
        root_summary.read_text(encoding="utf-8").replace(old_digest, new_digest),
        encoding="utf-8",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match=expected):
        validate_build_basic_fixture(fixture)


@pytest.mark.parametrize("case", ("digest", "path"))
def test_validate_build_basic_result_rejects_canonical_summary_mismatch(tmp_path, case) -> None:
    fixture = build_basic_result_fixture(tmp_path)
    two = fixture["members"]["fi-two"]
    root_summary = fixture["root_summary"]
    original = root_summary.read_text(encoding="utf-8")
    if case == "digest":
        digest = f"sha256:{hashlib.sha256(two['summary'].read_bytes()).hexdigest()}"
        changed = original.replace(digest, f"sha256:{'0' * 64}")
        expected = r"fi-two.*canonical.*digest"
    else:
        changed = original.replace(str(two["summary"]), str(two["summary"]) + ".stale")
        expected = r"fi-two.*canonical.*exact path"
    root_summary.write_text(
        changed,
        encoding="utf-8",
    )

    with pytest.raises(gascity_pack_inference_gate.GateError, match=expected):
        validate_build_basic_fixture(fixture)


def successful_build_basic_root(
    artifact_metadata: dict[str, str],
    *,
    artifact_root: Path | None = None,
) -> dict:
    resolved_artifact_root = artifact_root or Path(next(iter(artifact_metadata.values()))).parent
    metadata = {
        "gc.var.review_mode": "report",
        "gc.build.artifact_root": str(resolved_artifact_root.resolve()),
        "gc.build.status": "completed",
        "gc.build.finalize_status": "completed",
        "gc.build.finalize_outcome": "success",
        **artifact_metadata,
    }
    return {
        "id": "fi-root",
        "status": "closed",
        "metadata": {"gc.outcome": "pass", **metadata},
    }


def blocked_build_basic_root(
    artifact_metadata: dict[str, str],
    *,
    artifact_root: Path | None = None,
) -> dict:
    resolved_artifact_root = artifact_root or Path(next(iter(artifact_metadata.values()))).parent
    metadata = {
        "gc.var.review_mode": "report",
        "gc.build.artifact_root": str(resolved_artifact_root.resolve()),
        "gc.build.status": "blocked",
        "gc.build.finalize_status": "failed",
        "gc.build.finalize_outcome": "failure",
        **artifact_metadata,
    }
    return {
        "id": "fi-root",
        "status": "closed",
        "metadata": {"gc.outcome": "fail", **metadata},
    }


def add_sha256_upstreams(text: str, *upstream_paths: Path) -> str:
    entries = "".join(
        f"    - path: {path.resolve()}\n"
        f"      hash: sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}\n"
        for path in upstream_paths
    )
    return text.replace("  coverage:\n", entries + "  coverage:\n", 1)


PACK_BUILD_ARTIFACT_IDENTITIES = {
    "gascity": {
        "gc.build.requirements_path": ("build-basic", "gascity", "build-basic", "build-basic", "requirements"),
        "gc.build.plan_path": ("build-basic", "gascity", "build-basic", "build-basic", "plan"),
        "gc.build.decomposition_path": ("build-basic", "gascity", "build-basic", "build-basic", "decompose"),
        "gc.build.implementation_summary_path": (
            "build-basic",
            "gascity",
            "build-basic",
            "build-basic",
            "summarize-implementation",
        ),
        "gc.build.review_report_path": ("build-basic", "gascity", "build-basic", "build-basic-review", "review"),
        "gc.build.final_report_path": ("build-basic", "gascity", "build-basic", "build-basic", "finalize"),
    },
    "superpowers": {
        "gc.build.requirements_path": (
            "superpowers-build",
            "superpowers",
            "superpowers-brainstorming",
            "superpowers-brainstorming",
            "requirements",
        ),
        "gc.build.plan_path": ("superpowers-build", "superpowers", "writing-plans", "superpowers-build", "plan"),
        "gc.build.decomposition_path": (
            "superpowers-build",
            "superpowers",
            "superpowers-decomposition",
            "superpowers-build",
            "decompose",
        ),
        "gc.build.implementation_summary_path": (
            "superpowers-build",
            "superpowers",
            "superpowers-build",
            "superpowers-build",
            "summarize-implementation",
        ),
        "gc.build.review_report_path": (
            "superpowers-build",
            "superpowers",
            "superpowers-code-review",
            "superpowers-code-review",
            "adapter-report",
        ),
        "gc.build.final_report_path": (
            "superpowers-build",
            "superpowers",
            "superpowers-build",
            "superpowers-build",
            "finalize",
        ),
    },
    "compound-engineering": {
        "gc.build.requirements_path": (
            "compound-build",
            "compound-engineering",
            "ce-brainstorm",
            "compound-build",
            "requirements",
        ),
        "gc.build.plan_path": ("compound-build", "compound-engineering", "ce-plan", "compound-build", "plan"),
        "gc.build.decomposition_path": (
            "compound-build",
            "compound-engineering",
            "compound-decomposition",
            "compound-build",
            "decompose",
        ),
        "gc.build.implementation_summary_path": (
            "compound-build",
            "compound-engineering",
            "compound-build",
            "compound-build",
            "summarize-implementation",
        ),
        "gc.build.review_report_path": (
            "compound-review",
            "compound-engineering",
            "compound-review",
            "compound-code-review",
            "synthesize-code-review",
        ),
        "gc.build.final_report_path": (
            "compound-build",
            "compound-engineering",
            "ce-compound",
            "compound-resolution",
            "synthesize-resolution",
        ),
    },
    "gstack": {
        "gc.build.requirements_path": ("gstack-build", "gstack", "office-hours", "gstack-build", "requirements"),
        "gc.build.plan_path": ("gstack-build", "gstack", "autoplan", "gstack-build", "plan"),
        "gc.build.decomposition_path": (
            "gstack-build",
            "gstack",
            "gstack-decomposition",
            "gstack-build",
            "decompose",
        ),
        "gc.build.implementation_summary_path": (
            "gstack-build",
            "gstack",
            "gstack-build",
            "gstack-build",
            "summarize-implementation",
        ),
        "gc.build.review_report_path": (
            "gstack-review",
            "gstack",
            "gstack-review",
            "gstack-code-review",
            "adapter-report",
        ),
        "gc.build.final_report_path": ("gstack-build", "gstack", "gstack-build", "gstack-build", "finalize"),
    },
    "bmad": {
        "gc.build.requirements_path": ("bmad-build", "bmad", "bmad-prd", "bmad-build", "requirements"),
        "gc.build.plan_path": ("bmad-build", "bmad", "bmad-create-architecture", "bmad-build", "plan"),
        "gc.build.decomposition_path": (
            "bmad-build",
            "bmad",
            "bmad-create-epics-and-stories",
            "bmad-build",
            "decompose",
        ),
        "gc.build.implementation_summary_path": (
            "bmad-build",
            "bmad",
            "bmad-build",
            "bmad-build",
            "summarize-implementation",
        ),
        "gc.build.review_report_path": (
            "bmad-review",
            "bmad",
            "bmad-review",
            "bmad-code-review-flow",
            "synthesize-bmad-review",
        ),
        "gc.build.final_report_path": ("bmad-build", "bmad", "bmad-build", "bmad-build", "finalize"),
    },
}

PACK_BUILD_ARTIFACT_IDENTITY_ASSETS = {
    "gascity": {
        "gc.build.requirements_path": "gascity/assets/workflows/build-basic/requirements.md",
        "gc.build.plan_path": "gascity/assets/workflows/build-basic/plan.md",
        "gc.build.decomposition_path": "gascity/assets/workflows/build-basic/decompose.md",
        "gc.build.implementation_summary_path": "gascity/assets/workflows/build-base/summarize-implementation.md",
        "gc.build.review_report_path": "gascity/assets/workflows/build-basic-review/{target}.md",
        "gc.build.final_report_path": "gascity/assets/workflows/build-basic/finalize.md",
    },
    "superpowers": {
        "gc.build.requirements_path": (
            "superpowers/assets/workflows/superpowers-brainstorming/write-requirements-spec.md"
        ),
        "gc.build.plan_path": "superpowers/assets/workflows/superpowers-build/plan.md",
        "gc.build.decomposition_path": "superpowers/assets/workflows/superpowers-build/decompose.md",
        "gc.build.implementation_summary_path": "gascity/assets/workflows/build-base/summarize-implementation.md",
        "gc.build.review_report_path": (
            "superpowers/assets/workflows/superpowers-code-review/finalize-code-review.md"
        ),
        "gc.build.final_report_path": "superpowers/assets/workflows/superpowers-build/finalize.md",
    },
    "compound-engineering": {
        "gc.build.requirements_path": (
            "compound-engineering/assets/workflows/compound-build/requirements.md"
        ),
        "gc.build.plan_path": "compound-engineering/assets/workflows/compound-build/plan.md",
        "gc.build.decomposition_path": (
            "compound-engineering/assets/workflows/compound-decomposition/decompose.md"
        ),
        "gc.build.implementation_summary_path": "gascity/assets/workflows/build-base/summarize-implementation.md",
        "gc.build.review_report_path": (
            "compound-engineering/assets/workflows/compound-code-review/synthesize-code-review.md"
        ),
        "gc.build.final_report_path": (
            "compound-engineering/assets/workflows/compound-resolution/{target}.synthesize-resolution.md"
        ),
    },
    "gstack": {
        "gc.build.requirements_path": "gstack/assets/workflows/gstack-build/requirements.md",
        "gc.build.plan_path": "gstack/assets/workflows/gstack-build/plan.md",
        "gc.build.decomposition_path": "gstack/assets/workflows/gstack-build/decompose.md",
        "gc.build.implementation_summary_path": (
            "gstack/assets/workflows/gstack-build/summarize-implementation.md"
        ),
        "gc.build.review_report_path": (
            "gstack/assets/workflows/gstack-code-review/finalize-code-review.md"
        ),
        "gc.build.final_report_path": "gstack/assets/workflows/gstack-build/finalize.md",
    },
    "bmad": {
        "gc.build.requirements_path": "bmad/assets/workflows/bmad-build/requirements.md",
        "gc.build.plan_path": "bmad/assets/workflows/bmad-build/plan.md",
        "gc.build.decomposition_path": "bmad/assets/workflows/bmad-build/decompose.md",
        "gc.build.implementation_summary_path": "gascity/assets/workflows/build-base/summarize-implementation.md",
        "gc.build.review_report_path": (
            "bmad/assets/workflows/bmad-code-review-flow/synthesize-bmad-review.md"
        ),
        "gc.build.final_report_path": "bmad/assets/workflows/bmad-build/finalize.md",
    },
}


def write_build_basic_artifacts(
    rig_dir: Path,
    *,
    statuses: dict[str, str] | None = None,
    identities: dict[str, tuple[str, str, str, str, str]] | None = None,
    attempts: dict[str, int] | None = None,
) -> dict[str, str]:
    selected_statuses = statuses or {}
    selected_identities = identities or PACK_BUILD_ARTIFACT_IDENTITIES["gascity"]
    selected_attempts = attempts or {}
    metadata: dict[str, str] = {}
    for metadata_key, schema in gascity_pack_inference_gate.BUILD_BASIC_ARTIFACT_CONTRACTS:
        artifact_path = rig_dir / f"{metadata_key.rsplit('.', 1)[-1]}.md"
        status = selected_statuses.get(metadata_key, "approved")
        if schema == "gc.build.review.v1":
            text = valid_review_artifact(status)
        else:
            text = valid_build_artifact(schema).replace(
                "status: approved", f"status: {status}", 1
            )
        (
            workflow_formula,
            methodology_pack,
            methodology_name,
            producer_formula,
            producer_stage,
        ) = selected_identities[metadata_key]
        text = text.replace(
            "workflow:\n  id: fi-root\n  formula: build-basic\n",
            f"workflow:\n  id: fi-root\n  formula: {workflow_formula}\n",
            1,
        ).replace(
            "methodology:\n  pack: gascity\n  name: build-basic\n",
            f"methodology:\n  pack: {methodology_pack}\n  name: {methodology_name}\n",
            1,
        )
        text = text.replace(
            "producer:\n  formula: build-basic\n  stage: test\n",
            f"producer:\n  formula: {producer_formula}\n  stage: {producer_stage}\n",
            1,
        )
        text = text.replace(
            "  attempt: 1\n",
            f"  attempt: {selected_attempts.get(metadata_key, 1)}\n",
            1,
        )
        if metadata_key == "gc.build.review_report_path":
            text = add_sha256_upstreams(
                text,
                Path(metadata["gc.build.implementation_summary_path"]),
            )
        elif metadata_key == "gc.build.final_report_path":
            text = add_sha256_upstreams(
                text,
                Path(metadata["gc.build.implementation_summary_path"]),
                Path(metadata["gc.build.review_report_path"]),
            )
        artifact_path.write_text(text, encoding="utf-8")
        metadata[metadata_key] = str(artifact_path)
    return metadata


def build_basic_success_beads(
    review_path: Path,
    *,
    review_attempt: int = 1,
) -> list[dict]:
    report_terminal_path = review_path.parent / "apply-review-findings-report.md"
    controls = [
        {
            "id": f"fi-{step_id}-control",
            "status": "closed",
            "metadata": {
                "gc.root_bead_id": "fi-root",
                "gc.kind": "ralph",
                "gc.step_id": step_id,
                "gc.control_epoch": "1",
                "gc.outcome": "pass",
            },
        }
        for step_id in gascity_pack_inference_gate.BUILD_BASIC_STAGE_STEPS.values()
    ]
    controls.append(
        {
            "id": f"fi-review-report-attempt-{review_attempt}",
            "status": "closed",
            "metadata": {
                "gc.root_bead_id": "fi-root",
                "gc.attempt": str(review_attempt),
                "gc.ralph_step_id": "review.build-basic-review-loop",
                "gc.step_id": "review.report-review-findings",
                "gc.scope_role": "member",
                "gc.outcome": "pass",
                "code_review.verdict": "reported",
                "code_review.report_path": str(report_terminal_path),
                "code_review.output_path": str(report_terminal_path),
            },
        }
    )
    return controls


def derived_build_success_beads(
    *,
    stage_attempts: dict[str, int] | None = None,
) -> list[dict]:
    selected_attempts = stage_attempts or {}
    return [
        {
            "id": f"fi-{step_id}-control",
            "status": "closed",
            "metadata": {
                "gc.root_bead_id": "fi-root",
                "gc.kind": "ralph",
                "gc.step_id": step_id,
                "gc.control_epoch": str(selected_attempts.get(metadata_key, 1)),
                "gc.outcome": "pass",
            },
        }
        for metadata_key, step_id in (
            gascity_pack_inference_gate.BUILD_ARTIFACT_STAGE_BY_KEY.items()
        )
    ]


def test_validate_build_basic_artifacts_accepts_declared_markdown_artifacts(tmp_path) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(rig_dir)

    gascity_pack_inference_gate.validate_build_basic_artifacts(
        successful_build_basic_root(metadata),
        rig_dir=rig_dir,
        env={},
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )


@pytest.mark.parametrize(
    "pack_name",
    ("gascity", "superpowers", "compound-engineering", "gstack", "bmad"),
)
def test_validate_build_basic_artifacts_accepts_pack_specific_identities(
    tmp_path,
    pack_name: str,
) -> None:
    rig_dir = tmp_path / pack_name
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(
        rig_dir,
        identities=PACK_BUILD_ARTIFACT_IDENTITIES[pack_name],
    )

    gascity_pack_inference_gate.validate_build_basic_artifacts(
        successful_build_basic_root(metadata),
        rig_dir=rig_dir,
        env={},
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        pack_spec=gascity_pack_inference_gate.PACK_SPECS[pack_name],
    )


def prompt_declares_identity_value(
    text: str,
    *,
    section: str,
    field: str,
    value: str,
) -> bool:
    escaped_value = re.escape(value)
    inline = re.search(
        rf"{re.escape(section)}:\s*\{{[^}}\n]*\b{re.escape(field)}:\s*"
        rf"{escaped_value}(?=\s*[,}}])",
        text,
    )
    block = re.search(
        rf"(?m)^[ \t-]*{re.escape(section)}:\s*$\n"
        rf"(?:^[ \t]+.*\n){{0,3}}"
        rf"^[ \t]+{re.escape(field)}:\s*{escaped_value}\s*$",
        text,
    )
    return inline is not None or block is not None


def test_pack_build_artifact_identities_are_anchored_in_producer_assets() -> None:
    default_stage = {
        "gc.build.requirements_path": "requirements",
        "gc.build.plan_path": "plan",
        "gc.build.decomposition_path": "decompose",
        "gc.build.implementation_summary_path": "summarize-implementation",
        "gc.build.review_report_path": "review",
        "gc.build.final_report_path": "finalize",
    }
    fields = (
        ("workflow", "formula"),
        ("methodology", "pack"),
        ("methodology", "name"),
        ("producer", "formula"),
        ("producer", "stage"),
    )

    for pack_name, identities in PACK_BUILD_ARTIFACT_IDENTITIES.items():
        pack_spec = gascity_pack_inference_gate.PACK_SPECS[pack_name]
        for metadata_key, identity in identities.items():
            asset = (
                gascity_pack_inference_gate.REPO_ROOT
                / PACK_BUILD_ARTIFACT_IDENTITY_ASSETS[pack_name][metadata_key]
            )
            text = asset.read_text(encoding="utf-8").replace("`", "")
            generic_defaults = (
                pack_spec.build_formula,
                pack_name,
                pack_spec.build_formula,
                pack_spec.build_formula,
                default_stage[metadata_key],
            )
            for (section, field), expected, generic_default in zip(
                fields,
                identity,
                generic_defaults,
                strict=True,
            ):
                if prompt_declares_identity_value(
                    text,
                    section=section,
                    field=field,
                    value=expected,
                ):
                    continue
                assert expected == generic_default, (
                    f"{pack_name} {metadata_key} {section}.{field}={expected!r} "
                    f"is neither declared by {asset} nor the generic build contract "
                    f"default {generic_default!r}"
                )
                assert f"{section}.{field}" in text or (
                    f"{section}:" in text and f"{field}:" in text
                ), f"{asset} does not document generic field {section}.{field}"


def test_derived_build_finalizers_emit_success_lifecycle_metadata() -> None:
    finalizers = {
        "superpowers": "superpowers/assets/workflows/superpowers-build/finalize.md",
        "compound-engineering": (
            "compound-engineering/assets/workflows/compound-resolution/{target}.md"
        ),
        "gstack": "gstack/assets/workflows/gstack-build/finalize.md",
        "bmad": "bmad/assets/workflows/bmad-build/finalize.md",
    }
    required = (
        "gc.build.status=completed",
        "gc.build.finalize_status=completed",
        "gc.build.finalize_outcome=success",
        "gc.outcome=pass",
    )

    for pack_name, relative_path in finalizers.items():
        text = (gascity_pack_inference_gate.REPO_ROOT / relative_path).read_text(
            encoding="utf-8"
        )
        missing = [fragment for fragment in required if fragment not in text]
        assert not missing, f"{pack_name} finalizer is missing lifecycle contract: {missing}"


def test_derived_build_producers_declare_current_lineage_contract() -> None:
    producer_assets = {
        "superpowers": (
            "superpowers/assets/workflows/superpowers-code-review/finalize-code-review.md",
            "superpowers/assets/workflows/superpowers-build/finalize.md",
        ),
        "compound-engineering": (
            "compound-engineering/assets/workflows/compound-code-review/finalize-code-review.md",
            "compound-engineering/assets/workflows/compound-resolution/{target}.synthesize-resolution.md",
        ),
        "gstack": (
            "gstack/assets/workflows/gstack-code-review/finalize-code-review.md",
            "gstack/assets/workflows/gstack-build/finalize.md",
        ),
        "bmad": (
            "bmad/assets/workflows/bmad-code-review-flow/finalize-bmad-code-review.md",
            "bmad/assets/workflows/bmad-build/finalize.md",
        ),
    }

    for pack_name, (review_asset, final_asset) in producer_assets.items():
        review_text = (gascity_pack_inference_gate.REPO_ROOT / review_asset).read_text(
            encoding="utf-8"
        )
        final_text = (gascity_pack_inference_gate.REPO_ROOT / final_asset).read_text(
            encoding="utf-8"
        )
        review_contract = " ".join(review_text.replace("`", "").split())
        final_contract = " ".join(final_text.replace("`", "").split())
        for fragment in (
            "producer.attempt",
            "current positive",
            "gc.build.implementation_summary_path",
            "exactly one",
        ):
            assert fragment in review_contract, (
                f"{pack_name} review producer omits {fragment!r}"
            )
        for fragment in (
            "current positive",
            "gc.attempt",
            "gc.build.implementation_summary_path",
            "gc.build.review_report_path",
            "exactly once",
        ):
            assert fragment in final_contract, (
                f"{pack_name} final producer omits {fragment!r}"
            )


@pytest.mark.parametrize(
    "pack_name",
    ("gascity", "superpowers", "compound-engineering", "gstack", "bmad"),
)
def test_validate_build_basic_artifacts_rejects_wrong_pack_identity(
    tmp_path,
    pack_name: str,
) -> None:
    rig_dir = tmp_path / pack_name
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(
        rig_dir,
        identities=PACK_BUILD_ARTIFACT_IDENTITIES[pack_name],
    )
    plan_path = Path(metadata["gc.build.plan_path"])
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8").replace(
            f"  pack: {pack_name}\n",
            "  pack: wrong-pack\n",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=rf"gc\.build\.plan_path methodology\.pack.*{re.escape(pack_name)}.*wrong-pack",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
            pack_spec=gascity_pack_inference_gate.PACK_SPECS[pack_name],
        )


def test_validate_build_basic_artifacts_accepts_current_stage_attempts(tmp_path) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(rig_dir)

    gascity_pack_inference_gate.validate_build_basic_artifacts(
        successful_build_basic_root(metadata),
        rig_dir=rig_dir,
        env={},
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        beads=build_basic_success_beads(
            Path(metadata["gc.build.review_report_path"]),
        ),
    )


@pytest.mark.parametrize(
    "pack_name",
    ("superpowers", "compound-engineering", "gstack", "bmad"),
)
def test_validate_build_basic_artifacts_accepts_current_derived_pack_lineage(
    tmp_path,
    pack_name: str,
) -> None:
    rig_dir = tmp_path / pack_name
    rig_dir.mkdir()
    attempts = {
        metadata_key: attempt
        for attempt, (metadata_key, _) in enumerate(
            gascity_pack_inference_gate.BUILD_BASIC_ARTIFACT_CONTRACTS,
            start=2,
        )
    }
    metadata = write_build_basic_artifacts(
        rig_dir,
        identities=PACK_BUILD_ARTIFACT_IDENTITIES[pack_name],
        attempts=attempts,
    )

    gascity_pack_inference_gate.validate_build_basic_artifacts(
        successful_build_basic_root(metadata),
        rig_dir=rig_dir,
        env={},
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        beads=derived_build_success_beads(stage_attempts=attempts),
        pack_spec=gascity_pack_inference_gate.PACK_SPECS[pack_name],
    )


@pytest.mark.parametrize(
    "pack_name",
    ("superpowers", "compound-engineering", "gstack", "bmad"),
)
@pytest.mark.parametrize(
    "artifact_key",
    ("gc.build.review_report_path", "gc.build.final_report_path"),
)
def test_validate_build_basic_artifacts_rejects_stale_derived_producer_attempt(
    tmp_path,
    pack_name: str,
    artifact_key: str,
) -> None:
    rig_dir = tmp_path / pack_name
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(
        rig_dir,
        identities=PACK_BUILD_ARTIFACT_IDENTITIES[pack_name],
    )
    current_attempts = {artifact_key: 2}

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=rf"{re.escape(artifact_key)}.*producer\.attempt.*current.*2.*1",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
            beads=derived_build_success_beads(stage_attempts=current_attempts),
            pack_spec=gascity_pack_inference_gate.PACK_SPECS[pack_name],
        )


@pytest.mark.parametrize(
    "pack_name",
    ("superpowers", "compound-engineering", "gstack", "bmad"),
)
@pytest.mark.parametrize(
    ("artifact_key", "upstream_key"),
    (
        ("gc.build.review_report_path", "gc.build.implementation_summary_path"),
        ("gc.build.final_report_path", "gc.build.implementation_summary_path"),
        ("gc.build.final_report_path", "gc.build.review_report_path"),
    ),
)
def test_validate_build_basic_artifacts_rejects_disconnected_derived_lineage(
    tmp_path,
    pack_name: str,
    artifact_key: str,
    upstream_key: str,
) -> None:
    rig_dir = tmp_path / pack_name
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(
        rig_dir,
        identities=PACK_BUILD_ARTIFACT_IDENTITIES[pack_name],
    )
    artifact = Path(metadata[artifact_key])
    current_upstream = Path(metadata[upstream_key])
    stale_upstream = rig_dir / f"stale-{current_upstream.name}"
    stale_upstream.write_bytes(current_upstream.read_bytes())
    old_artifact_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            f"    - path: {current_upstream.resolve()}\n",
            f"    - path: {stale_upstream.resolve()}\n",
            1,
        ),
        encoding="utf-8",
    )
    if artifact_key == "gc.build.review_report_path":
        final_report = Path(metadata["gc.build.final_report_path"])
        new_artifact_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        final_report.write_text(
            final_report.read_text(encoding="utf-8").replace(
                f"sha256:{old_artifact_digest}",
                f"sha256:{new_artifact_digest}",
                1,
            ),
            encoding="utf-8",
        )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=rf"{re.escape(artifact_key)}.*exact current.*{re.escape(upstream_key)}",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
            beads=derived_build_success_beads(),
            pack_spec=gascity_pack_inference_gate.PACK_SPECS[pack_name],
        )


def test_validate_build_basic_artifacts_rejects_artifact_outside_current_root(tmp_path) -> None:
    rig_dir = tmp_path / "fixture"
    artifact_root = rig_dir / "current-artifacts"
    outside_root = tmp_path / "stale-run"
    artifact_root.mkdir(parents=True)
    outside_root.mkdir()
    metadata = write_build_basic_artifacts(artifact_root)
    current_final = Path(metadata["gc.build.final_report_path"])
    stale_final = outside_root / current_final.name
    current_final.rename(stale_final)
    metadata["gc.build.final_report_path"] = str(stale_final)

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"gc\.build\.final_report_path.*artifact root",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata, artifact_root=artifact_root),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


def test_validate_build_basic_artifacts_binds_workflow_id_to_current_root(tmp_path) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(rig_dir)
    final_report = Path(metadata["gc.build.final_report_path"])
    final_report.write_text(
        final_report.read_text(encoding="utf-8").replace(
            "  id: fi-root\n",
            "  id: fi-stale\n",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"gc\.build\.final_report_path.*workflow\.id.*fi-root.*fi-stale",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


def test_validate_build_basic_artifacts_rejects_stale_review_producer_attempt(tmp_path) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(rig_dir)
    review_report = Path(metadata["gc.build.review_report_path"])
    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"gc\.build\.review_report_path.*producer\.attempt.*current.*2.*1",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
            beads=build_basic_success_beads(review_report, review_attempt=2),
        )


def test_validate_build_basic_artifacts_rejects_old_terminal_when_newer_review_attempt_exists(
    tmp_path,
) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(rig_dir)
    review_report = Path(metadata["gc.build.review_report_path"])
    beads = build_basic_success_beads(review_report)
    beads.append(
        {
            "id": "fi-current-acceptance-attempt-2",
            "status": "closed",
            "metadata": {
                "gc.root_bead_id": "fi-root",
                "gc.attempt": "2",
                "gc.ralph_step_id": "review.build-basic-review-loop",
                "gc.step_id": "review.acceptance-review",
                "gc.scope_role": "member",
                "gc.outcome": "pass",
                "code_review.acceptance_verdict": "approve",
            },
        }
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"current review attempt 2.*exactly one closed/pass reported terminal",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
            beads=beads,
        )


@pytest.mark.parametrize(
    ("artifact_key", "upstream_key"),
    (
        ("gc.build.review_report_path", "gc.build.implementation_summary_path"),
        ("gc.build.final_report_path", "gc.build.review_report_path"),
    ),
)
def test_validate_build_basic_artifacts_requires_exact_current_report_upstream(
    tmp_path,
    artifact_key: str,
    upstream_key: str,
) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(rig_dir)
    artifact = Path(metadata[artifact_key])
    current_upstream = Path(metadata[upstream_key])
    stale_upstream = rig_dir / f"stale-{current_upstream.name}"
    stale_upstream.write_bytes(current_upstream.read_bytes())
    original_artifact_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            f"    - path: {current_upstream.resolve()}\n",
            f"    - path: {stale_upstream.resolve()}\n",
            1,
        ),
        encoding="utf-8",
    )
    if artifact_key == "gc.build.review_report_path":
        final_report = Path(metadata["gc.build.final_report_path"])
        new_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        final_report.write_text(
            final_report.read_text(encoding="utf-8").replace(
                f"sha256:{original_artifact_digest}",
                f"sha256:{new_digest}",
                1,
            ),
            encoding="utf-8",
        )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=rf"{re.escape(artifact_key)}.*exact current.*{re.escape(upstream_key)}",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


def test_validate_build_basic_artifacts_resolve_repo_relative_sha_from_rig_root(tmp_path) -> None:
    rig_dir = tmp_path / "fixture"
    artifact_dir = rig_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    source = rig_dir / "source.md"
    source.write_text("# Canonical build input\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata = write_build_basic_artifacts(artifact_dir)
    requirements_path = Path(metadata["gc.build.requirements_path"])
    requirements_path.write_text(
        requirements_path.read_text(encoding="utf-8").replace(
            "    - path: fixture\n      hash: literal:test",
            f"    - path: source.md\n      hash: sha256:{digest}",
        ),
        encoding="utf-8",
    )

    gascity_pack_inference_gate.validate_build_basic_artifacts(
        successful_build_basic_root(metadata),
        rig_dir=rig_dir,
        env={},
        validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
    )


def test_validate_build_basic_artifacts_rejects_json_artifacts(tmp_path) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(rig_dir)
    bad_path = Path(metadata["gc.build.requirements_path"])
    bad_path.write_text('{"schema":"gc.build.requirements.v1"}\n', encoding="utf-8")

    with pytest.raises(gascity_pack_inference_gate.GateError, match="failed validation"):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


@pytest.mark.parametrize(
    ("metadata_key", "status"),
    (
        ("gc.build.requirements_path", "questions"),
        ("gc.build.plan_path", "draft"),
        ("gc.build.decomposition_path", "changes_required"),
        ("gc.build.implementation_summary_path", "draft"),
    ),
)
def test_validate_build_basic_artifacts_requires_approved_pre_review_stages(
    tmp_path, metadata_key: str, status: str
) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(rig_dir, statuses={metadata_key: status})

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=rf"{re.escape(metadata_key)}.*status=approved.*{status}",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


@pytest.mark.parametrize(
    "case",
    ("approved-with-blocked-coverage", "changes-required-without-blocked-coverage"),
)
def test_validate_build_basic_artifacts_enforces_review_status_coverage_coherence(
    tmp_path, case: str
) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    if case == "approved-with-blocked-coverage":
        metadata = write_build_basic_artifacts(rig_dir)
        review_text = valid_review_artifact("approved").replace(
            "      status: covered\n",
            "      status: blocked\n"
            "      rationale: A required remediation remains unresolved.\n",
            1,
        ).replace("| AC1 | covered |", "| AC1 | blocked |", 1)
        root = successful_build_basic_root(metadata)
    else:
        metadata = write_build_basic_artifacts(
            rig_dir,
            statuses={
                "gc.build.review_report_path": "changes_required",
                "gc.build.final_report_path": "blocked",
            },
        )
        review_text = valid_review_artifact("changes_required").replace(
            "      status: blocked\n"
            "      rationale: The required security remediation remains unresolved.\n",
            "      status: covered\n",
            1,
        ).replace("| AC1 | blocked |", "| AC1 | covered |", 1)
        root = blocked_build_basic_root(metadata)
    Path(metadata["gc.build.review_report_path"]).write_text(review_text, encoding="utf-8")

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"gc\.build\.review_report_path.*failed validation",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            root,
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


@pytest.mark.parametrize("review_status", ("changes_required", "blocked"))
def test_validate_build_basic_artifacts_rejects_false_green_report_review(
    tmp_path, review_status: str
) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(
        rig_dir,
        statuses={"gc.build.review_report_path": review_status},
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=rf"report-mode review status={review_status}.*final status=approved",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


@pytest.mark.parametrize("review_status", ("changes_required", "blocked"))
def test_validate_build_basic_artifacts_rejects_success_lifecycle_for_blocked_final(
    tmp_path, review_status: str
) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(
        rig_dir,
        statuses={
            "gc.build.review_report_path": review_status,
            "gc.build.final_report_path": "blocked",
        },
    )
    root = successful_build_basic_root(metadata)
    root["metadata"]["gc.outcome"] = "fail"

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=rf"report-mode review status={review_status}.*blocked final report.*gc.build.status",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            root,
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


def test_validate_build_basic_artifacts_rejects_blocked_final_after_approved_review(tmp_path) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    metadata = write_build_basic_artifacts(
        rig_dir,
        statuses={"gc.build.final_report_path": "blocked"},
    )

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"report-mode review status=approved.*final status=blocked",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            successful_build_basic_root(metadata),
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


@pytest.mark.parametrize("review_mode", ("", "agent"), ids=("missing", "agent"))
def test_validate_build_basic_artifacts_requires_report_review_mode(
    tmp_path, review_mode: str
) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    root = successful_build_basic_root(write_build_basic_artifacts(rig_dir))
    if review_mode:
        root["metadata"]["gc.var.review_mode"] = review_mode
    else:
        del root["metadata"]["gc.var.review_mode"]

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=r"review mode=report",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            root,
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        ("root-status", "root status"),
        ("root-outcome", "gc.outcome"),
        ("missing-build-status", "gc.build.status"),
        ("finalize-status", "gc.build.finalize_status"),
        ("finalize-outcome", "gc.build.finalize_outcome"),
    ),
)
def test_validate_build_basic_artifacts_requires_success_lifecycle_for_approved_final(
    tmp_path, case: str, expected: str
) -> None:
    rig_dir = tmp_path / "fixture"
    rig_dir.mkdir()
    root = successful_build_basic_root(write_build_basic_artifacts(rig_dir))
    if case == "root-status":
        root["status"] = "open"
    elif case == "root-outcome":
        root["metadata"]["gc.outcome"] = "fail"
    elif case == "missing-build-status":
        del root["metadata"]["gc.build.status"]
    elif case == "finalize-status":
        root["metadata"]["gc.build.finalize_status"] = "failed"
    else:
        root["metadata"]["gc.build.finalize_outcome"] = "failure"

    with pytest.raises(
        gascity_pack_inference_gate.GateError,
        match=rf"approved final report.*{re.escape(expected)}",
    ):
        gascity_pack_inference_gate.validate_build_basic_artifacts(
            root,
            rig_dir=rig_dir,
            env={},
            validator_source=gascity_pack_inference_gate.REPO_ROOT / "gascity",
        )


def valid_review_artifact(status: str) -> str:
    artifact = valid_build_artifact("gc.build.review.v1").replace(
        "status: approved", f"status: {status}", 1
    )
    if status in {"changes_required", "blocked"}:
        artifact = artifact.replace(
            "      status: covered\n",
            "      status: blocked\n"
            "      rationale: The required security remediation remains unresolved.\n",
            1,
        ).replace("| AC1 | covered |", "| AC1 | blocked |", 1)
    return (
        artifact
        + """
## Security Finding

The reviewed diff uses `subprocess.run(..., shell=True)` with user-controlled
paths, which creates a shell injection risk.

## Remediation

The terminal report verifies the fix: use an argument vector / argument list
with `shell=False`, and mark SEC-001 covered after tests pass.
"""
    )


def review_artifact_traced_to_subject(
    subject_path: Path,
    *,
    status: str,
    hash_value: str = "",
) -> str:
    digest = hash_value or f"sha256:{hashlib.sha256(subject_path.read_bytes()).hexdigest()}"
    return valid_review_artifact(status=status).replace(
        "    - path: fixture\n      hash: literal:test",
        f"    - path: {subject_path}\n      hash: {digest}",
        1,
    )


def valid_build_artifact(schema: str) -> str:
    sections_by_schema = {
        "gc.build.requirements.v1": [
            "Problem Statement",
            "W6H",
            "User Stories",
            "Technical Stories",
            "Behavior Requirements",
            "Example Mapping",
            "Acceptance Criteria",
            "Out Of Scope",
            "Open Questions",
        ],
        "gc.build.plan.v1": [
            "Summary",
            "Current System",
            "Proposed Implementation",
            "Non-Goals",
            "Verification",
        ],
        "gc.build.decomposition.v1": [
            "Summary",
            "Selected Downstream Formulas",
            "Implementation Convoy",
            "Work Items",
        ],
        "gc.build.implementation-summary.v1": [
            "Summary",
            "Intended Behavior",
            "Changed Files",
            "Verification",
            "Remaining Risks",
        ],
        "gc.build.review.v1": [
            "Verdict",
            "Findings",
            "Verification",
        ],
        "gc.build.final-report.v1": [
            "Summary",
            "Outcome",
            "Artifacts",
            "Remaining Risks",
        ],
    }
    sections = sections_by_schema[schema]
    body = "\n".join(f"## {section}\n\nCovered.\n" for section in sections)
    return f"""\
---
schema: {schema}
workflow:
  id: fi-root
  formula: build-basic
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: build-basic
  stage: test
  attempt: 1
status: approved
trace:
  upstream:
    - path: fixture
      hash: literal:test
      ids:
        - AC1
  coverage:
    - id: AC1
      status: covered
---
| ID | Status |
| --- | --- |
| AC1 | covered |

{body}
"""
