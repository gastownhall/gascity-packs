from __future__ import annotations

import importlib.util
import io
import os
import pathlib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout


SCRIPT_PATH = pathlib.Path(__file__).resolve().parents[1] / "assets" / "scripts" / "artifacts.py"
BUILD_SCHEMA_ROOT = pathlib.Path(__file__).resolve().parents[1] / "schemas" / "build"


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

    def test_explicit_override_wins_over_default_root(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            override = pathlib.Path(temp_dir) / "custom" / "artifact-root"

            self.assertEqual(module.resolve_artifact_root(str(override)), override.resolve())

    def test_foreign_plans_directory_falls_back_to_gc_plans(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            rig_root = pathlib.Path(temp_dir)
            plans = rig_root / "plans"
            plans.mkdir()
            (plans / "team-roadmap.md").write_text("# Roadmap\n", encoding="utf-8")

            self.assertEqual(
                module.resolve_artifact_root("", rig_root=str(rig_root)),
                rig_root.resolve() / "gc-plans",
            )

    def test_gc_owned_plans_directory_is_stable_across_runs(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            rig_root = pathlib.Path(temp_dir)
            plans = rig_root / "plans"
            plans.mkdir()
            (plans / ".gc-plans").write_text("", encoding="utf-8")

            self.assertEqual(
                module.resolve_artifact_root("", rig_root=str(rig_root)),
                plans.resolve(),
            )

    def test_existing_github_artifacts_mark_plans_directory_as_owned(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            rig_root = pathlib.Path(temp_dir)
            (rig_root / "plans" / "github").mkdir(parents=True)

            self.assertEqual(
                module.resolve_artifact_root("", rig_root=str(rig_root)),
                (rig_root / "plans").resolve(),
            )

    def test_cli_mkdir_marks_default_plans_root_owned(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            rig_root = pathlib.Path(temp_dir)
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                code = module.main(
                    [
                        "path",
                        "--override",
                        "",
                        "--rig-root",
                        str(rig_root),
                        "--relative",
                        "/github/issues/owner/repo/1/source.json",
                        "--mkdir-parents",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertTrue((rig_root / "plans" / ".gc-plans").exists())
            self.assertEqual(
                module.resolve_artifact_root("", rig_root=str(rig_root)),
                (rig_root / "plans").resolve(),
            )
            self.assertIn("/plans/github/issues/owner/repo/1/source.json", stdout.getvalue())

    def test_cli_root_and_directory_branches(self) -> None:
        module = load_artifacts_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            rig_root = pathlib.Path(temp_dir)

            with redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(["root", "--rig-root", str(rig_root), "--mkdir"]), 0)
            self.assertTrue((rig_root / "plans" / ".gc-plans").exists())

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    module.main(
                        [
                            "path",
                            "--rig-root",
                            str(rig_root),
                            "--relative",
                            "/github/pulls/owner/repo/2/reviews/abc/",
                            "--directory",
                            "--mkdir-parents",
                        ]
                    ),
                    0,
                )
            self.assertTrue((rig_root / "plans" / "github" / "pulls" / "owner" / "repo" / "2" / "reviews" / "abc").is_dir())

    def test_cli_errors_return_one(self) -> None:
        module = load_artifacts_module()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            args = ["path", "--override", temp_dir, "--relative", "../outside"]

            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                code = module.main(args)

        self.assertEqual(code, 1)
        self.assertIn("error:", stderr.getvalue())

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

    def test_build_artifact_schema_files_have_stable_ids(self) -> None:
        expected = {
            "requirements.v1.yaml": "gc.build.requirements.v1",
            "plan.v1.yaml": "gc.build.plan.v1",
            "decomposition.v1.yaml": "gc.build.decomposition.v1",
            "implementation-summary.v1.yaml": "gc.build.implementation-summary.v1",
            "review.v1.yaml": "gc.build.review.v1",
            "final-report.v1.yaml": "gc.build.final-report.v1",
        }

        for filename, schema_id in expected.items():
            with self.subTest(filename=filename):
                path = BUILD_SCHEMA_ROOT / filename
                self.assertTrue(path.is_file(), f"missing {path}")
                self.assertIn(f"schema_id: {schema_id}", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
