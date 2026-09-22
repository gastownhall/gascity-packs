from __future__ import annotations

import pathlib
import unittest

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import discord_intake_status as status


class ChatIngressClippedMarkerTests(unittest.TestCase):
    def test_a_record_without_the_flag_gets_no_marker(self) -> None:
        # Records written before `body_truncated` existed carry neither field.
        # A missing flag is "unknown", not "short" — the README promises no
        # marker rather than a wrong one.
        self.assertEqual(status.chat_ingress_clipped_marker({}), "")
        self.assertEqual(status.chat_ingress_clipped_marker({"body_preview": "hi"}), "")
        self.assertEqual(status.chat_ingress_clipped_marker({"body_truncated": False}), "")

    def test_a_clipped_record_reports_the_whole_length(self) -> None:
        marker = status.chat_ingress_clipped_marker({"body_truncated": True, "body_length": 467})

        self.assertIn("CLIPPED", marker)
        self.assertIn("467 chars total", marker)
        self.assertIn("body", marker)

    def test_a_clipped_record_without_a_usable_length_uses_the_short_form(self) -> None:
        for item in ({"body_truncated": True}, {"body_truncated": True, "body_length": 0}):
            with self.subTest(item=item):
                marker = status.chat_ingress_clipped_marker(item)

                self.assertIn("CLIPPED", marker)
                self.assertNotIn("chars total", marker)


class RenderTextTests(unittest.TestCase):
    def test_the_marker_reaches_the_rendered_ingress_line(self) -> None:
        # The marker is the only thing on this surface that tells a clipped
        # record from a whole one: `build_status_snapshot` redacts
        # `body_preview`, so the preview it sits beside is "[redacted]".
        snapshot = {
            "recent_chat_ingress": [
                {
                    "ingress_id": "in-clipped",
                    "body_preview": "[redacted]",
                    "body_truncated": True,
                    "body_length": 467,
                },
                {"ingress_id": "in-whole", "body_preview": "[redacted]"},
            ]
        }

        rendered = status.render_text(snapshot).splitlines()
        clipped_line = next(line for line in rendered if "in-clipped" in line)
        whole_line = next(line for line in rendered if "in-whole" in line)

        self.assertIn("[CLIPPED — 467 chars total", clipped_line)
        self.assertNotIn("CLIPPED", whole_line)


if __name__ == "__main__":
    unittest.main()
