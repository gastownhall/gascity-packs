#!/usr/bin/env bash
set -euo pipefail

ROOT_ID="${GC_BEAD_ID:-}"
ATTEMPT="${GC_ITERATION:-}"

if [ -z "$ROOT_ID" ]; then
  echo "review check: GC_BEAD_ID is required" >&2
  exit 1
fi

if [ -z "$ATTEMPT" ]; then
  ATTEMPT="0"
fi

metadata_value() {
  local json="$1"
  local key="$2"
  printf '%s\n' "$json" | jq -r --arg key "$key" '
    (if type == "array" then (.[0] // {}) else . end)
    | .metadata[$key] // empty
  ' 2>/dev/null
}

git_top_level() {
  local candidate top
  candidate="$1"
  top="$(git -C "$candidate" rev-parse --show-toplevel 2>/dev/null)" || return 1
  (cd "$top" 2>/dev/null && pwd -P)
}

git_common_dir() {
  local top raw path
  top="$1"
  raw="$(git -C "$top" rev-parse --git-common-dir 2>/dev/null)" || return 1
  case "$raw" in
    /*) path="$raw" ;;
    *) path="$top/$raw" ;;
  esac
  (cd "$path" 2>/dev/null && pwd -P)
}

review_evidence_path() {
  local matches step key
  matches="$1"
  step="$2"
  key="$3"
  printf '%s\n' "$matches" | jq -r --arg step "$step" --arg key "$key" '
    [
      .[]
      | select(
          (.metadata["gc.step_id"] // "") == $step and
          (.metadata["gc.scope_role"] // "") == "member"
        )
    ][0].metadata[$key] // ""
  ' 2>/dev/null
}

validate_review_evidence_path() {
  local path label artifact_root expected_name canonical expected
  path="$1"
  label="$2"
  artifact_root="$3"
  expected_name="$4"
  case "$path" in
    /*) ;;
    *) implementation_provenance_fail "$label must be an absolute path: ${path:-<missing>}" ;;
  esac
  [ -f "$path" ] || implementation_provenance_fail "$label is not a regular file: $path"
  [ ! -L "$path" ] || implementation_provenance_fail "$label must not be a symlink: $path"
  canonical="$(cd "$(dirname "$path")" 2>/dev/null && pwd -P)/$(basename "$path")" || \
    implementation_provenance_fail "$label does not resolve: $path"
  case "$artifact_root" in
    /) expected="/$expected_name" ;;
    *) expected="$artifact_root/$expected_name" ;;
  esac
  [ "$canonical" = "$expected" ] || implementation_provenance_fail \
    "$label must use canonical path: path=$canonical expected=$expected"
}

ROOT_JSON="$(gc bd show "$ROOT_ID" --json 2>/dev/null || true)"
PARENT_ROOT="$(metadata_value "$ROOT_JSON" "gc.root_bead_id")"
if [ -z "$PARENT_ROOT" ]; then
  PARENT_ROOT="$ROOT_ID"
fi
PARENT_JSON="$ROOT_JSON"
if [ "$PARENT_ROOT" != "$ROOT_ID" ]; then
  PARENT_JSON="$(gc bd show "$PARENT_ROOT" --json 2>/dev/null || true)"
fi
STEP_ID="$(metadata_value "$ROOT_JSON" "gc.step_id")"
SCOPE_REF="$(metadata_value "$ROOT_JSON" "gc.scope_ref")"
if [ -z "$SCOPE_REF" ]; then
  SCOPE_REF="$(metadata_value "$ROOT_JSON" "gc.step_ref")"
fi
IMPLEMENTATION_PROVENANCE_REQUIRED="$(metadata_value "$ROOT_JSON" "gc.build.require_implementation_provenance")"
if [ -z "$IMPLEMENTATION_PROVENANCE_REQUIRED" ]; then
  IMPLEMENTATION_PROVENANCE_REQUIRED="$(metadata_value "$PARENT_JSON" "gc.build.require_implementation_provenance")"
fi
CURRENT_REPORT_TERMINAL_REQUIRED="$(metadata_value "$ROOT_JSON" "gc.review.require_current_report_terminal")"
ARTIFACT_PRODUCER_BINDING_REQUIRED="$(metadata_value "$ROOT_JSON" "gc.review.require_artifact_producer_binding")"
IMPLEMENTATION_PROVENANCE_VALIDATED=false
CURRENT_IMPLEMENTATION_SNAPSHOT=""
CURRENT_REVIEW_INPUT_SNAPSHOT=""

validate_declared_artifact() {
  local schema path_keys script_dir artifact_check
  schema="$(metadata_value "$ROOT_JSON" "gc.build.artifact_schema")"
  path_keys="$(metadata_value "$ROOT_JSON" "gc.build.artifact_path_keys")"

  if [ -z "$schema" ] && [ -z "$path_keys" ]; then
    return 0
  fi
  if [ -z "$schema" ] || [ -z "$path_keys" ]; then
    echo "review check: gc.build.artifact_schema and gc.build.artifact_path_keys must be declared together" >&2
    return 1
  fi

  script_dir="$(cd "$(dirname "$0")" && pwd)"
  artifact_check="$script_dir/build-artifact-valid.sh"
  if [ ! -x "$artifact_check" ]; then
    echo "review check: artifact validator is missing or not executable: $artifact_check" >&2
    return 1
  fi

  GC_BEAD_ID="$ROOT_ID" "$artifact_check"
}

implementation_provenance_fail() {
  echo "review check: implementation provenance $*" >&2
  return 1
}

validate_implementation_provenance() {
  local force="${1:-false}"
  local convoy_id convoy_json member_ids drain_policy member_id member_json
  local status outcome work_dir explicit_worktree canonical_worktree recorded_commit
  local resolved_commit head found_terminal_commit recorded_summary canonical_summary
  local root_summary candidate_worktree relative_path absolute_path allowed_path
  local seen allowed shared_worktree shared_head snapshot_members root_snapshot
  local launcher_work_dir launcher_top launcher_common_dir member_top member_common_dir
  local -a member_worktrees=()
  local -a allowed_untracked_paths=()

  [ "$IMPLEMENTATION_PROVENANCE_REQUIRED" = "true" ] || return 0
  if [ "$IMPLEMENTATION_PROVENANCE_VALIDATED" != "false" ] && [ "$force" != "true" ]; then
    return 0
  fi
  command -v python3 >/dev/null 2>&1 || implementation_provenance_fail \
    "requires python3 to compute the implementation snapshot"

  launcher_work_dir="$(metadata_value "$PARENT_JSON" "gc.work_dir")"
  [ -n "$launcher_work_dir" ] || implementation_provenance_fail \
    "requires gc.work_dir on workflow root $PARENT_ROOT"
  launcher_top="$(git_top_level "$launcher_work_dir")" || implementation_provenance_fail \
    "workflow root gc.work_dir is not inside a readable Git worktree: $launcher_work_dir"
  launcher_common_dir="$(git_common_dir "$launcher_top")" || implementation_provenance_fail \
    "workflow root Git common directory is unreadable: $launcher_top"

  convoy_id="$(metadata_value "$PARENT_JSON" "gc.build.implementation_convoy_id")"
  [ -n "$convoy_id" ] || implementation_provenance_fail \
    "requires gc.build.implementation_convoy_id on workflow root $PARENT_ROOT"

  convoy_json="$(gc convoy status "$convoy_id" --json 2>/dev/null || true)"
  if ! printf '%s\n' "$convoy_json" | jq -e --arg id "$convoy_id" '
    (.convoy.id == $id) and
    (.convoy.status == "closed") and
    (.children | type == "array" and length > 0) and
    (all(.children[]; (.id | type == "string" and length > 0) and .status == "closed")) and
    (([.children[].id] | unique | length) == (.children | length))
  ' >/dev/null 2>&1; then
    implementation_provenance_fail "convoy $convoy_id must be closed with unique closed members"
  fi
  member_ids="$(printf '%s\n' "$convoy_json" | jq -r '.children[].id')"
  drain_policy="$(metadata_value "$PARENT_JSON" "gc.var.drain_policy")"
  found_terminal_commit=false
  shared_worktree=""
  shared_head=""
  snapshot_members='[]'

  while IFS= read -r member_id; do
    [ -n "$member_id" ] || continue
    member_json="$(gc bd show "$member_id" --json 2>/dev/null || true)"
    status="$(printf '%s\n' "$member_json" | jq -r '
      (if type == "array" then (.[0] // {}) else . end) | .status // ""
    ' 2>/dev/null)"
    outcome="$(metadata_value "$member_json" "gc.outcome")"
    if [ "$status" != "closed" ] || [ "$outcome" != "pass" ]; then
      implementation_provenance_fail \
        "member $member_id must be closed/pass, got status=${status:-<missing>} outcome=${outcome:-<missing>}"
    fi

    work_dir="$(metadata_value "$member_json" "work_dir")"
    explicit_worktree="$(metadata_value "$member_json" "gc.implementation.worktree_path")"
    [ -n "$work_dir" ] || implementation_provenance_fail "member $member_id is missing work_dir"
    [ -n "$explicit_worktree" ] || implementation_provenance_fail \
      "member $member_id is missing gc.implementation.worktree_path"
    canonical_worktree="$(cd "$work_dir" 2>/dev/null && pwd -P)" || implementation_provenance_fail \
      "member $member_id work_dir does not resolve: $work_dir"
    member_top="$(git_top_level "$canonical_worktree")" || implementation_provenance_fail \
      "member $member_id work_dir is not inside a readable Git worktree: $canonical_worktree"
    if [ "$member_top" != "$canonical_worktree" ]; then
      implementation_provenance_fail \
        "member $member_id work_dir must equal its Git worktree root: recorded=$canonical_worktree top=$member_top"
    fi
    if [ "$(cd "$explicit_worktree" 2>/dev/null && pwd -P || true)" != "$canonical_worktree" ]; then
      implementation_provenance_fail \
        "member $member_id work_dir and gc.implementation.worktree_path disagree"
    fi
    member_common_dir="$(git_common_dir "$member_top")" || implementation_provenance_fail \
      "member $member_id Git common directory is unreadable: $member_top"
    if [ "$member_common_dir" != "$launcher_common_dir" ]; then
      implementation_provenance_fail \
        "member $member_id Git common directory does not match launcher repository: member=$member_common_dir launcher=$launcher_common_dir"
    fi

    recorded_commit="$(metadata_value "$member_json" "gc.implementation.commit")"
    case "$recorded_commit" in
      *[!0-9a-fA-F]*|'') implementation_provenance_fail \
        "member $member_id gc.implementation.commit must be hexadecimal" ;;
    esac
    [ "${#recorded_commit}" -eq 40 ] || implementation_provenance_fail \
      "member $member_id gc.implementation.commit must be a full 40-character commit"
    resolved_commit="$(git -C "$canonical_worktree" rev-parse --verify "${recorded_commit}^{commit}" 2>/dev/null)" || \
      implementation_provenance_fail "member $member_id recorded commit does not resolve"
    snapshot_members="$(printf '%s\n' "$snapshot_members" | jq -c \
      --arg id "$member_id" --arg commit "$resolved_commit" \
      '. + [{id: $id, commit: $commit}]')" || implementation_provenance_fail \
        "could not record the implementation snapshot for member $member_id"
    head="$(git -C "$canonical_worktree" rev-parse HEAD 2>/dev/null)" || \
      implementation_provenance_fail "member $member_id worktree HEAD is unreadable"

    if [ "$drain_policy" = "same-session" ]; then
      if [ -z "$shared_worktree" ]; then
        shared_worktree="$canonical_worktree"
        shared_head="$head"
      elif [ "$canonical_worktree" != "$shared_worktree" ] || [ "$head" != "$shared_head" ]; then
        implementation_provenance_fail \
          "same-session members must share one canonical worktree and terminal HEAD: expected=$shared_worktree@$shared_head observed=$canonical_worktree@$head"
      fi
      git -C "$canonical_worktree" merge-base --is-ancestor "$resolved_commit" "$head" 2>/dev/null || \
        implementation_provenance_fail \
          "member $member_id recorded commit is not an ancestor of shared worktree HEAD $head"
      if [ "$resolved_commit" = "$head" ]; then
        found_terminal_commit=true
      fi
    elif [ "$resolved_commit" != "$head" ]; then
      implementation_provenance_fail \
        "member $member_id recorded commit $resolved_commit does not equal worktree HEAD $head"
    fi

    if ! git -C "$canonical_worktree" diff --quiet "$head" --; then
      implementation_provenance_fail \
        "member $member_id tracked bytes differ from recorded worktree HEAD $head"
    fi

    member_worktrees+=("$canonical_worktree")
    recorded_summary="$(metadata_value "$member_json" "gc.implementation.summary_path")"
    [ -n "$recorded_summary" ] || implementation_provenance_fail \
      "member $member_id is missing gc.implementation.summary_path"
    case "$recorded_summary" in
      /*) ;;
      *) implementation_provenance_fail \
        "member $member_id gc.implementation.summary_path must be absolute" ;;
    esac
    [ -f "$recorded_summary" ] || implementation_provenance_fail \
      "member $member_id gc.implementation.summary_path is not a file: $recorded_summary"
    [ ! -L "$recorded_summary" ] || implementation_provenance_fail \
      "member $member_id gc.implementation.summary_path must not be a symlink: $recorded_summary"
    canonical_summary="$(cd "$(dirname "$recorded_summary")" 2>/dev/null && pwd -P)/$(basename "$recorded_summary")" || \
      implementation_provenance_fail \
        "member $member_id gc.implementation.summary_path does not resolve: $recorded_summary"
    case "$canonical_summary" in
      "$canonical_worktree"/*) allowed_untracked_paths+=("$canonical_summary") ;;
      *) implementation_provenance_fail \
        "member $member_id gc.implementation.summary_path must be inside its authoritative worktree" ;;
    esac
  done <<<"$member_ids"

  if [ "$drain_policy" = "same-session" ] && [ "$found_terminal_commit" != "true" ]; then
    implementation_provenance_fail \
      "same-session members do not bind the terminal shared worktree HEAD"
  fi

  if ! CURRENT_IMPLEMENTATION_SNAPSHOT="$(printf '%s' "$snapshot_members" | python3 -c '
import hashlib
import json
import sys

members = json.load(sys.stdin)
members = [
    {"id": str(member["id"]), "commit": str(member["commit"])}
    for member in members
]
members.sort(key=lambda member: member["id"])
payload = json.dumps(members, sort_keys=True, separators=(",", ":")).encode("utf-8")
print("sha256:" + hashlib.sha256(payload).hexdigest())
')"; then
    implementation_provenance_fail "could not compute the current implementation snapshot"
  fi

  root_snapshot="$(metadata_value "$PARENT_JSON" "gc.build.implementation_snapshot")"
  if [ "$root_snapshot" != "$CURRENT_IMPLEMENTATION_SNAPSHOT" ]; then
    implementation_provenance_fail \
      "workflow root gc.build.implementation_snapshot does not match current implementation: recorded=${root_snapshot:-<missing>} current=$CURRENT_IMPLEMENTATION_SNAPSHOT"
  fi

  root_summary="$(metadata_value "$PARENT_JSON" "gc.build.implementation_summary_path")"
  [ -n "$root_summary" ] || implementation_provenance_fail \
    "workflow root is missing gc.build.implementation_summary_path"
  [ -f "$root_summary" ] || implementation_provenance_fail \
    "gc.build.implementation_summary_path is not a file: $root_summary"
  [ ! -L "$root_summary" ] || implementation_provenance_fail \
    "gc.build.implementation_summary_path must not be a symlink: $root_summary"
  canonical_summary="$(cd "$(dirname "$root_summary")" 2>/dev/null && pwd -P)/$(basename "$root_summary")" || \
    implementation_provenance_fail \
      "gc.build.implementation_summary_path does not resolve: $root_summary"
  for candidate_worktree in "${member_worktrees[@]}"; do
    case "$canonical_summary" in
      "$candidate_worktree"/*) allowed_untracked_paths+=("$canonical_summary") ;;
    esac
  done

  local -a checked_worktrees=()
  for candidate_worktree in "${member_worktrees[@]}"; do
    seen=false
    for canonical_worktree in "${checked_worktrees[@]}"; do
      if [ "$candidate_worktree" = "$canonical_worktree" ]; then
        seen=true
        break
      fi
    done
    [ "$seen" = "false" ] || continue
    checked_worktrees+=("$candidate_worktree")

    while IFS= read -r -d '' absolute_path; do
      relative_path="${absolute_path#"$candidate_worktree/"}"
      if ! git -C "$candidate_worktree" ls-files --error-unmatch -- "$relative_path" >/dev/null 2>&1; then
        implementation_provenance_fail \
          "unexpected untracked worktree path in $candidate_worktree: $relative_path"
        return 1
      fi
    done < <(find "$candidate_worktree" \
      -path "$candidate_worktree/.git" -prune -o \
      \( -type l -o -type p -o -type s -o -type b -o -type c \) -print0)

    while IFS= read -r -d '' relative_path; do
      absolute_path="$candidate_worktree/$relative_path"
      case "$relative_path" in
        .pytest_cache/*|*/.pytest_cache/*)
          if [ -f "$absolute_path" ] && [ ! -L "$absolute_path" ]; then
            continue
          fi
          ;;
      esac
      allowed=false
      for allowed_path in "${allowed_untracked_paths[@]}"; do
        if [ "$absolute_path" = "$allowed_path" ]; then
          allowed=true
          break
        fi
      done
      if [ "$allowed" != "true" ]; then
        implementation_provenance_fail \
          "unexpected untracked worktree path in $candidate_worktree: $relative_path"
        return 1
      fi
    done < <(git -C "$candidate_worktree" ls-files --others -z)
  done

  local script_dir validator provenance_verifier provenance_output
  script_dir="$(cd "$(dirname "$0")" && pwd)"
  validator="$script_dir/../validate_build_artifact.py"
  provenance_verifier="$script_dir/../verify_implementation_provenance.py"
  [ -f "$validator" ] || implementation_provenance_fail \
    "artifact validator is missing: $validator"
  [ -f "$provenance_verifier" ] || implementation_provenance_fail \
    "shared verifier is missing: $provenance_verifier"
  if ! provenance_output="$(python3 "$provenance_verifier" \
    --root-id "$PARENT_ROOT" \
    --expected-snapshot "$CURRENT_IMPLEMENTATION_SNAPSHOT" \
    --expected-summary "$root_summary" \
    --validator "$validator" 2>&1)"; then
    implementation_provenance_fail "shared verification failed: $provenance_output"
  fi
  CURRENT_REVIEW_INPUT_SNAPSHOT="$(printf '%s\n' "$provenance_output" | jq -r \
    '.review_input_snapshot // ""' 2>/dev/null)"
  case "$CURRENT_REVIEW_INPUT_SNAPSHOT" in
    sha256:????????????????????????????????????????????????????????????????) ;;
    *) implementation_provenance_fail \
      "shared verifier returned an invalid review input snapshot" ;;
  esac
  IMPLEMENTATION_PROVENANCE_VALIDATED=true
}

approve() {
  local message="$1"
  local approved_snapshot="$CURRENT_IMPLEMENTATION_SNAPSHOT"
  local approved_review_input="$CURRENT_REVIEW_INPUT_SNAPSHOT"
  validate_declared_artifact
  validate_implementation_provenance true
  if [ -n "$approved_snapshot" ] && {
    [ "$approved_snapshot" != "$CURRENT_IMPLEMENTATION_SNAPSHOT" ] ||
      [ "$approved_review_input" != "$CURRENT_REVIEW_INPUT_SNAPSHOT" ];
  }; then
    implementation_provenance_fail \
      "implementation changed during final approval; a fresh review iteration is required"
    return 1
  fi
  echo "$message"
  exit 0
}

MATCHES="$(gc bd list --all --metadata-field "gc.root_bead_id=$PARENT_ROOT" --json --limit=0 2>/dev/null || printf '[]')"

if ! CURRENT_MATCHES="$(printf '%s\n' "$MATCHES" | jq -c \
  --arg root "$PARENT_ROOT" \
  --arg attempt "$ATTEMPT" \
  --arg scope "$SCOPE_REF" \
  --arg step "$STEP_ID" '
  def current_loop:
    select(.metadata["gc.root_bead_id"] == $root)
    | select(($attempt == "") or ((.metadata["gc.attempt"] // "") == $attempt))
    | select(
        if $attempt != "" and $step != "" then
          ((.metadata["gc.ralph_step_id"] // "") == $step) or
          ((.metadata["gc.step_id"] // "") == $step) or
          (((.metadata["gc.scope_ref"] // "") | startswith($step + ".iteration.")))
        elif $attempt != "" and $scope != "" then
          ((.metadata["gc.scope_ref"] // "") == $scope) or
          ((.metadata["gc.step_ref"] // "") == $scope)
        elif $step != "" then
          ((.metadata["gc.ralph_step_id"] // "") == $step) or
          (((.metadata["gc.scope_ref"] // "") | startswith($step + ".iteration.")))
        elif $scope != "" then
          ((.metadata["gc.scope_ref"] // "") == $scope)
        else
          true
        end
      );
  [.[] | current_loop] | sort_by([.updated_at // "", .id // ""])
')"; then
  echo "review check: current-attempt review metadata is malformed" >&2
  exit 1
fi

validate_current_report_terminal() {
  local rows count status outcome attempt verdict report_path output_path
  local artifact_root launcher_work_dir launcher_top canonical_root canonical_report
  local root_report_path root_gap_path root_formula producer_rows producer_count
  local script_dir validator validation_output

  rows="$(printf '%s\n' "$CURRENT_MATCHES" | jq -c '
    [.[] | select((.metadata["gc.review.report_terminal"] // "") == "true")]
  ' 2>/dev/null)" || {
    echo "review check: current report terminal metadata is malformed" >&2
    return 1
  }
  count="$(printf '%s\n' "$rows" | jq -r 'length' 2>/dev/null)"
  if [ "$count" != "1" ]; then
    echo "review check: expected exactly one current report terminal, observed ${count:-<invalid>}" >&2
    return 1
  fi

  status="$(printf '%s\n' "$rows" | jq -r '.[0].status // ""')"
  outcome="$(printf '%s\n' "$rows" | jq -r '.[0].metadata["gc.outcome"] // ""')"
  attempt="$(printf '%s\n' "$rows" | jq -r '.[0].metadata["gc.attempt"] // ""')"
  verdict="$(printf '%s\n' "$rows" | jq -r '.[0].metadata["code_review.verdict"] // ""')"
  report_path="$(printf '%s\n' "$rows" | jq -r '.[0].metadata["code_review.report_path"] // ""')"
  output_path="$(printf '%s\n' "$rows" | jq -r '.[0].metadata["code_review.output_path"] // ""')"

  if [ "$status" != "closed" ] || [ "$outcome" != "pass" ] || [ "$attempt" != "$ATTEMPT" ]; then
    echo "review check: current report terminal must be closed/pass for attempt $ATTEMPT: status=${status:-<missing>} outcome=${outcome:-<missing>} attempt=${attempt:-<missing>}" >&2
    return 1
  fi
  if [ "$verdict" != "reported" ]; then
    echo "review check: current report terminal must record code_review.verdict=reported, observed ${verdict:-<missing>}" >&2
    return 1
  fi
  if [ -z "$report_path" ] || [ "$report_path" != "$output_path" ]; then
    echo "review check: current report terminal report/output paths disagree: report=${report_path:-<missing>} output=${output_path:-<missing>}" >&2
    return 1
  fi

  artifact_root="$(metadata_value "$PARENT_JSON" "gc.build.artifact_root")"
  if [ -z "$artifact_root" ]; then
    artifact_root="$(metadata_value "$PARENT_JSON" "gc.var.artifact_root")"
  fi
  if [ -z "$artifact_root" ]; then
    artifact_root="$(metadata_value "$PARENT_JSON" "gc.build.code_review_artifact_root")"
  fi
  [ -n "$artifact_root" ] || {
    echo "review check: current report terminal requires workflow artifact root metadata" >&2
    return 1
  }
  case "$artifact_root" in
    /*) ;;
    *)
      launcher_work_dir="$(metadata_value "$PARENT_JSON" "gc.work_dir")"
      launcher_top="$(git_top_level "$launcher_work_dir")" || {
        echo "review check: current report terminal cannot resolve launcher root for relative artifact root" >&2
        return 1
      }
      artifact_root="$launcher_top/$artifact_root"
      ;;
  esac
  canonical_root="$(cd "$artifact_root" 2>/dev/null && pwd -P)" || {
    echo "review check: current report terminal artifact root does not resolve: $artifact_root" >&2
    return 1
  }

  case "$report_path" in
    /*) ;;
    *)
      echo "review check: current report terminal path must be absolute: $report_path" >&2
      return 1
      ;;
  esac
  [ -f "$report_path" ] || {
    echo "review check: current report terminal path is not a regular file: $report_path" >&2
    return 1
  }
  [ ! -L "$report_path" ] || {
    echo "review check: current report terminal path must not be a symlink: $report_path" >&2
    return 1
  }
  canonical_report="$(cd "$(dirname "$report_path")" 2>/dev/null && pwd -P)/$(basename "$report_path")" || {
    echo "review check: current report terminal path does not resolve: $report_path" >&2
    return 1
  }
  if [ "$canonical_report" != "$report_path" ]; then
    echo "review check: current report terminal path is not canonical: path=$report_path canonical=$canonical_report" >&2
    return 1
  fi
  case "$canonical_report" in
    "$canonical_root"/*) ;;
    *)
      echo "review check: current report terminal path must stay under canonical artifact root: path=$canonical_report root=$canonical_root" >&2
      return 1
      ;;
  esac

  root_report_path="$(metadata_value "$PARENT_JSON" "gc.build.code_review_report_path")"
  root_gap_path="$(metadata_value "$PARENT_JSON" "gc.build.gap_analysis_report_path")"
  root_formula="$(metadata_value "$PARENT_JSON" "gc.formula_name")"
  if ! producer_rows="$(printf '%s\n' "$CURRENT_MATCHES" | jq -c '
    . as $rows
    | [
        .[]
        | select((.metadata["gc.review.report_terminal"] // "") == "true")
      ][0] as $terminal
    | [
        $rows[]
        | . as $control
        | select(
            [
              $terminal.dependencies[]?
              | select((.type // "") == "blocks")
              | .depends_on_id // ""
            ]
            | index($control.id // "") != null
          )
        | $rows[]
        | . as $producer
        | select(
            [
              $control.dependencies[]?
              | select((.type // "") == "blocks")
              | .depends_on_id // ""
            ]
            | index($producer.id // "") != null
          )
        | ((.metadata["gc.build.artifact_path_keys"] // "")
            | split(",") | map(gsub("\\s"; ""))) as $path_keys
        | select(
            (($path_keys | index("gc.build.code_review_report_path")) != null) or
            (($path_keys | index("gc.build.gap_analysis_report_path")) != null)
          )
        | {
            control: {
              id: ($control.id // ""),
              status: ($control.status // ""),
              metadata: {
                "gc.outcome": ($control.metadata["gc.outcome"] // ""),
                "gc.attempt": ($control.metadata["gc.attempt"] // ""),
                "gc.scope_role": ($control.metadata["gc.scope_role"] // ""),
                "gc.kind": ($control.metadata["gc.kind"] // ""),
                "gc.control_for": ($control.metadata["gc.control_for"] // ""),
                "gc.step_id": ($control.metadata["gc.step_id"] // "")
              }
            },
            producer: {
              id: ($producer.id // ""),
              status: ($producer.status // ""),
              metadata: {
                "gc.outcome": ($producer.metadata["gc.outcome"] // ""),
                "gc.attempt": ($producer.metadata["gc.attempt"] // ""),
                "gc.scope_role": ($producer.metadata["gc.scope_role"] // ""),
                "gc.step_id": ($producer.metadata["gc.step_id"] // ""),
                "gc.step_ref": ($producer.metadata["gc.step_ref"] // ""),
                "gc.run_target": ($producer.metadata["gc.run_target"] // ""),
                "gc.build.artifact_schema": ($producer.metadata["gc.build.artifact_schema"] // ""),
                "gc.build.artifact_path_keys": ($producer.metadata["gc.build.artifact_path_keys"] // ""),
                "code_review.review_verdict": ($producer.metadata["code_review.review_verdict"] // ""),
                "code_review.review_report_path": ($producer.metadata["code_review.review_report_path"] // ""),
                "code_review.gap_verdict": ($producer.metadata["code_review.gap_verdict"] // ""),
                "code_review.gap_report_path": ($producer.metadata["code_review.gap_report_path"] // ""),
                "code_review.output_path": ($producer.metadata["code_review.output_path"] // "")
              }
            }
          }
      ]
  ' 2>/dev/null)"; then
    echo "review check: current code-review producer metadata is malformed" >&2
    return 1
  fi
  producer_count="$(printf '%s\n' "$producer_rows" | jq -r 'length' 2>/dev/null)"

  # The shared report-terminal gate also serves gstack QA/readiness loops.
  # Code-review loops opt into stronger binding explicitly; retain legacy
  # detection for graphs that expose a code-review producer or whose terminal
  # claims the workflow root's canonical code-review path.
  if [ "$ARTIFACT_PRODUCER_BINDING_REQUIRED" = "true" ] || \
    [ "$producer_count" != "0" ] || \
    { [ -n "$root_report_path" ] && [ "$root_report_path" = "$report_path" ]; }; then
    script_dir="$(cd "$(dirname "$0")" && pwd)"
    validator="$script_dir/../validate_build_artifact.py"
    [ -f "$validator" ] || {
      echo "review check: current code-review artifact validator is missing: $validator" >&2
      return 1
    }
    launcher_top=""
    launcher_work_dir="$(metadata_value "$PARENT_JSON" "gc.work_dir")"
    if [ -n "$launcher_work_dir" ]; then
      launcher_top="$(git_top_level "$launcher_work_dir")" || {
        echo "review check: current code-review producer cannot resolve launcher root from workflow gc.work_dir: $launcher_work_dir" >&2
        return 1
      }
    fi
    if ! validation_output="$(python3 - \
      "$validator" "$producer_rows" "$PARENT_ROOT" "$root_formula" \
      "$ATTEMPT" "$canonical_root" "$launcher_top" "$canonical_report" \
      "$root_report_path" "$root_gap_path" 2>&1 <<'PY'
import hashlib
import json
import stat
import sys
from pathlib import Path


class GateError(Exception):
    pass


validator_path = Path(sys.argv[1])
producer_pairs = json.loads(sys.argv[2])
workflow_root_id = sys.argv[3]
root_formula = sys.argv[4]
expected_attempt = sys.argv[5]
artifact_root = Path(sys.argv[6])
launcher_root = Path(sys.argv[7]) if sys.argv[7] else None
terminal_report = sys.argv[8]
root_report = sys.argv[9]
root_gap_report = sys.argv[10]
sys.path.insert(0, str(validator_path.parent))

import validate_build_artifact  # noqa: E402


PATH_CONTRACTS = {
    "gc.build.code_review_report_path": {
        "label": "code-review",
        "path_metadata": "code_review.review_report_path",
        "verdict_metadata": "code_review.review_verdict",
    },
    "gc.build.gap_analysis_report_path": {
        "label": "gap-analysis",
        "path_metadata": "code_review.gap_report_path",
        "verdict_metadata": "code_review.gap_verdict",
    },
}

IDENTITY_CONTRACTS = {
    "bmad": {
        "workflow_formula": "bmad-review",
        "methodology_name": "bmad-review",
        "producer_formula": "bmad-code-review-flow",
        "producers": {
            "gc.build.code_review_report_path": "synthesize-bmad-review",
        },
    },
    "compound-engineering": {
        "workflow_formula": "compound-review",
        "methodology_name": "compound-review",
        "producer_formula": "compound-code-review",
        "producers": {
            "gc.build.code_review_report_path": "synthesize-code-review",
        },
    },
    "gstack": {
        "workflow_formula": "gstack-review",
        "methodology_name": "gstack-review",
        "producer_formula": "gstack-code-review",
        "producers": {
            "gc.build.code_review_report_path": "synthesize-code-review",
        },
    },
    "superpowers": {
        "workflow_formula": root_formula,
        "methodology_name": "superpowers-code-review",
        "producer_formula": "superpowers-code-review",
        "producers": {
            "gc.build.code_review_report_path": "request-code-review",
            "gc.build.gap_analysis_report_path": "gap-analysis-review",
        },
    },
}


def metadata(row, key):
    value = (row.get("metadata") or {}).get(key, "")
    return str(value) if isinstance(value, (str, int)) else ""


def declared_path_keys(row):
    return {
        value.strip()
        for value in metadata(row, "gc.build.artifact_path_keys").split(",")
        if value.strip()
    }


def rows_for(path_key):
    return [
        pair
        for pair in producer_pairs
        if path_key in declared_path_keys(pair.get("producer") or {})
    ]


def file_fingerprint(path):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise GateError(f"not a regular non-symlink file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.lstat()

    def fields(value):
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    if fields(before) != fields(after) or not stat.S_ISREG(after.st_mode):
        raise GateError(f"file changed while fingerprinting: {path}")
    return (*fields(after), digest.hexdigest())


def canonical_artifact_path(raw_path, label):
    if not raw_path:
        raise GateError(f"workflow root is missing {label} artifact path")
    path = Path(raw_path)
    if not path.is_absolute():
        raise GateError(f"{label} artifact path must be absolute: {raw_path}")
    fingerprint = file_fingerprint(path)
    canonical = path.resolve(strict=True)
    if str(canonical) != raw_path:
        raise GateError(
            f"{label} artifact path must be canonical: path={raw_path} canonical={canonical}"
        )
    try:
        canonical.relative_to(artifact_root)
    except ValueError as exc:
        raise GateError(
            f"{label} artifact path must stay under canonical artifact root: "
            f"path={canonical} root={artifact_root}"
        ) from exc
    return canonical, fingerprint


def mapping(value):
    return value if isinstance(value, dict) else {}


def pin_sha256_upstreams(artifact, artifact_path, upstream_roots, pinned):
    for index, entry in enumerate(artifact.upstream):
        hash_value = str(entry.get("hash", ""))
        if not hash_value.lower().startswith("sha256:"):
            continue
        path = Path(str(entry.get("path", "")))
        if not path.is_absolute():
            path = validate_build_artifact.resolve_relative_sha256_upstream(
                path,
                index=index,
                artifact_path=artifact_path,
                upstream_roots=upstream_roots,
            )
        pinned.setdefault(path, file_fingerprint(path))


def validate_producer(path_key, pair, contract, upstream_roots, pinned):
    path_contract = PATH_CONTRACTS[path_key]
    label = path_contract["label"]
    expected_stage = contract["producers"][path_key]
    control = pair.get("control") or {}
    row = pair.get("producer") or {}
    control_status = str(control.get("status", ""))
    control_outcome = metadata(control, "gc.outcome")
    control_attempt = metadata(control, "gc.attempt")
    control_role = metadata(control, "gc.scope_role")
    control_kind = metadata(control, "gc.kind")
    producer_step_ref = metadata(row, "gc.step_ref")
    producer_step_id = metadata(row, "gc.step_id")
    control_for = metadata(control, "gc.control_for")
    control_step_id = metadata(control, "gc.step_id")
    if (
        control_status != "closed"
        or control_outcome != "pass"
        or control_attempt != expected_attempt
        or control_role != "control"
        or control_kind != "scope-check"
        or not producer_step_ref
        or control_for != producer_step_ref
        or control_step_id != producer_step_id
    ):
        raise GateError(
            f"current {label} scope-check must bind the current producer: "
            f"status={control_status or '<missing>'} "
            f"outcome={control_outcome or '<missing>'} "
            f"attempt={control_attempt or '<missing>'} "
            f"role={control_role or '<missing>'} "
            f"kind={control_kind or '<missing>'} "
            f"control_for={control_for or '<missing>'} "
            f"producer_step_ref={producer_step_ref or '<missing>'} "
            f"control_step_id={control_step_id or '<missing>'} "
            f"producer_step_id={producer_step_id or '<missing>'}"
        )

    row_status = str(row.get("status", ""))
    row_outcome = metadata(row, "gc.outcome")
    row_attempt = metadata(row, "gc.attempt")
    row_role = metadata(row, "gc.scope_role")
    if (
        row_status != "closed"
        or row_outcome != "pass"
        or row_attempt != expected_attempt
        or row_role != "member"
    ):
        raise GateError(
            f"current {label} producer must be a closed/pass member for attempt "
            f"{expected_attempt}: status={row_status or '<missing>'} "
            f"outcome={row_outcome or '<missing>'} "
            f"attempt={row_attempt or '<missing>'} role={row_role or '<missing>'}"
        )
    if metadata(row, "gc.build.artifact_schema") != "gc.build.review.v1":
        raise GateError(
            f"current {label} producer must declare gc.build.review.v1"
        )

    observed_stage = producer_step_id.rsplit(".", 1)[-1] if producer_step_id else ""
    run_target = metadata(row, "gc.run_target")
    observed_pack = run_target.split(".", 1)[0] if "." in run_target else ""
    if observed_stage != expected_stage or observed_pack != pack:
        raise GateError(
            f"current {label} producer identity mismatch: pack={observed_pack or '<missing>'} "
            f"stage={observed_stage or '<missing>'} expected_pack={pack} "
            f"expected_stage={expected_stage}"
        )

    expected_root_path = root_report if path_key == "gc.build.code_review_report_path" else root_gap_report
    artifact_path_raw = metadata(row, path_contract["path_metadata"])
    output_path = metadata(row, "code_review.output_path")
    if (
        not artifact_path_raw
        or artifact_path_raw != output_path
        or output_path != expected_root_path
        or (
            path_key == "gc.build.code_review_report_path"
            and output_path != terminal_report
        )
    ):
        raise GateError(
            f"current {label} producer, terminal, and workflow-root paths must agree: "
            f"producer_report={artifact_path_raw or '<missing>'} "
            f"producer_output={output_path or '<missing>'} "
            f"terminal={terminal_report} root={expected_root_path or '<missing>'}"
        )

    artifact_path, artifact_fingerprint = canonical_artifact_path(
        expected_root_path, label
    )
    pinned.setdefault(artifact_path, artifact_fingerprint)
    text = artifact_path.read_text(encoding="utf-8")
    artifact = validate_build_artifact.validate_artifact_text(
        text,
        expected_schema="gc.build.review.v1",
        enforce_review_status_coverage=True,
        artifact_path=artifact_path,
        upstream_roots=upstream_roots,
    )
    pin_sha256_upstreams(artifact, artifact_path, upstream_roots, pinned)
    artifact = validate_build_artifact.validate_artifact_text(
        text,
        expected_schema="gc.build.review.v1",
        verify_absolute_upstreams=True,
        enforce_review_status_coverage=True,
        artifact_path=artifact_path,
        upstream_roots=upstream_roots,
    )

    front = artifact.front_matter
    producer = mapping(front.get("producer"))
    observed_attempt = producer.get("attempt")
    if str(observed_attempt) != expected_attempt:
        raise GateError(
            f"artifact producer.attempt for current {label} producer does not "
            "match current review attempt: "
            f"expected={expected_attempt} observed={observed_attempt!r}"
        )

    expected_identity = {
        "workflow.id": workflow_root_id,
        "workflow.formula": contract["workflow_formula"],
        "methodology.pack": pack,
        "methodology.name": contract["methodology_name"],
        "producer.formula": contract["producer_formula"],
        "producer.stage": expected_stage,
    }
    observed_identity = {
        "workflow.id": mapping(front.get("workflow")).get("id"),
        "workflow.formula": mapping(front.get("workflow")).get("formula"),
        "methodology.pack": mapping(front.get("methodology")).get("pack"),
        "methodology.name": mapping(front.get("methodology")).get("name"),
        "producer.formula": producer.get("formula"),
        "producer.stage": producer.get("stage"),
    }
    if observed_identity != expected_identity:
        raise GateError(
            f"artifact identity mismatch for current {label} producer: "
            f"expected={expected_identity!r} observed={observed_identity!r}"
        )

    artifact_status = str(front.get("status", ""))
    if artifact_status not in {"approved", "changes_required", "blocked"}:
        raise GateError(
            "artifact terminal status must be approved, changes_required, or "
            f"blocked; observed={artifact_status or '<missing>'}"
        )
    producer_verdict = metadata(row, path_contract["verdict_metadata"])
    verdict_matches = (
        producer_verdict == "approve" and artifact_status == "approved"
    ) or (
        producer_verdict == "iterate"
        and artifact_status in {"changes_required", "blocked"}
    )
    if not verdict_matches:
        raise GateError(
            f"artifact status/verdict mismatch for current {label} producer: "
            f"status={artifact_status or '<missing>'} "
            f"verdict={producer_verdict or '<missing>'}"
        )


try:
    if not isinstance(producer_pairs, list):
        raise GateError("current code-review producer metadata must be a list")
    code_rows = rows_for("gc.build.code_review_report_path")
    if len(code_rows) != 1:
        raise GateError(
            "expected exactly one current code-review producer directly required "
            f"by the report terminal, observed {len(code_rows)}"
        )

    run_target = metadata(code_rows[0].get("producer") or {}, "gc.run_target")
    pack = run_target.split(".", 1)[0] if "." in run_target else ""
    contract = IDENTITY_CONTRACTS.get(pack)
    if contract is None:
        raise GateError(
            f"current code-review producer has unsupported pack identity: {pack or '<missing>'}"
        )
    if pack == "superpowers" and not root_formula:
        raise GateError(
            "current Superpowers code-review producer requires gc.formula_name on the workflow root"
        )

    gap_rows = rows_for("gc.build.gap_analysis_report_path")
    expected_gap = "gc.build.gap_analysis_report_path" in contract["producers"]
    if expected_gap and len(gap_rows) != 1:
        raise GateError(
            "expected exactly one current gap-analysis producer directly required "
            f"by the report terminal, observed {len(gap_rows)}"
        )
    if not expected_gap and gap_rows:
        raise GateError(
            "current report terminal has an unexpected gap-analysis artifact producer"
        )

    upstream_roots = [artifact_root]
    if launcher_root is not None:
        upstream_roots.append(launcher_root)
    pinned = {}
    validate_producer(
        "gc.build.code_review_report_path",
        code_rows[0],
        contract,
        upstream_roots,
        pinned,
    )
    if expected_gap:
        validate_producer(
            "gc.build.gap_analysis_report_path",
            gap_rows[0],
            contract,
            upstream_roots,
            pinned,
        )
    for pinned_path, expected_fingerprint in pinned.items():
        observed_fingerprint = file_fingerprint(pinned_path)
        if observed_fingerprint != expected_fingerprint:
            raise GateError(f"file changed during validation: {pinned_path}")
except Exception as exc:
    raise SystemExit(f"artifact validation failed: {exc}")
PY
    )"; then
      echo "review check: current code-review artifacts are invalid: $validation_output" >&2
      return 1
    fi
  fi
  printf '%s\n' "$canonical_report"
}

VERDICT="$(printf '%s\n' "$CURRENT_MATCHES" | jq -r '
  [
    .[] | select((.metadata["code_review.verdict"] // "") != "")
  ]
  | sort_by([.updated_at // "", .id // ""])
  | [
    .[]
    | select((.metadata["code_review.verdict"] // "") != "")
    | .metadata["code_review.verdict"]
  ] | last // ""
' 2>/dev/null)"

REVIEW_MODE="$(metadata_value "$ROOT_JSON" "gc.var.review_mode")"
if [ -z "$REVIEW_MODE" ]; then
  REVIEW_MODE="$(metadata_value "$PARENT_JSON" "gc.var.review_mode")"
fi
if [ "$REVIEW_MODE" = "report" ] && [ "$IMPLEMENTATION_PROVENANCE_REQUIRED" != "true" ]; then
  if [ "$CURRENT_REPORT_TERMINAL_REQUIRED" = "true" ]; then
    REPORT_MODE_PATH="$(validate_current_report_terminal)" || exit 1
    approve "Implementation review current report terminal satisfied: $REPORT_MODE_PATH"
  fi
  REPORT_MODE_PATH="$(metadata_value "$PARENT_JSON" "gc.build.code_review_report_path")"
  if [ -z "$REPORT_MODE_PATH" ]; then
    REPORT_MODE_PATH="$(metadata_value "$PARENT_JSON" "gc.build.review_report_path")"
  fi
  if [ -z "$REPORT_MODE_PATH" ]; then
    REPORT_MODE_PATH="$(metadata_value "$PARENT_JSON" "gc.var.report_path")"
  fi
  if [ -z "$REPORT_MODE_PATH" ]; then
    REPORT_MODE_PATH="$(printf '%s\n' "$CURRENT_MATCHES" | jq -r '
      [
        .[]
        | (
            .metadata["code_review.review_report_path"] //
            .metadata["code_review.report_path"] //
            .metadata["code_review.output_path"] //
            ""
          )
        | select(. != "")
      ] | last // ""
    ' 2>/dev/null)"
  fi
  if [ -n "$REPORT_MODE_PATH" ]; then
    approve "Implementation review report mode satisfied: $REPORT_MODE_PATH"
  fi
  echo "Implementation review report mode needs a review report path"
  exit 1
fi

validate_implementation_provenance

if [ "$IMPLEMENTATION_PROVENANCE_REQUIRED" = "true" ]; then
  case "$STEP_ID" in
    *.build-basic-review-loop)
      REVIEW_PREFIX="${STEP_ID%.build-basic-review-loop}"
      ;;
    *)
      echo "Implementation review needs another iteration: provenance-required loop has unexpected gc.step_id=${STEP_ID:-<missing>}" >&2
      exit 1
      ;;
  esac
  ACCEPTANCE_STEP="$REVIEW_PREFIX.acceptance-review"
  TEST_EVIDENCE_STEP="$REVIEW_PREFIX.test-evidence-review"
  SIMPLICITY_STEP="$REVIEW_PREFIX.simplicity-review"
  SYNTHESIS_STEP="$REVIEW_PREFIX.synthesize-review"
  if [ "$REVIEW_MODE" = "report" ]; then
    APPLY_STEP="$REVIEW_PREFIX.report-review-findings"
  else
    APPLY_STEP="$REVIEW_PREFIX.apply-review-findings"
  fi

  if ! STRICT_REVIEW_STATUS="$(printf '%s\n' "$CURRENT_MATCHES" | jq -r \
    --arg attempt "$ATTEMPT" \
    --arg snapshot "$CURRENT_IMPLEMENTATION_SNAPSHOT" \
    --arg review_input "$CURRENT_REVIEW_INPUT_SNAPSHOT" \
    --arg review_mode "$REVIEW_MODE" \
    --arg acceptance_step "$ACCEPTANCE_STEP" \
    --arg test_step "$TEST_EVIDENCE_STEP" \
    --arg simplicity_step "$SIMPLICITY_STEP" \
    --arg synthesis_step "$SYNTHESIS_STEP" \
    --arg apply_step "$APPLY_STEP" '
    def rows_for($step):
      [.[] | select(
        (.metadata["gc.step_id"] // "") == $step and
        (.metadata["gc.scope_role"] // "") == "member"
      )];
    def nonempty($value):
      (($value | type) == "string" and ($value | length) > 0);
    def base_ok($rows):
      (($rows | length) == 1) and
      (($rows[0].status // "") == "closed") and
      (($rows[0].metadata["gc.outcome"] // "") == "pass") and
      (($rows[0].metadata["gc.attempt"] // "") == $attempt) and
      ((($rows[0].metadata["code_review.reviewed_attempt"] // "") | tostring) ==
        ($attempt | tostring)) and
      (($rows[0].metadata["code_review.implementation_snapshot"] // "") == $snapshot) and
      (($rows[0].metadata["code_review.review_input_snapshot"] // "") == $review_input);
    def lane_ok($rows; $verdict_key):
      base_ok($rows) and
      (
        (($rows[0].metadata[$verdict_key] // "") == "approve") or
        (
          $review_mode == "report" and
          (($rows[0].metadata[$verdict_key] // "") == "iterate")
        )
      ) and
      nonempty($rows[0].metadata["code_review.output_path"] // "");
    rows_for($acceptance_step) as $acceptance
    | rows_for($test_step) as $test_evidence
    | rows_for($simplicity_step) as $simplicity
    | rows_for($synthesis_step) as $synthesis
    | rows_for($apply_step) as $apply
    | if (
        lane_ok($acceptance; "code_review.acceptance_verdict") and
        lane_ok($test_evidence; "code_review.test_evidence_verdict") and
        lane_ok($simplicity; "code_review.simplicity_verdict") and
        base_ok($synthesis) and
        nonempty($synthesis[0].metadata["code_review.synthesis_path"] // "") and
        nonempty($synthesis[0].metadata["code_review.output_path"] // "") and
        base_ok($apply) and
        (($apply[0].metadata["code_review.verdict"] // "") ==
          (if $review_mode == "report" then "reported" else "done" end)) and
        nonempty($apply[0].metadata["code_review.report_path"] // "") and
        nonempty($apply[0].metadata["code_review.output_path"] // "")
      ) then
        "approved"
      else
        "iterate: exact current-attempt build-basic evidence or implementation snapshot is incomplete or stale " +
        "counts acceptance=\($acceptance|length) test_evidence=\($test_evidence|length) " +
        "simplicity=\($simplicity|length) synthesis=\($synthesis|length) apply=\($apply|length)"
      end
  ')"; then
    echo "Implementation review needs another iteration: strict build-basic review metadata is malformed" >&2
    exit 1
  fi
  if [ "$STRICT_REVIEW_STATUS" != "approved" ]; then
    echo "Implementation review needs another iteration: $STRICT_REVIEW_STATUS"
    exit 1
  fi
  ARTIFACT_ROOT="$(metadata_value "$PARENT_JSON" "gc.build.artifact_root")"
  if [ -z "$ARTIFACT_ROOT" ]; then
    ARTIFACT_ROOT="$(metadata_value "$PARENT_JSON" "gc.var.artifact_root")"
  fi
  case "$ARTIFACT_ROOT" in
    /*) ;;
    *)
      ARTIFACT_LAUNCHER_TOP="$(git_top_level \
        "$(metadata_value "$PARENT_JSON" "gc.work_dir")")" || \
        implementation_provenance_fail "cannot resolve launcher root for relative artifact root"
      ARTIFACT_ROOT="$ARTIFACT_LAUNCHER_TOP/$ARTIFACT_ROOT"
      ;;
  esac
  ARTIFACT_ROOT="$(cd "$ARTIFACT_ROOT" 2>/dev/null && pwd -P)" || \
    implementation_provenance_fail "workflow artifact root does not resolve: $ARTIFACT_ROOT"
  if [ -n "${ARTIFACT_LAUNCHER_TOP:-}" ]; then
    case "$ARTIFACT_ROOT" in
      "$ARTIFACT_LAUNCHER_TOP"|"$ARTIFACT_LAUNCHER_TOP"/*) ;;
      *) implementation_provenance_fail "relative workflow artifact root escapes launcher worktree" ;;
    esac
  fi

  validate_review_evidence_path \
    "$(review_evidence_path "$CURRENT_MATCHES" "$ACCEPTANCE_STEP" "code_review.output_path")" \
    "acceptance review output" "$ARTIFACT_ROOT" "acceptance-review-report.md"
  validate_review_evidence_path \
    "$(review_evidence_path "$CURRENT_MATCHES" "$TEST_EVIDENCE_STEP" "code_review.output_path")" \
    "test evidence review output" "$ARTIFACT_ROOT" "test-evidence-review-report.md"
  validate_review_evidence_path \
    "$(review_evidence_path "$CURRENT_MATCHES" "$SIMPLICITY_STEP" "code_review.output_path")" \
    "simplicity review output" "$ARTIFACT_ROOT" "simplicity-review-report.md"
  validate_review_evidence_path \
    "$(review_evidence_path "$CURRENT_MATCHES" "$SYNTHESIS_STEP" "code_review.synthesis_path")" \
    "review synthesis" "$ARTIFACT_ROOT" "starter-review-synthesis.md"
  validate_review_evidence_path \
    "$(review_evidence_path "$CURRENT_MATCHES" "$SYNTHESIS_STEP" "code_review.output_path")" \
    "review synthesis output" "$ARTIFACT_ROOT" "starter-review-synthesis.md"
  validate_review_evidence_path \
    "$(review_evidence_path "$CURRENT_MATCHES" "$APPLY_STEP" "code_review.report_path")" \
    "review apply report" "$ARTIFACT_ROOT" "apply-review-findings-report.md"
  validate_review_evidence_path \
    "$(review_evidence_path "$CURRENT_MATCHES" "$APPLY_STEP" "code_review.output_path")" \
    "review apply output" "$ARTIFACT_ROOT" "apply-review-findings-report.md"
  if [ "$REVIEW_MODE" = "report" ]; then
    approve "Implementation review report recorded"
  fi
  approve "Implementation review approved"
fi

LANE_STATUS="$(printf '%s\n' "$CURRENT_MATCHES" | jq -r \
  --arg require_snapshot "$IMPLEMENTATION_PROVENANCE_REQUIRED" \
  --arg current_snapshot "$CURRENT_IMPLEMENTATION_SNAPSHOT" '
  def approved($value):
    (($value // "") | ascii_downcase) as $v
    | ($v == "approve" or $v == "approved" or $v == "pass");
  def rendered($row):
    (($row.verdict | if . == "" then "<missing>" else . end) + "@" +
    ($row.snapshot | if . == "" then "<missing implementation snapshot>" else . end));
  [
    .[]
    | .metadata as $metadata
    | [
        {
          lane: "acceptance",
          verdict: ($metadata["code_review.acceptance_verdict"] // ""),
          snapshot: ($metadata["code_review.implementation_snapshot"] // "")
        },
        {
          lane: "test_evidence",
          verdict: ($metadata["code_review.test_evidence_verdict"] // ""),
          snapshot: ($metadata["code_review.implementation_snapshot"] // "")
        },
        {
          lane: "simplicity",
          verdict: ($metadata["code_review.simplicity_verdict"] // ""),
          snapshot: ($metadata["code_review.implementation_snapshot"] // "")
        }
      ][]
    | select(.verdict != "")
  ] as $rows
  | {
      acceptance: ([$rows[] | select(.lane == "acceptance")] | last // {verdict: "", snapshot: ""}),
      test_evidence: ([$rows[] | select(.lane == "test_evidence")] | last // {verdict: "", snapshot: ""}),
      simplicity: ([$rows[] | select(.lane == "simplicity")] | last // {verdict: "", snapshot: ""})
    } as $latest
  | if $require_snapshot == "true" then
      if (
        approved($latest.acceptance.verdict) and
        approved($latest.test_evidence.verdict) and
        approved($latest.simplicity.verdict) and
        $latest.acceptance.snapshot == $current_snapshot and
        $latest.test_evidence.snapshot == $current_snapshot and
        $latest.simplicity.snapshot == $current_snapshot
      ) then
        "approved"
      else
        "iterate: implementation snapshot mismatch current=\($current_snapshot) acceptance=\(rendered($latest.acceptance)) test_evidence=\(rendered($latest.test_evidence)) simplicity=\(rendered($latest.simplicity))"
      end
    elif ($rows | length) > 0 then
      if (
        approved($latest.acceptance.verdict) and
        approved($latest.test_evidence.verdict) and
        approved($latest.simplicity.verdict)
      ) then
        "approved"
      else
        "iterate: acceptance=\($latest.acceptance.verdict // "<missing>") test_evidence=\($latest.test_evidence.verdict // "<missing>") simplicity=\($latest.simplicity.verdict // "<missing>")"
      end
    else
      ""
    end
' 2>/dev/null)"

if [ -n "$LANE_STATUS" ] && [ "$LANE_STATUS" != "approved" ]; then
  echo "Implementation review needs another iteration: $LANE_STATUS"
  exit 1
fi

if [ "$VERDICT" != "done" ]; then
  case "$VERDICT" in
    approved|pass)
      ;;
    "")
      if [ "$LANE_STATUS" = "approved" ]; then
        approve "Implementation review approved from lane verdicts"
      fi
      echo "Implementation review needs another iteration: ${LANE_STATUS:-missing verdict}"
      exit 1
      ;;
    *)
      echo "Implementation review needs another iteration: $VERDICT"
      exit 1
      ;;
  esac
fi

approve "Implementation review approved"
