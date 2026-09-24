#!/bin/sh
set -eu

if ! command -v gc >/dev/null 2>&1; then
  echo "gc CLI not found"
  echo "Install or build the gas-city CLI (\`make build\`) so you can run the city and reproduce behavior while contributing to gastownhall/gascity."
  exit 2
fi

echo "gc CLI available"
