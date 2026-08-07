#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "request_status_updates.py"
SPEC = importlib.util.spec_from_file_location("request_status_updates", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RequestStatusUpdatesTest(unittest.TestCase):
    def test_build_message_carries_portable_schema_and_owner_path(self) -> None:
        message = MODULE.build_message("research-pl", pathlib.Path("/vault/inputs"))

        self.assertIn("/vault/inputs/research-pl.md", message)
        self.assertIn("<!-- executive-status:start -->", message)
        self.assertIn("health: on-track|at-risk|blocked|parked", message)
        self.assertIn("owner: research-pl", message)
        self.assertIn("CEO-level plain language", message)

    def test_discover_agents_uses_agent_directories_and_sorts_names(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            for name in ("zeta-pl", "alpha-pl", "not-a-lead"):
                directory = root / name
                directory.mkdir()
                (directory / "agent.toml").write_text("", encoding="utf-8")

            agents = MODULE.discover_agents(root)

        self.assertEqual(agents, ["alpha-pl", "zeta-pl"])

    def test_discover_agents_rejects_missing_directory(self) -> None:
        with self.assertRaisesRegex(ValueError, "agents directory does not exist"):
            MODULE.discover_agents(pathlib.Path("/definitely/not/present"))

    def test_build_dispatch_command_preserves_message_as_one_argument(self) -> None:
        command = MODULE.build_dispatch_command(
            "sender --to {agent} --subject {subject} --message {message}",
            agent="research-pl",
            subject="Executive update",
            message="words with spaces and $shell syntax",
        )

        self.assertEqual(
            command,
            [
                "sender",
                "--to",
                "research-pl",
                "--subject",
                "Executive update",
                "--message",
                "words with spaces and $shell syntax",
            ],
        )

    def test_build_dispatch_command_rejects_unknown_placeholders(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported placeholder"):
            MODULE.build_dispatch_command(
                "sender {agent} {unknown}",
                agent="research-pl",
                subject="Executive update",
                message="message",
            )

    def test_build_dispatch_command_requires_agent_and_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires"):
            MODULE.build_dispatch_command(
                "sender {subject}",
                agent="research-pl",
                subject="Executive update",
                message="message",
            )

    def test_configured_agents_merges_explicit_and_discovered_owners(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            (root / "research-pl").mkdir()
            (root / "research-pl" / "agent.toml").write_text("", encoding="utf-8")

            agents = MODULE.configured_agents(["mayor", "research-pl"], root)

        self.assertEqual(agents, ["mayor", "research-pl"])

    def test_configured_agents_rejects_empty_and_path_like_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "no status owners"):
            MODULE.configured_agents([], None)
        with self.assertRaisesRegex(ValueError, "invalid agent"):
            MODULE.configured_agents(["../owner"], None)
        with self.assertRaisesRegex(ValueError, "invalid agent"):
            MODULE.configured_agents(["bad owner"], None)

    def test_main_supports_dry_run_and_shell_free_dispatch(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(
                sys,
                "argv",
                ["request_status_updates.py", "--agent", "research-pl", "--dry-run"],
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            dry_result = MODULE.main()

        self.assertEqual(dry_result, 0)
        self.assertIn("owner: research-pl", stdout.getvalue())
        self.assertIn("dispatched=0", stdout.getvalue())

        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(
                sys,
                "argv",
                [
                    "request_status_updates.py",
                    "--agent",
                    "research-pl",
                    "--dispatch-command",
                    "sender {agent} {message}",
                ],
            ),
            mock.patch.object(MODULE.subprocess, "run") as run,
        ):
            dispatch_result = MODULE.main()

        self.assertEqual(dispatch_result, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[0:2], ["sender", "research-pl"])
        self.assertIn("owner: research-pl", command[2])
        run.assert_called_once_with(command, timeout=30.0, check=True)

    def test_main_reports_configuration_and_dispatch_errors(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(
                sys, "argv", ["request_status_updates.py", "--agent", "research-pl"]
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            missing_command = MODULE.main()

        self.assertEqual(missing_command, 1)
        self.assertIn("set --dispatch-command", stderr.getvalue())

        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(
                sys,
                "argv",
                [
                    "request_status_updates.py",
                    "--agent",
                    "research-pl",
                    "--dispatch-command",
                    "sender {agent} {message}",
                ],
            ),
            mock.patch.object(
                MODULE.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(2, ["sender"]),
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            failed_dispatch = MODULE.main()

        self.assertEqual(failed_dispatch, 1)
        self.assertIn("returned non-zero exit status", stderr.getvalue())

    def test_main_continues_after_one_owner_dispatch_fails(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(
                sys,
                "argv",
                [
                    "request_status_updates.py",
                    "--agent",
                    "alpha-pl",
                    "--agent",
                    "zeta-pl",
                    "--dispatch-command",
                    "sender {agent} {message}",
                ],
            ),
            mock.patch.object(
                MODULE.subprocess,
                "run",
                side_effect=[subprocess.CalledProcessError(2, ["sender"]), None],
            ) as run,
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            result = MODULE.main()

        self.assertEqual(result, 1)
        self.assertEqual(run.call_count, 2)
        self.assertIn("alpha-pl", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
