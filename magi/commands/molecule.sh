#!/bin/sh
#
# magi/commands/molecule.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi molecule` to the Python
# orchestrator magi_molecule.py. Subcommands: bootstrap (chain doctor ->
# install -> bootstrap-project -> status -> analyze via bd_create+bd_dep);
# pour (delegates to bd mol pour with the bundled formula); wisp
# (delegates to bd mol wisp).
#
# USAGE:
#   gc magi molecule bootstrap [<project-path>]
#   gc magi molecule pour <formula>
#   gc magi molecule wisp <molecule-id>
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
    printf 'gc magi molecule: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_molecule.py" "$@"
