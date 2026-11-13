#!/bin/bash
# codex-infisical-shim.sh — start a Codex session with an Infisical machine
# identity token in its environment, then exec the real codex.
#
# Built to be a Gas City provider `command`. An agent's `env` map is static and
# `pre_start` runs in its own process, so a provider command wrapper is the one
# city-side place a freshly minted value can enter the session environment.
#
# INSTALL (the city half; this pack does not sync assets/scripts anywhere):
#
#   mkdir -p "$CITY/.gc/shims/codex-astra"
#   install -m 0755 path/to/gascity/assets/scripts/codex-infisical-shim.sh \
#     "$CITY/.gc/shims/codex-astra/codex"
#   # optional per-city settings, beside the shim, named <shim>.env:
#   cat > "$CITY/.gc/shims/codex-astra/codex.env" <<'EOF'
#   CODEX_SHIM_PATH_PREPEND=/abs/path/to/city/.gc/shims/toolchain
#   CODEX_SHIM_EXEC=npx -y @openai/codex@0.153.3
#   EOF
#
#   # city.toml — the provider runs the shim; the role agents select it.
#   [providers.codex-astra]
#   base = "builtin:codex"
#   command = "/abs/path/to/city/.gc/shims/codex-astra/codex"
#   resume_command = "/abs/path/to/city/.gc/shims/codex-astra/codex resume {{.SessionKey}}"
#
#   # agents/<role>/agent.toml — one per rig
#   provider = "codex-astra"
#   [env]
#   INFISICAL_PROJECT_ID = "<project id, not a secret>"
#
#   # verify the installed copy is this file at the installed pin (a wake
#   # checks it): record the canonical md5 once (the extraction must succeed
#   # before anything is hashed), compare the installed file to that literal,
#   # so a missing file, a bad pin or a missing md5 tool fails the check.
#   canonical=$(mktemp) && git -C path/to/gascity-packs show <pin>:gascity/assets/scripts/codex-infisical-shim.sh > "$canonical" && md5 -q "$canonical"
#   test "$(md5 -q "$CITY/.gc/shims/codex-astra/codex")" = <that md5>
#
# Inputs (a variable present in the environment, even empty, wins over
# <shim>.env; the file is plain KEY=VALUE lines, never evaluated by a shell;
# unknown keys are ignored with a WARN; a blank value means "not set"):
#   CODEX_SHIM_PATH_PREPEND  colon-separated directories put first on PATH, so
#                            the session and every child (git hooks included)
#                            resolve the city's toolchain wrappers.
#   CODEX_SHIM_EXEC          the command line that runs the real codex (split on
#                            whitespace, no quoting), for a pinned build such as
#                            `npx -y @openai/codex@0.153.3`. Default: `codex`
#                            resolved from PATH with the shim's own directory
#                            removed.
#   HOME                     token.sh is read from $HOME/.config/infisical-agent/.
#
# Contract:
#   * Fail-open token. If INFISICAL_TOKEN is unset or empty and
#     $HOME/.config/infisical-agent/token.sh is readable, the shim sources it in
#     a subshell whose stdout and stderr are /dev/null for its whole lifetime
#     (traces and EXIT traps included) and carries over exactly one value, the
#     INFISICAL_TOKEN it exported, through a dedicated descriptor; the helper's
#     other exports, an `exit` in it, or a `set --` in it cannot reach the shim.
#     A missing token.sh is silent; a helper that fails or leaves the token
#     empty leaves INFISICAL_TOKEN unset and prints one WARN on stderr. The
#     exec happens either way. Nothing the helper prints reaches the session
#     output.
#   * A non-empty INFISICAL_TOKEN is kept as is; token.sh is not sourced.
#   * argv reaches the real codex intact, in order, nothing added or dropped.
#   * The shim never execs itself. It locates itself with shell builtins only
#     and refuses to run (exit 127) when it cannot; every PATH entry that is
#     its own directory (same inode, so symlinked, relative or doubled-slash
#     spellings count) is removed before the lookup (the child's PATH is the
#     pruned one, empty entries kept; when nothing survives PATH becomes
#     /dev/null, never the empty string bash reads as the current directory).
#     The exec target is the executable FILE `type -P` finds (an exported
#     function or alias of the same name is ignored), it is refused when it is
#     the shim file itself, and that checked path is what runs, with argv[0]
#     kept. No codex left on PATH is an error (exit 127), never a loop. No
#     external utility is needed for any of this, and CDPATH has no effect.
#   * Nothing else in the environment is changed: PATH (prepend + prune) and
#     INFISICAL_TOKEN are the only writes; the shim's own variables carry the
#     cis_ prefix, are initialized before use (an inherited cis_ export is not
#     configuration) and are unset before the exec, so an inherited export of
#     an ordinary name is never overwritten. Inherited shell options are kept:
#     xtrace is switched off before the token is touched and back on for the
#     exec (so SHELLOPTS reaches the child as it came) with the shim's own
#     trace lines discarded on stdout and stderr alike (BASH_XTRACEFD=1 or 2
#     included), so a PS4 that expands the token prints nothing;
#     noglob and errexit are left as found (the lookups cannot trip errexit;
#     the 127 diagnostics still print).
#
# Relation to the copy this was extracted from (citadel, gp-e8r6, 2026-09-10):
# same fail-open semantics and the same helper; the PATH prepend and the pinned
# `npx` command line moved from hardcoded values into <shim>.env so one file
# installs on any city; the helper now runs in a subshell and only its token
# crosses over (the original sourced it in-process); the default exec target
# and the self-exec guard are new; the WARN prefix names this script.

# Inherited tracing (SHELLOPTS=xtrace) would print the token: off until the exec.
# The group's stdout and stderr are /dev/null so the lines that switch it off
# trace nowhere, whichever of the two BASH_XTRACEFD names.
{
  cis_xtrace=0
  case $- in *x*) cis_xtrace=1; set +x ;; esac
} >/dev/null 2>&1
cis_noglob=0
case $- in *f*) cis_noglob=1 ;; esac

cis_die() {
  echo "codex-infisical-shim: ERROR $1" >&2
  exit 127
}

# --- locate self with builtins only ---------------------------------------------
cis_self=$0
case $cis_self in
  */*) ;;
  *) cis_self=$(builtin type -P -- "$cis_self" 2>/dev/null || :) ;;
esac
[ -n "$cis_self" ] || cis_die "cannot locate the shim itself from \$0='$0'; refusing to exec"
cis_self_dir=${cis_self%/*}
[ "$cis_self_dir" != "$cis_self" ] || cis_self_dir=.
[ -n "$cis_self_dir" ] || cis_self_dir=/
cis_self_dir=$(unset CDPATH; cd -P -- "$cis_self_dir" >/dev/null 2>&1 && pwd -P) \
  || cis_die "cannot resolve the shim's directory from '$cis_self'; refusing to exec"
cis_self_file="$cis_self_dir/${cis_self##*/}"
[ -e "$cis_self_file" ] || cis_die "the shim does not exist at '$cis_self_file'; refusing to exec"

# --- settings: environment (presence wins), then <shim>.env ----------------------
cis_sidecar="$cis_self_file.env"
cis_prepend=
cis_exec=
if [ -r "$cis_sidecar" ]; then
  while IFS= read -r cis_line || [ -n "$cis_line" ]; do
    case $cis_line in ''|'#'*) continue ;; esac
    case $cis_line in
      *=*) ;;
      *) echo "codex-infisical-shim: WARN ignoring line without '=' in $cis_sidecar" >&2; continue ;;
    esac
    cis_key=${cis_line%%=*}
    cis_val=${cis_line#*=}
    case $cis_val in
      \"*\") cis_val=${cis_val#\"}; cis_val=${cis_val%\"} ;;
      \'*\') cis_val=${cis_val#\'}; cis_val=${cis_val%\'} ;;
    esac
    case $cis_key in
      CODEX_SHIM_PATH_PREPEND) [ -n "${CODEX_SHIM_PATH_PREPEND+x}" ] || cis_prepend=$cis_val ;;
      CODEX_SHIM_EXEC) [ -n "${CODEX_SHIM_EXEC+x}" ] || cis_exec=$cis_val ;;
      *) echo "codex-infisical-shim: WARN ignoring unknown key $cis_key in $cis_sidecar" >&2 ;;
    esac
  done < "$cis_sidecar"
fi
[ -z "${CODEX_SHIM_PATH_PREPEND+x}" ] || cis_prepend=$CODEX_SHIM_PATH_PREPEND
[ -z "${CODEX_SHIM_EXEC+x}" ] || cis_exec=$CODEX_SHIM_EXEC

# --- PATH: prepend the city's toolchain, then remove the shim's own directory ---
if [ -n "${cis_prepend:-}" ]; then
  PATH="$cis_prepend:$PATH"
fi
cis_rest=$PATH
cis_pruned=
cis_first=1
while :; do
  case $cis_rest in
    *:*) cis_entry=${cis_rest%%:*}; cis_rest=${cis_rest#*:}; cis_more=1 ;;
    *) cis_entry=$cis_rest; cis_more=0 ;;
  esac
  if ! [ "${cis_entry:-.}" -ef "$cis_self_dir" ]; then
    if [ "$cis_first" = 1 ]; then
      cis_pruned=$cis_entry
      cis_first=0
    else
      cis_pruned="$cis_pruned:$cis_entry"
    fi
  fi
  [ "$cis_more" = 1 ] || break
done
if [ "$cis_first" = 1 ]; then
  cis_pruned=/dev/null
fi
PATH=$cis_pruned
export PATH

# --- Infisical machine identity, fail-open, helper isolated in a subshell --------
cis_token_sh="${HOME:-}/.config/infisical-agent/token.sh"
if [ -z "${INFISICAL_TOKEN:-}" ] && [ -n "${HOME:-}" ] && [ -r "$cis_token_sh" ]; then
  # The subshell's stdout and stderr are /dev/null for its whole lifetime, so a
  # trace or an EXIT trap in the helper cannot print; the token leaves through
  # descriptor 3, the capture.
  # shellcheck disable=SC1090
  if cis_token=$( ( exec 3>&1 >/dev/null 2>&1; . "$cis_token_sh" && set +x && builtin printf '%s' "${INFISICAL_TOKEN-}" >&3 ) ) \
     && [ -n "$cis_token" ]; then
    INFISICAL_TOKEN=$cis_token
    export INFISICAL_TOKEN
  else
    unset INFISICAL_TOKEN
    echo "codex-infisical-shim: WARN Infisical machine-identity login failed; INFISICAL_TOKEN unset" >&2
  fi
  unset cis_token
fi

# --- exec the real codex --------------------------------------------------------
set -f
# shellcheck disable=SC2206
cis_words=(${cis_exec:-})
[ "$cis_noglob" = 1 ] || set +f
if [ "${#cis_words[@]}" -gt 0 ]; then
  set -- "${cis_words[@]}" "$@"
else
  set -- codex "$@"
fi
# The executable file, never a function, alias or builtin of that name.
cis_target=$(builtin type -P -- "$1" 2>/dev/null || :)
[ -n "$cis_target" ] \
  || cis_die "no '$1' on PATH after removing the shim's directory ($cis_self_dir); set CODEX_SHIM_EXEC or install codex"
if [ "$cis_target" -ef "$cis_self_file" ]; then
  cis_die "'$1' resolves to the shim itself ($cis_self_file); refusing to exec"
fi
# $1 = restore xtrace, $2 = the checked file, $3 = argv[0], the rest = codex's argv.
set -- "$cis_xtrace" "$cis_target" "$@"
unset cis_self cis_self_dir cis_self_file cis_sidecar cis_line cis_key cis_val cis_prepend cis_exec \
  cis_rest cis_pruned cis_first cis_entry cis_more cis_token_sh cis_token cis_words cis_target cis_xtrace cis_noglob
unset -f cis_die
if [ "$1" = 1 ]; then
  # Tracing back on for the child; the shim's own two trace lines go to
  # /dev/null on stdout and stderr alike, while the child gets the real
  # descriptors back (stderr saved on fd 3, stdout on fd 4).
  { set -x; exec -a "$3" "$2" "${@:4}" >&4 2>&3 3>&- 4>&-; } 3>&2 4>&1 >/dev/null 2>&1
fi
exec -a "$3" "$2" "${@:4}"
