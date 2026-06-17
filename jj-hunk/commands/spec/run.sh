#!/usr/bin/env bash
set -euo pipefail

exec jj-hunk list --spec-template --format yaml "$@"
