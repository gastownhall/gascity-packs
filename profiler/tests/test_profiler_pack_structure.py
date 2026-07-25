from __future__ import annotations

import pathlib
import subprocess
import sys
import tomllib
import unittest

PACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = PACK_ROOT.parent


class PackImportsTests(unittest.TestCase):
    """bench-nullop routes every step to gc.run-operator, which lives in the
    gascity pack. Without the import the pack cannot run standalone."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = tomllib.loads((PACK_ROOT / "pack.toml").read_text(encoding="utf-8"))

    def test_pack_declares_the_gascity_import(self) -> None:
        imports = self.pack.get("imports", {})
        self.assertIn("gc", imports, "profiler must import the gascity pack as `gc`")
        self.assertEqual(imports["gc"]["source"], "../gascity")

    def test_import_alias_matches_sibling_derived_packs(self) -> None:
        # bmad/compound-engineering/gstack/superpowers all bind gascity to `gc`;
        # a different alias would silently break every gc.* run target.
        for sibling in ("bmad", "compound-engineering", "gstack", "superpowers"):
            data = tomllib.loads((REPO_ROOT / sibling / "pack.toml").read_text(encoding="utf-8"))
            self.assertEqual(data["imports"]["gc"]["source"], "../gascity")

    def test_every_bench_nullop_run_target_is_importable(self) -> None:
        formula = tomllib.loads(
            (PACK_ROOT / "formulas" / "bench-nullop.formula.toml").read_text(encoding="utf-8"))
        aliases = set(self.pack.get("imports", {})) | {"profiler"}
        targets = {s["metadata"]["gc.run_target"] for s in formula["steps"]}
        self.assertTrue(targets, "bench-nullop must declare run targets")
        for target in targets:
            alias, _, role = target.partition(".")
            self.assertTrue(role, f"run target {target!r} must be alias-qualified")
            self.assertIn(alias, aliases,
                          f"run target {target!r} names no imported or local pack")

    def test_profile_analyze_routes_to_this_packs_own_role(self) -> None:
        # `gc.` is the gascity binding; a role this pack defines is only
        # reachable under the pack's own binding.
        formula = tomllib.loads(
            (PACK_ROOT / "formulas" / "profile-analyze.formula.toml").read_text(encoding="utf-8"))
        targets = {s["metadata"]["gc.run_target"] for s in formula["steps"]}
        self.assertEqual(targets, {"profiler.profile-analyst"})


class RoleTests(unittest.TestCase):
    ROLE = PACK_ROOT / "agents" / "profile-analyst"

    def test_role_lives_where_gc_discovers_pack_roles(self) -> None:
        # <pack>/agents/<role>/, as in bmad and superpowers. Under
        # <pack>/roles/agents/ the role is not discovered at all.
        self.assertTrue((self.ROLE / "agent.toml").exists(),
                        "profile-analyst must live in profiler/agents/")
        self.assertFalse((PACK_ROOT / "roles").exists(),
                         "profiler/roles/ is not a role location gc reads")

    def test_role_prompt_composes_the_shared_worker_fragment(self) -> None:
        prompt = (self.ROLE / "prompt.template.md").read_text(encoding="utf-8")
        self.assertIn('{{ template "gc-role-worker" . }}', prompt)
        self.assertTrue(prompt.startswith("# Profile Analyst"))
        # No inlined fork of the shared prompt: that is how the claim protocol
        # silently rots out of sync with gascity.
        self.assertNotIn("# GC Role Worker", prompt)
        self.assertNotIn("GC_CLAIM", prompt)
        self.assertLess(len(prompt.splitlines()), 40, "persona files stay short")

    def test_role_prompt_states_the_analysts_own_job(self) -> None:
        prompt = (self.ROLE / "prompt.template.md").read_text(encoding="utf-8")
        for token in ("report.json", "manifest.json", "read-only"):
            self.assertIn(token, prompt)

    def test_shared_fragment_is_reachable_through_the_gascity_import(self) -> None:
        # The fragment ships in gascity only; without [imports.gc] the template
        # reference above cannot resolve.
        fragment = REPO_ROOT / "gascity" / "template-fragments" / "gc-role-worker.template.md"
        self.assertIn('{{ define "gc-role-worker"',
                      fragment.read_text(encoding="utf-8"))


class CommandWiringTests(unittest.TestCase):
    COMMANDS = ("collect", "report", "compare")

    def test_each_command_points_at_an_executable_wrapper(self) -> None:
        for name in self.COMMANDS:
            data = tomllib.loads(
                (PACK_ROOT / "commands" / name / "command.toml").read_text(encoding="utf-8"))
            self.assertEqual(data["run"], f"../{name}.sh")
            wrapper = PACK_ROOT / "commands" / f"{name}.sh"
            self.assertTrue(wrapper.exists(), f"{name}.sh missing")
            self.assertTrue(wrapper.stat().st_mode & 0o111, f"{name}.sh not executable")
            self.assertTrue(data.get("description"), f"{name} needs a description")
            # Every other command in this repo ships help.md; `gc <binding>
            # <cmd> --help` shows only the one-line description without it.
            help_md = PACK_ROOT / "commands" / name / "help.md"
            self.assertTrue(help_md.exists(), f"{name} needs help.md")
            self.assertIn(f"gc profiler {name}", help_md.read_text(encoding="utf-8"))

    def test_wrapper_refuses_to_run_outside_a_pack_context(self) -> None:
        # The wrappers exec python against $GC_PACK_DIR; with no context they must
        # fail loudly rather than exec a path built from an empty variable.
        for name in self.COMMANDS:
            proc = subprocess.run(
                ["sh", str(PACK_ROOT / "commands" / f"{name}.sh")],
                capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
            self.assertEqual(proc.returncode, 1, f"{name}.sh should exit 1: {proc!r}")
            self.assertIn("missing Gas City pack context", proc.stderr)

    def test_wrapper_dispatches_to_its_script(self) -> None:
        for name, script in (("collect", "profile_collect.py"),
                             ("report", "profile_report.py"),
                             ("compare", "profile_compare.py")):
            body = (PACK_ROOT / "commands" / f"{name}.sh").read_text(encoding="utf-8")
            self.assertIn(f'"$GC_PACK_DIR/scripts/{script}"', body)
            self.assertTrue((PACK_ROOT / "scripts" / script).exists())


class ReadmeClaimsTests(unittest.TestCase):
    """The README is the pack's contract. These pin the claims that were wrong
    once, so they cannot silently drift back."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = (PACK_ROOT / "README.md").read_text(encoding="utf-8")
        cls.report_src = (PACK_ROOT / "scripts" / "profile_report.py").read_text(encoding="utf-8")

    def test_readme_documents_the_gascity_prerequisite(self) -> None:
        self.assertIn("../gascity", self.readme)

    def test_readme_token_cost_claim_is_backed_by_report_code(self) -> None:
        self.assertIn("usage.window.jsonl", self.readme)
        self.assertIn("usage.window.jsonl", self.report_src,
                      "README promises a usage rollup; report.py must actually read it")

    def test_readme_surfaces_the_unpriced_caveat(self) -> None:
        self.assertIn("unpriced", self.readme)

    def test_documented_command_prefix_matches_the_import_binding(self) -> None:
        # gc namespaces pack commands under the import binding: `gc <binding>
        # <command>`, as with `gc github ...` / `gc slack ...`. `gc profile ...`
        # never resolves.
        for doc in ("README.md", "formulas/profile-analyze.formula.toml",
                    "formulas/bench-nullop.formula.toml",
                    "agents/profile-analyst/prompt.template.md"):
            text = (PACK_ROOT / doc).read_text(encoding="utf-8")
            self.assertNotIn("gc profile ", text, f"{doc} documents a prefix gc does not register")
        for name in ("collect", "report", "compare"):
            self.assertIn(f"gc profiler {name}", self.readme)

    def test_readme_does_not_advertise_a_transcript_archive_order(self) -> None:
        # Dropped in 917764f: the pack profiles existing storage, it does not
        # back transcripts up.
        self.assertNotIn("transcript-archive", self.readme)
        self.assertFalse((PACK_ROOT / "orders").exists(),
                         "the pack ships no orders")


class ScriptHygieneTests(unittest.TestCase):
    def test_python_scripts_compile(self) -> None:
        scripts = sorted((PACK_ROOT / "scripts").glob("*.py"))
        self.assertTrue(scripts)
        proc = subprocess.run([sys.executable, "-m", "py_compile", *map(str, scripts)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_shell_wrappers_parse(self) -> None:
        wrappers = sorted((PACK_ROOT / "commands").glob("*.sh"))
        self.assertTrue(wrappers)
        for wrapper in wrappers:
            proc = subprocess.run(["sh", "-n", str(wrapper)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"{wrapper.name}: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
