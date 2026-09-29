"""Evidence binding and fail-closed routing, independent of live inference."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "assets/scripts/jev_evidence.py"
spec = importlib.util.spec_from_file_location("jev_evidence", SCRIPT)
jev = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = jev
spec.loader.exec_module(jev)


@pytest.fixture
def bundle(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c",
                    "user.email=test@example.test", "commit", "--allow-empty", "-qm", "fixture"], check=True)
    (tmp_path / "source.py").write_text("def double(x):\n    return x * 2\n")
    (tmp_path / "proof.txt").write_text("1 passed\n")
    return {
        "schema": "gc.evidence-bundle.v1", "worktree": str(tmp_path),
        "head": jev.git_head(tmp_path),
        "items": [{"id": "double", "criterion": "Doubles a positive integer",
                   "claim": "double(2) returns 4",
                   "sources": [{"path": "source.py", "sha256": jev.digest((tmp_path / "source.py").read_bytes())}],
                   "proofs": [{"path": "proof.txt", "sha256": jev.digest((tmp_path / "proof.txt").read_bytes()),
                               "command": "python3 -m pytest", "exit_code": 0,
                               "head": jev.git_head(tmp_path)}]}],
    }


def response(choice="supported", confidence=0.95):
    probs = {k: 0.01 for k in jev.CHOICES}
    probs[choice] = 0.97
    return {"model": "jev-1.13.0", "usage": {"input_tokens": 123, "output_tokens": 0},
            "answers": {"evidence_0": {"type": "choice", "choice": choice,
                        "confidence": confidence, "probabilities": probs}}}


def test_materializes_real_sources_and_proof(bundle):
    state = jev.materialize(bundle)
    assert "return x * 2" in state["items"][0]["sources"][0]["text"]
    assert "1 passed" in state["items"][0]["proofs"][0]["text"]


@pytest.mark.parametrize("change", ["source", "proof", "head", "escape", "duplicate", "empty"])
def test_rejects_unbound_or_stale_evidence(bundle, change):
    if change == "source":
        Path(bundle["worktree"], "source.py").write_text("return 7")
    elif change == "proof":
        bundle["items"][0]["proofs"][0]["head"] = "stale"
    elif change == "head":
        bundle["head"] = "stale"
    elif change == "escape":
        bundle["items"][0]["sources"][0]["path"] = "../secret"
    elif change == "duplicate":
        bundle["items"].append(bundle["items"][0])
    else:
        bundle["items"] = []
    with pytest.raises(ValueError):
        jev.materialize(bundle)


def test_questions_are_atomic_and_bound_to_item(bundle):
    q = jev.questions(jev.materialize(bundle))
    assert "items[0]" in q["evidence_0"]["instructions"]
    assert set(q["evidence_0"]["criteria"]) == set(jev.CHOICES)


def test_low_confidence_escalates_instead_of_approving(bundle):
    decision = jev.decisions(jev.materialize(bundle), response(confidence=0.4), 0.85)
    assert decision[0]["route"] == "llm_review"
    assert decision[0]["choice"] == "supported"


@pytest.mark.parametrize("choice,route", [("supported", "reviewer_check"),
    ("missing_evidence", "run_proof"), ("contradicted", "inspect_implementation"),
    ("unclear", "llm_review")])
def test_routes_are_advisory_and_not_approval(bundle, choice, route):
    assert jev.decisions(jev.materialize(bundle), response(choice), 0.85)[0]["route"] == route


@pytest.mark.parametrize("bad", ["missing", "unknown", "nan", "distribution", "usage"])
def test_rejects_malformed_response(bundle, bad):
    r = response()
    a = r["answers"]["evidence_0"]
    if bad == "missing": r["answers"] = {}
    elif bad == "unknown": a["choice"] = "ship_it"
    elif bad == "nan": a["confidence"] = float("nan")
    elif bad == "distribution": a["probabilities"]["supported"] = 4
    else: del r["usage"]
    with pytest.raises(ValueError):
        jev.decisions(jev.materialize(bundle), r, 0.85)


def test_no_key_fails_without_network(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        jev.evaluate({"items": []}, model="jev-1.13.0")


@pytest.mark.parametrize("mode,reason", [("off", "disabled"), ("auto", "missing_credential")])
def test_inactive_modes_skip_bundle_and_network(tmp_path, monkeypatch, mode, reason):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(jev, "evaluate", lambda *a, **kw: pytest.fail("network called"))
    output = tmp_path / "result"
    assert jev.main([str(tmp_path / "absent.json"), "--output-dir", str(output), "--mode", mode]) == 0
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "skipped"
    assert report["reason"] == reason
    assert report["route"] == "llm_review"
    assert "decisions" not in report


def test_auto_with_key_evaluates_bound_evidence(bundle, tmp_path, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-placeholder")
    monkeypatch.setattr(jev, "evaluate", lambda *a, **kw: response())
    source = tmp_path / "bundle.json"
    source.write_text(json.dumps(bundle))
    output = tmp_path / "result"
    assert jev.main([str(source), "--output-dir", str(output), "--mode", "auto"]) == 0
    assert json.loads((output / "report.json").read_text())["status"] == "completed"
