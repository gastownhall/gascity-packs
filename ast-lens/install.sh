#!/usr/bin/env bash
# ast-lens — install lifecycle (reversible, idempotent).
#
#   install.sh (--town | --rig <name>) [--dry-run] [--city <path>] [--no-reload]
#
# Turns the ast-lens pack ON at one of two scopes:
#   --town        city-wide: every agent gets the skill + (opt-in) the
#                 read-with-outline (read side) and symbolic-edits (write side)
#                 prompt fragments + the claude PreToolUse hook.
#   --rig <name>  one rig only: that rig's agents get the skill + hook.
#
# What it does (in order):
#   1. Build the emitter venv via setup.sh (skipped if .venv already present).
#   2. Add the pack import to the correct config scope. A LOCAL in-tree pack is
#      imported via a DIRECT config entry (the gastown pattern) — NOT via
#      `gc import add`, which targets remote/git-backed packs and mis-resolves a
#      local file:// source. So a surgical, backed-up edit writes:
#        --town       ->  <city>/pack.toml   [imports.ast-lens]
#        --rig <name> ->  <city>/city.toml   [rigs.imports.ast-lens] (under the
#                         [[rigs]] entry whose name matches <name>)
#      source is recorded relative to the city root (e.g. "packs/ast-lens").
#   3. --town only: add the pack's discipline fragments ("read-with-outline"
#      and "symbolic-edits") to city.toml global_fragments — each added only if
#      not already present (no gc-native command exists for this key, so a
#      backed-up, surgical edit is used; the file is backed up once per run, and
#      only when at least one fragment actually needs adding).
#   4. Trigger re-projection with `gc reload` so the claude overlay's
#      PreToolUse hook is materialized + merged into the projected settings.
#   5. Verify: `gc lint`, the skill shows in `gc skill list`, the import is
#      registered, and (best-effort) the projected .claude settings carry the
#      PreToolUse hook.
#
# Idempotent: re-running is a no-op (each mutating step is guarded by a
# presence check). Any config file it edits is backed up first. --dry-run
# prints the plan and changes nothing. Fails loudly on unexpected state.
#
# Reverse with uninstall.sh (same scope flags).

set -euo pipefail

# Stripped-PATH guard (this environment sometimes ships a minimal PATH).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOME}/go/bin:${HOME}/.local/bin:${PATH}"

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_NAME="ast-lens"          # import binding name + skill prefix
IMPORT_NAME="ast-lens"
# Both discipline prompt-fragments this pack ships (read side + write side).
# Each has a file at template-fragments/<name>.template.md and is wired into
# city.toml global_fragments on --town scope.
FRAGMENTS=("read-with-outline" "symbolic-edits")
SKILL_QUALIFIED="${PACK_NAME}.read-with-outline"
HOOK_MARKER="ast-lens/hooks/outline-on-read.sh"   # unique substring of our hook command

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
# Default: the city that physically contains this pack (…/<city>/packs/ast-lens).
if [ -z "$CITY" ]; then
  CITY="$(cd "$PACK_DIR/../.." && pwd)"
fi
[ -f "$CITY/city.toml" ] || die "no city.toml at city root: $CITY (pass --city <path>)"
CITY="$(cd "$CITY" && pwd)"

# Source path recorded in the import: relative to the city root if the pack
# lives under it (matches how gastown is referenced — a bare relative path with
# no "./" prefix, e.g. "packs/ast-lens"), else absolute.
if [ "${PACK_DIR#"$CITY"/}" != "$PACK_DIR" ]; then
  PACK_SRC="${PACK_DIR#"$CITY"/}"
else
  PACK_SRC="$PACK_DIR"
fi

GC=(gc --city "$CITY")

step "ast-lens install"
info "scope:     $SCOPE${RIG:+ ($RIG)}"
info "pack:      $PACK_DIR"
info "city:      $CITY"
info "import as: $IMPORT_NAME  (source: $PACK_SRC)"
[ "$DRY_RUN" -eq 1 ] && info "MODE:      DRY RUN (no changes will be made)"

command -v gc >/dev/null 2>&1 || die "gc not found on PATH"

# For --rig, fail loudly now if the rig isn't configured, before any other step
# runs. `gc import list --rig <name>` exits non-zero for an unknown rig.
if [ "$SCOPE" = "rig" ]; then
  if ! "${GC[@]}" import list --rig "$RIG" >/dev/null 2>&1; then
    die "rig \"$RIG\" not found in $CITY/city.toml (configure the rig first)"
  fi
fi

# ---- helpers ---------------------------------------------------------------
backup_file() { # back up $1 once per run to <file>.ast-lens.bak.<ts>
  local f="$1"
  [ -f "$f" ] || return 0
  local b="${f}.ast-lens.bak.$(date +%Y%m%d%H%M%S)"
  if [ "$DRY_RUN" -eq 1 ]; then printf '    [dry-run] backup %s -> %s\n' "$f" "$b"; return 0; fi
  cp -p "$f" "$b"; printf '    backup: %s\n' "$b"
}

import_present() { # 0 if IMPORT_NAME is registered at the active scope.
  # gc import list reports direct-config imports (the gastown style) too, so it
  # is the primary signal. Fall back to a config grep for the [..imports.NAME]
  # table in case the catalog is unbuilt (stopped/fresh city).
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

fragment_present() { # 0 if fragment $1 is already in global_fragments
  grep -Eq "global_fragments[[:space:]]*=.*\"$1\"" "$CITY/city.toml"
}

edit_fragment() { # add|remove fragment $2 in city.toml global_fragments (idempotent)
  python3 - "$CITY/city.toml" "$1" "$2" <<'PY'
import sys, re
path, action, frag = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(path).read()
m = re.search(r'(?m)^(\s*global_fragments\s*=\s*)(\[[^\]]*\])', src)
if not m:
    sys.stderr.write("global_fragments key not found in %s\n" % path); sys.exit(3)
prefix, arr = m.group(1), m.group(2)
items = [x.strip().strip('"').strip("'") for x in arr[1:-1].split(',') if x.strip()]
if action == "add":
    if frag in items: sys.exit(0)
    items.append(frag)
else:  # remove
    if frag not in items: sys.exit(0)
    items = [x for x in items if x != frag]
new = "[" + ", ".join('"%s"' % x for x in items) + "]"
open(path, "w").write(src[:m.start()] + prefix + new + src[m.end():])
PY
}

edit_import() { # add|remove a DIRECT-config import (gastown style); idempotent.
  # Local in-tree packs are imported by a direct config entry, NOT `gc import
  # add` (which is for remote/git-backed packs and would mis-resolve a file://
  # source). Mirrors edit_fragment: surgical text edit, rest of file byte-exact,
  # so add<->remove round-trips perfectly.
  #   town: file=pack.toml, target [imports] -> [imports.IMPORT_NAME]
  #   rig : file=city.toml, target the [rigs.imports] of the [[rigs]] named $3,
  #         -> [rigs.imports.IMPORT_NAME]
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
step "1/5  emitter venv"
if [ -x "$PACK_DIR/.venv/bin/python" ]; then
  info "already present: $PACK_DIR/.venv (skipping setup.sh)"
else
  run "bash \"$PACK_DIR/setup.sh\""
  [ "$DRY_RUN" -eq 1 ] && info "(dry-run) would build venv via setup.sh"
fi

# ---- step 2: import --------------------------------------------------------
# Local in-tree packs are imported via a DIRECT config entry (the gastown
# pattern), NOT `gc import add` — that command is for remote/git-backed packs
# and mis-resolves a local file:// source. So we hand-edit the right config,
# surgically and backed-up (see edit_import).
#   rig : <city>/city.toml -> [rigs.imports.ast-lens] under the [[rigs]] named $RIG
#   town: <city>/pack.toml -> [imports.ast-lens]
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

# ---- step 3: global fragments (town only) ----------------------------------
# Add EACH of the pack's discipline fragments to city.toml global_fragments,
# skipping any already present (idempotent). The file is backed up at most once
# per run, and only when at least one fragment actually needs adding — never
# under --dry-run, and never when everything is already in place.
step "3/5  prompt fragments (global_fragments)"
if [ "$SCOPE" = "town" ]; then
  backed_up=0
  for frag in "${FRAGMENTS[@]}"; do
    if fragment_present "$frag"; then
      info "\"$frag\" already in global_fragments — no-op"
    elif [ "$DRY_RUN" -eq 1 ]; then
      info "[dry-run] add \"$frag\" to global_fragments in $CITY/city.toml"
    else
      if [ "$backed_up" -eq 0 ]; then backup_file "$CITY/city.toml"; backed_up=1; fi
      edit_fragment add "$frag"
      info "added \"$frag\" to global_fragments"
    fi
  done
else
  info "rig scope: global_fragments is city-wide and not touched"
  info "(the rig's agents still get the skill + PreToolUse hook from the import)"
fi

# ---- step 4: re-project ----------------------------------------------------
step "4/5  re-project (gc reload)"
if [ "$NO_RELOAD" -eq 1 ]; then
  info "--no-reload: skipping. Run 'gc reload' (or restart the city) to apply."
elif [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] gc reload  (materializes the claude overlay + merges PreToolUse)"
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
  step "ast-lens install — DRY RUN complete (no changes made)"
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

# 5c. skill visible (binding-qualified). Town: city scope. Rig: --agent of a
#     rig agent would be ideal, but the rig-scope skill shows under --rig list.
if [ "$SCOPE" = "rig" ]; then
  if "${GC[@]}" skill list --rig "$RIG" 2>/dev/null | grep -q "$SKILL_QUALIFIED"; then
    info "skill: visible ($SKILL_QUALIFIED, rig $RIG)"
  else
    info "skill: not yet visible at rig scope (it lands when the rig's agents project)"
  fi
else
  # The skill catalog is rebuilt lazily; on a freshly-bootstrapped or stopped
  # city the first `gc skill list` can race the catalog build, so retry once.
  if "${GC[@]}" skill list 2>/dev/null | grep -q "$SKILL_QUALIFIED" \
     || "${GC[@]}" skill list 2>/dev/null | grep -q "$SKILL_QUALIFIED"; then
    info "skill: visible ($SKILL_QUALIFIED)"
  else
    # Soft: the import is registered (hard-checked above); the catalog
    # finishes building on the next 'gc start' / reconcile.
    info "skill: not yet listed (catalog builds on next gc start; import is registered)"
  fi
fi

# 5d. fragments (town only) — every fragment in the list must be present
if [ "$SCOPE" = "town" ]; then
  for frag in "${FRAGMENTS[@]}"; do
    if fragment_present "$frag"; then info "fragment: \"$frag\" in global_fragments"; else info "fragment: \"$frag\" MISSING"; fail=1; fi
  done
fi

# 5e. PreToolUse hook projected (best-effort — only present once a claude
#     agent has projected; absence is not fatal if the city is stopped).
hook_hits=0
while IFS= read -r f; do
  if grep -q "$HOOK_MARKER" "$f" 2>/dev/null; then hook_hits=$((hook_hits+1)); fi
done < <(find "$CITY/.gc/agents" "$CITY/.claude" "$CITY/.gc/settings.json" \
              -name 'settings.json' 2>/dev/null)
if [ "$hook_hits" -gt 0 ]; then
  info "hook: PreToolUse(Read) projected in $hook_hits settings file(s)"
else
  info "hook: not yet in any projected settings (expected if the city is stopped;"
  info "      it materializes on the next agent session start / gc start)"
fi

if [ "$SCOPE" = "rig" ]; then REVERSE_FLAGS="--rig $RIG"; else REVERSE_FLAGS="--town"; fi
echo
if [ "$fail" -eq 0 ]; then
  step "ast-lens install complete ($SCOPE${RIG:+ $RIG})"
  info "Agents will read large source files outline-first."
  info "Reverse with: $PACK_DIR/uninstall.sh $REVERSE_FLAGS"
  exit 0
else
  step "ast-lens install finished WITH WARNINGS ($SCOPE${RIG:+ $RIG})"
  info "Review the lines marked FAILED/MISSING above."
  exit 1
fi
