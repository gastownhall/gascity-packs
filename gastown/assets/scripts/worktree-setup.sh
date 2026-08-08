#!/bin/sh
# worktree-setup.sh — idempotent git worktree creation for Gas City agents.
#
# Usage: worktree-setup.sh <rig-root> <target-dir> <agent-name> [--sync] [--base <branch>]
#
# Ensures the target directory is a git worktree of the rig repo. For
# backward compatibility, the older <repo-dir> <agent-name> <city-root>
# signature still works and resolves the target under
# <city-root>/.gc/worktrees/<rig>/<agent-name>.
#
# --base pins the start point for a newly created worktree branch. Packs pass
# the rig's configured default_branch through it ({{.DefaultBranch}}); when it
# is absent the script probes origin/HEAD as it always has.
#
# Called from pre_start in pack configs. Runs before the session is created
# so the agent starts IN the worktree directory.

set -eu

RIG_ROOT="${1:?usage: worktree-setup.sh <rig-root> <target-dir> <agent-name> [--sync] [--base <branch>]}"
ARG2="${2:?missing target-dir}"
ARG3="${3:?missing agent-name}"

is_path_like() {
    # Legacy mode passes the city path as arg 3. Agent names are validated
    # elsewhere and are not expected to look like filesystem paths.
    case "$1" in
        */*|.*|*:*|*\\*) return 0 ;;
        *) return 1 ;;
    esac
}

if is_path_like "$ARG3"; then
    AGENT="$ARG2"
    CITY="$ARG3"
    RIG=$(basename "$RIG_ROOT")
    WT="$CITY/.gc/worktrees/$RIG/$AGENT"
else
    WT="$ARG2"
    AGENT="$ARG3"
fi

# Trailing flags are order-independent and shared by both positional forms.
# Unknown arguments are a hard error: this script decides which commit an
# agent's whole worktree is cut from, so a typo'd flag must not be ignored.
SYNC=""
BASE=""
shift 3
while [ "$#" -gt 0 ]; do
    case "$1" in
        --sync) SYNC="--sync" ;;
        --base)
            if [ "$#" -lt 2 ]; then
                echo "worktree-setup: --base requires a branch name" >&2
                exit 2
            fi
            BASE="$2"
            shift
            ;;
        --base=*) BASE="${1#--base=}" ;;
        *)
            echo "worktree-setup: unknown argument: $1" >&2
            exit 2
            ;;
    esac
    shift
done

sync_worktree() {
    [ "$SYNC" = "--sync" ] || return 0
    if ! git -C "$WT" remote get-url origin >/dev/null 2>&1; then
        return 0
    fi
    git -C "$WT" fetch origin 2>/dev/null || true
    git -C "$WT" pull --rebase 2>/dev/null || true
}

branch_name() {
    # Namescape worktree branches by target path so multiple cities or rigs
    # can share one underlying repo without colliding on global refs like
    # gc-refinery or gc-polecat-1.
    HASH=$(printf '%s' "$WT" | git -C "$RIG_ROOT" hash-object --stdin | cut -c1-12)
    printf 'gc-%s-%s' "$AGENT" "$HASH"
}

# resolve_start_point echoes the ref a new worktree branch is cut from, or
# nothing when the worktree should be created from the current checkout.
#
# An explicit --base is a deliberate pin (the rig's default_branch): honor it
# exactly or fail. Silently falling back to origin/HEAD is what let a rig
# pinned to an integration branch get worktrees cut from main, so its agents
# debugged a tree that did not match the deployed binary (gas-e6r).
#
# Remote-first, then local: the remote tip is preferred so long-lived agent
# branches do not drift behind origin, but a branch that exists only locally
# (an integration branch that was never pushed) is still a valid pin.
resolve_start_point() {
    if [ -n "$BASE" ]; then
        git -C "$RIG_ROOT" fetch origin "$BASE" >/dev/null 2>&1 || true
        if git -C "$RIG_ROOT" show-ref --verify --quiet "refs/remotes/origin/$BASE"; then
            printf 'refs/remotes/origin/%s' "$BASE"
            return 0
        fi
        if git -C "$RIG_ROOT" show-ref --verify --quiet "refs/heads/$BASE"; then
            printf 'refs/heads/%s' "$BASE"
            return 0
        fi
        echo "worktree-setup: base branch '$BASE' does not exist in $RIG_ROOT" >&2
        echo "worktree-setup: looked for refs/remotes/origin/$BASE and refs/heads/$BASE" >&2
        echo "worktree-setup: refusing to fall back to origin/HEAD — fix the rig's default_branch, or fetch/create the branch" >&2
        return 1
    fi

    # No pin. Refresh and use the upstream default so the agent's persistent
    # worktree branch starts from the remote tip rather than whatever happened
    # to be checked out locally. Without this fetch + explicit start point the
    # branch inherits a stale local default; across many beads that drifts
    # behind origin, and feature branches cut from it carry already-merged
    # commits that the refinery rebase rejects as spurious duplicates with
    # mismatched hashes.
    DEFAULT_REF=$(git -C "$RIG_ROOT" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null || true)
    if [ -n "$DEFAULT_REF" ]; then
        git -C "$RIG_ROOT" fetch origin "${DEFAULT_REF#refs/remotes/origin/}" >/dev/null 2>&1 || true
        printf '%s' "$DEFAULT_REF"
        return 0
    fi

    # No pin and no origin/HEAD. This is the one remaining implicit case, so
    # say so rather than letting the base be a silent mystery.
    echo "worktree-setup: no --base given and origin/HEAD is unset in $RIG_ROOT; creating $WT from the current checkout" >&2
    return 0
}

# Idempotent: skip if worktree already exists.
if [ -d "$WT/.git" ] || [ -f "$WT/.git" ]; then
    sync_worktree
    exit 0
fi

mkdir -p "$(dirname "$WT")"

STAGE=""

merge_stage_entry() (
    SRC="$1"
    DST="$2"

    if [ -d "$SRC" ]; then
        mkdir -p "$DST"
        for ENTRY in "$SRC"/.[!.]* "$SRC"/..?* "$SRC"/*; do
            [ -e "$ENTRY" ] || continue
            merge_stage_entry "$ENTRY" "$DST/$(basename "$ENTRY")"
        done
        rmdir "$SRC" 2>/dev/null || true
        exit 0
    fi

    if [ -e "$DST" ]; then
        exit 0
    fi
    mv "$SRC" "$DST"
)

restore_stage() {
    [ -n "$STAGE" ] || return 0
    mkdir -p "$WT"
    for ENTRY in "$STAGE"/.[!.]* "$STAGE"/..?* "$STAGE"/*; do
        [ -e "$ENTRY" ] || continue
        merge_stage_entry "$ENTRY" "$WT/$(basename "$ENTRY")"
    done
    rmdir "$STAGE" 2>/dev/null || true
    STAGE=""
}

if [ -d "$WT" ] && [ "$(find "$WT" -mindepth 1 -maxdepth 1 | head -n 1)" ]; then
    STAGE=$(mktemp -d "$(dirname "$WT")/.gascity-worktree-stage.XXXXXX")
    find "$WT" -mindepth 1 -maxdepth 1 -exec mv {} "$STAGE"/ \;
    trap 'restore_stage' EXIT HUP INT TERM
fi

rmdir "$WT" 2>/dev/null || true
# Clear stale metadata from removed worktrees before branch/worktree lookup.
git -C "$RIG_ROOT" worktree prune >/dev/null 2>&1 || true

BRANCH=$(branch_name)

if git -C "$RIG_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH"; then
    # The agent's persistent branch already exists; its start point was chosen
    # when it was created, so --base is not consulted here.
    if ! GIT_LFS_SKIP_SMUDGE=1 git -C "$RIG_ROOT" worktree add "$WT" "$BRANCH"; then
        echo "worktree-setup: failed to create worktree at $WT from $RIG_ROOT (branch $BRANCH)" >&2
        restore_stage
        exit 1
    fi
else
    if ! START_POINT=$(resolve_start_point); then
        restore_stage
        exit 1
    fi
    if [ -n "$START_POINT" ]; then
        WORKTREE_ADD="git -C $RIG_ROOT worktree add $WT -b $BRANCH $START_POINT"
    else
        WORKTREE_ADD="git -C $RIG_ROOT worktree add $WT -b $BRANCH"
    fi
    if ! GIT_LFS_SKIP_SMUDGE=1 $WORKTREE_ADD; then
        echo "worktree-setup: failed to create worktree at $WT from $RIG_ROOT (branch $BRANCH)" >&2
        restore_stage
        exit 1
    fi
fi

if [ -n "$STAGE" ]; then
    for ENTRY in "$STAGE"/.[!.]* "$STAGE"/..?* "$STAGE"/*; do
        [ -e "$ENTRY" ] || continue
        merge_stage_entry "$ENTRY" "$WT/$(basename "$ENTRY")"
    done
    rm -rf "$STAGE"
    STAGE=""
fi
trap - EXIT HUP INT TERM

# Bead redirect for filesystem beads.
mkdir -p "$WT/.beads"
echo "$RIG_ROOT/.beads" > "$WT/.beads/redirect"

# Submodule init (best-effort).
git -C "$WT" submodule init 2>/dev/null || true

# Keep runtime ignores local to git metadata instead of mutating the tracked
# repository .gitignore. --git-path resolves the exclude file Git actually
# consults for this worktree, including linked-worktree layouts.
EXCLUDE=$(git -C "$WT" rev-parse --git-path info/exclude)
case "$EXCLUDE" in
    /*) ;;
    *) EXCLUDE="$WT/$EXCLUDE" ;;
esac
mkdir -p "$(dirname "$EXCLUDE")"
touch "$EXCLUDE"

MARKER="# Gas City worktree infrastructure (local excludes)"
if ! grep -qF "$MARKER" "$EXCLUDE" 2>/dev/null; then
    if [ -s "$EXCLUDE" ] && [ "$(tail -c 1 "$EXCLUDE" 2>/dev/null || true)" != "" ]; then
        printf '\n' >> "$EXCLUDE"
    fi
    printf '%s\n' "$MARKER" >> "$EXCLUDE"
fi

append_exclude() {
    PATTERN="$1"
    grep -qxF "$PATTERN" "$EXCLUDE" 2>/dev/null || printf '%s\n' "$PATTERN" >> "$EXCLUDE"
}

append_exclude ".beads/redirect"
append_exclude ".beads/hooks/"
append_exclude ".beads/formulas/"
append_exclude ".logs/"
append_exclude "worktrees/"
append_exclude "__pycache__/"
append_exclude ".claude/"
append_exclude ".codex/"
append_exclude ".gemini/"
append_exclude ".opencode/"
append_exclude ".github/hooks/"
append_exclude ".github/copilot-instructions.md"
append_exclude "state.json"

# Optional sync.
sync_worktree

exit 0
