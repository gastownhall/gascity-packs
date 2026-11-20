"""Shipped `gc bd` invocations must not use flags or verbs bd rejects.

gc's split-store `gc bd` allowlist (gascity S2) scans every shipped bead
command and found invocations that bd rejects on every city, split or not:

  * `gc bd list ... --search` (gastown mol-refinery-patrol): the list verb has no
    --search flag. The refinery's duplicate-bug check errored, so a
    pre-existing failure was never matched and a duplicate bug was filed each
    time. The list verb's substring filter is --title-contains.
  * `gc bd meta set` (gastown adopt-pr-review-approved.sh): bd has no `meta`
    verb. It was only in a comment, but an agent following it fails. Metadata
    is written with `gc bd update <id> --set-metadata key=value`.
  * `gc bd update <bead> --status=escalated` (gastown polecat prompt): bd has
    no such status, so the escalation instruction errored on every use. bd's
    built-in statuses (per its invalid-status error, bd 1.3.2) are open,
    in_progress, blocked, deferred, closed, pinned, hooked — the same set its
    list filter accepts, help text notwithstanding. Custom statuses are
    per-city `bd config set status.custom`, so shipped pack docs must stay
    within the built-ins. The fixed instruction uses --status=blocked, which
    carries the escalation and stays out of bd ready until triage.

`gc lint` does not report the first two: its bd flag manifest skips them. This
guard is line-oriented and deliberately narrow: it fails on the specific
rejected forms, and ignores lines that tell agents NOT to use a form ("Do not
use"). The status check validates only bare literal values — a status is
[a-z_]+ (comma list), so quoted, shell-expanded ($VAR), and hyphen-leading
values simply don't match and are left to bd's own rejection.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNED_SUFFIXES = {".md", ".tmpl", ".toml", ".sh", ".py", ".bash"}
SKIP_DIRS = {".git", "vendor", "docs", "tests", "node_modules"}

GC_BD_LIST = re.compile(r"\bgc\s+(?:--\S+(?:\s+[^-\s]\S*)?\s+)*bd\s+list\b(?P<rest>.*)")
REJECTED_LIST_FLAGS = ("--search", "--root")
GC_BD_META = re.compile(r"\bgc\s+(?:--\S+(?:\s+[^-\s]\S*)?\s+)*bd\s+meta\b")
GC_BD_CREATE_ROOT_BEAD = re.compile(r"\bgc\s+(?:--\S+(?:\s+[^-\s]\S*)?\s+)*bd\s+create\b.*--root-bead\b")
GC_BD_INVOCATION = re.compile(r"\bgc\s+(?:--\S+(?:\s+[^-\s]\S*)?\s+)*bd\s+\S+(?P<rest>.*)")
# A status value is [a-z_]+ (comma lists for the list filter), so the capture
# stops at quotes, backticks, `$`, and trailing punctuation; quoted or shell
# values ("$STATUS") simply never match and are skipped, like hyphen-leading
# tokens bd rejects but the pattern can't disambiguate from a flag.
BD_STATUS_FLAG = re.compile(r"(?<![\w-])--status[= ](?P<val>\w[\w,]*)")
BD_STATUSES = frozenset(
    {"open", "in_progress", "blocked", "deferred", "closed", "pinned", "hooked"}
)
NEGATED = re.compile(r"\b(?:do not|don't|never)\s+use\b", re.IGNORECASE)


def shipped_files():
    for path in sorted(REPO_ROOT.rglob("*")):
        rel = path.relative_to(REPO_ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.is_file() and path.suffix in SCANNED_SUFFIXES:
            yield path, rel


def invalid_status_values(rest):
    """Return the invalid literal --status values one gc bd invocation carries."""
    bad = []
    for match in BD_STATUS_FLAG.finditer(rest):
        for part in match.group("val").split(","):
            if part and part not in BD_STATUSES:
                bad.append(part)
    return bad


def line_findings(line):
    """Return the rejected gc bd forms one line uses."""
    if NEGATED.search(line):
        return []
    forms = []
    match = GC_BD_LIST.search(line)
    if match:
        for flag in REJECTED_LIST_FLAGS:
            if re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", match.group("rest")):
                forms.append(f"gc bd list {flag}")
    if GC_BD_META.search(line):
        forms.append("gc bd meta")
    if GC_BD_CREATE_ROOT_BEAD.search(line):
        forms.append("gc bd create --root-bead")
    match = GC_BD_INVOCATION.search(line)
    if match:
        for value in invalid_status_values(match.group("rest")):
            forms.append(f"gc bd --status={value}")
    return forms


def rejected_invocations():
    findings = []
    for path, rel in shipped_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for form in line_findings(line):
                findings.append(f"{rel}:{lineno}: {form}: {line.strip()}")
    return findings


class ShippedBdFlagsExistTest(unittest.TestCase):
    def test_no_rejected_gc_bd_forms(self):
        findings = rejected_invocations()
        self.assertEqual(
            findings,
            [],
            "shipped gc bd invocations use flags or verbs bd rejects:\n" + "\n".join(findings),
        )

    def test_guard_catches_each_rejected_form(self):
        samples = {
            'gc bd list --type=bug --status=open --search "x"': True,
            "gc bd list --root X": True,
            "#   gc bd meta set $BEAD_ID review.verdict=done": True,
            "gc --city c bd create --root-bead X": True,
            "gc bd update <bead> --status=escalated": True,
            "gc bd update $BEAD --status=done": True,
            'gc bd list --type=bug --status=open --title-contains "x"': False,
            "gc bd list --root-only": False,
            "Do not use `gc bd list --root`; that flag is not supported.": False,
            'gh pr list --search "123"': False,
            "gc bd list --status=open,in_progress --json": False,
            "gc bd update <bead> --status=blocked && gc runtime drain-ack": False,
            'gc bd update "$BEAD" --status="$STATUS"': False,
            "gc bd list --status=pinned": False,
            "bd update <bead> --status=escalated (plain bd is not gc)": False,
            "gc bd update <bead> --status=-open": False,
        }
        for line, want in samples.items():
            with self.subTest(line=line):
                hit = bool(line_findings(line))
                self.assertEqual(hit, want)


if __name__ == "__main__":
    unittest.main()
