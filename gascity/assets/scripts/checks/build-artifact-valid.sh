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
# stderr. This gate never prompts.
#
# Three kinds of failure leave by three exit statuses, because the dispatcher
# treats them differently (formula-spec-v2 section 3.1):
#   1  - a verdict: the artifact is missing, unresolvable, or invalid. The
#        dispatcher records stderr in gc.attempt_log as repair context for the
#        next bounded producer attempt.
#   75 - infrastructure unreachable (EX_TEMPFAIL): gc/bd could not answer. No
#        verdict; this declares an infrastructure outcome, and Gas City
#        versions that support it re-run the check without spending an
#        attempt.
#   78 - this machine cannot run the check as configured (EX_CONFIG): gc or
#        python3 is missing or cannot start, the validator is not shipped
#        beside this check, or the validator's interpreter cannot import a
#        module it needs. No verdict and re-running cannot help; the
#        dispatcher holds the step open until an operator fixes the
#        environment. The dispatcher records about 256 bytes of the FIRST
#        stderr line as the hold reason, so each branch prints the fact an
#        operator needs first and detail after.

fail() {
  echo "build-artifact-check: $*" >&2
  exit 1
}

fail_infra() {
  echo "build-artifact-check: $* [infrastructure unreachable, exit 75]" >&2
  exit 75
}

fail_env() {
  echo "build-artifact-check: cannot run in this environment: $*" >&2
  exit 78
}

BEAD_ID="${GC_BEAD_ID:-}"
[ -n "$BEAD_ID" ] || fail_env "GC_BEAD_ID is required (the dispatcher sets it; a producer cannot)"
command -v gc >/dev/null 2>&1 || fail_env "gc is required on PATH"
command -v python3 >/dev/null 2>&1 || fail_env "python3 is required on PATH"
# A python3 that resolves but cannot start (a version-manager shim without its
# configuration under this HOME, a broken install) would otherwise fail inside
# the first metadata lookup below with only its own stderr, which the
# dispatcher would grade as a verdict.
PY_ERR="$(python3 -c 'import json, sys' 2>&1)" \
  || fail_env "python3 ($(command -v python3)) cannot start: $(printf '%s' "$PY_ERR" | tr '\n' ' ' | head -c 200)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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
print(value if isinstance(value, str) else "")
' "$2"
}

GC_ERR="$(mktemp)"
# EXIT alone does not fire on an untrapped signal, and check gates run under a
# documented 10m dispatcher budget -- timeout kills are an expected path, not a
# hypothetical one, so each would leak this capture file. SIGKILL leaks either way.
trap 'rm -f "$GC_ERR"' EXIT INT TERM HUP
SHOW_JSON="$(gc bd show "$BEAD_ID" --json 2>"$GC_ERR")" \
  || fail_infra "gc bd show $BEAD_ID failed: $(tail -c 400 "$GC_ERR" | tr '\n' ' ')"

SCHEMA="$(metadata_value "$SHOW_JSON" "gc.build.artifact_schema")"
PATH_KEYS="$(metadata_value "$SHOW_JSON" "gc.build.artifact_path_keys")"
[ -n "$SCHEMA" ] || fail "step metadata gc.build.artifact_schema is missing on $BEAD_ID"
[ -n "$PATH_KEYS" ] || fail "step metadata gc.build.artifact_path_keys is missing on $BEAD_ID"

ROOT_ID="$(metadata_value "$SHOW_JSON" "gc.root_bead_id")"
ROOT_JSON="$SHOW_JSON"
if [ -n "$ROOT_ID" ] && [ "$ROOT_ID" != "$BEAD_ID" ]; then
  ROOT_JSON="$(gc bd show "$ROOT_ID" --json 2>"$GC_ERR")" \
    || fail_infra "gc bd show $ROOT_ID failed: $(tail -c 400 "$GC_ERR" | tr '\n' ' ')"
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

case "$ARTIFACT_PATH" in
  /*) ;;
  *)
    # Formula artifact paths are rig-relative. A producer runs in a disposable
    # per-bead worktree, so GC_WORK_DIR points at the wrong place whenever the
    # runtime provides the durable rig root. Agent sessions use GC_RIG_ROOT and
    # controller checks use GC_BEADS_SCOPE_ROOT on some runtimes. A check
    # executed from an installed <rig>/.gc/scripts/checks copy (the legacy
    # launcher-relative formula path some derived packs still use) can derive
    # the rig root from its own location; a pack-asset or source-tree copy
    # cannot, so that fallback is limited to the installed layout.
    ARTIFACT_ROOT="${GC_RIG_ROOT:-${GC_BEADS_SCOPE_ROOT:-${GC_DIR:-}}}"
    if [ -z "$ARTIFACT_ROOT" ]; then
      case "$SCRIPT_DIR" in
        */.gc/scripts/checks)
          ARTIFACT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
          ;;
      esac
    fi
    if [ -n "$ARTIFACT_ROOT" ]; then
      ARTIFACT_PATH="$ARTIFACT_ROOT/$ARTIFACT_PATH"
    else
      # Controller-run gates resolved from pack assets (the gascity formulas'
      # ../assets/scripts/checks paths) get none of the signals above. The
      # dispatcher always exports GC_STORE_PATH, the durable store root (the
      # rig root for rig-scoped workflows), and may export GC_WORK_DIR, the
      # inherited gc.work_dir. Prefer the store root; use the work dir only
      # when the artifact is not under the store root.
      RELATIVE_PATH="$ARTIFACT_PATH"
      ARTIFACT_PATH=""
      TRIED=""
      for root in "${GC_STORE_PATH:-}" "${GC_WORK_DIR:-}"; do
        [ -n "$root" ] || continue
        TRIED="${TRIED:+$TRIED, }$root/$RELATIVE_PATH"
        if [ -f "$root/$RELATIVE_PATH" ]; then
          ARTIFACT_PATH="$root/$RELATIVE_PATH"
          break
        fi
      done
      [ -n "$TRIED" ] || fail "artifact path $RELATIVE_PATH from $RESOLVED_KEY is relative and no rig-root environment is set"
      [ -n "$ARTIFACT_PATH" ] || fail "artifact $RELATIVE_PATH from $RESOLVED_KEY does not exist; tried $TRIED"
    fi
    ;;
esac
[ -f "$ARTIFACT_PATH" ] || fail "artifact $ARTIFACT_PATH from $RESOLVED_KEY does not exist"

# Prefer the validator shipped beside this check when the pack's schemas sit
# beside it too (pack-asset layout: <pack>/assets/scripts/checks next to
# <pack>/schemas/build), so the gate validates against the schemas of the same
# pack layer that defined the formula rather than whatever checkout GC_WORK_DIR
# happens to be. An installed <rig>/.gc/scripts copy has no schemas beside it,
# so it keeps the historical GC_WORK_DIR source-tree lookup first.
PACK_VALIDATOR=""
if [ -d "$SCRIPT_DIR/../../../schemas/build" ]; then
  PACK_VALIDATOR="$SCRIPT_DIR/../validate_build_artifact.py"
fi
VALIDATOR=""
for candidate in \
  ${PACK_VALIDATOR:+"$PACK_VALIDATOR"} \
  ${GC_WORK_DIR:+"$GC_WORK_DIR/gascity/assets/scripts/validate_build_artifact.py"} \
  "$SCRIPT_DIR/../validate_build_artifact.py"; do
  if [ -n "$candidate" ] && [ -f "$candidate" ]; then
    VALIDATOR="$candidate"
    break
  fi
done
[ -n "$VALIDATOR" ] || fail_env "validate_build_artifact.py not found beside $SCRIPT_DIR or under GC_WORK_DIR (pack layout problem)"

RC=0
OUTPUT="$(python3 "$VALIDATOR" --schema "$SCHEMA" --path "$ARTIFACT_PATH" 2>&1)" || RC=$?
case "$RC" in
  0)
    echo "build artifact valid: schema=$SCHEMA path=$ARTIFACT_PATH"
    exit 0
    ;;
  78)
    # The validator never looked at the artifact: its interpreter cannot
    # import something it needs. Propagate the environment status so the
    # dispatcher holds the step rather than asking the producer to repair
    # content that may be fine. The validator's own first line names the
    # interpreter, HOME and PYTHONUSERBASE it saw, so it goes out first and
    # becomes the hold reason; the wrapper's detail follows.
    printf '%s\n' "$OUTPUT" >&2
    echo "build-artifact-check: cannot run in this environment: validator=$VALIDATOR launcher=$(command -v python3)" >&2
    exit 78
    ;;
esac

echo "build-artifact-check: schema=$SCHEMA path=$ARTIFACT_PATH failed validation" >&2
printf '%s\n' "$OUTPUT" >&2
exit 1
