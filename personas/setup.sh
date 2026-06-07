#!/usr/bin/env bash
# Bootstrap the personas pack's self-contained venv (idempotent).
#
# Optional: the engine is pure-stdlib, so bin/personas also runs under any system
# python3. The venv just pins the tomli fallback for interpreters older than 3.11.
set -euo pipefail
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
"$PY" -m venv "$PACK_DIR/.venv"
"$PACK_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$PACK_DIR/.venv/bin/pip" install --quiet -r "$PACK_DIR/requirements.txt"
echo "personas venv ready: $PACK_DIR/.venv"
