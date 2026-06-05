#!/usr/bin/env bash
# cockpit — install lifecycle (reversible, idempotent).
#
#   install.sh (--town | --rig <name>) [--dry-run] [--city <path>] [--no-reload]
#
# Turns the cockpit pack ON at one of two scopes:
#   --town        city-wide: the pack's bin/cockpit + skills + contract become
#                 available to the whole city.
#   --rig <name>  one rig only: scoped to that rig's [[rigs]] entry.
#
# What it does (in order):
#   1. Build the engine venv via setup.sh (skipped if .venv already present;
#      optional — bin/cockpit also runs under any system python3).
#   2. Add the pack import to the correct config scope. A LOCAL in-tree pack is
#      imported via a DIRECT config entry (the gastown pattern) — NOT via
#      `gc import add`, which targets remote/git-backed packs and mis-resolves a
#      local file:// source. So a surgical, backed-up edit writes:
#        --town       ->  <city>/pack.toml   [imports.cockpit]
#        --rig <name> ->  <city>/city.toml   [rigs.imports.cockpit] (under the
#                         [[rigs]] entry whose name matches <name>)
#      source is recorded relative to the city root (e.g. "packs/cockpit").
#   3. Trigger re-projection with `gc reload` so the pack's bin/skills surface.
#   4. Verify: `gc lint`, the import is registered, and a `cockpit ready` smoke.
#
# Like provider-forge, cockpit ships NO prompt fragment and NO overlay hook — it
# is a CLI + contract + skills — so there is no append_fragments edit and no
# projected-settings hook to materialize. The install is: venv + import + reload
# + verify.
#
# This pack lives in the gascity-cockpit RIG and is meant to be VENDORED into a
# city as packs/cockpit (see docs/DESIGN.md §6). Run with --city <city-root> if
# the pack is not already under the target city.
#
# Idempotent: re-running is a no-op (each mutating step is guarded by a presence
# check). Any config file it edits is backed up first. --dry-run prints the plan
# and changes nothing. Fails loudly on unexpected state.
#
# Reverse with uninstall.sh (same scope flags).

set -euo pipefail

# Stripped-PATH guard (this environment sometimes ships a minimal PATH).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOME}/go/bin:${HOME}/.local/bin:${PATH}"

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_NAME="cockpit"     # import binding name
IMPORT_NAME="cockpit"

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
  sed -n '2,33p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
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
# Default: the city that physically contains this pack (…/<city>/packs/cockpit).
# When the pack is still in its source rig (gascity-cockpit/pack), pass --city.
if [ -z "$CITY" ]; then
  CITY="$(cd "$PACK_DIR/../.." && pwd)"
fi
[ -f "$CITY/city.toml" ] || die "no city.toml at city root: $CITY (pass --city <path>; if the pack is in its source rig, vendor it into <city>/packs/cockpit first — see docs/DESIGN.md §6)"
CITY="$(cd "$CITY" && pwd)"

# Source path recorded in the import: relative to the city root if the pack lives
# under it (a bare relative path with no "./" prefix, e.g. "packs/cockpit"),
# else absolute.
if [ "${PACK_DIR#"$CITY"/}" != "$PACK_DIR" ]; then
  PACK_SRC="${PACK_DIR#"$CITY"/}"
else
  PACK_SRC="$PACK_DIR"
fi

GC=(gc --city "$CITY")

step "cockpit install"
info "scope:     $SCOPE${RIG:+ ($RIG)}"
info "pack:      $PACK_DIR"
info "city:      $CITY"
info "import as: $IMPORT_NAME  (source: $PACK_SRC)"
[ "$DRY_RUN" -eq 1 ] && info "MODE:      DRY RUN (no changes will be made)"

command -v gc >/dev/null 2>&1 || die "gc not found on PATH"

# For --rig, fail loudly now if the rig isn't configured, before any other step.
if [ "$SCOPE" = "rig" ]; then
  if ! "${GC[@]}" import list --rig "$RIG" >/dev/null 2>&1; then
    die "rig \"$RIG\" not found in $CITY/city.toml (configure the rig first)"
  fi
fi

# ---- helpers ---------------------------------------------------------------
backup_file() { # back up $1 once per run to <file>.cockpit.bak.<ts>
  local f="$1"
  [ -f "$f" ] || return 0
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
step "1/4  engine venv"
if [ -x "$PACK_DIR/.venv/bin/python" ]; then
  info "already present: $PACK_DIR/.venv (skipping setup.sh)"
else
  run "bash \"$PACK_DIR/setup.sh\""
  [ "$DRY_RUN" -eq 1 ] && info "(dry-run) would build venv via setup.sh"
fi

# ---- step 2: import --------------------------------------------------------
step "2/4  register pack import ($SCOPE scope)"
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

# ---- step 3: re-project ----------------------------------------------------
step "3/4  re-project (gc reload)"
if [ "$NO_RELOAD" -eq 1 ]; then
  info "--no-reload: skipping. Run 'gc reload' (or restart the city) to apply."
elif [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] gc reload  (surfaces the pack's bin/cockpit + skills)"
else
  if "${GC[@]}" reload >/dev/null 2>&1; then
    info "gc reload: ok"
  else
    info "gc reload returned non-zero (city may be stopped). Projection will"
    info "happen on the next 'gc start' / 'gc rig boot'. Continuing."
  fi
fi

# ---- step 4: verify --------------------------------------------------------
step "4/4  verify"
if [ "$DRY_RUN" -eq 1 ]; then
  info "[dry-run] would verify: gc lint, import registered, cockpit ready smoke"
  step "cockpit install — DRY RUN complete (no changes made)"
  exit 0
fi

fail=0

# 4a. lint
if "${GC[@]}" lint "$PACK_DIR" >/dev/null 2>&1; then
  info "lint: ok"
else
  info "lint: FAILED"; "${GC[@]}" lint "$PACK_DIR" || true; fail=1
fi

# 4b. import registered
if import_present; then info "import: registered ($IMPORT_NAME)"; else info "import: MISSING"; fail=1; fi

# 4c. cockpit ready smoke (best-effort): a non-zero exit means the /v0 API is down
#     or version-incompatible on THIS machine — surface as advice, not an install
#     failure (the install itself succeeded).
if [ -x "$PACK_DIR/bin/cockpit" ]; then
  if "$PACK_DIR/bin/cockpit" ready >/dev/null 2>&1; then
    info "ready: city is Cockpit-ready (/v0 reachable + compatible)"
  else
    info "ready: /v0 API not reachable/compatible yet (run 'bin/cockpit ready';"
    info "       start the city with 'gc start', then 'bin/cockpit discover --write')"
  fi
fi

if [ "$SCOPE" = "rig" ]; then REVERSE_FLAGS="--rig $RIG"; else REVERSE_FLAGS="--town"; fi
echo
if [ "$fail" -eq 0 ]; then
  step "cockpit install complete ($SCOPE${RIG:+ $RIG})"
  info "Next: 'bin/cockpit ready' to verify, then 'bin/cockpit discover --write'"
  info "to publish the discovery descriptor the extension reads."
  info "Reverse with: $PACK_DIR/uninstall.sh $REVERSE_FLAGS"
  exit 0
else
  step "cockpit install finished WITH WARNINGS ($SCOPE${RIG:+ $RIG})"
  info "Review the lines marked FAILED/MISSING above."
  exit 1
fi
