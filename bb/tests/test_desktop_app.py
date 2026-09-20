import json
import os
from pathlib import Path
import tempfile
import unittest
from desktop_app import isolated_updater_config


class DesktopIsolationTests(unittest.TestCase):
    def test_updater_cache_resolves_outside_normal_cache_into_owned_scratch(self):
        with tempfile.TemporaryDirectory(prefix="bb-desktop-config-") as name:
            root = Path(name).resolve()
            base, cache = root / "normal-cache", root / "owned-cache"
            source = 'channel: latest\nurl: https://example.invalid/releases/\nupdaterCacheDirName: old-cache\n'
            result = isolated_updater_config(source, cache, cache_base=base)
            relative = json.loads(result.split("updaterCacheDirName: ")[1].strip())
            self.assertEqual(Path(os.path.normpath(base / relative)), cache)
            self.assertIn('channel: latest\nurl: https://example.invalid/releases/\n', result)

    def test_ambiguous_or_missing_updater_config_fails_closed(self):
        for source in ('url: anything\n', 'updaterCacheDirName: one\nupdaterCacheDirName: two\n'):
            with self.assertRaises(ValueError):
                isolated_updater_config(source, '/tmp/bb-test-cache')


if __name__ == "__main__": unittest.main()
