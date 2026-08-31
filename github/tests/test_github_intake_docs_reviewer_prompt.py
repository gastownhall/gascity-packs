from __future__ import annotations

import pathlib
import tomllib
import unittest


GITHUB_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT_ROOT = GITHUB_ROOT / "agents" / "docs-impact-reviewer"


class DocsImpactReviewerPackageTests(unittest.TestCase):
    def test_agent_is_a_credential_free_techdocs_reviewer(self) -> None:
        metadata = tomllib.loads((AGENT_ROOT / "agent.toml").read_text(encoding="utf-8"))

        self.assertEqual(metadata["description"], "GitHub pull-request documentation impact reviewer")
        self.assertEqual(metadata["scope"], "rig")
        self.assertFalse(metadata["fallback"])

    def test_prompt_returns_only_a_validator_compatible_review_decision(self) -> None:
        prompt = (AGENT_ROOT / "prompt.template.md").read_text(encoding="utf-8")

        self.assertIn("github-pr-docs-impact-review", prompt)
        self.assertIn('"agent_skill": "developer-experience-techdocs"', prompt)
        self.assertIn('"proposal": null', prompt)
        self.assertIn("evidence_bundle", prompt)
        self.assertIn("developer-experience-techdocs/SKILL.md", prompt)

    def test_reviewer_metadata_and_prompt_remain_deployment_neutral_and_credential_free(self) -> None:
        artifacts = [
            AGENT_ROOT / "agent.toml",
            AGENT_ROOT / "prompt.template.md",
        ]
        content = "\n".join(path.read_text(encoding="utf-8").lower() for path in artifacts)

        for forbidden in (
            "github_token",
            "github_app_private_key",
            "provider",
            "docker compose",
            "tailnet",
            "dashboard",
            "manual diff",
            "git diff",
            "localhost",
            "/root/",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)

    def test_vendored_techdocs_skill_is_available_to_the_reviewer(self) -> None:
        skill = GITHUB_ROOT / "skills" / "developer-experience-techdocs" / "SKILL.md"

        self.assertTrue(skill.is_file())
        self.assertIn("Developer-experience technical documentation", skill.read_text(encoding="utf-8"))

    def test_rendered_prompt_is_assignment_only_and_non_mutating(self) -> None:
        rendered = (AGENT_ROOT / "prompt.template.md").read_text(encoding="utf-8")

        self.assertNotIn("{{", rendered)
        for forbidden in (
            "gc ",
            "bead",
            "runtime ack",
            "worktree",
            "local workspace",
            "manual diff",
            "git diff",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, rendered.lower())

    def test_candidate_documentation_uses_an_executable_neutral_projection(self) -> None:
        lifecycle = (GITHUB_ROOT / "docs" / "docs-pr-review-lifecycle.md").read_text(encoding="utf-8")

        self.assertIn(
            "candidate --once --candidate-file <candidate.json> --projection action-file \\\n  --actions-file <actions.json>",
            lifecycle,
        )


if __name__ == "__main__":
    unittest.main()
