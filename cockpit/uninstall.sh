#!/usr/bin/env bash
# cockpit — uninstall lifecycle (reverses everything install.sh did).
#
#   uninstall.sh (--town | --rig <name>) [--dry-run] [--city <path>]
#                [--purge] [--no-reload]
#
# Reverses, in order:
#   1. Remove the pack import. It is a DIRECT config entry (the gastown pattern,
#      not `gc import add`/`remove`), so a surgical, backed-up edit drops it:
#        --town       -> drops  <city>/pack.toml   [imports.cockpit]
#        --rig <name> -> drops  <city>/city.toml   [rigs.imports.cockpit]
#                        (from under the [[rigs]] entry whose name matches <name>)
#   2. Re-project with `gc reload` so the pack's surfaces drop out of projection.
#   3. --purge: delete the engine .venv.
#
# Like provider-forge, cockpit ships NO prompt fragment and NO overlay hook, so
# there is nothing to remove from append_fragments and no projected
# .claude/settings.json hook to strip — the uninstall is: import + reload
# (+ optional purge). The discovery descriptor it may have published under
# $GC_HOME/runtime/cockpit/ is NOT removed here (it is supervisor runtime state,
# refreshed/cleared by re-discovery or gc stop); delete it by hand if desired.
#
# Idempotent (re-running after a clean uninstall is a no-op). Any file it edits
# is backed up first. --dry-run prints the plan and changes nothing.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOME}/go/bin:${HOME}/.local/bin:${PATH}"

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_NAME="cockpit"
IMPORT_NAME="cockpit"

SCOPE=""; RIG=""; DRY_RUN=0; NO_RELOAD=0; PURGE=0; CITY=""

die()  { printf 'uninstall.sh: error: %s\n' "$*" >&2; exit 1; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
run()  { if [ "$DRY_RUN" -eq 1 ]; then printf '    [dry-run] %s\n' "$*"; else printf '    + %s\n' "$*"; eval "$@"; fi; }

usage() { sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

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

step "cockpit uninstall"
info "scope:  $SCOPE${RIG:+ ($RIG)}"
info "city:   $CITY"
[ "$PURGE" -eq 1 ]   && info "purge:  yes (will delete .venv)"
[ "$DRY_RUN" -eq 1 ] && info "MODE:   DRY RUN (no changes will be made)"

command -v gc >/dev/null 2>&1 || die "gc not found on PATH"

backup_file() {
  local f="$1"; [ -f "$f" ] || return 0
  local b="${f}.cockpit.bak.$(date +%Y%m%d%H%M%S)"
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

edit_import() { # add|remove a DIRECT-config import (gastown style); idempotent.
  # args: <action> <file> <import_name> <source> [<rig_name>]  (source ignored on remove)
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

# ---- step 1: import --------------------------------------------------------
step "1/3  remove pack import ($SCOPE scope)"
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

# ---- step 2: re-project ----------------------------------------------------
step "2/3  re-project (gc reload)"
if [ "$NO_RELOAD" -eq 1 ]; then
  info "--no-reload: skipping. Run 'gc reload' to drop the pack from projection."
elif [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] gc reload  (drops the pack's surfaces from projection)"
else
  if "${GC[@]}" reload >/dev/null 2>&1; then info "gc reload: ok"
  else info "gc reload non-zero (city may be stopped); clean state applies on next start"; fi
fi

# ---- step 3: purge venv ----------------------------------------------------
step "3/3  engine venv"
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
  step "cockpit uninstall — DRY RUN complete (no changes made)"; exit 0
fi
fail=0
if import_present; then info "import: STILL REGISTERED ($IMPORT_NAME)"; fail=1; else info "import: removed"; fi

echo
if [ "$fail" -eq 0 ]; then
  step "cockpit uninstall complete ($SCOPE${RIG:+ $RIG})"
  info "Backups (*.cockpit.bak.*) were left in place; remove them when satisfied."
  exit 0
else
  step "cockpit uninstall finished WITH WARNINGS"
  info "Review the STILL-* lines above."
  exit 1
fi
