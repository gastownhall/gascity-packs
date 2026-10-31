#!/usr/bin/env bash
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
    printf "python3 is required. Install Python 3 and retry this command.\n" >&2
    exit 78
fi
exec python3 "$(cd "$(dirname "$0")/.." && pwd)/source_delivery.py" check
