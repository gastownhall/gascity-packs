#!/usr/bin/env bash
#
# capture-invocation.sh — Claude Code Stop / SubagentStop hook for the
# model-advisor pack.
#
# Implements the *write side* of the advisor telemetry contract (DESIGN.md §5):
# at the end of a session/subagent turn it appends a `kind="dispatch"`
# invocation record to the project's
#     <project>/.beads/telemetry/invocations.jsonl
# so the advisor engine (sibling, modeladvisor/store.py + engine.py) can later
# reconstruct the cell `provider::agent::shape::tier_id` and join a quality
# outcome to it (INTEGRATION-FEASIBILITY.md verdict (B): a Stop hook is the
# pack-owned seam that supplies model + tokens, which gc-core's session events
# do not carry).
#
# CONTRACT (Claude Code Stop / SubagentStop):
#   - stdin : JSON describing the stop event. Fields we read when present:
#               { "hook_event_name": "Stop" | "SubagentStop",
#                 "session_id":     "<id>",
#                 "transcript_path":"/abs/path/to/transcript.jsonl",
#                 "cwd":            "/abs/working/dir",
#                 "stop_hook_active": true|false }
#             Most of the advisor's cell fields are NOT in the stop payload —
#             they come from the gc launcher env (GC_TEMPLATE / GC_AGENT_MODEL /
#             GC_PROVIDER / GC_RIG_ROOT, see INTEGRATION (A)/(B)). We read what
#             is present and mark the rest "unknown"; the engine degrades on
#             missing fields rather than failing.
#   - stdout: NONE. A Stop hook must not inject context; we only append a
#             telemetry line. (Emitting JSON here is harmless but unnecessary;
#             we stay silent so we can never interfere with the stop path.)
#   - exit  : ALWAYS 0. Capture is strictly best-effort; it must never block a
#             stop or fail a session. Every step below is guarded and falls
#             through to the final `exit 0`.
#
# Degradation (INTEGRATION (B)): gc session.stopped events carry no model and
# no tokens. So:
#   * agent           <- $GC_TEMPLATE (base name derived), else "unknown"
#   * model           <- $GC_AGENT_MODEL, else parsed from the transcript's last
#                        assistant message, else "unknown"
#   * provider        <- $GC_PROVIDER, else "unknown"
#   * tok_in/tok_out  <- summed from transcript usage if present, else omitted
#   * tier_id/shape   <- "unknown" at capture time; the engine resolves the
#                        canonical shape and roster tier from the roster/shapes
#                        config + this record's model/agent (DESIGN.md §2.2/§2.3).
# A record with unknowns is still a valid join anchor: bead_id / session_id are
# the keys the quality harvester (ingest.py) joins on.
#
# Escape hatch: MODEL_ADVISOR_DISABLE_CAPTURE=1 makes this hook a no-op without
# touching settings.json.
#
# Self-contained: shells out only to `jq` (robust JSON) with a grep/sed/python3
# fallback, and `date`. No pack Python is invoked on the hot path.

# Deliberately NOT using `set -e`/`set -u`/pipefail: every step is guarded and
# we must always reach `exit 0`, even on an unbound var or a broken pipe.

# ---- 0. Global escape hatch ------------------------------------------------
if [ "${MODEL_ADVISOR_DISABLE_CAPTURE:-}" = "1" ]; then
  exit 0
fi

SCHEMA_VERSION="advisor.v1"

# ---- 1. Read the Stop payload from stdin -----------------------------------
payload="$(cat 2>/dev/null)" || exit 0
# An empty/malformed payload is fine: we proceed with env-only fields. We never
# abort on a bad payload — the contract is "always emit something or nothing,
# always exit 0".

# ---- 2. Extract fields from the payload (jq, else grep/sed) ----------------
hook_event=""
session_id=""
transcript_path=""
cwd_in=""
have_jq=0
if command -v jq >/dev/null 2>&1; then
  have_jq=1
  hook_event="$(printf '%s' "$payload"      | jq -r '.hook_event_name // empty' 2>/dev/null)"
  session_id="$(printf '%s' "$payload"      | jq -r '.session_id // empty'      2>/dev/null)"
  transcript_path="$(printf '%s' "$payload" | jq -r '.transcript_path // empty' 2>/dev/null)"
  cwd_in="$(printf '%s' "$payload"          | jq -r '.cwd // empty'             2>/dev/null)"
else
  # Minimal fallback: pull first "key": "value" string for each field.
  _pull() { printf '%s' "$payload" | grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -n1 | sed 's/.*:[[:space:]]*"\([^"]*\)".*/\1/'; }
  hook_event="$(_pull hook_event_name)"
  session_id="$(_pull session_id)"
  transcript_path="$(_pull transcript_path)"
  cwd_in="$(_pull cwd)"
fi
[ -n "$hook_event" ] || hook_event="Stop"

# ---- 3. Resolve agent identity + model + provider from gc env --------------
# gc's launcher sets these at spawn (INTEGRATION (A)/(B)); they are the only
# reliable source of agent/model/provider on a Stop hook.
agent_instance="${GC_TEMPLATE:-}"           # e.g. "whiskeyshop/gastown.polecat"
model="${GC_AGENT_MODEL:-}"
provider="${GC_PROVIDER:-}"
rig_root="${GC_RIG_ROOT:-}"

# Base agent name = last dotted component of the template, rig/path stripped
# (DESIGN.md §2.4: cells key on the base role, not the instance). Examples:
#   "whiskeyshop/gastown.polecat#3" -> "polecat"
#   "gastown.deacon"                -> "deacon"
#   "polecat"                       -> "polecat"
agent="unknown"
if [ -n "$agent_instance" ]; then
  agent="$agent_instance"
  agent="${agent##*/}"   # drop "rig/" prefix
  agent="${agent##*.}"   # drop "namespace." prefix
  agent="${agent%%#*}"   # drop "#instance" suffix
  [ -n "$agent" ] || agent="unknown"
fi

# rig name = first path component of the instance (audit / future per-rig key).
rig=""
case "$agent_instance" in
  */*) rig="${agent_instance%%/*}" ;;
esac

# ---- 4. Best-effort: model + token usage from the transcript ---------------
# The Claude Code transcript is JSONL of message events; assistant messages
# carry `message.model` and `message.usage.{input_tokens,output_tokens,
# cache_*}`. We take the LAST assistant model and SUM usage across the
# transcript. Purely best-effort: any miss leaves the value unset/0.
tok_in=""
tok_out=""
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ] && [ "$have_jq" = "1" ]; then
  # Model: last non-null message.model (only override if env didn't supply one).
  if [ -z "$model" ]; then
    tmodel="$(jq -rs '[.[] | .message?.model // empty] | last // empty' "$transcript_path" 2>/dev/null)"
    [ -n "$tmodel" ] && model="$tmodel"
  fi
  # Tokens: sum input/output usage across all assistant messages. cache_read and
  # cache_creation count as input for cost purposes (DESIGN.md §2.3 cost fn uses
  # in/out token totals; the engine may refine).
  tok_in="$(jq -rs '[.[] | .message?.usage? | ((.input_tokens // 0) + (.cache_read_input_tokens // 0) + (.cache_creation_input_tokens // 0))] | add // 0' "$transcript_path" 2>/dev/null)"
  tok_out="$(jq -rs '[.[] | .message?.usage?.output_tokens // 0] | add // 0' "$transcript_path" 2>/dev/null)"
  # Guard against jq printing "null"/"" — treat as absent.
  case "$tok_in"  in ''|null) tok_in="" ;; esac
  case "$tok_out" in ''|null) tok_out="" ;; esac
fi

# Fill unknown sentinels for required string fields.
[ -n "$model" ]    || model="unknown"
[ -n "$provider" ] || provider="unknown"

# ---- 5. Locate the project root (walk up for .beads) -----------------------
# Same discovery the read-side pack uses. Start from cwd in the payload, then
# the gc rig root, then the process cwd. Walk up to 12 levels for a `.beads`.
start_dir=""
for cand in "$cwd_in" "$rig_root" "$PWD"; do
  if [ -n "$cand" ] && [ -d "$cand" ]; then start_dir="$cand"; break; fi
done
[ -n "$start_dir" ] || start_dir="$PWD"

proj_root=""
d="$start_dir"
i=0
while [ -n "$d" ] && [ "$i" -lt 12 ]; do
  if [ -d "$d/.beads" ]; then proj_root="$d"; break; fi
  nd="$(dirname "$d")"
  [ "$nd" = "$d" ] && break
  d="$nd"
  i=$((i + 1))
done
# No .beads anywhere up the tree: nothing to anchor telemetry to — exit clean.
[ -n "$proj_root" ] || exit 0

tel_dir="$proj_root/.beads/telemetry"
mkdir -p "$tel_dir" 2>/dev/null || exit 0
out_file="$tel_dir/invocations.jsonl"

# ---- 6. Timestamp ----------------------------------------------------------
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
[ -n "$ts" ] || ts="1970-01-01T00:00:00Z"

# ---- 7. Build + append the kind="dispatch" record --------------------------
# Cell key per DESIGN.md §2.4: provider::agent::shape::tier_id. At capture time
# shape and tier_id are unknown (resolved by the engine from config); we emit
# "unknown" placeholders so the key is well-formed and the engine can backfill.
shape="unknown"
tier_id="unknown"
cell_key="${provider}::${agent}::${shape}::${tier_id}"

# bead_id: the Stop payload has no bead id (gc binds work to a session, not a
# bead, at this layer). We leave it empty and let the engine/harvester join via
# session_id (DESIGN.md §5.1 "join key"; INTEGRATION (C): bead.metadata.session_id
# joins a closed bead to this dispatch). session_id is the load-bearing key here.

if [ "$have_jq" = "1" ]; then
  # jq builds the object with correct escaping. Numbers are emitted only when
  # present; absent token counts are omitted (the engine falls back to a
  # representative budget per DESIGN.md §5.4).
  jq -cn \
    --arg sv   "$SCHEMA_VERSION" \
    --arg ts   "$ts" \
    --arg sid  "$session_id" \
    --arg prov "$provider" \
    --arg ag   "$agent" \
    --arg agi  "$agent_instance" \
    --arg rig  "$rig" \
    --arg shp  "$shape" \
    --arg tid  "$tier_id" \
    --arg mdl  "$model" \
    --arg ck   "$cell_key" \
    --arg ev   "$hook_event" \
    --arg ti   "$tok_in" \
    --arg to   "$tok_out" \
    '{
       schema_version: $sv,
       kind:           "dispatch",
       ts:             $ts,
       bead_id:        "",
       session_id:     $sid,
       provider:       $prov,
       agent:          $ag,
       agent_instance: $agi,
       rig:            $rig,
       shape:          $shp,
       tier_id:        $tid,
       model:          $mdl,
       q_tol_class:    "unknown",
       baseline_tier:  "unknown",
       advised_tier:   "unknown",
       forced_baseline:false,
       cell_key:       $ck,
       source:         ("hook:" + $ev)
     }
     | (if ($ti|length) > 0 then . + {tok_in:  ($ti|tonumber)} else . end)
     | (if ($to|length) > 0 then . + {tok_out: ($to|tonumber)} else . end)' \
    >> "$out_file" 2>/dev/null || true
elif command -v python3 >/dev/null 2>&1; then
  # python3 fallback: same record, JSON-safe.
  SV="$SCHEMA_VERSION" TS="$ts" SID="$session_id" PROV="$provider" AG="$agent" \
  AGI="$agent_instance" RIG="$rig" SHP="$shape" TID="$tier_id" MDL="$model" \
  CK="$cell_key" EV="$hook_event" TI="$tok_in" TO="$tok_out" OUT="$out_file" \
  python3 - <<'PY' 2>/dev/null || true
import json, os
rec = {
    "schema_version": os.environ.get("SV", "advisor.v1"),
    "kind": "dispatch",
    "ts": os.environ.get("TS", ""),
    "bead_id": "",
    "session_id": os.environ.get("SID", ""),
    "provider": os.environ.get("PROV", "unknown"),
    "agent": os.environ.get("AG", "unknown"),
    "agent_instance": os.environ.get("AGI", ""),
    "rig": os.environ.get("RIG", ""),
    "shape": os.environ.get("SHP", "unknown"),
    "tier_id": os.environ.get("TID", "unknown"),
    "model": os.environ.get("MDL", "unknown"),
    "q_tol_class": "unknown",
    "baseline_tier": "unknown",
    "advised_tier": "unknown",
    "forced_baseline": False,
    "cell_key": os.environ.get("CK", ""),
    "source": "hook:" + os.environ.get("EV", "Stop"),
}
for env_k, rec_k in (("TI", "tok_in"), ("TO", "tok_out")):
    v = os.environ.get(env_k, "")
    if v not in ("", "null"):
        try:
            rec[rec_k] = int(v)
        except ValueError:
            pass
try:
    with open(os.environ["OUT"], "a") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")
except Exception:
    pass
PY
fi
# If neither jq nor python3 is available we simply emit nothing — never a
# half-written/garbled line.

# A capture failure must never break a stop.
exit 0
