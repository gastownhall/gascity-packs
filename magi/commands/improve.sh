#!/bin/sh
#
# magi/commands/improve.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi improve` to the Python
# orchestrator magi_improve.py. Same argv hygiene as analyze: orchestrator
# consumes its own argv and exports PROJECT_ANALYZER_* env vars before
# exec'ing the project_analyzer/improve_project_analysis.sh script.
#
# USAGE:
#   gc magi improve <project-path> [--model NAME] [--lm-url URL]
#                                  [--force] [--context N] [--api-token TOK]
#                                  [--blocks-on KIND] [--no-bd]
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
    printf 'gc magi improve: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_improve.py" "$@"
