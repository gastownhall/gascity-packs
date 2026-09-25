#!/bin/sh
set -eu

if ! command -v git >/dev/null 2>&1; then
  echo "git not found"
  echo "Install git so you can verify the bug against origin/main before filing."
  exit 2
fi

echo "git available"
