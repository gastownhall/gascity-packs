import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from full_e2e_fixture_catalog import prepare_fixtures, wait_for_fixture_catalog, browser_fixture, error_fixture
from live_assertions import AcceptanceFailure


class FixtureCatalogTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bb-fixture-catalog-")
        self.addCleanup(directory.cleanup)
        self.runner = SimpleNamespace(private=Path(directory.name),
            manifest={"hostId": "actual-host", "bbUrl": "http://127.0.0.1:1234"}, progress=lambda _: None)

    def test_prepare_keeps_approval_and_fresh_trust_fixtures_distinct_and_unstarted(self):
        made = []
        def create(_runner, **options):
            item = {"agent": {"id": "fixture-" + str(len(made))}, "options": options}
            made.append(item)
            return item
        with patch("full_e2e_browser_cases.create_fixture", side_effect=create), \
             patch("full_e2e_error_cases.create_error_fixture", side_effect=lambda r, mode: create(r, mode=mode)), \
             patch("full_e2e_fixture_catalog.wait_for_fixture_catalog") as wait:
            prepare_fixtures(self.runner, {"approvals.approve", "approvals.deny", "approvals.repeated",
                "approvals.interrupt", "trust.fresh", "error.provider", "native.personal"})
            wait.assert_not_called()
            self.assertEqual(len(made), 6)
            self.assertEqual(len(self.runner.prepared_catalog_ids), 6)
            permissions = [browser_fixture(self.runner, (True, False)) for _ in range(4)]
            self.assertEqual(len({item["agent"]["id"] for item in permissions}), 4)
            fresh = browser_fixture(self.runner, (False, False))
            self.assertFalse(fresh["options"]["trusted"])
            self.assertEqual(error_fixture(self.runner, "provider")["options"]["mode"], "provider")
            with self.assertRaises(AcceptanceFailure): browser_fixture(self.runner, (True, False))

    def test_wait_observes_stale_then_fresh_public_catalog_without_mutation(self):
        self.runner.prepared_catalog_ready = False
        self.runner.prepared_catalog_ids = {"new-a", "new-b"}
        elapsed, urls = [0], []
        def read(url):
            urls.append(url)
            return {"models": [{"id": value} for value in (["old"] if len(urls) == 1 else ["new-a", "new-b"])],
                    "modelLoadError": None}
        wait_for_fixture_catalog(self.runner, read=read, now=lambda: elapsed[0],
                                 sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
        self.assertEqual(len(urls), 2)
        self.assertTrue(all(url.endswith("hostId=actual-host&providerId=gas-city") for url in urls))
        evidence = json.loads((self.runner.private / "fixture-catalog-ready.json").read_text())
        self.assertFalse(evidence["cache_modified"])
        self.assertEqual(evidence["required_model_ids"], ["new-a", "new-b"])
        wait_for_fixture_catalog(self.runner, read=lambda _: self.fail("ready catalog re-read"))

    def test_missing_model_or_failed_catalog_cannot_satisfy_wait_and_timeout_is_bounded(self):
        for catalog in ({"models": [{"id": "other"}]},
                        {"models": [{"id": "required"}], "modelLoadError": {"code": "failed"}}):
            with self.subTest(catalog=catalog):
                self.runner.prepared_catalog_ready = False
                self.runner.prepared_catalog_ids = {"required"}
                elapsed = [0]
                with self.assertRaises(AcceptanceFailure):
                    wait_for_fixture_catalog(self.runner, timeout=3, read=lambda _: catalog,
                        now=lambda: elapsed[0], sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
                self.assertLess(elapsed[0], 4)
                self.assertFalse(self.runner.prepared_catalog_ready)


if __name__ == "__main__": unittest.main()
