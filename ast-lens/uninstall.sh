#!/usr/bin/env bash
# ast-lens — uninstall lifecycle (reverses everything install.sh did).
#
#   uninstall.sh (--town | --rig <name>) [--dry-run] [--city <path>]
#                [--purge] [--no-reload]
#
# Reverses, in order:
#   1. Remove the pack's discipline fragments ("read-with-outline" and
#      "symbolic-edits") from city.toml global_fragments (--town only); each is
#      removed only if present (idempotent), and the file is backed up once.
#   2. Remove the pack import. It is a DIRECT config entry (the gastown pattern,
#      not `gc import add`/`remove`), so a surgical, backed-up edit drops it:
#        --town       -> drops  <city>/pack.toml   [imports.ast-lens]
#        --rig <name> -> drops  <city>/city.toml   [rigs.imports.ast-lens] (from
#                        under the [[rigs]] entry whose name matches <name>)
#   3. Clean the materialized claude overlay: strip the ast-lens PreToolUse
#      (Read) hook ENTRY from every projected .claude/settings.json under the
#      city (the override source is merge-sticky — gc never deletes overlay
#      keys, so it must be removed explicitly). Any non-ast-lens hook entry is
#      preserved; an empty matcher block / empty PreToolUse key is removed.
#   4. Re-project with `gc reload` so the city-level .gc/settings.json is
#      regenerated from the now-clean override (drops the stale PreToolUse).
#   5. --purge: delete the emitter .venv.
#
# Idempotent (re-running after a clean uninstall is a no-op). Any file it edits
# is backed up first. --dry-run prints the plan and changes nothing.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOME}/go/bin:${HOME}/.local/bin:${PATH}"

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_NAME="ast-lens"
IMPORT_NAME="ast-lens"
# Both discipline prompt-fragments this pack ships (read side + write side);
# mirror of install.sh. Removed from city.toml global_fragments on --town scope.
FRAGMENTS=("read-with-outline" "symbolic-edits")
HOOK_MARKER="ast-lens/hooks/outline-on-read.sh"

SCOPE=""; RIG=""; DRY_RUN=0; NO_RELOAD=0; PURGE=0; CITY=""

die()  { printf 'uninstall.sh: error: %s\n' "$*" >&2; exit 1; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
run()  { if [ "$DRY_RUN" -eq 1 ]; then printf '    [dry-run] %s\n' "$*"; else printf '    + %s\n' "$*"; eval "$@"; fi; }

usage() { sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --town)      SCOPE="town"; shift ;;
    --rig)       SCOPE="rig"; RIG="${2:-}"; [ -n "$RIG" ] || die "--rig requires a rig name"; shift 2 ;;
    --rig=*)     SCOPE="rig"; RIG="${1#*=}"; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --purge)     PURGE=1; shift ;;
    --no-reload) NO_RELOAD=1; shift ;;
    --city)      CITY="${2:-}"; [ -n "$CITY" ] || die "--city requires a path"; shift 2 ;;
    --city=*)    CITY="${1#*=}"; shift ;;
    -h|--help)   usage 0 ;;
    *)           die "unknown argument: $1 (try --help)" ;;
  esac
done

[ -n "$SCOPE" ] || die "choose a scope: --town or --rig <name>"

if [ -z "$CITY" ]; then CITY="$(cd "$PACK_DIR/../.." && pwd)"; fi
[ -f "$CITY/city.toml" ] || die "no city.toml at city root: $CITY (pass --city <path>)"
CITY="$(cd "$CITY" && pwd)"

GC=(gc --city "$CITY")

step "ast-lens uninstall"
info "scope:  $SCOPE${RIG:+ ($RIG)}"
info "city:   $CITY"
[ "$PURGE" -eq 1 ]   && info "purge:  yes (will delete .venv)"
[ "$DRY_RUN" -eq 1 ] && info "MODE:   DRY RUN (no changes will be made)"

command -v gc >/dev/null 2>&1 || die "gc not found on PATH"

backup_file() {
  local f="$1"; [ -f "$f" ] || return 0
  local b="${f}.ast-lens.bak.$(date +%Y%m%d%H%M%S)"
  if [ "$DRY_RUN" -eq 1 ]; then printf '    [dry-run] backup %s -> %s\n' "$f" "$b"; return 0; fi
  cp -p "$f" "$b"; printf '    backup: %s\n' "$b"
}

import_present() { # 0 if IMPORT_NAME is registered at the active scope.
  # gc import list reports direct-config imports (the gastown style); fall back
  # to a config grep for the [..imports.NAME] table if the catalog is unbuilt.
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

fragment_present() { grep -Eq "global_fragments[[:space:]]*=.*\"$1\"" "$CITY/city.toml"; }

edit_fragment_remove() { # remove fragment $1 from city.toml global_fragments (idempotent)
  python3 - "$CITY/city.toml" "$1" <<'PY'
import sys, re
path, frag = sys.argv[1], sys.argv[2]
src = open(path).read()
m = re.search(r'(?m)^(\s*global_fragments\s*=\s*)(\[[^\]]*\])', src)
if not m: sys.exit(0)
prefix, arr = m.group(1), m.group(2)
items = [x.strip().strip('"').strip("'") for x in arr[1:-1].split(',') if x.strip()]
if frag not in items: sys.exit(0)
items = [x for x in items if x != frag]
new = "[" + ", ".join('"%s"' % x for x in items) + "]"
open(path, "w").write(src[:m.start()] + prefix + new + src[m.end():])
PY
}

edit_import() { # add|remove a DIRECT-config import (gastown style); idempotent.
  # The mirror of install.sh's helper — a local in-tree pack is a direct config
  # entry, not `gc import add`. Surgical text edit; rest of file byte-exact, so
  # removal exactly reverses the add install.sh made.
  #   town: file=pack.toml, [imports] -> [imports.IMPORT_NAME]
  #   rig : file=city.toml, the [rigs.imports] of the [[rigs]] named $5
  #         -> [rigs.imports.IMPORT_NAME]
  # args: <action> <file> <import_name> <source> [<rig_name>]   (source ignored
  #       on remove; pass "" for clarity)
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

# Strip our PreToolUse(Read) entry from one settings.json, in place.
# Returns 0 (success) iff the file was modified; 1 if there was nothing of ours
# to strip. All human-readable progress goes to stderr so the return code is the
# sole signal callers consume.
strip_hook() {
  local f="$1"
  [ -f "$f" ] || return 1
  grep -q "$HOOK_MARKER" "$f" 2>/dev/null || return 1   # nothing of ours here
  if [ "$DRY_RUN" -eq 1 ]; then printf '    [dry-run] strip ast-lens PreToolUse from %s\n' "$f" >&2; return 0; fi
  local tmp; tmp="$(mktemp)"
  if jq --arg mark "$HOOK_MARKER" '
        if (.hooks.PreToolUse | type) == "array" then
          .hooks.PreToolUse = (
            .hooks.PreToolUse
            | map( .hooks = ((.hooks // []) | map(select((.command // "") | contains($mark) | not))) )
            | map(select((.hooks | length) > 0))
          )
          | (if (.hooks.PreToolUse | length) == 0 then del(.hooks.PreToolUse) else . end)
        else . end
      ' "$f" > "$tmp" 2>/dev/null; then
    if ! cmp -s "$f" "$tmp"; then
      backup_file "$f" >&2
      cat "$tmp" > "$f"
      printf '    cleaned: %s\n' "$f" >&2
      rm -f "$tmp"
      return 0
    fi
    rm -f "$tmp"
    return 1
  else
    rm -f "$tmp"
    printf '    WARN: jq could not rewrite %s (left untouched)\n' "$f" >&2
    return 1
  fi
}

# ---- step 1: fragments (town only) -----------------------------------------
# Remove EACH of the pack's discipline fragments from city.toml global_fragments,
# skipping any already absent (idempotent). The file is backed up at most once
# per run, and only when at least one fragment actually needs removing — never
# under --dry-run, and never when none are present.
step "1/5  prompt fragments (global_fragments)"
if [ "$SCOPE" = "town" ]; then
  backed_up=0
  for frag in "${FRAGMENTS[@]}"; do
    if fragment_present "$frag"; then
      if [ "$DRY_RUN" -eq 1 ]; then
        info "[dry-run] remove \"$frag\" from global_fragments"
      else
        if [ "$backed_up" -eq 0 ]; then backup_file "$CITY/city.toml"; backed_up=1; fi
        edit_fragment_remove "$frag"
        info "removed \"$frag\" from global_fragments"
      fi
    else
      info "\"$frag\" not in global_fragments — no-op"
    fi
  done
else
  info "rig scope: global_fragments not touched"
fi

# ---- step 2: import --------------------------------------------------------
# The import is a DIRECT config entry (the gastown pattern), so remove it with a
# surgical, backed-up edit — NOT `gc import remove` (paired with install's
# edit_import; the removal exactly reverses the added table).
#   rig : <city>/city.toml -> drop [rigs.imports.ast-lens] under the [[rigs]] named $RIG
#   town: <city>/pack.toml -> drop [imports.ast-lens]
step "2/5  remove pack import ($SCOPE scope)"
if import_present; then
  if [ "$SCOPE" = "rig" ]; then
    IMPORT_CFG="$CITY/city.toml"
    backup_file "$IMPORT_CFG"
    if [ "$DRY_RUN" -eq 1 ]; then
      info "[dry-run] remove [rigs.imports.$IMPORT_NAME] from under rig \"$RIG\" in $IMPORT_CFG"
    else
      edit_import remove "$IMPORT_CFG" "$IMPORT_NAME" "" "$RIG" \
        || die "failed to remove [rigs.imports.$IMPORT_NAME] from $IMPORT_CFG"
      info "removed [rigs.imports.$IMPORT_NAME] from under rig \"$RIG\""
    fi
  else
    IMPORT_CFG="$CITY/pack.toml"
    backup_file "$IMPORT_CFG"
    if [ "$DRY_RUN" -eq 1 ]; then
      info "[dry-run] remove [imports.$IMPORT_NAME] from $IMPORT_CFG"
    else
      edit_import remove "$IMPORT_CFG" "$IMPORT_NAME" "" \
        || die "failed to remove [imports.$IMPORT_NAME] from $IMPORT_CFG"
      info "removed [imports.$IMPORT_NAME]"
    fi
  fi
else
  info "import \"$IMPORT_NAME\" not registered at this scope — no-op"
fi

# ---- step 3: clean materialized claude overlay -----------------------------
step "3/5  clean projected claude settings (strip PreToolUse hook)"
changed_any=0
# Search every settings.json under the city: the city-root override
# (<city>/.claude/settings.json), the projected output (<city>/.gc/settings.json),
# and any per-agent workdir copies (rig worktrees etc.). node_modules excluded.
# `find … -prune` keeps the walk out of vendored .claude dirs in node_modules.
while IFS= read -r f; do
  [ -n "$f" ] || continue
  if strip_hook "$f"; then changed_any=1; fi
done < <(find "$CITY/.gc" "$CITY/.claude" \
              \( -path '*/node_modules/*' -prune \) -o \
              -name 'settings.json' -print 2>/dev/null | sort -u)
if [ "$changed_any" -eq 1 ]; then
  info "stripped ast-lens PreToolUse hook from projected settings"
else
  info "no ast-lens PreToolUse hook found in any projected settings — nothing to clean"
fi

# ---- step 4: re-project ----------------------------------------------------
step "4/5  re-project (gc reload)"
if [ "$NO_RELOAD" -eq 1 ]; then
  info "--no-reload: skipping. Run 'gc reload' to regenerate projected settings."
elif [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] gc reload  (regenerates .gc/settings.json from the clean override)"
else
  if "${GC[@]}" reload >/dev/null 2>&1; then info "gc reload: ok"
  else info "gc reload non-zero (city may be stopped); clean state applies on next start"; fi
fi

# ---- step 5: purge venv ----------------------------------------------------
step "5/5  emitter venv"
if [ "$PURGE" -eq 1 ]; then
  if [ -d "$PACK_DIR/.venv" ]; then
    run "rm -rf \"$PACK_DIR/.venv\""
    info "purged $PACK_DIR/.venv"
  else
    info "no .venv to purge"
  fi
else
  info "kept $PACK_DIR/.venv (pass --purge to delete it)"
fi

# ---- verify ----------------------------------------------------------------
step "verify"
if [ "$DRY_RUN" -eq 1 ]; then
  step "ast-lens uninstall — DRY RUN complete (no changes made)"; exit 0
fi
fail=0
if import_present; then info "import: STILL REGISTERED ($IMPORT_NAME)"; fail=1; else info "import: removed"; fi
if [ "$SCOPE" = "town" ]; then
  for frag in "${FRAGMENTS[@]}"; do
    if fragment_present "$frag"; then info "fragment: \"$frag\" STILL PRESENT"; fail=1; else info "fragment: \"$frag\" removed"; fi
  done
fi
leftover=0
while IFS= read -r f; do grep -q "$HOOK_MARKER" "$f" 2>/dev/null && leftover=$((leftover+1)); done \
  < <(find "$CITY/.gc" "$CITY/.claude" \( -path '*/node_modules/*' -prune \) -o -name 'settings.json' -print 2>/dev/null)
if [ "$leftover" -gt 0 ]; then info "hook: STILL in $leftover settings file(s)"; fail=1; else info "hook: removed from all projected settings"; fi

echo
if [ "$fail" -eq 0 ]; then
  step "ast-lens uninstall complete ($SCOPE${RIG:+ $RIG})"
  info "Backups (*.ast-lens.bak.*) were left in place; remove them when satisfied."
  exit 0
else
  step "ast-lens uninstall finished WITH WARNINGS"
  info "Review the STILL-* lines above."
  exit 1
fi
