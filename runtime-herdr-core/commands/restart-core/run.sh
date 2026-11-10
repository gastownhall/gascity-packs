#!/bin/sh
exec "$(dirname "$0")/../../assets/bin/gc-runtime-herdr-core" x-command restart-core "$@"
