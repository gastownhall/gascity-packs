"""Hold `gc lint gastown` at a pinned finding set.

gastown is a supported pack. It is exercised by supported-pack-nightly.yml and
it is NOT in the `gc lint` loop in .github/workflows/ci.yml, which is how it
accumulated fourteen findings that nothing failed on: nine prompt templates and
formulas telling agents to run bd flags that do not exist, and five pack-level
diagnostics.

Seven of those were real and are fixed. The rest are defects in gc's own
linter, enumerated with their gc-side cause in
`tests/gastown_lint_upstream_defects.txt`.

A NEW finding fails, which is the regression this exists to catch. A pinned
finding that DISAPPEARS also fails, because that is the upstream fix landing
and the waiver should be deleted in the same change rather than quietly
outliving it.

Which findings gc emits depends on which gc ran, and this test does not paper
over that. `.github/workflows/ci.yml` installs `gc@latest`; twenty-two findings
that a released gc reports were fixed on gascity main by 7724983de and are
absent from a dev build. So the waiver file is sectioned: entries every gc
reports are required, and a version-dependent section is tolerated but has to
be wholly present or wholly absent. That is what the sections are for, and it
is why the first run of this test in CI went red while it was green locally.

Fidelity, and where it stops: this runs the real `gc lint` against the real
pack, so it is not a fixture reimplementation of the linter and it cannot drift
from it. What it cannot do is check a flag `gc lint` does not know about --
internal/bdflags/bdflags.go carries a manifest of bd subcommands, and anything
outside that manifest is skipped by design. It is also line-oriented and does
not join backslash-continued shell lines, so the three multi-line `gc bd create
... \\ --labels=warrant` invocations fixed alongside this test were never
reported by it at all. A green here means "no NEW finding of a kind gc lint can
see", not "every bead command in the pack is valid".
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = "gastown"
PACK_DIR = REPO_ROOT / PACK
WAIVER = Path(__file__).with_name("gastown_lint_upstream_defects.txt")

SECTION_DIRECTIVE = "# @section:"
UNIVERSAL = "universal"

# The findings gc emits depend on which gc ran. `.github/workflows/ci.yml`
# installs `gc@latest`; a contributor is as likely to have a build from main.
# So the waiver file separates findings every gc reports from findings a
# released gc reports and main no longer does, and this test holds each to the
# assertion that is true of it. Collapsing the two would mean either CI red on
# an upstream release, or a real regression waved through on a dev build.
TOLERATED_SECTIONS = ("pre-5220",)


def gc_binary() -> str | None:
    """The gc binary to lint with, or None when there is none to use.

    GC_TEST_BIN is how .github/workflows/ci.yml already hands a freshly built
    gc to tests/test_gc_role_prompt_integration.py; honor the same variable so
    the two run off one installation.
    """
    pinned = os.environ.get("GC_TEST_BIN", "").strip()
    if pinned:
        return pinned
    return shutil.which("gc")


def waived_findings() -> dict[str, Counter[str]]:
    """The pinned findings by section, read off disk rather than inlined here.

    Counters, not sets: two diagnostics that normalize to the same key are two
    findings, and collapsing them would let a duplicate arrive unnoticed.

    An unknown section name is an error rather than a silent extra bucket. A
    typo there would otherwise waive its lines against nothing and read as a
    clean pass.
    """
    sections: dict[str, Counter[str]] = {
        name: Counter() for name in (UNIVERSAL, *TOLERATED_SECTIONS)
    }
    current = UNIVERSAL
    for raw in WAIVER.read_text().splitlines():
        line = raw.strip()
        if line.startswith(SECTION_DIRECTIVE):
            current = line[len(SECTION_DIRECTIVE) :].strip()
            if current not in sections:
                raise AssertionError(
                    f"{WAIVER.name} names section {current!r}, which this test "
                    f"does not know. Known: {sorted(sections)}."
                )
            continue
        if not line or line.startswith("#"):
            continue
        sections[current][line] += 1
    return sections


# gc lint exits 0 when a pack is clean and 1 when it has findings. Both are
# reports. Anything else is the tool failing, and a failing tool must not be
# read as "no new findings" -- that is the shape where a guard goes green
# because nothing looked, rather than because nothing was wrong.
LINT_REPORTING_EXITS = (0, 1)


def observed_findings(gc_bin: str) -> Counter[str]:
    """Run `gc lint gastown --json` and normalize its diagnostics.

    Paths come back absolute, so they are made relative to the pack directory:
    a finding key must be identical on a contributor's machine and on a runner.

    The line number is deliberately NOT part of the key. It was, for one day,
    and #265 moved the mayor prompt's rig-routing table without changing a
    single diagnostic -- same file, same message, same count of two of them
    where the table had four -- and every open PR in the repo inherited a red
    main. A guard keyed on position reports edits. What is left still fails on
    a new path, a new message, or an extra occurrence, because these are
    Counters: three identical waiver lines waive exactly three findings.
    """
    proc = subprocess.run(
        [gc_bin, "lint", PACK, "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in LINT_REPORTING_EXITS:
        raise AssertionError(
            f"gc lint exited {proc.returncode}, which is neither clean (0) nor "
            f"findings-present (1), so its output is not a report.\n"
            f"stdout: {proc.stdout[:2000]}\nstderr: {proc.stderr[:2000]}"
        )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"gc lint emitted no JSON report (exit {proc.returncode}).\n"
            f"stdout: {proc.stdout[:2000]}\nstderr: {proc.stderr[:2000]}"
        ) from exc

    packs = report.get("packs")
    if not isinstance(packs, list) or len(packs) != 1:
        raise AssertionError(
            f"expected exactly one pack report for {PACK!r}, got "
            f"{len(packs) if isinstance(packs, list) else packs!r}"
        )
    # Without this the guard passes on a report about some other pack, which
    # is what a typo in the invocation or a future gc argument change looks
    # like from here.
    reported = packs[0].get("name")
    if reported != PACK:
        raise AssertionError(
            f"gc lint reported on pack {reported!r}, not {PACK!r}"
        )

    findings: Counter[str] = Counter()
    for diag in packs[0].get("diagnostics") or []:
        path = Path(diag.get("path", ""))
        try:
            rel = path.relative_to(PACK_DIR)
        except ValueError:
            rel = path
        findings[f"{rel}: {diag.get('message', '')}"] += 1
    return findings


def render(counted: Counter[str]) -> list[str]:
    """Findings as sorted lines, with a count suffix when one repeats."""
    return [
        key if n == 1 else f"{key}   (x{n})" for key, n in sorted(counted.items())
    ]


class GastownLintFindingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.gc_bin = gc_binary()
        if not self.gc_bin:
            self.skipTest(
                "no gc binary; set GC_TEST_BIN or put gc on PATH. "
                "ci.yml installs one for the shared-role-prompt step."
            )

    def waiver_sets(self) -> tuple[Counter[str], Counter[str]]:
        sections = waived_findings()
        tolerated: Counter[str] = Counter()
        for name in TOLERATED_SECTIONS:
            tolerated += sections[name]
        return sections[UNIVERSAL], tolerated

    def test_gastown_lint_reports_nothing_outside_the_waiver(self) -> None:
        observed = observed_findings(self.gc_bin)
        universal, tolerated = self.waiver_sets()

        new = render(observed - universal - tolerated)
        self.assertFalse(
            new,
            "gc lint gastown reported findings that are not in "
            f"{WAIVER.name}:\n  " + "\n  ".join(new) + "\n"
            "If these are pack defects, fix them. If they are gc linter "
            "defects, add them to that file with the gc-side cause and a "
            "command that refutes the claim.",
        )

    def test_every_universal_waiver_entry_is_still_reported(self) -> None:
        """A waiver that outlives its defect is the failure this catches.

        Only the universal section is held to this. A version-dependent
        section legitimately vanishes when the gc under test carries the fix,
        which is the whole reason it is a separate section.
        """
        observed = observed_findings(self.gc_bin)
        universal, _ = self.waiver_sets()

        gone = render(universal - observed)
        self.assertFalse(
            gone,
            "these findings are pinned in "
            f"{WAIVER.name} but gc lint no longer reports them:\n  "
            + "\n  ".join(gone)
            + "\nThat is the upstream fix landing. Delete the entry (and its "
            "explanatory block) in the same change.",
        )

    def test_a_version_dependent_section_is_all_present_or_all_absent(self) -> None:
        """Tolerating a set is not tolerating an arbitrary subset of it.

        Without this, a real regression that happens to reuse one of these
        path/message pairs is absorbed by the waiver, and the section can rot
        an entry at a time as the pack moves under it.
        """
        observed = observed_findings(self.gc_bin)
        sections = waived_findings()
        for name in TOLERATED_SECTIONS:
            entries = sections[name]
            present = entries & observed
            with self.subTest(section=name):
                if not present:
                    continue
                missing = render(entries - observed)
                self.assertFalse(
                    missing,
                    f"section {name!r} of {WAIVER.name} is partially reported "
                    f"by this gc. Present but missing:\n  "
                    + "\n  ".join(missing)
                    + "\nEither the pack moved under the waiver or the section "
                    "is no longer one upstream change. Re-derive it.",
                )

    def test_no_bd_unknown_flag_finding_outside_the_waiver(self) -> None:
        """The pack's own half of the finding set, stated separately.

        The first test would also go red if a `named_session` diagnostic
        changed shape upstream, which is not this pack's problem. This one
        fails only on the class gastown actually owns: a prompt template or
        formula telling an agent to run a bd flag that does not exist.
        """
        observed = observed_findings(self.gc_bin)
        universal, tolerated = self.waiver_sets()
        bd_flag = Counter(
            {k: n for k, n in observed.items() if "bd-unknown-flag:" in k}
        )
        unexpected = render(bd_flag - universal - tolerated)
        self.assertFalse(
            unexpected,
            "a bd flag that does not exist is back in a gastown prompt or "
            "formula:\n  " + "\n  ".join(unexpected),
        )


if __name__ == "__main__":
    unittest.main()
