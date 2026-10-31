"""The beginner route cannot close source work before review and integration."""
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]

def test_local_delivery_graph_is_bounded_and_reviewed_independently():
    formula = tomllib.loads((ROOT / "formulas/quick-start.formula.toml").read_text())
    steps = {step["id"]: step for step in formula["steps"]}
    assert formula["contract"] == "graph.v2"
    assert steps["implement"]["needs"] == ["prepare"]
    assert steps["review"]["needs"] == ["implement"]
    assert steps["review"]["check"]["max_attempts"] == 3  # initial + two repair rounds
    children = {step["id"]: step for step in steps["review"]["children"]}
    assert children["inspect"]["needs"] == ["repair"]
    assert children["repair"]["metadata"]["gc.run_target"] != children["inspect"]["metadata"]["gc.run_target"]
    assert steps["integrate"]["needs"] == ["review"]
    assert steps["cleanup"]["needs"] == ["integrate"]
    assert "push" not in formula["vars"] and "open_pr" not in formula["vars"]
    for step in steps.values():
        assert step["metadata"]["gc.scope_ref"] == "delivery-body" if step["id"] != "delivery-body" else True
    assert steps["delivery-body"]["metadata"]["gc.scope_role"] == "body"
