"""A report-only step must still let its worker close its own step bead.

2026-11-02: review.validate-context said "must not mutate beads", and Codex
workers refused to close their step bead, deadlocking github-pr-review runs
(two runs observed on 2026-11-02).
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "gascity" / "assets" / "workflows"
BLANKET = re.compile(r"must not mutate\s+beads", re.IGNORECASE)


def test_no_step_forbids_all_bead_writes():
    offenders = [
        str(p.relative_to(ROOT))
        for p in ROOT.rglob("*.md")
        if BLANKET.search(p.read_text())
    ]
    assert offenders == [], offenders


def test_validate_context_steps_allow_own_close():
    for name in ("review", "gap-analysis"):
        text = (ROOT / name / "validate-context.md").read_text()
        assert "this step's own" in text
        assert "Closing this step's bead" in text
