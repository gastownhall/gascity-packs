"""Source delivery must prove the commit, not just close workflow beads."""
import importlib.util
from pathlib import Path
import subprocess
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "assets/scripts/source_delivery.py"

def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

@pytest.fixture
def delivery(tmp_path):
    spec = importlib.util.spec_from_file_location("source_delivery", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Delivery test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "app.txt").write_text("before\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")
    base = git(repo, "rev-parse", "HEAD")
    tree = tmp_path / "worktree"
    git(repo, "worktree", "add", "-b", "task", str(tree), base)
    (tree / "app.txt").write_text("after\n")
    git(tree, "commit", "-am", "implement")
    output = git(tree, "rev-parse", "HEAD")
    return module, repo, tree, base, output

def test_local_delivery_without_origin_and_retry(delivery):
    mod, repo, tree, base, output = delivery
    assert git(repo, "remote") == ""
    assert mod.integrate(repo, tree, base, output, output, output) == output
    assert (repo / "app.txt").read_text() == "after\n"
    assert mod.integrate(repo, tree, base, output, output, output) == output

@pytest.mark.parametrize("evidence", ["review", "test"])
def test_rejects_stale_evidence(delivery, evidence):
    mod, repo, tree, base, output = delivery
    reviewed, tested = (base, output) if evidence == "review" else (output, base)
    with pytest.raises(ValueError, match="same commit"):
        mod.integrate(repo, tree, base, output, reviewed, tested)
    assert git(repo, "rev-parse", "HEAD") == base

@pytest.mark.parametrize("dirty", ["repo", "worktree"])
def test_never_integrates_dirty_checkout(delivery, dirty):
    mod, repo, tree, base, output = delivery
    ((repo if dirty == "repo" else tree) / "untracked.txt").write_text("keep me")
    with pytest.raises(ValueError, match="dirty"):
        mod.integrate(repo, tree, base, output, output, output)
    assert git(repo, "rev-parse", "HEAD") == base

def test_rejects_moved_integration_input(delivery):
    mod, repo, tree, base, output = delivery
    (repo / "other.txt").write_text("another task")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "concurrent input")
    advanced = git(repo, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="input changed"):
        mod.integrate(repo, tree, base, output, output, output)
    assert git(repo, "rev-parse", "HEAD") == advanced

def test_rejects_unreviewed_output_mutation(delivery):
    mod, repo, tree, base, output = delivery
    (tree / "app.txt").write_text("unreviewed\n")
    git(tree, "commit", "-am", "unreviewed")
    with pytest.raises(ValueError, match="output changed"):
        mod.integrate(repo, tree, base, output, output, output)
    assert git(repo, "rev-parse", "HEAD") == base

@pytest.mark.parametrize("identity", ["HEAD", "--help", "", "abc123"])
def test_requires_immutable_commit_ids(delivery, identity):
    mod, repo, tree, base, output = delivery
    with pytest.raises(ValueError, match="commit SHA"):
        mod.integrate(repo, tree, base, identity, identity, identity)
    assert git(repo, "rev-parse", "HEAD") == base

def test_refuses_launcher_as_implementation_tree(delivery):
    mod, repo, tree, base, output = delivery
    with pytest.raises(ValueError, match="isolated"):
        mod.integrate(repo, repo, base, output, output, output)


def test_refuses_unrelated_repository(delivery, tmp_path):
    mod, repo, tree, base, output = delivery
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "--no-local", str(repo), str(other)], check=True, capture_output=True)
    with pytest.raises(ValueError, match="different repository"):
        mod.integrate(repo, other, base, output, output, output)


def test_store_outage_does_not_spend_content_repair_budget(delivery, monkeypatch):
    mod, repo, tree, base, output = delivery
    def unavailable(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["gc", "bd", "show"])
    monkeypatch.setattr(subprocess, "check_output", unavailable)
    with pytest.raises(mod.InfrastructureError):
        mod.gc("gc", "bd", "show", "task-1", "--json", json_output=True)


def test_store_queries_use_the_invoking_gc_binary(delivery, monkeypatch):
    mod, repo, tree, base, output = delivery
    commands = []
    def capture(command, **kwargs):
        commands.append(command)
        return "{}"
    monkeypatch.setattr(subprocess, "check_output", capture)
    monkeypatch.setenv("GC_BIN", "/candidate/bin/gc")
    assert mod.gc("gc", "bd", "show", "task-1", "--json", json_output=True) == {}
    assert commands == [["/candidate/bin/gc", "bd", "show", "task-1", "--json"]]
    with pytest.raises(ValueError, match="explicit gc"):
        mod.gc("bd", "show", "task-1")


def test_prepare_links_native_source_finalization_before_provisioning(delivery, tmp_path, monkeypatch):
    mod, repo, tree, base, output = delivery
    calls = []
    def observe(*args, **kwargs):
        calls.append(args)
        if args[:3] == ("gc", "rig", "list"):
            return {"rigs": [{"path": str(repo), "default_branch": "main"}]}
        if args[:3] == ("gc", "bd", "show"):
            return {"id": args[3], "status": "open", "metadata": {"gc.root_store_ref": "rig:practice"}}
        if args[:3] == ("gc", "worktree", "ensure"):
            assert any("gc.source_bead_id=task-1" in call and "gc.source_store_ref=rig:practice" in call for call in calls)
            assert args[args.index("--store-ref") + 1] == "rig:practice"
            return {"provenance": {"attempt_id": "owned-attempt"}}
        if args[:3] == ("gc", "bd", "update"):
            return ""
        raise AssertionError(args)
    monkeypatch.setattr(mod, "gc", observe)
    record = mod.prepare("flow-1", "task-1", repo, tmp_path / "owned", "true")
    assert record["store_ref"] == "rig:practice"
    assert record["base_sha"] == base


def test_integration_leaves_source_open_for_required_cleanup_and_finalization(delivery, monkeypatch):
    mod, repo, tree, base, output = delivery
    record = dict(root="flow-1", source="task-1", repo=str(repo), worktree=str(tree),
                  worktree_root=str(tree.parent), branch="task", base_ref="refs/heads/main",
                  base_sha=base, reviewed_sha=output, tested_sha=output,
                  output_sha=output, review_status="approved", attempt_id="owned-attempt")
    calls, saved = [], []
    def observe(*args, **kwargs):
        calls.append(args)
        if args[:3] == ("gc", "worktree", "verify"):
            return {"ok": True}
        if args[:4] == ("gc", "bd", "update", "task-1"):
            assert git(repo, "rev-parse", "HEAD") == output
            assert "gc.delivery.integrated_sha=" + output in args
            return ""
        raise AssertionError(f"source closure belongs to the native finalizer: {args}")
    monkeypatch.setattr(mod, "load", lambda root: dict(record))
    monkeypatch.setattr(mod, "save", lambda root, value: saved.append(dict(value)))
    monkeypatch.setattr(mod, "gc", observe)
    monkeypatch.setattr("sys.argv", ["source-delivery", "integrate", "--root", "flow-1"])
    mod.main()
    assert git(repo, "rev-parse", "HEAD") == output
    assert saved[-1]["integrated_sha"] == output
    assert not any("close" in call for call in calls)


def test_local_input_uses_configured_default_branch(delivery):
    mod, repo, tree, base, output = delivery
    assert mod.task_input(repo, "main") == ("refs/heads/main", base, base)
    with pytest.raises(ValueError, match="configured default branch"):
        mod.task_input(repo, "feature")


def test_remote_input_fast_forwards_clean_default_checkout(delivery, tmp_path):
    mod, repo, tree, base, output = delivery
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(tree, "push", "origin", "HEAD:refs/heads/main")
    assert mod.task_input(repo, "main") == ("refs/heads/main", output, output)
    assert git(repo, "rev-parse", "HEAD") == output
    assert mod.integrate(repo, tree, output, output, output, output) == output


def test_remote_input_preserves_local_mainline_commits(delivery, tmp_path):
    mod, repo, tree, base, output = delivery
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    (repo / "local.txt").write_text("preserve local work")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "local work")
    local = git(repo, "rev-parse", "HEAD")
    assert mod.task_input(repo, "main") == ("refs/heads/main", local, local)
    assert (repo / "local.txt").read_text() == "preserve local work"
    git(tree, "push", "origin", "HEAD:refs/heads/main")
    with pytest.raises(ValueError, match="diverged"):
        mod.task_input(repo, "main")
    assert git(repo, "rev-parse", "HEAD") == local


def test_remote_fetch_failure_is_infrastructure_blocker(delivery, tmp_path):
    mod, repo, tree, base, output = delivery
    git(repo, "remote", "add", "origin", str(tmp_path / "unavailable"))
    with pytest.raises(mod.InfrastructureError, match="cannot fetch"):
        mod.task_input(repo, "main")
    assert git(repo, "rev-parse", "HEAD") == base

def test_fetched_default_input_supports_native_local_integration_cleanup(delivery, tmp_path):
    import json
    import os
    gc_bin = os.environ.get("GC_TEST_BIN")
    if not gc_bin:
        pytest.skip("set GC_TEST_BIN for native worktree lifecycle qualification")
    mod, repo, tree, base, remote_output = delivery
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(tree, "push", "origin", "HEAD:refs/heads/main")
    base_ref, input_sha, predecessor = mod.task_input(repo, "main")
    root = tmp_path / "owned"
    owned = root / "flow-1"
    args = ["--repo", str(repo), "--root", str(root), "--path", str(owned),
            "--branch", "gc/flow-1", "--base", base_ref, "--base-sha", input_sha,
            "--bead", "task-1", "--store-ref", "rig:practice", "--creator", "formula-quick-start",
            "--owner", "formula", "--generation", "flow-1", "--json"]
    report = json.loads(subprocess.check_output([gc_bin, "worktree", "ensure", *args], text=True))
    (owned / "next.txt").write_text("next accepted task\n")
    git(owned, "add", ".")
    git(owned, "commit", "-m", "next local delivery")
    output = git(owned, "rev-parse", "HEAD")
    mod.integrate(repo, owned, predecessor, output, output, output)
    cleanup = subprocess.run([gc_bin, "worktree", "cleanup", *args,
                              "--attempt-id", report["provenance"]["attempt_id"]],
                             text=True, capture_output=True)
    assert cleanup.returncode == 0, cleanup.stdout + cleanup.stderr
    assert not owned.exists()
    assert git(repo, "rev-parse", "HEAD") == output


@pytest.mark.parametrize("change", ["dirty", "commit", "branch"])
def test_remote_input_refuses_checkout_changes_during_fetch(delivery, tmp_path, monkeypatch, change):
    mod, repo, tree, base, output = delivery
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(tree, "push", "origin", "HEAD:refs/heads/main")
    original_git = mod.git
    def changed_during_fetch(path, *args):
        result = original_git(path, *args)
        if args[0] == "fetch":
            if change == "branch":
                git(repo, "switch", "-c", "user-work")
            else:
                (repo / "user.txt").write_text("preserve concurrent user work")
                if change == "commit":
                    git(repo, "add", ".")
                    git(repo, "commit", "-m", "concurrent user work")
        return result
    monkeypatch.setattr(mod, "git", changed_during_fetch)
    with pytest.raises(ValueError, match="dirty checkout|changed during fetch"):
        mod.task_input(repo, "main")
    assert git(repo, "rev-parse", "refs/heads/main") != output
    if change != "branch":
        assert (repo / "user.txt").read_text() == "preserve concurrent user work"
    else:
        assert git(repo, "symbolic-ref", "--short", "HEAD") == "user-work"


@pytest.mark.parametrize("failure", ["missing", "not-executable", "configuration", "temporary"])
def test_verifier_launch_failure_does_not_spend_content_repair_budget(delivery, tmp_path, monkeypatch, failure):
    mod, repo, tree, base, output = delivery
    validator = tmp_path / "validator"
    if failure == "not-executable":
        validator.write_text("#!/bin/sh\nexit 0\n")
        validator.chmod(0o644)
    if failure in ("configuration", "temporary"):
        validator.write_text("#!/bin/sh\nexit " + ("78" if failure == "configuration" else "75") + "\n")
        validator.chmod(0o755)
    record = dict(root="flow-1", source="task-1", repo=str(repo), worktree=str(tree),
                  worktree_root=str(tree.parent), branch="task", base_ref="refs/heads/main",
                  base_sha=base, reviewed_sha=output, review_status="approved",
                  verify_command=str(validator), attempt_id="owned-attempt")
    monkeypatch.setattr(mod, "load", lambda root: dict(record))
    def observe(*args, **kwargs):
        assert args[:3] == ("gc", "worktree", "verify"), args
        return {"ok": True}
    monkeypatch.setattr(mod, "gc", observe)
    monkeypatch.setattr(mod, "save", lambda *args: pytest.fail("unexecuted validator cannot record tested output"))
    with pytest.raises(mod.InfrastructureError, match="verification command.*(75|78|126|127)"):
        mod.verify_output("flow-1")
    assert git(tree, "rev-parse", "HEAD") == output
    assert git(repo, "rev-parse", "HEAD") == base
    assert "tested_sha" not in record


def test_failed_repository_verification_remains_a_content_verdict(delivery, monkeypatch):
    mod, repo, tree, base, output = delivery
    record = dict(root="flow-1", source="task-1", repo=str(repo), worktree=str(tree),
                  worktree_root=str(tree.parent), branch="task", base_ref="refs/heads/main",
                  base_sha=base, reviewed_sha=output, review_status="approved",
                  verify_command="false", attempt_id="owned-attempt")
    monkeypatch.setattr(mod, "load", lambda root: dict(record))
    monkeypatch.setattr(mod, "gc", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(mod, "save", lambda *args: pytest.fail("failed verification cannot record tested output"))
    with pytest.raises(ValueError, match="verification failed with exit 1"):
        mod.verify_output("flow-1")
    assert git(repo, "rev-parse", "HEAD") == base


def test_actual_validator_dependency_failure_uses_its_selected_interpreter(delivery, tmp_path, monkeypatch, capsys):
    import shlex
    import sys
    mod, repo, tree, base, output = delivery
    report = tmp_path / "review.md"
    report.write_text('---\nkind: review\nverdict: pass\nseverity: none\nsummary: Reviewed the change\nfindings: []\n---\n')
    validator = SCRIPT.parent / "validate_verdict_report.py"
    # -S exercises the actual validator with this exact interpreter while its
    # third-party site packages are unavailable. No validator exit is stubbed.
    command = shlex.join([sys.executable, "-S", str(validator), str(report), "--kind", "review"])
    record = dict(root="flow-1", source="task-1", repo=str(repo), worktree=str(tree),
                  worktree_root=str(tree.parent), branch="task", base_ref="refs/heads/main",
                  base_sha=base, reviewed_sha=output, review_status="approved",
                  verify_command=command, attempt_id="owned-attempt")
    monkeypatch.setattr(mod, "load", lambda root: dict(record))
    monkeypatch.setattr(mod, "gc", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(mod, "save", lambda *args: pytest.fail("unavailable validator cannot record a verdict"))
    with pytest.raises(mod.InfrastructureError, match="verification command.*78"):
        mod.verify_output("flow-1")
    diagnostic = capsys.readouterr().out
    assert "PyYAML not importable" in diagnostic
    assert sys.executable in diagnostic
    assert git(repo, "rev-parse", "HEAD") == base


@pytest.mark.parametrize("failure,expected", [("missing", 78), ("module", 78), ("temporary", 75)])
def test_cli_preserves_dispatcher_configuration_hold_protocol(delivery, tmp_path, monkeypatch, capsys, failure, expected):
    import json
    import runpy
    import shlex
    import sys
    mod, repo, tree, base, output = delivery
    validator = tmp_path / "validator"
    if failure == "module":
        report = tmp_path / "review.md"
        report.write_text("---\nkind: review\nverdict: pass\nfindings: []\n---\n")
        command = shlex.join([sys.executable, "-S", str(SCRIPT.parent / "validate_verdict_report.py"), str(report)])
    else:
        if failure == "temporary":
            validator.write_text("#!/bin/sh\nexit 75\n")
            validator.chmod(0o755)
        command = str(validator)
    record = dict(root="flow-1", source="task-1", repo=str(repo), worktree=str(tree),
                  worktree_root=str(tree.parent), branch="task", base_ref="refs/heads/main",
                  base_sha=base, reviewed_sha=output, review_status="approved",
                  verify_command=command, attempt_id="owned-attempt")
    original = subprocess.check_output
    def gc_boundary(argv, **kwargs):
        if argv[0] != "gc-contract-probe":
            return original(argv, **kwargs)
        if argv[:4] == ["gc-contract-probe", "bd", "show", "flow-1"]:
            # Native gc bd emits scope information before the validator runs.
            # It must remain visible without replacing the actual hold reason.
            kwargs.get("stderr", sys.stderr).write('gc bd: answering from the rig "practice" store\n')
            return json.dumps({"id":"flow-1", "metadata":{"gc.delivery.record":json.dumps(record)}})
        if argv[1:3] == ["worktree", "verify"]:
            return "{}"
        pytest.fail("a failed validator must not write progress: " + repr(argv))
    monkeypatch.setattr(subprocess, "check_output", gc_boundary)
    monkeypatch.setenv("GC_BIN", "gc-contract-probe")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "check", "--root", "flow-1"])
    with pytest.raises(SystemExit) as ended:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert ended.value.code == expected
    diagnostic = capsys.readouterr().err
    first = next(line for line in diagnostic.splitlines() if line.strip())
    assert first.startswith("source delivery " + ("environment:" if expected == 78 else "infrastructure:")), diagnostic
    assert 'gc bd: answering from the rig "practice" store' in diagnostic
    if failure == "module":
        assert "PyYAML not importable" in first
        assert sys.executable in first
    assert git(repo, "rev-parse", "HEAD") == base


@pytest.mark.parametrize("unexpected", [False, True])
def test_cli_retains_child_diagnostics_without_corrupting_json(delivery, monkeypatch, capsys, unexpected):
    import json
    import runpy
    import sys
    record = {"root": "flow-1", "source": "task-1"}
    original = subprocess.check_output
    def boundary(argv, **kwargs):
        if argv[0] != "gc-stdio-probe":
            return original(argv, **kwargs)
        assert argv == ["gc-stdio-probe", "bd", "show", "flow-1", "--json"]
        kwargs["stderr"].write("native diagnostic retained\n")
        if unexpected:
            raise RuntimeError("unexpected native boundary bug")
        return json.dumps({"id": "flow-1", "metadata": {"gc.delivery.record": json.dumps(record)}})
    monkeypatch.setattr(subprocess, "check_output", boundary)
    monkeypatch.setenv("GC_BIN", "gc-stdio-probe")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "show", "--root", "flow-1"])
    if unexpected:
        with pytest.raises(RuntimeError, match="unexpected native boundary bug"):
            runpy.run_path(str(SCRIPT), run_name="__main__")
    else:
        with pytest.raises(SystemExit) as ended:
            runpy.run_path(str(SCRIPT), run_name="__main__")
        assert ended.value.code == 0
    captured = capsys.readouterr()
    assert captured.err == "native diagnostic retained\n"
    if not unexpected:
        assert json.loads(captured.out) == record
