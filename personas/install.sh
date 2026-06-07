#!/usr/bin/env bash
# personas — install lifecycle (reversible, idempotent).
#
#   install.sh (--town | --rig <name>) [--dry-run] [--city <path>] [--no-reload]
#
# Turns the personas pack ON at one of two scopes:
#   --town        city-wide: every agent gets the equip-persona skill + (opt-in) the
#                 use-personas discipline fragment + the claude SessionStart
#                 equip-on-task-pickup hook (equips a persona as a session picks up work).
#   --rig <name>  one rig only: that rig's agents get the skill + the equip hook.
#
# What it does (in order):
#   1. Build the engine venv via setup.sh (skipped if .venv already present; optional —
#      bin/personas also runs under any system python3).
#   2. Add the pack import to the correct config scope. A LOCAL in-tree pack is imported
#      via a DIRECT config entry (the gastown pattern) — NOT via `gc import add`, which
#      targets remote/git-backed packs and mis-resolves a local file:// source. So a
#      surgical, backed-up edit writes:
#        --town       ->  <city>/pack.toml   [imports.personas]
#        --rig <name> ->  <city>/city.toml   [rigs.imports.personas] (under the [[rigs]]
#                         entry whose name matches <name>)
#      source is recorded relative to the city root (e.g. "packs/personas").
#   3. --town only: add the "use-personas" discipline fragment to city.toml
#      [agent_defaults] append_fragments (idempotent; the table/array are created if
#      absent). This is the non-deprecated home; the old top-level global_fragments key
#      is deprecated.
#   4. Trigger re-projection with `gc reload` so the claude overlay's SessionStart hook
#      is materialized + merged into projected settings.
#   5. Verify: `gc lint`, the skill shows in `gc skill list`, the import is registered,
#      and (best-effort) the projected .claude settings carry the equip hook.
#
# Idempotent: re-running is a no-op (each mutating step is guarded by a presence check).
# Any config file it edits is backed up first. --dry-run prints the plan and changes
# nothing. Fails loudly on unexpected state.
#
# Reverse with uninstall.sh (same scope flags).

set -euo pipefail

# Stripped-PATH guard (this environment sometimes ships a minimal PATH).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOME}/go/bin:${HOME}/.local/bin:${PATH}"

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_NAME="personas"     # import binding name + skill prefix
IMPORT_NAME="personas"
# The single discipline prompt-fragment this pack ships. It has a file at
# template-fragments/<name>.template.md and is wired into city.toml [agent_defaults]
# append_fragments on --town scope.
FRAGMENTS=("use-personas")
SKILL_QUALIFIED="${PACK_NAME}.equip-persona"
HOOK_MARKER="personas/hooks/equip-on-task-pickup.sh"   # unique substring of our hook command

# ---- arg parsing -----------------------------------------------------------
SCOPE=""          # "town" | "rig"
RIG=""
DRY_RUN=0
NO_RELOAD=0
CITY=""

die()  { printf 'install.sh: error: %s\n' "$*" >&2; exit 1; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
run()  { # echo + execute, or just echo under --dry-run
  if [ "$DRY_RUN" -eq 1 ]; then printf '    [dry-run] %s\n' "$*"; else printf '    + %s\n' "$*"; eval "$@"; fi
}

usage() {
  sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --town)      SCOPE="town"; shift ;;
    --rig)       SCOPE="rig"; RIG="${2:-}"; [ -n "$RIG" ] || die "--rig requires a rig name"; shift 2 ;;
    --rig=*)     SCOPE="rig"; RIG="${1#*=}"; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --no-reload) NO_RELOAD=1; shift ;;
    --city)      CITY="${2:-}"; [ -n "$CITY" ] || die "--city requires a path"; shift 2 ;;
    --city=*)    CITY="${1#*=}"; shift ;;
    -h|--help)   usage 0 ;;
    *)           die "unknown argument: $1 (try --help)" ;;
  esac
done

[ -n "$SCOPE" ] || die "choose a scope: --town or --rig <name>"

# ---- locate the city -------------------------------------------------------
# Default: the city that physically contains this pack (…/<city>/packs/personas).
# When the pack is still in its source rig (blackrim-personas/pack), pass --city.
if [ -z "$CITY" ]; then
  CITY="$(cd "$PACK_DIR/../.." && pwd)"
fi
[ -f "$CITY/city.toml" ] || die "no city.toml at city root: $CITY (pass --city <path>; if the pack is in its source rig, vendor it into <city>/packs/personas first)"
CITY="$(cd "$CITY" && pwd)"

# Source path recorded in the import: relative to the city root if the pack lives under
# it (a bare relative path with no "./" prefix, e.g. "packs/personas"), else absolute.
if [ "${PACK_DIR#"$CITY"/}" != "$PACK_DIR" ]; then
  PACK_SRC="${PACK_DIR#"$CITY"/}"
else
  PACK_SRC="$PACK_DIR"
fi

GC=(gc --city "$CITY")

step "personas install"
info "scope:     $SCOPE${RIG:+ ($RIG)}"
info "pack:      $PACK_DIR"
info "city:      $CITY"
info "import as: $IMPORT_NAME  (source: $PACK_SRC)"
[ "$DRY_RUN" -eq 1 ] && info "MODE:      DRY RUN (no changes will be made)"

command -v gc >/dev/null 2>&1 || die "gc not found on PATH"

# For --rig, fail loudly now if the rig isn't configured, before any other step runs.
if [ "$SCOPE" = "rig" ]; then
  if ! "${GC[@]}" import list --rig "$RIG" >/dev/null 2>&1; then
    die "rig \"$RIG\" not found in $CITY/city.toml (configure the rig first)"
  fi
fi

# ---- helpers ---------------------------------------------------------------
backup_file() { # back up $1 once per run to <file>.personas.bak.<ts>
  local f="$1"
  [ -f "$f" ] || return 0
  local b="${f}.personas.bak.$(date +%Y%m%d%H%M%S)"
  if [ "$DRY_RUN" -eq 1 ]; then printf '    [dry-run] backup %s -> %s\n' "$f" "$b"; return 0; fi
  cp -p "$f" "$b"; printf '    backup: %s\n' "$b"
}

import_present() { # 0 if IMPORT_NAME is registered at the active scope.
  if [ "$SCOPE" = "rig" ]; then
    if "${GC[@]}" import list --rig "$RIG" 2>/dev/null | awk '{print $1}' | grep -qx "$IMPORT_NAME"; then
      return 0
    fi
    rig_import_in_config "$RIG"
  else
    if "${GC[@]}" import list 2>/dev/null | awk '{print $1}' | grep -qx "$IMPORT_NAME"; then
      return 0
    fi
    grep -Eq "^\[imports\.${IMPORT_NAME}\][[:space:]]*$" "$CITY/pack.toml" 2>/dev/null
  fi
}

rig_import_in_config() { # 0 if [rigs.imports.IMPORT_NAME] exists under rig $1
  python3 - "$CITY/city.toml" "$1" "$IMPORT_NAME" <<'PY'
import sys, re
path, rig, name = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path).read().splitlines(keepends=True)
starts = [i for i, l in enumerate(lines) if re.match(r'^\[\[rigs\]\]\s*$', l)]
for k, s in enumerate(starts):
    end = starts[k + 1] if k + 1 < len(starts) else len(lines)
    for j in range(s + 1, end):
        if re.match(r'^\[', lines[j]) and not re.match(r'^\[(\[rigs\]\]|rigs(\.|\]))', lines[j]):
            end = j; break
    named = None
    for j in range(s + 1, end):
        m = re.match(r'^\s*name\s*=\s*["\'](.+?)["\']\s*$', lines[j])
        if m:
            named = m.group(1); break
    if named != rig:
        continue
    hdr = re.compile(r'^\[rigs\.imports\.%s\]\s*$' % re.escape(name))
    if any(hdr.match(lines[j]) for j in range(s + 1, end)):
        sys.exit(0)
    sys.exit(1)
sys.exit(1)
PY
}

fragment_present() { # 0 if fragment $1 is already in [agent_defaults] append_fragments
  python3 - "$CITY/city.toml" "$1" <<'PY'
import sys, re
path, frag = sys.argv[1], sys.argv[2]
try:
    src = open(path).read()
except OSError:
    sys.exit(1)
lines = src.splitlines(keepends=True)
hdr = re.compile(r'^\[agent_defaults\]\s*$')
start = next((i for i, l in enumerate(lines) if hdr.match(l)), None)
if start is None:
    sys.exit(1)
end = len(lines)
for j in range(start + 1, len(lines)):
    if re.match(r'^\[', lines[j]):
        end = j; break
body = "".join(lines[start + 1:end])
m = re.search(r'(?m)^\s*append_fragments\s*=\s*(\[[^\]]*\])', body)
if not m:
    sys.exit(1)
items = [x.strip().strip('"').strip("'") for x in m.group(1)[1:-1].split(',') if x.strip()]
sys.exit(0 if frag in items else 1)
PY
}

edit_fragment() { # add|remove fragment $2 in [agent_defaults] append_fragments (idempotent)
  python3 - "$CITY/city.toml" "$1" "$2" <<'PY'
import sys, re
path, action, frag = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(path).read()
lines = src.splitlines(keepends=True)

def find_table(name):
    hdr = re.compile(r'^\[%s\]\s*$' % re.escape(name))
    s = next((i for i, l in enumerate(lines) if hdr.match(l)), None)
    if s is None:
        return None, None
    e = len(lines)
    for j in range(s + 1, len(lines)):
        if re.match(r'^\[', lines[j]):
            e = j; break
    return s, e

start, end = find_table("agent_defaults")

if action == "add":
    if start is None:
        sep = "" if (src == "" or src.endswith("\n")) else "\n"
        block = '%s\n[agent_defaults]\nappend_fragments = ["%s"]\n' % (sep, frag)
        open(path, "w").write(src + block)
        sys.exit(0)
    body_lines = lines[start + 1:end]
    body = "".join(body_lines)
    m = re.search(r'(?m)^(\s*append_fragments\s*=\s*)(\[[^\]]*\])', body)
    if m:
        items = [x.strip().strip('"').strip("'")
                 for x in m.group(2)[1:-1].split(',') if x.strip()]
        if frag in items:
            sys.exit(0)
        items.append(frag)
        new_arr = "[" + ", ".join('"%s"' % x for x in items) + "]"
        new_body = body[:m.start(2)] + new_arr + body[m.end(2):]
        open(path, "w").write("".join(lines[:start + 1]) + new_body + "".join(lines[end:]))
        sys.exit(0)
    insert = 'append_fragments = ["%s"]\n' % frag
    out = lines[:start + 1] + [insert] + lines[start + 1:]
    open(path, "w").write("".join(out))
    sys.exit(0)

# action == remove
if start is None:
    sys.exit(0)
body_lines = lines[start + 1:end]
body = "".join(body_lines)
m = re.search(r'(?m)^(\s*append_fragments\s*=\s*)(\[[^\]]*\])', body)
if not m:
    sys.exit(0)
items = [x.strip().strip('"').strip("'")
         for x in m.group(2)[1:-1].split(',') if x.strip()]
if frag not in items:
    sys.exit(0)
items = [x for x in items if x != frag]
new_arr = "[" + ", ".join('"%s"' % x for x in items) + "]"
new_body = body[:m.start(2)] + new_arr + body[m.end(2):]
open(path, "w").write("".join(lines[:start + 1]) + new_body + "".join(lines[end:]))
PY
}

edit_import() { # add|remove a DIRECT-config import (gastown style); idempotent.
  # args: <action> <file> <import_name> <source> [<rig_name>]
  python3 - "$2" "$1" "$3" "$4" "${5:-}" <<'PY'
import sys, re
path, action, name, source, rig = sys.argv[1:6]
rig = rig or None

def fail(msg):
    sys.stderr.write("edit_import: %s\n" % msg); sys.exit(3)

lines = open(path).read().splitlines(keepends=True)

if rig is None:
    table = "imports"
    anchor = next((i for i, l in enumerate(lines) if re.match(r'^\[imports\]\s*$', l)), None)
    if anchor is None: fail("[imports] table not found in %s" % path)
    hi = len(lines)
else:
    table = "rigs.imports"
    starts = [i for i, l in enumerate(lines) if re.match(r'^\[\[rigs\]\]\s*$', l)]
    if not starts: fail("no [[rigs]] blocks in %s" % path)
    target_start = None; hi = len(lines)
    for k, s in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        for j in range(s + 1, end):
            if re.match(r'^\[', lines[j]) and not re.match(r'^\[(\[rigs\]\]|rigs(\.|\]))', lines[j]):
                end = j; break
        named = None
        for j in range(s + 1, end):
            m = re.match(r'^\s*name\s*=\s*["\'](.+?)["\']\s*$', lines[j])
            if m: named = m.group(1); break
        if named == rig:
            target_start, hi = s, end; break
    if target_start is None: fail('no [[rigs]] block with name = "%s" in %s' % (rig, path))
    anchor = next((i for i in range(target_start, hi) if re.match(r'^\[rigs\.imports\]\s*$', lines[i])), None)
    if anchor is None: fail('[rigs.imports] not found under rig "%s" in %s' % (rig, path))

header = "[%s.%s]" % (table, name)
sub = re.compile(r'^\[%s\.%s\]\s*$' % (re.escape(table), re.escape(name)))
existing = next((i for i in range(anchor, hi) if sub.match(lines[i])), None)

if action == "add":
    if existing is not None: sys.exit(0)
    lines.insert(anchor + 1, "%s\nsource = \"%s\"\n" % (header, source))
    open(path, "w").write("".join(lines))
elif action == "remove":
    if existing is None: sys.exit(0)
    end = existing + 1
    if end < len(lines) and re.match(r'^\s*source\s*=', lines[end]): end += 1
    del lines[existing:end]
    open(path, "w").write("".join(lines))
else:
    fail("unknown action: %s" % action)
PY
}

# ---- step 1: venv ----------------------------------------------------------
step "1/5  engine venv"
if [ -x "$PACK_DIR/.venv/bin/python" ]; then
  info "already present: $PACK_DIR/.venv (skipping setup.sh)"
else
  run "bash \"$PACK_DIR/setup.sh\""
  [ "$DRY_RUN" -eq 1 ] && info "(dry-run) would build venv via setup.sh"
fi

# ---- step 2: import --------------------------------------------------------
step "2/5  register pack import ($SCOPE scope)"
if import_present; then
  info "import \"$IMPORT_NAME\" already registered — no-op"
else
  if [ "$SCOPE" = "rig" ]; then
    IMPORT_CFG="$CITY/city.toml"
    backup_file "$IMPORT_CFG"
    if [ "$DRY_RUN" -eq 1 ]; then
      info "[dry-run] add [rigs.imports.$IMPORT_NAME] (source = \"$PACK_SRC\") under rig \"$RIG\" in $IMPORT_CFG"
    else
      edit_import add "$IMPORT_CFG" "$IMPORT_NAME" "$PACK_SRC" "$RIG" \
        || die "failed to add [rigs.imports.$IMPORT_NAME] under rig \"$RIG\" in $IMPORT_CFG"
      info "added [rigs.imports.$IMPORT_NAME] (source = \"$PACK_SRC\") under rig \"$RIG\""
    fi
  else
    IMPORT_CFG="$CITY/pack.toml"
    backup_file "$IMPORT_CFG"
    if [ "$DRY_RUN" -eq 1 ]; then
      info "[dry-run] add [imports.$IMPORT_NAME] (source = \"$PACK_SRC\") to $IMPORT_CFG"
    else
      edit_import add "$IMPORT_CFG" "$IMPORT_NAME" "$PACK_SRC" \
        || die "failed to add [imports.$IMPORT_NAME] to $IMPORT_CFG"
      info "added [imports.$IMPORT_NAME] (source = \"$PACK_SRC\")"
    fi
  fi
fi

# ---- step 3: agent_defaults append_fragments (town only) -------------------
step "3/5  prompt fragment ([agent_defaults] append_fragments)"
if [ "$SCOPE" = "town" ]; then
  backed_up=0
  for frag in "${FRAGMENTS[@]}"; do
    if fragment_present "$frag"; then
      info "\"$frag\" already in [agent_defaults] append_fragments — no-op"
    elif [ "$DRY_RUN" -eq 1 ]; then
      info "[dry-run] add \"$frag\" to [agent_defaults] append_fragments in $CITY/city.toml"
    else
      if [ "$backed_up" -eq 0 ]; then backup_file "$CITY/city.toml"; backed_up=1; fi
      edit_fragment add "$frag"
      info "added \"$frag\" to [agent_defaults] append_fragments"
    fi
  done
else
  info "rig scope: append_fragments is city-wide and not touched"
  info "(the rig's agents still get the skill + equip hook from the import)"
fi

# ---- step 4: re-project ----------------------------------------------------
step "4/5  re-project (gc reload)"
if [ "$NO_RELOAD" -eq 1 ]; then
  info "--no-reload: skipping. Run 'gc reload' (or restart the city) to apply."
elif [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] gc reload  (materializes the claude overlay + merges SessionStart)"
else
  if "${GC[@]}" reload >/dev/null 2>&1; then
    info "gc reload: ok"
  else
    info "gc reload returned non-zero (city may be stopped). Projection will"
    info "happen on the next 'gc start' / 'gc rig boot'. Continuing."
  fi
fi

# ---- step 5: verify --------------------------------------------------------
step "5/5  verify"
if [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] would verify: gc lint, gc skill list, import registered, hook projected"
  step "personas install — DRY RUN complete (no changes made)"
  exit 0
fi

fail=0

# 5a. lint
if "${GC[@]}" lint "$PACK_DIR" >/dev/null 2>&1; then
  info "lint: ok"
else
  info "lint: FAILED"; "${GC[@]}" lint "$PACK_DIR" || true; fail=1
fi

# 5b. import registered
if import_present; then info "import: registered ($IMPORT_NAME)"; else info "import: MISSING"; fail=1; fi

# 5c. skill visible (binding-qualified).
if [ "$SCOPE" = "rig" ]; then
  if "${GC[@]}" skill list --rig "$RIG" 2>/dev/null | grep -q "$SKILL_QUALIFIED"; then
    info "skill: visible ($SKILL_QUALIFIED, rig $RIG)"
  else
    info "skill: not yet visible at rig scope (it lands when the rig's agents project)"
  fi
else
  if "${GC[@]}" skill list 2>/dev/null | grep -q "$SKILL_QUALIFIED" \
     || "${GC[@]}" skill list 2>/dev/null | grep -q "$SKILL_QUALIFIED"; then
    info "skill: visible ($SKILL_QUALIFIED)"
  else
    info "skill: not yet listed (catalog builds on next gc start; import is registered)"
  fi
fi

# 5d. fragment (town only) — must be present
if [ "$SCOPE" = "town" ]; then
  for frag in "${FRAGMENTS[@]}"; do
    if fragment_present "$frag"; then info "fragment: \"$frag\" in [agent_defaults] append_fragments"; else info "fragment: \"$frag\" MISSING"; fail=1; fi
  done
fi

# 5e. equip hook projected (best-effort — only present once a claude agent has
#     projected; absence is not fatal if the city is stopped).
hook_hits=0
while IFS= read -r f; do
  if grep -q "$HOOK_MARKER" "$f" 2>/dev/null; then hook_hits=$((hook_hits+1)); fi
done < <(find "$CITY/.gc/agents" "$CITY/.claude" "$CITY/.gc/settings.json" \
              -name 'settings.json' 2>/dev/null)
if [ "$hook_hits" -gt 0 ]; then
  info "hook: SessionStart equip hook projected in $hook_hits settings file(s)"
else
  info "hook: not yet in any projected settings (expected if the city is stopped;"
  info "      it materializes on the next agent session start / gc start)"
fi

if [ "$SCOPE" = "rig" ]; then REVERSE_FLAGS="--rig $RIG"; else REVERSE_FLAGS="--town"; fi
echo
if [ "$fail" -eq 0 ]; then
  step "personas install complete ($SCOPE${RIG:+ $RIG})"
  info "Agents will equip a best-fit persona on task pickup; inspect with"
  info "'personas list' / 'personas match \"<task>\"' / 'personas cache'."
  info "Reverse with: $PACK_DIR/uninstall.sh $REVERSE_FLAGS"
  exit 0
else
  step "personas install finished WITH WARNINGS ($SCOPE${RIG:+ $RIG})"
  info "Review the lines marked FAILED/MISSING above."
  exit 1
fi
