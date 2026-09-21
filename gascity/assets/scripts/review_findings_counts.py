#!/usr/bin/env python3
"""Deterministic severity and scorecard parser for review artifacts.

Shared by the `build-from-review-base` review slot, `apply-review-fixes`, and
any expansion bound on the review slot so every producer and consumer counts
findings the same way. The predicates mirror the private adopt-pr review gate
(`adopt-pr-review-approved.sh`): severity bullets are counted under one `##`
heading, and the scorecard decision/score/threshold lines use the same regexes.

Usage:
  review_findings_counts.py findings <report.md> [--section Findings] [--json]
    -> blocker=N,major=N,minor=N,nit=N
  review_findings_counts.py scorecard <scorecard.md> [--json]
    -> decision=<approve|request_changes|block|missing>,score=<int|missing>,threshold=<int>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERITIES = ("blocker", "major", "minor", "nit")
SCORECARD_THRESHOLD = 850

# Severity bullets under a `##` heading. Mirrors the awk predicate in
# adopt-pr-review-approved.sh synthesis_has_blocker_or_major():
#   /^##[[:space:]]+new findings[[:space:]]*$/            (section start)
#   /^##[[:space:]]+/                                     (section end)
#   /^[[:space:]]*[-*][[:space:]]*(\*\*)?severity:(\*\*)?[[:space:]]*(blocker|major)([^[:alpha:]]|$)/
HEADING_RE = re.compile(r"^##[ \t]+")
SEVERITY_BULLET_RE = re.compile(
    r"^[ \t]*[-*][ \t]*(?:\*\*)?severity:(?:\*\*)?[ \t]*(blocker|major|minor|nit)(?:[^a-z]|$)"
)

# Scorecard lines. Copied verbatim from adopt-pr-review-approved.sh
# scorecard_blocks_done().
DECISION_RE = re.compile(
    r"(?im)^\s*(?:##\s*)?(?:[-*]\s*)?(?:\*\*)?decision(?:\*\*)?\s*:\s*([a-z_]+)\b"
)
SCORE_RE = re.compile(
    r"(?im)^\s*(?:##\s*)?(?:[-*]\s*)?(?:\*\*)?quality score(?:\*\*)?\s*:\s*(\d{1,4})\s*/\s*1000\b"
)
THRESHOLD_RE = re.compile(
    r"(?im)^\s*(?:##\s*)?(?:[-*]\s*)?(?:\*\*)?threshold(?:\*\*)?\s*:\s*(\d{1,4})\b"
)


def count_findings(text: str, section: str = "Findings") -> dict[str, int]:
    """Count severity bullets under the `## <section>` heading (case-insensitive)."""
    counts = {severity: 0 for severity in SEVERITIES}
    section_re = re.compile(r"^##[ \t]+" + re.escape(section.strip().lower()) + r"[ \t]*$")
    in_section = False
    for raw in text.splitlines():
        line = raw.lower()
        if section_re.match(line):
            in_section = True
            continue
        if in_section and HEADING_RE.match(line):
            in_section = False
        if not in_section:
            continue
        match = SEVERITY_BULLET_RE.match(line)
        if match:
            counts[match.group(1)] += 1
    return counts


def parse_scorecard(text: str) -> dict[str, object]:
    decision_match = DECISION_RE.search(text)
    score_match = SCORE_RE.search(text)
    threshold_match = THRESHOLD_RE.search(text)
    decision = decision_match.group(1).lower() if decision_match else "missing"
    # An absent score is the literal string "missing" in both the text and the
    # JSON form so every consumer (shell gates, the receipt sealer, the judge)
    # sees one spelling.
    score: int | str = int(score_match.group(1)) if score_match else "missing"
    threshold = int(threshold_match.group(1)) if threshold_match else SCORECARD_THRESHOLD
    return {"decision": decision, "score": score, "threshold": threshold}


def format_findings(counts: dict[str, int]) -> str:
    return ",".join(f"{severity}={counts[severity]}" for severity in SEVERITIES)


def format_scorecard(card: dict[str, object]) -> str:
    return f"decision={card['decision']},score={card['score']},threshold={card['threshold']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    findings = sub.add_parser("findings", help="count severity bullets under a ## section")
    findings.add_argument("path", type=Path)
    findings.add_argument("--section", default="Findings")
    findings.add_argument("--json", action="store_true")
    scorecard = sub.add_parser("scorecard", help="parse decision/score/threshold from a quality scorecard")
    scorecard.add_argument("path", type=Path)
    scorecard.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        text = args.path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"review_findings_counts: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2

    if args.command == "findings":
        counts = count_findings(text, args.section)
        print(json.dumps(counts, sort_keys=True) if args.json else format_findings(counts))
        return 0
    card = parse_scorecard(text)
    print(json.dumps(card, sort_keys=True) if args.json else format_scorecard(card))
    return 0


if __name__ == "__main__":
    sys.exit(main())
