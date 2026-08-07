#!/bin/sh
set -eu

if ! command -v gc >/dev/null 2>&1 || ! gc bd version >/dev/null 2>&1; then
  echo "gc bd unavailable"
  echo "Install or expose gc with a working bd backend so the mattermost pack can manage fix-workflow beads."
  exit 2
fi

echo "gc bd available"
