from __future__ import annotations

import pathlib
import re
import unittest


class SkillFrontmatterTests(unittest.TestCase):
    def test_all_skills_have_name_and_description(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        skill_files = sorted(root.glob("skills/*/SKILL.md"))

        self.assertEqual(
            [path.parent.name for path in skill_files],
            [
                "find-work",
                "fine-tune",
                "map-blast-radius",
                "orchestrate-contribution",
                "plan-implementation",
                "review",
                "start-contribution",
                "write-issue",
            ],
        )
        for path in skill_files:
            text = path.read_text(encoding="utf-8")
            match = re.match(r"\A---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
            self.assertIsNotNone(match, f"{path} missing YAML front matter")
            body = match.group("body") if match else ""
            self.assertRegex(body, r"(?m)^name:\s*\S+", f"{path} missing name")
            self.assertRegex(body, r"(?m)^description:\s*\S+", f"{path} missing description")

    def test_frontmatter_scalars_are_yaml_safe(self) -> None:
        # A bare ": " inside an unquoted single-line scalar makes a YAML parser
        # read it as a nested mapping ("mapping values are not allowed here").
        # That silently breaks GitHub's frontmatter render and any YAML-based
        # skill loader. Quote the value or use an em-dash instead.
        root = pathlib.Path(__file__).resolve().parents[1]
        for path in sorted(root.glob("skills/*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            match = re.match(r"\A---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
            body = match.group("body") if match else ""
            for line in body.splitlines():
                m = re.match(r"^(?P<key>[A-Za-z][\w-]*):[ \t](?P<value>\S.*)$", line)
                if not m:
                    continue
                value = m.group("value")
                if value[0] in "\"'|>[{":  # quoted, block, or flow collection
                    continue
                self.assertNotIn(
                    ": ",
                    value,
                    f"{path}: front matter '{m.group('key')}' has an unquoted "
                    f"': ' — quote the value or use an em-dash (breaks YAML).",
                )


if __name__ == "__main__":
    unittest.main()
