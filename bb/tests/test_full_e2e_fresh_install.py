import unittest
from unittest.mock import patch
from full_e2e_fresh_install import fresh_environment, check_gc_read_or_pack_command
from live_assertions import AcceptanceFailure


class FreshInstallGuards(unittest.TestCase):
    def test_fresh_cache_retains_the_existing_playwright_binary_location(self):
        original = {"GC_HOME": "/tmp/bb-live-fixture/gc-home", "HOME": "/home/person"}
        for platform, extra, expected in (
            ("linux", {}, "/home/person/.cache/ms-playwright"),
            ("linux", {"XDG_CACHE_HOME": "/installed/cache"}, "/installed/cache/ms-playwright"),
            ("darwin", {}, "/home/person/Library/Caches/ms-playwright"),
            ("linux", {"PLAYWRIGHT_BROWSERS_PATH": "/pinned/browser"}, "/pinned/browser"),
            ("linux", {"PLAYWRIGHT_BROWSERS_PATH": "0"}, "0"),
        ):
            with self.subTest(platform=platform, extra=extra), patch("full_e2e_fresh_install.sys.platform", platform):
                updated = fresh_environment({**original, **extra}, "/tmp/bb-live-fixture",
                                            "/tmp/bb-live-fixture/fresh", 54321, 54322)
                self.assertEqual(updated["PLAYWRIGHT_BROWSERS_PATH"], expected)
                self.assertNotIn("PLAYWRIGHT_BROWSERS_PATH", original)

    def test_fresh_bb_isolates_every_store_while_retaining_gc_and_home(self):
        original = {"GC_HOME": "/tmp/bb-live-fixture/gc-home", "HOME": "/Users/person", "BB_DATA_DIR": "/tmp/bb-live-fixture/bb-data"}
        updated = fresh_environment(original, "/tmp/bb-live-fixture", "/tmp/bb-live-fixture/fresh", 54321, 54322)
        self.assertEqual(updated["GC_HOME"], original["GC_HOME"])
        self.assertEqual(updated["HOME"], original["HOME"])
        self.assertEqual(original["BB_DATA_DIR"], "/tmp/bb-live-fixture/bb-data")
        for key in ("BB_DATA_DIR", "GC_BB_CONFIG", "GC_BB_INSTALL_DIR", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
            self.assertIn("bb-live-fixture/fresh/", updated[key])

    def test_normal_ports_shared_ports_and_outside_state_are_rejected(self):
        for path, ports in [("/Users/person/.bb", (54321, 54322)), ("/tmp/bb-live-fixture/fresh", (38886, 54322)),
                            ("/tmp/bb-live-fixture/fresh", (54321, 54321))]:
            with self.assertRaises(AcceptanceFailure): fresh_environment({"GC_HOME": "/tmp/bb-live-fixture/gc-home"}, "/tmp/bb-live-fixture", path, *ports)

    def test_new_bb_store_keeps_the_controller_native_configuration_and_pinned_path(self):
        original = {"GC_HOME": "/tmp/bb-live-fixture/gc-home", "HOME": "/Users/person",
            "MANIFOLD_CLAUDE_LAUNCH_CONFIG": "/tmp/bb-live-fixture/native-claude-launch.json",
            "CLAUDE_CONFIG_DIR": "/tmp/bb-live-fixture/claude-config", "PATH": "/pinned/runtime:/usr/bin"}
        updated = fresh_environment(original, "/tmp/bb-live-fixture", "/tmp/bb-live-fixture/fresh", 54321, 54322)
        for name in original:
            self.assertEqual(updated[name], original[name])

    def test_fresh_install_cannot_start_stop_or_reconfigure_the_existing_gc(self):
        for args in [("start",), ("stop",), ("supervisor", "start"), ("supervisor", "stop"), ("config", "set")]:
            with self.assertRaises(AcceptanceFailure): check_gc_read_or_pack_command(args)
        for args in [("bb", "install", "--yes"), ("bb", "connect"), ("bb", "agents"), ("supervisor", "status", "--json")]:
            check_gc_read_or_pack_command(args)


if __name__ == "__main__": unittest.main()
