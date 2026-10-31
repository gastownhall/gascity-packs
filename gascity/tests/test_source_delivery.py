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


def test_remote_input_fetches_new_default_commit_without_moving_checkout(delivery, tmp_path):
    mod, repo, tree, base, output = delivery
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(tree, "push", "origin", "HEAD:refs/heads/main")
    assert mod.task_input(repo, "main") == ("refs/remotes/origin/main", output, base)
    assert git(repo, "rev-parse", "HEAD") == base
    assert mod.integrate(repo, tree, base, output, output, output) == output


def test_remote_input_refuses_unpublished_local_commits(delivery, tmp_path):
    mod, repo, tree, base, output = delivery
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    (repo / "local.txt").write_text("preserve local work")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "local work")
    with pytest.raises(ValueError, match="unpublished or divergent"):
        mod.task_input(repo, "main")
    assert (repo / "local.txt").read_text() == "preserve local work"


def test_remote_fetch_failure_is_infrastructure_blocker(delivery, tmp_path):
    mod, repo, tree, base, output = delivery
    git(repo, "remote", "add", "origin", str(tmp_path / "unavailable"))
    with pytest.raises(mod.InfrastructureError, match="cannot fetch"):
        mod.task_input(repo, "main")
    assert git(repo, "rev-parse", "HEAD") == base
