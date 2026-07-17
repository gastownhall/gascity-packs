#!/usr/bin/env bash
set -euo pipefail

# Generic producer-stage build-artifact validation gate.
#
# The checked formula step names its artifact contract in step metadata:
#   gc.build.artifact_schema    - expected schema id (e.g. gc.build.requirements.v1)
#   gc.build.artifact_path_keys - comma-separated workflow-root metadata keys;
#                                 the first non-empty value is the artifact path
#
# The step bead (and the ralph control bead cloned from it) carries that
# metadata, so this script reads $GC_BEAD_ID, resolves the workflow root via
# gc.root_bead_id, resolves the artifact path, and validates the artifact with
# the shared base validator. All failures print machine-readable lines on
# stderr; the dispatcher records them in gc.attempt_log as repair context for
# the next bounded producer attempt. This gate never prompts.

fail() {
  echo "build-artifact-check: $*" >&2
  exit 1
}

BEAD_ID="${GC_BEAD_ID:-}"
[ -n "$BEAD_ID" ] || fail "GC_BEAD_ID is required"
command -v gc >/dev/null 2>&1 || fail "gc is required on PATH"
command -v python3 >/dev/null 2>&1 || fail "python3 is required on PATH"

metadata_value() {
  # metadata_value <json> <key> -> prints metadata[key] or empty
  printf '%s' "$1" | python3 -c '
import json
import sys

key = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
if isinstance(data, list):
    data = data[0] if data else {}
if not isinstance(data, dict):
    print("")
    raise SystemExit(0)
metadata = data.get("metadata") or {}
value = metadata.get(key, "") if isinstance(metadata, dict) else ""
if isinstance(value, bool):
    print("true" if value else "false")
elif isinstance(value, (str, int)):
    print(value)
else:
    print("")
' "$2"
}

launcher_root_from_work_dir() {
  candidate="${GC_WORK_DIR:-}"
  [ -n "$candidate" ] || return 1
  candidate="$(cd "$candidate" 2>/dev/null && pwd -P)" || return 1

  while :; do
    if [ -f "$candidate/.gc/scripts/checks/build-artifact-valid.sh" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
    [ "$candidate" != "/" ] || return 1
    parent="$(dirname "$candidate")"
    [ "$parent" != "$candidate" ] || return 1
    candidate="$parent"
  done
}

resolve_declared_path() {
  value="$1"
  key="$2"
  case "$value" in
    /*) printf '%s\n' "$value" ;;
    *)
      [ -n "${GC_WORK_DIR:-}" ] || fail "artifact path $value from $key is relative and GC_WORK_DIR is unset"
      launcher_root="$(launcher_root_from_work_dir)" || fail "artifact path $value from $key is relative but no launcher root containing .gc/scripts/checks/build-artifact-valid.sh exists at or above GC_WORK_DIR=$GC_WORK_DIR"
      printf '%s/%s\n' "$launcher_root" "$value"
      ;;
  esac
}

canonical_file_path() {
  python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve(strict=True))' "$1"
}

file_fingerprint() {
  python3 - "$1" <<'PY'
import hashlib
import json
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1])
before = path.lstat()
if not stat.S_ISREG(before.st_mode):
    raise SystemExit(f"not a regular non-symlink file: {path}")

digest = hashlib.sha256()
with path.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)

after = path.lstat()
fields = lambda value: (
    value.st_dev,
    value.st_ino,
    value.st_mode,
    value.st_nlink,
    value.st_size,
    value.st_mtime_ns,
    value.st_ctime_ns,
)
if fields(before) != fields(after) or not stat.S_ISREG(after.st_mode):
    raise SystemExit(f"file changed while fingerprinting: {path}")

print(json.dumps([*fields(after), digest.hexdigest()], separators=(",", ":")))
PY
}

PINNED_PATHS=()
PINNED_FINGERPRINTS=()

pin_file() {
  local path fingerprint
  path="$1"
  fingerprint="$(file_fingerprint "$path")" || fail "could not fingerprint file: $path"
  PINNED_PATHS+=("$path")
  PINNED_FINGERPRINTS+=("$fingerprint")
}

verify_pinned_files() {
  local index path observed
  for index in "${!PINNED_PATHS[@]}"; do
    path="${PINNED_PATHS[$index]}"
    observed="$(file_fingerprint "$path")" || fail "could not re-read pinned file: $path"
    if [ "$observed" != "${PINNED_FINGERPRINTS[$index]}" ]; then
      fail "file changed during validation: $path"
    fi
  done
}

git_worktree_root_for_file() {
  local file_path file_dir git_root
  file_path="$(canonical_file_path "$1")" || return 1
  file_dir="$(dirname "$file_path")"
  git_root="$(git -C "$file_dir" rev-parse --show-toplevel 2>/dev/null)" || return 1
  git_root="$(cd "$git_root" 2>/dev/null && pwd -P)" || return 1

  if [ "$git_root" != "/" ]; then
    case "$file_path" in
      "$git_root"/*) ;;
      *) return 1 ;;
    esac
  fi
  printf '%s\n' "$git_root"
}

require_subject_trace() {
  report_path="$1"
  subject_path="$2"
  python3 - "$report_path" "$subject_path" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

import yaml

report_path = Path(sys.argv[1])
subject_path = Path(sys.argv[2]).resolve()
text = report_path.read_text(encoding="utf-8", errors="replace")
match = re.match(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)", text, re.DOTALL)
if not match:
    print(f"build-artifact-check: review report has no parseable front matter: {report_path}", file=sys.stderr)
    raise SystemExit(1)

front_matter = yaml.safe_load(match.group("front")) or {}
trace = front_matter.get("trace") if isinstance(front_matter, dict) else None
upstream = trace.get("upstream") if isinstance(trace, dict) else None
if not isinstance(upstream, list):
    print(f"build-artifact-check: review report trace.upstream is missing: {report_path}", file=sys.stderr)
    raise SystemExit(1)

expected_hash = f"sha256:{hashlib.sha256(subject_path.read_bytes()).hexdigest()}"
observed = []
for entry in upstream:
    if not isinstance(entry, dict):
        continue
    raw_path = entry.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        continue
    traced_path = Path(raw_path.strip())
    path_matches = traced_path.is_absolute() and traced_path.resolve() == subject_path
    if path_matches:
        observed.append(str(entry.get("hash") or ""))

if expected_hash not in observed:
    print(
        "build-artifact-check: review report must trace the canonical review subject digest exactly: "
        f"report={report_path} subject={subject_path} expected={expected_hash} observed={observed}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
}

require_review_adapter_fidelity() {
  internal_path="$1"
  adapter_path="$2"
  expected_internal_stage="$3"
  expected_adapter_stage="$4"
  expected_adapter_attempt="$5"
  implementation_summary_path="$6"
  python3 - \
    "$internal_path" "$adapter_path" \
    "$expected_internal_stage" "$expected_adapter_stage" \
    "$expected_adapter_attempt" "$implementation_summary_path" <<'PY'
import copy
import hashlib
import re
import sys
from pathlib import Path

import yaml


def fail(message: str) -> None:
    print(f"build-artifact-check: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_report(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        fail(f"review report has no parseable front matter: {path}")
    front = yaml.safe_load(match.group("front")) or {}
    if not isinstance(front, dict):
        fail(f"review report front matter must be a mapping: {path}")
    return front, text[match.end():]


def producer_stage(front: dict) -> str:
    producer = front.get("producer")
    if not isinstance(producer, dict):
        return ""
    stage = producer.get("stage")
    return stage.strip() if isinstance(stage, str) else ""


def without_adapter_provenance(front: dict) -> dict:
    normalized = copy.deepcopy(front)
    producer = normalized.get("producer")
    if isinstance(producer, dict):
        producer.pop("stage", None)
        producer.pop("attempt", None)
    trace = normalized.get("trace")
    if isinstance(trace, dict):
        trace.pop("upstream", None)
    return normalized


internal_path = Path(sys.argv[1])
adapter_path = Path(sys.argv[2])
expected_internal_stage = sys.argv[3]
expected_adapter_stage = sys.argv[4]
expected_adapter_attempt = sys.argv[5]
implementation_summary_path = Path(sys.argv[6]).resolve(strict=True)
internal_front, internal_body = parse_report(internal_path)
adapter_front, adapter_body = parse_report(adapter_path)

observed_internal_stage = producer_stage(internal_front)
observed_adapter_stage = producer_stage(adapter_front)
if observed_internal_stage != expected_internal_stage:
    fail(
        "internal review report producer.stage mismatch: "
        f"expected={expected_internal_stage!r} observed={observed_internal_stage!r} "
        f"path={internal_path}"
    )
if observed_adapter_stage != expected_adapter_stage:
    fail(
        "adapter review report producer.stage mismatch: "
        f"expected={expected_adapter_stage!r} observed={observed_adapter_stage!r} "
        f"path={adapter_path}"
    )
adapter_producer = adapter_front.get("producer")
observed_adapter_attempt = (
    str(adapter_producer.get("attempt") or "")
    if isinstance(adapter_producer, dict)
    else ""
)
if observed_adapter_attempt != expected_adapter_attempt:
    fail(
        "adapter review report producer.attempt mismatch: "
        f"expected producer.attempt={expected_adapter_attempt} "
        f"observed={observed_adapter_attempt or '<missing>'} path={adapter_path}"
    )

adapter_trace = adapter_front.get("trace")
adapter_upstream = (
    adapter_trace.get("upstream") if isinstance(adapter_trace, dict) else None
)
expected_summary_hash = (
    f"sha256:{hashlib.sha256(implementation_summary_path.read_bytes()).hexdigest()}"
)
if not isinstance(adapter_upstream, list) or len(adapter_upstream) != 1:
    fail(
        "adapter review report must trace exactly one current implementation summary: "
        f"expected={implementation_summary_path} path={adapter_path}"
    )
summary_entry = adapter_upstream[0]
raw_summary_path = summary_entry.get("path") if isinstance(summary_entry, dict) else None
raw_summary_hash = summary_entry.get("hash") if isinstance(summary_entry, dict) else None
if (
    raw_summary_path != str(implementation_summary_path)
    or raw_summary_hash != expected_summary_hash
):
    fail(
        "adapter review report must trace the exact current implementation summary: "
        f"expected_path={implementation_summary_path} "
        f"expected_hash={expected_summary_hash} observed_path={raw_summary_path!r} "
        f"observed_hash={raw_summary_hash!r} adapter={adapter_path}"
    )

if (
    without_adapter_provenance(internal_front)
    != without_adapter_provenance(adapter_front)
    or internal_body != adapter_body
):
    fail(
        "internal and adapter review reports must preserve identical semantic content "
        "while allowing only adapter lifecycle provenance to differ: "
        f"internal={internal_path} adapter={adapter_path}"
    )
PY
}

require_implementation_provenance() {
  artifact_path="$1"
  expected_snapshot="$2"
  expected_review_input="$3"
  expected_reviewed_attempt="$4"
  artifact_kind="$5"
  workflow_root_id="$6"
  expected_status="$7"
  shift 7
  python3 - "$artifact_path" "$expected_snapshot" "$expected_review_input" "$expected_reviewed_attempt" "$artifact_kind" "$workflow_root_id" "$expected_status" "$@" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

import yaml

artifact_path = Path(sys.argv[1])
expected_snapshot = sys.argv[2]
expected_review_input = sys.argv[3]
expected_reviewed_attempt = sys.argv[4]
artifact_kind = sys.argv[5]
workflow_root_id = sys.argv[6]
expected_status = sys.argv[7]
required_paths = [Path(value).resolve(strict=True) for value in sys.argv[8:]]
text = artifact_path.read_text(encoding="utf-8", errors="replace")
match = re.match(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)", text, re.DOTALL)
if not match:
    print(
        f"build-artifact-check: implementation provenance front matter is missing: {artifact_path}",
        file=sys.stderr,
    )
    raise SystemExit(1)

front_matter = yaml.safe_load(match.group("front")) or {}
contracts = {
    "review": {
        "schema": "gc.build.review.v1",
        "workflow": {"id": workflow_root_id, "formula": "build-basic"},
        "methodology": {"pack": "gascity", "name": "build-basic"},
        "producer": {"formula": "build-basic-review", "stage": "review"},
    },
    "final-report": {
        "schema": "gc.build.final-report.v1",
        "workflow": {"id": workflow_root_id, "formula": "build-basic"},
        "methodology": {"pack": "gascity", "name": "build-basic"},
        "producer": {"formula": "build-basic", "stage": "finalize"},
    },
}
contract = contracts.get(artifact_kind)
if contract is None:
    print(
        f"build-artifact-check: implementation provenance artifact kind is unsupported: {artifact_kind}",
        file=sys.stderr,
    )
    raise SystemExit(1)

def mapping(value):
    return value if isinstance(value, dict) else {}

identity_matches = (
    isinstance(front_matter, dict)
    and front_matter.get("schema") == contract["schema"]
    and front_matter.get("status") == expected_status
    and all(mapping(front_matter.get("workflow")).get(key) == value for key, value in contract["workflow"].items())
    and all(mapping(front_matter.get("methodology")).get(key) == value for key, value in contract["methodology"].items())
    and all(mapping(front_matter.get("producer")).get(key) == value for key, value in contract["producer"].items())
)
if not identity_matches:
    print(
        "build-artifact-check: implementation provenance artifact identity/status mismatch: "
        f"artifact={artifact_path} kind={artifact_kind} root={workflow_root_id}",
        file=sys.stderr,
    )
    raise SystemExit(1)

observed_snapshot = (
    front_matter.get("implementation_snapshot", "")
    if isinstance(front_matter, dict)
    else ""
)
if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_snapshot) or observed_snapshot != expected_snapshot:
    print(
        "build-artifact-check: implementation provenance snapshot mismatch: "
        f"artifact={artifact_path} expected={expected_snapshot or '<missing>'} "
        f"observed={observed_snapshot or '<missing>'}",
        file=sys.stderr,
    )
    raise SystemExit(1)

observed_review_input = (
    front_matter.get("review_input_snapshot", "")
    if isinstance(front_matter, dict)
    else ""
)
observed_reviewed_attempt = (
    str(front_matter.get("reviewed_attempt", ""))
    if isinstance(front_matter, dict)
    else ""
)
if (
    not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_review_input)
    or observed_review_input != expected_review_input
    or not re.fullmatch(r"[1-9][0-9]*", expected_reviewed_attempt)
    or observed_reviewed_attempt != expected_reviewed_attempt
):
    print(
        "build-artifact-check: implementation provenance review input mismatch: "
        f"artifact={artifact_path} expected_input={expected_review_input or '<missing>'} "
        f"observed_input={observed_review_input or '<missing>'} "
        f"expected_attempt={expected_reviewed_attempt or '<missing>'} "
        f"observed_attempt={observed_reviewed_attempt or '<missing>'}",
        file=sys.stderr,
    )
    raise SystemExit(1)

trace = front_matter.get("trace") if isinstance(front_matter, dict) else None
upstream = trace.get("upstream") if isinstance(trace, dict) else None
coverage = trace.get("coverage") if isinstance(trace, dict) else None
if not isinstance(upstream, list):
    print(
        f"build-artifact-check: implementation provenance trace.upstream is missing: {artifact_path}",
        file=sys.stderr,
    )
    raise SystemExit(1)
has_blocked_coverage = (
    isinstance(coverage, list)
    and any(
        isinstance(entry, dict) and entry.get("status") == "blocked"
        for entry in coverage
    )
)
if artifact_kind == "review" and (
    not isinstance(coverage, list)
    or (front_matter.get("status") == "approved" and has_blocked_coverage)
    or (
        front_matter.get("status") == "changes_required"
        and not has_blocked_coverage
    )
):
    print(
        f"build-artifact-check: implementation provenance review status/coverage mismatch: {artifact_path}",
        file=sys.stderr,
    )
    raise SystemExit(1)

for required_path in required_paths:
    expected_hash = f"sha256:{hashlib.sha256(required_path.read_bytes()).hexdigest()}"
    expected_path = str(required_path)
    observed_hashes = []
    for entry in upstream:
        if not isinstance(entry, dict):
            continue
        raw_path = entry.get("path")
        if raw_path == expected_path:
            observed_hashes.append(str(entry.get("hash") or ""))
    if observed_hashes != [expected_hash]:
        print(
            "build-artifact-check: implementation provenance must trace exact current bytes once: "
            f"artifact={artifact_path} upstream={required_path} "
            f"expected={expected_hash} observed={observed_hashes}",
            file=sys.stderr,
        )
        raise SystemExit(1)
PY
}

front_matter_value() {
  python3 - "$1" "$2" <<'PY'
import re
import sys
from pathlib import Path

import yaml

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
match = re.match(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)", text, re.DOTALL)
if not match:
    raise SystemExit(1)
front = yaml.safe_load(match.group("front")) or {}
value = front
for part in sys.argv[2].split("."):
    value = value.get(part, "") if isinstance(value, dict) else ""
print(value if isinstance(value, (str, int)) else "")
PY
}

current_producer_attempt() {
  local control_epoch iteration_attempt ralph_step_id control_for controls control_json control_label
  control_epoch="$(metadata_value "$SHOW_JSON" "gc.control_epoch")"
  if [ -n "$control_epoch" ]; then
    printf '%s\n' "$control_epoch"
    return 0
  fi

  iteration_attempt="$(metadata_value "$SHOW_JSON" "gc.attempt")"
  ralph_step_id="$(metadata_value "$SHOW_JSON" "gc.ralph_step_id")"
  control_for="$(metadata_value "$SHOW_JSON" "gc.control_for")"
  case "$iteration_attempt" in
    ''|*[!0-9]*|0) fail "current producer attempt is invalid on $BEAD_ID: ${iteration_attempt:-<missing>}" ;;
  esac
  [ -n "$ROOT_ID" ] || fail "current producer iteration $BEAD_ID is missing gc.root_bead_id"
  if [ -n "$ralph_step_id" ]; then
    control_label="$ralph_step_id"
    controls="$(gc bd list --all --metadata-field \
      "gc.root_bead_id=$ROOT_ID" --json --limit=0 2>/dev/null)" || \
      fail "could not list current producer controls for workflow root $ROOT_ID"
    if ! control_epoch="$(printf '%s\n' "$controls" | jq -er \
      --arg root "$ROOT_ID" \
      --arg step "$ralph_step_id" '
        [.[] | select(
          (.metadata["gc.root_bead_id"] // "") == $root and
          (.metadata["gc.kind"] // "") == "ralph" and
          (.metadata["gc.step_id"] // "") == $step
        )] as $controls
        | if ($controls | length) != 1 then
            error("expected exactly one current producer control")
          else
            ($controls[0].metadata["gc.control_epoch"] // "") | tostring
          end
      ' 2>/dev/null)"; then
      fail "current producer iteration $BEAD_ID could not resolve exactly one logical control for $ralph_step_id"
    fi
  elif [ -n "$control_for" ]; then
    control_label="$control_for"
    control_json="$(gc bd show "$control_for" --json 2>/dev/null)" || \
      fail "current producer iteration $BEAD_ID could not read control bead $control_for"
    if ! control_epoch="$(printf '%s\n' "$control_json" | jq -er \
      --arg id "$control_for" \
      --arg root "$ROOT_ID" '
        if type != "array" or length != 1 then
          error("expected exactly one control bead")
        else
          .[0] as $control
          | if (($control.id // "") | tostring) != $id then
              error("control bead id mismatch")
            elif ($control.metadata["gc.root_bead_id"] // "") != $root then
              error("control bead root mismatch")
            elif ($control.metadata["gc.kind"] // "") != "ralph" then
              error("control bead kind mismatch")
            else
              ($control.metadata["gc.control_epoch"] // "") | tostring
            end
        end
      ' 2>/dev/null)"; then
      fail "current producer iteration $BEAD_ID could not resolve control bead $control_for for workflow root $ROOT_ID"
    fi
  else
    fail "current producer iteration $BEAD_ID is missing gc.ralph_step_id and gc.control_for"
  fi
  case "$control_epoch" in
    ''|*[!0-9]*|0) fail "current producer control epoch is invalid for $control_label: ${control_epoch:-<missing>}" ;;
  esac
  [ "$iteration_attempt" = "$control_epoch" ] || fail \
    "current producer iteration attempt $iteration_attempt does not match current control epoch $control_epoch for $control_label"
  printf '%s\n' "$iteration_attempt"
}

require_review_attempt_provenance() {
  workflow_root_id="$1"
  reviewed_attempt="$2"
  expected_snapshot="$3"
  expected_review_input="$4"
  review_status="$5"
  review_mode="$(metadata_value "$ROOT_JSON" "gc.var.review_mode")"
  rows="$(gc bd list --all --metadata-field \
    "gc.root_bead_id=$workflow_root_id" --json --limit=0 2>/dev/null)" || \
    fail "implementation provenance could not list review rows for $workflow_root_id"
  if ! printf '%s\n' "$rows" | jq -e \
    --arg root "$workflow_root_id" \
    --arg attempt "$reviewed_attempt" \
    --arg snapshot "$expected_snapshot" \
    --arg review_input "$expected_review_input" \
    --arg review_status "$review_status" \
    --arg review_mode "$review_mode" '
    def rows_for($step):
      [.[] | select(
        (.metadata["gc.root_bead_id"] // "") == $root and
        (.metadata["gc.attempt"] // "") == $attempt and
        (.metadata["gc.ralph_step_id"] // "") == "review.build-basic-review-loop" and
        (.metadata["gc.step_id"] // "") == $step and
        (.metadata["gc.scope_role"] // "") == "member"
      )];
    def all_review_rows:
      [.[] | select(
        (.metadata["gc.root_bead_id"] // "") == $root and
        (.metadata["gc.ralph_step_id"] // "") == "review.build-basic-review-loop" and
        (.metadata["gc.scope_role"] // "") == "member"
      )];
    def latest_attempt_ok:
      all_review_rows as $rows
      | (($attempt | test("^[1-9][0-9]*$")) and
         (($rows | length) > 0) and
         all($rows[]; ((.metadata["gc.attempt"] // "") | test("^[1-9][0-9]*$"))) and
         (([$rows[] | .metadata["gc.attempt"] | tonumber] | max) == ($attempt | tonumber)));
    def base_ok($rows):
      (($rows | length) == 1) and
      (($rows[0].status // "") == "closed") and
      (($rows[0].metadata["gc.outcome"] // "") == "pass") and
      ((($rows[0].metadata["code_review.reviewed_attempt"] // "") | tostring) ==
        ($attempt | tostring)) and
      (($rows[0].metadata["code_review.implementation_snapshot"] // "") == $snapshot) and
      (($rows[0].metadata["code_review.review_input_snapshot"] // "") == $review_input);
    def lane_verdict_ok($rows; $key):
      (($rows[0].metadata[$key] // "") == "approve") or
      (
        $review_mode == "report" and
        (($rows[0].metadata[$key] // "") == "iterate")
      );
    latest_attempt_ok and (
      rows_for("review.acceptance-review") as $acceptance
      | rows_for("review.test-evidence-review") as $tests
      | rows_for("review.simplicity-review") as $simplicity
      | rows_for("review.synthesize-review") as $synthesis
      | rows_for(
          if $review_mode == "report"
          then "review.report-review-findings"
          else "review.apply-review-findings"
          end
        ) as $terminal
      | base_ok($acceptance)
      and lane_verdict_ok($acceptance; "code_review.acceptance_verdict")
      and base_ok($tests)
      and lane_verdict_ok($tests; "code_review.test_evidence_verdict")
      and base_ok($simplicity)
      and lane_verdict_ok($simplicity; "code_review.simplicity_verdict")
      and base_ok($synthesis)
      and base_ok($terminal)
      and (($terminal[0].metadata["code_review.verdict"] // "") ==
        (if $review_mode == "report" then "reported" else "done" end))
      and (
        if $review_mode == "report" then
          (
            $review_status == "approved" and
            (($acceptance[0].metadata["code_review.acceptance_verdict"] // "") == "approve") and
            (($tests[0].metadata["code_review.test_evidence_verdict"] // "") == "approve") and
            (($simplicity[0].metadata["code_review.simplicity_verdict"] // "") == "approve")
          ) or (
            $review_status == "changes_required" and
            (
              (($acceptance[0].metadata["code_review.acceptance_verdict"] // "") == "iterate") or
              (($tests[0].metadata["code_review.test_evidence_verdict"] // "") == "iterate") or
              (($simplicity[0].metadata["code_review.simplicity_verdict"] // "") == "iterate")
            )
          )
        else
          $review_status == "approved"
        end
      )
    )
  ' >/dev/null 2>&1; then
    fail "implementation provenance exact review attempt is incomplete or stale: root=$workflow_root_id attempt=$reviewed_attempt"
  fi
}

SHOW_JSON="$(gc bd show "$BEAD_ID" --json 2>/dev/null)" || fail "gc bd show $BEAD_ID failed"

SCHEMA="$(metadata_value "$SHOW_JSON" "gc.build.artifact_schema")"
PATH_KEYS="$(metadata_value "$SHOW_JSON" "gc.build.artifact_path_keys")"
[ -n "$SCHEMA" ] || fail "step metadata gc.build.artifact_schema is missing on $BEAD_ID"
[ -n "$PATH_KEYS" ] || fail "step metadata gc.build.artifact_path_keys is missing on $BEAD_ID"

ROOT_ID="$(metadata_value "$SHOW_JSON" "gc.root_bead_id")"
ROOT_JSON="$SHOW_JSON"
if [ -n "$ROOT_ID" ] && [ "$ROOT_ID" != "$BEAD_ID" ]; then
  ROOT_JSON="$(gc bd show "$ROOT_ID" --json 2>/dev/null)" || fail "gc bd show $ROOT_ID failed"
fi

ARTIFACT_PATH=""
RESOLVED_KEY=""
IFS=',' read -r -a KEYS <<<"$PATH_KEYS"
for key in "${KEYS[@]}"; do
  key="$(printf '%s' "$key" | tr -d '[:space:]')"
  [ -n "$key" ] || continue
  value="$(metadata_value "$ROOT_JSON" "$key")"
  if [ -n "$value" ]; then
    ARTIFACT_PATH="$value"
    RESOLVED_KEY="$key"
    break
  fi
done
[ -n "$ARTIFACT_PATH" ] || fail "no artifact path recorded on workflow root ${ROOT_ID:-$BEAD_ID}; tried metadata keys: $PATH_KEYS. The producing stage must record the resolved artifact path before closing."

ARTIFACT_PATH="$(resolve_declared_path "$ARTIFACT_PATH" "$RESOLVED_KEY")"
[ -f "$ARTIFACT_PATH" ] || fail "artifact $ARTIFACT_PATH from $RESOLVED_KEY does not exist"
[ ! -L "$ARTIFACT_PATH" ] || fail "artifact $ARTIFACT_PATH from $RESOLVED_KEY must not be a symlink"
pin_file "$ARTIFACT_PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VALIDATOR="$SCRIPT_DIR/../validate_build_artifact.py"
[ -f "$VALIDATOR" ] || fail "installed validate_build_artifact.py not found beside $SCRIPT_DIR"

BASE_VALIDATOR_UPSTREAM_ARGS=()
MISSING_LAUNCHER_ROOT=""
if [ -n "${GC_WORK_DIR:-}" ]; then
  if UPSTREAM_LAUNCHER_ROOT="$(launcher_root_from_work_dir)"; then
    BASE_VALIDATOR_UPSTREAM_ARGS+=(--upstream-root "$UPSTREAM_LAUNCHER_ROOT")
  else
    MISSING_LAUNCHER_ROOT="GC_WORK_DIR is set but no launcher root containing .gc/scripts/checks/build-artifact-valid.sh exists at or above GC_WORK_DIR=$GC_WORK_DIR"
  fi
fi

VALIDATOR_UPSTREAM_ARGS=("${BASE_VALIDATOR_UPSTREAM_ARGS[@]}")
if ARTIFACT_WORKTREE_ROOT="$(git_worktree_root_for_file "$ARTIFACT_PATH")"; then
  VALIDATOR_UPSTREAM_ARGS+=(--upstream-root "$ARTIFACT_WORKTREE_ROOT")
fi
VALIDATOR_POLICY_ARGS=()
if [ "$(metadata_value "$SHOW_JSON" "gc.build.require_review_status_coverage")" = "true" ]; then
  VALIDATOR_POLICY_ARGS+=(--enforce-review-status-coverage)
fi

if ! OUTPUT="$(python3 "$VALIDATOR" --schema "$SCHEMA" --path "$ARTIFACT_PATH" \
  --verify-absolute-upstreams "${VALIDATOR_UPSTREAM_ARGS[@]}" \
  "${VALIDATOR_POLICY_ARGS[@]}" 2>&1)"; then
  echo "build-artifact-check: schema=$SCHEMA path=$ARTIFACT_PATH failed validation" >&2
  printf '%s\n' "$OUTPUT" >&2
  exit 1
fi
[ -z "$MISSING_LAUNCHER_ROOT" ] || fail "$MISSING_LAUNCHER_ROOT"

if [ "$(metadata_value "$SHOW_JSON" "gc.build.require_approved_status")" = "true" ]; then
  ARTIFACT_STATUS="$(front_matter_value "$ARTIFACT_PATH" status)" || \
    fail "artifact status is unreadable: $ARTIFACT_PATH"
  [ "$ARTIFACT_STATUS" = "approved" ] || fail \
    "schema=$SCHEMA path=$ARTIFACT_PATH requires status=approved; observed=${ARTIFACT_STATUS:-<missing>}"
fi

EXPECTED_PRODUCER_FORMULA="$(metadata_value "$SHOW_JSON" "gc.build.expected_producer_formula")"
if [ -n "$EXPECTED_PRODUCER_FORMULA" ]; then
  ARTIFACT_PRODUCER_FORMULA="$(front_matter_value "$ARTIFACT_PATH" producer.formula)" || \
    fail "artifact producer.formula is unreadable: $ARTIFACT_PATH"
  [ "$ARTIFACT_PRODUCER_FORMULA" = "$EXPECTED_PRODUCER_FORMULA" ] || fail \
    "schema=$SCHEMA path=$ARTIFACT_PATH requires producer.formula=$EXPECTED_PRODUCER_FORMULA; observed=${ARTIFACT_PRODUCER_FORMULA:-<missing>}"
fi

EXPECTED_PRODUCER_STAGE="$(metadata_value "$SHOW_JSON" "gc.build.expected_producer_stage")"
if [ -n "$EXPECTED_PRODUCER_STAGE" ]; then
  ARTIFACT_PRODUCER_STAGE="$(front_matter_value "$ARTIFACT_PATH" producer.stage)" || \
    fail "artifact producer.stage is unreadable: $ARTIFACT_PATH"
  [ "$ARTIFACT_PRODUCER_STAGE" = "$EXPECTED_PRODUCER_STAGE" ] || fail \
    "schema=$SCHEMA path=$ARTIFACT_PATH requires producer.stage=$EXPECTED_PRODUCER_STAGE; observed=${ARTIFACT_PRODUCER_STAGE:-<missing>}"
fi

if [ "$(metadata_value "$SHOW_JSON" "gc.build.require_current_producer_attempt")" = "true" ]; then
  CURRENT_PRODUCER_ATTEMPT="$(current_producer_attempt)"
  case "$CURRENT_PRODUCER_ATTEMPT" in
    ''|*[!0-9]*|0) fail "current producer attempt is invalid on $BEAD_ID: ${CURRENT_PRODUCER_ATTEMPT:-<missing>}" ;;
  esac
  ARTIFACT_PRODUCER_ATTEMPT="$(front_matter_value "$ARTIFACT_PATH" producer.attempt)" || \
    fail "artifact producer.attempt is unreadable: $ARTIFACT_PATH"
  [ "$ARTIFACT_PRODUCER_ATTEMPT" = "$CURRENT_PRODUCER_ATTEMPT" ] || fail \
    "schema=$SCHEMA path=$ARTIFACT_PATH requires producer.attempt=$CURRENT_PRODUCER_ATTEMPT; observed=${ARTIFACT_PRODUCER_ATTEMPT:-<missing>}"
fi

IMPLEMENTATION_PROVENANCE_REQUIRED="$(metadata_value "$SHOW_JSON" "gc.build.require_implementation_provenance")"
if [ "$IMPLEMENTATION_PROVENANCE_REQUIRED" = "true" ]; then
  case "$SCHEMA:$RESOLVED_KEY" in
    gc.build.review.v1:gc.build.review_report_path) ARTIFACT_KIND="review" ;;
    gc.build.final-report.v1:gc.build.final_report_path) ARTIFACT_KIND="final-report" ;;
    *) fail "implementation provenance is unsupported for schema/path contract $SCHEMA:$RESOLVED_KEY" ;;
  esac
  WORKFLOW_ROOT_ID="${ROOT_ID:-$BEAD_ID}"
  IMPLEMENTATION_SNAPSHOT="$(metadata_value "$ROOT_JSON" "gc.build.implementation_snapshot")"
  REVIEW_INPUT_SNAPSHOT="$(metadata_value "$ROOT_JSON" "gc.build.review_input_snapshot")"
  REVIEW_MODE="$(metadata_value "$ROOT_JSON" "gc.var.review_mode")"
  IMPLEMENTATION_SUMMARY_RAW="$(metadata_value "$ROOT_JSON" "gc.build.implementation_summary_path")"
  REVIEW_CONTEXT_RAW="$(metadata_value "$ROOT_JSON" "gc.build.code_review_context_path")"
  [ -n "$IMPLEMENTATION_SNAPSHOT" ] || fail "implementation provenance gc.build.implementation_snapshot is missing"
  [ -n "$REVIEW_INPUT_SNAPSHOT" ] || fail "implementation provenance gc.build.review_input_snapshot is missing"
  [ -n "$IMPLEMENTATION_SUMMARY_RAW" ] || fail "implementation provenance gc.build.implementation_summary_path is missing"
  [ -n "$REVIEW_CONTEXT_RAW" ] || fail "implementation provenance gc.build.code_review_context_path is missing"
  IMPLEMENTATION_SUMMARY_PATH="$(resolve_declared_path "$IMPLEMENTATION_SUMMARY_RAW" "gc.build.implementation_summary_path")"
  [ -f "$IMPLEMENTATION_SUMMARY_PATH" ] || fail "implementation provenance summary does not exist: $IMPLEMENTATION_SUMMARY_PATH"
  [ ! -L "$IMPLEMENTATION_SUMMARY_PATH" ] || fail "implementation provenance summary must not be a symlink: $IMPLEMENTATION_SUMMARY_PATH"
  pin_file "$IMPLEMENTATION_SUMMARY_PATH"
  REVIEW_CONTEXT_PATH="$(resolve_declared_path "$REVIEW_CONTEXT_RAW" "gc.build.code_review_context_path")"
  [ -f "$REVIEW_CONTEXT_PATH" ] || fail "implementation provenance review context does not exist: $REVIEW_CONTEXT_PATH"
  [ ! -L "$REVIEW_CONTEXT_PATH" ] || fail "implementation provenance review context must not be a symlink: $REVIEW_CONTEXT_PATH"
  pin_file "$REVIEW_CONTEXT_PATH"
  EXPECTED_ARTIFACT_ARGS=(--expected-artifact "$ARTIFACT_PATH")
  REVIEW_REPORT_PATH=""
  if [ "$ARTIFACT_KIND" = "final-report" ]; then
    REVIEW_REPORT_RAW="$(metadata_value "$ROOT_JSON" "gc.build.review_report_path")"
    [ -n "$REVIEW_REPORT_RAW" ] || fail "implementation provenance gc.build.review_report_path is missing"
    REVIEW_REPORT_PATH="$(resolve_declared_path "$REVIEW_REPORT_RAW" "gc.build.review_report_path")"
    [ -f "$REVIEW_REPORT_PATH" ] || fail "implementation provenance review report does not exist: $REVIEW_REPORT_PATH"
    [ ! -L "$REVIEW_REPORT_PATH" ] || fail "implementation provenance review report must not be a symlink: $REVIEW_REPORT_PATH"
    pin_file "$REVIEW_REPORT_PATH"
    EXPECTED_ARTIFACT_ARGS+=(--expected-artifact "$REVIEW_REPORT_PATH")
  fi
  PROVENANCE_VERIFIER="$SCRIPT_DIR/../verify_implementation_provenance.py"
  [ -f "$PROVENANCE_VERIFIER" ] || fail "installed implementation provenance verifier is missing: $PROVENANCE_VERIFIER"
  if ! PROVENANCE_OUTPUT="$(python3 "$PROVENANCE_VERIFIER" \
    --root-id "$WORKFLOW_ROOT_ID" \
    --expected-snapshot "$IMPLEMENTATION_SNAPSHOT" \
    --expected-summary "$IMPLEMENTATION_SUMMARY_PATH" \
    "${EXPECTED_ARTIFACT_ARGS[@]}" \
    --validator "$VALIDATOR" 2>&1)"; then
    echo "build-artifact-check: implementation provenance validation failed" >&2
    printf '%s\n' "$PROVENANCE_OUTPUT" >&2
    exit 1
  fi

  if [ "$ARTIFACT_KIND" = "review" ]; then
    REVIEWED_ATTEMPT="$(front_matter_value "$ARTIFACT_PATH" reviewed_attempt)" || \
      fail "implementation provenance review artifact reviewed_attempt is unreadable"
    REVIEW_STATUS="$(front_matter_value "$ARTIFACT_PATH" status)" || \
      fail "implementation provenance review artifact status is unreadable"
    require_review_attempt_provenance \
      "$WORKFLOW_ROOT_ID" "$REVIEWED_ATTEMPT" \
      "$IMPLEMENTATION_SNAPSHOT" "$REVIEW_INPUT_SNAPSHOT" "$REVIEW_STATUS"
    require_implementation_provenance \
      "$ARTIFACT_PATH" "$IMPLEMENTATION_SNAPSHOT" "$REVIEW_INPUT_SNAPSHOT" \
      "$REVIEWED_ATTEMPT" review "$WORKFLOW_ROOT_ID" \
      "$REVIEW_STATUS" \
      "$IMPLEMENTATION_SUMMARY_PATH" "$REVIEW_CONTEXT_PATH" || exit 1
  else
    REVIEW_VALIDATOR_UPSTREAM_ARGS=("${BASE_VALIDATOR_UPSTREAM_ARGS[@]}")
    if REVIEW_WORKTREE_ROOT="$(git_worktree_root_for_file "$REVIEW_REPORT_PATH")"; then
      REVIEW_VALIDATOR_UPSTREAM_ARGS+=(--upstream-root "$REVIEW_WORKTREE_ROOT")
    fi
    if ! REVIEW_OUTPUT="$(python3 "$VALIDATOR" --schema gc.build.review.v1 \
      --path "$REVIEW_REPORT_PATH" --verify-absolute-upstreams \
      "${REVIEW_VALIDATOR_UPSTREAM_ARGS[@]}" 2>&1)"; then
      echo "build-artifact-check: implementation provenance review report failed validation: $REVIEW_REPORT_PATH" >&2
      printf '%s\n' "$REVIEW_OUTPUT" >&2
      exit 1
    fi
    REVIEWED_ATTEMPT="$(front_matter_value "$REVIEW_REPORT_PATH" reviewed_attempt)" || \
      fail "implementation provenance approved review reviewed_attempt is unreadable"
    REVIEW_STATUS="$(front_matter_value "$REVIEW_REPORT_PATH" status)" || \
      fail "implementation provenance review status is unreadable"
    require_review_attempt_provenance \
      "$WORKFLOW_ROOT_ID" "$REVIEWED_ATTEMPT" \
      "$IMPLEMENTATION_SNAPSHOT" "$REVIEW_INPUT_SNAPSHOT" "$REVIEW_STATUS"
    case "$REVIEW_MODE:$REVIEW_STATUS" in
      *:approved) EXPECTED_FINAL_STATUS="approved" ;;
      report:changes_required) EXPECTED_FINAL_STATUS="blocked" ;;
      *) fail "implementation provenance review status cannot finalize: mode=${REVIEW_MODE:-<missing>} status=${REVIEW_STATUS:-<missing>}" ;;
    esac
    require_implementation_provenance \
      "$REVIEW_REPORT_PATH" "$IMPLEMENTATION_SNAPSHOT" "$REVIEW_INPUT_SNAPSHOT" \
      "$REVIEWED_ATTEMPT" review "$WORKFLOW_ROOT_ID" \
      "$REVIEW_STATUS" \
      "$IMPLEMENTATION_SUMMARY_PATH" "$REVIEW_CONTEXT_PATH" || exit 1
    require_implementation_provenance \
      "$ARTIFACT_PATH" "$IMPLEMENTATION_SNAPSHOT" "$REVIEW_INPUT_SNAPSHOT" \
      "$REVIEWED_ATTEMPT" final-report "$WORKFLOW_ROOT_ID" \
      "$EXPECTED_FINAL_STATUS" \
      "$IMPLEMENTATION_SUMMARY_PATH" "$REVIEW_REPORT_PATH" || exit 1
  fi
fi

if [ "$SCHEMA" = "gc.build.review.v1" ]; then
  CALLER_SUBJECT_RAW="$(metadata_value "$ROOT_JSON" "gc.var.subject_path")"
  CANONICAL_SUBJECT_RAW="$(metadata_value "$ROOT_JSON" "gc.build.review_subject_path")"
  SUBJECT_PATH=""
  if [ -n "$CALLER_SUBJECT_RAW" ]; then
    CALLER_SUBJECT_PATH="$(resolve_declared_path "$CALLER_SUBJECT_RAW" "gc.var.subject_path")"
    [ -f "$CALLER_SUBJECT_PATH" ] || fail "caller review subject does not exist: $CALLER_SUBJECT_PATH"
    SUBJECT_PATH="$CALLER_SUBJECT_PATH"
    if [ -n "$CANONICAL_SUBJECT_RAW" ]; then
      CANONICAL_SUBJECT_PATH="$(resolve_declared_path "$CANONICAL_SUBJECT_RAW" "gc.build.review_subject_path")"
      [ -f "$CANONICAL_SUBJECT_PATH" ] || fail "canonical review subject does not exist: $CANONICAL_SUBJECT_PATH"
      [ "$(canonical_file_path "$CALLER_SUBJECT_PATH")" = "$(canonical_file_path "$CANONICAL_SUBJECT_PATH")" ] || fail "review subject metadata paths disagree: caller=$CALLER_SUBJECT_PATH canonical=$CANONICAL_SUBJECT_PATH"
      SUBJECT_PATH="$CANONICAL_SUBJECT_PATH"
    fi
  elif [ -n "$CANONICAL_SUBJECT_RAW" ]; then
    SUBJECT_PATH="$(resolve_declared_path "$CANONICAL_SUBJECT_RAW" "gc.build.review_subject_path")"
    [ -f "$SUBJECT_PATH" ] || fail "canonical review subject does not exist: $SUBJECT_PATH"
  fi
  if [ -n "$SUBJECT_PATH" ]; then
    pin_file "$SUBJECT_PATH"
    require_subject_trace "$ARTIFACT_PATH" "$SUBJECT_PATH" || exit 1
  fi

  REQUIRE_INTERNAL="$(metadata_value "$SHOW_JSON" "gc.build.require_internal_review_report")"
  INTERNAL_RAW="$(metadata_value "$ROOT_JSON" "gc.build.code_review_report_path")"
  if [ "$RESOLVED_KEY" != "gc.build.code_review_report_path" ]; then
    if [ "$REQUIRE_INTERNAL" = "true" ] && [ -z "$INTERNAL_RAW" ]; then
      fail "required internal review report metadata gc.build.code_review_report_path is missing"
    fi
  fi
  if [ "$REQUIRE_INTERNAL" = "true" ] && [ -n "$INTERNAL_RAW" ] && [ "$RESOLVED_KEY" != "gc.build.code_review_report_path" ]; then
    INTERNAL_PATH="$(resolve_declared_path "$INTERNAL_RAW" "gc.build.code_review_report_path")"
    [ -f "$INTERNAL_PATH" ] || fail "internal review report does not exist: $INTERNAL_PATH"
    [ ! -L "$INTERNAL_PATH" ] || fail "internal review report must not be a symlink: $INTERNAL_PATH"
    [ ! "$INTERNAL_PATH" -ef "$ARTIFACT_PATH" ] || fail "internal and adapter review report paths must be distinct: internal=$INTERNAL_PATH adapter=$ARTIFACT_PATH"
    pin_file "$INTERNAL_PATH"
    INTERNAL_VALIDATOR_UPSTREAM_ARGS=("${BASE_VALIDATOR_UPSTREAM_ARGS[@]}")
    if INTERNAL_WORKTREE_ROOT="$(git_worktree_root_for_file "$INTERNAL_PATH")"; then
      INTERNAL_VALIDATOR_UPSTREAM_ARGS+=(--upstream-root "$INTERNAL_WORKTREE_ROOT")
    fi
    if ! INTERNAL_OUTPUT="$(python3 "$VALIDATOR" --schema "$SCHEMA" --path "$INTERNAL_PATH" --verify-absolute-upstreams "${INTERNAL_VALIDATOR_UPSTREAM_ARGS[@]}" 2>&1)"; then
      echo "build-artifact-check: internal review report $INTERNAL_PATH failed validation" >&2
      printf '%s\n' "$INTERNAL_OUTPUT" >&2
      exit 1
    fi
    if [ -n "$SUBJECT_PATH" ]; then
      require_subject_trace "$INTERNAL_PATH" "$SUBJECT_PATH" || exit 1
    fi
    EXPECTED_INTERNAL_STAGE="$(metadata_value "$SHOW_JSON" "gc.build.expected_internal_review_producer_stage")"
    EXPECTED_ADAPTER_STAGE="$(metadata_value "$SHOW_JSON" "gc.build.expected_adapter_review_producer_stage")"
    if [ "$RESOLVED_KEY" = "gc.build.review_report_path" ] && \
      { [ -n "$EXPECTED_INTERNAL_STAGE" ] || [ -n "$EXPECTED_ADAPTER_STAGE" ]; }; then
      if [ -z "$EXPECTED_INTERNAL_STAGE" ] || [ -z "$EXPECTED_ADAPTER_STAGE" ]; then
        fail "internal adapter fidelity requires both expected producer stages"
      fi
      CURRENT_ADAPTER_ATTEMPT="$(current_producer_attempt)"
      IMPLEMENTATION_SUMMARY_RAW="$(metadata_value "$ROOT_JSON" "gc.build.implementation_summary_path")"
      [ -n "$IMPLEMENTATION_SUMMARY_RAW" ] || fail \
        "review adapter fidelity requires gc.build.implementation_summary_path"
      IMPLEMENTATION_SUMMARY_PATH="$(resolve_declared_path \
        "$IMPLEMENTATION_SUMMARY_RAW" "gc.build.implementation_summary_path")"
      [ -f "$IMPLEMENTATION_SUMMARY_PATH" ] || fail \
        "current implementation summary does not exist: $IMPLEMENTATION_SUMMARY_PATH"
      [ ! -L "$IMPLEMENTATION_SUMMARY_PATH" ] || fail \
        "current implementation summary must not be a symlink: $IMPLEMENTATION_SUMMARY_PATH"
      IMPLEMENTATION_SUMMARY_PATH="$(canonical_file_path "$IMPLEMENTATION_SUMMARY_PATH")" || fail \
        "could not resolve current implementation summary: $IMPLEMENTATION_SUMMARY_PATH"
      pin_file "$IMPLEMENTATION_SUMMARY_PATH"
      require_review_adapter_fidelity \
        "$INTERNAL_PATH" "$ARTIFACT_PATH" \
        "$EXPECTED_INTERNAL_STAGE" "$EXPECTED_ADAPTER_STAGE" \
        "$CURRENT_ADAPTER_ATTEMPT" "$IMPLEMENTATION_SUMMARY_PATH" || exit 1
    else
      cmp -s "$INTERNAL_PATH" "$ARTIFACT_PATH" || fail "internal and adapter review reports must be byte-identical: internal=$INTERNAL_PATH adapter=$ARTIFACT_PATH"
    fi
  fi
fi

verify_pinned_files
echo "build artifact valid: schema=$SCHEMA path=$ARTIFACT_PATH"
