from __future__ import annotations

import unittest
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from github_docs_pr_review_lifecycle import (
    Candidate,
    begin,
    reconcile,
)


class DocsPrReviewLifecycleTests(unittest.TestCase):
    def test_duplicate_delivery_reuses_one_visible_run(self) -> None:
        first = begin("42:7:head-a", now=100)
        duplicate = begin("42:7:head-a", existing=first.run, now=101)

        self.assertEqual(first.actions, ("ensure_check", "dispatch"))
        self.assertEqual(duplicate.run, first.run)
        self.assertEqual(duplicate.actions, ("ensure_check",))


    def test_recovery_redispatches_an_expired_lease_without_another_check(self) -> None:
        started = begin("42:7:head-a", now=100, lease_seconds=30)

        recovered = reconcile(started.run, now=131, head_is_current=True)

        self.assertEqual(recovered.run.attempt, 2)
        self.assertEqual(recovered.run.state, "dispatched")
        self.assertEqual(recovered.actions, ("dispatch",))


    def test_late_candidate_does_not_reopen_an_expired_run(self) -> None:
        started = begin("42:7:head-a", now=100, lease_seconds=30, deadline_seconds=60)
        expired = reconcile(started.run, now=161, head_is_current=True)

        late = reconcile(
            expired.run,
            now=162,
            head_is_current=True,
            candidate=Candidate(identity="42:7:head-a", verdict="docs-sufficient"),
        )

        self.assertEqual(expired.run.state, "terminal")
        self.assertEqual(expired.run.conclusion, "action_required")
        self.assertEqual(expired.actions, ("ensure_terminal_check",))
        self.assertEqual(late.run, expired.run)
        self.assertEqual(late.actions, ("ensure_terminal_check",))


    def test_matching_candidate_completes_the_original_run_once(self) -> None:
        started = begin("42:7:head-a", now=100)

        completed = reconcile(
            started.run,
            now=101,
            head_is_current=True,
            candidate=Candidate(identity="42:7:head-a", verdict="no-impact"),
        )
        duplicate = reconcile(
            completed.run,
            now=102,
            head_is_current=True,
            candidate=Candidate(identity="42:7:head-a", verdict="no-impact"),
        )

        self.assertEqual(completed.run.state, "terminal")
        self.assertEqual(completed.run.conclusion, "success")
        self.assertEqual(completed.actions, ("ensure_terminal_check",))
        self.assertEqual(duplicate.run, completed.run)
        self.assertEqual(duplicate.actions, ("ensure_terminal_check",))

    def test_changed_head_marks_the_old_run_stale_without_dispatching(self) -> None:
        started = begin("42:7:head-a", now=100)

        stale = reconcile(started.run, now=101, head_is_current=False)

        self.assertEqual(stale.run.state, "stale")
        self.assertEqual(stale.run.conclusion, "stale")
        self.assertEqual(stale.actions, ("ensure_stale_check",))

    def test_reconcile_reensures_a_waiting_visible_check_after_restart(self) -> None:
        started = begin("42:7:head-a", now=100)

        recovered = reconcile(started.run, now=101, head_is_current=True)

        self.assertEqual(recovered.run, started.run)
        self.assertEqual(recovered.actions, ("ensure_check",))
