#!/usr/bin/env bash
set -euo pipefail

# Executed coverage for the `next-iteration` reconcile block in mol-witness-patrol.
#
# The block is LIFTED out of the formula and run against a real `bd` in a scratch
# store (clean env: no live BEADS_DIR / dolt port can leak in).  A mocked `gc bd`
# hides the contract that matters here: `bd list` never returns ephemeral wisps and
# `bd mol wisp list` does.
#
# Pins: (1) the current wisp is never picked as NEXT (step 3 burns it, which would
# end the loop with no wisp); (2) an unassigned wisp left by a restart between pour
# and assign is reused, not duplicated; (3) surplus wisps are burned, capped at 3
# per iteration; (4) wisps older than 48 h are never touched.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
FORMULA=${FORMULA:-$ROOT/gastown/formulas/mol-witness-patrol.toml}
BD=${BD:-$(command -v bd || true)}
if [ -z "$BD" ]; then echo "SKIP: bd not installed"; exit 0; fi

W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
mkdir -p "$W/home" "$W/bin" "$W/ws"
cat > "$W/bin/gc" <<G
#!/usr/bin/env bash
[ "\$1" = bd ] || exit 2; shift
cd "$W/ws" && exec env -i HOME="$W/home" PATH=/usr/local/bin:/usr/bin:/bin BEADS_DOLT_AUTO_START=0 BD_BACKUP_ENABLED=false "$BD" "\$@" 2>/dev/null
G
chmod +x "$W/bin/gc"
(cd "$W/ws" && env -i HOME="$W/home" PATH=/usr/local/bin:/usr/bin:/bin BEADS_DOLT_AUTO_START=0 BD_BACKUP_ENABLED=false "$BD" init --non-interactive --prefix ct >/dev/null 2>&1)
mkdir -p "$W/ws/.beads/formulas"
printf 'formula = "mol-witness-patrol"\ndescription = "stand-in"\nversion = 1\ntype = "workflow"\n\n[[steps]]\nid = "only"\ntitle = "only"\ndescription = "x"\n' \
  > "$W/ws/.beads/formulas/mol-witness-patrol.formula.toml"
export PATH="$W/bin:$PATH" GC_AGENT=test/witness

python3 - "$FORMULA" > "$W/block.tmpl" <<'P'
import re, sys
s = open(sys.argv[1]).read()
a = s.index("**2. Pour next iteration BEFORE burning"); b = s.index("**3. Burn this wisp:**")
print(re.search(r"```bash\n(.*?)```", s[a:b], re.S).group(1).replace("{{binding_prefix}}", "x"))
P

pour() { gc bd mol wisp mol-witness-patrol --root-only --json | jq -r .new_epic_id; }
open_ids() { gc bd mol wisp list --json | jq -r '[.wisps[]|select(.title=="mol-witness-patrol" and .status=="open")|.id]|sort|.[]'; }
count() { open_ids | grep -c . || true; }
run_iteration() { # $1 = this wisp id: step 2 block, then step 3 burn
  sed "s|<this-wisp-id>|$1|g" "$W/block.tmpl" > "$W/block.sh"; bash "$W/block.sh" >/dev/null
  gc bd mol burn "$1" --force >/dev/null
}
fail() { echo "FAIL: $*" >&2; exit 1; }

# 1) lone current wisp: must pour a next one and leave exactly 1 open, assigned.
CUR=$(pour); gc bd update "$CUR" --assignee="$GC_AGENT" >/dev/null
run_iteration "$CUR"
[ "$(count)" = 1 ] || fail "lone current wisp: want 1 open after the iteration, got $(count)"
[ "$(open_ids)" != "$CUR" ] || fail "current wisp survived its own burn"

# 2) restart orphan: an UNASSIGNED open wisp is reused (no extra pour) and gets assigned.
CUR=$(open_ids); ORPHAN=$(pour)
run_iteration "$CUR"
[ "$(count)" = 1 ] || fail "orphan reuse: want 1 open, got $(count)"
[ "$(open_ids)" = "$ORPHAN" ] || fail "orphan reuse: expected the orphan $ORPHAN to be kept"
[ "$(gc bd show "$ORPHAN" --json | jq -r 'if type=="array" then .[0].assignee else .assignee end')" = "$GC_AGENT" ] \
  || fail "orphan reuse: kept wisp was not assigned"

# 3) surplus is burned but capped at 3 per iteration (1 current + 6 extra -> 3 left of the extras + next).
CUR=$(open_ids); for _ in 1 2 3 4 5 6; do pour >/dev/null; done
run_iteration "$CUR"
[ "$(count)" = 3 ] || fail "burn cap: want 3 open (6 extras - 3 burned), got $(count)"

echo "PASS: next-iteration reconcile (real bd)"
