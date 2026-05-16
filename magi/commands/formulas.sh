#!/bin/sh
#
# magi/commands/formulas.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi formulas` to the Python
# orchestrator magi_formulas.py. Subcommands: list (enumerates bundled
# formulas), show <name> (pretty-prints a formula definition), cook <name>
# (invokes `bd mol pour` on the named formula).
#
# USAGE:
#   gc magi formulas list
#   gc magi formulas show <name>
#   gc magi formulas cook <name>
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH   Gas City root (required)
#   GC_PACK_DIR    Pack root for magi (required)
#
# DEPENDENCIES:
#   External: python3
# ==============================================================================
set -eu
if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_PACK_DIR:-}" ]; then
    printf 'gc magi formulas: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_formulas.py" "$@"
