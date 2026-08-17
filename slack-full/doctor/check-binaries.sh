#!/bin/sh
set -eu

pack_dir="${GC_PACK_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"

missing=""
for bin in adapter/gc-slack-adapter cli/gc-slack-cli; do
  if [ ! -x "$pack_dir/$bin" ]; then
    missing="$missing $bin"
  fi
done

if [ -n "$missing" ]; then
  echo "pack binaries not built:$missing"
  echo "Build them: run scripts/build-binaries.sh (rebuilds both in place; needed after any 'gc import install' / repin). See CONTRIBUTING.md."
  exit 2
fi

echo "adapter and CLI binaries built"
