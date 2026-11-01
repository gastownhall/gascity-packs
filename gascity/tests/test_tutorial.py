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
        assert args[0] == "gc"
        args = args[1:]
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
        assert args[0] == "gc"
        args = args[1:]
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


def test_registration_changes_are_baselined_before_source_work(tutorial, tmp_path):
    repo = tmp_path / "practice"
    tutorial.scaffold(repo)
    with (repo / ".gitignore").open("a") as stream:
        stream.write("\n# Gas City\n.beads/*\n!.beads/identity.toml\n")
    git = lambda *args: subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
    git("add", ".gitignore")
    skills = repo / ".claude/skills/test-skill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("generated runtime skill")
    tutorial.finish_registration(repo)
    assert git("status", "--porcelain") == ""
    assert (repo / "hello.py").read_text().startswith("def greet")


def test_registration_never_commits_unfinished_source(tutorial, tmp_path):
    repo = tmp_path / "practice"
    tutorial.scaffold(repo)
    (repo / "hello.py").write_text("# unfinished work\n")
    before = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True)
    with pytest.raises(ValueError, match="source changes"):
        tutorial.finish_registration(repo)
    assert subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True) == before


def test_status_does_not_call_skipped_cleanup_a_completed_tutorial(tutorial, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import source_delivery
    destination = tmp_path / "projects/practice"
    def observations(*args, **kwargs):
        assert args[0] == "gc"
        if args[:3] == ("gc", "rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(destination)}]}
        if args[:5] == ("gc", "--rig", "practice", "bd", "list"):
            return [{"id": "practice-1", "status": "closed", "metadata": {
                "gc.delivery.integrated_sha": "a" * 40, "gc.delivery.workflow_root": "flow-1"}}]
        if args[:4] == ("gc", "bd", "show", "flow-1"):
            return {"id": "flow-1", "status": "closed", "metadata": {"gc.outcome": "skipped"}}
        raise AssertionError(args)
    monkeypatch.setattr(source_delivery, "gc", observations)
    monkeypatch.setattr(tutorial, "git", lambda *args: "")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["tutorial", "status"])
    with pytest.raises(ValueError, match="finalization"):
        tutorial.main()


def test_api_lesson_requires_verified_previous_delivery(tutorial, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import source_delivery
    destination = tmp_path / "projects/practice"
    def observations(*args, **kwargs):
        if args[:3] == ("gc", "rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(destination)}]}
        if args[:5] == ("gc", "--rig", "practice", "bd", "list"):
            return [{"id": "pr-first", "status": "open"}] if args[args.index("--metadata-field") + 1] == "gc.tutorial=" + tutorial.MARKER else []
        raise AssertionError(f"an incomplete lesson must not create or submit work: {args}")
    monkeypatch.setattr(source_delivery, "gc", observations)
    monkeypatch.setattr(tutorial, "scaffold", lambda path: path)
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["tutorial", "start", "--lesson", "api"])
    with pytest.raises(ValueError, match="complete"):
        tutorial.main()


def test_client_lesson_records_dependency_before_submitting(tutorial, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import source_delivery
    import json
    destination = tmp_path / "projects/practice"
    calls = []
    api_sha = "a" * 40
    predecessor = {"id": "pr-api", "status": "closed", "metadata": {
        "gc.delivery.integrated_sha": api_sha, "gc.delivery.workflow_root": "flow-api"}}
    def observations(*args, **kwargs):
        calls.append(args)
        if args[:3] == ("gc", "rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(destination)}]}
        if args[:5] == ("gc", "--rig", "practice", "bd", "list"):
            marker = args[args.index("--metadata-field") + 1]
            return [predecessor] if marker == "gc.tutorial=" + tutorial.MARKER + ":api" else []
        if args[:4] == ("gc", "bd", "show", "flow-api"):
            return {"id": "flow-api", "status": "closed", "metadata": {"gc.outcome": "pass", "gc.delivery.record": json.dumps({"cleanup_complete": True, "worktree": str(tmp_path / "retired"), "output_sha": api_sha, "reviewed_sha": api_sha, "tested_sha": api_sha, "integrated_sha": api_sha, "review_status": "approved"})}}
        if args[:5] == ("gc", "--rig", "practice", "bd", "create"):
            assert api_sha in args[args.index("--description") + 1]
            assert args[args.index("--deps") + 1] == "pr-api"
            return {"id": "pr-client", "status": "open"}
        if args[:4] == ("gc", "--rig", "practice", "sling"):
            assert any(call[:5] == ("gc", "--rig", "practice", "bd", "create") and "--deps" in call for call in calls)
            assert args[4:6] == ("practice/gc.run-operator", "pr-client")
            return "routed\n"
        raise AssertionError(args)
    monkeypatch.setattr(source_delivery, "gc", observations)
    monkeypatch.setattr(tutorial, "scaffold", lambda path: path)
    monkeypatch.setattr(tutorial, "git", lambda *args: "")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["tutorial", "start", "--lesson", "client"])
    tutorial.main()
    assert any(call[:4] == ("gc", "--rig", "practice", "sling") for call in calls)


def test_client_lesson_refuses_closed_api_without_cleanup_evidence(tutorial, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import source_delivery
    destination = tmp_path / "projects/practice"
    def observations(*args, **kwargs):
        if args[:3] == ("gc", "rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(destination)}]}
        if args[:5] == ("gc", "--rig", "practice", "bd", "list"):
            marker = args[args.index("--metadata-field") + 1]
            return [{"id": "pr-api", "status": "closed", "metadata": {"gc.delivery.integrated_sha": "a" * 40, "gc.delivery.workflow_root": "flow-api"}}] if marker.endswith(":api") else []
        if args[:4] == ("gc", "bd", "show", "flow-api"):
            return {"id": "flow-api", "status": "closed", "metadata": {"gc.outcome": "skipped"}}
        raise AssertionError(f"invalid predecessor must not create work: {args}")
    monkeypatch.setattr(source_delivery, "gc", observations)
    monkeypatch.setattr(tutorial, "scaffold", lambda path: path)
    monkeypatch.setattr(tutorial, "git", lambda *args: "")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["tutorial", "start", "--lesson", "client"])
    with pytest.raises(ValueError, match="finalization"):
        tutorial.main()


@pytest.mark.parametrize("field,bad_value", [
    ("reviewed_sha", "b" * 40), ("tested_sha", "b" * 40),
    ("output_sha", "b" * 40), ("integrated_sha", "b" * 40),
    ("review_status", "rejected"),
])
def test_status_rejects_inconsistent_delivery_evidence(tutorial, tmp_path, field, bad_value):
    import json
    sha = "a" * 40
    record = {"cleanup_complete": True, "worktree": str(tmp_path / "retired"),
              "output_sha": sha, "reviewed_sha": sha, "tested_sha": sha,
              "integrated_sha": sha, "review_status": "approved"}
    record[field] = bad_value
    source = {"id": "pr-task", "status": "closed", "metadata": {
        "gc.delivery.integrated_sha": sha, "gc.delivery.workflow_root": "flow"}}
    def observations(*args, **kwargs):
        return {"id": "flow", "status": "closed", "metadata": {
            "gc.outcome": "pass", "gc.delivery.record": json.dumps(record)}}
    tutorial.git = lambda *args: ""
    with pytest.raises(ValueError, match="reviewed and tested"):
        tutorial.verified_delivery(source, tmp_path, observations)
