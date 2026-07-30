#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMMAND="$ROOT/gastown/commands/polecat-workspace/run.sh"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

write_fake_gc() {
    local path=$1
    cat >"$path" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

state=${GC_TEST_STATE:?}
log="$state/calls.log"
printf '%s\n' "$*" >>"$log"

read_record() {
    jq -c -s '.' "$1"
}

update_record() {
    local file=$1
    shift
    local arg key value tmp
    while (($#)); do
        arg=$1
        shift
        case "$arg" in
            --set-metadata)
                value=$1
                shift
                key=${value%%=*}
                value=${value#*=}
                tmp="$file.tmp"
                jq --arg key "$key" --arg value "$value" \
                    '.metadata[$key] = $value' "$file" >"$tmp"
                mv "$tmp" "$file"
                ;;
            --unset-metadata)
                key=$1
                shift
                tmp="$file.tmp"
                jq --arg key "$key" 'del(.metadata[$key])' "$file" >"$tmp"
                mv "$tmp" "$file"
                ;;
            --status=*)
                value=${arg#--status=}
                tmp="$file.tmp"
                jq --arg value "$value" '.status = $value' "$file" >"$tmp"
                mv "$tmp" "$file"
                ;;
            --status)
                value=$1
                shift
                tmp="$file.tmp"
                jq --arg value "$value" '.status = $value' "$file" >"$tmp"
                mv "$tmp" "$file"
                ;;
            --append-notes)
                shift
                ;;
            *)
                ;;
        esac
    done
}

if [[ "${1:-}" == "bd" ]]; then
    shift
    if [[ "${1:-}" == "--rig" ]]; then
        shift 2
    fi
    action=${1:-}
    shift || true
    case "$action" in
        list)
            assignee=""
            status=""
            while (($#)); do
                case "$1" in
                    --assignee) assignee=$2; shift 2 ;;
                    --assignee=*) assignee=${1#--assignee=}; shift ;;
                    --status=*) status=${1#--status=}; shift ;;
                    --status) status=$2; shift 2 ;;
                    *) shift ;;
                esac
            done
            jq -c --arg assignee "$assignee" --arg status "$status" \
                'if .assignee == $assignee and .status == $status
                 then [.] else [] end' "$state/step.json"
            ;;
        show)
            id=$1
            case "$id" in
                step-1) read_record "$state/step.json" ;;
                root-1) read_record "$state/root.json" ;;
                source-1)
                    [[ ! -f "$state/fail-source-show" ]] || exit 1
                    if [[ -f "$state/malformed-source" ]]; then
                        printf '%s\n' '{}'
                    else
                        read_record "$state/source.json"
                    fi
                    ;;
                *) exit 1 ;;
            esac
            ;;
        update)
            id=$1
            shift
            case "$id" in
                step-1) update_record "$state/step.json" "$@" ;;
                source-1) update_record "$state/source.json" "$@" ;;
                *) exit 1 ;;
            esac
            ;;
        *)
            exit 1
            ;;
    esac
    exit 0
fi

if [[ "${1:-}" == "convoy" && "${2:-}" == "status" ]]; then
    cat "$state/convoy.json"
    exit 0
fi

if [[ "${1:-}" == "gastown" && "${2:-}" == "polecat-lease" &&
      "${3:-}" == "workspace" ]]; then
    exit 0
fi

if [[ "${1:-}" == "gastown" && "${2:-}" == "polecat-step" &&
      "${3:-}" == "block" ]]; then
    printf '%s\n' "$*" >"$state/block.log"
    exit 0
fi

if [[ "${1:-}" == "gastown" && "${2:-}" == "polecat-step" &&
      "${3:-}" == "complete" ]]; then
    if [[ -f "$state/fail-complete-once" ]]; then
        rm "$state/fail-complete-once"
        exit 1
    fi
    tmp="$state/step.json.tmp"
    jq '.status = "closed" | .metadata["gc.outcome"] = "pass"' \
        "$state/step.json" >"$tmp"
    mv "$tmp" "$state/step.json"
    printf '%s\n' "POLECAT_STEP_COMPLETE"
    exit 0
fi

exit 1
EOF
    chmod 755 "$path"
}

init_fixture() {
    local tmp=$1 setup_command=$2
    local remote seed rig city state fake vars
    remote="$tmp/remote.git"
    seed="$tmp/seed"
    rig="$tmp/rig"
    city="$tmp/city"
    state="$tmp/state"
    fake="$tmp/gc"
    mkdir -p "$state" "$city/.gc/worktrees/demo"

    git init -q --bare "$remote"
    git -C "$remote" symbolic-ref HEAD refs/heads/main
    git init -q "$seed"
    git -C "$seed" config user.email workspace-test@example.com
    git -C "$seed" config user.name "Workspace Test"
    printf 'base\n' >"$seed/base.txt"
    git -C "$seed" add base.txt
    git -C "$seed" commit -qm base
    git -C "$seed" branch -M main
    git -C "$seed" remote add origin "$remote"
    git -C "$seed" push -q -u origin main
    git clone -q "$remote" "$rig"
    git -C "$rig" config user.email workspace-test@example.com
    git -C "$rig" config user.name "Workspace Test"

    vars=$(jq -cn \
        --arg setup "$setup_command" \
        '{base_branch:"main", rig_name:"demo",
          binding_prefix:"", setup_command:$setup}')
    jq -cn --arg vars "$vars" '{
      id:"root-1", status:"in_progress", assignee:"",
      metadata:{
        "gc.kind":"workflow",
        "gc.formula_contract":"graph.v2",
        "gc.formula_name":"mol-polecat-work",
        "gc.input_convoy_id":"convoy-1",
        "gc.var.base_branch":"main",
        "gc.var.rig_name":"demo",
        "gc.var.binding_prefix":"",
        "gc.graphv2_vars.v1":$vars
      }
    }' >"$state/root.json"
    jq -cn '{
      id:"step-1", status:"in_progress", assignee:"polecat/demo",
      metadata:{
        "gc.step_ref":"mol-polecat-work.workspace-setup",
        "gc.root_bead_id":"root-1"
      }
    }' >"$state/step.json"
    jq -cn '{
      id:"source-1", status:"open", assignee:"",
      metadata:{}
    }' >"$state/source.json"
    jq -cn '{
      schema_version:"1",
      convoy:{id:"convoy-1"},
      children:[{id:"source-1"}]
    }' >"$state/convoy.json"
    : >"$state/calls.log"
    write_fake_gc "$fake"
}

run_workspace() {
    local tmp=$1
    shift
    GC_BIN="$tmp/gc" \
    GC_TEST_STATE="$tmp/state" \
    GC_CITY_PATH="$tmp/city" \
    GC_RIG=demo \
    GC_RIG_ROOT="$tmp/rig" \
    GC_SESSION_ID=session-1 \
    GC_SESSION_NAME=polecat/demo \
    BEADS_ACTOR=polecat/demo \
    GIT_DIR=/definitely/not/the/rig \
        "$COMMAND" execute "$@"
}

test_receipt_retry_and_closed_replay() {
    local tmp artifact output rc setup_command
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    setup_command='printf "setup\n" >>"$GC_CITY_PATH/setup.log"'
    init_fixture "$tmp" "$setup_command"
    touch "$tmp/state/fail-complete-once"

    set +e
    output=$(run_workspace "$tmp" 2>&1)
    rc=$?
    set -e
    [[ "$rc" -eq 75 ]] ||
        fail "completion uncertainty returned $rc instead of 75: $output"
    [[ "$(wc -l <"$tmp/city/setup.log")" -eq 1 ]] ||
        fail "first workspace attempt did not run setup exactly once"
    jq -e '
      .status == "in_progress" and
      .metadata["gc.polecat_workspace_version"] == "1" and
      .metadata["gc.polecat_workspace_session_id"] == "session-1"
    ' "$tmp/state/step.json" >/dev/null ||
        fail "completion uncertainty did not preserve an exact live receipt"

    output=$(run_workspace "$tmp" 2>&1) ||
        fail "receipt retry did not complete: $output"
    rg -q 'POLECAT_WORKSPACE_EXECUTE_COMPLETE .*replay=false' <<<"$output" ||
        fail "receipt retry lacked the live completion receipt"
    [[ "$(wc -l <"$tmp/city/setup.log")" -eq 1 ]] ||
        fail "receipt retry repeated the setup command"
    jq -e '
      .status == "closed" and .metadata["gc.outcome"] == "pass"
    ' "$tmp/state/step.json" >/dev/null ||
        fail "receipt retry did not close/pass the exact step"

    artifact=$(jq -er '.metadata.artifact_dir' "$tmp/state/source.json")
    [[ "$artifact" == "$tmp/city/.gc/worktrees/demo/artifacts/worktrees/source-1" ]] ||
        fail "workspace used a noncanonical artifact path: $artifact"
    [[ "$(git -C "$artifact" branch --show-current)" == "polecat/source-1" ]] ||
        fail "workspace did not select the canonical task branch"
    jq -e \
        --arg artifact "$artifact" '
        .status == "open" and .assignee == "" and
        .metadata.artifact_dir == $artifact and
        .metadata.branch == "polecat/source-1" and
        (.metadata.fork_sha | type) == "string" and
        (.metadata.fork_sha | length) == 40 and
        (.metadata | has("work_dir") | not)
    ' "$tmp/state/source.json" >/dev/null ||
        fail "workspace source metadata did not read back canonically"

    output=$(run_workspace "$tmp" 2>&1) ||
        fail "closed workspace replay failed: $output"
    rg -q 'POLECAT_WORKSPACE_EXECUTE_COMPLETE .*replay=true' <<<"$output" ||
        fail "closed workspace replay lacked an exact replay receipt"
    [[ "$(wc -l <"$tmp/city/setup.log")" -eq 1 ]] ||
        fail "closed replay repeated project setup"
}

test_successful_block_is_nonzero() {
    local tmp collision output rc
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    init_fixture "$tmp" ""
    collision="$tmp/city/.gc/worktrees/demo/artifacts/worktrees/source-1"
    mkdir -p "$collision"
    printf 'preserve\n' >"$collision/unrelated"

    set +e
    output=$(run_workspace "$tmp" 2>&1)
    rc=$?
    set -e
    [[ "$rc" -eq 64 ]] ||
        fail "successful durable block returned $rc instead of 64: $output"
    rg -q 'workspace.artifact-path-collision' "$tmp/state/block.log" ||
        fail "artifact collision did not invoke the exact durable block"
    [[ -f "$collision/unrelated" ]] ||
        fail "artifact collision handling destroyed unrelated state"
    ! rg -q 'POLECAT_WORKSPACE_EXECUTE_COMPLETE' <<<"$output" ||
        fail "successful durable block was reported as workspace success"
}

test_partial_receipt_fails_closed_without_replaying_setup() {
    local tmp output rc setup_command
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    setup_command='printf "should-not-run\n" >>"$GC_CITY_PATH/setup.log"'
    init_fixture "$tmp" "$setup_command"
    jq '.metadata["gc.polecat_workspace_version"] = "1"' \
        "$tmp/state/step.json" >"$tmp/state/step.json.tmp"
    mv "$tmp/state/step.json.tmp" "$tmp/state/step.json"

    set +e
    output=$(run_workspace "$tmp" 2>&1)
    rc=$?
    set -e
    [[ "$rc" -eq 75 ]] ||
        fail "partial workspace receipt returned $rc instead of 75: $output"
    rg -q 'partial or conflicting durable receipt' <<<"$output" ||
        fail "partial workspace receipt lacked a fail-closed diagnostic"
    [[ ! -e "$tmp/city/setup.log" ]] ||
        fail "partial workspace receipt allowed project setup to run"
    jq -e '.status == "in_progress"' "$tmp/state/step.json" >/dev/null ||
        fail "partial workspace receipt terminalized the live step"
    ! rg -q 'gastown polecat-step complete' "$tmp/state/calls.log" ||
        fail "partial workspace receipt invoked completion"
}

test_source_reads_fail_closed_before_workspace_mutation() {
    local mode tmp output rc
    for mode in fail-source-show malformed-source; do
        tmp=$(mktemp -d)
        trap 'rm -rf "$tmp"' RETURN
        init_fixture "$tmp" ""
        touch "$tmp/state/$mode"

        set +e
        output=$(run_workspace "$tmp" 2>&1)
        rc=$?
        set -e
        [[ "$rc" -eq 75 ]] ||
            fail "$mode returned $rc instead of 75: $output"
        [[ ! -e "$tmp/city/.gc/worktrees/demo/artifacts" ]] ||
            fail "$mode created an artifact before source authority verified"
        [[ ! -e "$tmp/state/block.log" ]] ||
            fail "$mode converted unreadable source state into a hard block"
        rm -rf "$tmp"
        trap - RETURN
    done
}

test_redirected_artifact_root_is_blocked_and_preserved() {
    local tmp outside output rc
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    init_fixture "$tmp" ""
    outside="$tmp/outside"
    mkdir -p "$outside"
    printf 'preserve\n' >"$outside/sentinel"
    ln -s "$outside" "$tmp/city/.gc/worktrees/demo/artifacts"

    set +e
    output=$(run_workspace "$tmp" 2>&1)
    rc=$?
    set -e
    [[ "$rc" -eq 64 ]] ||
        fail "redirected artifact root returned $rc instead of 64: $output"
    rg -q 'workspace.artifact-root-unsafe' "$tmp/state/block.log" ||
        fail "redirected artifact root did not use the exact durable block"
    [[ -f "$outside/sentinel" ]] ||
        fail "redirected artifact root handling modified the external target"
}

test_receipt_retry_and_closed_replay
test_successful_block_is_nonzero
test_partial_receipt_fails_closed_without_replaying_setup
test_source_reads_fail_closed_before_workspace_mutation
test_redirected_artifact_root_is_blocked_and_preserved

echo "polecat workspace command tests passed"
