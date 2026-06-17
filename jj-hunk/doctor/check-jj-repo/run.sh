#!/usr/bin/env bash
set -euo pipefail

if ! command -v jj >/dev/null 2>&1; then
  echo "jj is required for jj-hunk workflows"
  exit 1
fi

if ! jj root >/dev/null 2>&1; then
  echo "current directory is not inside a jj repository"
  exit 1
fi

echo "jj repo: $(jj root)"
