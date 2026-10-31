#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")/.." && pwd)/source_delivery.py" check
