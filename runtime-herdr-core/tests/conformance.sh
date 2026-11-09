#!/usr/bin/env bash
# gc's RPP checks for runtime herdr-core, against fake-hc (never a real
# herdr-core: its holder-loss sweep can kill unrelated processes).
#
#   GC_BIN=/path/to/gc tests/conformance.sh [--default-root] [--json]
#
# Runs `gc runtime check` and `gc runtime conformance` on the pack's
# executable and fails unless both pass, every requirement passes or is
# skipped, and the report says v2-ready. fake-hc stands in for the hc binary
# (GC_HC_TEST_BIN, honoured only under GC_HC_TEST=1).
#
# By default all state lives in a scratch GC_EXEC_STATE_DIR. --default-root
# leaves GC_EXEC_STATE_DIR unset, proving the default state root under the
# password-database home; it refuses to run outside CI (CI=true), where the
# home is ephemeral. --json reads `gc runtime conformance --json` instead of
# the text report (needs a gc whose --json report encodes).
#
# Teardown stops every core under the state root (the city key, `unscoped`
# and the conformance kit's own city keys each start one), fails if fake-hc
# saw a request or sent a result outside hc's schema, and removes the root.
#
# PYTHON names the interpreter fake-hc runs under (it needs jsonschema);
# default: python3.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pack="$(cd "$here/.." && pwd)"
entry="$pack/assets/bin/gc-runtime-herdr-core"
gc="${GC_BIN:-gc}"
python="${PYTHON:-python3}"
default_root=0
json=0
for arg in "$@"; do
  case "$arg" in
    --default-root) default_root=1 ;;
    --json) json=1 ;;
    *) echo "usage: $0 [--default-root] [--json]" >&2; exit 2 ;;
  esac
done

if [ "$default_root" = 1 ] && [ "${CI:-}" != "true" ]; then
  echo "conformance.sh: --default-root writes under your home; it runs only in CI (CI=true)" >&2
  exit 2
fi

scratch="$(mktemp -d /tmp/hcconf-XXXXXX)"
bin="$scratch/bin"
mkdir -p "$bin"
"$python" -c 'import sys; sys.path.insert(0, sys.argv[1]); from fakehc.cli import write_launcher; write_launcher(sys.argv[2])' \
  "$pack/tests" "$bin/herdr-core"

if [ "$default_root" = 1 ]; then
  unset GC_EXEC_STATE_DIR
  root="$("$python" -c 'import os, pwd; print(os.path.join(pwd.getpwuid(os.getuid()).pw_dir, ".local/state/gc-runtime-herdr-core"))')"
else
  export GC_EXEC_STATE_DIR="$scratch/state"
  root="$GC_EXEC_STATE_DIR"
fi
export GC_HC_TEST=1
export GC_HC_TEST_BIN="$bin/herdr-core"
unset GC_EXEC_CITY_PATH GC_EXEC_CITY_NAME GC_RPP_FAULT

teardown() {
  local status=$?
  local lock state session sock
  for lock in "$root"/herdr-core/*/core.lock; do
    [ -e "$lock" ] || continue
    state="$(dirname "$lock")"
    session="$(basename "$state")"
    sock="$(cat "$lock")"
    HC_SESSION="$session" HC_SOCKET="$sock" XDG_STATE_HOME="$root" "$bin/herdr-core" server stop >/dev/null 2>&1 || true
    if [ -s "$state/schema-violations.log" ]; then
      echo "fake-hc schema violations ($session):" >&2
      cat "$state/schema-violations.log" >&2
      status=1
    fi
  done
  rm -rf "$scratch"
  if [ "$default_root" = 1 ]; then rm -rf "$root"; fi
  exit "$status"
}
trap teardown EXIT

echo "== gc runtime check"
"$gc" runtime check "$entry"

echo "== gc runtime conformance"
report="$scratch/conformance.out"
if [ "$json" = 1 ]; then
  "$gc" runtime conformance --json "$entry" | tee "$report"
  "$python" - "$report" <<'PY'
import json, sys
report = json.load(open(sys.argv[1]))
failed = [r["code"] for r in report["results"] if r["status"].lower() == "fail"]
assert not failed, f"failed: {failed}"
assert report["v2_ready"] is True, "not v2-ready"
PY
else
  "$gc" runtime conformance "$entry" | tee "$report"
  if grep -q '^FAIL' "$report"; then
    echo "conformance: a requirement failed" >&2
    exit 1
  fi
  grep -qx 'v2-ready: yes' "$report" || { echo "conformance: not v2-ready" >&2; exit 1; }
fi
echo "== conformance passed (v2-ready)"
