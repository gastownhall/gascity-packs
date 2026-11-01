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
        if args[:4] == ("--rig", "practice", "bd", "dep"):
            return []
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
        if args[:4] == ("--rig", "practice", "bd", "dep"):
            return []
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
        if args[:5] == ("gc", "--rig", "practice", "bd", "dep"):
            return []
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


@pytest.mark.parametrize("status", ["open", "in_progress", "closed"])
@pytest.mark.parametrize("recorded_root", [False, True])
def test_start_observes_attached_workflow_instead_of_reslinging(tutorial, tmp_path, monkeypatch, capsys, status, recorded_root):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import source_delivery
    destination = tmp_path / "projects/practice"
    calls = []
    def observations(*args, **kwargs):
        args = args[1:]
        calls.append(args)
        if args[:4] == ("--rig", "practice", "bd", "dep"):
            return []
        if args[:2] == ("rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(destination)}]}
        if args[:4] == ("--rig", "practice", "bd", "list"):
            marker = args[args.index("--metadata-field") + 1]
            if marker.startswith("gc.tutorial="):
                return [{"id": "practice-1", "status": "open",
                         "metadata": {"gc.delivery.workflow_root": "flow-1"} if recorded_root else {}}]
            assert marker == "gc.source_bead_id=practice-1"
            return [{"id": "flow-1", "status": status,
                     "metadata": {"gc.kind": "workflow", "gc.formula_name": "quick-start"}}]
        raise AssertionError(f"an attached workflow must not be replaced or mutated: {args}")
    monkeypatch.setattr(source_delivery, "gc", observations)
    monkeypatch.setattr(tutorial, "scaffold", lambda path: path)
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["tutorial", "start"])
    tutorial.main()
    assert "Existing workflow: flow-1" in capsys.readouterr().out
    assert not any("sling" in call for call in calls)


def test_multiple_live_workflows_require_inspection_without_mutation(tutorial):
    def observations(*args, **kwargs):
        if args[4:6] == ("dep", "list"):
            return []
        return [{"id": name, "status": "open", "metadata": {"gc.kind": "workflow"}}
                for name in ("flow-1", "flow-2")]
    with pytest.raises(ValueError, match="multiple live workflows"):
        tutorial.attached_workflow(observations, {"id": "practice-1"})


def test_active_workflow_wins_over_retained_history(tutorial):
    def observations(*args, **kwargs):
        if args[4:6] == ("dep", "list"):
            return []
        return [{"id": "old", "status": "closed", "metadata": {"gc.kind": "workflow"}},
                {"id": "current", "status": "in_progress", "metadata": {"gc.kind": "workflow"}},
                {"id": "step", "status": "open", "metadata": {"gc.kind": "scope"}}]
    assert tutorial.attached_workflow(observations, {"id": "practice-1"}) == "current"


@pytest.mark.parametrize("attach_during_sling", [False, True])
def test_start_preserves_native_admission_guard(tutorial, tmp_path, monkeypatch, capsys, attach_during_sling):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import source_delivery
    calls = []
    probes = 0
    destination = tmp_path / "projects/practice"
    def observations(*args, **kwargs):
        nonlocal probes
        args = args[1:]
        calls.append(args)
        if args[:4] == ("--rig", "practice", "bd", "dep"):
            return []
        if args[:2] == ("rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(destination)}]}
        if args[:4] == ("--rig", "practice", "bd", "list"):
            marker = args[args.index("--metadata-field") + 1]
            if marker.startswith("gc.tutorial="):
                return [{"id": "practice-1", "status": "open"}]
            probes += 1
            if probes > 1 and attach_during_sling:
                return [{"id": "concurrent", "status": "open", "metadata": {"gc.kind": "workflow"}}]
            return []
        if args[:3] == ("--rig", "practice", "sling"):
            raise source_delivery.InfrastructureError("native admission unavailable")
        raise AssertionError(args)
    monkeypatch.setattr(source_delivery, "gc", observations)
    monkeypatch.setattr(tutorial, "scaffold", lambda path: path)
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["tutorial", "start"])
    if attach_during_sling:
        tutorial.main()
        assert "Existing workflow: concurrent" in capsys.readouterr().out
    else:
        with pytest.raises(source_delivery.InfrastructureError, match="native admission unavailable"):
            tutorial.main()
    assert len([call for call in calls if call[:3] == ("--rig", "practice", "sling")]) == 1
    assert all("--force" not in call and "delete-source" not in call for call in calls)


def test_attached_workflow_read_failure_never_becomes_an_unbound_launch(tutorial):
    def unavailable(*args, **kwargs):
        raise RuntimeError("native binding lookup unavailable")
    with pytest.raises(RuntimeError, match="native binding lookup unavailable"):
        tutorial.attached_workflow(unavailable, {"id": "practice-1"})


@pytest.mark.parametrize("root_status", ["open", "in_progress", "closed"])
@pytest.mark.parametrize("root_kind", ["workflow", "graph.v2"])
def test_retry_follows_native_input_convoy_before_prepare(tutorial, root_status, root_kind):
    """Sling stamps the convoy binding before prepare adds a source back-link."""
    calls = []
    def observations(*args, **kwargs):
        calls.append(args)
        if args[4:6] == ("dep", "list"):
            assert args[6:] == ("practice-1", "--direction", "up", "--type", "tracks", "--json")
            return [{"id": "input-1", "issue_type": "convoy", "status": "closed",
                     "dependency_type": "tracks", "metadata": {"gc.synthetic": "true"}}]
        assert args[4] == "list"
        marker = args[args.index("--metadata-field") + 1]
        if marker == "gc.source_bead_id=practice-1":
            return []
        assert marker == "gc.input_convoy_id=input-1"
        # Model the native visibility contract rather than always returning rows.
        if "--include-ephemeral" not in args:
            return []
        metadata = {"gc.formula_name": "quick-start"}
        metadata["gc.kind" if root_kind == "workflow" else "gc.formula_contract"] = root_kind
        return [{"id": "flow-1", "status": root_status, "metadata": metadata}]
    assert tutorial.attached_workflow(observations, {"id": "practice-1"}) == "flow-1"
    assert all("sling" not in args and "update" not in args for args in calls)


def test_retry_excludes_unrelated_convoy_formulas_and_controller_rows(tutorial):
    def observations(*args, **kwargs):
        if args[4:6] == ("dep", "list"):
            return [
                {"id": "sprint", "issue_type": "convoy", "metadata": {}},
                {"id": "input", "issue_type": "convoy", "metadata": {"gc.synthetic": "true"}},
            ]
        marker = args[args.index("--metadata-field") + 1]
        if marker == "gc.source_bead_id=practice-1":
            return []
        assert marker == "gc.input_convoy_id=input"
        return [
            {"id": "other", "status": "open", "metadata": {
                "gc.kind": "workflow", "gc.formula_name": "review"}},
            {"id": "session", "issue_type": "session", "status": "open", "metadata": {
                "gc.formula_contract": "graph.v2", "gc.formula_name": "quick-start"}},
            {"id": "expected", "status": "open", "metadata": {
                "gc.formula_contract": "graph.v2", "gc.formula_name": "quick-start"}},
        ]
    assert tutorial.attached_workflow(observations, {"id": "practice-1"}) == "expected"


def test_retry_checks_convoy_bindings_even_with_a_direct_root(tutorial):
    def observations(*args, **kwargs):
        if args[4:6] == ("dep", "list"):
            return [{"id": "input", "issue_type": "convoy", "metadata": {"gc.synthetic": "true"}}]
        marker = args[args.index("--metadata-field") + 1]
        root = "direct" if marker.startswith("gc.source_bead_id=") else "convoy"
        return [{"id": root, "status": "open", "metadata": {
            "gc.kind": "workflow", "gc.formula_name": "quick-start"}}]
    with pytest.raises(ValueError, match="multiple live workflows"):
        tutorial.attached_workflow(observations, {"id": "practice-1"})


def test_retry_deduplicates_direct_and_convoy_binding(tutorial):
    def observations(*args, **kwargs):
        if args[4:6] == ("dep", "list"):
            return [{"id": "input", "issue_type": "convoy", "metadata": {"gc.synthetic": "true"}}]
        return [{"id": "same", "status": "open", "metadata": {
            "gc.kind": "workflow", "gc.formula_name": "quick-start"}}]
    assert tutorial.attached_workflow(observations, {"id": "practice-1"}) == "same"


def test_retry_never_relaunches_after_a_convoy_read_failure(tutorial):
    def observations(*args, **kwargs):
        if args[4:6] == ("dep", "list"):
            raise RuntimeError("tracking edge lookup unavailable")
        return []
    with pytest.raises(RuntimeError, match="tracking edge lookup unavailable"):
        tutorial.attached_workflow(observations, {"id": "practice-1"})
