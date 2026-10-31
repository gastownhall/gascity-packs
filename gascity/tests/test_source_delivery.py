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
