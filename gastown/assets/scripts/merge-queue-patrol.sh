#!/usr/bin/env bash
# merge-queue-patrol - clear agent PR backpressure.
#
# Runs from mol-mayor-merge-queue-patrol.  The checks are intentionally
# mechanical: GitHub PR state, bead metadata, and session timestamps.
set -euo pipefail

GH_BIN="${GH_BIN:-gh}"
BD_BIN="${BD_BIN:-bd}"
GC_BIN="${GC_BIN:-gc}"
DRY_RUN="${MERGE_QUEUE_DRY_RUN:-0}"
ENABLE_ORPHAN_CLOSE="${MERGE_QUEUE_ENABLE_ORPHAN_CLOSE:-${MERGE_QUEUE_ORPHAN_CLOSE:-0}}"
CONFLICT_AGE_HOURS="${MERGE_QUEUE_CONFLICT_AGE_HOURS:-8}"
IDLE_POLECAT_MINUTES="${MERGE_QUEUE_IDLE_POLECAT_MINUTES:-30}"
SPAWN_STORM_THRESHOLD="${SPAWN_STORM_THRESHOLD:-2}"
COMMAND_TIMEOUT_SECONDS="${MERGE_QUEUE_COMMAND_TIMEOUT_SECONDS:-45}"
AGENT_PR_PREFIX_REGEX="${MERGE_QUEUE_AGENT_PR_PREFIX_REGEX:-^(polecat|refinery)/}"
ENV_FILE="${MERGE_QUEUE_ENV_FILE:-}"
BD_REPO_ROOT="${MERGE_QUEUE_BD_REPO_ROOT:-}"
POLECAT_ROUTE="${MERGE_QUEUE_POLECAT_ROUTE:-}"

CONFLICT_AGE_SECONDS=$((CONFLICT_AGE_HOURS * 3600))
IDLE_POLECAT_SECONDS=$((IDLE_POLECAT_MINUTES * 60))

cleared=0
closed=0
escalated=0
ages=()
busy_file_tokens=""
live_beads_json="[]"

log() {
  printf 'merge-queue-patrol: %s\n' "$*" >&2
}

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  . "$file"
  set +a
}

if [[ -n "$ENV_FILE" ]]; then
  load_env_file "$ENV_FILE"
fi
if [[ -n "$BD_REPO_ROOT" ]]; then
  cd "$BD_REPO_ROOT"
fi
if [[ -z "${GH_TOKEN:-}" && -n "${GITHUB_TOKEN:-}" ]]; then
  export GH_TOKEN="$GITHUB_TOKEN"
fi
GH_REPO_SLUG="${MERGE_QUEUE_GH_REPO:-${GH_REPO:-}}"

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

gh_pr_list_open() {
  local args=(pr list)
  if [[ -n "$GH_REPO_SLUG" ]]; then
    args+=(--repo "$GH_REPO_SLUG")
  fi
  args+=(--state open --limit 200)
  args+=(--json number,title,headRefName,baseRefName,headRefOid,mergeStateStatus,isDraft,autoMergeRequest,updatedAt,url,statusCheckRollup,files)
  # json_required_array, not json_or_empty_array. `gh pr list` resolves the
  # repository from the working directory, and /root/saitoc-city is not a git
  # checkout, so the call fails there with "not a git repository". Failing
  # open turned that into `[]`, and the patrol then printed
  # "swept cleared=0 closed=0 escalated=0" -- the same line a genuinely empty
  # queue prints. Measured on the live host 2026-08-23: 30 open pull requests,
  # 0 seen. Every bead query in this script already uses the required form.
  json_required_array "$GH_BIN" "${args[@]}"
}

gh_pr_close() {
  local number="$1" comment="$2" args
  args=(pr close "$number")
  if [[ -n "$GH_REPO_SLUG" ]]; then
    args+=(--repo "$GH_REPO_SLUG")
  fi
  args+=(--comment "$comment")
  run_cmd "$GH_BIN" "${args[@]}"
}

json_or_empty_array() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "${COMMAND_TIMEOUT_SECONDS}s" "$@" 2>/dev/null || printf '[]'
    return 0
  fi
  "$@" 2>/dev/null || printf '[]'
}

json_required_array() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "${COMMAND_TIMEOUT_SECONDS}s" "$@" 2>/dev/null && return 0
    printf '[]'
    return 1
  fi
  "$@" 2>/dev/null && return 0
  printf '[]'
  return 1
}

is_agent_pr() {
  local head="$1"
  [[ "$head" =~ $AGENT_PR_PREFIX_REGEX ]]
}

epoch_for() {
  local stamp="${1:-}"
  if [[ -z "$stamp" || "$stamp" == "null" ]]; then
    printf '0\n'
    return 0
  fi
  date -u -d "$stamp" +%s 2>/dev/null && return 0
  date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "$stamp" +%s 2>/dev/null && return 0
  python3 - "$stamp" <<'PY' 2>/dev/null || printf '0\n'
from datetime import datetime, timezone
import sys

stamp = sys.argv[1].replace("Z", "+00:00")
try:
    parsed = datetime.fromisoformat(stamp)
except ValueError:
    raise SystemExit(1)
if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
print(int(parsed.timestamp()))
PY
}

age_for() {
  local stamp="$1" now epoch
  now="$(date -u +%s)"
  epoch="$(epoch_for "$stamp")"
  if [[ "$epoch" == "0" ]]; then
    printf '0\n'
    return 0
  fi
  printf '%s\n' "$((now - epoch))"
}

age_p95() {
  if [[ "${#ages[@]}" -eq 0 ]]; then
    printf '0\n'
    return 0
  fi
  printf '%s\n' "${ages[@]}" | sort -n | awk '
    { values[NR] = $1 }
    END {
      idx = int((NR * 95 + 99) / 100)
      if (idx < 1) idx = 1
      if (idx > NR) idx = NR
      print values[idx]
    }'
}

emit_summary() {
  local p95 payload
  p95="$(age_p95)"
  payload="$(jq -cn \
    --argjson cleared "$cleared" \
    --argjson closed "$closed" \
    --argjson escalated "$escalated" \
    --argjson age_seconds_p95 "$p95" \
    '{cleared: $cleared, closed: $closed, escalated: $escalated, age_seconds_p95: $age_seconds_p95}')"
  run_cmd "$GC_BIN" event emit merge_queue.swept \
    --actor gastown.mayor \
    --payload "$payload" >/dev/null 2>&1 || true
  log "swept cleared=$cleared closed=$closed escalated=$escalated age_seconds_p95=$p95"
}

if ! command -v "$GH_BIN" >/dev/null 2>&1; then
  log "gh not found; skipping PR rules"
  emit_summary
  exit 0
fi

if ! command -v "$BD_BIN" >/dev/null 2>&1; then
  log "bd not found; skipping bead rules"
  emit_summary
  exit 0
fi

find_live_bead_by_filter() {
  local key="$1" value="$2" result
  [[ -n "$value" && "$value" != "null" ]] || return 1
  if ! result="$(json_required_array "$BD_BIN" list \
    --status=open,in_progress,blocked \
    --metadata-field "$key=$value" \
    --json \
    --limit=1)"; then
    return 2
  fi
  if [[ "$(jq 'length' <<< "$result")" -gt 0 ]]; then
    printf '%s\n' "$result" | jq -c '.[0]'
    return 0
  fi
  return 1
}

find_live_bead_by_id() {
  local bead_id="$1" result
  [[ -n "$bead_id" && "$bead_id" != "null" ]] || return 1
  if ! result="$(json_required_array "$BD_BIN" list \
    --status=open,in_progress,blocked \
    --id "$bead_id" \
    --json \
    --limit=1)"; then
    return 2
  fi
  if [[ "$(jq 'length' <<< "$result")" -gt 0 ]]; then
    printf '%s\n' "$result" | jq -c '.[0]'
    return 0
  fi
  return 1
}

is_bead_id() {
  [[ "$1" =~ ^saitoc-[a-z0-9]{6}$ ]]
}

find_source_repair_bead() {
  local number="$1" url="$2" rc
  find_live_bead_by_filter ops.source_pr "$number"
  rc=$?
  [[ "$rc" -eq 0 ]] && return 0
  [[ "$rc" -eq 2 ]] && return 2

  find_live_bead_by_filter ops.source_url "$url"
  rc=$?
  [[ "$rc" -eq 0 ]] && return 0
  [[ "$rc" -eq 2 ]] && return 2

  return 1
}

find_live_bead() {
  local number="$1" branch="$2" url="$3" branch_id rc
  branch_id="${branch#*/}"
  if is_bead_id "$branch_id"; then
    find_live_bead_by_id "$branch_id"
    rc=$?
    [[ "$rc" -eq 0 ]] && return 0
    [[ "$rc" -eq 2 ]] && return 2
  fi

  find_live_bead_by_filter branch "$branch"
  rc=$?
  [[ "$rc" -eq 0 ]] && return 0
  [[ "$rc" -eq 2 ]] && return 2

  find_live_bead_by_filter existing_pr "$url"
  rc=$?
  [[ "$rc" -eq 0 ]] && return 0
  [[ "$rc" -eq 2 ]] && return 2

  find_live_bead_by_filter pr_url "$url"
  rc=$?
  [[ "$rc" -eq 0 ]] && return 0
  [[ "$rc" -eq 2 ]] && return 2

  find_source_repair_bead "$number" "$url"
  rc=$?
  [[ "$rc" -eq 0 ]] && return 0
  [[ "$rc" -eq 2 ]] && return 2

  return 1
}

live_bead_matches_pr() {
  local number="$1" branch="$2" url="$3" branch_id
  branch_id="${branch#*/}"
  printf '%s\n' "$live_beads_json" | jq -e \
    --arg number "$number" \
    --arg branch "$branch" \
    --arg url "$url" \
    --arg branch_id "$branch_id" \
    '
      any(.[]?;
        ((.id // "") == $branch_id) or
        ((.metadata.branch // "") == $branch) or
        ((.metadata.existing_pr // "") == $url) or
        ((.metadata.pr_url // "") == $url) or
        (((.metadata["ops.source_pr"] // "") | tostring) == $number) or
        ((.metadata["ops.source_url"] // "") == $url)
      )
    ' >/dev/null
}

reset_conflicting_bead() {
  local bead_id="$1" branch="$2" target="$3" age="$4"
  local update_args=(
    "$BD_BIN" update "$bead_id"
    --status=open \
    --assignee="" \
  )
  if [[ -n "$POLECAT_ROUTE" ]]; then
    update_args+=(--set-metadata "gc.routed_to=$POLECAT_ROUTE")
  else
    update_args+=(--unset-metadata gc.routed_to)
  fi
  update_args+=(--notes "auto-reset: conflicting PR for $branch against $target after ${age}s")
  if run_cmd "${update_args[@]}"; then
    cleared=$((cleared + 1))
  else
    escalated=$((escalated + 1))
  fi
}

reset_failing_bead() {
  local bead_id="$1" branch="$2" checks="$3"
  local update_args=(
    "$BD_BIN" update "$bead_id"
    --status=open
    --assignee=""
  )
  if [[ -n "$POLECAT_ROUTE" ]]; then
    update_args+=(--set-metadata "gc.routed_to=$POLECAT_ROUTE")
  else
    update_args+=(--unset-metadata gc.routed_to)
  fi
  update_args+=(--notes "auto-reset: failing PR for $branch; failing checks: ${checks:-unknown}")
  if run_cmd "${update_args[@]}"; then
    cleared=$((cleared + 1))
  else
    escalated=$((escalated + 1))
  fi
}

check_state_for_pr() {
  jq -r '
    [(.statusCheckRollup // [])[]] as $checks
    | if ($checks | length) == 0 then "unknown"
      elif any($checks[];
        ((.status // "") | ascii_upcase) as $status
        | ((.state // "") | ascii_upcase) as $state
        | ($status != "COMPLETED" and ($state != "SUCCESS" and $state != "FAILURE" and $state != "ERROR"))
      ) then "pending"
      elif any($checks[];
        ((.conclusion // .state // "") | ascii_upcase) as $c
        | ($c != "SUCCESS" and $c != "SKIPPED" and $c != "NEUTRAL")
      ) then "failed"
      else "passed"
      end
  ' <<< "$1"
}

failing_checks_for_pr() {
  jq -r '
    [(.statusCheckRollup // [])[]
      | select(
        ((.conclusion // .state // "") | ascii_upcase) as $c
        | ($c != "" and $c != "SUCCESS" and $c != "SKIPPED" and $c != "NEUTRAL")
      )
      | (.name // .context // .workflowName // "unknown")
    ] | unique | join(", ")
  ' <<< "$1"
}

pr_file_tokens() {
  jq -r '
    [(.files // [])[]
      | (.path // .filename // .name // empty)
      | select(. != "")
    ] | unique | .[]
  ' <<< "$1"
}

busy_token_present() {
  local token="$1"
  [[ -n "$token" ]] || return 1
  grep -Fxq -- "$token" <<< "$busy_file_tokens"
}

mark_files_busy() {
  local files="$1" token marked=0
  while IFS= read -r token; do
    [[ -n "$token" ]] || continue
    if ! busy_token_present "$token"; then
      busy_file_tokens="${busy_file_tokens}${busy_file_tokens:+$'\n'}${token}"
    fi
    marked=1
  done <<< "$files"
  if [[ "$marked" -eq 0 ]]; then
    token="__unknown_files__"
    if ! busy_token_present "$token"; then
      busy_file_tokens="${busy_file_tokens}${busy_file_tokens:+$'\n'}${token}"
    fi
  fi
}

busy_overlap_token() {
  local files="$1" token saw_file=0
  while IFS= read -r token; do
    [[ -n "$token" ]] || continue
    saw_file=1
    if busy_token_present "$token"; then
      printf '%s\n' "$token"
      return 0
    fi
  done <<< "$files"
  if [[ "$saw_file" -eq 0 ]] && busy_token_present "__unknown_files__"; then
    printf '%s\n' "__unknown_files__"
    return 0
  fi
  return 1
}

merge_clean_pr() {
  local number="$1" files="$2" overlap
  overlap="$(busy_overlap_token "$files" || true)"
  if [[ -n "$overlap" ]]; then
    log "PR #$number clean but merge cluster busy on $overlap; leaving for next tick"
    return 2
  fi
  # Permanent guardrail: this patrol may inspect and repair queue state, but it
  # must not create a native auto-merge request. Such a request can execute
  # after its pause, freeze, base, or admission evidence becomes stale. The
  # repository workflow owns immediate merge authority and re-reads every
  # control at the irreversible boundary.
  log "PR #$number clean and unarmed; leaving merge authority with the repository workflow"
  return 0
}

block_spawn_storm_bead() {
  local bead_id="$1" reset_count="$2" title="$3"
  if run_cmd "$BD_BIN" update "$bead_id" \
    --status=blocked \
    --assignee="" \
    --unset-metadata gc.routed_to \
    --notes "auto-blocked: storm-detect threshold."; then
    cleared=$((cleared + 1))
    run_cmd "$GC_BIN" mail send mayor/ \
      -s "AUDIT: spawn storm auto-blocked $bead_id" \
      -m "No action required.  $bead_id ($title) reached reset_count=$reset_count and was auto-blocked as pool poison." \
      >/dev/null 2>&1 || true
  else
    escalated=$((escalated + 1))
  fi
}

if ! prs="$(gh_pr_list_open)"; then
  log "FATAL: cannot read the pull request queue (gh pr list failed). Refusing to report a swept queue from a blind read."
  exit 4
fi

agent_pr_count="$(printf '%s\n' "$prs" | jq --arg re "$AGENT_PR_PREFIX_REGEX" '[.[] | select((.headRefName // "") | test($re))] | length')"
process_prs=1
if [[ "$agent_pr_count" -eq 0 ]]; then
  process_prs=0
fi

if [[ "$process_prs" -eq 1 ]]; then
  scan_ok=1
  open_live="[]"
  in_progress_live="[]"
  blocked_live="[]"
  if ! open_live="$(json_required_array "$BD_BIN" list --status=open --json --limit=0)"; then
    scan_ok=0
  fi
  if ! in_progress_live="$(json_required_array "$BD_BIN" list --status=in_progress --json --limit=0)"; then
    scan_ok=0
  fi
  if ! blocked_live="$(json_required_array "$BD_BIN" list --status=blocked --json --limit=0)"; then
    scan_ok=0
  fi

  # Permanent guardrail: skip close/merge rules on empty or unmatched bead scans
  # to prevent a transient bd failure from mass-closing live agent PRs.
  if [[ "$scan_ok" -eq 0 ]]; then
    log "bead scan failed or timed out; skipping PR close/merge rules for this tick"
    escalated=$((escalated + 1))
    process_prs=0
  fi

  live_beads_json="$(
    printf '%s\n%s\n%s\n' "$open_live" "$in_progress_live" "$blocked_live" | jq -s 'add'
  )"

  live_bead_count="$(printf '%s\n' "$live_beads_json" | jq 'length')"
  if [[ "$process_prs" -eq 1 && "$live_bead_count" -eq 0 ]]; then
    log "bead scan returned zero live beads for $agent_pr_count agent PRs; skipping PR close/merge rules for this tick"
    escalated=$((escalated + 1))
    process_prs=0
  fi

  if [[ "$process_prs" -eq 1 ]]; then
    matched_agent_pr_count=0
    while IFS= read -r pr; do
      [[ -z "$pr" ]] && continue
      head="$(jq -r '.headRefName // ""' <<< "$pr")"
      url="$(jq -r '.url // ""' <<< "$pr")"
      number="$(jq -r '.number' <<< "$pr")"
      is_agent_pr "$head" || continue
      if live_bead_matches_pr "$number" "$head" "$url"; then
        matched_agent_pr_count=$((matched_agent_pr_count + 1))
      fi
    done < <(printf '%s\n' "$prs" | jq -c '.[]')

    if [[ "$matched_agent_pr_count" -eq 0 ]]; then
      log "no live bead matched any of $agent_pr_count agent PRs; skipping PR close/merge rules for this tick"
      escalated=$((escalated + 1))
      process_prs=0
    fi
  fi
fi

if [[ "$process_prs" -eq 1 ]]; then
  while IFS= read -r pr; do
    [[ -z "$pr" ]] && continue
    auto_merge="$(jq -r 'if .autoMergeRequest == null then "none" else "set" end' <<< "$pr")"
    head="$(jq -r '.headRefName // ""' <<< "$pr")"
    is_agent_pr "$head" || continue
    [[ "$auto_merge" == "set" ]] || continue
    mark_files_busy "$(pr_file_tokens "$pr")"
  done < <(printf '%s\n' "$prs" | jq -c '.[]')

  while IFS= read -r pr; do
    [[ -z "$pr" ]] && continue

    number="$(jq -r '.number' <<< "$pr")"
    head="$(jq -r '.headRefName // ""' <<< "$pr")"
    target="$(jq -r '.baseRefName // "main"' <<< "$pr")"
    state="$(jq -r '.mergeStateStatus // "UNKNOWN"' <<< "$pr")"
    draft="$(jq -r '.isDraft // false' <<< "$pr")"
    auto_merge="$(jq -r 'if .autoMergeRequest == null then "none" else "set" end' <<< "$pr")"
    updated_at="$(jq -r '.updatedAt // ""' <<< "$pr")"
    url="$(jq -r '.url // ""' <<< "$pr")"
    branch_id="${head#*/}"
    files="$(pr_file_tokens "$pr")"

    is_agent_pr "$head" || continue

    age="$(age_for "$updated_at")"
    ages+=("$age")
    check_state="$(check_state_for_pr "$pr")"
    failing_checks="$(failing_checks_for_pr "$pr")"

    if is_bead_id "$branch_id"; then
      if [[ "$state" == "DIRTY" && "$age" -gt "$CONFLICT_AGE_SECONDS" ]]; then
        source_repair=""
        source_lookup_rc=0
        if source_repair="$(find_source_repair_bead "$number" "$url")"; then
          source_lookup_rc=0
        else
          source_lookup_rc=$?
        fi
        if [[ "$source_lookup_rc" -eq 2 ]]; then
          log "source-repair lookup timed out for PR #$number branch=$head; leaving PR untouched"
          escalated=$((escalated + 1))
          continue
        fi
        if [[ -n "$source_repair" ]]; then
          source_repair_id="$(jq -r '.id' <<< "$source_repair")"
          source_repair_kind="$(jq -r '.metadata["ops.kind"] // ""' <<< "$source_repair")"
          if [[ "$source_repair_kind" == "pr-repair" ]]; then
            log "PR #$number is covered by repair bead $source_repair_id; leaving source PR to refinery"
            continue
          fi
        fi
        if gh_pr_close "$number" \
          "Closing conflicting agent PR after ${age}s; resetting $branch_id to the pool."; then
          closed=$((closed + 1))
          reset_conflicting_bead "$branch_id" "$head" "$target" "$age"
        else
          escalated=$((escalated + 1))
        fi
        continue
      fi

      if [[ "$check_state" == "failed" ]]; then
        log "PR #$number has failing checks; routing $branch_id back to the agent pool"
        reset_failing_bead "$branch_id" "$head" "$failing_checks"
        continue
      fi

      if [[ "$check_state" == "pending" ]]; then
        log "PR #$number checks pending; leaving $branch_id out of agent time"
      fi

      if [[ "$draft" == "false" && "$auto_merge" == "none" ]]; then
        case "$state" in
          CLEAN|HAS_HOOKS)
            merge_clean_pr "$number" "$files" || true
            ;;
        esac
      fi
      continue
    fi

    bead=""
    lookup_rc=0
    if bead="$(find_live_bead "$number" "$head" "$url")"; then
      lookup_rc=0
    else
      lookup_rc=$?
    fi
    if [[ "$lookup_rc" -eq 2 ]]; then
      log "bead lookup timed out for PR #$number branch=$head; leaving PR untouched"
      escalated=$((escalated + 1))
      continue
    fi
    if [[ -z "$bead" ]]; then
      if [[ "$ENABLE_ORPHAN_CLOSE" == "1" ]]; then
        if gh_pr_close "$number" \
          "Closing orphan agent PR: no live bead references branch $head."; then
          closed=$((closed + 1))
        else
          escalated=$((escalated + 1))
        fi
      else
        log "orphan-close disabled; unmatched agent PR #$number branch=$head url=$url"
        escalated=$((escalated + 1))
      fi
      continue
    fi

    bead_id="$(jq -r '.id' <<< "$bead")"
    repair_source_pr="$(jq -r '.metadata["ops.source_pr"] // ""' <<< "$bead")"
    repair_kind="$(jq -r '.metadata["ops.kind"] // ""' <<< "$bead")"
    if [[ "$repair_kind" == "pr-repair" && "$repair_source_pr" == "$number" ]]; then
      log "PR #$number is covered by repair bead $bead_id; leaving source PR to refinery"
      continue
    fi

    if [[ "$state" == "DIRTY" && "$age" -gt "$CONFLICT_AGE_SECONDS" ]]; then
      if gh_pr_close "$number" \
        "Closing conflicting agent PR after ${age}s; resetting $bead_id to the pool."; then
        closed=$((closed + 1))
        reset_conflicting_bead "$bead_id" "$head" "$target" "$age"
      else
        escalated=$((escalated + 1))
      fi
      continue
    fi

    if [[ "$check_state" == "failed" ]]; then
      log "PR #$number has failing checks; routing $bead_id back to the agent pool"
      reset_failing_bead "$bead_id" "$head" "$failing_checks"
      continue
    fi

    if [[ "$check_state" == "pending" ]]; then
      log "PR #$number checks pending; leaving $bead_id out of agent time"
    fi

    if [[ "$draft" == "false" && "$auto_merge" == "none" ]]; then
      case "$state" in
        CLEAN|HAS_HOOKS)
          merge_clean_pr "$number" "$files" || true
          ;;
      esac
    fi
  done < <(printf '%s\n' "$prs" | jq -c '.[]')
fi

open_beads="$(json_or_empty_array "$BD_BIN" list \
  --status=open \
  --assignee="" \
  --has-metadata-key reset_count \
  --json \
  --limit=0)"
while IFS= read -r bead; do
  [[ -z "$bead" ]] && continue
  bead_id="$(jq -r '.id' <<< "$bead")"
  title="$(jq -r '.title // "unknown"' <<< "$bead")"
  reset_count="$(jq -r '(.metadata.reset_count // 0) | tonumber? // 0' <<< "$bead")"
  if [[ "$reset_count" -gt "$SPAWN_STORM_THRESHOLD" ]]; then
    block_spawn_storm_bead "$bead_id" "$reset_count" "$title"
  fi
done < <(printf '%s\n' "$open_beads" | jq -c '.[]')

if command -v "$GC_BIN" >/dev/null 2>&1; then
  sessions_raw="$(json_or_empty_array "$GC_BIN" session list --json)"
  # `gc session list --json` returns a WRAPPER OBJECT:
  #   {filters, ok, schema_version, sessions, summary}
  # Iterating it with `.[]` walks the wrapper's VALUES, so the loop saw the
  # `filters` and `summary` objects and never a session. The existing
  # select(type == "object") hid that: it drops the boolean and the string,
  # which stops the crash and still yields no sessions.
  sessions="$(jq -c 'if type == "object" then (.sessions // []) else . end
                     | if type == "array" then . else [] end' <<< "$sessions_raw" 2>/dev/null || printf '[]')"
  while IFS= read -r session; do
    [[ -z "$session" ]] && continue
    # Live `gc` emits snake_case. The fixtures were written in PascalCase, so
    # both are read here. Reading only PascalCase left every field empty, the
    # `state == active` guard skipped every session, and the idle polecat
    # reaper reported success having examined nothing.
    template="$(jq -r '(.template // .Template) // ""' <<< "$session")"
    state="$(jq -r '(.state // .State) // ""' <<< "$session")"
    last_active="$(jq -r '(.last_active // .LastActive) // ""' <<< "$session")"
    session_name="$(jq -r '(.session_name // .SessionName) // ""' <<< "$session")"
    id="$(jq -r '(.id // .ID) // ""' <<< "$session")"
    alias="$(jq -r '(.alias // .Alias) // ""' <<< "$session")"
    agent_name="$(jq -r '(.agent_name // .AgentName) // ""' <<< "$session")"

    [[ "$state" == "active" ]] || continue
    case "$template" in
      */polecat|polecat) ;;
      *) continue ;;
    esac

    idle_age="$(age_for "$last_active")"
    [[ "$idle_age" -gt "$IDLE_POLECAT_SECONDS" ]] || continue

    has_work=0
    for assignee in "$id" "$session_name" "$alias" "$agent_name"; do
      [[ -z "$assignee" || "$assignee" == "null" ]] && continue
      count="$(json_or_empty_array "$BD_BIN" list --status=in_progress --assignee="$assignee" --json --limit=1 | jq 'length')"
      if [[ "$count" -gt 0 ]]; then
        has_work=1
        break
      fi
    done

    [[ "$has_work" -eq 0 ]] || continue
    if [[ -n "$session_name" && "$session_name" != "null" ]]; then
      if run_cmd "$GC_BIN" session kill "$session_name"; then
        cleared=$((cleared + 1))
      else
        escalated=$((escalated + 1))
      fi
    fi
  done < <(printf '%s\n' "$sessions" | jq -c '.[] | select(type == "object")')
fi

emit_summary
