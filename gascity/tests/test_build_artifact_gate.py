"""End-to-end tests for assets/scripts/checks/build-artifact-valid.sh.

The orchestrator reads this gate's exit status to decide what the failure
means (formula-spec-v2 section 3.1): 0 passes the step, 1 is a content verdict
that costs a producer attempt, 75 is "infrastructure unreachable" and may be
re-run attempt-free, and 78 is "this machine cannot run the check" and holds
the step open until an operator fixes the environment. These tests run the
real script under a scrubbed environment shaped like the gate sandbox, with a
stub `gc` on PATH, and pin one case per status.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

PACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = PACK_ROOT / "assets" / "scripts" / "checks" / "build-artifact-valid.sh"

REQUIREMENTS_SECTIONS = [
    "Problem Statement",
    "W6H",
    "User Stories",
    "Technical Stories",
    "Behavior Requirements",
    "Example Mapping",
    "Acceptance Criteria",
    "Out Of Scope",
    "Open Questions",
]


def valid_requirements_artifact() -> str:
    """A minimal artifact that passes gc.build.requirements.v1."""
    sections = []
    for section in REQUIREMENTS_SECTIONS:
        content = f"{section} content."
        if section == "Example Mapping":
            content += "\n\n| ID | Status |\n| --- | --- |\n| GC-METH-001 | covered |"
        sections.append(f"## {section}\n\n{content}")
    body = "\n\n".join(sections)
    return textwrap.dedent("""\
        ---
        schema: gc.build.requirements.v1
        workflow:
          id: build-20260609-001
          formula: build-basic
        methodology:
          pack: gascity
          name: build-basic
        producer:
          formula: planning-base
          stage: requirements
          attempt: 1
        status: approved
        trace:
          upstream:
            - path: requirements.after.md
              hash: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
          coverage:
            - id: GC-METH-001
              status: covered
        ---

        """) + body + "\n"


@unittest.skipUnless(shutil.which("bash"), "bash is required to run the gate")
class BuildArtifactGateExitStatusTests(unittest.TestCase):
    SCHEMA = "gc.build.requirements.v1"

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.city = self.tmp / "city"
        self.city.mkdir()
        self.artifact = self.tmp / "requirements.md"
        self.artifact.write_text(valid_requirements_artifact(), encoding="utf-8")
        self.write_gc_stub(fail=False)
        # The gate calls bare `python3`. Pin it to the interpreter running the
        # tests so the result does not depend on which python3 the host PATH
        # happens to resolve first (a framework install, for instance, ships
        # only `python3.X` in its bin directory).
        os.symlink(sys.executable, self.bin / "python3")

    def write_gc_stub(self, *, fail: bool) -> None:
        """A `gc` that answers `gc bd show <id> --json` from fixture metadata.

        The step bead carries the artifact contract; the root bead carries the
        resolved artifact path, as the real producer stage records it.
        """
        step = {"id": "step-1", "metadata": {
            "gc.build.artifact_schema": self.SCHEMA,
            "gc.build.artifact_path_keys": "gc.build.requirements_path",
            "gc.root_bead_id": "root-1",
        }}
        root = {"id": "root-1", "metadata": {"gc.build.requirements_path": str(self.artifact)}}
        if fail:
            body = "echo 'Error 1045 (28000): Access denied for user' >&2\nexit 1\n"
        else:
            body = textwrap.dedent(f"""\
                case "$3" in
                  step-1) printf '%s\\n' {json.dumps(json.dumps(step))} ;;
                  root-1) printf '%s\\n' {json.dumps(json.dumps(root))} ;;
                  *) echo "unknown bead $3" >&2; exit 1 ;;
                esac
                """)
        stub = self.bin / "gc"
        stub.write_text("#!/usr/bin/env bash\nset -eu\n" + body, encoding="utf-8")
        stub.chmod(0o755)

    def run_gate(self, **extra_env: str) -> subprocess.CompletedProcess[str]:
        # Shaped like the orchestrator's sandbox: a short PATH holding the stub
        # gc and pinned python3 plus the directory of the real bash, HOME
        # pointed at the city (not the developer's home), and no inherited
        # PYTHON* vars unless the test sets them.
        bash_dir = str(pathlib.Path(shutil.which("bash")).resolve().parent)
        env = {
            "PATH": os.pathsep.join([str(self.bin), bash_dir, "/usr/bin", "/bin"]),
            "HOME": str(self.city),
            "GC_BEAD_ID": "step-1",
            "GC_STORE_PATH": str(self.city),
        }
        env.update(extra_env)
        return subprocess.run(
            ["bash", str(GATE)], env=env, capture_output=True, text=True, check=False, cwd=str(self.city),
        )

    def pyyaml_pythonpath(self) -> str:
        """Where the test interpreter imported PyYAML from, for the control cases.

        The gate runs with HOME set to the city, so a PyYAML installed in the
        developer's user site is invisible to it (the very failure the 78 path
        reports). The control cases exist to prove 0 and 1 still work when the
        dependency is present, so they hand the gate the directory explicitly.
        """
        try:
            import yaml
        except ImportError:  # pragma: no cover
            self.skipTest("PyYAML is not installed for the test interpreter")
        return str(pathlib.Path(yaml.__file__).resolve().parents[1])

    def first_stderr_line(self, proc: subprocess.CompletedProcess[str]) -> str:
        lines = [line for line in proc.stderr.splitlines() if line.strip()]
        self.assertTrue(lines, f"expected stderr, got none (stdout: {proc.stdout!r})")
        return lines[0]

    def test_valid_artifact_exits_0(self) -> None:
        proc = self.run_gate(PYTHONPATH=self.pyyaml_pythonpath())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("build artifact valid", proc.stdout)

    def test_invalid_content_exits_1(self) -> None:
        self.artifact.write_text("---\nschema: [\n---\n", encoding="utf-8")
        proc = self.run_gate(PYTHONPATH=self.pyyaml_pythonpath())
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("failed validation", self.first_stderr_line(proc))

    def test_gc_failure_exits_75(self) -> None:
        self.write_gc_stub(fail=True)
        proc = self.run_gate()
        self.assertEqual(proc.returncode, 75, proc.stderr)
        first = self.first_stderr_line(proc)
        self.assertIn("build-artifact-check: gc bd show step-1 failed", first)
        self.assertIn("infrastructure unreachable", first)

    def test_missing_python3_exits_78(self) -> None:
        # A PATH with the stub gc, bash and the coreutils the script uses, but
        # no python3 at all.
        bash_dir = str(pathlib.Path(shutil.which("bash")).resolve().parent)
        only = self.tmp / "only"
        only.mkdir()
        os.symlink(self.bin / "gc", only / "gc")
        for tool in ("bash", "env", "dirname", "mktemp", "tail", "tr", "printf", "cat", "rm"):
            found = shutil.which(tool, path=os.pathsep.join([bash_dir, "/usr/bin", "/bin"]))
            if found:
                os.symlink(found, only / tool)
        proc = subprocess.run(
            ["bash", str(GATE)],
            env={"PATH": str(only), "HOME": str(self.city),
                 "GC_BEAD_ID": "step-1", "GC_STORE_PATH": str(self.city)},
            capture_output=True, text=True, check=False, cwd=str(self.city),
        )
        self.assertEqual(proc.returncode, 78, proc.stderr)
        first = self.first_stderr_line(proc)
        self.assertIn("cannot run in this environment", first)
        self.assertIn("python3 is required", first)

    def test_validator_without_pyyaml_exits_78_and_names_the_interpreter(self) -> None:
        # A `yaml` package that raises ImportError sits first on PYTHONPATH:
        # the shape a missing module presents to whichever python3 the gate
        # PATH resolves. The artifact itself is valid, so a 1 here would be the
        # misclassification this status exists to prevent.
        shadow = self.tmp / "shadow" / "yaml"
        shadow.mkdir(parents=True)
        (shadow / "__init__.py").write_text("raise ImportError('shadowed for test')\n", encoding="utf-8")

        proc = self.run_gate(PYTHONPATH=str(shadow.parent))

        self.assertEqual(proc.returncode, 78, proc.stderr)
        lines = [line for line in proc.stderr.splitlines() if line.strip()]
        # The orchestrator records about 256 bytes of the FIRST stderr line as
        # the hold reason, so the validator's diagnosis must come first and
        # name what the operator has to fix within that budget: the module,
        # the interpreter that ran, and the HOME it derived user site from.
        head = lines[0].encode("utf-8")[:256].decode("utf-8", "ignore")
        self.assertTrue(head.startswith("environment error:"), lines[0])
        self.assertIn("PyYAML", head)
        # The interpreter named is the one behind the pinned `python3`, however
        # many symlinks the interpreter itself resolves in sys.executable.
        reported = head.split("not importable by ", 1)[1].split(" (Python", 1)[0]
        self.assertEqual(pathlib.Path(reported).resolve(), pathlib.Path(sys.executable).resolve())
        self.assertIn("HOME=" + repr(str(self.city)), head)
        # The wrapper's own detail follows.
        self.assertTrue(any("cannot run in this environment: validator=" in line for line in lines[1:]), proc.stderr)
        self.assertNotIn("failed validation", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_python3_that_cannot_start_exits_78(self) -> None:
        # The shape of a version-manager shim whose configuration lives under
        # the real HOME: `python3` resolves, then dies before running anything.
        (self.bin / "python3").unlink()
        broken = self.bin / "python3"
        broken.write_text("#!/usr/bin/env bash\necho 'mise ERROR config not trusted under this HOME' >&2\nexit 1\n", encoding="utf-8")
        broken.chmod(0o755)

        proc = self.run_gate()

        self.assertEqual(proc.returncode, 78, proc.stderr)
        first = self.first_stderr_line(proc)
        self.assertIn("cannot run in this environment", first)
        self.assertIn("python3 (", first)
        self.assertIn("cannot start", first)
        self.assertIn("config not trusted", first)

    def test_missing_validator_beside_check_exits_78(self) -> None:
        # A copy of the check installed without its validator is a pack
        # layout problem, not something the producer can repair.
        installed = self.tmp / "installed" / ".gc" / "scripts" / "checks"
        installed.mkdir(parents=True)
        copy = installed / GATE.name
        copy.write_text(GATE.read_text(encoding="utf-8"), encoding="utf-8")
        copy.chmod(0o755)

        bash_dir = str(pathlib.Path(shutil.which("bash")).resolve().parent)
        proc = subprocess.run(
            ["bash", str(copy)],
            env={"PATH": os.pathsep.join([str(self.bin), bash_dir, "/usr/bin", "/bin"]), "HOME": str(self.city),
                 "GC_BEAD_ID": "step-1", "GC_STORE_PATH": str(self.city)},
            capture_output=True, text=True, check=False, cwd=str(self.city),
        )

        self.assertEqual(proc.returncode, 78, proc.stderr)
        first = self.first_stderr_line(proc)
        self.assertIn("cannot run in this environment", first)
        self.assertIn("validate_build_artifact.py not found", first)


if __name__ == "__main__":
    unittest.main()
