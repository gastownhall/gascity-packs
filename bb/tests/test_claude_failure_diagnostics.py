"""Private native evidence may yield only finite public failure metadata."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from live_acceptance import claude_failure_diagnostics


class ClaudeFailureDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "claude-config/projects/owned"
        self.project.mkdir(parents=True)
        self.answer = 'API Error: 403 secret-token-private-model-request'
        self.report = {"status": "failed", "marker_mismatch": {
            "output_sha256": hashlib.sha256(self.answer.encode()).hexdigest()}}

    def write(self, entry, name="session.jsonl"):
        (self.project / name).write_text(json.dumps(entry) + "\n")

    def entry(self, **fields):
        return {"type": "assistant", "isApiErrorMessage": True,
                "message": {"model": "secret-model", "content": [{"type": "text", "text": self.answer}]},
                "apiError": "dlp_request_denied", "error": "authentication_failed",
                "errorDetails": "secret-details", "requestId": "secret-request", **fields}

    def test_exact_native_match_emits_only_allowlisted_fields(self):
        self.write(self.entry())
        before = copy.deepcopy(self.report)
        result = claude_failure_diagnostics(self.root, self.report)
        self.assertEqual(result, {"status": "matched", "matching_records": 1, "classifications": [{
            "is_api_error_message": True, "api_error": "dlp_request_denied",
            "error": "authentication_failed", "http_status": 403}]})
        self.assertEqual(self.report, before)
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(self.report["status"], "failed")

    def test_unknown_fields_and_model_generated_api_words_are_not_native_errors(self):
        self.write(self.entry(isApiErrorMessage=False, apiError="secret-enum", error="secret-error"))
        result = claude_failure_diagnostics(self.root, self.report)
        self.assertEqual(result["classifications"], [{"is_api_error_message": False}])
        self.assertNotIn("secret", json.dumps(result))

    def test_unknown_native_error_fields_are_omitted(self):
        self.write(self.entry(apiError={"message": "secret-payload"}, error="secret-error"))
        result = claude_failure_diagnostics(self.root, self.report)
        self.assertEqual(result["classifications"], [{"is_api_error_message": True, "http_status": 403}])
        self.assertNotIn("secret", json.dumps(result))

    def test_native_http_status_is_preferred_and_strictly_bounded(self):
        for index, (value, expected) in enumerate(((401, 401), (599, 599),
                                                  (True, 403), ("secret", 403),
                                                  (400.0, 403), (399, 403), (600, 403))):
            with self.subTest(value=value):
                owned = self.root / str(index)
                project = owned / "claude-config/projects/owned"
                project.mkdir(parents=True)
                (project / "session.jsonl").write_text(json.dumps(self.entry(apiErrorStatus=value)) + "\n")
                result = claude_failure_diagnostics(owned, self.report)
                self.assertEqual(result["classifications"][0]["http_status"], expected)
                self.assertNotIn("secret", json.dumps(result))
                self.assertEqual(self.report["status"], "failed")

    def test_matches_a_single_completed_text_block(self):
        entry = self.entry()
        entry["message"]["content"].insert(0, {"type": "text", "text": "private earlier block"})
        self.write(entry)
        result = claude_failure_diagnostics(self.root, self.report)
        self.assertEqual(result["status"], "matched")
        self.assertNotIn("private", json.dumps(result))

    def test_unrelated_reply_or_symlink_cannot_supply_diagnostics(self):
        entry = self.entry()
        entry["message"]["content"][0]["text"] = "other output"
        self.write(entry)
        outside = self.root / "outside.jsonl"
        outside.write_text(json.dumps(self.entry()) + "\n")
        (self.project / "linked.jsonl").symlink_to(outside)
        self.assertEqual(claude_failure_diagnostics(self.root, self.report), {"status": "unmatched"})

    def test_non_marker_failures_and_success_are_not_scanned(self):
        self.write(self.entry())
        for report in ({"status": "passed", "marker_mismatch": self.report["marker_mismatch"]},
                       {"status": "failed"}, {"status": "failed", "marker_mismatch": {"output_sha256": "secret"}}):
            self.assertIsNone(claude_failure_diagnostics(self.root, report))

    def test_malformed_or_oversized_records_remain_bounded(self):
        (self.project / "bad.jsonl").write_text('{broken\n' + 'x' * (1024 * 1024 + 1))
        self.assertEqual(claude_failure_diagnostics(self.root, self.report), {"status": "limit_reached"})


if __name__ == "__main__":
    unittest.main()
