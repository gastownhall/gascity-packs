#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "executive_status_sync.py"
SPEC = importlib.util.spec_from_file_location("executive_status_sync", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def status_block(
    *,
    project: str = "Research",
    owner: str = "research-pl",
    updated: str = "2026-08-07T10:00:00-04:00",
    health: str = "on-track",
    current: str = "Validating the new evaluation path.",
    next_step: str = "Run the larger comparison.",
    risk: str = "none",
) -> str:
    return f"""---
tags: [executive-status-input]
---
# {project}

<!-- executive-status:start -->
project: {project}
owner: {owner}
updated: {updated}
health: {health}
current: {current}
next: {next_step}
risk: {risk}
<!-- executive-status:end -->
"""


class ParseStatusTest(unittest.TestCase):
    def test_parses_complete_status_block(self) -> None:
        status = MODULE.parse_status(status_block(), pathlib.Path("research-pl.md"))

        self.assertEqual(status.project, "Research")
        self.assertEqual(status.owner, "research-pl")
        self.assertEqual(status.health, "on-track")
        self.assertEqual(status.next_step, "Run the larger comparison.")

    def test_rejects_missing_required_field(self) -> None:
        text = status_block().replace(
            "current: Validating the new evaluation path.\n", ""
        )

        with self.assertRaisesRegex(ValueError, "missing required field: current"):
            MODULE.parse_status(text, pathlib.Path("research-pl.md"))

    def test_rejects_invalid_health_and_oversized_content(self) -> None:
        invalid_health = status_block().replace("health: on-track", "health: great")
        with self.assertRaisesRegex(ValueError, "invalid health"):
            MODULE.parse_status(invalid_health, pathlib.Path("research-pl.md"))

        with self.assertRaisesRegex(ValueError, "current exceeds 240 characters"):
            MODULE.parse_status(
                status_block(current="x" * 241), pathlib.Path("research-pl.md")
            )

    def test_rejects_filename_owner_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "owner must match filename"):
            MODULE.parse_status(status_block(), pathlib.Path("different-pl.md"))

    def test_rejects_structural_and_timestamp_errors(self) -> None:
        cases = (
            ("no fences", "missing executive-status fence"),
            (
                status_block().replace("project: Research", "project Research"),
                "invalid field line",
            ),
            (
                status_block().replace("risk: none", "risk: none\nrisk: duplicate"),
                "duplicate field",
            ),
            (
                status_block().replace("risk: none", "risk: none\nextra: value"),
                "unexpected field",
            ),
            (
                status_block(owner="bad owner"),
                "owner contains unsupported characters",
            ),
            (
                status_block(updated="not-a-date"),
                "updated must be an ISO-8601 timestamp",
            ),
            (
                status_block(updated="2026-08-07T10:00:00"),
                "updated must include a timezone",
            ),
        )
        for text, message in cases:
            owner = "bad owner" if "bad owner" in text else "research-pl"
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                MODULE.parse_status(text, pathlib.Path(f"{owner}.md"))

    def test_structural_errors_do_not_echo_input_content(self) -> None:
        with self.assertRaises(ValueError) as raised:
            MODULE.parse_status(
                f"{MODULE.START}\nprivate-value-without-colon\n{MODULE.END}",
                pathlib.Path("research-pl.md"),
            )

        self.assertNotIn("private-value", str(raised.exception))


class RenderBriefTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = dt.datetime.fromisoformat("2026-08-07T12:00:00-04:00")

    def test_renders_configurable_brief_and_publish_summary(self) -> None:
        statuses = [
            MODULE.parse_status(status_block(), pathlib.Path("research-pl.md")),
            MODULE.parse_status(
                status_block(
                    project="Platform",
                    owner="platform-pl",
                    updated="2026-08-07T09:00:00-04:00",
                    health="blocked",
                    current="Delivery is paused while capacity is restored.",
                    next_step="Resume the queued validation work.",
                    risk="No throughput until capacity returns.",
                ),
                pathlib.Path("platform-pl.md"),
            ),
        ]

        markdown = MODULE.render_brief(statuses, self.now, title="Portfolio Brief")
        summary = MODULE.render_publish_summary(
            statuses, self.now, title="Portfolio Brief"
        )

        self.assertIn("# Portfolio Brief", markdown)
        self.assertIn("| Platform | 🔴 Blocked |", markdown)
        self.assertIn("## Risks to watch", markdown)
        self.assertNotIn("platform-pl", markdown)
        self.assertIn("Portfolio Brief", summary)
        self.assertIn("2 projects reporting", summary)
        self.assertIn("🔴 **Platform**", summary)

    def test_marks_old_inputs_stale_and_output_is_deterministic(self) -> None:
        status = MODULE.parse_status(
            status_block(updated="2026-08-04T10:00:00-04:00"),
            pathlib.Path("research-pl.md"),
        )

        first = MODULE.render_brief([status], self.now, title="Portfolio Brief")
        later = MODULE.render_brief(
            [status], self.now + dt.timedelta(minutes=20), title="Portfolio Brief"
        )

        self.assertIn("⚪ Stale", first)
        self.assertEqual(first, later)

    def test_load_statuses_reports_invalid_inputs_and_duplicate_owners(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            (root / "research-pl.md").write_text(status_block(), encoding="utf-8")
            (root / "invalid.md").write_text("not a status", encoding="utf-8")
            (root / "copy.md").write_text(status_block(), encoding="utf-8")

            statuses, errors = MODULE.load_statuses(root)

        self.assertEqual(len(statuses), 1)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("invalid.md" in error for error in errors))
        self.assertTrue(any("copy.md" in error for error in errors))

    def test_load_statuses_reports_missing_directory(self) -> None:
        statuses, errors = MODULE.load_statuses(pathlib.Path("/definitely/not/present"))

        self.assertEqual(statuses, [])
        self.assertIn("input directory does not exist", errors[0])

    def test_load_statuses_rejects_symlinks_and_oversized_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            inputs = root / "inputs"
            inputs.mkdir()
            outside = root / "research-pl.md"
            outside.write_text(status_block(), encoding="utf-8")
            (inputs / "research-pl.md").symlink_to(outside)
            (inputs / "large-pl.md").write_text(
                "x" * (MODULE.MAX_INPUT_BYTES + 1), encoding="utf-8"
            )

            statuses, errors = MODULE.load_statuses(inputs)

        self.assertEqual(statuses, [])
        self.assertTrue(
            any("symbolic links are not allowed" in error for error in errors)
        )
        self.assertTrue(any("input exceeds" in error for error in errors))

    def test_render_includes_coverage_warnings_and_truncates_summary(self) -> None:
        status = MODULE.parse_status(status_block(), pathlib.Path("research-pl.md"))

        markdown = MODULE.render_brief(
            [status],
            self.now,
            title="Portfolio Brief",
            missing={"platform-pl"},
            errors=["bad input"],
        )
        summary = MODULE.render_publish_summary(
            [status],
            self.now,
            title="Portfolio Brief",
            missing={"platform-pl"},
            errors=["bad input"],
            max_length=80,
        )

        self.assertIn("Awaiting first update: platform-pl", markdown)
        self.assertIn("1 malformed input", markdown)
        self.assertEqual(len(summary), 80)
        self.assertTrue(summary.endswith("…"))

    def test_render_escapes_raw_html_from_owner_fields(self) -> None:
        status = MODULE.parse_status(
            status_block(
                project="<script>alert(1)</script>",
                current="Evidence is ready & reviewed.",
                risk="<img src=x onerror=alert(1)>",
                health="at-risk",
            ),
            pathlib.Path("research-pl.md"),
        )

        markdown = MODULE.render_brief([status], self.now, title="Portfolio <Status>")
        summary = MODULE.render_publish_summary(
            [status], self.now, title="Portfolio <Status>"
        )

        self.assertNotIn("<script>", markdown)
        self.assertNotIn("<img", markdown)
        self.assertNotIn("<script>", summary)
        self.assertIn("&lt;script&gt;", markdown)


class PersistenceAndCommandTest(unittest.TestCase):
    def test_write_if_changed_is_atomic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = pathlib.Path(raw) / "nested" / "brief.md"

            first = MODULE.write_if_changed(path, "brief")
            second = MODULE.write_if_changed(path, "brief")

        self.assertTrue(first)
        self.assertFalse(second)

    def test_publish_command_validation_and_execution(self) -> None:
        command = MODULE.build_publish_command(
            "publisher --title {title} --body {body_file}",
            body_file=pathlib.Path("/tmp/body.md"),
            title="Portfolio Brief",
        )
        self.assertEqual(
            command,
            ["publisher", "--title", "Portfolio Brief", "--body", "/tmp/body.md"],
        )
        with self.assertRaisesRegex(ValueError, "unsupported publish placeholder"):
            MODULE.build_publish_command(
                "publisher {unsupported}",
                body_file=pathlib.Path("/tmp/body.md"),
                title="Portfolio Brief",
            )
        with self.assertRaisesRegex(ValueError, "requires"):
            MODULE.build_publish_command(
                "publisher {title}",
                body_file=pathlib.Path("/tmp/body.md"),
                title="Portfolio Brief",
            )

        with mock.patch.object(MODULE.subprocess, "run") as run:
            MODULE.publish_summary(
                "publisher {body_file}",
                "summary",
                title="Portfolio Brief",
                timeout=12,
            )

        published_path = pathlib.Path(run.call_args.args[0][1])
        self.assertFalse(published_path.exists())
        run.assert_called_once_with(
            ["publisher", str(published_path)], timeout=12, check=True
        )

    def test_expected_owners_and_log(self) -> None:
        self.assertEqual(
            MODULE.expected_owners("research-pl, platform-pl, research-pl"),
            {"research-pl", "platform-pl"},
        )
        with tempfile.TemporaryDirectory() as raw:
            path = pathlib.Path(raw) / "nested" / "sync.log"
            MODULE.log(path, "reporting=2")
            content = path.read_text(encoding="utf-8")

        self.assertIn("reporting=2", content)


class MainIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        (self.inputs / "research-pl.md").write_text(status_block(), encoding="utf-8")
        self.environment = {
            "EXECUTIVE_STATUS_INPUT_DIR": str(self.inputs),
            "EXECUTIVE_STATUS_OUTPUT": str(self.root / "vault" / "Brief.md"),
            "EXECUTIVE_STATUS_TITLE": "Portfolio Brief",
            "EXECUTIVE_STATUS_EXPECTED_OWNERS": "research-pl,platform-pl",
            "EXECUTIVE_STATUS_SENTINEL": str(self.root / "summary.sha256"),
            "EXECUTIVE_STATUS_LOG": str(self.root / "sync.log"),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_main_dry_run_and_vault_only_run(self) -> None:
        with (
            mock.patch.dict(os.environ, self.environment, clear=True),
            mock.patch.object(sys, "argv", ["executive_status_sync.py", "--dry-run"]),
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            dry_result = MODULE.main()

        self.assertEqual(dry_result, 0)
        self.assertIn("Publish preview", stdout.getvalue())
        self.assertFalse((self.root / "vault" / "Brief.md").exists())

        with (
            mock.patch.dict(os.environ, self.environment, clear=True),
            mock.patch.object(
                sys, "argv", ["executive_status_sync.py", "--no-publish"]
            ),
        ):
            first = MODULE.main()
            second = MODULE.main()

        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertIn(
            "Awaiting first update: platform-pl",
            (self.root / "vault" / "Brief.md").read_text(encoding="utf-8"),
        )

    def test_main_publishes_changed_summary_and_records_sentinel(self) -> None:
        environment = {
            **self.environment,
            "EXECUTIVE_STATUS_PUBLISH_COMMAND": "publisher {body_file}",
            "EXECUTIVE_STATUS_STALE_HOURS": "72",
            "EXECUTIVE_STATUS_MAX_PUBLISH_LENGTH": "1000",
            "EXECUTIVE_STATUS_PUBLISH_TIMEOUT": "15",
        }
        with (
            mock.patch.dict(os.environ, environment, clear=True),
            mock.patch.object(sys, "argv", ["executive_status_sync.py"]),
            mock.patch.object(MODULE, "publish_summary") as publish,
        ):
            result = MODULE.main()

        self.assertEqual(result, 0)
        publish.assert_called_once()
        self.assertTrue((self.root / "summary.sha256").is_file())

    def test_main_fails_closed_without_valid_inputs_and_surfaces_publish_errors(
        self,
    ) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        no_inputs = {**self.environment, "EXECUTIVE_STATUS_INPUT_DIR": str(empty)}
        with (
            mock.patch.dict(os.environ, no_inputs, clear=True),
            mock.patch.object(sys, "argv", ["executive_status_sync.py"]),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            no_input_result = MODULE.main()

        self.assertEqual(no_input_result, 1)
        self.assertIn("preserving existing brief", stderr.getvalue())

        publish_environment = {
            **self.environment,
            "EXECUTIVE_STATUS_PUBLISH_COMMAND": "publisher {body_file}",
        }
        with (
            mock.patch.dict(os.environ, publish_environment, clear=True),
            mock.patch.object(sys, "argv", ["executive_status_sync.py"]),
            mock.patch.object(
                MODULE,
                "publish_summary",
                side_effect=subprocess.CalledProcessError(2, ["publisher"]),
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            publish_result = MODULE.main()

        self.assertEqual(publish_result, 1)
        self.assertIn("returned non-zero exit status", stderr.getvalue())

    def test_main_names_malformed_inputs_in_stderr_and_audit_log(self) -> None:
        (self.inputs / "broken.md").write_text("not a status", encoding="utf-8")
        with (
            mock.patch.dict(os.environ, self.environment, clear=True),
            mock.patch.object(
                sys, "argv", ["executive_status_sync.py", "--no-publish"]
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            result = MODULE.main()

        self.assertEqual(result, 1)
        self.assertIn("broken.md", stderr.getvalue())
        self.assertIn(
            "broken.md",
            pathlib.Path(self.environment["EXECUTIVE_STATUS_LOG"]).read_text(
                encoding="utf-8"
            ),
        )


if __name__ == "__main__":
    unittest.main()
