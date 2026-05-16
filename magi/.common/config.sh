#!/usr/bin/env bash
#
# config.sh
# ==============================================================================
# Deprecated compatibility shim for the pack-root .env file.
#
# OPTIONS:
#   source .common/config.sh
#
# ENVIRONMENT VARIABLES:
#   All variables from ../.env are exported when that file exists.
#
# DEPENDENCIES:
#   Internal: ../.env
#   External: None.
# ==============================================================================

set -a
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PACK_ENV_FILE="${SCRIPT_DIR}/../.env"
if [[ -f "${PACK_ENV_FILE}" ]]; then
    source "${PACK_ENV_FILE}"
fi
set +a
