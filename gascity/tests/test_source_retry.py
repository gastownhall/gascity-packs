"""Manual recovery must use native admission and keep failed work/input intact."""
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "assets/scripts/source_delivery.py"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


@pytest.fixture
def failed_delivery(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("retry_delivery_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    repo = tmp_path / "city/projects/practice"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Retry qualification")
    git(repo, "config", "user.email", "retry@example.invalid")
    git(repo, "config", "gascity.tutorial", "rfc8191-first-local-change-v1")
    (repo / "app.txt").write_text("fixed input\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "Record task input")
    base = git(repo, "rev-parse", "HEAD")
    retained = tmp_path / "failed-worktree"
    git(repo, "worktree", "add", "-b", "failed-attempt", str(retained), base)
    (retained / "app.txt").write_text("preserve my unfinished implementation\n")
    verify = "python3 -m unittest discover -s tests -v"
    record = dict(root="wf-old", source="pr-task", repo=str(repo), store_ref="rig:practice",
                  base_ref="refs/heads/main", base_sha=base, integration_ref="refs/heads/main",
                  worktree=str(retained), verify_command=verify)
    old = {"id": "wf-old", "status": "closed", "metadata": {
        "gc.kind": "workflow", "gc.formula_name": "quick-start", "gc.outcome": "fail",
        "gc.source_bead_id": "pr-task", "gc.root_store_ref": "rig:practice",
        "gc.var.rig_name": "practice", "gc.var.verify_command": verify,
        "gc.delivery.record": json.dumps(record)}}
    source = {"id": "pr-task", "status": "open", "metadata": {"gc.delivery.workflow_root": "wf-old"}}
    state = SimpleNamespace(mod=mod, repo=repo, retained=retained, base=base, verify=verify,
                            record=record, old=old, source=source, roots={"wf-old": old},
                            calls=[], lost_ack=False, fail_admission=False, convoy_binding=False,
                            convoys=[], convoy_children=[{"id": "pr-task", "issue_type": "task"}])
    def observe(*args, **kwargs):
        state.calls.append(args)
        assert args[0] == "gc"
        if args[1:3] == ("rig", "list"):
            return {"rigs": [{"name": "practice", "path": str(repo), "default_branch": "main",
                              "default_sling_target": "practice/gc.run-operator"}]}
        if args[1:3] == ("bd", "show") or args[1:5] == ("--rig", "practice", "bd", "show"):
            bid = args[-2]
            return state.source if bid == "pr-task" else state.roots[bid]
        if args[1:5] == ("--rig", "practice", "bd", "dep"):
            return state.convoys + ([{"id": "cv-new", "issue_type": "convoy", "metadata": {"gc.synthetic": "true"}}]
                    if state.convoy_binding and "wf-new" in state.roots else [])
        if args[1:5] == ("--rig", "practice", "bd", "list"):
            marker = args[args.index("--metadata-field") + 1]
            key, value = marker.split("=", 1)
            return [r for r in state.roots.values() if r["metadata"].get(key) == value]
        if args[1:3] == ("convoy", "status"):
            return {"children": state.convoy_children}
        if args[1:4] == ("--rig", "practice", "sling"):
            assert "pr-task" in args and args[args.index("--on") + 1] == "quick-start"
            assert "verify_command=" + verify in args and "input_sha=" + base in args
            assert "--force" not in args and "delete-source" not in args
            if state.fail_admission:
                raise mod.InfrastructureError("admission unavailable")
            metadata = {"gc.kind": "workflow", "gc.formula_name": "quick-start"}
            metadata["gc.input_convoy_id" if state.convoy_binding else "gc.source_bead_id"] = ("cv-new" if state.convoy_binding else "pr-task")
            state.roots["wf-new"] = {"id": "wf-new", "status": "in_progress", "metadata": metadata}
            if state.lost_ack:
                raise mod.InfrastructureError("native acknowledgment lost")
            return "Attached workflow wf-new\n"
        raise AssertionError(f"recovery may only observe or use native sling admission: {args}")
    monkeypatch.setattr(mod, "gc", observe)
    return state


def test_retry_preserves_source_failed_work_and_fixed_input(failed_delivery):
    s = failed_delivery
    before = json.dumps(s.old, sort_keys=True)
    receipt = s.mod.retry_delivery("wf-old")
    assert receipt["workflow"] == "wf-new" and receipt["source"] == "pr-task"
    assert receipt["input_sha"] == s.base
    assert json.dumps(s.old, sort_keys=True) == before
    assert s.source["status"] == "open" and git(s.repo, "rev-parse", "HEAD") == s.base
    assert (s.retained / "app.txt").read_text() == "preserve my unfinished implementation\n"
    assert len([a for a in s.calls if "sling" in a]) == 1


@pytest.mark.parametrize("convoy_binding", [False, True])
def test_retry_recovers_lost_ack_and_observes_repeated_request(failed_delivery, convoy_binding):
    s = failed_delivery
    s.lost_ack = True
    s.convoy_binding = convoy_binding
    first = s.mod.retry_delivery("wf-old")
    second = s.mod.retry_delivery("wf-old")
    assert first["workflow"] == second["workflow"] == "wf-new"
    assert len([a for a in s.calls if "sling" in a]) == 1


def test_failed_admission_is_not_masked_by_an_old_closed_workflow(failed_delivery):
    s = failed_delivery
    s.fail_admission = True
    with pytest.raises(s.mod.InfrastructureError, match="admission unavailable"):
        s.mod.retry_delivery("wf-old")
    assert len(s.roots) == 1


@pytest.mark.parametrize("fault", ["completed source", "passed root", "integrated output", "advanced input", "dirty input", "changed branch", "changed verification"])
def test_retry_refuses_unsafe_replacement_without_mutation(failed_delivery, fault):
    s = failed_delivery
    if fault == "completed source":
        s.source["status"] = "closed"
    elif fault == "passed root":
        s.old["metadata"]["gc.outcome"] = "pass"
    elif fault == "integrated output":
        s.record["integrated_sha"] = s.base
    elif fault == "advanced input":
        (s.repo / "next.txt").write_text("another accepted task\n")
        git(s.repo, "add", ".")
        git(s.repo, "commit", "-m", "Advance mainline")
    elif fault == "dirty input":
        (s.repo / "untracked.txt").write_text("preserve this\n")
    elif fault == "changed branch":
        git(s.repo, "checkout", "-b", "different-input")
    else:
        s.old["metadata"]["gc.var.verify_command"] = "different verification"
    s.old["metadata"]["gc.delivery.record"] = json.dumps(s.record)
    before = git(s.repo, "rev-parse", "HEAD")
    with pytest.raises(ValueError):
        s.mod.retry_delivery("wf-old")
    assert git(s.repo, "rev-parse", "HEAD") == before
    assert not any("sling" in a or "update" in a or "delete-source" in a for a in s.calls)
    assert (s.retained / "app.txt").read_text() == "preserve my unfinished implementation\n"


def test_retry_observes_an_active_workflow_without_replacing_it(failed_delivery):
    s = failed_delivery
    s.old["status"] = "in_progress"
    receipt = s.mod.retry_delivery("wf-old")
    assert receipt["workflow"] == "wf-old"
    assert not any("sling" in a for a in s.calls)


def test_fixed_retry_input_does_not_fetch_or_advance_to_a_new_origin(failed_delivery, tmp_path):
    s = failed_delivery
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(s.repo), str(origin)], check=True, capture_output=True)
    git(s.repo, "remote", "add", "origin", str(origin))
    git(s.repo, "fetch", "origin")
    writer = tmp_path / "writer"
    subprocess.run(["git", "clone", str(origin), str(writer)], check=True, capture_output=True)
    git(writer, "config", "user.name", "Origin writer")
    git(writer, "config", "user.email", "origin@example.invalid")
    (writer / "advanced.txt").write_text("new remote input\n")
    git(writer, "add", ".")
    git(writer, "commit", "-m", "Advance origin")
    git(writer, "push", "origin", "main")
    assert git(writer, "rev-parse", "HEAD") != s.base
    assert s.mod.task_input(s.repo, "main", input_sha=s.base) == ("refs/heads/main", s.base, s.base)
    assert git(s.repo, "rev-parse", "HEAD") == s.base
    assert git(s.repo, "rev-parse", "refs/remotes/origin/main") == s.base


@pytest.fixture
def tutorial_retry(failed_delivery, monkeypatch):
    import source_delivery
    s = failed_delivery
    spec = importlib.util.spec_from_file_location("tutorial_retry_under_test", SCRIPT.with_name("tutorial.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = s.mod.gc
    s.native_retry_calls = []
    s.lesson_missing = False
    def observe(*args, **kwargs):
        if args[1:5] == ("--rig", "practice", "bd", "list"):
            marker = args[args.index("--metadata-field") + 1]
            if marker.startswith("gc.tutorial="):
                return [] if s.lesson_missing else [s.source]
        if args[1:4] == ("gc", "source-delivery", "retry"):
            assert args[4:] == ("--root", "wf-old", "--source", "pr-task")
            s.native_retry_calls.append(args)
            return {"status": "started", "source": "pr-task", "workflow": "wf-new",
                    "input_sha": s.base, "retained_worktree": str(s.retained)}
        return original(*args, **kwargs)
    monkeypatch.setattr(source_delivery, "gc", observe)
    monkeypatch.setenv("GC_CITY_PATH", str(s.repo.parents[1]))
    monkeypatch.setattr("sys.argv", ["tutorial", "retry"])
    monkeypatch.setattr(module, "scaffold", lambda path: pytest.fail("retry must preserve the existing project"))
    return module, s


def test_tutorial_retry_uses_one_native_delivery_admission(tutorial_retry, capsys):
    tutorial, s = tutorial_retry
    tutorial.main()
    text = capsys.readouterr().out
    assert "Source task: pr-task" in text and "wf-new" in text
    assert len(s.native_retry_calls) == 1
    assert not any("sling" in a or "create" in a or "rig" in a[1:2] and "add" in a for a in s.calls)


def test_tutorial_retry_of_active_work_is_observation_only(tutorial_retry, capsys):
    tutorial, s = tutorial_retry
    s.old["status"] = "in_progress"
    tutorial.main()
    assert "Existing workflow: wf-old" in capsys.readouterr().out
    assert not s.native_retry_calls


def test_tutorial_retry_requires_an_existing_lesson(tutorial_retry):
    tutorial, s = tutorial_retry
    s.lesson_missing = True
    with pytest.raises(ValueError, match="start"):
        tutorial.main()
    assert not s.native_retry_calls
    assert not any("create" in a or "sling" in a for a in s.calls)


def test_status_observes_new_live_attempt_before_its_source_backlink_is_written(tutorial_retry, monkeypatch, capsys):
    tutorial, s = tutorial_retry
    s.roots["wf-new"] = {"id": "wf-new", "status": "in_progress", "metadata": {
        "gc.kind": "workflow", "gc.formula_name": "quick-start", "gc.source_bead_id": "pr-task"}}
    monkeypatch.setattr("sys.argv", ["tutorial", "status"])
    tutorial.main()
    text = capsys.readouterr().out
    assert "Workflow: wf-new" in text and "stopped" not in text
    assert not s.native_retry_calls


def test_preparation_failure_can_retry_only_its_single_native_input_source(failed_delivery):
    s = failed_delivery
    s.old["metadata"].pop("gc.delivery.record")
    s.old["metadata"].pop("gc.source_bead_id")
    s.old["metadata"]["gc.input_convoy_id"] = "cv-old"
    s.source["metadata"].clear()
    s.convoys = [{"id": "cv-old", "issue_type": "convoy", "metadata": {"gc.synthetic": "true"}}]
    receipt = s.mod.retry_delivery("wf-old", source="pr-task")
    assert receipt["source"] == "pr-task" and receipt["workflow"] == "wf-new"
    assert receipt["input_sha"] == s.base


@pytest.mark.parametrize("bad_input", ["wrong source", "multiple sources"])
def test_unprepared_retry_refuses_a_different_or_ambiguous_source(failed_delivery, bad_input):
    s = failed_delivery
    s.old["metadata"].pop("gc.delivery.record")
    s.old["metadata"].pop("gc.source_bead_id")
    s.old["metadata"]["gc.input_convoy_id"] = "cv-old"
    if bad_input == "multiple sources":
        s.convoy_children.append({"id": "other", "issue_type": "task"})
    with pytest.raises(ValueError):
        s.mod.retry_delivery("wf-old", source="other" if bad_input == "wrong source" else "pr-task")
    assert not any("sling" in a for a in s.calls)


@pytest.mark.parametrize("missing", ["registration", "source"])
def test_tutorial_retry_never_creates_missing_work(tutorial_retry, monkeypatch, missing):
    import source_delivery
    tutorial, s = tutorial_retry
    if missing == "source":
        s.lesson_missing = True
    else:
        previous = source_delivery.gc
        def observe(*args, **kwargs):
            if args[1:3] == ("rig", "list"):
                return {"rigs": []}
            return previous(*args, **kwargs)
        monkeypatch.setattr(source_delivery, "gc", observe)
    with pytest.raises(ValueError, match="start"):
        tutorial.main()
    assert not s.native_retry_calls
    assert not any("create" in a or "sling" in a or "add" in a for a in s.calls)


@pytest.mark.parametrize("raw", ["[]", "null", "{bad json", "{}"])
def test_retry_rejects_malformed_prepared_evidence_before_admission(failed_delivery, raw):
    s = failed_delivery
    s.old["metadata"]["gc.delivery.record"] = raw
    with pytest.raises(ValueError):
        s.mod.retry_delivery("wf-old")
    assert not any("sling" in a or "update" in a for a in s.calls)


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("fixed", ["not-a-full-sha", "a" * 40])
def test_retry_never_discards_an_existing_native_input_contract(failed_delivery, prepared, fixed):
    s = failed_delivery
    s.old["metadata"]["gc.var.input_sha"] = fixed
    if not prepared:
        s.old["metadata"].pop("gc.delivery.record")
        s.old["metadata"].pop("gc.source_bead_id")
        s.old["metadata"]["gc.input_convoy_id"] = "cv-old"
        s.source["metadata"].clear()
        s.convoys = [{"id": "cv-old", "issue_type": "convoy", "metadata": {"gc.synthetic": "true"}}]
    with pytest.raises(ValueError, match="input"):
        s.mod.retry_delivery("wf-old", source="pr-task")
    assert not any("sling" in a or "update" in a for a in s.calls)


@pytest.mark.parametrize("prepared", [False, True])
def test_prepare_reads_native_fixed_input_before_any_write(failed_delivery, monkeypatch, prepared):
    s = failed_delivery
    s.old["metadata"]["gc.var.input_sha"] = "a" * 40
    if not prepared:
        s.old["metadata"].pop("gc.delivery.record")
    with pytest.raises(ValueError, match="input"):
        s.mod.prepare("wf-old", "pr-task", s.repo, s.repo.parent / "owned", s.verify)
    assert not any("update" in a or "ensure" in a for a in s.calls)


def test_prepare_uses_native_fixed_input_to_provision(failed_delivery, monkeypatch):
    s = failed_delivery
    s.old["metadata"].pop("gc.delivery.record")
    s.old["metadata"]["gc.var.input_sha"] = s.base
    writes = []
    previous = s.mod.gc
    def observe(*args, **kwargs):
        if args[1:3] == ("bd", "update"):
            writes.append(args)
            return ""
        if args[1:3] == ("worktree", "ensure"):
            assert args[args.index("--base-sha") + 1] == s.base
            assert args[args.index("--generation") + 1] == "wf-old"
            return {"provenance": {"attempt_id": "native-attempt"}}
        return previous(*args, **kwargs)
    monkeypatch.setattr(s.mod, "gc", observe)
    record = s.mod.prepare("wf-old", "pr-task", s.repo, s.repo.parent / "owned", s.verify)
    assert record["base_sha"] == s.base and record["attempt_id"] == "native-attempt"
    assert writes and git(s.repo, "rev-parse", "HEAD") == s.base


def test_failed_lesson_status_has_a_concrete_recovery_command(tutorial_retry, monkeypatch):
    tutorial, s = tutorial_retry
    monkeypatch.setattr("sys.argv", ["tutorial", "status"])
    with pytest.raises(ValueError, match="gc gc tutorial retry --lesson greeting"):
        tutorial.main()


def test_integrated_failure_does_not_suggest_replacing_implementation(tutorial_retry, monkeypatch):
    tutorial, s = tutorial_retry
    s.record["integrated_sha"] = s.base
    s.old["metadata"]["gc.delivery.record"] = json.dumps(s.record)
    monkeypatch.setattr("sys.argv", ["tutorial", "status"])
    with pytest.raises(ValueError) as caught:
        tutorial.main()
    assert "finalization" in str(caught.value)
    assert "tutorial retry" not in str(caught.value)
