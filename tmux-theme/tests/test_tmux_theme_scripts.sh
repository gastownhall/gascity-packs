#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

fail() {
  printf 'not ok - %s\n' "$*" >&2
  exit 1
}

assert_eq() {
  local want="$1"
  local got="$2"
  local label="$3"
  [[ "${got}" == "${want}" ]] || fail "${label}: expected [${want}], got [${got}]"
}

mkdir -p "${TMPDIR}/bin"

cat >"${TMPDIR}/bin/timeout" <<'STUB_TIMEOUT'
#!/bin/sh
shift
exec "$@"
STUB_TIMEOUT

cat >"${TMPDIR}/bin/bd" <<'STUB_BD'
#!/bin/sh
printf '%s\n' "$*" >> "${TMUX_THEME_TEST_BD_ARGS}"
pwd >> "${TMUX_THEME_TEST_BD_PWD}"
case "$*" in
  *"--label gc:nudge"*)
    printf '[{"id":"n1"},{"id":"n2"}]\n'
    ;;
  *"--type message"*)
    printf '[{"id":"m1"}]\n'
    ;;
  *)
    printf '[]\n'
    ;;
esac
STUB_BD

chmod +x "${TMPDIR}/bin/timeout" "${TMPDIR}/bin/bd"

TMUX_THEME_TEST_BD_ARGS="${TMPDIR}/bd.args"
TMUX_THEME_TEST_BD_PWD="${TMPDIR}/bd.pwd"
export TMUX_THEME_TEST_BD_ARGS
export TMUX_THEME_TEST_BD_PWD
mkdir -p "${TMPDIR}/city"
status_output="$(PATH="${TMPDIR}/bin:${PATH}" "${ROOT}/scripts/status-line.sh" ora_gascity.mayor "${TMPDIR}/city")"
assert_eq "ora_gascity.mayor | 🪝 2 | 📬 1" "${status_output}" "status-line renders hook and mail badges"

grep -F -- '--label gc:nudge --status open --metadata-field agent=ora_gascity.mayor --json --limit 0' "${TMUX_THEME_TEST_BD_ARGS}" >/dev/null \
  || fail "status-line should query hook nudges through bd"
grep -F -- '--type message --status open --assignee ora_gascity.mayor --json --limit 0' "${TMUX_THEME_TEST_BD_ARGS}" >/dev/null \
  || fail "status-line should query unread mail through bd"
grep -Fx "${TMPDIR}/city" "${TMUX_THEME_TEST_BD_PWD}" >/dev/null \
  || fail "status-line should run Beads queries from the provided city path"

cat >"${TMPDIR}/bin/jq" <<'STUB_JQ_FAIL'
#!/bin/sh
exit 1
STUB_JQ_FAIL
chmod +x "${TMPDIR}/bin/jq"
fallback_output="$(PATH="${TMPDIR}/bin:${PATH}" "${ROOT}/scripts/status-line.sh" ora_gascity.mayor)"
assert_eq "ora_gascity.mayor" "${fallback_output}" "status-line suppresses badges when JSON count fails"
rm -f "${TMPDIR}/bin/jq"

cat >"${TMPDIR}/bin/tmux" <<'STUB_TMUX_IDEMPOTENT'
#!/bin/sh
case "$*" in
  *"list-keys -T prefix n"*)
    printf "%s\n" "bind-key -T prefix n if-shell \"tmux -L city show-environment -t '#{session_name}' GC_AGENT >/dev/null 2>&1\" \"run-shell '/tmp/tmux-theme/scripts/cycle.sh next #{session_name} #{client_tty}'\" next-window"
    ;;
  *"bind-key"*)
    printf '%s\n' "$*" >> "${TMUX_THEME_TEST_TMUX_BINDS}"
    ;;
esac
STUB_TMUX_IDEMPOTENT
chmod +x "${TMPDIR}/bin/tmux"

TMUX_THEME_TEST_TMUX_BINDS="${TMPDIR}/tmux.binds"
export TMUX_THEME_TEST_TMUX_BINDS
PATH="${TMPDIR}/bin:${PATH}" "${ROOT}/scripts/bind-key.sh" n "run-shell '/tmp/tmux-theme/scripts/cycle.sh next #{session_name} #{client_tty}'"
[[ ! -s "${TMUX_THEME_TEST_TMUX_BINDS}" ]] || fail "bind-key should not wrap an existing theme run-shell binding"

cat >"${TMPDIR}/bin/tmux" <<'STUB_TMUX_BIND'
#!/bin/sh
case "$*" in
  *"list-keys -T prefix x"*)
    printf "%s\n" "bind-key -T prefix x display-message fallback"
    ;;
  *"bind-key"*)
    printf '%s\n' "$*" >> "${TMUX_THEME_TEST_TMUX_BINDS}"
    ;;
esac
STUB_TMUX_BIND
chmod +x "${TMPDIR}/bin/tmux"

: >"${TMUX_THEME_TEST_TMUX_BINDS}"
PATH="${TMPDIR}/bin:${PATH}" "${ROOT}/scripts/bind-key.sh" x "run-shell '/tmp/tmux-theme/scripts/agent-menu.sh #{client_tty}'"
grep -F 'bind-key -T prefix x if-shell' "${TMUX_THEME_TEST_TMUX_BINDS}" >/dev/null \
  || fail "bind-key should install a theme binding when no theme binding exists"

printf 'tmux-theme-script-tests=passed\n'
