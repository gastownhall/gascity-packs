#!/usr/bin/env bash
# personas — uninstall lifecycle (reverses everything install.sh did).
#
#   uninstall.sh (--town | --rig <name>) [--dry-run] [--city <path>]
#                [--purge] [--no-reload]
#
# Reverses, in order:
#   1. --town only: remove the "use-personas" fragment from city.toml [agent_defaults]
#      append_fragments (surgical, backed-up; rest of the file byte-exact).
#   2. Remove the pack import. It is a DIRECT config entry (the gastown pattern), so a
#      surgical, backed-up edit drops it:
#        --town       -> drops  <city>/pack.toml   [imports.personas]
#        --rig <name> -> drops  <city>/city.toml   [rigs.imports.personas]
#                        (from under the [[rigs]] entry whose name matches <name>)
#   3. Re-project with `gc reload` so the pack's surfaces (skill + SessionStart equip
#      hook) drop out of projection.
#   4. --purge: delete the engine .venv.
#
# The shared warm cache (under .beads/personas/ or $GC_RIG_ROOT) is NOT removed here —
# it is rebuildable runtime state. Clear it with `personas sweep --all` or delete the
# file by hand if desired.
#
# Idempotent (re-running after a clean uninstall is a no-op). Any file it edits is
# backed up first. --dry-run prints the plan and changes nothing.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOME}/go/bin:${HOME}/.local/bin:${PATH}"

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_NAME="personas"
IMPORT_NAME="personas"
FRAGMENTS=("use-personas")

SCOPE=""; RIG=""; DRY_RUN=0; NO_RELOAD=0; PURGE=0; CITY=""

die()  { printf 'uninstall.sh: error: %s\n' "$*" >&2; exit 1; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
run()  { if [ "$DRY_RUN" -eq 1 ]; then printf '    [dry-run] %s\n' "$*"; else printf '    + %s\n' "$*"; eval "$@"; fi; }

usage() { sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

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

step "personas uninstall"
info "scope:  $SCOPE${RIG:+ ($RIG)}"
info "city:   $CITY"
[ "$PURGE" -eq 1 ]   && info "purge:  yes (will delete .venv)"
[ "$DRY_RUN" -eq 1 ] && info "MODE:   DRY RUN (no changes will be made)"

command -v gc >/dev/null 2>&1 || die "gc not found on PATH"

backup_file() {
  local f="$1"; [ -f "$f" ] || return 0
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
if action == "remove":
    if start is None:
        sys.exit(0)
    body = "".join(lines[start + 1:end])
    m = re.search(r'(?m)^(\s*append_fragments\s*=\s*)(\[[^\]]*\])', body)
    if not m:
        sys.exit(0)
    items = [x.strip().strip('"').strip("'") for x in m.group(2)[1:-1].split(',') if x.strip()]
    if frag not in items:
        sys.exit(0)
    items = [x for x in items if x != frag]
    new_arr = "[" + ", ".join('"%s"' % x for x in items) + "]"
    new_body = body[:m.start(2)] + new_arr + body[m.end(2):]
    open(path, "w").write("".join(lines[:start + 1]) + new_body + "".join(lines[end:]))
    sys.exit(0)
sys.exit(0)
PY
}

edit_import() { # remove a DIRECT-config import (gastown style); idempotent.
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

sub = re.compile(r'^\[%s\.%s\]\s*$' % (re.escape(table), re.escape(name)))
existing = next((i for i in range(anchor, hi) if sub.match(lines[i])), None)
if existing is None:
    sys.exit(0)
end = existing + 1
if end < len(lines) and re.match(r'^\s*source\s*=', lines[end]): end += 1
del lines[existing:end]
open(path, "w").write("".join(lines))
PY
}

# ---- step 1: fragment (town only) ------------------------------------------
step "1/4  remove prompt fragment ([agent_defaults] append_fragments)"
if [ "$SCOPE" = "town" ]; then
  backed_up=0
  for frag in "${FRAGMENTS[@]}"; do
    if fragment_present "$frag"; then
      if [ "$DRY_RUN" -eq 1 ]; then
        info "[dry-run] remove \"$frag\" from [agent_defaults] append_fragments"
      else
        if [ "$backed_up" -eq 0 ]; then backup_file "$CITY/city.toml"; backed_up=1; fi
        edit_fragment remove "$frag"
        info "removed \"$frag\" from [agent_defaults] append_fragments"
      fi
    else
      info "\"$frag\" not in append_fragments — no-op"
    fi
  done
else
  info "rig scope: append_fragments is city-wide and not touched"
fi

# ---- step 2: import --------------------------------------------------------
step "2/4  remove pack import ($SCOPE scope)"
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

# ---- step 3: re-project ----------------------------------------------------
step "3/4  re-project (gc reload)"
if [ "$NO_RELOAD" -eq 1 ]; then
  info "--no-reload: skipping. Run 'gc reload' to drop the pack from projection."
elif [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] gc reload  (drops the pack's surfaces from projection)"
else
  if "${GC[@]}" reload >/dev/null 2>&1; then info "gc reload: ok"
  else info "gc reload non-zero (city may be stopped); clean state applies on next start"; fi
fi

# ---- step 4: purge venv ----------------------------------------------------
step "4/4  engine venv"
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
  step "personas uninstall — DRY RUN complete (no changes made)"; exit 0
fi
fail=0
if import_present; then info "import: STILL REGISTERED ($IMPORT_NAME)"; fail=1; else info "import: removed"; fi
if [ "$SCOPE" = "town" ]; then
  for frag in "${FRAGMENTS[@]}"; do
    if fragment_present "$frag"; then info "fragment: \"$frag\" STILL PRESENT"; fail=1; else info "fragment: \"$frag\" removed"; fi
  done
fi

echo
if [ "$fail" -eq 0 ]; then
  step "personas uninstall complete ($SCOPE${RIG:+ $RIG})"
  info "Backups (*.personas.bak.*) were left in place; remove them when satisfied."
  info "The shared warm cache was left intact (clear with 'personas sweep --all')."
  exit 0
else
  step "personas uninstall finished WITH WARNINGS"
  info "Review the STILL-* lines above."
  exit 1
fi
