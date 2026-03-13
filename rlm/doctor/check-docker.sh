#!/bin/sh
set -eu

RUNTIME_DIR="${GC_PACK_STATE_DIR:-${GC_CITY_RUNTIME_DIR:-${GC_CITY_PATH:-}/.gc/runtime}/packs/rlm}"
if [ ! -f "$RUNTIME_DIR/config.toml" ] && [ -f "${GC_CITY_PATH:-}/.gc/rlm/config.toml" ]; then
  RUNTIME_DIR="${GC_CITY_PATH:-}/.gc/rlm"
fi
CONFIG_PATH="$RUNTIME_DIR/config.toml"
DOCKER_REQUIRED=0

if [ -n "${GC_CITY_PATH:-}" ] && [ -f "$CONFIG_PATH" ]; then
  if grep -Eq '^allowed_environments = .*"docker"' "$CONFIG_PATH"; then
    DOCKER_REQUIRED=1
  else
    echo "Docker not required"
    echo "The installed RLM runtime is configured for local-only execution."
    exit 0
  fi
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found"
  if [ "$DOCKER_REQUIRED" -eq 1 ]; then
    echo "Docker is required for the installed sandboxed execution path."
    exit 1
  fi
  echo "Sandboxed Docker execution is unavailable. Install Docker, or use gc rlm install --environment local for trusted local-only use."
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker CLI found but daemon unavailable"
  if [ "$DOCKER_REQUIRED" -eq 1 ]; then
    echo "Start the Docker daemon before using the installed sandboxed execution path."
    exit 1
  fi
  echo "Start the Docker daemon to enable sandboxed execution."
  exit 0
fi

echo "Docker available"
