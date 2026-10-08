#!/bin/sh
set -eu
bb_plugin_dir="${GC_BB_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/gascity/bb/plugin}"
if [ -L "$bb_plugin_dir/current" ]; then
    bb_plugin_dir="$bb_plugin_dir/current"
elif [ -e "$bb_plugin_dir/current" ]; then
    echo "Unrecognized BB provider current entry; inspect $bb_plugin_dir/current before running." >&2
    exit 1
fi
if [ ! -f "$bb_plugin_dir/dist/cli.js" ]; then
    echo "BB provider is not installed on this host. Run gc bb install." >&2
    exit 1
fi
exec node "$bb_plugin_dir/dist/cli.js" "$@"
