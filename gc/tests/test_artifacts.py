from __future__ import annotations

import importlib.util
import os
import pathlib
import tempfile
import unittest


SCRIPT_PATH = pathlib.Path(__file__).resolve().parents[1] / "assets" / "scripts" / "artifacts.py"


def load_artifacts_module():
    spec = importlib.util.spec_from_file_location("gc_artifacts", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load artifacts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArtifactHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_env)

    def test_helper_is_executable(self) -> None:
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK))

    def test_empty_override_defaults_to_rig_plans_directory(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["GC_RIG_ROOT"] = temp_dir
            self.assertEqual(
                module.resolve_artifact_root(""),
                pathlib.Path(temp_dir).resolve() / "plans",
            )

    def test_default_plans_dir_reused_when_gc_owned(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["GC_RIG_ROOT"] = temp_dir
            rig = pathlib.Path(temp_dir).resolve()
            (rig / "plans" / "demo").mkdir(parents=True)
            (rig / "plans" / "demo" / "requirements.md").write_text("x", encoding="utf-8")
            self.assertEqual(module.resolve_artifact_root(""), rig / "plans")

    def test_empty_plans_dir_is_treated_as_gc_owned(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["GC_RIG_ROOT"] = temp_dir
            rig = pathlib.Path(temp_dir).resolve()
            (rig / "plans").mkdir()
            self.assertEqual(module.resolve_artifact_root(""), rig / "plans")

    def test_marker_makes_nonempty_plans_dir_gc_owned(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["GC_RIG_ROOT"] = temp_dir
            rig = pathlib.Path(temp_dir).resolve()
            (rig / "plans").mkdir()
            (rig / "plans" / ".gc-plans").write_text("", encoding="utf-8")
            (rig / "plans" / "unrelated.txt").write_text("x", encoding="utf-8")
            self.assertEqual(module.resolve_artifact_root(""), rig / "plans")

    def test_foreign_plans_dir_falls_back_to_gc_plans(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["GC_RIG_ROOT"] = temp_dir
            rig = pathlib.Path(temp_dir).resolve()
            (rig / "plans" / "roadmap").mkdir(parents=True)
            (rig / "plans" / "roadmap" / "q3.md").write_text("x", encoding="utf-8")
            self.assertEqual(module.resolve_artifact_root(""), rig / "gc-plans")

    def test_plans_path_that_is_a_file_falls_back_to_gc_plans(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["GC_RIG_ROOT"] = temp_dir
            rig = pathlib.Path(temp_dir).resolve()
            (rig / "plans").write_text("not a dir", encoding="utf-8")
            self.assertEqual(module.resolve_artifact_root(""), rig / "gc-plans")

    def test_leading_slash_paths_are_artifact_root_relative(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = module.resolve_artifact_path(
                temp_dir,
                "/github/issues/gastownhall/gascity/11/source.json",
            )
            self.assertEqual(
                target,
                pathlib.Path(temp_dir).resolve()
                / "github"
                / "issues"
                / "gastownhall"
                / "gascity"
                / "11"
                / "source.json",
            )

    def test_artifact_path_rejects_root_escape(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                module.resolve_artifact_path(temp_dir, "../outside")


if __name__ == "__main__":
    unittest.main()
