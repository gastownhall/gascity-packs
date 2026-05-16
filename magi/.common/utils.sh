#!/usr/bin/env bash
#
# magi/.common/utils.sh - Generic pack-local helpers for magi
# ==============================================================================
# Pack-local helpers that every commands/<verb>.sh and doctor/check-*.sh source.
# Sources colors.sh + logging.sh + bd_subprocess.sh in dependency order. Exposes
# small path-resolution helpers that read $GC_PACK_DIR and $GC_CITY_PATH from
# the Gas City harness environment contract.
#
# USAGE:
#   COMMON_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
#   source "${COMMON_DIR}/utils.sh"
#   magi_preflight_env
#   magi_pack_root
#   magi_city_runtime_dir
#   magi_log_path doctor lmstudio
#
# EXPORTED FUNCTIONS:
#   magi_preflight_env       Asserts GC_PACK_DIR + GC_CITY_PATH; rc 1 on miss
#   magi_pack_root           Echoes $GC_PACK_DIR
#   magi_city_runtime_dir    Echoes "${GC_CITY_PATH}/.gc/runtime/packs/magi"
#   magi_log_path verb [tgt] Echoes per-verb log path under runtime/logs
#
# DEPENDENCIES:
#   Internal: colors.sh, logging.sh, bd_subprocess.sh
#   External: date
# ==============================================================================
set -Eeuo pipefail
[[ -n "${_SOURCED_MAGI_UTILS_SH:-}" ]] && return 0
readonly _SOURCED_MAGI_UTILS_SH=1
_MAGI_UTILS_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly _MAGI_UTILS_DIR
[[ -f "${_MAGI_UTILS_DIR}/colors.sh" ]] || { printf 'ERROR: magi/.common/colors.sh missing under %s\n' "${_MAGI_UTILS_DIR}" >&2; return 1; }
source "${_MAGI_UTILS_DIR}/colors.sh"
[[ -f "${_MAGI_UTILS_DIR}/logging.sh" ]] || { printf 'ERROR: magi/.common/logging.sh missing under %s\n' "${_MAGI_UTILS_DIR}" >&2; return 1; }
source "${_MAGI_UTILS_DIR}/logging.sh"
[[ -f "${_MAGI_UTILS_DIR}/bd_subprocess.sh" ]] || { printf 'ERROR: magi/.common/bd_subprocess.sh missing under %s\n' "${_MAGI_UTILS_DIR}" >&2; return 1; }
source "${_MAGI_UTILS_DIR}/bd_subprocess.sh"
magi_preflight_env() {
    local errors=0
    [[ -n "${GC_PACK_DIR:-}" ]] || { log_error "GC_PACK_DIR not set (missing Gas City pack context)"; errors=$((errors + 1)); }
    [[ -n "${GC_CITY_PATH:-}" ]] || { log_error "GC_CITY_PATH not set (missing Gas City pack context)"; errors=$((errors + 1)); }
    [[ "${errors}" == "0" ]] || return 1
    return 0
}
magi_pack_root() {
    [[ -n "${GC_PACK_DIR:-}" ]] || { log_error "magi_pack_root: GC_PACK_DIR not set"; return 1; }
    printf '%s' "${GC_PACK_DIR}"
}
magi_city_runtime_dir() {
    [[ -n "${GC_CITY_PATH:-}" ]] || { log_error "magi_city_runtime_dir: GC_CITY_PATH not set"; return 1; }
    printf '%s' "${GC_CITY_PATH}/.gc/runtime/packs/magi"
}
magi_log_path() {
    local verb="${1:-}"
    local target="${2:-}"
    [[ -n "${verb}" ]] || { log_error "magi_log_path: verb argument required"; return 1; }
    [[ -n "${GC_CITY_PATH:-}" ]] || { log_error "magi_log_path: GC_CITY_PATH not set"; return 1; }
    local stamp
    stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
    local logs_dir="${GC_CITY_PATH}/.gc/runtime/packs/magi/logs"
    mkdir -p "${logs_dir}"
    [[ -z "${target}" ]] && printf '%s/%s-%s.log' "${logs_dir}" "${verb}" "${stamp}" || printf '%s/%s-%s-%s.log' "${logs_dir}" "${verb}" "${target}" "${stamp}"
}