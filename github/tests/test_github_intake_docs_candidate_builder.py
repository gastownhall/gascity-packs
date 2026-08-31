from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import github_intake_docs_candidate_builder as builder


SHA = "a" * 40


def assignment(head_sha: str = SHA) -> dict[str, object]:
    return {"schema_version": 1, "kind": "github-pr-docs-impact-assignment", "identity": {"repository_id": "17", "repository": "allenday/demo", "pr_number": 9, "head_sha": head_sha, "source_key": f"github-pr:17:9:{head_sha}"}, "agent_skill": "developer-experience-techdocs", "evidence_bundle": {"head_sha": head_sha, "proposal_identity": {"repository_id": "17", "repository": "allenday/demo", "pr_number": 9, "base_sha": "b" * 40, "head_sha": head_sha, "head_repository_id": "17", "head_repository": "allenday/demo", "base_ref": "main"}, "files": [{"path": "docs/guide.md", "reference": f"github://allenday/demo/blob/{head_sha}/docs/guide.md", "patch": "@@ -1 +1 @@\n-old\n+new\n"}]}}


def decision(head_sha: str) -> dict[str, object]:
    source = assignment(head_sha)
    return {"schema_version": 1, "kind": "github-pr-docs-impact-review", "identity": source["identity"], "agent_skill": source["agent_skill"], "verdict": "proposal-ready", "rationale": "Ready for a generated proposal.", "evidence": [{"path": "docs/guide.md", "evidence": f"github://allenday/demo/blob/{head_sha}/docs/guide.md"}], "confidence": 0.9, "proposal": None}


class CandidateBuilderTests(unittest.TestCase):
    def test_proposal_ready_review_receives_only_git_derived_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = pathlib.Path(temp_dir)
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
            (repo / "docs").mkdir()
            (repo / "docs" / "guide.md").write_text("Old guidance.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "base"], check=True)
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            (repo / "docs" / "guide.md").write_text("New guidance.\n", encoding="utf-8")
            source = assignment(head)
            review = {"schema_version": 1, "kind": "github-pr-docs-impact-review", "identity": source["identity"], "agent_skill": source["agent_skill"], "verdict": "proposal-ready", "rationale": "Ready for a generated proposal.", "evidence": [{"path": "docs/guide.md", "evidence": f"github://allenday/demo/blob/{head}/docs/guide.md"}], "confidence": 0.9, "proposal": None}
            candidate = builder.build_candidate(json.dumps(source).encode(), repo, generated_at="2026-08-31T12:00:00Z", claims=[{"claim": "A claim.", "evidence": f"github://allenday/demo/blob/{head}/docs/guide.md", "release_scope": "unreleased"}], checks=[{"command": "true", "status": "passed", "explanation": "ok"}], review=review)
            self.assertEqual(candidate["artifact"]["verdict"], "proposal-ready")
            self.assertIn("diff --git", candidate["artifact"]["proposal"]["diff"])

    def test_build_candidate_derives_a_docs_only_git_diff_and_binds_raw_assignment_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = pathlib.Path(temp_dir)
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
            (repo / "docs").mkdir()
            (repo / "docs" / "guide.md").write_text("Old guidance.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "base"], check=True)
            (repo / "docs" / "guide.md").write_text("New guidance.\n", encoding="utf-8")
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            raw = json.dumps(assignment(head), separators=(",", ":")).encode()
            envelope = builder.build_candidate(raw, repo, generated_at="2026-08-31T12:00:00Z", claims=[{"claim": "The guide documents the workflow.", "evidence": f"github://allenday/demo/blob/{head}/docs/guide.md", "release_scope": "unreleased"}], checks=[{"command": "make docs-check", "status": "passed", "explanation": "Documentation checks passed."}], review=decision(head))
            self.assertEqual(envelope["artifact"]["kind"], "github-pr-docs-impact-review")
            self.assertEqual(envelope["snapshot_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertIn("diff --git a/docs/guide.md b/docs/guide.md", envelope["artifact"]["proposal"]["diff"])
            self.assertEqual(envelope["artifact"]["proposal"]["files"], [{"path": "docs/guide.md", "sha256": envelope["artifact"]["proposal"]["files"][0]["sha256"]}])

    def test_builder_rejects_a_checkout_whose_head_is_not_the_assigned_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = pathlib.Path(temp_dir)
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
            (repo / "docs").mkdir()
            (repo / "docs" / "guide.md").write_text("Old guidance.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "base"], check=True)
            with self.assertRaisesRegex(ValueError, "HEAD"):
                builder.build_candidate(json.dumps(assignment()).encode(), repo, generated_at="2026-08-31T12:00:00Z", claims=[{"claim": "A claim.", "evidence": f"github://allenday/demo/blob/{SHA}/docs/guide.md", "release_scope": "unreleased"}], checks=[{"command": "true", "status": "passed", "explanation": "ok"}], review=decision(SHA))

    def test_build_candidate_rejects_a_non_documentation_git_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = pathlib.Path(temp_dir)
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
            (repo / "app.py").write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "base"], check=True)
            (repo / "app.py").write_text("after\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "documentation path"):
                head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
                builder.build_candidate(json.dumps(assignment(head)).encode(), repo, generated_at="2026-08-31T12:00:00Z", claims=[{"claim": "A claim.", "evidence": f"github://allenday/demo/blob/{head}/docs/guide.md", "release_scope": "unreleased"}], checks=[{"command": "true", "status": "passed", "explanation": "ok"}], review=decision(head))


if __name__ == "__main__":
    unittest.main()
