"""Fail-closed matrix and privacy checks; a green ledger test is not live E2E."""

import json
from pathlib import Path
import tempfile
import unittest

from e2e_report import E2ELedger, ReportFailure, validate_artifacts


ARTIFACTS = {"gc_commit": "a" * 40, "gc_binary_sha256": "b" * 64, "pack_sha256": "c" * 64,
             "bb_version": "0.42.1", "runtime": "codex", "runtime_version": "0.121.0",
             "verification_mode": "development", "gc_version": "1.4.0-pr6106+abcdef1234"}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = E2ELedger(self.root / "run", required_cases=["personal-global", "mapped-rig"], artifacts=ARTIFACTS)
        self.addCleanup(self.finalize_if_needed)
        self.proof = self.ledger.private / "browser-proof.json"
        self.proof.write_text('{"fixture": "only unit-test evidence"}')

    def finalize_if_needed(self):
        if not self.ledger._finalized:
            self.ledger.finalize()

    def pass_case(self, case):
        return self.ledger.record(case, "passed", assertions=["independent-transcript"], evidence_files=[self.proof])

    def test_missing_required_case_prevents_pass(self):
        self.pass_case("personal-global")
        result = self.ledger.finalize()
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["cases"][1]["status"], "not_run")
        self.assertEqual(result["counts"]["not_run"], 1)

    def test_all_declared_cases_with_evidence_can_pass_and_events_are_retained(self):
        self.pass_case("personal-global")
        original = (self.ledger.root / "cases.jsonl").read_bytes()
        self.pass_case("mapped-rig")
        result = self.ledger.finalize()
        self.assertEqual(result["status"], "passed")
        self.assertTrue((self.ledger.root / "cases.jsonl").read_bytes().startswith(original))
        self.assertEqual(json.loads((self.ledger.root / "summary.json").read_text()), result)
        self.assertEqual(result["artifacts"], ARTIFACTS)
        with self.assertRaisesRegex(ReportFailure, "already finalized"):
            self.ledger.finalize()

    def test_blocked_failed_or_skipped_cases_cannot_pass(self):
        self.ledger.record("personal-global", "blocked", reason_code="missing_credentials")
        self.assertEqual(self.ledger.summary()["status"], "blocked")
        self.ledger.record("mapped-rig", "failed", reason_code="timeout")
        self.assertEqual(self.ledger.summary()["status"], "failed")
        with self.assertRaisesRegex(ReportFailure, "settled case"):
            self.pass_case("mapped-rig")

    def test_unknown_case_fake_pass_or_arbitrary_reason_is_rejected(self):
        with self.assertRaisesRegex(ReportFailure, "not declared"):
            self.pass_case("missing-from-matrix")
        with self.assertRaisesRegex(ReportFailure, "requires assertions"):
            self.ledger.record("personal-global", "passed")
        with self.assertRaisesRegex(ReportFailure, "recognized public"):
            self.ledger.record("personal-global", "failed", reason_code="token=secret /Users/private")
        with self.assertRaisesRegex(ReportFailure, "explicitly pass"):
            self.ledger.record("personal-global", "skipped")

    def test_exception_details_are_private_and_public_summary_has_only_hashes(self):
        secret = "token=very-secret /Users/private/customer-project"
        self.ledger.record_error("personal-global", RuntimeError(secret), reason_code="provider_unavailable")
        self.ledger.block_remaining("dependency_failed")
        report = self.ledger.finalize()
        public = json.dumps(report) + (self.ledger.root / "cases.jsonl").read_text()
        self.assertNotIn(secret, public)
        self.assertNotIn("/Users", public)
        self.assertNotIn("RuntimeError", public)
        private = self.ledger.private / "case-0001-exception.txt"
        self.assertIn(secret, private.read_text())
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)

    def test_artifact_identities_must_be_complete_exact_and_safe(self):
        for changed in ({key: value for key, value in ARTIFACTS.items() if key != "gc_commit"},
                        {**ARTIFACTS, "gc_commit": "abcd123"},
                        {**ARTIFACTS, "runtime_version": "latest"},
                        {**ARTIFACTS, "extra": "secret"},
                        {**ARTIFACTS, "bb_version": "0.42.1 /Users/private"}):
            with self.subTest(changed=changed), self.assertRaises(ReportFailure):
                validate_artifacts(changed)

    def test_existing_directory_or_external_evidence_is_not_touched(self):
        with self.assertRaises(FileExistsError):
            E2ELedger(self.ledger.root, required_cases=["one"], artifacts=ARTIFACTS)
        outside = self.root / "outside.txt"
        outside.write_text("preserve")
        with self.assertRaisesRegex(ReportFailure, "scratch tree"):
            self.ledger.record("personal-global", "passed", assertions=["proof"], evidence_files=[outside])
        self.assertEqual(outside.read_text(), "preserve")

    def test_optional_route_is_bounded_metadata_and_cannot_satisfy_acceptance(self):
        labeled = {**ARTIFACTS, "runtime": "claude", "model_route": "kimi-for-coding"}
        self.assertEqual(validate_artifacts(labeled), labeled)
        self.assertEqual(validate_artifacts(ARTIFACTS), ARTIFACTS)
        ledger = E2ELedger(self.root / "labeled", required_cases=["inference"], artifacts=labeled)
        self.assertEqual(ledger.finalize()["status"], "incomplete")
        for value in (None, "", "https://private.example/api?key=secret", "/Users/private", "a" * 97, {"key": "secret"}):
            with self.subTest(value=value), self.assertRaises(ReportFailure):
                validate_artifacts({**ARTIFACTS, "model_route": value})

    def test_duplicate_case_ids_cannot_shrink_the_required_matrix(self):
        with self.assertRaisesRegex(ReportFailure, "unique stable"):
            E2ELedger(self.root / "unused", required_cases=["one", "one"], artifacts=ARTIFACTS)


if __name__ == "__main__":
    unittest.main()
