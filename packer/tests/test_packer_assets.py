from __future__ import annotations

import os
import pathlib
import tomllib
import unittest


class PackerAssetTests(unittest.TestCase):
    def test_pack_manifest_shape(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        data = tomllib.loads((root / "pack.toml").read_text(encoding="utf-8"))

        self.assertEqual(data["pack"]["name"], "packer")
        self.assertEqual(data["pack"]["schema"], 2)
        self.assertEqual(data["named_session"][0]["template"], "packer")

    def test_formulas_are_named(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        formulas = {
            path.name: tomllib.loads(path.read_text(encoding="utf-8"))["formula"]
            for path in sorted((root / "formulas").glob("*.toml"))
        }

        self.assertEqual(
            formulas,
            {
                "mol-packer-convert-repo-to-pack.toml": "mol-packer-convert-repo-to-pack",
                "mol-packer-import-local-pack.toml": "mol-packer-import-local-pack",
                "mol-packer-live-city-test.toml": "mol-packer-live-city-test",
                "mol-packer-validate.toml": "mol-packer-validate",
            },
        )

    def test_conversion_formula_captures_artifact_decisions(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        formula = root / "formulas" / "mol-packer-convert-repo-to-pack.toml"
        data = tomllib.loads(formula.read_text(encoding="utf-8"))
        text = formula.read_text(encoding="utf-8")

        self.assertEqual(data["formula"], "mol-packer-convert-repo-to-pack")
        for term in [
            "skills/",
            "template-fragments/",
            "assets/",
            "commands/",
            "formulas/",
            "agents/",
        ]:
            self.assertIn(term, text)

    def test_command_script_is_executable(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        script = root / "commands" / "pack-check" / "run.sh"

        self.assertTrue(os.access(script, os.X_OK))

    def test_repo_and_registry_fragment_is_included(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        prompt = (root / "agents" / "packer" / "prompt.template.md").read_text(
            encoding="utf-8"
        )
        fragment = root / "template-fragments" / "repo-and-registry.template.md"

        self.assertIn('{{ template "repo-and-registry" . }}', prompt)
        self.assertTrue(fragment.exists())
        text = fragment.read_text(encoding="utf-8")
        self.assertIn("registry.toml", text)
        self.assertIn("pack.toml", text)


if __name__ == "__main__":
    unittest.main()