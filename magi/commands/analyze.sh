#!/bin/sh
#
# magi/commands/analyze.sh
# ==============================================================================
# Description: POSIX wrapper that dispatches `gc magi analyze` to the Python
# orchestrator magi_analyze.py. The orchestrator owns argv parsing
# (allow_abbrev=False) and exports the corresponding PROJECT_ANALYZER_* env
# vars before exec'ing the project_analyzer/analyze_project.sh distribution
# script with a single positional path.
#
# USAGE:
#   gc magi analyze <project-path> [--model NAME] [--lm-url URL]
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
    printf 'gc magi analyze: missing Gas City pack context\n' >&2
    exit 1
fi
exec python3 "${GC_PACK_DIR}/scripts/magi_analyze.py" "$@"
