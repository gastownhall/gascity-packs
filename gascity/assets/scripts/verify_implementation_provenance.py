#!/usr/bin/env python3
"""Recompute and verify a build-basic implementation snapshot from live state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


class ProvenanceError(RuntimeError):
    pass


GIT_ENV = {
    key: value
    for key, value in os.environ.items()
    if not key.startswith("GIT_")
}
GIT_ENV["GIT_NO_REPLACE_OBJECTS"] = "1"


def command(
    args: list[str],
    *,
    context: str,
    text: bool = True,
    env: dict[str, str] | None = None,
    input_data: str | bytes | None = None,
) -> str | bytes:
    result = subprocess.run(
        args,
        capture_output=True,
        text=text,
        check=False,
        env=env,
        input=input_data,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() if text else result.stderr.decode(errors="replace").strip()
        suffix = f": {stderr.splitlines()[0]}" if stderr else ""
        raise ProvenanceError(f"{context} failed{suffix}")
    return result.stdout


def json_command(args: list[str], *, context: str) -> Any:
    raw = command(args, context=context)
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError as exc:
        raise ProvenanceError(f"{context} returned invalid JSON: {exc}") from exc


def one_bead(bead_id: str) -> dict[str, Any]:
    value = json_command(["gc", "bd", "show", bead_id, "--json"], context=f"gc bd show {bead_id}")
    if isinstance(value, list):
        value = value[0] if value else {}
    if not isinstance(value, dict) or str(value.get("id") or "") != bead_id:
        raise ProvenanceError(f"gc bd show {bead_id} did not return that bead")
    return value


def metadata(bead: dict[str, Any], key: str) -> str:
    values = bead.get("metadata")
    value = values.get(key, "") if isinstance(values, dict) else ""
    return value.strip() if isinstance(value, str) else ""


def required_absolute_path(bead: dict[str, Any], key: str, *, label: str) -> Path:
    raw = metadata(bead, key)
    if not raw:
        raise ProvenanceError(f"{label} is missing {key}")
    path = Path(raw)
    if not path.is_absolute():
        raise ProvenanceError(f"{label} {key} must be absolute: {raw}")
    try:
        return path.resolve(strict=True)
    except OSError as exc:
        raise ProvenanceError(f"{label} {key} does not resolve: {raw}: {exc}") from exc


def required_regular_path(declared: Path, *, label: str) -> Path:
    if not declared.is_absolute():
        raise ProvenanceError(f"{label} must be absolute: {declared}")
    try:
        mode = declared.lstat().st_mode
    except OSError as exc:
        raise ProvenanceError(f"{label} is unreadable: {declared}: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise ProvenanceError(
            f"{label} must be a regular non-symlink file: {declared}"
        )
    try:
        return declared.resolve(strict=True)
    except OSError as exc:
        raise ProvenanceError(f"{label} does not resolve: {declared}: {exc}") from exc


def required_regular_file(bead: dict[str, Any], key: str, *, label: str) -> Path:
    raw = metadata(bead, key)
    if not raw:
        raise ProvenanceError(f"{label} is missing {key}")
    return required_regular_path(Path(raw), label=f"{label} {key}")


def required_artifact_root(
    bead: dict[str, Any],
    *,
    launcher_top: Path,
    label: str,
) -> Path:
    key = (
        "gc.build.artifact_root"
        if metadata(bead, "gc.build.artifact_root")
        else "gc.var.artifact_root"
    )
    raw = metadata(bead, key)
    if not raw:
        raise ProvenanceError(
            f"{label} is missing gc.build.artifact_root and gc.var.artifact_root"
        )
    declared = Path(raw)
    candidate = declared if declared.is_absolute() else launcher_top / declared
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ProvenanceError(f"{label} {key} does not resolve: {raw}: {exc}") from exc
    if not declared.is_absolute():
        try:
            resolved.relative_to(launcher_top)
        except ValueError as exc:
            raise ProvenanceError(
                f"{label} relative {key} escapes the launcher worktree: {raw}"
            ) from exc
    if not resolved.is_dir():
        raise ProvenanceError(f"{label} {key} must resolve to a directory: {resolved}")
    return resolved


def git_text(repo: Path, *args: str, context: str) -> str:
    return str(
        command(
            ["git", "-C", str(repo), *args],
            context=context,
            env=GIT_ENV,
        )
    ).strip()


def git_top_level(path: Path, *, label: str) -> Path:
    top = Path(git_text(path, "rev-parse", "--show-toplevel", context=f"read {label} Git top-level"))
    try:
        return top.resolve(strict=True)
    except OSError as exc:
        raise ProvenanceError(f"{label} Git top-level does not resolve: {top}: {exc}") from exc


def git_common_dir(top: Path, *, label: str) -> Path:
    raw = Path(git_text(top, "rev-parse", "--git-common-dir", context=f"read {label} Git common-dir"))
    path = raw if raw.is_absolute() else top / raw
    try:
        return path.resolve(strict=True)
    except OSError as exc:
        raise ProvenanceError(f"{label} Git common-dir does not resolve: {raw}: {exc}") from exc


def is_allowed_cache(path: Path, relative: str) -> bool:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    if not stat.S_ISREG(mode):
        return False
    if mode & 0o111 or path.suffix.lower() in {".py", ".pyc", ".pyo", ".so", ".sh"}:
        return False
    parts = Path(relative).parts
    return ".pytest_cache" in parts


def reject_untracked_drift(worktree: Path, allowed_paths: set[Path]) -> None:
    raw = command(
        ["git", "-C", str(worktree), "ls-files", "--others", "-z"],
        context=f"read untracked paths in {worktree}",
        text=False,
        env=GIT_ENV,
    )
    for encoded in bytes(raw).split(b"\0"):
        if not encoded:
            continue
        relative = os.fsdecode(encoded)
        candidate = worktree / relative
        if candidate.resolve(strict=False) in allowed_paths:
            continue
        if is_allowed_cache(candidate, relative):
            continue
        raise ProvenanceError(f"unexpected untracked worktree path in {worktree}: {relative}")

    def walk_error(error: OSError) -> None:
        raise ProvenanceError(f"cannot inspect worktree path: {error.filename}: {error}")

    for directory, names, filenames in os.walk(
        worktree,
        topdown=True,
        onerror=walk_error,
        followlinks=False,
    ):
        current = Path(directory)
        if current == worktree and ".git" in names:
            names.remove(".git")
        for name in [*names, *filenames]:
            candidate = current / name
            try:
                mode = candidate.lstat().st_mode
            except OSError as exc:
                raise ProvenanceError(
                    f"cannot inspect worktree path: {candidate}: {exc}"
                ) from exc
            if stat.S_ISREG(mode) or stat.S_ISDIR(mode):
                continue
            relative = os.fsdecode(os.path.relpath(os.fsencode(candidate), os.fsencode(worktree)))
            tracked = subprocess.run(
                ["git", "-C", str(worktree), "ls-files", "--error-unmatch", "--", relative],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                env=GIT_ENV,
            )
            if tracked.returncode != 0:
                raise ProvenanceError(
                    f"unexpected untracked worktree path in {worktree}: {relative}"
                )


def hash_blob(repo: Path, payload: bytes) -> str:
    value = command(
        ["git", "-C", str(repo), "hash-object", "--stdin"],
        context=f"hash raw worktree bytes in {repo}",
        text=False,
        env=GIT_ENV,
        input_data=payload,
    )
    return bytes(value).decode("ascii").strip()


def verify_raw_tracked_tree(worktree: Path, head: str) -> None:
    replacements = git_text(
        worktree,
        "replace",
        "-l",
        context=f"read Git replacement refs in {worktree}",
    )
    if replacements:
        raise ProvenanceError(f"Git replacement refs are not allowed in {worktree}: {replacements}")

    index_raw = command(
        ["git", "-C", str(worktree), "ls-files", "-v", "-z"],
        context=f"read index flags in {worktree}",
        text=False,
        env=GIT_ENV,
    )
    index_paths: set[bytes] = set()
    for record in bytes(index_raw).split(b"\0"):
        if not record:
            continue
        if len(record) < 3 or record[:2] != b"H ":
            rendered = os.fsdecode(record[2:] if len(record) >= 2 else record)
            tag = os.fsdecode(record[:1]) if record else "<missing>"
            raise ProvenanceError(
                f"tracked path has unsupported index flag in {worktree}: tag={tag} path={rendered}"
            )
        index_paths.add(record[2:])

    stage_raw = command(
        ["git", "-C", str(worktree), "ls-files", "--stage", "-z"],
        context=f"read staged index entries in {worktree}",
        text=False,
        env=GIT_ENV,
    )
    index_entries: dict[bytes, tuple[str, str]] = {}
    for record in bytes(stage_raw).split(b"\0"):
        if not record:
            continue
        header, separator, encoded_path = record.partition(b"\t")
        fields = header.split()
        if not separator or len(fields) != 3:
            raise ProvenanceError(f"Git index contains a malformed entry in {worktree}")
        mode, object_id, stage = (field.decode("ascii") for field in fields)
        if stage != "0" or encoded_path in index_entries:
            relative = os.fsdecode(encoded_path)
            raise ProvenanceError(
                f"Git index contains an unsupported staged entry in {worktree}: "
                f"stage={stage} path={relative}"
            )
        index_entries[encoded_path] = (mode, object_id)

    tree_raw = command(
        ["git", "-C", str(worktree), "ls-tree", "-r", "-z", "--full-tree", head],
        context=f"read committed tree {head} in {worktree}",
        text=False,
        env=GIT_ENV,
    )
    tree_paths: set[bytes] = set()
    tree_entries: dict[bytes, tuple[str, str]] = {}
    for record in bytes(tree_raw).split(b"\0"):
        if not record:
            continue
        header, separator, encoded_path = record.partition(b"\t")
        fields = header.split()
        if not separator or len(fields) != 3:
            raise ProvenanceError(f"committed tree {head} contains a malformed entry")
        mode, object_type, expected_object = (field.decode("ascii") for field in fields)
        tree_paths.add(encoded_path)
        tree_entries[encoded_path] = (mode, expected_object)
        relative = os.fsdecode(encoded_path)
        candidate = worktree / relative
        try:
            current_mode = candidate.lstat().st_mode
        except OSError as exc:
            raise ProvenanceError(f"tracked path is unreadable in {worktree}: {relative}: {exc}") from exc

        if mode in {"100644", "100755"} and object_type == "blob":
            if not stat.S_ISREG(current_mode):
                raise ProvenanceError(f"tracked regular file changed type in {worktree}: {relative}")
            expected_executable = mode == "100755"
            current_executable = bool(current_mode & 0o111)
            if current_executable != expected_executable:
                raise ProvenanceError(f"tracked file mode differs from commit in {worktree}: {relative}")
            try:
                payload = candidate.read_bytes()
            except OSError as exc:
                raise ProvenanceError(f"tracked file bytes are unreadable in {worktree}: {relative}: {exc}") from exc
        elif mode == "120000" and object_type == "blob":
            if not stat.S_ISLNK(current_mode):
                raise ProvenanceError(f"tracked symlink changed type in {worktree}: {relative}")
            payload = os.fsencode(os.readlink(candidate))
        elif mode == "160000" and object_type == "commit":
            raise ProvenanceError(
                f"tracked submodules are unsupported by exact-byte provenance verification: {relative}"
            )
        else:
            raise ProvenanceError(
                f"unsupported committed tree entry in {worktree}: mode={mode} type={object_type} path={relative}"
            )
        observed_object = hash_blob(worktree, payload)
        if observed_object != expected_object:
            raise ProvenanceError(
                f"tracked raw bytes differ from commit in {worktree}: {relative}"
            )

    if index_paths != tree_paths:
        missing = sorted(os.fsdecode(path) for path in tree_paths - index_paths)
        extra = sorted(os.fsdecode(path) for path in index_paths - tree_paths)
        raise ProvenanceError(
            f"Git index paths differ from committed tree in {worktree}: missing={missing} extra={extra}"
        )
    if set(index_entries) != tree_paths:
        raise ProvenanceError(f"Git staged index paths differ from committed tree in {worktree}")
    for encoded_path in sorted(tree_paths):
        if index_entries[encoded_path] != tree_entries[encoded_path]:
            relative = os.fsdecode(encoded_path)
            raise ProvenanceError(
                f"Git index entry differs from commit in {worktree}: {relative}"
            )


def artifact_front_matter(path: Path, *, label: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        raise ProvenanceError(f"{label} has no parseable YAML front matter: {path}")
    try:
        value = yaml.safe_load(match.group("front")) or {}
    except yaml.YAMLError as exc:
        raise ProvenanceError(f"{label} has invalid YAML front matter: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProvenanceError(f"{label} front matter must be a mapping: {path}")
    return value


def validate_summary(
    path: Path,
    *,
    validator: Path,
    roots: list[Path],
    label: str,
    verify_upstreams: bool,
) -> dict[str, Any]:
    args = [
        sys.executable,
        str(validator),
        "--schema",
        "gc.build.implementation-summary.v1",
        "--path",
        str(path),
    ]
    if verify_upstreams:
        args.append("--verify-absolute-upstreams")
        for root in roots:
            args.extend(("--upstream-root", str(root)))
    command(args, context=f"validate {label}")
    front_matter = artifact_front_matter(path, label=label)
    if front_matter.get("status") != "approved":
        raise ProvenanceError(f"{label} must have status=approved: {path}")
    return front_matter


def upstream_entries(front_matter: dict[str, Any], *, label: str) -> list[dict[str, Any]]:
    trace = front_matter.get("trace")
    upstream = trace.get("upstream") if isinstance(trace, dict) else None
    if not isinstance(upstream, list) or any(not isinstance(entry, dict) for entry in upstream):
        raise ProvenanceError(f"{label} trace.upstream must be an array of mappings")
    return upstream


def require_member_source_trace(
    front_matter: dict[str, Any],
    *,
    member_id: str,
    label: str,
) -> None:
    expected_path = f"beads/{member_id}"
    expected_hash = f"bead:{member_id}"
    matches = [
        entry
        for entry in upstream_entries(front_matter, label=label)
        if entry.get("path") == expected_path or entry.get("hash") == expected_hash
    ]
    if len(matches) != 1 or matches[0].get("path") != expected_path or matches[0].get("hash") != expected_hash:
        raise ProvenanceError(
            f"{label} must trace source member {member_id} exactly once"
        )


def require_build_basic_summary_identity(
    front_matter: dict[str, Any],
    *,
    root_id: str,
    label: str,
) -> None:
    expected = {
        "workflow.id": root_id,
        "workflow.formula": "build-basic",
        "methodology.pack": "gascity",
        "methodology.name": "build-basic",
        "producer.formula": "build-basic",
        "producer.stage": "summarize-implementation",
    }
    for dotted, expected_value in expected.items():
        current: Any = front_matter
        for part in dotted.split("."):
            current = current.get(part) if isinstance(current, dict) else None
        if current != expected_value:
            raise ProvenanceError(
                f"{label} {dotted} must be {expected_value!r}, got {current!r}"
            )


def require_exact_summary_traces(
    front_matter: dict[str, Any],
    *,
    summaries: list[Path],
    label: str,
) -> None:
    entries = upstream_entries(front_matter, label=label)
    for summary in summaries:
        expected_hash = f"sha256:{hashlib.sha256(summary.read_bytes()).hexdigest()}"
        expected_path = str(summary)
        observed: list[str] = []
        for entry in entries:
            raw_path = entry.get("path")
            if raw_path == expected_path:
                observed.append(str(entry.get("hash") or ""))
        if observed != [expected_hash]:
            raise ProvenanceError(
                f"{label} must trace current member summary exactly once: "
                f"summary={summary} expected={expected_hash} observed={observed}"
            )


def sha256_uri(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def review_input_snapshot(
    *,
    implementation_snapshot: str,
    summary: Path,
    context: Path,
) -> str:
    value = {
        "context": {"path": str(context), "sha256": sha256_uri(context)},
        "implementation_snapshot": implementation_snapshot,
        "summary": {"path": str(summary), "sha256": sha256_uri(summary)},
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def implementation_snapshot(members: list[dict[str, str]]) -> str:
    canonical = [
        {"id": str(member["id"]), "commit": str(member["commit"])}
        for member in members
    ]
    canonical.sort(key=lambda member: member["id"])
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def convoy_member_ids(root: dict[str, Any]) -> list[str]:
    convoy_id = metadata(root, "gc.build.implementation_convoy_id")
    if not convoy_id:
        raise ProvenanceError("workflow root is missing gc.build.implementation_convoy_id")
    value = json_command(
        ["gc", "convoy", "status", convoy_id, "--json"],
        context=f"gc convoy status {convoy_id}",
    )
    if not isinstance(value, dict):
        raise ProvenanceError(f"implementation convoy {convoy_id} did not return an object")
    convoy = value.get("convoy")
    children = value.get("children")
    if (
        not isinstance(convoy, dict)
        or str(convoy.get("id") or "") != convoy_id
        or str(convoy.get("status") or "") != "closed"
        or not isinstance(children, list)
        or not children
    ):
        raise ProvenanceError(
            f"implementation convoy {convoy_id} must be closed with non-empty children"
        )
    member_ids: list[str] = []
    for child in children:
        member_id = str(child.get("id") or "").strip() if isinstance(child, dict) else ""
        status_value = str(child.get("status") or "") if isinstance(child, dict) else ""
        if not member_id or status_value != "closed":
            raise ProvenanceError(
                f"implementation convoy {convoy_id} contains a missing or non-closed child"
            )
        member_ids.append(member_id)
    if len(member_ids) != len(set(member_ids)):
        raise ProvenanceError(f"implementation convoy {convoy_id} child ids must be unique")
    return member_ids


def verify(
    root_id: str,
    expected_snapshot: str | None,
    expected_summary: Path,
    validator: Path,
    expected_artifacts: list[Path],
    *,
    enforce_recorded_snapshots: bool = True,
) -> tuple[str, str, list[dict[str, str]]]:
    root = one_bead(root_id)
    launcher_work_dir = required_absolute_path(root, "gc.work_dir", label="workflow root")
    launcher_top = git_top_level(launcher_work_dir, label="launcher")
    launcher_common = git_common_dir(launcher_top, label="launcher")

    recorded_summary = required_regular_file(
        root, "gc.build.implementation_summary_path", label="workflow root"
    )
    if recorded_summary != expected_summary.resolve(strict=True):
        raise ProvenanceError(
            "workflow root implementation summary disagrees with the artifact gate: "
            f"recorded={recorded_summary} expected={expected_summary}"
        )
    artifact_root = required_artifact_root(
        root,
        launcher_top=launcher_top,
        label="workflow root",
    )
    expected_summary = artifact_root / "implementation-summary.md"
    if recorded_summary != expected_summary:
        raise ProvenanceError(
            "canonical implementation summary must use the workflow artifact root filename: "
            f"summary={recorded_summary} expected={expected_summary}"
        )
    for expected_artifact in expected_artifacts:
        resolved_artifact = required_regular_path(
            expected_artifact,
            label="expected build artifact",
        )
        try:
            resolved_artifact.relative_to(artifact_root)
        except ValueError as exc:
            raise ProvenanceError(
                "expected build artifact must be under the workflow artifact root: "
                f"artifact={resolved_artifact} root={artifact_root}"
            ) from exc
    try:
        recorded_summary.relative_to(artifact_root)
    except ValueError as exc:
        raise ProvenanceError(
            "canonical implementation summary must be under the workflow artifact root: "
            f"summary={recorded_summary} root={artifact_root}"
        ) from exc
    recorded_context = required_regular_file(
        root, "gc.build.code_review_context_path", label="workflow root"
    )
    expected_context = artifact_root / "review-context.md"
    if recorded_context != expected_context:
        raise ProvenanceError(
            "canonical review context must use the workflow artifact root filename: "
            f"context={recorded_context} expected={expected_context}"
        )
    try:
        recorded_context.relative_to(artifact_root)
    except ValueError as exc:
        raise ProvenanceError(
            "review context must be under the workflow artifact root: "
            f"context={recorded_context} root={artifact_root}"
        ) from exc
    summary_identity = (recorded_summary.stat().st_dev, recorded_summary.stat().st_ino)
    context_identity = (recorded_context.stat().st_dev, recorded_context.stat().st_ino)
    if context_identity == summary_identity:
        raise ProvenanceError(
            "review context must be distinct from the canonical implementation summary"
        )
    drain_policy = metadata(root, "gc.var.drain_policy")
    shared_worktree: Path | None = None
    shared_head = ""
    found_terminal = False
    snapshot_members: list[dict[str, str]] = []
    checked_worktrees: dict[Path, set[Path]] = {}
    summary_file_ids = {summary_identity, context_identity}
    member_summaries: list[Path] = []

    for member_id in convoy_member_ids(root):
        member = one_bead(member_id)
        if str(member.get("status") or "") != "closed" or metadata(member, "gc.outcome") != "pass":
            raise ProvenanceError(f"implementation member {member_id} must be closed/pass")
        worktree = required_absolute_path(member, "work_dir", label=f"member {member_id}")
        explicit = required_absolute_path(
            member, "gc.implementation.worktree_path", label=f"member {member_id}"
        )
        top = git_top_level(worktree, label=f"member {member_id}")
        if worktree != top or explicit != top:
            raise ProvenanceError(
                f"member {member_id} work_dir and gc.implementation.worktree_path must equal Git top-level"
            )
        common = git_common_dir(top, label=f"member {member_id}")
        if common != launcher_common:
            raise ProvenanceError(
                f"member {member_id} Git common-dir does not match launcher repository"
            )

        recorded_commit = metadata(member, "gc.implementation.commit")
        if re.fullmatch(r"[0-9a-fA-F]{40}", recorded_commit) is None:
            raise ProvenanceError(
                f"member {member_id} gc.implementation.commit must be a full hexadecimal commit"
            )
        resolved_commit = git_text(
            top,
            "rev-parse",
            "--verify",
            f"{recorded_commit}^{{commit}}",
            context=f"resolve member {member_id} commit",
        )
        head = git_text(top, "rev-parse", "HEAD", context=f"read member {member_id} HEAD")

        if drain_policy == "same-session":
            if shared_worktree is None:
                shared_worktree, shared_head = top, head
            elif top != shared_worktree or head != shared_head:
                raise ProvenanceError(
                    "same-session members must share one canonical worktree and terminal HEAD"
                )
            ancestor = subprocess.run(
                ["git", "-C", str(top), "merge-base", "--is-ancestor", resolved_commit, head],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                env=GIT_ENV,
            )
            if ancestor.returncode != 0:
                raise ProvenanceError(
                    f"member {member_id} commit is not an ancestor of shared terminal HEAD"
                )
            found_terminal = found_terminal or resolved_commit == head
        elif resolved_commit != head:
            raise ProvenanceError(
                f"member {member_id} recorded commit does not equal current worktree HEAD"
            )

        member_summary = required_regular_file(
            member, "gc.implementation.summary_path", label=f"member {member_id}"
        )
        if member_summary == recorded_summary:
            raise ProvenanceError(
                f"member {member_id} summary must be distinct from the canonical implementation summary"
            )
        summary_file_id = (member_summary.stat().st_dev, member_summary.stat().st_ino)
        if summary_file_id in summary_file_ids:
            raise ProvenanceError(
                f"member {member_id} summary aliases another implementation summary"
            )
        summary_file_ids.add(summary_file_id)
        try:
            member_summary.relative_to(top)
        except ValueError as exc:
            raise ProvenanceError(f"member {member_id} summary must be inside its worktree") from exc
        allowed = checked_worktrees.setdefault(top, set())
        allowed.add(member_summary)
        try:
            recorded_summary.relative_to(top)
        except ValueError:
            pass
        else:
            allowed.add(recorded_summary)
        try:
            recorded_context.relative_to(top)
        except ValueError:
            pass
        else:
            allowed.add(recorded_context)
        member_front_matter = validate_summary(
            member_summary,
            validator=validator,
            roots=[top],
            label=f"member {member_id} implementation summary",
            verify_upstreams=False,
        )
        require_member_source_trace(
            member_front_matter,
            member_id=member_id,
            label=f"member {member_id} implementation summary",
        )
        member_summaries.append(member_summary)
        snapshot_members.append({"id": member_id, "commit": resolved_commit})

    if drain_policy == "same-session" and not found_terminal:
        raise ProvenanceError("same-session members do not bind the terminal shared worktree HEAD")

    for worktree, allowed_paths in checked_worktrees.items():
        verify_raw_tracked_tree(worktree, git_text(worktree, "rev-parse", "HEAD", context=f"read {worktree} HEAD"))
        reject_untracked_drift(worktree, allowed_paths)

    canonical_front_matter = validate_summary(
        recorded_summary,
        validator=validator,
        roots=[launcher_top, *checked_worktrees],
        label="canonical implementation summary",
        verify_upstreams=True,
    )
    require_build_basic_summary_identity(
        canonical_front_matter,
        root_id=root_id,
        label="canonical implementation summary",
    )
    require_exact_summary_traces(
        canonical_front_matter,
        summaries=member_summaries,
        label="canonical implementation summary",
    )

    snapshot_members.sort(key=lambda item: item["id"])
    current_snapshot = implementation_snapshot(snapshot_members)
    root_snapshot = metadata(root, "gc.build.implementation_snapshot")
    if enforce_recorded_snapshots and (
        root_snapshot != current_snapshot or expected_snapshot != current_snapshot
    ):
        raise ProvenanceError(
            "implementation snapshot mismatch: "
            f"root={root_snapshot or '<missing>'} expected={expected_snapshot or '<missing>'} "
            f"current={current_snapshot}"
        )
    current_review_input = review_input_snapshot(
        implementation_snapshot=current_snapshot,
        summary=recorded_summary,
        context=recorded_context,
    )
    root_review_input = metadata(root, "gc.build.review_input_snapshot")
    if enforce_recorded_snapshots and root_review_input != current_review_input:
        raise ProvenanceError(
            "review input snapshot mismatch: "
            f"root={root_review_input or '<missing>'} current={current_review_input}"
        )
    return current_snapshot, current_review_input, snapshot_members


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-id", required=True)
    parser.add_argument("--expected-snapshot")
    parser.add_argument(
        "--emit-current",
        action="store_true",
        help="emit deterministically computed live snapshots without comparing root snapshot metadata",
    )
    parser.add_argument("--expected-summary", required=True, type=Path)
    parser.add_argument(
        "--expected-artifact",
        action="append",
        default=[],
        type=Path,
    )
    parser.add_argument("--validator", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.emit_current and not args.expected_snapshot:
        parser.error("--expected-snapshot is required unless --emit-current is used")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        snapshot, review_input, members = verify(
            args.root_id,
            args.expected_snapshot,
            args.expected_summary,
            args.validator.resolve(strict=True),
            args.expected_artifact,
            enforce_recorded_snapshots=not args.emit_current,
        )
    except (OSError, ProvenanceError) as exc:
        print(f"implementation-provenance-check: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "implementation_snapshot": snapshot,
                "members": members,
                "ok": True,
                "review_input_snapshot": review_input,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
