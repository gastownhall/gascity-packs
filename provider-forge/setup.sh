#!/usr/bin/env bash
# Bootstrap the provider-forge pack's self-contained venv (idempotent).
set -euo pipefail
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
"$PY" -m venv "$PACK_DIR/.venv"
"$PACK_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$PACK_DIR/.venv/bin/pip" install --quiet -r "$PACK_DIR/requirements.txt"
echo "provider-forge venv ready: $PACK_DIR/.venv"
