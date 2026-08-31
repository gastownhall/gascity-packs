"""Durable, deployment-neutral runtime for the docs-impact lifecycle.

This module owns only files and lifecycle transitions.  A deployment provides
an adapter whose ``perform(action, run)`` method performs the recorded action
and whose ``head_is_current(run)`` method reads the current pull-request head.
"""

from __future__ import annotations

import copy
import base64
import hashlib
import json
import os
import pathlib
import tempfile
from contextlib import contextmanager
from typing import Any, Protocol

import fcntl

import github_intake_docs_patch_worker as worker
from github_docs_pr_review_lifecycle import Candidate, DocsReviewRun, Transition, begin, reconcile


class DocsReviewAdapter(Protocol):
    def head_is_current(self, run: dict[str, Any]) -> bool: ...
    def perform(self, action: str, run: dict[str, Any]) -> None: ...


class FileDocsReviewStore:
    """A small atomic-json store suitable for one deployment's shared volume."""

    def __init__(self, root: pathlib.Path | str) -> None:
        self.root = pathlib.Path(root)
        self.runs_dir = self.root / "runs"
        self.candidates_dir = self.root / "candidates"

    @staticmethod
    def _name(identity: str) -> str:
        return hashlib.sha256(identity.encode("utf-8")).hexdigest() + ".json"

    def _path(self, identity: str) -> pathlib.Path:
        return self.runs_dir / self._name(identity)

    @contextmanager
    def lock(self, identity: str):
        """Serialize all read-transition-write operations for one immutable run."""
        self.runs_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_path = self.runs_dir / f"{self._name(identity)}.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def load(self, identity: str) -> dict[str, Any] | None:
        try:
            value = json.loads(self._path(identity).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if not isinstance(value, dict) or value.get("identity") != identity:
            raise ValueError("stored docs review run is invalid")
        return value

    def save(self, run: dict[str, Any]) -> dict[str, Any]:
        identity = str(run.get("identity", ""))
        if not identity:
            raise ValueError("stored docs review run requires identity")
        self.runs_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(identity)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.runs_dir, delete=False) as handle:
            handle.write(json.dumps(run, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = pathlib.Path(handle.name)
        temporary.replace(path)
        return run

    def list_runs(self) -> list[dict[str, Any]]:
        if not self.runs_dir.exists():
            return []
        result = []
        for path in sorted(self.runs_dir.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("stored docs review run is invalid")
            result.append(value)
        return result

    def audit_candidate(self, identity: str, envelope: dict[str, Any], now: float) -> None:
        self.candidates_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        digest = hashlib.sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        path = self.candidates_dir / f"{self._name(identity)[:-5]}-{digest}.json"
        if not path.exists():
            path.write_text(json.dumps({"received_at": now, "candidate": envelope}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def assignment_from_paginated_evidence(delivery: dict[str, Any], pages: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Construct a Task-1 assignment only from complete text patches on all pages."""
    required = ("repository_id", "repository", "pr_number", "head_sha", "base_sha", "base_ref")
    if not isinstance(delivery, dict) or any(key not in delivery for key in required):
        raise ValueError("delivery lacks immutable pull-request identity")
    repository_id, repository = str(delivery["repository_id"]), str(delivery["repository"])
    pr_number = delivery["pr_number"]
    head_sha, base_sha, base_ref = str(delivery["head_sha"]).lower(), str(delivery["base_sha"]).lower(), str(delivery["base_ref"])
    if not repository_id or not repository or type(pr_number) is not int or pr_number <= 0:
        raise ValueError("delivery lacks immutable pull-request identity")
    files: list[dict[str, str]] = []
    for page in pages:
        if not isinstance(page, list):
            raise ValueError("evidence page must be a list")
        for changed in page:
            if not isinstance(changed, dict):
                raise ValueError("evidence file must be an object")
            path, patch = changed.get("filename"), changed.get("patch")
            if (not isinstance(path, str) or not path or not isinstance(patch, str) or not patch
                    or changed.get("truncated") is True or "Binary files" in patch or "GIT binary patch" in patch):
                raise ValueError("evidence requires a complete text patch")
            files.append({"path": path, "reference": f"github://{repository}/blob/{head_sha}/{path}", "patch": patch})
    if not files:
        raise ValueError("evidence requires at least one complete text patch")
    files.sort(key=lambda item: item["path"])
    if len({item["path"] for item in files}) != len(files):
        raise ValueError("evidence paths must be unique")
    identity = {"repository_id": repository_id, "repository": repository, "pr_number": pr_number, "head_sha": head_sha, "source_key": f"github-pr:{repository_id}:{pr_number}:{head_sha}"}
    assignment = {"schema_version": 1, "kind": "github-pr-docs-impact-assignment", "identity": identity, "agent_skill": "developer-experience-techdocs", "evidence_bundle": {"head_sha": head_sha, "files": files, "proposal_identity": {"repository_id": repository_id, "repository": repository, "pr_number": pr_number, "base_sha": base_sha, "head_sha": head_sha, "head_repository_id": str(delivery.get("head_repository_id", repository_id)), "head_repository": str(delivery.get("head_repository", repository)), "base_ref": base_ref}}}
    return worker.validate_assignment(assignment)


def _model(record: dict[str, Any]) -> DocsReviewRun:
    return DocsReviewRun(**{key: record.get(key) for key in ("identity", "state", "created_at", "deadline_at", "lease_until", "attempt", "conclusion")})


def _record(transition: Transition, assignment: dict[str, Any], assignment_bytes: bytes, prior: dict[str, Any] | None = None) -> dict[str, Any]:
    run = transition.run
    pending_actions = list(transition.actions)
    if prior and prior.get("state") == run.state and prior.get("pending_actions"):
        pending_actions = list(prior["pending_actions"])
    result = {"identity": run.identity, "state": run.state, "created_at": run.created_at, "deadline_at": run.deadline_at, "lease_until": run.lease_until, "attempt": run.attempt, "conclusion": run.conclusion, "assignment": assignment, "assignment_bytes": base64.b64encode(assignment_bytes).decode("ascii"), "external_id": f"docs-impact:{run.identity}", "pending_actions": pending_actions}
    if prior and "candidate" in prior:
        result["candidate"] = prior["candidate"]
    # Projection state is durable intent/result evidence.  The generic runtime
    # does not interpret it, but must not discard it while reconciling the
    # lifecycle around an App crash or restart.
    if prior:
        for key in ("followup", "check"):
            if key in prior:
                result[key] = copy.deepcopy(prior[key])
    return result


def _perform(store: FileDocsReviewStore, adapter: DocsReviewAdapter, record: dict[str, Any]) -> None:
    """Perform actions after their durable intent has been written, one at a time."""
    while record["pending_actions"]:
        action = record["pending_actions"][0]
        action_record = copy.deepcopy(record)
        adapter.perform(action, action_record)
        # A trusted projection may durably attach its own intent/result record
        # while performing an action. Keep that state when acknowledging the
        # lifecycle action; otherwise this final save could erase crash
        # recovery evidence written immediately before a remote mutation.
        for key in ("followup", "check"):
            if key in action_record:
                record[key] = action_record[key]
        for key in ("state", "conclusion"):
            if key in action_record:
                record[key] = action_record[key]
        record["pending_actions"] = record["pending_actions"][1:]
        store.save(record)


def _normalize_assignment(value: dict[str, Any] | bytes) -> tuple[dict[str, Any], bytes]:
    if isinstance(value, bytes):
        return worker.load_assignment_bytes(value), value
    assignment = worker.validate_assignment(value)
    return assignment, json.dumps(assignment, sort_keys=True, separators=(",", ":")).encode()


def _assignment_bytes(record: dict[str, Any]) -> bytes:
    encoded = record.get("assignment_bytes")
    if not isinstance(encoded, str):
        raise ValueError("stored docs review run lacks original assignment bytes")
    return base64.b64decode(encoded, validate=True)


def _proven_assignment_bytes(record: dict[str, Any]) -> bytes:
    """Prove byte evidence and persisted normalized assignment are identical."""
    raw = _assignment_bytes(record)
    from_bytes = worker.load_assignment_bytes(raw)
    persisted = worker.validate_assignment(record.get("assignment"))
    canonical_bytes = json.dumps(from_bytes, sort_keys=True, separators=(",", ":"))
    canonical_persisted = json.dumps(persisted, sort_keys=True, separators=(",", ":"))
    if canonical_bytes != canonical_persisted:
        raise ValueError("assignment proof does not match persisted immutable evidence")
    return raw


def _legacy_record(record: dict[str, Any]) -> dict[str, Any]:
    """Fail closed when an old record cannot prove its immutable assignment."""
    failed = copy.deepcopy(record)
    failed["state"] = "terminal"
    failed["conclusion"] = "action_required"
    failed["pending_actions"] = ["ensure_terminal_check"]
    failed["operational_reason"] = "legacy immutable assignment proof is unavailable or mismatched"
    return failed


def _has_assignment_bytes(record: dict[str, Any]) -> bool:
    try:
        _proven_assignment_bytes(record)
    except (ValueError, TypeError):
        return False
    return True


def intake_delivery(store: FileDocsReviewStore, assignment: dict[str, Any] | bytes, adapter: DocsReviewAdapter, *, now: float, lease_seconds: float = 300, deadline_seconds: float = 1800, perform_actions: bool = True) -> dict[str, Any]:
    assignment, assignment_bytes = _normalize_assignment(assignment)
    identity = assignment["identity"]["source_key"]
    with store.lock(identity):
        prior = store.load(identity)
        if prior is not None and not _has_assignment_bytes(prior):
            record = _legacy_record(prior)
            store.save(record)
            if perform_actions:
                _perform(store, adapter, record)
            return record
        if prior is not None and prior["assignment"] != assignment:
            raise ValueError("different assignment for existing immutable review identity")
        transition = begin(identity, now=now, existing=_model(prior) if prior else None, lease_seconds=lease_seconds, deadline_seconds=deadline_seconds)
        record = _record(transition, assignment, _proven_assignment_bytes(prior) if prior else assignment_bytes, prior)
        store.save(record)
        if perform_actions:
            _perform(store, adapter, record)
        return record


def accept_candidate(store: FileDocsReviewStore, envelope: dict[str, Any], adapter: DocsReviewAdapter, *, now: float) -> dict[str, Any]:
    identity = str(((envelope.get("artifact") or {}).get("identity") or {}).get("source_key", ""))
    with store.lock(identity):
        record = store.load(identity)
        if record is None:
            return {"accepted": False, "reason": "unknown run"}
        if not _has_assignment_bytes(record):
            record = _legacy_record(record)
            store.save(record)
            _perform(store, adapter, record)
            return {"accepted": False, "reason": "legacy record cannot validate candidate"}
        normalized = worker.validate_final_candidate(_proven_assignment_bytes(record), envelope)
        store.audit_candidate(identity, normalized, now)
        if record["state"] in {"terminal", "stale"} or "candidate" in record:
            transition = reconcile(_model(record), now=now, head_is_current=adapter.head_is_current(copy.deepcopy(record)))
            record = _record(transition, record["assignment"], _proven_assignment_bytes(record), record)
            store.save(record)
            _perform(store, adapter, record)
            return {"accepted": False, "reason": "terminal or duplicate"}
        record["candidate"] = normalized
        transition = reconcile(_model(record), now=now, head_is_current=adapter.head_is_current(copy.deepcopy(record)), candidate=Candidate(identity=identity, verdict=normalized["artifact"]["verdict"]))
        record = _record(transition, record["assignment"], _proven_assignment_bytes(record), record)
        store.save(record)
        _perform(store, adapter, record)
        return {"accepted": True, "run": record}


def reconcile_pending(store: FileDocsReviewStore, adapter: DocsReviewAdapter, *, now: float, lease_seconds: float = 300) -> list[dict[str, Any]]:
    reconciled: list[dict[str, Any]] = []
    for listed in store.list_runs():
        identity = listed["identity"]
        with store.lock(identity):
            prior = store.load(identity)
            if prior is None:
                continue
            if not _has_assignment_bytes(prior):
                record = _legacy_record(prior)
                store.save(record)
                _perform(store, adapter, record)
                reconciled.append(record)
                continue
            candidate = prior.get("candidate")
            value = Candidate(identity=prior["identity"], verdict=candidate["artifact"]["verdict"]) if candidate and prior["state"] not in {"terminal", "stale"} else None
            transition = reconcile(_model(prior), now=now, head_is_current=adapter.head_is_current(copy.deepcopy(prior)), candidate=value, lease_seconds=lease_seconds)
            record = _record(transition, prior["assignment"], _proven_assignment_bytes(prior), prior)
            store.save(record)
            _perform(store, adapter, record)
            reconciled.append(record)
    return reconciled
