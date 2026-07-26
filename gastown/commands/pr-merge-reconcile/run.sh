#!/bin/sh
set -eu

usage() {
    echo "usage: gc gastown pr-merge-reconcile [record WORK PR_URL PR_NUMBER TARGET HEAD_SHA]" >&2
    exit 2
}

require_identity() {
    if [ -z "${GC_AGENT:-}" ]; then
        echo "pr-merge-reconcile: GC_AGENT is empty; refusing an unowned state transition" >&2
        exit 2
    fi
}

bd_update() {
    if [ -n "${GC_RIG:-}" ]; then
        gc bd update --rig="$GC_RIG" "$@"
    else
        gc bd update "$@"
    fi
}

bd_close() {
    if [ -n "${GC_RIG:-}" ]; then
        gc bd close --rig="$GC_RIG" "$@"
    else
        gc bd close "$@"
    fi
}

mail_mayor() {
    subject=$1
    body=$2
    if ! gc mail send mayor/ -s "$subject" -m "$body"; then
        echo "pr-merge-reconcile: state is safe, but mayor escalation delivery failed" >&2
    fi
}

valid_number() {
    case "$1" in
        ""|*[!0-9]*) return 1 ;;
        *) return 0 ;;
    esac
}

valid_sha() {
    case "$1" in
        ""|*[!0-9a-fA-F]*) return 1 ;;
        *)
            [ "${#1}" -ge 40 ]
            ;;
    esac
}

github_repo_from_pr_url() {
    parsed_url=$1
    case "$parsed_url" in
        https://github.com/*) parsed_path=${parsed_url#https://github.com/} ;;
        *) return 1 ;;
    esac

    parsed_owner=${parsed_path%%/*}
    parsed_remainder=${parsed_path#*/}
    [ "$parsed_remainder" != "$parsed_path" ] || return 1
    parsed_repo=${parsed_remainder%%/*}
    parsed_pull_path=${parsed_remainder#*/}
    [ "$parsed_pull_path" != "$parsed_remainder" ] || return 1
    parsed_number=${parsed_pull_path#pull/}
    [ "pull/$parsed_number" = "$parsed_pull_path" ] || return 1
    [ -n "$parsed_owner" ] && [ -n "$parsed_repo" ] || return 1
    case "$parsed_owner$parsed_repo" in
        *[!A-Za-z0-9_.-]*) return 1 ;;
    esac
    valid_number "$parsed_number" || return 1
    printf '%s/%s\n' "$parsed_owner" "$parsed_repo"
}

valid_pr_url() {
    github_repo_from_pr_url "$1" >/dev/null
}

github_repo_from_origin_url() {
    origin_url=$1
    case "$origin_url" in
        https://github.com/*)
            origin_path=${origin_url#https://github.com/}
            ;;
        https://*@github.com/*)
            origin_path=${origin_url#https://}
            origin_path=${origin_path#*@github.com/}
            ;;
        git@github.com:*)
            origin_path=${origin_url#git@github.com:}
            ;;
        ssh://git@github.com/*)
            origin_path=${origin_url#ssh://git@github.com/}
            ;;
        *)
            return 1
            ;;
    esac
    origin_path=${origin_path%/}
    origin_path=${origin_path%.git}
    origin_owner=${origin_path%%/*}
    origin_repo=${origin_path#*/}
    [ "$origin_repo" != "$origin_path" ] || return 1
    [ -n "$origin_owner" ] && [ -n "$origin_repo" ] || return 1
    case "$origin_repo" in
        */*) return 1 ;;
    esac
    case "$origin_owner$origin_repo" in
        *[!A-Za-z0-9_.-]*) return 1 ;;
    esac
    printf '%s/%s\n' "$origin_owner" "$origin_repo"
}

rig_git() {
    if [ -n "${GC_RIG_ROOT:-}" ]; then
        git -C "$GC_RIG_ROOT" "$@"
    else
        git "$@"
    fi
}

rig_git_without_history_overrides() {
    # Both refs/replace and the deprecated info/grafts file rewrite ancestry
    # for merge-base. Neither is acceptable evidence that a GitHub merge
    # commit reached the recorded target.
    if [ -n "${GC_RIG_ROOT:-}" ]; then
        GIT_GRAFT_FILE=/dev/null \
            git --no-replace-objects -C "$GC_RIG_ROOT" "$@"
    else
        GIT_GRAFT_FILE=/dev/null git --no-replace-objects "$@"
    fi
}

lowercase_repo() {
    printf '%s\n' "$1" | tr '[:upper:]' '[:lower:]'
}

repos_equal() {
    [ "$(lowercase_repo "$1")" = "$(lowercase_repo "$2")" ]
}

current_origin_repo() {
    current_origin_url=$(rig_git remote get-url origin 2>/dev/null) || return 1
    github_repo_from_origin_url "$current_origin_url"
}

now_utc() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

resolve_github_token() {
    token=${GH_TOKEN:-${GITHUB_TOKEN:-${GIT_TOKEN:-}}}
    if [ -n "$token" ]; then
        printf '%s\n' "$token"
        return 0
    fi
    printf 'protocol=https\nhost=github.com\n\n' |
        GIT_TERMINAL_PROMPT=0 git credential fill 2>/dev/null |
        sed -n 's/^password=//p' |
        head -n 1
}

lookup_pr_info() {
    pr_url=$1
    err_file=$2
    if [ "${GASTOWN_PR_RECONCILE_FORCE_REST:-0}" != "1" ] &&
       command -v gh >/dev/null 2>&1; then
        gh pr view "$pr_url" \
            --json url,number,state,headRefName,headRefOid,baseRefName,mergedAt,mergeCommit \
            2>"$err_file"
        return $?
    fi

    token=$(resolve_github_token)
    if [ -z "$token" ]; then
        echo "GitHub PR reconciliation requires gh or a GitHub token." >"$err_file"
        return 1
    fi
    path=${pr_url#https://github.com/}
    owner=${path%%/*}
    remainder=${path#*/}
    repo=${remainder%%/*}
    pr_number=${path##*/}
    raw=$(curl -fsS \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer $token" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/repos/$owner/$repo/pulls/$pr_number" \
        2>"$err_file") || return 1
    printf '%s\n' "$raw" | jq '{
        url: .html_url,
        number,
        state: (if .merged_at then "MERGED" else (.state | ascii_upcase) end),
        headRefName: .head.ref,
        headRefOid: .head.sha,
        baseRefName: .base.ref,
        mergedAt: .merged_at,
        mergeCommit: (if .merge_commit_sha then {oid: .merge_commit_sha} else null end)
    }'
}

record_handoff() {
    [ "$#" -eq 5 ] || usage
    require_identity

    work=$1
    pr_url=$2
    pr_number=$3
    target=$4
    head_sha=$5

    [ -n "$work" ] || usage
    valid_pr_url "$pr_url" || {
        echo "pr-merge-reconcile: invalid GitHub pull-request URL: $pr_url" >&2
        exit 2
    }
    valid_number "$pr_number" || {
        echo "pr-merge-reconcile: invalid pull-request number: $pr_number" >&2
        exit 2
    }
    [ "${pr_url##*/}" = "$pr_number" ] || {
        echo "pr-merge-reconcile: pull-request URL and number disagree" >&2
        exit 2
    }
    valid_sha "$head_sha" || {
        echo "pr-merge-reconcile: invalid pull-request head SHA: $head_sha" >&2
        exit 2
    }
    git check-ref-format "refs/heads/$target" >/dev/null 2>&1 || {
        echo "pr-merge-reconcile: invalid target branch: $target" >&2
        exit 2
    }
    pr_repo=$(github_repo_from_pr_url "$pr_url")
    origin_repo=$(current_origin_repo) || {
        echo "pr-merge-reconcile: cannot resolve a standard github.com origin repository" >&2
        exit 2
    }
    repos_equal "$pr_repo" "$origin_repo" || {
        echo "pr-merge-reconcile: pull request repository $pr_repo does not match origin $origin_repo" >&2
        exit 2
    }

    # Arm the retry marker while the bead is still open. If any later
    # metadata write fails, normal refinery work discovery can retry this
    # open bead; only move it to blocked after the complete record exists.
    bd_update "$work" \
        --assignee="$GC_AGENT" \
        --set-metadata pr_reconcile_pending=true
    bd_update "$work" \
        --assignee="$GC_AGENT" \
        --set-metadata merge_result=pull_request_pending \
        --set-metadata pr_url="$pr_url" \
        --set-metadata pr_number="$pr_number" \
        --set-metadata pr_head_sha="$head_sha" \
        --set-metadata pr_repo="$pr_repo" \
        --set-metadata pr_state=open \
        --set-metadata pr_last_checked_at="$(now_utc)" \
        --set-metadata merged_target="$target" \
        --set-metadata blocked_reason="Awaiting verified merge of $pr_url" \
        --unset-metadata gc.routed_to \
        --unset-metadata rejection_reason \
        --unset-metadata pr_reconcile_error
    bd_update "$work" \
        --status=blocked \
        --assignee="$GC_AGENT"
}

quarantine_metadata() {
    work=$1
    reason=$2
    now=$3
    bd_update "$work" \
        --status=blocked \
        --set-metadata merge_result=pull_request_reconcile_invalid \
        --set-metadata pr_state=invalid \
        --set-metadata pr_last_checked_at="$now" \
        --set-metadata blocked_reason="$reason"
    bd_update "$work" --unset-metadata pr_reconcile_pending
    mail_mayor \
        "ESCALATION: invalid pending PR metadata for $work" \
        "$reason
Work bead: $work
The bead remains blocked; correct its PR metadata before retrying."
}

record_retryable_error() {
    work=$1
    state=$2
    reason=$3
    now=$4
    bd_update "$work" \
        --set-metadata pr_state="$state" \
        --set-metadata pr_last_checked_at="$now" \
        --set-metadata pr_reconcile_error="$reason"
}

requeue_changed_open_head() {
    work=$1
    pr_url=$2
    expected=$3
    actual=$4
    now=$5
    reason="PR head changed after refinery validation ($expected -> $actual); quality gates must run again"
    bd_update "$work" \
        --status=open \
        --assignee="$GC_AGENT" \
        --set-metadata merge_result=pull_request_head_changed \
        --set-metadata existing_pr="$pr_url" \
        --set-metadata observed_pr_head_sha="$actual" \
        --set-metadata pr_state=open \
        --set-metadata pr_last_checked_at="$now" \
        --set-metadata rejection_reason="$reason" \
        --unset-metadata blocked_reason \
        --unset-metadata pr_reconcile_error
    bd_update "$work" --unset-metadata pr_reconcile_pending
    echo "REVALIDATE: $work — $reason"
}

quarantine_terminal_pr() {
    work=$1
    result=$2
    state=$3
    reason=$4
    now=$5
    bd_update "$work" \
        --status=blocked \
        --set-metadata merge_result="$result" \
        --set-metadata pr_state="$state" \
        --set-metadata pr_last_checked_at="$now" \
        --set-metadata blocked_reason="$reason"
    bd_update "$work" --unset-metadata pr_reconcile_pending
    mail_mayor \
        "ESCALATION: PR lifecycle blocked for $work" \
        "$reason
Work bead: $work
The bead and its dependents remain blocked."
}

reconcile_one() {
    require_identity

    if [ -n "${GC_RIG:-}" ]; then
        pending_json=$(gc bd list --rig="$GC_RIG" \
            --status=blocked \
            --has-metadata-key=pr_reconcile_pending \
            --limit=0 \
            --json)
    else
        pending_json=$(gc bd list \
            --status=blocked \
            --has-metadata-key=pr_reconcile_pending \
            --limit=0 \
            --json)
    fi

    row=$(printf '%s\n' "$pending_json" | jq -c '
        [
          .[]
          | select(((.metadata.pr_reconcile_pending // "") | tostring) == "true")
        ]
        | sort_by(.metadata.pr_last_checked_at // "")
        | .[0] // empty
    ')
    [ -n "$row" ] || {
        echo "No pending pull-request merges."
        return 0
    }

    work=$(printf '%s\n' "$row" | jq -r '.id // empty')
    pr_url=$(printf '%s\n' "$row" | jq -r '.metadata.pr_url // empty')
    pr_number=$(printf '%s\n' "$row" | jq -r '.metadata.pr_number // empty')
    expected_head=$(printf '%s\n' "$row" | jq -r '.metadata.pr_head_sha // empty')
    recorded_repo=$(printf '%s\n' "$row" | jq -r '.metadata.pr_repo // empty')
    branch=$(printf '%s\n' "$row" | jq -r '.metadata.branch // empty')
    target=$(printf '%s\n' "$row" | jq -r '.metadata.merged_target // .metadata.target // empty')
    now=$(now_utc)

    if [ -z "$work" ]; then
        echo "pr-merge-reconcile: pending row has no bead id; refusing last-touched fallback" >&2
        return 1
    fi
    parsed_repo=$(github_repo_from_pr_url "$pr_url" 2>/dev/null || true)
    if [ -z "$parsed_repo" ] ||
       ! valid_number "$pr_number" ||
       [ "${pr_url##*/}" != "$pr_number" ] ||
       ! valid_sha "$expected_head" ||
       [ -z "$recorded_repo" ] ||
       ! repos_equal "$parsed_repo" "$recorded_repo" ||
       [ -z "$branch" ] ||
       ! git check-ref-format "refs/heads/$branch" >/dev/null 2>&1 ||
       ! git check-ref-format "refs/heads/$target" >/dev/null 2>&1; then
        quarantine_metadata "$work" "Pending PR metadata is incomplete or invalid (url/number/head/branch/target)." "$now"
        return 1
    fi
    origin_repo=$(current_origin_repo 2>/dev/null || true)
    if [ -z "$origin_repo" ] || ! repos_equal "$recorded_repo" "$origin_repo"; then
        record_retryable_error \
            "$work" \
            origin_mismatch \
            "Recorded PR repository $recorded_repo does not match the current standard github.com origin (${origin_repo:-unresolved}); will retry." \
            "$now"
        return 1
    fi

    err_file=$(mktemp "${TMPDIR:-/tmp}/gascity-pr-reconcile.XXXXXX")
    trap 'rm -f "$err_file"' EXIT HUP INT TERM
    if ! pr_info=$(lookup_pr_info "$pr_url" "$err_file"); then
        record_retryable_error "$work" lookup_failed "GitHub PR lookup failed; will retry." "$now"
        cat "$err_file" >&2
        return 1
    fi
    rm -f "$err_file"
    trap - EXIT HUP INT TERM

    actual_url=$(printf '%s\n' "$pr_info" | jq -r '.url // empty')
    actual_number=$(printf '%s\n' "$pr_info" | jq -r '.number // empty')
    state=$(printf '%s\n' "$pr_info" | jq -r '.state // empty' | tr '[:lower:]' '[:upper:]')
    actual_head=$(printf '%s\n' "$pr_info" | jq -r '.headRefOid // empty')
    actual_branch=$(printf '%s\n' "$pr_info" | jq -r '.headRefName // empty')
    actual_base=$(printf '%s\n' "$pr_info" | jq -r '.baseRefName // empty')

    if [ "$actual_url" != "$pr_url" ] ||
       [ "$actual_number" != "$pr_number" ] ||
       [ "$actual_branch" != "$branch" ] ||
       [ "$actual_base" != "$target" ] ||
       ! valid_sha "$actual_head"; then
        quarantine_metadata "$work" "GitHub PR identity no longer matches recorded URL, number, branch, head, or target." "$now"
        return 1
    fi

    case "$state" in
        OPEN)
            if [ "$actual_head" != "$expected_head" ]; then
                requeue_changed_open_head "$work" "$pr_url" "$expected_head" "$actual_head" "$now"
                return 0
            fi
            bd_update "$work" \
                --assignee="$GC_AGENT" \
                --set-metadata pr_state=open \
                --set-metadata pr_last_checked_at="$now" \
                --unset-metadata pr_reconcile_error
            echo "PENDING: $work — $pr_url is still open."
            ;;
        CLOSED)
            quarantine_terminal_pr \
                "$work" \
                pull_request_closed_unmerged \
                closed_unmerged \
                "Pull request $pr_url closed without merging." \
                "$now"
            return 1
            ;;
        MERGED)
            merged_sha=$(printf '%s\n' "$pr_info" | jq -r '.mergeCommit.oid // empty')
            merged_at=$(printf '%s\n' "$pr_info" | jq -r '.mergedAt // empty')
            if [ "$actual_head" != "$expected_head" ]; then
                quarantine_terminal_pr \
                    "$work" \
                    pull_request_merged_unvalidated_head \
                    merged_unvalidated_head \
                    "Pull request $pr_url merged a different head than refinery validated ($expected_head -> $actual_head)." \
                    "$now"
                return 1
            fi
            if ! valid_sha "$merged_sha" || [ -z "$merged_at" ]; then
                record_retryable_error "$work" merged_unverified "GitHub reported MERGED without complete merge evidence; will retry." "$now"
                return 1
            fi
            if ! rig_git fetch origin "+refs/heads/${target}:refs/remotes/origin/${target}"; then
                record_retryable_error "$work" merged_unverified "Could not fetch origin/$target to verify the PR merge; will retry." "$now"
                return 1
            fi
            if ! rig_git_without_history_overrides \
                merge-base --is-ancestor "$merged_sha" "origin/$target"; then
                record_retryable_error "$work" merged_unverified "PR merge commit $merged_sha is not reachable from origin/$target; will retry." "$now"
                return 1
            fi

            short_sha=$(rig_git rev-parse --short "$merged_sha")
            bd_update "$work" \
                --assignee="$GC_AGENT" \
                --set-metadata merge_result=merged \
                --set-metadata merged_sha="$merged_sha" \
                --set-metadata merged_target="$target" \
                --set-metadata pr_state=merged \
                --set-metadata pr_merged_at="$merged_at" \
                --set-metadata pr_last_checked_at="$now" \
                --unset-metadata rejection_reason \
                --unset-metadata pr_reconcile_error
            if ! bd_close "$work" --reason "PR #$pr_number merged to $target at $short_sha ($pr_url)"; then
                echo "pr-merge-reconcile: merge verified but bead close failed; pending marker retained for retry" >&2
                return 1
            fi
            bd_update "$work" \
                --unset-metadata pr_reconcile_pending \
                --unset-metadata blocked_reason \
                --unset-metadata gc.routed_to >/dev/null 2>&1 || true
            echo "MERGED: closed $work after verifying $merged_sha on origin/$target."
            ;;
        *)
            record_retryable_error "$work" unknown "GitHub returned unknown PR state '$state'; will retry." "$now"
            return 1
            ;;
    esac
}

case "${1:-}" in
    "")
        reconcile_one
        ;;
    record)
        shift
        record_handoff "$@"
        ;;
    *)
        usage
        ;;
esac
