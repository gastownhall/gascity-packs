#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
GASTOWN="$ROOT/gastown"
POLECAT_FORMULA="$GASTOWN/formulas/mol-polecat-work.toml"
WITNESS_FORMULA="$GASTOWN/formulas/mol-witness-patrol.toml"
SHUTDOWN_FORMULA="$GASTOWN/formulas/mol-shutdown-dance.toml"
REFINERY_FORMULA="$GASTOWN/formulas/mol-refinery-patrol.toml"
WORKTREE_SETUP="$GASTOWN/assets/scripts/worktree-setup.sh"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

extract_validator() {
    local output=$1
    python3 - "$POLECAT_FORMULA" "$output" <<'PY'
import pathlib
import sys
import tomllib

formula_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
with formula_path.open("rb") as handle:
    formula = tomllib.load(handle)
workspace = next(step for step in formula["steps"] if step["id"] == "workspace-setup")
description = workspace["description"]
begin = description.index("# BEGIN ARTIFACT_WORKTREE_VALIDATOR")
end = description.index("# END ARTIFACT_WORKTREE_VALIDATOR", begin)
block = description[begin:end].splitlines()[1:]
output_path.write_text("\n".join(block) + "\n", encoding="utf-8")
PY
}

extract_shutdown_probe() {
    local output=$1
    python3 - "$SHUTDOWN_FORMULA" "$output" <<'PY'
import pathlib
import sys
import tomllib

formula_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
with formula_path.open("rb") as handle:
    formula = tomllib.load(handle)
execute = next(step for step in formula["steps"] if step["id"] == "execute")
description = execute["description"]
begin = description.index("# BEGIN SHUTDOWN_PROGRESS_PROBE")
end = description.index("# END SHUTDOWN_PROGRESS_PROBE", begin)
block = description[begin:end].splitlines()[1:]
output_path.write_text("\n".join(block) + "\n", encoding="utf-8")
PY
}

extract_workspace_creation() {
    local output=$1
    python3 - "$POLECAT_FORMULA" "$output" <<'PY'
import pathlib
import re
import sys
import tomllib

formula_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
with formula_path.open("rb") as handle:
    formula = tomllib.load(handle)
workspace = next(step for step in formula["steps"] if step["id"] == "workspace-setup")
blocks = re.findall(r"```bash\n(.*?)```", workspace["description"], re.DOTALL)
if len(blocks) < 4:
    raise SystemExit(f"workspace-setup has {len(blocks)} bash blocks; expected at least 4")
script = "\n".join(blocks[:4])
script = script.replace("{{convoy_id}}", "convoy-test")
script = script.replace("{{base_branch}}", "main")
if "{{" in script:
    raise SystemExit("workspace creation extraction retained an unresolved template")
output_path.write_text(script, encoding="utf-8")
PY
}

init_repo() {
    local repo=$1
    git init -q "$repo"
    git -C "$repo" config user.email artifact-test@example.com
    git -C "$repo" config user.name "Artifact Test"
    printf 'fixture\n' >"$repo/fixture.txt"
    git -C "$repo" add fixture.txt
    git -C "$repo" commit -qm "fixture"
}

test_workspace_creation_uses_canonical_sibling() {
    local tmp rig remote city provider canonical setup calls bd_subcommand
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    rig="$tmp/rig"
    remote="$tmp/remote.git"
    city="$tmp/city"
    provider="$city/.gc/worktrees/demo/polecats/gastown.nux"
    canonical="$city/.gc/worktrees/demo/artifacts/worktrees/ac-safe1"
    setup="$tmp/workspace-create.sh"
    calls="$tmp/gc-calls"
    bd_subcommand=$(printf '%s%s' b d)

    init_repo "$rig"
    git -C "$rig" branch -M main
    git init -q --bare "$remote"
    git -C "$remote" symbolic-ref HEAD refs/heads/main
    git -C "$rig" remote add origin "$remote"
    git -C "$rig" push -qu origin main
    mkdir -p "$(dirname "$provider")"
    git -C "$rig" worktree add -qb provider-home "$provider" main
    extract_workspace_creation "$setup"

    (
        gc() {
            printf '%s\n' "$*" >>"$calls"
            case "$*" in
                "convoy status convoy-test --json")
                    printf '%s\n' '{"children":[{"id":"ac-safe1"}]}'
                    ;;
                "$bd_subcommand show ac-safe1 --json")
                    printf '%s\n' '[{"metadata":{}}]'
                    ;;
                "$bd_subcommand update ac-safe1 --set-metadata artifact_dir="*)
                    return 0
                    ;;
                "runtime drain-ack")
                    fail "canonical workspace creation unexpectedly drain-acked"
                    ;;
                *)
                    fail "unexpected gc call during workspace creation: $*"
                    ;;
            esac
        }
        export GC_CITY_PATH="$city"
        export GC_RIG=demo
        export GC_RIG_ROOT="$rig"
        cd "$provider"
        # shellcheck source=/dev/null
        source "$setup"
    )

    [[ -e "$canonical/.git" ]] ||
        fail "formula did not create the canonical sibling task worktree"
    [[ "$(git -C "$canonical" rev-parse --show-toplevel)" == "$canonical" ]] ||
        fail "canonical artifact path is not a Git worktree root"
    [[ ! -e "$provider/worktrees/ac-safe1" ]] ||
        fail "formula created a nested task worktree under the provider home"
    grep -qF \
        "$bd_subcommand update ac-safe1 --set-metadata artifact_dir=$canonical --unset-metadata work_dir" \
        "$calls" ||
        fail "formula did not record the exact canonical artifact_dir"
}

test_worktree_setup_ignores_gc_without_mutating_tracked_or_global_ignores() {
    local tmp rig city provider global_config global_ignore exclude
    local tracked_before config_before global_before status
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    rig="$tmp/rig"
    city="$tmp/city"
    provider="$city/.gc/worktrees/demo/polecats/gastown.nux"
    global_config="$tmp/global.gitconfig"
    global_ignore="$tmp/global-ignore"

    init_repo "$rig"
    printf '/tracked-only\n' >"$rig/.gitignore"
    git -C "$rig" add .gitignore
    git -C "$rig" commit -qm "tracked ignore fixture"

    printf 'global-only\n' >"$global_ignore"
    GIT_CONFIG_GLOBAL="$global_config" \
        git config --global core.excludesFile "$global_ignore"
    tracked_before=$(git -C "$rig" hash-object .gitignore)
    config_before=$(git hash-object "$global_config")
    global_before=$(git hash-object "$global_ignore")

    mkdir -p "$provider/.gc"
    printf '{"runtime":"scaffold"}\n' >"$provider/.gc/settings.json"
    GIT_CONFIG_GLOBAL="$global_config" \
        "$WORKTREE_SETUP" "$rig" "$provider" gastown.nux

    [[ -e "$provider/.git" ]] ||
        fail "worktree setup did not replace the scaffold with a Git worktree"
    [[ -f "$provider/.gc/settings.json" ]] ||
        fail "worktree setup did not preserve staged .gc runtime metadata"
    status=$(GIT_CONFIG_GLOBAL="$global_config" \
        git -C "$provider" status --porcelain --untracked-files=all)
    [[ -z "$status" ]] ||
        fail ".gc runtime metadata remained visible to git status: $status"
    [[ "$(git -C "$provider" hash-object .gitignore)" == "$tracked_before" ]] ||
        fail "worktree setup mutated the tracked .gitignore"
    [[ "$(git hash-object "$global_config")" == "$config_before" ]] ||
        fail "worktree setup mutated global Git configuration"
    [[ "$(git hash-object "$global_ignore")" == "$global_before" ]] ||
        fail "worktree setup mutated the user's global excludes file"

    exclude=$(git -C "$provider" rev-parse --git-path info/exclude)
    [[ "$(grep -cxF '.gc/' "$exclude")" -eq 1 ]] ||
        fail "repository-local exclude does not contain exactly one .gc/ entry"

    # Existing worktrees take the idempotent fast path. That path must still
    # repair an installation created before .gc/ became a runtime exclude.
    sed -i '\|^\.gc/$|d' "$exclude"
    GIT_CONFIG_GLOBAL="$global_config" \
        "$WORKTREE_SETUP" "$rig" "$provider" gastown.nux
    [[ "$(grep -cxF '.gc/' "$exclude")" -eq 1 ]] ||
        fail "existing-worktree fast path did not restore exactly one .gc/ entry"
}

test_shutdown_probe_scopes_rig_and_fails_closed() {
    local tmp probe calls output bd_subcommand
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    probe="$tmp/probe.sh"
    calls="$tmp/calls"
    output="$tmp/output"
    bd_subcommand=$(printf '%s%s' b d)
    extract_shutdown_probe "$probe"

    (
        gc() {
            printf '%s\n' "$*" >> "$calls"
            case "$*" in
                "session list --state=all --json")
                    printf '%s\n' '{"sessions":[{"id":"session-1","name":"demo/gastown.worker","template":"gastown.polecat","rig":"demo","alias":"demo/gastown.worker","agent_name":"demo/gastown.worker","session_name":"demo--worker","work_dir":"/missing/provider"}]}'
                    ;;
                "$bd_subcommand --rig demo list --status=in_progress --json --limit=0")
                    printf '%s\n' '[]'
                    ;;
                *)
                    return 1
                    ;;
            esac
        }
        target="demo/gastown.worker"
        # shellcheck source=/dev/null
        source "$probe"
    ) > "$output"

    rg -q "^${bd_subcommand} --rig demo list --status=in_progress --json --limit=0$" "$calls" ||
        fail "shutdown probe did not route the target work query to its rig store"
    rg -q '^progress_signal=none$' "$output" ||
        fail "successful exact lookup with no claimed work did not produce progress=none"

    : > "$calls"
    (
        gc() {
            printf '%s\n' "$*" >> "$calls"
            case "$*" in
                "session list --state=all --json")
                    printf '%s\n' '{"sessions":[{"id":"s1","name":"demo/gastown.worker","template":"demo/gastown.polecat"},{"id":"s2","alias":"demo/gastown.worker","template":"demo/gastown.polecat"}]}'
                    ;;
                *)
                    return 1
                    ;;
            esac
        }
        target="demo/gastown.worker"
        # shellcheck source=/dev/null
        source "$probe"
    ) > "$output"

    rg -q '^progress_signal=unknown$' "$output" ||
        fail "ambiguous target-session lookup did not fail closed"
    if rg -q '^bd ' "$calls"; then
        fail "ambiguous target-session lookup queried an arbitrary bead store"
    fi
}

test_validator_rejects_provider_and_unrelated_paths() {
    local tmp validator rig provider bead valid got plain alias_root foreign foreign_wt
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' RETURN
    validator="$tmp/validator.sh"
    extract_validator "$validator"
    # shellcheck source=/dev/null
    source "$validator"

    rig="$tmp/rig"
    provider="$tmp/provider-home"
    bead="ac-safe1"
    valid="$provider/worktrees/$bead"
    init_repo "$rig"
    git -C "$rig" worktree add -qb provider "$provider" HEAD
    mkdir -p "$provider/worktrees"
    git -C "$rig" worktree add -qb "polecat/$bead" "$valid" HEAD

    if validate_artifact_worktree "$provider" "$rig" "$bead" >/dev/null; then
        fail "persistent provider home was accepted as a task artifact"
    fi

    alias_root="$tmp/provider-alias/worktrees"
    mkdir -p "$alias_root"
    ln -s "$provider" "$alias_root/$bead"
    if validate_artifact_worktree "$alias_root/$bead" "$rig" "$bead" >/dev/null; then
        fail "symlink resolving to provider home was accepted"
    fi

    plain="$provider/worktrees/ac-plain"
    mkdir -p "$plain"
    if validate_artifact_worktree "$plain" "$rig" ac-plain >/dev/null; then
        fail "plain nested directory was accepted as a Git worktree root"
    fi

    if validate_artifact_worktree "$valid" "$rig" ac-wrong >/dev/null; then
        fail "worktree for a different bead id was accepted"
    fi
    if validate_artifact_worktree "$tmp/missing" "$rig" "$bead" >/dev/null; then
        fail "missing artifact directory was accepted"
    fi

    foreign="$tmp/foreign"
    foreign_wt="$tmp/foreign-parent/worktrees/$bead"
    init_repo "$foreign"
    mkdir -p "$(dirname "$foreign_wt")"
    git -C "$foreign" worktree add -qb foreign-task "$foreign_wt" HEAD
    if validate_artifact_worktree "$foreign_wt" "$rig" "$bead" >/dev/null; then
        fail "same-shaped worktree from a foreign repository was accepted"
    fi

    got=$(validate_artifact_worktree "$valid" "$rig" "$bead") ||
        fail "valid per-bead legacy worktree was rejected"
    [[ "$got" == "$(cd "$valid" && pwd -P)" ]] ||
        fail "validator did not return the physical valid worktree path"
}

test_metadata_migration_and_consumers_are_canonical_first() {
    python3 - \
        "$POLECAT_FORMULA" \
        "$WITNESS_FORMULA" \
        "$SHUTDOWN_FORMULA" \
        "$REFINERY_FORMULA" \
        "$GASTOWN/agents/polecat/prompt.template.md" \
        "$GASTOWN/agents/witness/prompt.template.md" <<'PY'
import pathlib
import sys
import tomllib

(
    polecat_path,
    witness_path,
    shutdown_path,
    refinery_path,
    polecat_prompt_path,
    witness_prompt_path,
) = (
    pathlib.Path(arg) for arg in sys.argv[1:]
)

with polecat_path.open("rb") as handle:
    polecat = tomllib.load(handle)
workspace = next(step["description"] for step in polecat["steps"] if step["id"] == "workspace-setup")
submit = next(step["description"] for step in polecat["steps"] if step["id"] == "submit-and-exit")

required_workspace = (
    ".artifact_dir // empty",
    ".work_dir // empty",
    "validate_artifact_worktree",
    '--set-metadata artifact_dir="$WORKTREE"',
    "--unset-metadata work_dir",
    'cd -- "$WORKTREE"',
    'ARTIFACT_HOME="$CITY_ROOT/.gc/worktrees/$GC_RIG/artifacts"',
    'EXPECTED_BRANCH="polecat/$WORK_BEAD_ID"',
    'git merge-base --is-ancestor HEAD "origin/{{base_branch}}"',
    "Canonical artifact_dir is missing or unsafe",
)
for fragment in required_workspace:
    if fragment not in workspace:
        raise SystemExit(f"workspace contract missing: {fragment}")
if workspace.index(".artifact_dir // empty") > workspace.index(".work_dir // empty"):
    raise SystemExit("legacy task work_dir is read before canonical artifact_dir")
if workspace.index("validate_artifact_worktree") > workspace.index('cd -- "$WORKTREE"'):
    raise SystemExit("workspace enters the task path before defining/using its validator")
if "--set-metadata work_dir=" in workspace:
    raise SystemExit("workspace still writes deprecated task work_dir")
for forbidden in (
    'WORKTREE_PATH=$(pwd)/worktrees/',
    'WORKTREE_PATH="$PWD/worktrees/',
    'WORKTREE_PATH="${PWD}/worktrees/',
):
    if forbidden in workspace:
        raise SystemExit(f"workspace still creates provider-nested task artifacts: {forbidden}")
if "GC_WORK_DIR" in workspace:
    raise SystemExit("workspace relies on convergence-only GC_WORK_DIR")
if 'git branch -D "$EXPECTED_BRANCH"' in workspace or 'git branch -D "$BRANCH"' in workspace:
    raise SystemExit("empty-branch recovery can delete an unrecorded work branch")
if "--unset-metadata artifact_source_sha" not in submit:
    raise SystemExit("polecat submission does not retire stale refinery artifact proof")
canonical_guard = workspace.index("Canonical artifact_dir is missing or unsafe")
legacy_fallback = workspace.index('elif [ -n "$LEGACY_WORK_DIR" ]')
if canonical_guard > legacy_fallback:
    raise SystemExit("invalid canonical artifact_dir can fall through to legacy/new creation")

with witness_path.open("rb") as handle:
    witness = tomllib.load(handle)
recovery = next(step["description"] for step in witness["steps"] if step["id"] == "recover-orphaned-beads")
for fragment in (
    "metadata.artifact_dir",
    "validate_recovery_artifact_worktree",
    '--set-metadata artifact_dir="$WORKTREE"',
    "--unset-metadata work_dir",
    'git ls-remote --exit-code --heads origin "refs/heads/$BRANCH"',
    'merge-base --is-ancestor',
    'git -C "$GC_RIG_ROOT" worktree remove "$WORKTREE"',
    "confirm_orphan_still_unowned",
    "Canonical artifact metadata is present but invalid",
    'cd "$GC_RIG_ROOT"',
):
    if fragment not in recovery:
        raise SystemExit(f"witness recovery contract missing: {fragment}")
for forbidden in ("rm -rf <worktree-path>",):
    if forbidden in recovery:
        raise SystemExit(f"witness recovery retained unsafe legacy behavior: {forbidden}")
if 'if [ -n "$BRANCH" ]; then' not in recovery:
    raise SystemExit("witness recovery can run remote/merge checks with an empty branch")
if 'worktree remove "$WORKTREE" --force' in recovery:
    raise SystemExit("witness artifact cleanup force-removes a worktree")
if recovery.index("confirm_orphan_still_unowned") > recovery.index(
    "--set-metadata artifact_dir="
):
    raise SystemExit("witness migration mutates metadata before its fresh owner fence")
if recovery.index("confirm_orphan_still_unowned") > recovery.index(
    'checkout -b "$EXPECTED_BRANCH"'
):
    raise SystemExit("witness branch recovery runs before its fresh owner fence")

with shutdown_path.open("rb") as handle:
    shutdown = tomllib.load(handle)
execute = next(step["description"] for step in shutdown["steps"] if step["id"] == "execute")
if execute.index(".metadata.artifact_dir // empty") > execute.index(".metadata.work_dir // empty"):
    raise SystemExit("shutdown dance does not read canonical artifact_dir first")
if 'validate_progress_artifact_dir' not in execute:
    raise SystemExit("shutdown dance lacks the artifact path validator")
if 'find "$artifact_dir"' not in execute or 'find "$work_dir"' in execute:
    raise SystemExit("shutdown dance can scan an unvalidated legacy/provider work_dir")
for fragment in (
    'progress="unknown"',
    'gc bd --rig "$target_rig" list',
    'gc bd --rig "$target_rig" show',
    'if [ "$progress" = "unknown" ]; then',
):
    if fragment not in execute:
        raise SystemExit(f"shutdown fail-closed rig lookup contract missing: {fragment}")

with refinery_path.open("rb") as handle:
    refinery = tomllib.load(handle)
rebase = next(step["description"] for step in refinery["steps"] if step["id"] == "rebase")
merge = next(step["description"] for step in refinery["steps"] if step["id"] == "merge-push")
if '--set-metadata artifact_source_sha="$ARTIFACT_SOURCE_SHA"' not in rebase:
    raise SystemExit("refinery does not durably capture the pre-rebase artifact SHA")
for fragment in (
    "**Successful task-artifact cleanup (direct and mr):**",
    ".artifact_dir",
    'git -C "$GC_RIG_ROOT" worktree remove "$SAFE_ARTIFACT"',
    '--unset-metadata artifact_dir',
    '--unset-metadata work_dir',
    '[ -z "$(git -C "$ARTIFACT_REAL" status --porcelain)" ]',
    '.artifact_source_sha // empty',
    '[ "$LOCAL_SHA" = "$EXPECTED_ARTIFACT_SHA" ]',
):
    if fragment not in merge:
        raise SystemExit(f"refinery artifact cleanup contract missing: {fragment}")
if 'worktree remove --force "$SAFE_ARTIFACT"' in merge:
    raise SystemExit("refinery task-artifact cleanup force-removes a worktree")

polecat_prompt = polecat_prompt_path.read_text(encoding="utf-8")
witness_prompt = witness_prompt_path.read_text(encoding="utf-8")
if "`metadata.artifact_dir`" not in polecat_prompt:
    raise SystemExit("polecat prompt does not document canonical artifact_dir")
for fragment in (
    "$GC_CITY_PATH/.gc/worktrees/$GC_RIG/artifacts/worktrees/<bead-id>",
    'gc bd formula show mol-polecat-work --rig "$GC_RIG"',
    "Execute its `workspace-setup` step before reading or editing task source",
    "Do not search\nthe filesystem for formula files",
    "<provider-home>/worktrees/<bead-id>",
):
    if fragment not in polecat_prompt:
        raise SystemExit(f"polecat prompt lacks fail-closed workspace guidance: {fragment}")
if "<home>/worktrees/vg-1jp" in polecat_prompt:
    raise SystemExit("polecat prompt still advertises the legacy provider-nested path")
if "new nested worktree is created" in workspace:
    raise SystemExit("workspace recipe still describes canonical artifacts as nested worktrees")
if "`metadata.artifact_dir`" not in witness_prompt:
    raise SystemExit("witness prompt does not document canonical artifact_dir")
PY
}

test_validator_rejects_provider_and_unrelated_paths
test_workspace_creation_uses_canonical_sibling
test_worktree_setup_ignores_gc_without_mutating_tracked_or_global_ignores
test_shutdown_probe_scopes_rig_and_fails_closed
test_metadata_migration_and_consumers_are_canonical_first

echo "polecat artifact_dir tests passed"
