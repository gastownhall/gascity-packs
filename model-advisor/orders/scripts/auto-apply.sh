#!/usr/bin/env bash
# auto-apply.sh — exec-order entrypoint for model-advisor's scheduled auto-apply.
#
# Invoked by orders/model-advisor-auto-apply.toml (an EXEC order: no LLM, no
# agent, no wisp). It drives the pack's own CLI:
#
#     bin/advisor auto-apply [--apply] [--rig <rig>] --city <city> --json
#
# which sweeps every configured agent and sets each one's `model` config field to
# its conservative per-agent tier (the safest tier across the agent's shapes),
# but ONLY for evidence-strong changes — never auto-downgrading on thin evidence
# and never touching Critical-pinned agents. See docs/AUTO-APPLY.md for the full
# policy.
#
# SAFE BY DEFAULT: runs in DRY-RUN unless MODEL_ADVISOR_AUTO_APPLY is set to a
# truthy value (1/true/yes). A dry run computes + prints the plan but writes
# nothing — so the order can be imported and observed before it is armed.
#
# Optional environment knobs (all have safe defaults):
#   MODEL_ADVISOR_AUTO_APPLY   1|true|yes  -> actually write (else dry-run)
#   MODEL_ADVISOR_RIG          <rig name>  -> narrow scope to one rig
#   ADVISOR_TOML               <path>      -> advisor.toml (else pack default)
#   ADVISOR_TELEMETRY_DIR      <path>      -> telemetry dir (else <city>/.beads/telemetry)
#
# The controller exports GC_PACK_DIR / GC_CITY (and GC_CITY_PATH / GC_RIG) into
# an exec order's environment; we fall back sensibly when run by hand.
set -euo pipefail

# --- resolve the pack directory (prefer the controller-provided GC_PACK_DIR) ---
PACK_DIR="${GC_PACK_DIR:-}"
if [ -z "$PACK_DIR" ]; then
    # orders/scripts/auto-apply.sh -> pack root is two levels up.
    PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

# --- resolve the city root -----------------------------------------------------
CITY="${GC_CITY:-${GC_CITY_PATH:-.}}"

# --- telemetry: default to the city's .beads/telemetry if not overridden -------
# (build_state also defaults this, but being explicit keeps the log auditable.)
if [ -z "${ADVISOR_TELEMETRY_DIR:-}" ] && [ -d "$CITY/.beads/telemetry" ]; then
    export ADVISOR_TELEMETRY_DIR="$CITY/.beads/telemetry"
fi

# --- assemble the auto-apply invocation ----------------------------------------
ADVISOR="$PACK_DIR/bin/advisor"
if [ ! -x "$ADVISOR" ]; then
    echo "auto-apply.sh: $ADVISOR not found/executable (pack dir wrong?)" >&2
    exit 2
fi

args=("auto-apply" "--city" "$CITY" "--json")

# scope: town (default) or a single rig.
RIG="${MODEL_ADVISOR_RIG:-${GC_RIG:-}}"
if [ -n "$RIG" ]; then
    args+=("--rig" "$RIG")
fi

# arm only when explicitly opted in.
case "${MODEL_ADVISOR_AUTO_APPLY:-}" in
    1|true|TRUE|yes|YES|on|ON)
        args+=("--apply")
        echo "auto-apply.sh: ARMED (writing config changes)" >&2
        ;;
    *)
        echo "auto-apply.sh: DRY-RUN (set MODEL_ADVISOR_AUTO_APPLY=1 to arm)" >&2
        ;;
esac

# Run it. The CLI emits a structured JSON report on stdout (captured by the
# order's run log) and a human note on stderr; exit code is non-zero only if a
# per-agent error occurred, which surfaces in `gc order history`.
exec "$ADVISOR" "${args[@]}"
