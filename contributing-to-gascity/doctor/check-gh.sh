#!/bin/sh
set -eu

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found"
  echo "Install the GitHub CLI so you can search duplicates and file issues/PRs against gastownhall/gascity."
  exit 2
fi

echo "gh CLI available"
