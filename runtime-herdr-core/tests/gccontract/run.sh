#!/usr/bin/env bash
# gc's un-welded launch contract (RUNTIME-CONTRACT-020:
# runtimetest.RunUnweldedLaunchContract) against runtime herdr-core, through
# gc's own exec provider and fake-hc (never a real herdr-core).
#
#   GASCITY_PIN=<commit> tests/gccontract/run.sh
#   GASCITY_SRC=/path/to/gascity tests/gccontract/run.sh   (a local checkout)
#
# Copies the pinned gascity module (or GASCITY_SRC) to a scratch directory,
# installs unwelded_test.go.in as internal/runtime/exec's
# zz_herdrcore_unwelded_test.go, and runs it there. PYTHON names the
# interpreter fake-hc and the test agent run under (it needs jsonschema, and
# tomli below Python 3.11); default: python3.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pack="$(cd "$here/../.." && pwd)"
python="$(command -v "${PYTHON:-python3}")"

work="$(mktemp -d /tmp/hcgc-src-XXXXXX)"
cleanup() {
  chmod -R u+w "$work" 2>/dev/null || true
  rm -rf "$work"
}
trap cleanup EXIT

if [ -n "${GASCITY_SRC:-}" ]; then
  src="$GASCITY_SRC"
else
  : "${GASCITY_PIN:?set GASCITY_PIN to a gascity commit, or GASCITY_SRC to a checkout}"
  src="$(cd "$work" && go mod download -json "github.com/gastownhall/gascity@${GASCITY_PIN}" | "$python" -c 'import json, sys; print(json.load(sys.stdin)["Dir"])')"
fi
mkdir "$work/gascity"
(cd "$src" && tar --exclude=.git -cf - .) | (cd "$work/gascity" && tar -xf -)
chmod -R u+w "$work/gascity"
cp "$here/unwelded_test.go.in" "$work/gascity/internal/runtime/exec/zz_herdrcore_unwelded_test.go"

cd "$work/gascity"
GC_HERDR_CORE_PACK="$pack" GC_HERDR_CORE_PYTHON="$python" \
  go test ./internal/runtime/exec -run '^TestHerdrCoreUnwelded$' -count=1 -v
