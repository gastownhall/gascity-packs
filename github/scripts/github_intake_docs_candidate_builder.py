#!/usr/bin/env python3
"""Build a canonical docs proposal from a Git worktree, never an agent diff."""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
from typing import Any

import github_intake_docs_patch as docs_patch
import github_intake_docs_patch_worker as worker


def _git(repository: pathlib.Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), *args], capture_output=True, check=False
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip() or "git could not derive the proposal")
    return result.stdout


def _changed_paths(diff: str) -> list[str]:
    paths: set[str] = set()
    for old_path, new_path in docs_patch.DIFF_PATH_PATTERN.findall(diff):
        if old_path != "/dev/null":
            paths.add(docs_patch._validate_path(old_path))
        if new_path != "/dev/null":
            paths.add(docs_patch._validate_path(new_path))
    if not paths:
        raise ValueError("git produced no unified documentation paths")
    return sorted(paths)


def _file_digest(repository: pathlib.Path, path: str) -> str:
    candidate = repository / path
    if candidate.is_file():
        content = candidate.read_bytes()
    else:
        content = _git(repository, "show", f"HEAD:{path}")
    return hashlib.sha256(content).hexdigest()


def build_candidate(
    raw_assignment: bytes,
    repository: pathlib.Path,
    *,
    generated_at: str,
    claims: list[dict[str, str]],
    checks: list[dict[str, str]],
    review: dict[str, Any],
) -> dict[str, Any]:
    """Derive the only accepted patch from Git and bind it to raw assignment bytes."""
    assignment = worker.load_assignment_bytes(raw_assignment)
    repository = pathlib.Path(repository)
    actual_head = _git(repository, "rev-parse", "HEAD").decode("ascii").strip()
    if actual_head != assignment["evidence_bundle"]["proposal_identity"]["head_sha"]:
        raise ValueError("checkout HEAD does not match assigned proposal head SHA")
    diff_bytes = _git(repository, "diff", "--no-ext-diff", "--full-index", "--binary", "HEAD", "--")
    try:
        diff = diff_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("git produced a non-text documentation diff") from exc
    paths = _changed_paths(diff)
    identity = assignment["evidence_bundle"]["proposal_identity"]
    artifact = docs_patch.validate_artifact({
        "schema_version": docs_patch.SCHEMA_VERSION,
        "status": "proposed",
        "generated_at": generated_at,
        "identity": identity,
        "patch_sha256": hashlib.sha256(diff_bytes).hexdigest(),
        "diff": diff,
        "files": [{"path": path, "sha256": _file_digest(repository, path)} for path in paths],
        "claims": claims,
        "checks": checks,
    })
    envelope = {
        "schema_version": docs_patch.SCHEMA_VERSION,
        "snapshot_sha256": hashlib.sha256(raw_assignment).hexdigest(),
        "artifact": artifact,
    }
    review = docs_patch.validate_review_decision(review)
    if review["identity"] != assignment["identity"] or review["agent_skill"] != assignment["agent_skill"]:
        raise ValueError("review is not a proposal-free assignment-bound proposal-ready result")
    final_review = dict(review)
    final_review.pop("review_sha256", None)
    final_review["proposal"] = artifact
    return worker.validate_final_candidate(raw_assignment, {"schema_version": docs_patch.SCHEMA_VERSION, "snapshot_sha256": envelope["snapshot_sha256"], "artifact": docs_patch.validate_agent_review(final_review)})
