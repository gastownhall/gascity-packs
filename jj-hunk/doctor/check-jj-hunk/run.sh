#!/usr/bin/env bash
set -euo pipefail

if ! command -v jj-hunk >/dev/null 2>&1; then
  echo "jj-hunk is required. Install with: cargo install --git https://github.com/mvzink/jj-hunk-tool.git"
  exit 1
fi

jj-hunk --help >/dev/null
echo "jj-hunk available: $(command -v jj-hunk)"
