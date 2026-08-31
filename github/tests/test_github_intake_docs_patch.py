from __future__ import annotations

import copy
import hashlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import github_intake_docs_patch as docs_patch


SHA = "a" * 40
BASE = "b" * 40
DIFF = """diff --git a/docs/guide.md b/docs/guide.md
index 1111111..2222222 100644
--- a/docs/guide.md
+++ b/docs/guide.md
@@ -1 +1 @@
-Old guidance.
+New guidance.
"""


def proposal() -> dict[str, object]:
    return {"schema_version": 1, "status": "proposed", "generated_at": "2026-08-31T12:00:00Z", "identity": {"repository_id": "17", "repository": "allenday/demo", "pr_number": 9, "base_sha": BASE, "head_sha": SHA, "head_repository_id": "17", "head_repository": "allenday/demo", "base_ref": "main"}, "patch_sha256": hashlib.sha256(DIFF.encode()).hexdigest(), "diff": DIFF, "files": [{"path": "docs/guide.md", "sha256": "c" * 64}], "claims": [{"claim": "The guide documents the workflow.", "evidence": f"github://allenday/demo/blob/{SHA}/README.md", "release_scope": "unreleased"}], "checks": [{"command": "make docs-check", "status": "passed", "explanation": "Documentation checks passed."}]}


def review() -> dict[str, object]:
    return {"schema_version": 1, "kind": "github-pr-docs-impact-review", "identity": {"repository_id": "17", "repository": "allenday/demo", "pr_number": 9, "head_sha": SHA, "source_key": f"github-pr:17:9:{SHA}"}, "agent_skill": "developer-experience-techdocs", "verdict": "proposal-ready", "rationale": "A bounded documentation patch is ready.", "evidence": [{"path": "docs/guide.md", "evidence": f"github://allenday/demo/blob/{SHA}/docs/guide.md"}], "confidence": 0.9, "proposal": proposal()}


class DocsPatchTests(unittest.TestCase):
    def test_review_decision_accepts_every_non_proposal_verdict(self) -> None:
        for verdict in ("no-impact", "docs-sufficient", "docs-change-required", "inconclusive"):
            with self.subTest(verdict=verdict):
                value = review()
                value["verdict"] = verdict
                value["proposal"] = None
                self.assertEqual(docs_patch.validate_review_decision(value)["verdict"], verdict)
    def test_proposal_ready_requires_a_complete_proposal(self) -> None:
        value = review()
        value["proposal"] = None
        with self.assertRaisesRegex(ValueError, "proposal-ready"):
            docs_patch.validate_agent_review(value)

    def test_review_rejects_proposal_identity_that_is_not_exactly_the_review_source(self) -> None:
        value = review()
        value["proposal"]["identity"]["repository"] = "allenday/other"
        with self.assertRaisesRegex(ValueError, "proposal identity"):
            docs_patch.validate_agent_review(value)

    def test_review_digest_covers_canonical_proposal(self) -> None:
        validated = docs_patch.validate_agent_review(review())
        changed = copy.deepcopy(validated)
        changed["proposal"]["claims"][0]["claim"] = "Changed after validation."
        changed["proposal"].pop("artifact_sha256")
        with self.assertRaisesRegex(ValueError, "review_sha256"):
            docs_patch.validate_agent_review(changed)

    def test_artifact_rejects_gitlink_and_boolean_integral_fields(self) -> None:
        gitlink = proposal()
        gitlink["diff"] = DIFF.replace("index 1111111..2222222 100644", "new file mode 160000\nindex 1111111..2222222 160000")
        gitlink["patch_sha256"] = hashlib.sha256(gitlink["diff"].encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "gitlink"):
            docs_patch.validate_artifact(gitlink)
        for field, value in (("schema_version", True), ("pr_number", True)):
            malformed = proposal()
            if field == "schema_version":
                malformed[field] = value
            else:
                malformed["identity"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                docs_patch.validate_artifact(malformed)


if __name__ == "__main__":
    unittest.main()
