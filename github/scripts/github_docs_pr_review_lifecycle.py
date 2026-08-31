"""Deployment-neutral state transitions for GitHub docs PR review.

Deployments persist :class:`DocsReviewRun` and perform the returned actions.
This module deliberately has no GitHub, process, queue, or scheduler client.
"""

from __future__ import annotations

from dataclasses import dataclass


SUCCESS_VERDICTS = frozenset({"no-impact", "docs-sufficient"})


@dataclass(frozen=True)
class Candidate:
    """A validated candidate bound to the immutable review identity."""

    identity: str
    verdict: str


@dataclass(frozen=True)
class DocsReviewRun:
    """Persisted state for exactly one repository, PR, and head revision."""

    identity: str
    state: str
    created_at: float
    deadline_at: float
    lease_until: float
    attempt: int
    conclusion: str | None = None


@dataclass(frozen=True)
class Transition:
    """The new durable state and idempotent adapter actions to perform."""

    run: DocsReviewRun
    actions: tuple[str, ...]


def begin(
    identity: str,
    *,
    now: float,
    existing: DocsReviewRun | None = None,
    lease_seconds: float = 300,
    deadline_seconds: float = 1800,
) -> Transition:
    """Create one visible run and dispatch it once; duplicate delivery converges."""
    if existing is not None:
        if existing.identity != identity:
            raise ValueError("existing run identity differs from delivery identity")
        action = "ensure_stale_check" if existing.state == "stale" else "ensure_terminal_check" if existing.state == "terminal" else "ensure_check"
        return Transition(existing, (action,))
    if not identity:
        raise ValueError("review identity is required")
    if lease_seconds <= 0 or deadline_seconds <= 0:
        raise ValueError("lease and deadline must be positive")
    return Transition(
        DocsReviewRun(
            identity=identity,
            state="dispatched",
            created_at=now,
            deadline_at=now + deadline_seconds,
            lease_until=now + lease_seconds,
            attempt=1,
        ),
        ("ensure_check", "dispatch"),
    )


def reconcile(
    run: DocsReviewRun,
    *,
    now: float,
    head_is_current: bool,
    candidate: Candidate | None = None,
    lease_seconds: float = 300,
) -> Transition:
    """Advance a run at most once, safely after duplicate work or restart."""
    if run.state == "stale":
        return Transition(run, ("ensure_stale_check",))
    if run.state == "terminal":
        return Transition(run, ("ensure_terminal_check",))
    if not head_is_current:
        return Transition(
            _terminal(run, "stale"),
            ("ensure_stale_check",),
        )
    if now >= run.deadline_at:
        return Transition(
            _terminal(run, "action_required"),
            ("ensure_terminal_check",),
        )
    if candidate is not None and candidate.identity == run.identity:
        conclusion = "success" if candidate.verdict in SUCCESS_VERDICTS else "action_required"
        return Transition(_terminal(run, conclusion), ("ensure_terminal_check",))
    if now >= run.lease_until:
        if lease_seconds <= 0:
            raise ValueError("lease must be positive")
        return Transition(
            DocsReviewRun(
                identity=run.identity,
                state="dispatched",
                created_at=run.created_at,
                deadline_at=run.deadline_at,
                lease_until=now + lease_seconds,
                attempt=run.attempt + 1,
            ),
            ("dispatch",),
        )
    # A persisted in-progress run may have crashed before its Check Run write.
    # Re-emitting this idempotent action lets an adapter adopt or create it.
    return Transition(run, ("ensure_check",))


def _terminal(run: DocsReviewRun, conclusion: str) -> DocsReviewRun:
    return DocsReviewRun(
        identity=run.identity,
        state="stale" if conclusion == "stale" else "terminal",
        created_at=run.created_at,
        deadline_at=run.deadline_at,
        lease_until=run.lease_until,
        attempt=run.attempt,
        conclusion=conclusion,
    )
