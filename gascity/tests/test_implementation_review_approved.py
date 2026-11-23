"""Guards for the implementation-review gate in `assets/scripts/checks`.

Two properties, both of which the gate lost at some point:

1. It runs on the bash the gate actually gets. macOS /bin/bash is 3.2, which
   has no `${var,,}`. The gate had one, so on a macOS city the expansion was a
   fatal "bad substitution" -- and bash exited 0 on it, so the gate silently
   APPROVED every bead, including one whose verdict was `iterate`.
2. An approving verdict still passes. The fix for (1) rewrites the comparison,
   so the approvals it accepts are held here.

The scan in (1) is static on purpose: CI runs bash 5, where the broken
expression works, so a behavior test alone cannot see this defect.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import tempfile
import textwrap
import unittest

CHECKS_DIR = pathlib.Path(__file__).resolve().parents[1] / "assets" / "scripts" / "checks"
GATE = CHECKS_DIR / "implementation-review-approved.sh"

# `${name,,}` and `${name^^}`. The gate PATH on macOS is /bin/bash 3.2.
BASH4_ONLY = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(\[[^]]*\])?(,,|\^\^)\}")
# `${name:0:1}` is fine on 3.2. `${name@Q}` is not, and shells die on it the
# same way, so it is held too.
BASH4_QUOTE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*@[QEPAa]\}")

STUB_GC = textwrap.dedent(
    """\
    #!/bin/sh
    # Minimal `gc` for the review gate: one root bead, one member bead.
    verdict="$GC_STUB_VERDICT"
    case "$1 $2" in
      "bd show")
        if [ "$3" = "root-1" ]; then
          printf '%s\\n' '{"id":"root-1","updated_at":"2026-01-01T00:00:00Z","metadata":{"gc.root_bead_id":"root-1"}}'
        else
          printf '{"id":"member-1","updated_at":"2026-01-02T00:00:00Z","metadata":{"gc.root_bead_id":"root-1","gc.attempt":"0","code_review.verdict":"%s"}}\\n' "$verdict"
        fi
        ;;
      "ready --metadata-field")
        status=""
        prev=""
        for arg in "$@"; do
          [ "$prev" = "--status" ] && status="$arg"
          prev="$arg"
        done
        if [ "$status" = "closed" ]; then
          printf '[{"id":"member-1","updated_at":"2026-01-02T00:00:00Z","metadata":{"gc.root_bead_id":"root-1","gc.attempt":"0","code_review.verdict":"%s"}}]\\n' "$verdict"
        else
          printf '[]\\n'
        fi
        ;;
      *)
        echo "stub gc: unhandled: $*" >&2
        exit 2
        ;;
    esac
    """
)


class Bash3PortabilityTests(unittest.TestCase):
    def test_check_scripts_avoid_bash4_only_expansions(self) -> None:
        offenders = []
        for script in sorted(CHECKS_DIR.glob("*.sh")):
            for number, line in enumerate(script.read_text().splitlines(), 1):
                # Comments may name the construct they warn about.
                if line.lstrip().startswith("#"):
                    continue
                for pattern in (BASH4_ONLY, BASH4_QUOTE):
                    match = pattern.search(line)
                    if match:
                        offenders.append(f"{script.name}:{number}: {match.group(0)}")
        self.assertEqual(
            offenders,
            [],
            "macOS gate bash is 3.2; these expansions are a fatal "
            "'bad substitution' there:\n  " + "\n  ".join(offenders),
        )


class ApprovalVerdictTests(unittest.TestCase):
    def run_gate(self, verdict: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            stub = pathlib.Path(tmp) / "gc"
            stub.write_text(STUB_GC)
            stub.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = f"{tmp}{os.pathsep}{env.get('PATH', '')}"
            env["GC_BEAD_ID"] = "root-1"
            env["GC_STUB_VERDICT"] = verdict
            bash = os.environ.get("CHECK_BASH", "bash")
            return subprocess.run(
                [bash, str(GATE)],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )

    def test_approving_verdict_passes(self) -> None:
        for verdict in ("done", "Done", "approved"):
            with self.subTest(verdict=verdict):
                result = self.run_gate(verdict)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Implementation review approved", result.stdout)
                self.assertNotIn("bad substitution", result.stderr)

    def test_non_approving_verdict_blocks(self) -> None:
        result = self.run_gate("iterate")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("needs another iteration", result.stdout)
        self.assertNotIn("bad substitution", result.stderr)


if __name__ == "__main__":
    unittest.main()
