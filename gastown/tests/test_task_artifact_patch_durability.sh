#!/usr/bin/env bash
# Real local Git histories; cleanup never removes a worktree in this suite.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CLEANUP="$ROOT/gastown/assets/scripts/task-artifact-cleanup.sh"
REAL_GIT=$(command -v git)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/task-patch-proof.XXXXXX")
TMP=$(cd "$TMP" && pwd -P)
trap 'rm -rf "$TMP"' EXIT
PASS=0
FAIL=0

setup_case() {
    local shape=$1
    CASE="$TMP/$TEST_NAME"
    RIG="$CASE/rig"
    REMOTE="$CASE/remote.git"
    CITY="$CASE/city"
    ARTIFACT="$CITY/.gc/worktrees/demo/artifacts/worktrees/ac-direct"
    mkdir -p "$RIG" "$(dirname "$ARTIFACT")" "$CASE/bin"
    "$REAL_GIT" init -q "$RIG"
    "$REAL_GIT" -C "$RIG" config user.name 'Patch Fixture'
    "$REAL_GIT" -C "$RIG" config user.email patch@example.invalid
    echo base >"$RIG/base"
    "$REAL_GIT" -C "$RIG" add .
    "$REAL_GIT" -C "$RIG" commit -qm base
    "$REAL_GIT" -C "$RIG" branch -M main
    BASE=$("$REAL_GIT" -C "$RIG" rev-parse HEAD)
    "$REAL_GIT" init -q --bare "$REMOTE"
    "$REAL_GIT" -C "$RIG" remote add origin "$REMOTE"
    "$REAL_GIT" -C "$RIG" worktree add -qb polecat/ac-direct "$ARTIFACT" HEAD
    echo first >"$ARTIFACT/first"
    "$REAL_GIT" -C "$ARTIFACT" add .
    "$REAL_GIT" -C "$ARTIFACT" commit -qm first
    FIRST=$("$REAL_GIT" -C "$ARTIFACT" rev-parse HEAD)
    if [[ "$shape" = multiple || "$shape" = partial ]]; then
        echo second >"$ARTIFACT/second"
        "$REAL_GIT" -C "$ARTIFACT" add .
        "$REAL_GIT" -C "$ARTIFACT" commit -qm second
    fi
    if [[ "$shape" = source-merge ]]; then
        "$REAL_GIT" -C "$RIG" checkout -qb side "$BASE"
        echo side >"$RIG/side"
        "$REAL_GIT" -C "$RIG" add .
        "$REAL_GIT" -C "$RIG" commit -qm side
        "$REAL_GIT" -C "$ARTIFACT" merge -q --no-ff -m combined side
        "$REAL_GIT" -C "$RIG" checkout -q main
    fi
    SOURCE=$("$REAL_GIT" -C "$ARTIFACT" rev-parse HEAD)
    "$REAL_GIT" -C "$ARTIFACT" push -q origin HEAD:refs/heads/polecat/ac-direct
    echo unrelated >"$RIG/unrelated"
    "$REAL_GIT" -C "$RIG" add .
    "$REAL_GIT" -C "$RIG" commit -qm unrelated
    case "$shape" in
        ancestry) "$REAL_GIT" -C "$RIG" merge -q --no-ff -m landed "$SOURCE" ;;
        cherry|partial) "$REAL_GIT" -C "$RIG" cherry-pick "$FIRST" >/dev/null ;;
        multiple) "$REAL_GIT" -C "$RIG" cherry-pick "$FIRST" "$SOURCE" >/dev/null ;;
        rebase)
            "$REAL_GIT" -C "$RIG" checkout -qb landing "$SOURCE"
            "$REAL_GIT" -C "$RIG" rebase main >/dev/null 2>&1
            "$REAL_GIT" -C "$RIG" checkout -q main
            "$REAL_GIT" -C "$RIG" merge -q --ff-only landing ;;
        different)
            echo altered >"$RIG/first"
            "$REAL_GIT" -C "$RIG" add .
            "$REAL_GIT" -C "$RIG" commit -qm 'different resolution' ;;
        source-merge)
            "$REAL_GIT" -C "$RIG" cherry-pick "$FIRST" side >/dev/null ;;
        unlanded) : ;;
        *) echo "unknown shape $shape" >&2; return 1 ;;
    esac
    TARGET=$("$REAL_GIT" -C "$RIG" rev-parse HEAD)
    "$REAL_GIT" -C "$RIG" push -q origin main
    jq -n --arg source "$SOURCE" --arg target "$TARGET" --arg path "$ARTIFACT" \
      '[{id:"ac-direct",status:"closed",metadata:{merge_result:"merged",
      target:"main",branch:"polecat/ac-direct",artifact_source_sha:$source,
      artifact_dir:$path,artifact_cleanup_state:"pending",merged_sha:$target}}]' >"$CASE/bead.json"
    cat >"$CASE/bin/gc" <<'SH'
#!/bin/sh
set -eu
printf '%s\n' "$*" >>"$FIXTURE_CASE/gc.log"
case "$*" in
  'bd --rig demo show ac-direct --json')
    n=0; [ ! -f "$FIXTURE_CASE/shows" ] || n=$(cat "$FIXTURE_CASE/shows")
    n=$((n+1)); echo "$n" >"$FIXTURE_CASE/shows"
    if [ "$n" -ge 2 ] && [ -f "$FIXTURE_CASE/changed.json" ]; then
        cat "$FIXTURE_CASE/changed.json"
    else cat "$FIXTURE_CASE/bead.json"; fi ;;
  'bd --rig demo list '*) cat "$FIXTURE_CASE/bead.json" ;;
  'bd --rig demo update ac-direct '*) : ;;
  *) echo "unexpected gc: $*" >&2; exit 91 ;;
esac
SH
    cat >"$CASE/bin/git" <<'SH'
#!/bin/sh
set -eu
printf '%s\n' "$*" >>"$FIXTURE_CASE/git.log"
case " $* " in
  *' worktree remove '*)
    [ "$*" = "-C $GC_RIG_ROOT worktree remove $FIXTURE_ARTIFACT" ] || exit 93
    echo removed >>"$FIXTURE_CASE/removals"
    exit 0 ;;
esac
if [ "$FIXTURE_MODE" = source-read-fail ]; then
    case " $* " in *' ls-remote '*) exit 73 ;; esac
fi
if [ "$FIXTURE_MODE" = fetch-fail ]; then
    case " $* " in *' fetch '*) exit 73 ;; esac
fi
case " $* " in
  *" merge-base --is-ancestor $FIXTURE_SOURCE "*)
    [ "$FIXTURE_MODE" != source-ancestry-fail ] || exit 73 ;;
  *' rev-list --merges '*)
    [ "$FIXTURE_MODE" != source-merges-fail ] || exit 73 ;;
  *' rev-parse --is-shallow-repository '*)
    [ "$FIXTURE_MODE" != shallow-query-fail ] || exit 73 ;;
esac
for query in merge-base rev-list cherry; do
    case " $* " in
      *" $query "*)
        [ "${GIT_GRAFT_FILE:-}" = /dev/null ] || exit 94
        case " $* " in *' --no-replace-objects '*) : ;; *) exit 94 ;; esac
        [ "$FIXTURE_MODE" != "$query-fail" ] || exit 73 ;;
    esac
done
case " $* " in
  *' cherry '*)
    case "$FIXTURE_MODE" in
      cherry-empty) exit 0 ;;
      cherry-malformed) echo '- definitely-not-an-object'; exit 0 ;;
      cherry-extra) printf '%s\n' "- $FIXTURE_SOURCE extra"; exit 0 ;;
      cherry-positive) printf '%s\n' "+ $FIXTURE_SOURCE"; exit 0 ;;
      cherry-blank-tail) printf '%s\n\n' "- $FIXTURE_SOURCE"; exit 0 ;;
    esac ;;
esac
if [ "$FIXTURE_MODE" = pin-race ]; then
    case " $* " in
      *' rev-parse --verify refs/remotes/origin/main^{commit} '*)
        "$FIXTURE_GIT" "$@"
        "$FIXTURE_GIT" -C "$GC_RIG_ROOT" update-ref refs/remotes/origin/main "$FIXTURE_BASE"
        exit 0 ;;
    esac
fi
exec "$FIXTURE_GIT" "$@"
SH
    chmod +x "$CASE/bin/gc" "$CASE/bin/git"
}

metadata() {
    jq "$1" "$CASE/bead.json" >"$CASE/next.json"
    mv "$CASE/next.json" "$CASE/bead.json"
}

run_cleanup() {
    local mode=${1:-normal} rc=0
    FIXTURE_CASE="$CASE" FIXTURE_MODE="$mode" FIXTURE_GIT="$REAL_GIT" \
    FIXTURE_SOURCE="$SOURCE" FIXTURE_BASE="$BASE" FIXTURE_ARTIFACT="$ARTIFACT" \
    GC_CITY_PATH="$CITY" GC_RIG=demo GC_RIG_ROOT="$RIG" \
    PATH="$CASE/bin:$PATH" sh "$CLEANUP" ${WORK_ARG-ac-direct} \
        >"$CASE/stdout" 2>"$CASE/stderr" || rc=$?
    RC=$rc
}

assert_allowed() {
    [[ "$RC" = 0 && -f "$CASE/removals" ]] || {
        echo "expected removal, rc=$RC"; cat "$CASE/stdout" "$CASE/stderr"; return 1; }
    [[ $(wc -l <"$CASE/removals") -eq 1 ]] || return 1
    rg -q 'artifact_cleanup_state=complete' "$CASE/gc.log" || return 1
    ! rg -q -- '--force' "$CASE/git.log" || return 1
    [[ -d "$ARTIFACT" ]] # Only the removal shim can run.
}

assert_blocked() {
    [[ "$RC" != 0 && ! -f "$CASE/removals" && -d "$ARTIFACT" ]] || return 1
    rg -q "ARTIFACT_CLEANUP_BLOCKED.*$1" "$CASE/stderr" || {
        cat "$CASE/stderr"; return 1; }
    rg -q "artifact_cleanup_state=${2:-blocked}" "$CASE/gc.log" || return 1
    ! rg -q -- '--unset-metadata artifact_dir' "$CASE/gc.log" || return 1
}

check() {
    local name=$1
    TEST_NAME=$name
    shift
    local rc
    set +e
    ( set -e; "$@" )
    rc=$?
    set -e
    if [[ "$rc" = 0 ]]; then echo "PASS $name"; PASS=$((PASS+1))
    else echo "FAIL $name"; FAIL=$((FAIL+1)); fi
}

allow_shape() {
    setup_case "$1" "$1-$2"
    metadata "$2"
    run_cleanup
    assert_allowed
}

block_shape() {
    setup_case "$1" "$1"
    metadata '.[0].metadata.merged_target="main"'
    run_cleanup
    assert_blocked 'source patches are not proven'
}

query_failure() {
    setup_case cherry "$1"
    metadata '.[0].metadata.merged_target="main"'
    run_cleanup "$1"
    assert_blocked 'source patches are not proven'
}

control_case() {
    local control=$1
    setup_case cherry "$control"
    metadata '.[0].metadata.merged_target="main"'
    case "$control" in
        false-merged-target)
            metadata '.[0].metadata.merged_target=false'
            run_cleanup
            assert_blocked 'incomplete direct-merge evidence' ;;
        invalid-merged-target)
            metadata '.[0].metadata.merged_target="bad..branch"'
            run_cleanup
            assert_blocked 'incomplete direct-merge evidence' ;;
        source-ref-missing)
            "$REAL_GIT" -C "$REMOTE" update-ref -d refs/heads/polecat/ac-direct
            run_cleanup
            assert_blocked 'cleanup remains pending' pending ;;
        source-ref-moved)
            "$REAL_GIT" -C "$REMOTE" update-ref refs/heads/polecat/ac-direct "$BASE"
            run_cleanup
            assert_blocked 'does not retain the artifact source' ;;
        fetch-fail|source-read-fail)
            run_cleanup "$control"
            assert_blocked 'cleanup remains pending' pending ;;
        merge-base-fail)
            run_cleanup "$control"
            assert_blocked 'merged SHA is not durable' ;;
        shallow)
            # Build a genuine shallow clone via local file transport, then
            # add the source ref and artifact in that same repository.
            "$REAL_GIT" -C "$REMOTE" symbolic-ref HEAD refs/heads/main
            "$REAL_GIT" clone -q --depth=1 "file://$REMOTE" "$CASE/shallow"
            RIG="$CASE/shallow"
            "$REAL_GIT" -C "$RIG" fetch -q --depth=1 origin refs/heads/polecat/ac-direct
            # Keep the original fixture intact; use a new canonical layout.
            ARTIFACT="$CASE/shallow-city/.gc/worktrees/demo/artifacts/worktrees/ac-direct"
            CITY="$CASE/shallow-city"
            mkdir -p "$(dirname "$ARTIFACT")"
            "$REAL_GIT" -C "$RIG" worktree add -q --detach "$ARTIFACT" "$SOURCE"
            jq --arg p "$ARTIFACT" '.[0].metadata.artifact_dir=$p' "$CASE/bead.json" >"$CASE/next.json"
            mv "$CASE/next.json" "$CASE/bead.json"
            run_cleanup
            assert_blocked 'source patches are not proven' ;;
        missing-parent)
            rm "$RIG/.git/objects/${BASE:0:2}/${BASE:2}"
            run_cleanup
            assert_blocked 'source patches are not proven' ;;
        pin-race)
            run_cleanup pin-race
            assert_allowed
            rg -qF -- "merge-base --is-ancestor $TARGET $TARGET" "$CASE/git.log"
            rg -qF -- "merge-base --is-ancestor $SOURCE $TARGET" "$CASE/git.log"
            [[ $("$REAL_GIT" -C "$RIG" rev-parse refs/remotes/origin/main) = "$BASE" ]] ;;
        old-integration)
            jq --arg base "$BASE" '.[0].metadata.merged_sha=$base' "$CASE/bead.json" >"$CASE/next.json"
            mv "$CASE/next.json" "$CASE/bead.json"
            run_cleanup
            assert_allowed ;;
        later-revert)
            "$REAL_GIT" -C "$RIG" revert --no-edit "$TARGET" >/dev/null
            "$REAL_GIT" -C "$RIG" push -q origin main
            run_cleanup
            assert_allowed
            [[ ! -e "$RIG/first" ]] ;;
        dirty)
            echo dirt >"$ARTIFACT/dirt"
            run_cleanup
            assert_blocked 'artifact is dirty' ;;
        wrong-head)
            metadata '.[0].metadata.artifact_source_sha="1111111111111111111111111111111111111111"'
            run_cleanup
            assert_blocked 'artifact HEAD mismatch' ;;
        revision-branch)
            metadata '.[0].metadata.branch="polecat/ac-direct-r2"'
            run_cleanup
            assert_blocked 'incomplete direct-merge evidence' ;;
        final-reread)
            jq '.[0].status="open"' "$CASE/bead.json" >"$CASE/changed.json"
            run_cleanup
            [[ "$RC" != 0 && ! -f "$CASE/removals" && -d "$ARTIFACT" ]]
            rg -q 'work bead changed before artifact removal' "$CASE/stderr"
            ! rg -q -- '--unset-metadata artifact_dir' "$CASE/gc.log" ;;
        nonterminal)
            metadata '.[0].status="open"'
            run_cleanup
            [[ "$RC" = 0 && ! -f "$CASE/removals" && -d "$ARTIFACT" ]]
            rg -q 'ARTIFACT_CLEANUP_DEFERRED' "$CASE/stdout" ;;
        mr-no-fallback)
            metadata '.[0].metadata.merge_result="mr_merged" | del(.[0].metadata.merged_target)'
            run_cleanup
            assert_blocked 'incomplete verified-PR evidence' ;;
        retry-selection)
            WORK_ARG='' run_cleanup
            assert_allowed
            rg -q 'list --status=closed' "$CASE/gc.log" ;;
        *) return 1 ;;
    esac
}

unlanded_integration() {
    setup_case cherry unlanded-integration
    jq --arg source "$SOURCE" '.[0].metadata.merged_sha=$source' "$CASE/bead.json" >"$CASE/next.json"
    mv "$CASE/next.json" "$CASE/bead.json"
    run_cleanup
    assert_blocked 'merged SHA is not durable'
}

history_spoof() {
    setup_case unlanded "$1"
    if [[ "$1" = replacement ]]; then
        "$REAL_GIT" -C "$RIG" replace "$TARGET" "$SOURCE"
    else
        mkdir -p "$RIG/.git/info"
        printf '%s %s\n' "$TARGET" "$SOURCE" >"$RIG/.git/info/grafts"
    fi
    run_cleanup
    assert_blocked 'source patches are not proven'
}

if [[ "${1:-}" = causal ]]; then
    check target-only-cherry allow_shape cherry '.'
    check target-only-rebase allow_shape rebase '.'
else
    check target-only-cherry allow_shape cherry '.'
    check target-only-rebase allow_shape rebase '.'
    check multiple allow_shape multiple '.[0].metadata.merged_target=null'
    check empty-target allow_shape cherry '.[0].metadata.merged_target=""'
    check already-merged allow_shape rebase '.[0].metadata.merge_result="already_merged"'
    check ancestry allow_shape ancestry '.'
    check merged-target-precedence allow_shape cherry '.[0].metadata.merged_target="main" | .[0].metadata.target="absent"'
    for shape in unlanded partial different source-merge; do
        check "$shape" block_shape "$shape"
    done
    for mode in cherry-empty cherry-malformed cherry-extra cherry-positive cherry-blank-tail cherry-fail rev-list-fail source-ancestry-fail source-merges-fail shallow-query-fail; do
        check "$mode" query_failure "$mode"
    done
    for control in invalid-merged-target false-merged-target source-ref-missing source-ref-moved \
        fetch-fail source-read-fail merge-base-fail shallow missing-parent \
        pin-race old-integration later-revert dirty wrong-head revision-branch \
        final-reread nonterminal mr-no-fallback retry-selection; do
        check "$control" control_case "$control"
    done
    check unlanded-integration unlanded_integration
    check replacements-disabled history_spoof replacement
    check grafts-disabled history_spoof graft
fi
printf 'RESULT passed=%s failed=%s\n' "$PASS" "$FAIL"
[[ "$FAIL" = 0 ]]
