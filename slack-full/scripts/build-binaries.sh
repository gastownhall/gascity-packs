#!/bin/sh
# build-binaries.sh — build the slack-full pack's Go binaries in place.
#
# The adapter (adapter/gc-slack-adapter) and operator CLI (cli/gc-slack-cli)
# are gitignored build artifacts. A fresh pack cache clone — `gc import
# install`, a repin, `gc pack fetch` — does NOT contain them, and gc runs
# no pack build hook on import, so after every such clone the [[service]]
# command and the commands/<cmd>.sh wrappers point at binaries that do not
# exist. That is the root cause of the 2026-07-05 ~16.6h Slack outage.
#
# Run this once after any import/repin to (re)build both binaries in place;
# the binaries/doctor check (`gc slack-full doctor`, doctor/check-binaries.sh)
# then verifies the result. Idempotent — re-running rebuilds in place. Loud —
# a failed compile aborts non-zero with the toolchain output and never
# leaves a half-built pack reported as success.
#
# Pack dir resolves from $GC_PACK_DIR when set (the installed-pack path gc
# exports), else from this script's location — same idiom as
# doctor/check-binaries.sh.
set -eu

pack_dir="${GC_PACK_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"

if ! command -v go >/dev/null 2>&1; then
	echo "build-binaries: 'go' toolchain not found on PATH — cannot build pack binaries" >&2
	exit 1
fi

echo "build-binaries: pack dir = $pack_dir"
echo "build-binaries: using $(command -v go) — $(go version)"

echo "build-binaries: building adapter/gc-slack-adapter ..."
( cd "$pack_dir/adapter" && go build -o gc-slack-adapter . )

echo "build-binaries: building cli/gc-slack-cli ..."
( cd "$pack_dir/cli" && go build -o gc-slack-cli . )

# Never report success on a partial build: confirm both binaries landed as
# executables (mirrors doctor/check-binaries.sh's own check).
missing=""
for bin in adapter/gc-slack-adapter cli/gc-slack-cli; do
	if [ ! -x "$pack_dir/$bin" ]; then
		missing="$missing $bin"
	fi
done
if [ -n "$missing" ]; then
	echo "build-binaries: FAILED — expected binaries missing after build:$missing" >&2
	exit 1
fi

echo "build-binaries: OK — adapter and CLI binaries built in place"
