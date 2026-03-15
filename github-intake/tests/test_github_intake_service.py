from __future__ import annotations

import pathlib
import tempfile
import unittest

import os
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import github_intake_service as service


class GitHubIntakeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def test_fix_command_behavior(self) -> None:
        behavior = service.command_behavior("fix")

        self.assertEqual(behavior["mode"], "fix_issue")
        self.assertFalse(behavior["ack_comment"])
        self.assertEqual(behavior["workflow_scope"], "issue")
        self.assertTrue(behavior["requires_write_permission"])

    def test_rig_from_target_extracts_rig_name(self) -> None:
        self.assertEqual(service.rig_from_target("product/polecat"), "product")
        self.assertEqual(service.rig_from_target("product/polecat-2"), "product")
        self.assertEqual(service.rig_from_target("polecat"), "")

    def test_extract_json_output_accepts_dict_and_list_shapes(self) -> None:
        self.assertEqual(service.extract_json_output('{"id":"bd-1"}')["id"], "bd-1")
        self.assertEqual(service.extract_json_output('[{"id":"bd-2"}]')["id"], "bd-2")
        self.assertEqual(service.extract_json_output("not json"), {})

    def test_build_fix_bead_notes_includes_issue_and_context(self) -> None:
        request = {
            "repository_full_name": "owner/repo",
            "issue_number": "42",
            "issue_url": "https://github.com/owner/repo/issues/42",
            "comment_url": "https://github.com/owner/repo/issues/42#issuecomment-99",
            "request_id": "gh-123-99-fix",
            "comment_author": "alice",
            "issue_title": "Crash on startup",
            "issue_body": "The app crashes if X is unset.",
            "command_context": "missing env guard\nsteps to reproduce",
        }

        notes = service.build_fix_bead_notes(request)

        self.assertIn("## GitHub Source", notes)
        self.assertIn("Crash on startup", notes)
        self.assertIn("missing env guard", notes)
        self.assertIn("gh-123-99-fix", notes)


if __name__ == "__main__":
    unittest.main()
