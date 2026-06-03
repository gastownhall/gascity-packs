#!/usr/bin/env bash
#
# outline-on-read.sh — Claude Code PreToolUse hook for the ast-lens pack.
#
# Implements "Subsystem B: Outline-discipline" (paper §4) for the *claude*
# provider: when an agent issues a `Read` on a large source file, this hook
# runs the canonical outline emitter (`bin/outline`) and feeds the resulting
# Markdown back to the agent as additional context, so the agent sees the
# file's structure before (and alongside) the raw bytes.
#
# CONTRACT (Claude Code PreToolUse):
#   - stdin  : JSON describing the pending tool call, e.g.
#                { "hook_event_name": "PreToolUse",
#                  "tool_name": "Read",
#                  "tool_input": { "file_path": "/abs/path/to/file.py", ... } }
#   - stdout : JSON. We emit the "advisory / inject context" shape:
#                { "hookSpecificOutput": {
#                    "hookEventName": "PreToolUse",
#                    "additionalContext": "<outline markdown>" } }
#              Claude Code injects `additionalContext` into the model's context
#              for this turn. We DO NOT set permissionDecision, so the Read is
#              never blocked or modified — this is warn-mode (rich warning),
#              exactly as the paper specifies ("The hook never blocks the Read").
#   - exit   : ALWAYS 0. A non-zero exit (or stderr "block" payload) could
#              interfere with the Read; this hook must be pure passthrough on
#              every error path.
#
# Design notes
#   * The emitter is itself the gate (Alg 1): it stays silent / exits 0 for
#     files < threshold LoC (default 200, theta_L), unsupported types, files
#     carrying `// outline:skip` / `# outline:skip` in their first lines, or any
#     parse/runtime failure. So this hook does NOT re-implement the threshold —
#     it simply asks the emitter and only injects when the emitter has something
#     to say. One emitter, one schema (paper §4 "one emitter, three surfaces").
#   * All sanitisation of file contents into the outline is already handled
#     inside the emitter (outline.py `sanitise()`), so nothing untrusted from
#     the source file is echoed raw here.
#   * Escape hatch: set BLACKRIM_DISABLE_OUTLINE_HOOK=1 (paper §4) to make this
#     hook a no-op without touching settings.
#   * Telemetry (paper §4): one JSON line per fired event is appended to
#     .beads/telemetry/outline-events.jsonl when a project root is discoverable.
#     Telemetry is strictly best-effort and never affects the exit path.
#
# This script is intentionally self-contained: it shells out only to `jq`
# (for robust stdin parsing) and the pack's own `bin/outline`. If `jq` is
# missing it falls back to a minimal grep/sed extraction so the hook still
# degrades gracefully rather than failing.

# NOTE: deliberately NOT using `set -e` — every step below is guarded, and we
# must reach the final `exit 0` no matter what. `set -u`/pipefail are likewise
# avoided so an unbound var or broken pipe can never abort mid-hook.

# ---- 0. Global escape hatch ------------------------------------------------
if [ "${BLACKRIM_DISABLE_OUTLINE_HOOK:-}" = "1" ]; then
  exit 0
fi

# ---- 1. Locate the pack + emitter ------------------------------------------
# This file lives at <pack>/hooks/outline-on-read.sh, so the pack root is one
# level up. Resolve it robustly even when invoked via an absolute path.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || exit 0
PACK_DIR="$(cd "$HOOK_DIR/.." 2>/dev/null && pwd)" || exit 0
OUTLINE_BIN="$PACK_DIR/bin/outline"
[ -x "$OUTLINE_BIN" ] || exit 0

# ---- 2. Read the PreToolUse payload from stdin -----------------------------
payload="$(cat 2>/dev/null)" || exit 0
[ -n "$payload" ] || exit 0

# ---- 3. Extract tool_name and file_path ------------------------------------
tool_name=""
file_path=""
if command -v jq >/dev/null 2>&1; then
  # `// empty` keeps the vars empty (not the string "null") on absence.
  tool_name="$(printf '%s' "$payload"  | jq -r '.tool_name // empty'             2>/dev/null)"
  file_path="$(printf '%s' "$payload"  | jq -r '.tool_input.file_path // empty'  2>/dev/null)"
else
  # Minimal fallback parser: pull the first "file_path": "<...>" string.
  tool_name="$(printf '%s' "$payload" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed 's/.*:[[:space:]]*"\([^"]*\)".*/\1/')"
  file_path="$(printf '%s' "$payload" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed 's/.*:[[:space:]]*"\([^"]*\)".*/\1/')"
fi

# Only act on Read (the discipline targets Read specifically). If some future
# matcher routes other tools here, just pass through.
[ "$tool_name" = "Read" ] || exit 0
[ -n "$file_path" ] || exit 0
[ -f "$file_path" ] || exit 0

# ---- 4. Run the emitter ----------------------------------------------------
# The emitter decides (Alg 1) whether this file warrants an outline; it prints
# Markdown to stdout and is silent otherwise. Errors -> empty -> passthrough.
outline_md="$("$OUTLINE_BIN" "$file_path" 2>/dev/null)" || outline_md=""

# Nothing to inject (sub-threshold / unsupported / skip / parse miss): be quiet.
[ -n "$outline_md" ] || exit 0

# ---- 5. Best-effort telemetry (never fatal) --------------------------------
# Append one event line to .beads/telemetry/outline-events.jsonl, walking up
# from the read file to find a project root that already has a .beads dir.
{
  tel_root=""
  d="$(dirname "$file_path")"
  for _ in 1 2 3 4 5 6 7 8; do
    [ -d "$d/.beads" ] && { tel_root="$d"; break; }
    nd="$(dirname "$d")"; [ "$nd" = "$d" ] && break; d="$nd"
  done
  if [ -n "$tel_root" ]; then
    tel_dir="$tel_root/.beads/telemetry"
    mkdir -p "$tel_dir" 2>/dev/null
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    bytes="$(printf '%s' "$outline_md" | wc -c | tr -d ' ')"
    # Build the JSON line with jq when available (proper escaping); else skip.
    if command -v jq >/dev/null 2>&1; then
      printf '%s' "$file_path" \
        | jq -R -c --arg ts "$ts" --arg b "$bytes" \
            '{event:"outline_injected", surface:"PreToolUse", provider:"claude", ts:$ts, file:., outline_bytes:($b|tonumber)}' \
            >> "$tel_dir/outline-events.jsonl" 2>/dev/null || true
    fi
  fi
} 2>/dev/null || true

# ---- 6. Emit additionalContext JSON to stdout ------------------------------
# Prefer jq for correct JSON string escaping of the Markdown body. The fallback
# python3 path covers boxes without jq; if both are missing we pass through
# (printing raw Markdown is NOT safe — Claude Code expects JSON on stdout here).
context_body="$(printf 'Structural outline for %s (outline-first reading, ast-lens). Use it to navigate before reading the full file.\n\n%s' "$file_path" "$outline_md")"

if command -v jq >/dev/null 2>&1; then
  printf '%s' "$context_body" | jq -R -s \
    '{hookSpecificOutput:{hookEventName:"PreToolUse", additionalContext:.}}' \
    2>/dev/null || exit 0
elif command -v python3 >/dev/null 2>&1; then
  CTX="$context_body" python3 - <<'PY' 2>/dev/null || exit 0
import json, os
ctx = os.environ.get("CTX", "")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "additionalContext": ctx}}))
PY
fi

# Always succeed: a hook failure must never break a Read.
exit 0
