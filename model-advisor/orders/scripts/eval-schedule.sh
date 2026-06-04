#!/usr/bin/env bash
# eval-schedule.sh — exec-order entrypoint for model-advisor's Layer-4 auto-eval.
#
# Invoked by orders/model-advisor-eval-schedule.toml (an EXEC order: no LLM, no
# agent, no wisp). It drives the pack's own CLI:
#
#     bin/advisor eval-schedule [--max N] [--apply] --city <city> --json
#
# which sweeps every configured (agent, shape) cell, ranks the cells that are
# GATING a downgrade on uncertainty by `posterior CI half-width × unlock-value`
# (the spend confirming the downgrade would save), and emits an eval-request bead
# for the top N — auto-dispatch proportional to posterior width (DESIGN §5.4).
# This closes the loop that v1 only *surfaced* in `advisor inspect`.
#
# SAFE BY DEFAULT: runs in DRY-RUN unless MODEL_ADVISOR_EVAL_SCHEDULE is set to a
# truthy value (1/true/yes). A dry run computes + prints the ranked eval plan
# (the `gc bd create` commands it WOULD run) but creates no beads — so the order
# can be imported and observed before it is armed.
#
# Optional environment knobs (all have safe defaults):
#   MODEL_ADVISOR_EVAL_SCHEDULE  1|true|yes  -> actually create eval beads (else dry-run)
#   MODEL_ADVISOR_EVAL_MAX       <int>       -> cap on eval beads per run (default 5)
#   MODEL_ADVISOR_RIG            <rig name>  -> create eval beads in this rig's db
#   ADVISOR_TOML                 <path>      -> advisor.toml (else pack default)
#   ADVISOR_TELEMETRY_DIR        <path>      -> telemetry dir (else <city>/.beads/telemetry)
#
# The controller exports GC_PACK_DIR / GC_CITY (and GC_CITY_PATH / GC_RIG) into
# an exec order's environment; we fall back sensibly when run by hand.
set -euo pipefail

# --- resolve the pack directory (prefer the controller-provided GC_PACK_DIR) ---
PACK_DIR="${GC_PACK_DIR:-}"
if [ -z "$PACK_DIR" ]; then
    # orders/scripts/eval-schedule.sh -> pack root is two levels up.
    PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

# --- resolve the city root -----------------------------------------------------
CITY="${GC_CITY:-${GC_CITY_PATH:-.}}"

# --- telemetry: default to the city's .beads/telemetry if not overridden -------
# (build_state also defaults this, but being explicit keeps the log auditable.)
if [ -z "${ADVISOR_TELEMETRY_DIR:-}" ] && [ -d "$CITY/.beads/telemetry" ]; then
    export ADVISOR_TELEMETRY_DIR="$CITY/.beads/telemetry"
fi

# --- assemble the eval-schedule invocation -------------------------------------
ADVISOR="$PACK_DIR/bin/advisor"
if [ ! -x "$ADVISOR" ]; then
    echo "eval-schedule.sh: $ADVISOR not found/executable (pack dir wrong?)" >&2
    exit 2
fi

args=("eval-schedule" "--city" "$CITY" "--json")

# eval budget: how many eval beads to schedule this run.
MAXN="${MODEL_ADVISOR_EVAL_MAX:-}"
if [ -n "$MAXN" ]; then
    args+=("--max" "$MAXN")
fi

# scope: create the eval beads in a specific rig's database, if requested.
RIG="${MODEL_ADVISOR_RIG:-${GC_RIG:-}}"
if [ -n "$RIG" ]; then
    args+=("--rig" "$RIG")
fi

# arm only when explicitly opted in.
case "${MODEL_ADVISOR_EVAL_SCHEDULE:-}" in
    1|true|TRUE|yes|YES|on|ON)
        args+=("--apply")
        echo "eval-schedule.sh: ARMED (creating eval-request beads)" >&2
        ;;
    *)
        echo "eval-schedule.sh: DRY-RUN (set MODEL_ADVISOR_EVAL_SCHEDULE=1 to arm)" >&2
        ;;
esac

# Run it. The CLI emits a structured JSON report on stdout (captured by the
# order's run log) and a human note on stderr; exit code is non-zero only if a
# scheduling/creation error occurred, which surfaces in `gc order history`.
exec "$ADVISOR" "${args[@]}"
