from pathlib import Path
from types import SimpleNamespace
import unittest
from full_e2e_desktop_cases import desktop_journeys, HERE


class DesktopRoutingTests(unittest.TestCase):
    def test_only_ui_driver_is_routed_and_original_is_restored_after_failure(self):
        calls = []
        def original(*args, timeout=60): calls.append((args, timeout))
        runner = SimpleNamespace(command=original)
        with self.assertRaisesRegex(RuntimeError, "fixture error"):
            with desktop_journeys(runner, "/tmp/owned/desktop.json"):
                runner.command("node", HERE / "browser_driver.mjs", "--prompt", "exact", timeout=123)
                runner.command("bb", "thread", "list")
                raise RuntimeError("fixture error")
        self.assertIs(runner.command, original)
        self.assertEqual(calls[0], (("node", HERE / "desktop_journey.mjs", "--spec", "/tmp/owned/desktop.json", "--", "--prompt", "exact"), 123))
        self.assertEqual(calls[1], (("bb", "thread", "list"), 60))


if __name__ == "__main__": unittest.main()
