from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = REPO_ROOT / "gstack/skills/gstack-lite/scripts/audit_city.py"
VALID_PACK = """\
[pack]
name = "city"
schema = 2

[imports.gstack]
source = "gstack"
"""
VALID_CITY = """\
[agent_defaults]
append_fragments = ["gstack-lite-policy"]

[providers.sol-research]
base = "builtin:codex"
[providers.sol-research.option_defaults]
model = "gpt-5.6-sol"
effort = "max"
[providers.sol-fast]
base = "builtin:codex"
[providers.luna-economy]
base = "builtin:codex"
[providers.claude-careful]
base = "builtin:claude"
[providers.claude-review]
base = "builtin:claude"
[providers.sol-rescue]
base = "builtin:codex"

[defaults.rig.imports.gc]
source = "gc"

[[patches.agent]]
name = "gastown.mayor"
[patches.agent.option_defaults]
model = "gpt-5.6-sol"
effort = "high"

[[patches.agent]]
dir = "demo"
name = "gc.research-planner"
provider = "sol-research"
max_active_sessions = 1

[[patches.agent]]
dir = "demo"
name = "gc.implementation-reviewer"
provider = "claude-review"
max_active_sessions = 1

[[rigs]]
name = "demo"
suspended_on_start = true
max_active_sessions = 5
[rigs.imports.gc]
source = "gc"

[[rigs.patches]]
agent = "polecat"
[rigs.patches.pool]
max = 2
"""


def load_audit_module():
    spec = importlib.util.spec_from_file_location("gstack_lite_audit", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {AUDIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_city(root: Path, city_toml: str = VALID_CITY, pack_toml: str = VALID_PACK) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "city.toml").write_text(city_toml, encoding="utf-8")
    (root / "pack.toml").write_text(pack_toml, encoding="utf-8")
    return root


class GstackLiteContractTests(unittest.TestCase):
    def test_formula_catalog_accepts_null_for_an_empty_catalog(self) -> None:
        audit_module = load_audit_module()
        completed = subprocess.CompletedProcess(
            args=["gc", "formula", "list", "--json"],
            returncode=0,
            stdout='{"ok":true,"formulas":null}',
            stderr="",
        )
        with mock.patch.object(audit_module.subprocess, "run", return_value=completed):
            names, error = audit_module.active_formula_names(Path("/tmp"))
        self.assertEqual(names, set())
        self.assertIsNone(error)

    def test_skill_is_concise_and_owns_generic_delivery_triggers(self) -> None:
        skill = (REPO_ROOT / "gstack/skills/gstack-lite/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: gstack-lite", skill)
        self.assertIn("Use by default for Gas City requests", skill)
        self.assertIn("Never install or launch a retired delivery graph", skill)
        self.assertIn("Do not mention retired", skill)
        self.assertNotIn("TODO", skill)
        self.assertLess(len(skill.splitlines()), 240)

    def test_mayor_and_prompt_fragment_default_to_gstack_lite(self) -> None:
        mayor = (REPO_ROOT / "gascity/skills/mayor/SKILL.md").read_text(encoding="utf-8")
        fragment = (
            REPO_ROOT / "gascity/template-fragments/gstack-lite-policy.template.md"
        ).read_text(encoding="utf-8")
        self.assertIn("## Default Delivery Policy", mayor)
        self.assertIn("Do not mention retired workflow names", mayor)
        self.assertIn('{{ define "gstack-lite-policy" -}}', fragment)
        self.assertIn("one consolidated exact-head", fragment)
        self.assertIn("sol-research", fragment)
        self.assertIn("Sol/max", fragment)
        self.assertIn("--no-formula", fragment)
        for content in (mayor, fragment):
            self.assertIn("gc session attach", content)
            self.assertIn("READY_FOR_ATTACH", content)
            self.assertIn("/home/nvidia/gascity/reports", content)
            self.assertIn("HTML/CSS", content)
        self.assertIn("autostart=true", mayor)
        self.assertIn("gc session logs", mayor)
        self.assertIn("queue autonomous continuation", mayor)
        self.assertIn("--intent follow_up", mayor)

    def test_active_policy_surfaces_require_consolidated_review_before_repair(self) -> None:
        canonical = (REPO_ROOT / "gstack/skills/gstack-lite/SKILL.md").read_text(
            encoding="utf-8"
        )
        mayor = (REPO_ROOT / "gascity/skills/mayor/SKILL.md").read_text(
            encoding="utf-8"
        )
        public_fragment = (
            REPO_ROOT / "gascity/template-fragments/gstack-lite-policy.template.md"
        ).read_text(encoding="utf-8")
        roles_fragment = (
            REPO_ROOT
            / "gascity/roles/template-fragments/gstack-lite-policy.template.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(public_fragment, roles_fragment)
        for content in (canonical, mayor, public_fragment):
            normalized = " ".join(content.split())
            self.assertIn("required CI", normalized)
            self.assertIn("external PR", normalized)
            self.assertIn("bounded", normalized)
            self.assertIn("timeout", normalized)
            self.assertIn("unavailable", normalized)
            self.assertIn("exact repaired head", normalized)
            self.assertIn("safety", normalized.lower())
            self.assertIn("blocks", normalized.lower())

        self.assertIn("never repair serially", canonical)
        self.assertLess(
            canonical.index("external PR review bots"),
            canonical.index("single repair allowance"),
        )

    def test_active_policy_preserves_rejected_work_for_rescue(self) -> None:
        canonical = (REPO_ROOT / "gstack/skills/gstack-lite/SKILL.md").read_text(
            encoding="utf-8"
        )
        mayor = (REPO_ROOT / "gascity/skills/mayor/SKILL.md").read_text(
            encoding="utf-8"
        )
        fragment = (
            REPO_ROOT / "gascity/template-fragments/gstack-lite-policy.template.md"
        ).read_text(encoding="utf-8")

        for content in (canonical, mayor, fragment):
            normalized = " ".join(content.split())
            self.assertIn("exact commit", normalized)
            self.assertIn("diff", normalized)
            self.assertIn("evidence", normalized)
            self.assertIn(
                "carries the failed candidate forward by default", normalized
            )
            self.assertIn("rebuild from protected", normalized.lower())
            self.assertIn("architecture, provenance, or security", normalized)

        self.assertNotIn(
            "delete any protection-required PR branch after\n  merge", fragment
        )

    def test_research_planner_is_persistent_attachable_and_publishes(self) -> None:
        role_root = REPO_ROOT / "gascity/roles/agents/research-planner"
        agent = (role_root / "agent.toml").read_text(encoding="utf-8")
        prompt = (role_root / "prompt.template.md").read_text(encoding="utf-8")
        self.assertIn('scope = "rig"', agent)
        self.assertIn("persistent, attachable", prompt)
        self.assertIn("Do not call `gc runtime drain-ack`", prompt)
        self.assertIn("do not run `gc hook --claim`", prompt)
        self.assertIn("`autostart=true`", prompt)
        self.assertIn("exactly `READY_FOR_ATTACH`", prompt)
        self.assertIn("research immediately", prompt)
        self.assertIn("Within 30 seconds", prompt)
        self.assertIn("without waiting for attachment", prompt)
        self.assertIn("not permission to start work", prompt)
        self.assertIn("/home/nvidia/gascity/reports", prompt)
        self.assertIn("gascity.tail96374b.ts.net/reports", prompt)

    def test_complete_delivery_is_historical_only(self) -> None:
        readme = (REPO_ROOT / "complete-delivery/README.md").read_text(encoding="utf-8")
        archived_readme = (
            REPO_ROOT / "deprecated/complete-delivery/README.md"
        ).read_text(encoding="utf-8")
        registry = (REPO_ROOT / "registry.toml").read_text(encoding="utf-8")
        self.assertFalse((REPO_ROOT / "complete-delivery/skills").exists())
        self.assertIn("registry-compatible tombstone", readme)
        self.assertIn("ARCHIVED / DEPRECATED", archived_readme)
        self.assertIn("DEPRECATED historical pack", registry)

    def test_audit_removes_only_exact_stale_skill_symlinks(self) -> None:
        audit_module = load_audit_module()
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(Path(tmp))
            skill_dir = city / ".gc/agents/demo/.codex/skills"
            skill_dir.mkdir(parents=True)
            stale = skill_dir / "complete-delivery.complete-delivery"
            stale.symlink_to("/cache/complete-delivery/skills/complete-delivery")
            unrelated = skill_dir / "keep-me"
            unrelated.symlink_to("/cache/gstack/skills/review")
            same_name_unrelated_target = (
                city / ".agents/skills/complete-delivery.complete-delivery"
            )
            same_name_unrelated_target.parent.mkdir(parents=True)
            same_name_unrelated_target.symlink_to("/cache/gstack/skills/review")
            regular_same_name = (
                city / ".claude/skills/complete-delivery.complete-delivery"
            )
            regular_same_name.parent.mkdir(parents=True)
            regular_same_name.write_text("preserve me", encoding="utf-8")

            with mock.patch.object(
                audit_module, "active_formula_names", return_value=(set(), None)
            ):
                errors, _ = audit_module.audit(city, fix_stale_skills=False)
                self.assertIn("1 stale Complete Delivery skill symlink(s) remain", errors)
                errors, notes = audit_module.audit(city, fix_stale_skills=True)
            self.assertEqual(errors, [])
            self.assertTrue(any("removed stale skill symlink" in note for note in notes))
            self.assertFalse(stale.exists())
            self.assertTrue(unrelated.is_symlink())
            self.assertTrue(same_name_unrelated_target.is_symlink())
            self.assertTrue(regular_same_name.is_file())

    def test_audit_reports_each_configuration_guard(self) -> None:
        audit_module = load_audit_module()
        city_without_rig_table = "rigs = [\"demo\"]\n" + VALID_CITY.split("[[rigs]]", 1)[0]
        cases = [
            (
                "missing gstack import",
                VALID_CITY,
                "[pack]\nname = \"city\"\nschema = 2\n",
                "city pack must import gstack",
            ),
            (
                "active Complete Delivery import",
                VALID_CITY,
                VALID_PACK + "\n[imports.complete-delivery]\nsource = \"legacy\"\n",
                "city pack still contains an active Complete Delivery import",
            ),
            (
                "Complete Delivery city setting",
                VALID_CITY + "\n[metadata]\npolicy = \"complete-delivery\"\n",
                VALID_PACK,
                "city.toml still contains active Complete Delivery configuration",
            ),
            (
                "missing provider",
                VALID_CITY.replace(
                    '[providers.sol-fast]\nbase = "builtin:codex"\n', ""
                ),
                VALID_PACK,
                "missing provider aliases: sol-fast",
            ),
            (
                "research provider is not max Sol",
                VALID_CITY.replace('effort = "max"', 'effort = "xhigh"', 1),
                VALID_PACK,
                "sol-research must use gpt-5.6-sol at max effort",
            ),
            (
                "persistent Mayor is not high Sol",
                VALID_CITY.replace('effort = "high"', 'effort = "max"', 1),
                VALID_PACK,
                "persistent gastown.mayor must use gpt-5.6-sol at high effort",
            ),
            (
                "missing policy fragment",
                VALID_CITY.replace(
                    'append_fragments = ["gstack-lite-policy"]',
                    "append_fragments = []",
                ),
                VALID_PACK,
                "agent_defaults.append_fragments must include gstack-lite-policy",
            ),
            (
                "missing future rig role",
                VALID_CITY.replace(
                    "[defaults.rig.imports.gc]", "[defaults.rig.imports.other]"
                ),
                VALID_PACK,
                "future rigs must inherit the gc roles import",
            ),
            (
                "missing current rig role",
                VALID_CITY.replace("[rigs.imports.gc]", "[rigs.imports.other]"),
                VALID_PACK,
                "current rigs missing explicit gc roles import: demo",
            ),
            (
                "missing reviewer patch",
                VALID_CITY.replace(
                    'name = "gc.implementation-reviewer"', 'name = "other"'
                ),
                VALID_PACK,
                "current rigs need exactly one Claude gc.implementation-reviewer patch: demo",
            ),
            (
                "missing research singleton",
                VALID_CITY.replace(
                    'dir = "demo"\nname = "gc.research-planner"',
                    'dir = "demo"\nname = "other-research"',
                ),
                VALID_PACK,
                "current rigs need exactly one singleton Sol/max gc.research-planner patch: demo",
            ),
            (
                "unsafe research concurrency",
                VALID_CITY.replace(
                    'name = "gc.research-planner"\nprovider = "sol-research"\nmax_active_sessions = 1',
                    'name = "gc.research-planner"\nprovider = "sol-research"\nmax_active_sessions = 2',
                ),
                VALID_PACK,
                "current rigs need exactly one singleton Sol/max gc.research-planner patch: demo",
            ),
            (
                "missing research provider binding",
                VALID_CITY.replace(
                    'provider = "sol-research"\nmax_active_sessions = 1',
                    'provider = "sol-fast"\nmax_active_sessions = 1',
                    1,
                ),
                VALID_PACK,
                "current rigs need exactly one singleton Sol/max gc.research-planner patch: demo",
            ),
            (
                "nonexistent global reviewer scope",
                VALID_CITY.replace(
                    'dir = "demo"\nname = "gc.implementation-reviewer"',
                    'name = "gc.implementation-reviewer"',
                ),
                VALID_PACK,
                "gc.implementation-reviewer patches target unknown scopes: <city>",
            ),
            (
                "invalid rigs shape",
                city_without_rig_table,
                VALID_PACK,
                "city.toml rigs must be an array of tables",
            ),
            (
                "unsafe startup",
                VALID_CITY.replace("suspended_on_start = true", "suspended_on_start = false"),
                VALID_PACK,
                "current rigs must set suspended_on_start=true: demo",
            ),
            (
                "unsafe total session cap",
                VALID_CITY.replace("max_active_sessions = 5", "max_active_sessions = 6"),
                VALID_PACK,
                "current rigs must cap max_active_sessions between 1 and 5: demo",
            ),
            (
                "unsafe writer cap",
                VALID_CITY.replace("max = 2", "max = 3"),
                VALID_PACK,
                "current rigs must set one polecat pool cap between 1 and 2: demo",
            ),
            (
                "malformed writer pool",
                VALID_CITY.replace("[rigs.patches.pool]\nmax = 2", "pool = 2"),
                VALID_PACK,
                "current rigs must set one polecat pool cap between 1 and 2: demo",
            ),
        ]

        for label, city_toml, pack_toml, expected in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                city = write_city(Path(tmp), city_toml, pack_toml)
                errors, _ = audit_module.audit(city, fix_stale_skills=False)
                self.assertIn(expected, errors)

    def test_audit_handles_missing_and_malformed_city_files(self) -> None:
        audit_module = load_audit_module()
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            errors, _ = audit_module.audit(missing, fix_stale_skills=False)
            self.assertIn("is not a Gas City root", errors[0])

            malformed = write_city(Path(tmp) / "malformed", city_toml="[")
            errors, _ = audit_module.audit(malformed, fix_stale_skills=False)
            self.assertIn("cannot read", errors[0])
            self.assertIn("city.toml", errors[0])

    def test_cleanup_reports_unlink_failure_and_preserves_link(self) -> None:
        audit_module = load_audit_module()
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(Path(tmp))
            stale = city / ".codex/skills/complete-delivery.complete-delivery"
            stale.parent.mkdir(parents=True)
            stale.symlink_to("/cache/complete-delivery/skills/complete-delivery")
            original_unlink = Path.unlink

            def fail_stale_unlink(path: Path, *args, **kwargs):
                if path == stale:
                    raise PermissionError("test denial")
                return original_unlink(path, *args, **kwargs)

            with mock.patch.object(audit_module.Path, "unlink", fail_stale_unlink):
                errors, _ = audit_module.audit(city, fix_stale_skills=True)

            self.assertTrue(stale.is_symlink())
            self.assertTrue(
                any("could not remove stale skill symlink" in error for error in errors)
            )

    def test_cli_exit_codes_and_fail_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            city = write_city(Path(tmp))
            fake_bin = Path(tmp) / "bin"
            fake_bin.mkdir()
            fake_gc = fake_bin / "gc"
            fake_gc.write_text(
                "#!/bin/sh\nprintf '%s\\n' '{\"formulas\":[]}'\n",
                encoding="utf-8",
            )
            fake_gc.chmod(0o755)
            env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
            passed = subprocess.run(
                [sys.executable, str(AUDIT_PATH), "--city", str(city)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertIn("PASS Gstack Lite city contract", passed.stdout)

            (city / "city.toml").write_text("[", encoding="utf-8")
            failed = subprocess.run(
                [sys.executable, str(AUDIT_PATH), "--city", str(city)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(failed.returncode, 1)
            self.assertIn("FAIL cannot read", failed.stderr)
            self.assertNotIn("Traceback", failed.stderr)


if __name__ == "__main__":
    unittest.main()
