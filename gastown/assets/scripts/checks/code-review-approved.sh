#!/usr/bin/env bash
# Ralph check script for code review loop (personal work formula).
#
# Reads the code review verdict from bead metadata.
# Exit 0 = pass (stop iterating), exit 1 = fail (retry).
#
# Expected metadata key: code_review.verdict
# Values: "done" | "iterate"

set -euo pipefail

# json_payload strips any non-JSON prefix lines (e.g., the bead CLI's
# `warning: beads.role not configured` diagnostic, which is emitted on
# stdout before the real payload). Without this, jq fails to parse the
# combined stdout and the script exits with empty output and status 1,
# which has produced flaky CI failures for
# TestReviewCheckScriptsPreferNewestVerdictAcrossRalphStep.
json_payload() {
    awk 'found || /^[[:space:]]*[[{]/{ found=1; print }'
}

# root_members ROOT prints every member of molecule ROOT as one JSON array.
#
# `gc bd list --all` reads only the work store. On a split-store city the
# molecule's steps live in the class binding, so it answered [] and the gate
# never saw a verdict. `gc ready` federates the city store, the rig stores and
# the relocated graph store; it takes one --status and has no --all, so the
# member set is the union of one leg per status. A leg that fails fails the
# whole read rather than contributing an empty set.
root_members() {
    local root="$1" tmp st rc=0
    tmp="$(mktemp -d)" || return 1
    for st in open in_progress blocked closed; do
        { gc ready --metadata-field "gc.root_bead_id=$root" --status "$st" --limit 0 --json 2>/dev/null |
            json_payload >"$tmp/$st.json" || printf '%s\n' "$st" >>"$tmp/failed"; } &
    done
    wait
    if [ -s "$tmp/failed" ]; then
        echo "root_members: gc ready failed for status: $(tr '\n' ' ' <"$tmp/failed")" >&2
        rc=1
    fi
    if [ "$rc" -eq 0 ]; then
        jq -s 'map(select(type == "array")) | add // [] | unique_by(.id)' "$tmp"/*.json || rc=1
    fi
    rm -rf "$tmp"
    return "$rc"
}

bd_json() {
    local attempt=0
    local output=""
    local stderr_file=""
    local last_stderr=""
    while [ "$attempt" -lt 10 ]; do
        stderr_file=$(mktemp)
        if output=$(gc bd "$@" 2>"$stderr_file" | json_payload) && [ -n "$output" ]; then
            rm -f "$stderr_file"
            printf '%s\n' "$output"
            return 0
        fi
        if [ -s "$stderr_file" ]; then
            last_stderr=$(cat "$stderr_file")
        fi
        rm -f "$stderr_file"
        attempt=$((attempt + 1))
        sleep 0.2
    done
    if [ -n "$last_stderr" ]; then
        printf '%s\n' "$last_stderr" >&2
    fi
    return 1
}

load_bead_context() {
    local bead_id="$1"
    local bead_json=""
    local attempt=0

    ATTEMPT=""
    ROOT_ID=""

    while [ "$attempt" -lt 5 ]; do
        bead_json=$(bd_json show "$bead_id" --json) || bead_json=""
        if [ -n "$bead_json" ]; then
            ATTEMPT=$(printf '%s\n' "$bead_json" | jq -r 'if type == "array" then (.[0].metadata["gc.attempt"] // "") else (.metadata["gc.attempt"] // "") end' 2>/dev/null || printf '')
            ROOT_ID=$(printf '%s\n' "$bead_json" | jq -r 'if type == "array" then (.[0].metadata["gc.root_bead_id"] // "") else (.metadata["gc.root_bead_id"] // "") end' 2>/dev/null || printf '')
            if [ -n "$ATTEMPT" ] && [ -n "$ROOT_ID" ]; then
                return 0
            fi
        fi
        attempt=$((attempt + 1))
        sleep 0.2
    done

    ATTEMPT=""
    ROOT_ID=""
    return 1
}

load_verdict() {
    local apply_ref="$1"
    local root_id="$2"
    local current=""
    local previous=""
    local stable_run=0
    local attempt=0
    # See adopt-pr-review-approved.sh load_verdict for rationale: sample
    # until two consecutive reads agree, then return. Guards against a
    # race with the bead store observed in
    # TestReviewCheckScriptsPreferNewestVerdictAcrossRalphStep.
    while [ "$attempt" -lt 10 ]; do
        current=$(
            root_members "$root_id" 2>/dev/null |
                json_payload |
                jq -r --arg ref "$apply_ref" --arg root "$root_id" '
                    [
                        .[]
                        | select(.metadata["gc.step_ref"] == $ref and .metadata["gc.root_bead_id"] == $root)
                        | {
                            verdict: .metadata["code_review.verdict"],
                            timestamp: (.updated_at // .created_at // ""),
                            id: (.id // "")
                        }
                        | select(.verdict != null and .verdict != "")
                    ]
                    | sort_by(.timestamp, .id)
                    | .[-1].verdict // ""
                ' 2>/dev/null
        ) || current=""
        if [ -n "$current" ] && [ "$current" = "$previous" ]; then
            stable_run=$((stable_run + 1))
            if [ "$stable_run" -ge 1 ]; then
                printf '%s\n' "$current"
                return 0
            fi
        else
            stable_run=0
        fi
        previous="$current"
        attempt=$((attempt + 1))
        sleep 0.2
    done

    if [ -n "$current" ]; then
        printf '%s\n' "$current"
        return 0
    fi
    return 1
}

BEAD_ID="${GC_BEAD_ID:-}"
if [ -z "$BEAD_ID" ]; then
    echo "ERROR: GC_BEAD_ID not set" >&2
    exit 1
fi

if ! load_bead_context "$BEAD_ID"; then
    echo "ERROR: missing gc.attempt or gc.root_bead_id on $BEAD_ID" >&2
    exit 1
fi

APPLY_REF="mol-personal-work-v2.code-review-loop.run.${ATTEMPT}.apply-code-fixes"
if ! VERDICT=$(load_verdict "$APPLY_REF" "$ROOT_ID"); then
    echo "ERROR: unable to determine code review verdict" >&2
    exit 2
fi

case "$VERDICT" in
    done|approved|pass)
        echo "Code review approved — stopping iteration"
        exit 0
        ;;
    iterate|fail|retry)
        echo "Code review needs iteration — retrying"
        exit 1
        ;;
    *)
        echo "Unknown verdict: $VERDICT — treating as iterate" >&2
        exit 1
        ;;
esac
