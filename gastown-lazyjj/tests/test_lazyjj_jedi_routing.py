from __future__ import annotations

import pathlib
import tomllib
import unittest


class LazyJJJediRoutingTests(unittest.TestCase):
    def test_jedi_is_on_demand_pool_worker(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        data = tomllib.loads((root / "pack.toml").read_text(encoding="utf-8"))
        sessions = {
            session["template"]: session
            for session in data.get("named_session", [])
        }

        self.assertEqual(sessions["jedi"]["mode"], "on_demand")

    def test_jedi_prompt_uses_gc_hook_for_pool_work(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        prompt = (root / "agents" / "jedi" / "prompt.template.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("gc hook", prompt)
        self.assertNotIn("{{ .WorkQuery }}", prompt)


if __name__ == "__main__":
    unittest.main()
