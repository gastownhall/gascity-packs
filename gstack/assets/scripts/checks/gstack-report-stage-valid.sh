#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "gstack-report-stage-check: $*" >&2
  exit 1
}

metadata_value() {
  local json="$1"
  local key="$2"
  printf '%s\n' "$json" | jq -r --arg key "$key" '
    (if type == "array" then (.[0] // {}) else . end)
    | .metadata[$key] // empty
  ' 2>/dev/null
}

BEAD_ID="${GC_BEAD_ID:-}"
[ -n "$BEAD_ID" ] || fail "GC_BEAD_ID is required"
command -v gc >/dev/null 2>&1 || fail "gc is required on PATH"
command -v jq >/dev/null 2>&1 || fail "jq is required on PATH"
command -v python3 >/dev/null 2>&1 || fail "python3 is required on PATH"

STEP_JSON="$(gc bd show "$BEAD_ID" --json 2>/dev/null || true)"
ROOT_ID="$(metadata_value "$STEP_JSON" "gc.root_bead_id")"
[ -n "$ROOT_ID" ] || ROOT_ID="$BEAD_ID"
ROOT_JSON="$STEP_JSON"
if [ "$ROOT_ID" != "$BEAD_ID" ]; then
  ROOT_JSON="$(gc bd show "$ROOT_ID" --json 2>/dev/null || true)"
fi

REVIEW_MODE="$(metadata_value "$ROOT_JSON" "gc.var.review_mode")"
case "$REVIEW_MODE" in
  report) ;;
  agent|interactive)
    echo "gstack current report stage not required: mode=$REVIEW_MODE"
    exit 0
    ;;
  *) fail "unsupported review mode: ${REVIEW_MODE:-<missing>}" ;;
esac

LOOP_STEP="$(metadata_value "$STEP_JSON" "gc.gstack.report_loop_step")"
PATH_KEY="$(metadata_value "$STEP_JSON" "gc.gstack.report_path_key")"
SYNTHESIS_STEP="$(metadata_value "$STEP_JSON" "gc.gstack.synthesis_step")"
SYNTHESIS_PATH_KEY="$(metadata_value "$STEP_JSON" "gc.gstack.synthesis_path_key")"
SYNTHESIS_VERDICT_KEY="$(metadata_value "$STEP_JSON" "gc.gstack.synthesis_verdict_key")"
SYNTHESIS_APPROVED_VERDICT="$(metadata_value "$STEP_JSON" "gc.gstack.synthesis_approved_verdict")"
SYNTHESIS_SCHEMA="$(metadata_value "$STEP_JSON" "gc.gstack.synthesis_schema")"
SYNTHESIS_STAGE="$(metadata_value "$STEP_JSON" "gc.gstack.synthesis_stage")"
TERMINAL_PATH_KEY="$(metadata_value "$STEP_JSON" "gc.gstack.terminal_path_key")"
REPORT_SCHEMA="$(metadata_value "$STEP_JSON" "gc.gstack.report_schema")"
REPORT_STAGE="$(metadata_value "$STEP_JSON" "gc.gstack.report_stage")"
[ -n "$LOOP_STEP" ] || fail "finalizer is missing gc.gstack.report_loop_step"
[ -n "$PATH_KEY" ] || fail "finalizer is missing gc.gstack.report_path_key"
for REQUIRED_KEY in \
  SYNTHESIS_STEP \
  SYNTHESIS_PATH_KEY \
  SYNTHESIS_VERDICT_KEY \
  SYNTHESIS_APPROVED_VERDICT \
  SYNTHESIS_SCHEMA \
  SYNTHESIS_STAGE \
  TERMINAL_PATH_KEY \
  REPORT_SCHEMA \
  REPORT_STAGE; do
  REQUIRED_VALUE="${!REQUIRED_KEY}"
  [ -n "$REQUIRED_VALUE" ] || fail "finalizer is missing gstack report contract value $REQUIRED_KEY"
done
case "$LOOP_STEP" in
  *'{'*|*'}'*) fail "report loop step was not rendered: $LOOP_STEP" ;;
esac
case "$SYNTHESIS_STEP" in
  *'{'*|*'}'*) fail "synthesis step was not rendered: $SYNTHESIS_STEP" ;;
esac

SELECTED_PATH="$(metadata_value "$ROOT_JSON" "$PATH_KEY")"
[ -n "$SELECTED_PATH" ] || fail "workflow root is missing $PATH_KEY"

MATCHES="$(gc bd list --all --metadata-field "gc.root_bead_id=$ROOT_ID" --json --limit=0 2>/dev/null || printf '[]')"
if ! CONTROL_ROWS="$(printf '%s\n' "$MATCHES" | jq -c \
  --arg root "$ROOT_ID" \
  --arg step "$LOOP_STEP" '
    [
      .[]
      | select((.metadata["gc.root_bead_id"] // "") == $root)
      | select((.metadata["gc.kind"] // "") == "ralph")
      | select((.metadata["gc.step_id"] // "") == $step)
      | select((.metadata["gc.attempt"] // "") == "")
    ]
  ' 2>/dev/null)"; then
  fail "workflow report-control metadata is malformed"
fi
CONTROL_COUNT="$(printf '%s\n' "$CONTROL_ROWS" | jq -r 'length' 2>/dev/null)"
[ "$CONTROL_COUNT" = "1" ] || fail \
  "expected exactly one logical report-loop control for $LOOP_STEP, observed ${CONTROL_COUNT:-<invalid>}"

CONTROL_STATUS="$(printf '%s\n' "$CONTROL_ROWS" | jq -r '.[0].status // ""')"
CONTROL_OUTCOME="$(printf '%s\n' "$CONTROL_ROWS" | jq -r '.[0].metadata["gc.outcome"] // ""')"
CURRENT_ATTEMPT="$(printf '%s\n' "$CONTROL_ROWS" | jq -r '.[0].metadata["gc.control_epoch"] // ""')"
case "$CURRENT_ATTEMPT" in
  ''|0|*[!0-9]*) fail "report-loop control has invalid gc.control_epoch=${CURRENT_ATTEMPT:-<missing>}" ;;
esac
if [ "$CONTROL_STATUS" != "closed" ] || [ "$CONTROL_OUTCOME" != "pass" ]; then
  fail "report-loop control must be closed/pass: step=$LOOP_STEP status=${CONTROL_STATUS:-<missing>} outcome=${CONTROL_OUTCOME:-<missing>}"
fi

if ! SYNTHESIS_ROWS="$(printf '%s\n' "$MATCHES" | jq -c \
  --arg root "$ROOT_ID" \
  --arg loop "$LOOP_STEP" \
  --arg step "$SYNTHESIS_STEP" \
  --arg attempt "$CURRENT_ATTEMPT" '
    [
      .[]
      | select((.metadata["gc.root_bead_id"] // "") == $root)
      | select((.metadata["gc.ralph_step_id"] // "") == $loop)
      | select((.metadata["gc.step_id"] // "") == $step)
      | select((.metadata["gc.scope_role"] // "") == "member")
      | select((.metadata["gc.attempt"] // "") == $attempt)
    ]
  ' 2>/dev/null)"; then
  fail "current synthesis metadata is malformed"
fi
SYNTHESIS_COUNT="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r 'length' 2>/dev/null)"
[ "$SYNTHESIS_COUNT" = "1" ] || fail \
  "expected exactly one current synthesis for $SYNTHESIS_STEP attempt $CURRENT_ATTEMPT, observed ${SYNTHESIS_COUNT:-<invalid>}"

SYNTHESIS_ID="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r '.[0].id // ""')"
SYNTHESIS_STATUS="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r '.[0].status // ""')"
SYNTHESIS_OUTCOME="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r '.[0].metadata["gc.outcome"] // ""')"
SYNTHESIS_REVIEWED_ATTEMPT="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r '.[0].metadata["code_review.reviewed_attempt"] // ""')"
SYNTHESIS_VERDICT="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r --arg key "$SYNTHESIS_VERDICT_KEY" '.[0].metadata[$key] // ""')"
SYNTHESIS_PATH="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r --arg key "$SYNTHESIS_PATH_KEY" '.[0].metadata[$key] // ""')"
SYNTHESIS_REPORT_PATH="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r '.[0].metadata["code_review.report_path"] // ""')"
SYNTHESIS_OUTPUT_PATH="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r '.[0].metadata["code_review.output_path"] // ""')"
SYNTHESIS_RECORDED_SHA256="$(printf '%s\n' "$SYNTHESIS_ROWS" | jq -r '.[0].metadata["gstack.synthesis.sha256"] // ""')"

[ -n "$SYNTHESIS_ID" ] || fail "current synthesis has no bead id"
if [ "$SYNTHESIS_STATUS" != "closed" ] || [ "$SYNTHESIS_OUTCOME" != "pass" ]; then
  fail "current synthesis must be closed/pass: status=${SYNTHESIS_STATUS:-<missing>} outcome=${SYNTHESIS_OUTCOME:-<missing>}"
fi
[ "$SYNTHESIS_REVIEWED_ATTEMPT" = "$CURRENT_ATTEMPT" ] || fail \
  "current synthesis reviewed attempt mismatch: expected=$CURRENT_ATTEMPT observed=${SYNTHESIS_REVIEWED_ATTEMPT:-<missing>}"
case "$SYNTHESIS_VERDICT" in
  "$SYNTHESIS_APPROVED_VERDICT"|iterate) ;;
  *) fail "current synthesis has unsupported $SYNTHESIS_VERDICT_KEY=${SYNTHESIS_VERDICT:-<missing>}" ;;
esac
if [ -z "$SYNTHESIS_PATH" ] || \
  [ "$SYNTHESIS_PATH" != "$SYNTHESIS_REPORT_PATH" ] || \
  [ "$SYNTHESIS_PATH" != "$SYNTHESIS_OUTPUT_PATH" ]; then
  fail "current synthesis paths disagree: selected=${SYNTHESIS_PATH:-<missing>} report=${SYNTHESIS_REPORT_PATH:-<missing>} output=${SYNTHESIS_OUTPUT_PATH:-<missing>}"
fi

if ! TERMINAL_ROWS="$(printf '%s\n' "$MATCHES" | jq -c \
  --arg root "$ROOT_ID" \
  --arg step "$LOOP_STEP" \
  --arg attempt "$CURRENT_ATTEMPT" '
    [
      .[]
      | select((.metadata["gc.root_bead_id"] // "") == $root)
      | select((.metadata["gc.ralph_step_id"] // "") == $step)
      | select((.metadata["gc.attempt"] // "") == $attempt)
      | select((.metadata["gc.review.report_terminal"] // "") == "true")
    ]
  ' 2>/dev/null)"; then
  fail "current report-terminal metadata is malformed"
fi
TERMINAL_COUNT="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r 'length' 2>/dev/null)"
[ "$TERMINAL_COUNT" = "1" ] || fail \
  "expected exactly one current report terminal for $LOOP_STEP attempt $CURRENT_ATTEMPT, observed ${TERMINAL_COUNT:-<invalid>}"

TERMINAL_STATUS="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].status // ""')"
TERMINAL_ID="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].id // ""')"
TERMINAL_OUTCOME="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["gc.outcome"] // ""')"
TERMINAL_VERDICT="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["code_review.verdict"] // ""')"
REPORT_PATH="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["code_review.report_path"] // ""')"
OUTPUT_PATH="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["code_review.output_path"] // ""')"
TERMINAL_SELECTED_PATH="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r --arg key "$TERMINAL_PATH_KEY" '.[0].metadata[$key] // ""')"
TERMINAL_REVIEWED_ATTEMPT="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["code_review.reviewed_attempt"] // ""')"
TERMINAL_SYNTHESIS_ID="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["gstack.report.synthesis_bead_id"] // ""')"
TERMINAL_SYNTHESIS_PATH="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["gstack.report.synthesis_path"] // ""')"
TERMINAL_SYNTHESIS_SHA256="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["gstack.report.synthesis_sha256"] // ""')"
TERMINAL_SEMANTIC_VERDICT="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["gstack.report.semantic_verdict"] // ""')"
TERMINAL_SEMANTIC_STATUS="$(printf '%s\n' "$TERMINAL_ROWS" | jq -r '.[0].metadata["gstack.report.semantic_status"] // ""')"

[ -n "$TERMINAL_ID" ] || fail "current report terminal has no bead id"
if [ "$TERMINAL_STATUS" != "closed" ] || [ "$TERMINAL_OUTCOME" != "pass" ]; then
  fail "current report terminal must be closed/pass: status=${TERMINAL_STATUS:-<missing>} outcome=${TERMINAL_OUTCOME:-<missing>}"
fi
[ "$TERMINAL_VERDICT" = "reported" ] || fail \
  "current report terminal must record code_review.verdict=reported, observed ${TERMINAL_VERDICT:-<missing>}"
if [ -z "$REPORT_PATH" ] || [ "$REPORT_PATH" != "$OUTPUT_PATH" ]; then
  fail "current report terminal report/output paths disagree: report=${REPORT_PATH:-<missing>} output=${OUTPUT_PATH:-<missing>}"
fi
[ "$TERMINAL_SELECTED_PATH" = "$REPORT_PATH" ] || fail \
  "$TERMINAL_PATH_KEY does not match current report terminal output: selected=${TERMINAL_SELECTED_PATH:-<missing>} report=$REPORT_PATH"
[ "$TERMINAL_REVIEWED_ATTEMPT" = "$CURRENT_ATTEMPT" ] || fail \
  "current report terminal reviewed attempt mismatch: expected=$CURRENT_ATTEMPT observed=${TERMINAL_REVIEWED_ATTEMPT:-<missing>}"
[ "$SELECTED_PATH" = "$REPORT_PATH" ] || fail \
  "$PATH_KEY does not match current report terminal: selected=$SELECTED_PATH current=$REPORT_PATH"

ARTIFACT_ROOT="$(metadata_value "$ROOT_JSON" "gc.build.artifact_root")"
if [ -z "$ARTIFACT_ROOT" ]; then
  ARTIFACT_ROOT="$(metadata_value "$ROOT_JSON" "gc.var.artifact_root")"
fi
[ -n "$ARTIFACT_ROOT" ] || fail "workflow root is missing artifact-root metadata"
case "$ARTIFACT_ROOT" in
  /*) ;;
  *)
    WORK_DIR="$(metadata_value "$ROOT_JSON" "gc.work_dir")"
    [ -n "$WORK_DIR" ] || fail "relative artifact root requires workflow gc.work_dir"
    LAUNCHER_ROOT="$(git -C "$WORK_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
    [ -n "$LAUNCHER_ROOT" ] || fail "relative artifact root has no readable launcher Git root"
    ARTIFACT_ROOT="$LAUNCHER_ROOT/$ARTIFACT_ROOT"
    ;;
esac
CANONICAL_ROOT="$(cd "$ARTIFACT_ROOT" 2>/dev/null && pwd -P)" || fail \
  "artifact root does not resolve: $ARTIFACT_ROOT"

canonical_artifact_file() {
  local raw_path="$1"
  local label="$2"
  local canonical_path
  case "$raw_path" in
    /*) ;;
    *) fail "$label must be absolute: $raw_path" ;;
  esac
  [ -f "$raw_path" ] || fail "$label is not a regular file: $raw_path"
  [ ! -L "$raw_path" ] || fail "$label must not be a symlink: $raw_path"
  canonical_path="$(cd "$(dirname "$raw_path")" 2>/dev/null && pwd -P)/$(basename "$raw_path")" || fail \
    "$label does not resolve: $raw_path"
  [ "$canonical_path" = "$raw_path" ] || fail \
    "$label is not canonical: path=$raw_path canonical=$canonical_path"
  case "$CANONICAL_ROOT" in
    /) ;;
    *)
      case "$canonical_path" in
        "$CANONICAL_ROOT"/*) ;;
        *) fail "$label must stay under artifact root: path=$canonical_path root=$CANONICAL_ROOT" ;;
      esac
      ;;
  esac
  printf '%s\n' "$canonical_path"
}

CANONICAL_SYNTHESIS="$(canonical_artifact_file "$SYNTHESIS_PATH" "current synthesis path")"
CANONICAL_REPORT="$(canonical_artifact_file "$REPORT_PATH" "current report path")"
[ "$CANONICAL_SYNTHESIS" != "$CANONICAL_REPORT" ] || fail \
  "current report terminal must write a distinct artifact from the synthesis: $CANONICAL_REPORT"

SYNTHESIS_SHA256="$(python3 - "$CANONICAL_SYNTHESIS" <<'PY'
import hashlib
import pathlib
import sys

print("sha256:" + hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)" || fail "could not compute current synthesis digest"
case "$SYNTHESIS_SHA256" in
  sha256:????????????????????????????????????????????????????????????????) ;;
  *) fail "computed current synthesis digest is malformed: $SYNTHESIS_SHA256" ;;
esac
[ "$SYNTHESIS_RECORDED_SHA256" = "$SYNTHESIS_SHA256" ] || fail \
  "current synthesis digest metadata is stale: recorded=${SYNTHESIS_RECORDED_SHA256:-<missing>} current=$SYNTHESIS_SHA256"
[ "$TERMINAL_SYNTHESIS_ID" = "$SYNTHESIS_ID" ] || fail \
  "current report terminal synthesis bead mismatch: recorded=${TERMINAL_SYNTHESIS_ID:-<missing>} current=$SYNTHESIS_ID"
[ "$TERMINAL_SYNTHESIS_PATH" = "$CANONICAL_SYNTHESIS" ] || fail \
  "current report terminal synthesis path mismatch: recorded=${TERMINAL_SYNTHESIS_PATH:-<missing>} current=$CANONICAL_SYNTHESIS"
[ "$TERMINAL_SYNTHESIS_SHA256" = "$SYNTHESIS_SHA256" ] || fail \
  "current report terminal synthesis digest mismatch: recorded=${TERMINAL_SYNTHESIS_SHA256:-<missing>} current=$SYNTHESIS_SHA256"
[ "$TERMINAL_SEMANTIC_VERDICT" = "$SYNTHESIS_VERDICT" ] || fail \
  "current report terminal semantic verdict mismatch: recorded=${TERMINAL_SEMANTIC_VERDICT:-<missing>} synthesis=$SYNTHESIS_VERDICT"

python3 - \
  "$CANONICAL_SYNTHESIS" \
  "$CANONICAL_REPORT" \
  "$SYNTHESIS_ID" \
  "$TERMINAL_ID" \
  "$CURRENT_ATTEMPT" \
  "$SYNTHESIS_VERDICT" \
  "$SYNTHESIS_APPROVED_VERDICT" \
  "$SYNTHESIS_SCHEMA" \
  "$REPORT_SCHEMA" \
  "$SYNTHESIS_STAGE" \
  "$REPORT_STAGE" \
  "$SYNTHESIS_SHA256" \
  "$TERMINAL_SEMANTIC_STATUS" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


(
    synthesis_path_raw,
    report_path_raw,
    synthesis_id,
    terminal_id,
    current_attempt,
    synthesis_verdict,
    approved_verdict,
    synthesis_schema,
    report_schema,
    synthesis_stage,
    report_stage,
    synthesis_sha256,
    terminal_semantic_status,
) = sys.argv[1:]
synthesis_path = Path(synthesis_path_raw)
report_path = Path(report_path_raw)


def fail(message: str) -> None:
    print(f"gstack-report-stage-check: {message}", file=sys.stderr)
    raise SystemExit(1)


def artifact(path: Path, *, label: str) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)(?P<body>.*)\Z", text, re.DOTALL)
    if not match:
        fail(f"{label} has no parseable YAML front matter: {path}")
    try:
        front = yaml.safe_load(match.group("front")) or {}
    except yaml.YAMLError as exc:
        fail(f"{label} front matter is invalid: {path}: {exc}")
    if not isinstance(front, dict):
        fail(f"{label} front matter must be a mapping: {path}")
    return front, match.group("body")


def producer(
    front: dict[str, Any],
    *,
    label: str,
    expected_id: str,
    expected_stage: str,
) -> None:
    value = front.get("producer")
    if not isinstance(value, dict):
        fail(f"{label} producer must be a mapping")
    if value.get("bead_id") != expected_id:
        fail(
            f"{label} producer bead mismatch: "
            f"expected={expected_id!r} observed={value.get('bead_id')!r}"
        )
    if value.get("stage") != expected_stage:
        fail(
            f"{label} producer stage mismatch: "
            f"expected={expected_stage!r} observed={value.get('stage')!r}"
        )
    observed_attempt = value.get("attempt")
    if isinstance(observed_attempt, bool) or str(observed_attempt) != current_attempt:
        fail(
            f"{label} producer attempt mismatch: "
            f"expected={current_attempt} observed={observed_attempt!r}"
        )


def required_sections(body: str, *, label: str, names: list[str]) -> None:
    matches = list(re.finditer(r"(?m)^## ([^\n]+)\s*$", body))
    observed = [match.group(1).strip() for match in matches]
    if observed != names:
        fail(f"{label} headings mismatch: expected={names!r} observed={observed!r}")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        if not body[match.end() : end].strip():
            fail(f"{label} section is empty: {names[index]}")


synthesis_front, synthesis_body = artifact(synthesis_path, label="synthesis artifact")
if synthesis_front.get("schema") != synthesis_schema:
    fail(
        "synthesis artifact schema mismatch: "
        f"expected={synthesis_schema!r} observed={synthesis_front.get('schema')!r}"
    )
producer(
    synthesis_front,
    label="synthesis artifact",
    expected_id=synthesis_id,
    expected_stage=synthesis_stage,
)
if synthesis_front.get("semantic_verdict") != synthesis_verdict:
    fail(
        "synthesis artifact semantic verdict mismatch: "
        f"row={synthesis_verdict!r} artifact={synthesis_front.get('semantic_verdict')!r}"
    )
synthesis_status = synthesis_front.get("status")
allowed_synthesis_statuses = (
    {"approved"}
    if synthesis_verdict == approved_verdict
    else {"changes_required", "blocked"}
)
if synthesis_status not in allowed_synthesis_statuses:
    fail(
        "synthesis artifact status contradicts its semantic verdict: "
        f"verdict={synthesis_verdict!r} status={synthesis_status!r}"
    )
required_sections(
    synthesis_body,
    label="synthesis artifact",
    names=["Summary", "Findings", "Evidence"],
)

report_front, report_body = artifact(report_path, label="report artifact")
if report_front.get("schema") != report_schema:
    fail(
        "report artifact schema mismatch: "
        f"expected={report_schema!r} observed={report_front.get('schema')!r}"
    )
producer(
    report_front,
    label="report artifact",
    expected_id=terminal_id,
    expected_stage=report_stage,
)
if report_front.get("semantic_verdict") != synthesis_verdict:
    fail(
        "report artifact semantic verdict mismatch: "
        f"synthesis={synthesis_verdict!r} report={report_front.get('semantic_verdict')!r}"
    )
report_status = report_front.get("status")
if report_status != synthesis_status:
    fail(
        "report artifact status does not preserve synthesis status: "
        f"synthesis={synthesis_status!r} report={report_status!r}"
    )
if terminal_semantic_status != report_status:
    fail(
        "current report terminal semantic status mismatch: "
        f"metadata={terminal_semantic_status!r} report={report_status!r}"
    )

trace = report_front.get("trace")
upstream = trace.get("upstream") if isinstance(trace, dict) else None
if not isinstance(upstream, list) or len(upstream) != 1 or not isinstance(upstream[0], dict):
    fail("report artifact must trace exactly one synthesis artifact")
entry = upstream[0]
expected_trace = {
    "path": str(synthesis_path),
    "hash": synthesis_sha256,
    "ids": [synthesis_id],
}
if entry != expected_trace:
    fail(
        "report artifact synthesis trace mismatch: "
        f"expected={expected_trace!r} observed={entry!r}"
    )
required_sections(
    report_body,
    label="report artifact",
    names=["Summary", "Findings", "Evidence", "Next Action"],
)
PY

echo "gstack current report stage valid: step=$LOOP_STEP attempt=$CURRENT_ATTEMPT path=$CANONICAL_REPORT"
