"""Static safety contract for Project Lead execution-intent reconciliation."""

from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
PROMPT = (PACK_ROOT / "agents" / "project-lead" / "prompt.template.md").read_text()
README = (PACK_ROOT / "README.md").read_text()
PACK = (PACK_ROOT / "pack.toml").read_text()


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_project_lead_uses_the_selector_as_its_only_candidate_source() -> None:
    prompt = normalized(PROMPT)
    assert "select-execution-candidates.py" in prompt
    assert "READY != RUN" in prompt
    assert "plain open, unblocked backlog bead is not execution-authorized" in prompt
    assert "Never run an unrestricted `gc bd list --ready` scan" in prompt
    assert "Do not invoke `gc-sling`" in prompt


def test_prompt_forbids_route_invention_and_keeps_formula_control_owned() -> None:
    prompt = normalized(PROMPT)
    for phrase in (
        "Do not invent, select, overwrite, normalize, or repair a route.",
        "Formula control steps remain controller-owned.",
        "without its existing route/control state is an anomaly to surface",
        "custom ACTIVE/COMMITTED marker",
        "arbitrary bead tree",
    ):
        assert phrase in prompt


def test_documentation_describes_reconciliation_not_ready_dispatch() -> None:
    readme = normalized(README)
    pack = normalized(PACK)
    assert "Dispatch safety: READY != RUN" in readme
    assert "does not invent or rewrite routes" in readme
    assert "reconciles committed ready work" in readme
    assert "reconciles committed ready work" in pack
    assert "dispatches ready, in-scope work" not in pack


def test_pool_routes_are_not_treated_as_concrete_sessions() -> None:
    prompt = normalized(PROMPT)
    readme = normalized(README)
    assert "do not pass the returned pool route to `gc session wake`" in prompt
    assert "or `gc session nudge`" in prompt
    assert "Let the controller reconcile that demand." in prompt
    assert "Never guess a session name, add an instance suffix" in prompt
    assert "Pool routes remain controller scheduling demand" in readme
    assert "gc session wake <exact-existing-route>" not in PROMPT
    assert "gc session nudge <exact-existing-route>" not in PROMPT
