from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from typing import NamedTuple

import os


class DoctorCheck(NamedTuple):
    name: str
    script: str
    tool: str
    probe: tuple[str, ...] | None
    failure_marker: str


DOCTOR_CHECKS = (
    DoctorCheck("bd", "check-bd.sh", "gc", ("gc", "bd", "version"), "gc bd unavailable"),
    DoctorCheck("gc", "check-gc.sh", "gc", None, "gc CLI not found"),
    DoctorCheck("git", "check-git.sh", "git", None, "git not found"),
    DoctorCheck("jq", "check-jq.sh", "jq", None, "jq not found"),
    DoctorCheck("openssl", "check-openssl.sh", "openssl", None, "openssl not found"),
    DoctorCheck("python", "check-python.sh", "python3", None, "python3 not found"),
)


class MattermostDoctorScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name
        self.doctor_dir = pathlib.Path(__file__).resolve().parents[1] / "doctor"
        self.bd_doctor = self.doctor_dir / "bd" / "doctor.toml"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def _empty_path_env(self) -> dict[str, str]:
        empty_bin = pathlib.Path(self.tempdir.name, "empty-bin")
        empty_bin.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PATH"] = str(empty_bin)
        return env

    def test_every_doctor_toml_points_at_an_executable_check_script(self) -> None:
        for check in DOCTOR_CHECKS:
            with self.subTest(check=check.name):
                toml_path = self.doctor_dir / check.name / "doctor.toml"
                self.assertTrue(toml_path.is_file())
                with toml_path.open("rb") as handle:
                    doctor = tomllib.load(handle)
                self.assertEqual(doctor["run"], f"../{check.script}")
                script = (toml_path.parent / doctor["run"]).resolve()
                self.assertTrue(script.is_file())
                self.assertTrue(os.access(script, os.X_OK))

    def test_doctor_descriptions_reference_the_mattermost_pack(self) -> None:
        for check in DOCTOR_CHECKS:
            with self.subTest(check=check.name):
                toml_path = self.doctor_dir / check.name / "doctor.toml"
                with toml_path.open("rb") as handle:
                    doctor = tomllib.load(handle)
                self.assertIn("mattermost", doctor["description"].lower())
                self.assertNotIn("discord", doctor["description"].lower())

    def test_checks_fail_with_guidance_when_the_tool_is_missing(self) -> None:
        env = self._empty_path_env()
        for check in DOCTOR_CHECKS:
            with self.subTest(check=check.name):
                result = subprocess.run(
                    [str(self.doctor_dir / check.script)],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn(check.failure_marker, result.stdout)
                self.assertIn("Install", result.stdout)

    def test_checks_pass_when_the_tool_is_available(self) -> None:
        for check in DOCTOR_CHECKS:
            with self.subTest(check=check.name):
                if shutil.which(check.tool) is None:
                    self.skipTest(f"{check.tool} is not installed")
                if check.probe is not None:
                    probed = subprocess.run(list(check.probe), capture_output=True, text=True, check=False)
                    if probed.returncode != 0:
                        self.skipTest(f"{' '.join(check.probe)} is unavailable")
                result = subprocess.run(
                    [str(self.doctor_dir / check.script)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("available", result.stdout)

    def test_bd_doctor_describes_the_store_aware_gc_wrapper(self) -> None:
        with self.bd_doctor.open("rb") as handle:
            doctor = tomllib.load(handle)

        self.assertIn("gc bd", doctor["description"])
        self.assertNotIn("bd CLI", doctor["description"])


if __name__ == "__main__":
    unittest.main()
