#!/usr/bin/env bash
set -euo pipefail

# Build requirements provenance gate.
#
# The shared artifact check proves schema validity. This wrapper additionally
# proves that requirements trace every direct member of the immutable launch
# convoy exactly once, preventing a workflow from replacing its requested
# product scope with inferred or invented work. The internal
# superpowers-planning methodology has no launch convoy; it may instead use its
# explicitly supplied context file as the source of truth.

fail() {
  echo "build-requirements-source-check: $*" >&2
  exit 1
}

BEAD_ID="${GC_BEAD_ID:-}"
[ -n "$BEAD_ID" ] || fail "GC_BEAD_ID is required"
command -v gc >/dev/null 2>&1 || fail "gc is required on PATH"
command -v python3 >/dev/null 2>&1 || fail "python3 is required on PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
BASE_CHECK="$SCRIPT_DIR/build-artifact-valid.sh"
[ -x "$BASE_CHECK" ] || fail "shared build-artifact-valid.sh is missing or not executable: $BASE_CHECK"

"$BASE_CHECK"

python3 - "$BEAD_ID" <<'PY'
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


BEAD_ID = sys.argv[1]


def fail(message: str) -> None:
    print(f"build-requirements-source-check: {message}", file=sys.stderr)
    raise SystemExit(1)


def json_command(args: list[str], *, label: str) -> Any:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        suffix = f": {detail[0]}" if detail else ""
        fail(f"{label} failed{suffix}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"{label} returned invalid JSON: {exc}")


def bead(bead_id: str) -> dict[str, Any]:
    data = json_command(
        ["gc", "bd", "show", bead_id, "--json"],
        label=f"gc bd show {bead_id}",
    )
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict) or str(data.get("id") or "") != bead_id:
        fail(f"gc bd show {bead_id} did not return that bead")
    return data


def metadata(item: dict[str, Any], key: str) -> str:
    values = item.get("metadata")
    value = values.get(key, "") if isinstance(values, dict) else ""
    return value.strip() if isinstance(value, str) else ""


def requirements_upstream(
    root: dict[str, Any], root_id: str, work_dir: Path
) -> tuple[Path, list[Any]]:
    raw_requirements_path = metadata(root, "gc.build.requirements_path") or metadata(
        root, "gc.var.requirements_path"
    )
    if not raw_requirements_path:
        fail(f"workflow root {root_id} is missing gc.build.requirements_path")
    requirements_path = Path(raw_requirements_path)
    if not requirements_path.is_absolute():
        requirements_path = work_dir / requirements_path
    try:
        requirements_path = requirements_path.resolve(strict=True)
    except OSError as exc:
        fail(f"requirements path does not resolve: {raw_requirements_path}: {exc}")
    if not requirements_path.is_file():
        fail(f"requirements path is not a regular file: {requirements_path}")

    text = requirements_path.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        fail(f"requirements artifact has no parseable YAML front matter: {requirements_path}")
    try:
        front = yaml.safe_load(match.group("front")) or {}
    except yaml.YAMLError as exc:
        fail(f"requirements artifact has invalid YAML front matter: {exc}")
    trace = front.get("trace") if isinstance(front, dict) else None
    upstream = trace.get("upstream") if isinstance(trace, dict) else None
    if not isinstance(upstream, list):
        fail(f"requirements trace.upstream is missing: {requirements_path}")
    return requirements_path, upstream


step = bead(BEAD_ID)
root_id = metadata(step, "gc.root_bead_id") or BEAD_ID
root = bead(root_id) if root_id != BEAD_ID else step
work_dir = Path(metadata(root, "gc.work_dir") or Path.cwd())

launch_convoy_id = metadata(root, "gc.var.convoy_id")
if not launch_convoy_id:
    formula_name = metadata(root, "gc.formula_name")
    if formula_name != "superpowers-planning":
        fail(f"workflow root {root_id} is missing reserved launch convoy metadata gc.var.convoy_id")

    raw_context_path = metadata(root, "gc.var.context_path")
    if not raw_context_path:
        fail(
            f"internal planning context is missing on workflow root {root_id}: "
            "gc.var.context_path is required"
        )
    context_path = Path(raw_context_path)
    if not context_path.is_absolute():
        context_path = work_dir / context_path
    try:
        context_path = context_path.resolve(strict=True)
    except OSError as exc:
        fail(f"internal planning context path does not resolve: {raw_context_path}: {exc}")
    if not context_path.is_file():
        fail(f"internal planning context path is not a regular file: {context_path}")

    requirements_path, upstream = requirements_upstream(root, root_id, work_dir)
    expected_path = str(context_path)
    expected_hash = f"sha256:{hashlib.sha256(context_path.read_bytes()).hexdigest()}"
    identity_entries = [
        entry
        for entry in upstream
        if isinstance(entry, dict)
        and (entry.get("path") == expected_path or entry.get("hash") == expected_hash)
    ]
    if not identity_entries:
        fail(
            "missing internal planning context trace in requirements: "
            f"path={expected_path} hash={expected_hash}"
        )
    if len(identity_entries) != 1:
        fail(
            "duplicate internal planning context trace in requirements: "
            f"path={expected_path} matches={len(identity_entries)}"
        )
    identity = identity_entries[0]
    if (identity.get("path"), identity.get("hash")) != (expected_path, expected_hash):
        fail(
            "mismatched internal planning context trace in requirements: "
            f"expected=({expected_path}, {expected_hash}) "
            f"observed=({identity.get('path')}, {identity.get('hash')})"
        )
    if len(upstream) != 1:
        fail(
            "unexpected internal planning source trace in requirements: "
            f"expected_only=({expected_path}, {expected_hash}) "
            f"observed_entries={len(upstream)}"
        )

    print(
        "build requirements source valid: internal planning context "
        f"path={context_path} requirements={requirements_path}"
    )
    raise SystemExit(0)

status = json_command(
    ["gc", "convoy", "status", launch_convoy_id, "--json"],
    label=f"gc convoy status {launch_convoy_id}",
)
if not isinstance(status, dict):
    fail(f"gc convoy status {launch_convoy_id} did not return an object")
convoy = status.get("convoy")
if not isinstance(convoy, dict) or str(convoy.get("id") or "") != launch_convoy_id:
    fail(f"gc convoy status {launch_convoy_id} returned a different convoy")
children = status.get("children")
if not isinstance(children, list) or any(not isinstance(row, dict) for row in children):
    fail(f"gc convoy status {launch_convoy_id} omitted valid children")
source_ids = [str(row.get("id") or "").strip() for row in children]
if not source_ids or any(not source_id for source_id in source_ids):
    fail(f"launch convoy {launch_convoy_id} has no valid source targets")
if len(source_ids) != len(set(source_ids)):
    fail(f"launch convoy {launch_convoy_id} contains duplicate source targets: {source_ids}")
for source_id in source_ids:
    bead(source_id)

requirements_path, upstream = requirements_upstream(root, root_id, work_dir)

observed_source_traces: list[str] = []
malformed_source_traces: list[dict[str, Any]] = []
for entry in upstream:
    if not isinstance(entry, dict):
        continue
    raw_path = str(entry.get("path") or "").strip()
    raw_hash = str(entry.get("hash") or "").strip()
    has_bead_path = raw_path.startswith("beads/")
    has_bead_hash = raw_hash.lower().startswith("bead:")
    if not has_bead_path and not has_bead_hash:
        continue

    source_id = raw_path[len("beads/") :] if has_bead_path else ""
    if (
        not has_bead_path
        or not has_bead_hash
        or not source_id
        or raw_hash != f"bead:{source_id}"
    ):
        malformed_source_traces.append({"path": raw_path, "hash": raw_hash})
        continue
    observed_source_traces.append(source_id)
if malformed_source_traces:
    fail(
        "malformed launch source trace in requirements: "
        f"launch_convoy={launch_convoy_id} observed={malformed_source_traces}"
    )
missing = [source_id for source_id in source_ids if source_id not in observed_source_traces]
if missing:
    fail(
        "missing launch source trace in requirements: "
        f"launch_convoy={launch_convoy_id} missing={missing} "
        f"observed={sorted(observed_source_traces)}"
    )
duplicates = sorted(
    source_id for source_id in source_ids if observed_source_traces.count(source_id) != 1
)
if duplicates:
    fail(
        "duplicate launch source trace in requirements: "
        f"launch_convoy={launch_convoy_id} duplicates={duplicates}"
    )
unexpected = sorted(
    source_id for source_id in set(observed_source_traces) if source_id not in source_ids
)
if unexpected:
    fail(
        "unexpected launch source trace in requirements: "
        f"launch_convoy={launch_convoy_id} unexpected={unexpected} "
        f"expected={sorted(source_ids)}"
    )

print(
    "build requirements source valid: "
    f"launch_convoy={launch_convoy_id} sources={','.join(source_ids)} "
    f"path={requirements_path}"
)
PY
