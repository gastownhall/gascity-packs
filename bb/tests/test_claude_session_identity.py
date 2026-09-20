"""The installed CLI must document caller-selected conversation identities."""
import unittest

from live_assertions import AcceptanceFailure
from runtime_artifact import require_claude_session_id


class ClaudeSessionIdentityTests(unittest.TestCase):
    def test_checks_exact_raw_binary_help_for_fresh_identity_support(self):
        calls = []
        def command(*args):
            calls.append(args)
            return "Options:\n  --session-id <uuid>  Use a specific session ID for the conversation\n"
        require_claude_session_id("/qualified/claude", command)
        self.assertEqual(calls, [("/qualified/claude", "--help")])

    def test_resume_only_or_mention_in_prose_is_not_fresh_identity_support(self):
        for text in ("  --resume <session-id>\n", "No --session-id <uuid> support", "  --session-id-old <uuid>\n", ""):
            with self.subTest(text=text), self.assertRaises(AcceptanceFailure):
                require_claude_session_id("/qualified/claude", lambda *_: text)


if __name__ == "__main__":
    unittest.main()
