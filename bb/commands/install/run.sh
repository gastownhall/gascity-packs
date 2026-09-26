#!/bin/sh
set -eu
: "${GC_PACK_DIR:?Run this command through gc bb install}"
command -v node >/dev/null 2>&1 || { echo "Node.js 22+ is required" >&2; exit 2; }
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) process.exit(1)' || { echo "Node.js 22+ is required" >&2; exit 2; }
command -v npm >/dev/null 2>&1 || { echo "npm is required" >&2; exit 2; }
command -v bb >/dev/null 2>&1 || { echo "Install the BB CLI first" >&2; exit 2; }
exec node "$(dirname "$0")/install.mjs" "$@"
