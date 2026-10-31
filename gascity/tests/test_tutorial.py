"""Tutorial setup owns only its new practice repository and preserves retries."""
import importlib.util
from pathlib import Path
import subprocess
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "assets/scripts/tutorial.py"

@pytest.fixture
def tutorial():
    spec = importlib.util.spec_from_file_location("tutorial", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_practice_project_is_local_and_starts_with_reproducible_bug(tutorial, tmp_path):
    repo = tmp_path / "practice"
    tutorial.scaffold(repo)
    assert subprocess.check_output(["git", "-C", str(repo), "remote"], text=True) == ""
    assert subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True) == ""
    result = subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests"], cwd=repo, capture_output=True)
    assert result.returncode == 1
    assert b"AssertionError" in result.stderr


def test_retry_preserves_task_changes(tutorial, tmp_path):
    repo = tmp_path / "practice"
    tutorial.scaffold(repo)
    (repo / "hello.py").write_text("# preserve my unfinished work\n")
    tutorial.scaffold(repo)
    assert (repo / "hello.py").read_text() == "# preserve my unfinished work\n"


def test_refuses_unowned_existing_path(tutorial, tmp_path):
    repo = tmp_path / "practice"
    repo.mkdir()
    (repo / "keep.txt").write_text("mine")
    with pytest.raises(ValueError, match="existing"):
        tutorial.scaffold(repo)
    assert (repo / "keep.txt").read_text() == "mine"
