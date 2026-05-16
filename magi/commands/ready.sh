#!/bin/sh
#
# magi/commands/ready.sh
# ==============================================================================
# Description: POSIX wrapper for `gc magi ready`. Directly invokes `bd ready
# --label pack:magi` and passes user-supplied flags through. Deduplicates
# --label pack:magi if the user already supplied it. Warns when the user
# supplies additional --label flags (an AND filter, not OR). When bd is not
# on PATH the wrapper warns and exits 0.
#
# USAGE:
#   gc magi ready [--limit N] [--json] [--label TAG]
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH   Gas City root (required)
#   GC_PACK_DIR    Pack root for magi (required)
#
# DEPENDENCIES:
#   External: bd (optional; graceful degradation when missing)
# ==============================================================================
set -eu
if [ -z "${GC_CITY_PATH:-}" ] || [ -z "${GC_PACK_DIR:-}" ]; then
    printf 'gc magi ready: missing Gas City pack context\n' >&2
    exit 1
fi
BD_BIN="$(command -v bd || printf '')"
if [ -z "${BD_BIN}" ]; then
    printf 'gc magi ready: bd not on PATH; no ready work to report\n' >&2
    exit 0
fi
PACK_LABEL_SEEN=0
USER_LABEL_COUNT=0
for arg in "$@"; do
    case "${arg}" in
        --label=pack:magi|pack:magi)
            PACK_LABEL_SEEN=1
            ;;
        --label=*)
            USER_LABEL_COUNT=$((USER_LABEL_COUNT + 1))
            ;;
        --label)
            USER_LABEL_COUNT=$((USER_LABEL_COUNT + 1))
            ;;
    esac
done
if [ "${USER_LABEL_COUNT}" -gt 0 ] && [ "${PACK_LABEL_SEEN}" = "0" ]; then
    printf 'note: gc magi ready filters on pack:magi; your --label adds an AND filter, not an OR\n' >&2
fi
if [ "${PACK_LABEL_SEEN}" = "1" ]; then
    exec "${BD_BIN}" ready "$@"
fi
exec "${BD_BIN}" ready --label pack:magi "$@"
