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


def test_status_reads_existing_task_without_restarting_it(tutorial, tmp_path, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import source_delivery
    destination = tmp_path / "projects/practice"
    def observations(*args, **kwargs):
        if args[:2] == ("rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(destination)}]}
        if args[:4] == ("--rig", "practice", "bd", "list"):
            return [{"id": "practice-1", "status": "open"}]
        raise AssertionError(f"status must not mutate or launch work: {args}")
    monkeypatch.setattr(source_delivery, "gc", observations)
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["tutorial", "status"])
    tutorial.main()
    assert "Source task: practice-1; status: open" in capsys.readouterr().out


def test_start_routes_existing_task_without_manual_rig_defaults(tutorial, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import source_delivery
    destination = tmp_path / "projects/practice"
    calls = []
    def observations(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(destination)}]}
        if args[:4] == ("--rig", "practice", "bd", "list"):
            return [{"id": "practice-1", "status": "open"}]
        if args[:3] == ("--rig", "practice", "sling"):
            assert args[3:5] == ("practice/gc.run-operator", "practice-1")
            return "routed\n"
        raise AssertionError(f"retry must reuse the existing task: {args}")
    monkeypatch.setattr(source_delivery, "gc", observations)
    monkeypatch.setattr(tutorial, "scaffold", lambda path: path)
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["tutorial", "start"])
    tutorial.main()
    assert len([call for call in calls if call[:3] == ("--rig", "practice", "sling")]) == 1
