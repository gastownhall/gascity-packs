#!/usr/bin/env bash
set -euo pipefail

exec jj-hunk squash "$@"
