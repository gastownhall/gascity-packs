#!/usr/bin/env bash
#
# equip-on-task-pickup.sh — Claude Code SessionStart hook for the personas pack.
#
# This is the gas-town integration (README "How it works" §2 / "The pack"): when a
# polecat picks up its work, equip the best-fit principal-engineer persona so the agent
# performs the task at that level. For a gas-town worker, session start *is* task
# pickup — the polecat is spawned with work already on its hook — so SessionStart is
# the equip moment.
#
# What it does:
#   1. Resolve the agent's current in-progress work bead (by session name / id / alias).
#   2. Ask the personas engine to match + equip a persona from that bead's title +
#      description: `bin/personas equip --from-bead <id> --emit-context`. That also
#      materializes the persona into the shared warm cache (so the next agent reuses it).
#   3. Emit the engine's SessionStart payload (hookSpecificOutput.additionalContext) so
#      the persona's playbook + verification bar overlay this session.
#
# CONTRACT (Claude Code SessionStart):
#   - stdin : JSON describing the session start (we don't require any field from it;
#             the work bead is resolved from the gc launcher env).
#   - stdout: either nothing, or a single JSON object:
#               {"hookSpecificOutput":{"hookEventName":"SessionStart",
#                                      "additionalContext":"<persona context>"}}
#   - exit  : ALWAYS 0. Equip is strictly best-effort; it must never block or fail a
#             session start. Every step is guarded and falls through to `exit 0`.
#
# Escape hatch: PERSONAS_DISABLE_EQUIP=1 makes this hook a no-op without touching
# settings.json.
#
# Self-contained: locates the pack's bin/personas relative to its own path and shells
# out to `bd` + `jq` (both guarded). No pack Python is invoked unless a bead is found.

# Deliberately NOT using `set -e`/`set -u`/pipefail: every step is guarded and we must
# always reach `exit 0`, even on an unbound var or a broken pipe.

# ---- 0. Escape hatch -------------------------------------------------------
if [ "${PERSONAS_DISABLE_EQUIP:-}" = "1" ]; then
  exit 0
fi

# ---- 1. Drain stdin (we don't need a field from it, but must not leave it) --
_payload="$(cat 2>/dev/null)" || true
: "${_payload:=}"

# ---- 2. Locate the pack's CLI ----------------------------------------------
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || exit 0
PERSONAS_BIN="$PACK_DIR/bin/personas"
[ -x "$PERSONAS_BIN" ] || exit 0

# ---- 3. Resolve the current in-progress work bead --------------------------
# Prefer the runtime session name, then the session id, then the alias — the same
# identity precedence the polecat startup hook check uses. Needs `bd` + `jq`.
command -v bd >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

bead=""
for id in "${GC_SESSION_NAME:-}" "${GC_SESSION_ID:-}" "${GC_ALIAS:-}"; do
  [ -z "$id" ] && continue
  r="$(bd list --status in_progress --assignee="$id" --json --limit=1 2>/dev/null)" || continue
  bead="$(printf '%s' "$r" | jq -r '.[0].id // empty' 2>/dev/null)"
  [ -n "$bead" ] && break
done

# No assigned in-progress work -> nothing to equip. Stay silent, exit clean.
[ -n "$bead" ] || exit 0

# ---- 4. Equip + emit the SessionStart context payload ----------------------
# `equip --emit-context` prints the hook JSON on success and matches even a
# weakly-described bead (falling back to the default persona). Any failure (engine
# error, bd hiccup) prints nothing and we still exit 0 — never block the session.
"$PERSONAS_BIN" equip --from-bead "$bead" --emit-context 2>/dev/null || true

exit 0
