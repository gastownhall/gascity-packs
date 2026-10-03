#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


SKILL_DIR = pathlib.Path(__file__).parents[1]
SYNC = SKILL_DIR / "scripts" / "executive_status_sync.py"


class ExecutiveStatusEndToEndTest(unittest.TestCase):
    def test_cli_writes_brief_and_publishes_only_when_summary_changes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            inputs = root / "inputs"
            inputs.mkdir()
            timestamp = dt.datetime.now().astimezone().isoformat(timespec="minutes")
            (inputs / "research-pl.md").write_text(
                "---\ntags: [executive-status-input]\n---\n"
                "<!-- executive-status:start -->\n"
                "project: Research\n"
                "owner: research-pl\n"
                f"updated: {timestamp}\n"
                "health: on-track\n"
                "current: The evaluation path is producing useful evidence.\n"
                "next: Complete the larger comparison.\n"
                "risk: none\n"
                "<!-- executive-status:end -->\n",
                encoding="utf-8",
            )
            publisher = root / "publisher.py"
            publisher.write_text(
                "import pathlib, sys\n"
                "log = pathlib.Path(sys.argv[1])\n"
                "body = pathlib.Path(sys.argv[2]).read_text(encoding='utf-8')\n"
                "with log.open('a', encoding='utf-8') as handle:\n"
                "    handle.write(body.replace('\\n', ' ') + '\\n')\n",
                encoding="utf-8",
            )
            output = root / "vault" / "Portfolio Brief.md"
            publish_log = root / "published.log"
            environment = {
                **os.environ,
                "EXECUTIVE_STATUS_INPUT_DIR": str(inputs),
                "EXECUTIVE_STATUS_OUTPUT": str(output),
                "EXECUTIVE_STATUS_TITLE": "Portfolio Brief",
                "EXECUTIVE_STATUS_SENTINEL": str(root / "summary.sha256"),
                "EXECUTIVE_STATUS_LOG": str(root / "sync.log"),
                "EXECUTIVE_STATUS_PUBLISH_COMMAND": (
                    f"{sys.executable} {publisher} {publish_log} {{body_file}}"
                ),
            }

            first = subprocess.run(
                [sys.executable, str(SYNC)],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )
            second = subprocess.run(
                [sys.executable, str(SYNC)],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("# Portfolio Brief", output.read_text(encoding="utf-8"))
            self.assertEqual(len(publish_log.read_text().splitlines()), 1)
            self.assertIn("published=true", first.stdout)
            self.assertIn("published=false", second.stdout)


if __name__ == "__main__":
    unittest.main()
