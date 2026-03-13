#!/bin/sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found"
  echo "Docker is required for the default sandboxed execution path. Install it, or use gc rlm install --environment local for trusted local-only use."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker CLI found but daemon unavailable"
  echo "Start the Docker daemon before using the default sandboxed execution path."
  exit 1
fi

echo "Docker available"
