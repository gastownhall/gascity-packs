from __future__ import annotations

import hashlib
import json
import multiprocessing
import pathlib
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import github_intake_docs_review_runtime as runtime


SHA = "a" * 40


def assignment(head_sha: str = SHA) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "github-pr-docs-impact-assignment",
        "identity": {
            "repository_id": "17",
            "repository": "example/docs",
            "pr_number": 9,
            "head_sha": head_sha,
            "source_key": f"github-pr:17:9:{head_sha}",
        },
        "agent_skill": "developer-experience-techdocs",
        "evidence_bundle": {
            "head_sha": head_sha,
            "proposal_identity": {
                "repository_id": "17", "repository": "example/docs", "pr_number": 9,
                "base_sha": "b" * 40, "head_sha": head_sha,
                "head_repository_id": "17", "head_repository": "example/docs", "base_ref": "main",
            },
            "files": [{
                "path": "docs/guide.md",
                "reference": f"github://example/docs/blob/{head_sha}/docs/guide.md",
                "patch": "@@ -1 +1 @@\n-old\n+new\n",
            }],
        },
    }


def candidate(source: dict[str, object], verdict: str = "no-impact") -> dict[str, object]:
    raw = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    identity = source["identity"]
    artifact = {
        "schema_version": 1, "kind": "github-pr-docs-impact-review", "identity": identity,
        "agent_skill": "developer-experience-techdocs", "verdict": verdict,
        "rationale": "The documentation is sufficient.",
        "evidence": [{"path": "docs/guide.md", "evidence": f"github://example/docs/blob/{identity['head_sha']}/docs/guide.md"}],
        "confidence": 0.9, "proposal": None,
    }
    return {"schema_version": 1, "snapshot_sha256": hashlib.sha256(raw).hexdigest(), "artifact": artifact}


class RecordingAdapter:
    def __init__(self, current: bool = True) -> None:
        self.current = current
        self.actions: list[tuple[str, str]] = []

    def head_is_current(self, run: dict[str, object]) -> bool:
        return self.current

    def perform(self, action: str, run: dict[str, object]) -> None:
        self.actions.append((action, str(run["identity"])))


class NoopAdapter:
    def head_is_current(self, run: dict[str, object]) -> bool:
        return True

    def perform(self, action: str, run: dict[str, object]) -> None:
        return None


def submit_from_process(root: str, envelope: dict[str, object], queue: multiprocessing.Queue) -> None:
    response = runtime.accept_candidate(runtime.FileDocsReviewStore(root), envelope, NoopAdapter(), now=101)
    queue.put(response["accepted"])


class DocsReviewRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store = runtime.FileDocsReviewStore(pathlib.Path(self.tempdir.name))
        self.adapter = RecordingAdapter()

    def test_duplicate_delivery_reuses_persisted_run_and_only_reensures_check(self) -> None:
        source = assignment()
        first = runtime.intake_delivery(self.store, source, self.adapter, now=100)
        duplicate = runtime.intake_delivery(self.store, source, self.adapter, now=101)

        self.assertEqual(first["identity"], duplicate["identity"])
        self.assertEqual(first["attempt"], 1)
        self.assertEqual(self.adapter.actions, [("ensure_check", first["identity"]), ("dispatch", first["identity"]), ("ensure_check", first["identity"])])

    def test_duplicate_intake_keeps_the_original_bytes_and_pending_dispatch(self) -> None:
        source = assignment()
        raw = json.dumps(source, separators=(",", ":")).encode()
        first = runtime.intake_delivery(self.store, raw, self.adapter, now=100, perform_actions=False)

        duplicate = runtime.intake_delivery(self.store, source, self.adapter, now=101, perform_actions=False)

        self.assertEqual(duplicate["assignment_bytes"], first["assignment_bytes"])
        self.assertEqual(duplicate["pending_actions"], ["ensure_check", "dispatch"])

    def test_duplicate_intake_rejects_a_different_assignment_for_the_same_identity(self) -> None:
        source = assignment()
        runtime.intake_delivery(self.store, source, self.adapter, now=100)
        different = assignment()
        different["evidence_bundle"]["files"][0]["patch"] = "@@ -1 +1 @@\n-old\n+different\n"

        with self.assertRaisesRegex(ValueError, "different assignment"):
            runtime.intake_delivery(self.store, different, self.adapter, now=101)

    def test_complete_paginated_evidence_becomes_a_sorted_assignment(self) -> None:
        delivery = {"repository_id": "17", "repository": "example/docs", "pr_number": 9, "head_sha": SHA, "base_sha": "b" * 40, "base_ref": "main"}
        pages = [
            [{"filename": "README.md", "patch": "@@ -1 +1 @@\n-old\n+new\n"}],
            [{"filename": "docs/guide.md", "patch": "@@ -1 +1 @@\n-old\n+new\n"}],
        ]

        built = runtime.assignment_from_paginated_evidence(delivery, pages)

        self.assertEqual([item["path"] for item in built["evidence_bundle"]["files"]], ["README.md", "docs/guide.md"])
        self.assertEqual(built["identity"]["source_key"], f"github-pr:17:9:{SHA}")

    def test_missing_binary_or_truncated_evidence_is_rejected_before_dispatch(self) -> None:
        delivery = {"repository_id": "17", "repository": "example/docs", "pr_number": 9, "head_sha": SHA, "base_sha": "b" * 40, "base_ref": "main"}
        for item in ({"filename": "docs/a.md"}, {"filename": "docs/a.md", "patch": "Binary files differ"}, {"filename": "docs/a.md", "patch": "@@ -1 +1 @@\n-old\n+new\n", "truncated": True}):
            with self.subTest(item=item):
                with self.assertRaisesRegex(ValueError, "complete text patch"):
                    runtime.assignment_from_paginated_evidence(delivery, [[item]])

    def test_reconcile_recovers_persisted_dispatch_after_a_crash(self) -> None:
        source = assignment()
        run = runtime.intake_delivery(self.store, source, self.adapter, now=100, perform_actions=False)

        runtime.reconcile_pending(self.store, self.adapter, now=101)

        self.assertEqual(self.adapter.actions, [("ensure_check", run["identity"]), ("dispatch", run["identity"])])

    def test_expired_lease_redispatches_without_another_check(self) -> None:
        run = runtime.intake_delivery(self.store, assignment(), self.adapter, now=100, lease_seconds=30)
        self.adapter.actions.clear()

        runtime.reconcile_pending(self.store, self.adapter, now=131, lease_seconds=30)

        self.assertEqual(self.adapter.actions, [("dispatch", run["identity"])])
        self.assertEqual(self.store.load(run["identity"])["attempt"], 2)

    def test_stale_head_completes_only_the_stale_check(self) -> None:
        run = runtime.intake_delivery(self.store, assignment(), self.adapter, now=100)
        self.adapter.actions.clear()
        self.adapter.current = False

        runtime.reconcile_pending(self.store, self.adapter, now=101)

        self.assertEqual(self.store.load(run["identity"])["state"], "stale")
        self.assertEqual(self.adapter.actions, [("ensure_stale_check", run["identity"])])

    def test_stale_reconciliation_replaces_obsolete_pending_dispatch(self) -> None:
        run = runtime.intake_delivery(self.store, assignment(), self.adapter, now=100, perform_actions=False)
        self.adapter.current = False

        runtime.reconcile_pending(self.store, self.adapter, now=101)

        self.assertEqual(self.adapter.actions, [("ensure_stale_check", run["identity"])])

    def test_late_candidate_is_audited_but_cannot_reopen_deadline_terminal_run(self) -> None:
        source = assignment()
        run = runtime.intake_delivery(self.store, source, self.adapter, now=100, deadline_seconds=60)
        runtime.reconcile_pending(self.store, self.adapter, now=160)
        self.adapter.actions.clear()

        accepted = runtime.accept_candidate(self.store, candidate(source), self.adapter, now=161)

        self.assertFalse(accepted["accepted"])
        self.assertEqual(self.store.load(run["identity"])["conclusion"], "action_required")
        self.assertEqual(self.adapter.actions, [("ensure_terminal_check", run["identity"])])

    def test_deadline_completes_an_operational_failure_once(self) -> None:
        run = runtime.intake_delivery(self.store, assignment(), self.adapter, now=100, deadline_seconds=60)
        self.adapter.actions.clear()

        runtime.reconcile_pending(self.store, self.adapter, now=160)
        runtime.reconcile_pending(self.store, self.adapter, now=161)

        self.assertEqual(self.store.load(run["identity"])["conclusion"], "action_required")
        self.assertEqual(self.adapter.actions, [("ensure_terminal_check", run["identity"]), ("ensure_terminal_check", run["identity"])])

    def test_concurrent_valid_candidates_allow_only_one_terminal_winner(self) -> None:
        source = assignment()
        self.store = runtime.FileDocsReviewStore(pathlib.Path(self.tempdir.name))
        runtime.intake_delivery(self.store, source, self.adapter, now=100)
        contenders = [candidate(source, "no-impact"), candidate(source, "inconclusive")]
        barrier = threading.Barrier(2)
        results: list[tuple[str, bool]] = []

        def submit(envelope: dict[str, object]) -> None:
            barrier.wait()
            response = runtime.accept_candidate(self.store, envelope, self.adapter, now=101)
            results.append((str(envelope["artifact"]["verdict"]), bool(response["accepted"])))

        threads = [threading.Thread(target=submit, args=(envelope,)) for envelope in contenders]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        winners = [verdict for verdict, accepted in results if accepted]
        self.assertEqual(len(winners), 1)
        stored = self.store.load(str(source["identity"]["source_key"]))
        self.assertEqual(stored["candidate"]["artifact"]["verdict"], winners[0])

    def test_processes_serialise_candidate_acceptance_for_one_run(self) -> None:
        source = assignment()
        runtime.intake_delivery(self.store, source, self.adapter, now=100)
        queue: multiprocessing.Queue = multiprocessing.Queue()
        processes = [multiprocessing.Process(target=submit_from_process, args=(self.tempdir.name, envelope, queue)) for envelope in (candidate(source, "no-impact"), candidate(source, "inconclusive"))]
        for process in processes:
            process.start()
        for process in processes:
            process.join()

        self.assertEqual([process.exitcode for process in processes], [0, 0])
        self.assertEqual(sorted([queue.get(), queue.get()]), [False, True])

    def test_legacy_record_without_assignment_bytes_fails_closed_and_does_not_stop_scan(self) -> None:
        legacy_source = assignment()
        legacy = runtime.intake_delivery(self.store, legacy_source, self.adapter, now=100)
        legacy_record = self.store.load(legacy["identity"])
        legacy_record.pop("assignment_bytes")
        self.store.save(legacy_record)
        current_source = assignment("c" * 40)
        current = runtime.intake_delivery(self.store, current_source, self.adapter, now=100)
        self.adapter.actions.clear()

        reconciled = runtime.reconcile_pending(self.store, self.adapter, now=101)

        failed_closed = self.store.load(legacy["identity"])
        self.assertEqual(failed_closed["state"], "terminal")
        self.assertEqual(failed_closed["conclusion"], "action_required")
        self.assertIn("legacy", failed_closed["operational_reason"])
        self.assertEqual(failed_closed["assignment"], legacy_source)
        self.assertIn(current["identity"], [record["identity"] for record in reconciled])

    def test_duplicate_intake_and_candidate_for_legacy_record_fail_closed(self) -> None:
        source = assignment()
        run = runtime.intake_delivery(self.store, source, self.adapter, now=100)
        legacy_record = self.store.load(run["identity"])
        legacy_record.pop("assignment_bytes")
        self.store.save(legacy_record)

        duplicate = runtime.intake_delivery(self.store, source, self.adapter, now=101)
        received = runtime.accept_candidate(self.store, candidate(source), self.adapter, now=102)

        self.assertEqual(duplicate["state"], "terminal")
        self.assertFalse(received["accepted"])
        self.assertEqual(self.store.load(run["identity"])["conclusion"], "action_required")

    def test_mismatched_valid_assignment_bytes_fail_closed_before_candidate_b(self) -> None:
        source_a = assignment()
        source_b = assignment()
        source_b["evidence_bundle"]["files"][0]["patch"] = "@@ -1 +1 @@\n-old\n+evidence-b\n"
        run = runtime.intake_delivery(self.store, source_a, self.adapter, now=100)
        record = self.store.load(run["identity"])
        record["assignment"] = source_b
        self.store.save(record)

        received = runtime.accept_candidate(self.store, candidate(source_b), self.adapter, now=101)

        failed_closed = self.store.load(run["identity"])
        self.assertFalse(received["accepted"])
        self.assertEqual(failed_closed["conclusion"], "action_required")
        self.assertIn("proof", failed_closed["operational_reason"])


if __name__ == "__main__":
    unittest.main()
