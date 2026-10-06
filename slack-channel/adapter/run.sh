#!/usr/bin/env bash
set -euo pipefail

log() { echo "gc-slack-channel-adapter run.sh: $*" >&2; }

version_key() {
  local trimmed major minor patch rest
  trimmed="${1%%[!0-9.]*}"
  IFS=. read -r major minor patch rest <<<"$trimmed"
  printf '%05d%05d%05d\n' \
    "$((10#0${major:-0}))" "$((10#0${minor:-0}))" "$((10#0${patch:-0}))"
}

bin_dir="$(cd "$(dirname "$0")" && pwd)"
adapter_bin="$bin_dir/gc-slack-channel-adapter"

if [[ -x "$adapter_bin" ]]; then
  exec "$adapter_bin" "$@"
fi

log "binary missing at $adapter_bin — rebuilding from source (pack cache was likely re-materialized git-only by 'gc import install')"

go_bin="$(type -P go 2>/dev/null || true)"
if [[ -n "$go_bin" ]]; then
  if [[ "$go_bin" != /* ]]; then
    go_bin="$(cd "$(dirname "$go_bin")" && pwd)/$(basename "$go_bin")"
  fi
else
  for cand in /opt/homebrew/bin/go /usr/local/go/bin/go /usr/local/bin/go \
              /usr/bin/go /bin/go "${HOME:-}/go/bin/go"; do
    if [[ -x "$cand" ]]; then go_bin="$cand"; break; fi
  done
fi
if [[ -z "$go_bin" ]]; then
  log "ERROR: no Go toolchain found (checked PATH, /opt/homebrew/bin, /usr/local/go/bin, /usr/local/bin, /usr/bin, /bin, ~/go/bin)"
  log "manual fix: cd $bin_dir && go build -o gc-slack-channel-adapter ."
  exit 1
fi

go_version="$("$go_bin" version 2>/dev/null || echo 'version unknown')"
need_go="$(sed -n 's/^go[[:space:]]\{1,\}\([0-9][0-9.]*\).*/\1/p' "$bin_dir/go.mod" 2>/dev/null | head -n1)"
have_go="$(printf '%s\n' "$go_version" | sed -n 's/^go version go\([0-9][0-9.]*\).*/\1/p')"
go_too_old=0
if [[ -n "$need_go" && -n "$have_go" ]] &&
   (( 10#$(version_key "$have_go") < 10#$(version_key "$need_go") )); then
  go_too_old=1
  if [[ "${GOTOOLCHAIN:-auto}" == "local" ]]; then
    log "ERROR: need Go >= $need_go, found $have_go at $go_bin (GOTOOLCHAIN=local pins this toolchain)"
    log "manual fix: install Go >= $need_go, unset GOTOOLCHAIN, or prebuild: cd $bin_dir && go build -o gc-slack-channel-adapter ."
    exit 1
  fi
  log "WARNING: $go_bin is $have_go but go.mod needs >= $need_go — Go will try to fetch the required toolchain (needs network and a writable module cache)"
fi

if [[ -z "${GOCACHE:-}" && -z "${XDG_CACHE_HOME:-}" && -z "${HOME:-}" ]]; then
  export GOCACHE="${TMPDIR:-/tmp}/gc-slack-channel-adapter-gocache"
  log "no HOME / XDG_CACHE_HOME / GOCACHE in the environment — building with GOCACHE=$GOCACHE"
fi

if [[ -z "${GOPATH:-}" && -z "${GOMODCACHE:-}" && -z "${HOME:-}" ]]; then
  export GOPATH="${TMPDIR:-/tmp}/gc-slack-channel-adapter-gopath"
  log "no HOME / GOMODCACHE / GOPATH in the environment — building with GOPATH=$GOPATH"
fi

tmp_bin="$adapter_bin.build.$$"
trap 'rm -f "$tmp_bin"' EXIT
log "building with $go_bin ($go_version)"
if ! (cd "$bin_dir" && "$go_bin" build -o "$tmp_bin" .); then
  log "ERROR: go build failed (compiler output above) — service cannot start"
  if (( go_too_old )); then
    log "likely cause: $go_bin is $have_go but go.mod needs >= $need_go — install Go >= $need_go or prebuild the binary"
  fi
  log "manual fix: cd $bin_dir && go build -o gc-slack-channel-adapter ."
  exit 1
fi
mv -f "$tmp_bin" "$adapter_bin"
trap - EXIT
log "rebuilt $adapter_bin OK — starting adapter"
exec "$adapter_bin" "$@"
