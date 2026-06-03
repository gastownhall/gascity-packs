#!/usr/bin/env bash
# One-command test + coverage runner for the ast-lens emitter.
#
# Runs the behavioral suite under tests/ with branch coverage of bin/outline.py
# and FAILS if line coverage drops below the threshold (default 90%, enforced by
# coverage.py's fail_under in pyproject.toml). Optionally runs ruff lint first.
#
# Usage:
#   tests/run.sh             # tests + coverage (gated at >= 90% line cov)
#   tests/run.sh --lint      # also run `ruff check` on bin/ and tests/ first
#   COV_MIN=95 tests/run.sh  # override the coverage gate
#
# Exit code is non-zero if any test fails, lint fails, or coverage is under gate.
set -euo pipefail

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PACK_DIR"

PY="$PACK_DIR/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

COV_MIN="${COV_MIN:-90}"

LINT=0
for arg in "$@"; do
  case "$arg" in
    --lint) LINT=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

if [ "$LINT" -eq 1 ]; then
  echo "==> ruff check"
  "$PY" -m ruff check bin/outline.py tests/
fi

echo "==> pytest + coverage (gate: ${COV_MIN}% line)"
exec "$PY" -m pytest tests/ \
  --cov=bin \
  --cov-branch \
  --cov-report=term-missing \
  "--cov-fail-under=${COV_MIN}"
