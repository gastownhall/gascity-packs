#!/bin/sh
set -eu
bb_pack_dir="${GC_PACK_DIR:?Run this command through gc bb install}"
bb_plugin_dir="${GC_BB_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/gascity/bb/plugin}"
command -v node >/dev/null 2>&1 || { echo "Node.js 22+ is required" >&2; exit 2; }
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) process.exit(1)' || { echo "Node.js 22+ is required" >&2; exit 2; }
command -v npm >/dev/null 2>&1 || { echo "npm is required" >&2; exit 2; }
command -v bb >/dev/null 2>&1 || { echo "Install the BB CLI first" >&2; exit 2; }
mkdir -p "$bb_plugin_dir"
cp "$bb_pack_dir/assets/plugin/package.json" "$bb_pack_dir/assets/plugin/package-lock.json" "$bb_pack_dir/assets/plugin/tsconfig.json" "$bb_pack_dir/assets/plugin/server.ts" "$bb_pack_dir/assets/plugin/host.ts" "$bb_plugin_dir/"
mkdir -p "$bb_plugin_dir/src"
cp "$bb_pack_dir/assets/plugin/src/"*.ts "$bb_plugin_dir/src/"
(cd "$bb_plugin_dir" && npm ci --ignore-scripts --no-audit --no-fund && npm run build)
bb plugin install "path:$bb_plugin_dir" "$@"
echo "Provider installed. Run gc bb connect on each BB execution host."
