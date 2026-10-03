"""Command cwd selection is exercised by real, harmless scratch executables."""
import os
from pathlib import Path
import tempfile
import unittest

from full_e2e import Runner
from live_assertions import AcceptanceFailure


class CommandDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="bb-command-guards-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name).resolve()
        self.city = self.root / "city"
        self.city.mkdir()
        self.gc = self.executable(self.root / "bin/gc")
        self.runner = object.__new__(Runner)
        self.runner.root = self.root
        self.runner.private = self.root / "private"
        self.runner.private.mkdir()
        self.runner.counter = 0
        self.runner.env = dict(os.environ)
        self.runner.manifest = {"city": str(self.city), "commands": {"gc": str(self.gc)}}

    def executable(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\npwd\n")
        path.chmod(0o700)
        return path

    def test_selected_gc_and_its_symlink_run_in_the_prepared_city(self):
        self.assertEqual(self.runner.command(self.gc, "bb", "install").strip(), str(self.city))
        alias = self.root / "gc-alias"
        alias.symlink_to(self.gc)
        self.assertEqual(self.runner.command(alias, "supervisor", "status").strip(), str(self.city))

    def test_other_commands_including_another_gc_filename_keep_scratch_cwd(self):
        other = self.executable(self.root / "other/gc")
        self.assertEqual(self.runner.command(other).strip(), str(self.root))

    def test_gc_cannot_use_an_outside_or_root_city(self):
        for city in (self.root.parent, self.root):
            self.runner.manifest["city"] = str(city)
            with self.subTest(city=city), self.assertRaises(AcceptanceFailure):
                self.runner.command(self.gc, "bb", "install")


if __name__ == "__main__": unittest.main()
