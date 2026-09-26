"""Unit checks for the credential preflight's redaction; these do not call a model."""

import unittest

from credential_preflight import classify


class ClassifyTests(unittest.TestCase):
    def test_keeps_only_status_and_known_error_words(self):
        text = ('API Error: 403 {"type":"error","error":{"type":"authentication_failed",'
                '"message":"token sk-ant-secret-value rejected for user@example.com"}}')
        result = classify(text)
        self.assertEqual(result, {"http_status": ["403"], "error_kinds": ["authentication_failed"]})
        self.assertNotIn("sk-ant", repr(result))

    def test_quota_and_rate_limits_are_recognised(self):
        result = classify("stream error: 429 Too Many Requests; insufficient_quota")
        self.assertEqual(result["http_status"], ["429"])
        self.assertIn("insufficient_quota", result["error_kinds"])

    def test_versions_and_long_numbers_are_not_statuses(self):
        self.assertEqual(classify("codex-cli 0.153.4 took 4031 ms at 2.1.403")["http_status"], [])


if __name__ == "__main__":
    unittest.main()
