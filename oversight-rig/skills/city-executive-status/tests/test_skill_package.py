#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import unittest


SKILL_DIR = pathlib.Path(__file__).parents[1]
REQUIRED_RESOURCES = (
    "SKILL.md",
    "agents/openai.yaml",
    "assets/executive-status.env.example",
    "assets/status-input-template.md",
    "assets/orders/request-status-updates.toml",
    "assets/orders/sync-status-brief.toml",
    "references/configuration.md",
    "scripts/request_status_updates.py",
    "scripts/executive_status_sync.py",
)


class SkillPackageTest(unittest.TestCase):
    def test_contains_complete_shareable_package(self) -> None:
        missing = [
            name for name in REQUIRED_RESOURCES if not (SKILL_DIR / name).is_file()
        ]

        self.assertEqual(missing, [])

    def test_contains_no_local_identity_or_secret_placeholders(self) -> None:
        forbidden = (
            re.compile("/" + "home/" + r"[^/\s]+/"),
            re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            re.compile(r"\bC[A-Z0-9]{10}\b"),
        )
        offenders: list[str] = []
        for path in SKILL_DIR.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path == pathlib.Path(__file__)
            ):
                continue
            text = path.read_text(encoding="utf-8")
            if any(pattern.search(text) for pattern in forbidden):
                offenders.append(str(path.relative_to(SKILL_DIR)))

        self.assertEqual(offenders, [])

    def test_order_examples_do_not_assume_a_provider_skill_directory(self) -> None:
        for name in (
            "assets/orders/request-status-updates.toml",
            "assets/orders/sync-status-brief.toml",
        ):
            text = (SKILL_DIR / name).read_text(encoding="utf-8")
            self.assertNotIn(".claude/skills", text)
            self.assertNotIn(".agents/skills", text)


if __name__ == "__main__":
    unittest.main()
