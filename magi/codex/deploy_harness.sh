#!/usr/bin/env bash
#
# deploy_harness.sh - install the codex_dist harness into ~/.codex/
# ==============================================================================
# Idempotent installer for the bundled Codex enforcement harness. It copies the
# self-contained enforcement tree, enables native Codex hooks, installs the
# execpolicy rules, writes runtime environment defaults, and backs up files that
# it modifies.
#
# USAGE:
#   ./deploy_harness.sh
#   ./deploy_harness.sh --target=DIR
#   ./deploy_harness.sh --dry-run
#   ./deploy_harness.sh --non-interactive
#   ./deploy_harness.sh --skip-prereqs
#
# ENVIRONMENT VARIABLES:
#   CODEX_HOME                  Target Codex home when --target is omitted.
#   INSTALL_CODEX_HOOKS         1 to install hooks.json entries.
#   INSTALL_EXEC_POLICY         1 to install native execpolicy rules.
#   INSTALL_LM_STUDIO           1 to enable Stop-hook quality review.
#   LM_STUDIO_HOST              OpenAI-compatible reviewer host.
#   LM_STUDIO_PORT              OpenAI-compatible reviewer port.
#   LM_STUDIO_MODEL             Reviewer model name.
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
PACK_DIR="$(cd -P -- "${SCRIPT_DIR}/.." && pwd)"
readonly PACK_DIR
readonly HARNESS_DIR="${SCRIPT_DIR}/harness"
readonly ENV_FILE="${PACK_DIR}/.env"
TS="$(date '+%Y%m%d-%H%M%S')"
readonly TS

DEPLOY_TARGET="${CODEX_HOME:-${HOME}/.codex}"
DRY_RUN=0
NON_INTERACTIVE=0
SKIP_PREREQS=0

for arg in "$@"; do
    case "${arg}" in
        --target=*) DEPLOY_TARGET="${arg#--target=}" ;;
        --dry-run) DRY_RUN=1 ;;
        --non-interactive) NON_INTERACTIVE=1 ;;
        --skip-prereqs) SKIP_PREREQS=1 ;;
        -h|--help)
            sed -n '2,35p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            printf 'unknown argument: %s\n' "${arg}" >&2
            exit 1
            ;;
    esac
done

readonly DEPLOY_TARGET DRY_RUN NON_INTERACTIVE SKIP_PREREQS
readonly SCRATCH_DIR="${SCRIPT_DIR}/.deploy_scratch"

if [[ -t 1 ]]; then
    readonly C_BOLD=$'\033[1m' C_DIM=$'\033[2m' C_RED=$'\033[31m' C_GREEN=$'\033[32m' C_YELLOW=$'\033[33m' C_BLUE=$'\033[34m' C_NC=$'\033[0m'
else
    readonly C_BOLD='' C_DIM='' C_RED='' C_GREEN='' C_YELLOW='' C_BLUE='' C_NC=''
fi

log() { printf '%b>%b %s\n' "${C_BLUE}" "${C_NC}" "$*"; }
ok() { printf '%bOK%b %s\n' "${C_GREEN}" "${C_NC}" "$*"; }
warn() { printf '%bWARN%b %s\n' "${C_YELLOW}" "${C_NC}" "$*" >&2; }
fatal() { printf '%bERROR%b %s\n' "${C_RED}" "${C_NC}" "$*" >&2; exit 1; }
section() { printf '\n%b%s%b\n' "${C_BOLD}" "$*" "${C_NC}"; }

run_mkdir() {
    local path="$1"
    if [[ "${DRY_RUN}" == "1" ]]; then
        printf '%b[dry-run]%b mkdir -p %s\n' "${C_DIM}" "${C_NC}" "${path}"
    else
        mkdir -p "${path}"
    fi
}

run_cp() {
    local src="$1" dst="$2"
    if [[ "${DRY_RUN}" == "1" ]]; then
        printf '%b[dry-run]%b cp -a %s %s\n' "${C_DIM}" "${C_NC}" "${src}" "${dst}"
    else
        cp -a "${src}" "${dst}"
    fi
}

run_rsync() {
    local src="$1" dst="$2"
    if [[ "${DRY_RUN}" == "1" ]]; then
        printf '%b[dry-run]%b rsync -a --exclude=.DS_Store %s %s\n' "${C_DIM}" "${C_NC}" "${src}" "${dst}"
    else
        rsync -a --exclude='.DS_Store' "${src}" "${dst}"
    fi
}

scratch_file() {
    local name="$1"
    mkdir -p "${SCRATCH_DIR}"
    printf '%s/%s.%s' "${SCRATCH_DIR}" "${name}" "${TS}"
}

cleanup() {
    rm -rf "${SCRATCH_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

ask_yes_no() {
    local prompt="$1"
    local default="${2:-n}"
    local reply
    if [[ "${NON_INTERACTIVE}" == "1" ]]; then
        [[ "${default}" == "y" ]]
        return $?
    fi
    while true; do
        printf '%s [y/n] ' "${prompt}"
        read -r reply || reply="${default}"
        reply="${reply:-${default}}"
        case "${reply}" in
            [Yy]*) return 0 ;;
            [Nn]*) return 1 ;;
            *) printf 'answer y or n\n' ;;
        esac
    done
}

prompt_value() {
    local prompt="$1"
    local default="${2:-}"
    local reply
    if [[ "${NON_INTERACTIVE}" == "1" ]]; then
        printf '%s' "${default}"
        return 0
    fi
    if [[ -n "${default}" ]]; then
        printf '%s [%s] ' "${prompt}" "${default}" >&2
    else
        printf '%s ' "${prompt}" >&2
    fi
    read -r reply || reply=""
    printf '%s' "${reply:-${default}}"
}

load_env() {
    if [[ "${MAGI_PACK_ENV_LOADED:-0}" == "1" ]]; then
        log "pack .env already loaded by magi"
        return 0
    fi
    if [[ -f "${ENV_FILE}" ]]; then
        log "loading ${ENV_FILE}"
        set -a
        # shellcheck disable=SC1090
        source "${ENV_FILE}"
        set +a
    else
        log ".env not found; using prompts/defaults"
    fi
}

resolve_flag() {
    local var_name="$1"
    local prompt="$2"
    local default="${3:-1}"
    local current="${!var_name:-}"
    if [[ -n "${current}" ]]; then
        printf '%s' "${current}"
        return 0
    fi
    if [[ "${NON_INTERACTIVE}" == "1" ]]; then
        printf '%s' "${default}"
        return 0
    fi
    if ask_yes_no "${prompt}" "$( [[ "${default}" == "1" ]] && printf 'y' || printf 'n' )"; then
        printf '1'
    else
        printf '0'
    fi
}

resolve_value() {
    local var_name="$1"
    local prompt="$2"
    local default="${3:-}"
    local current="${!var_name:-}"
    if [[ -n "${current}" ]]; then
        printf '%s' "${current}"
        return 0
    fi
    prompt_value "${prompt}" "${default}"
}

check_prereqs() {
    section "Prerequisites"
    local missing=0
    local cmd
    for cmd in jq rsync sed awk find chmod; do
        if command -v "${cmd}" >/dev/null 2>&1; then
            ok "${cmd} found"
        else
            warn "${cmd} missing"
            missing=1
        fi
    done
    [[ "${missing}" == "0" ]] || fatal "install missing prerequisites and rerun"
}

backup_existing() {
    local path="$1"
    [[ -e "${path}" ]] || return 0
    local backup="${path}.pre-codex-harness-${TS}.bak"
    run_cp "${path}" "${backup}"
    log "backed up ${path} -> ${backup}"
}

backup_deploy_target() {
    [[ -d "${DEPLOY_TARGET}" ]] || { log "deploy target does not yet exist; skipping folder backup"; return 0; }
    local parent base ts_short backup_path
    parent="$(dirname "${DEPLOY_TARGET}")"
    base="$(basename "${DEPLOY_TARGET}")"
    ts_short="$(date '+%y%m%d-%H%M%S')"
    backup_path="${parent}/${base}_backup-${ts_short}"
    if [[ -e "${backup_path}" ]]; then
        warn "folder backup path already exists: ${backup_path}; skipping"
        return 0
    fi
    run_cp "${DEPLOY_TARGET}" "${backup_path}"
    ok "backed up ${DEPLOY_TARGET} -> ${backup_path}"
}

sed_escape() {
    printf '%s' "$1" | sed -e 's|[\/&]|\\&|g'
}

substitute_codex_home() {
    local src="$1"
    local dst="$2"
    local escaped_codex_home
    escaped_codex_home="$(sed_escape "${DEPLOY_TARGET}")"
    if [[ "${DRY_RUN}" == "1" ]]; then
        printf '%b[dry-run]%b substitute __CODEX_HOME__ in %s -> %s\n' "${C_DIM}" "${C_NC}" "${src}" "${dst}"
    else
        sed "s|__CODEX_HOME__|${escaped_codex_home}|g" "${src}" > "${dst}"
    fi
}

# shellcheck disable=SC2016 # jq program uses $a/$b inside single-quoted source.
JQ_DEEP_MERGE='
def dedup_stable:
  reduce .[] as $x ([]; if any(.[]; . == $x) then . else . + [$x] end);
def merge(a; b):
  if (a|type) == "object" and (b|type) == "object" then
    reduce ((a|keys_unsorted) + (b|keys_unsorted) | dedup_stable)[] as $k
      ({}; .[$k] = (
        if (a[$k]|type) == "object" and (b[$k]|type) == "object" then merge(a[$k]; b[$k])
        elif (a[$k]|type) == "array" and (b[$k]|type) == "array" then ((a[$k] + b[$k]) | dedup_stable)
        elif b|has($k) then b[$k]
        else a[$k]
        end
      ))
  elif (a|type) == "array" and (b|type) == "array" then ((a + b) | dedup_stable)
  else b
  end;
merge($a; $b)
'

deep_merge_json() {
    local existing="$1"
    local incoming="$2"
    local output="$3"
    local merged
    merged="$(scratch_file "json-merge")"
    if [[ ! -f "${existing}" ]]; then
        run_cp "${incoming}" "${output}"
        return 0
    fi
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "[dry-run] would deep-merge ${existing} <- ${incoming}"
        return 0
    fi
    jq -n --slurpfile a "${existing}" --slurpfile b "${incoming}" \
        "${JQ_DEEP_MERGE} | (\$a[0] as \$a | \$b[0] as \$b | merge(\$a; \$b))" \
        > "${merged}"
    mv -f "${merged}" "${output}"
}

ensure_codex_hooks_enabled() {
    local config="${DEPLOY_TARGET}/config.toml"
    local updated
    run_mkdir "${DEPLOY_TARGET}"
    if [[ ! -f "${config}" ]]; then
        if [[ "${DRY_RUN}" == "1" ]]; then
            log "[dry-run] would create ${config}"
        else
            cp "${HARNESS_DIR}/config/config.toml.snippet" "${config}"
        fi
        ok "enabled codex_hooks in config.toml"
        return 0
    fi

    backup_existing "${config}"
    updated="$(scratch_file "config.toml")"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "[dry-run] would set [features].codex_hooks = true in ${config}"
        return 0
    fi
    awk '
        BEGIN { in_features = 0; seen_features = 0; seen_hook = 0 }
        /^\[features\][[:space:]]*$/ {
            if (in_features && !seen_hook) print "codex_hooks = true"
            in_features = 1
            seen_features = 1
            print
            next
        }
        /^\[[^]]+\][[:space:]]*$/ {
            if (in_features && !seen_hook) print "codex_hooks = true"
            in_features = 0
            print
            next
        }
        in_features && /^[[:space:]]*codex_hooks[[:space:]]*=/ {
            print "codex_hooks = true"
            seen_hook = 1
            next
        }
        { print }
        END {
            if (!seen_features) {
                print ""
                print "[features]"
                print "codex_hooks = true"
            } else if (in_features && !seen_hook) {
                print "codex_hooks = true"
            }
        }
    ' "${config}" > "${updated}"
    mv -f "${updated}" "${config}"
    ok "enabled codex_hooks in config.toml"
}

install_hooks_json() {
    [[ "${INSTALL_CODEX_HOOKS_RESOLVED}" == "1" ]] || { log "Codex hooks disabled; skipping hooks.json"; return 0; }
    local target="${DEPLOY_TARGET}/hooks.json"
    local incoming
    incoming="$(scratch_file "hooks.json")"
    run_mkdir "${DEPLOY_TARGET}"
    backup_existing "${target}"
    substitute_codex_home "${HARNESS_DIR}/hooks.json" "${incoming}"
    deep_merge_json "${target}" "${incoming}" "${target}"
    ok "installed hooks.json entries"
}

install_exec_policy() {
    [[ "${INSTALL_EXEC_POLICY_RESOLVED}" == "1" ]] || { log "execpolicy disabled; skipping native rules"; return 0; }
    local rules_dir="${DEPLOY_TARGET}/rules"
    local target="${rules_dir}/default.rules"
    local cleaned
    run_mkdir "${rules_dir}"
    backup_existing "${target}"
    cleaned="$(scratch_file "default.rules")"
    if [[ "${DRY_RUN}" == "1" ]]; then
        log "[dry-run] would append Codex enforcement rules to ${target}"
        return 0
    fi
    if [[ -f "${target}" ]]; then
        awk '
            /^# BEGIN CODEX_DIST ENFORCEMENT RULES$/ { skip = 1; next }
            /^# END CODEX_DIST ENFORCEMENT RULES$/ { skip = 0; next }
            skip == 0 { print }
        ' "${target}" > "${cleaned}"
    else
        : > "${cleaned}"
    fi
    {
        sed -n '1,$p' "${cleaned}"
        printf '\n# BEGIN CODEX_DIST ENFORCEMENT RULES\n'
        sed -n '1,$p' "${HARNESS_DIR}/rules/codex-enforcement.rules"
        printf '# END CODEX_DIST ENFORCEMENT RULES\n'
    } > "${target}"
    ok "installed native execpolicy rules"
}

write_runtime_env() {
    local env_target="${DEPLOY_TARGET}/enforcement/env"
    [[ "${DRY_RUN}" == "1" ]] && { log "[dry-run] would write ${env_target}"; return 0; }
    backup_existing "${env_target}"
    {
        printf '# Generated by codex_dist deploy_harness.sh on %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
        if [[ "${INSTALL_LM_STUDIO_RESOLVED}" == "1" ]]; then
            printf 'CODEX_SKIP_QUALITY_CHECK=0\n'
        else
            printf 'CODEX_SKIP_QUALITY_CHECK=1\n'
        fi
        printf 'CODEX_MAX_QUALITY_ATTEMPTS=%s\n' "${CODEX_MAX_QUALITY_ATTEMPTS_RESOLVED}"
        printf 'CODEX_TURN_CONTENT_LIMIT=%s\n' "${CODEX_TURN_CONTENT_LIMIT_RESOLVED}"
        printf 'LM_STUDIO_HOST=%s\n' "${LM_STUDIO_HOST_RESOLVED}"
        printf 'LM_STUDIO_PORT=%s\n' "${LM_STUDIO_PORT_RESOLVED}"
        printf 'LM_STUDIO_MODEL=%s\n' "${LM_STUDIO_MODEL_RESOLVED}"
        printf 'LM_STUDIO_CONNECT_TIMEOUT=%s\n' "${LM_STUDIO_CONNECT_TIMEOUT_RESOLVED}"
        printf 'LM_STUDIO_MAX_TIME=%s\n' "${LM_STUDIO_MAX_TIME_RESOLVED}"
    } > "${env_target}"
    chmod 600 "${env_target}" 2>/dev/null || true
    ok "wrote enforcement runtime env"
}

copy_enforcement_tree() {
    section "Copying enforcement harness"
    run_mkdir "${DEPLOY_TARGET}/enforcement"
    run_rsync "${HARNESS_DIR}/enforcement/" "${DEPLOY_TARGET}/enforcement/"
    if [[ "${DRY_RUN}" == "0" ]]; then
        chmod +x "${DEPLOY_TARGET}/enforcement/bin/"*.sh 2>/dev/null || true
        chmod +x "${DEPLOY_TARGET}/enforcement/tests/run-fixtures.sh" 2>/dev/null || true
    fi
    ok "copied enforcement/"
}

main() {
    section "codex_dist deploy_harness"
    log "harness source: ${HARNESS_DIR}"
    log "deploy target:  ${DEPLOY_TARGET}"
    [[ "${DRY_RUN}" == "1" ]] && warn "DRY RUN - no files will be modified"
    [[ -d "${HARNESS_DIR}" ]] || fatal "harness directory not found: ${HARNESS_DIR}"

    load_env

    section "Feature flags"
    INSTALL_CODEX_HOOKS_RESOLVED="$(resolve_flag INSTALL_CODEX_HOOKS 'install Codex hooks?' 1)"
    INSTALL_EXEC_POLICY_RESOLVED="$(resolve_flag INSTALL_EXEC_POLICY 'install native Codex execpolicy rules?' 1)"
    INSTALL_LM_STUDIO_RESOLVED="$(resolve_flag INSTALL_LM_STUDIO 'enable LM Studio Stop quality review?' 1)"
    log "Codex hooks: ${INSTALL_CODEX_HOOKS_RESOLVED}"
    log "execpolicy:  ${INSTALL_EXEC_POLICY_RESOLVED}"
    log "LM Studio:   ${INSTALL_LM_STUDIO_RESOLVED}"

    section "Runtime values"
    LM_STUDIO_HOST_RESOLVED="$(resolve_value LM_STUDIO_HOST 'LM Studio host:' 'localhost')"
    LM_STUDIO_PORT_RESOLVED="$(resolve_value LM_STUDIO_PORT 'LM Studio port:' '1234')"
    LM_STUDIO_MODEL_RESOLVED="$(resolve_value LM_STUDIO_MODEL 'LM Studio model:' 'nvidia/nemotron-3-super')"
    LM_STUDIO_CONNECT_TIMEOUT_RESOLVED="$(resolve_value LM_STUDIO_CONNECT_TIMEOUT 'LM Studio connect timeout seconds:' '3')"
    LM_STUDIO_MAX_TIME_RESOLVED="$(resolve_value LM_STUDIO_MAX_TIME 'LM Studio request timeout seconds:' '75')"
    CODEX_MAX_QUALITY_ATTEMPTS_RESOLVED="$(resolve_value CODEX_MAX_QUALITY_ATTEMPTS 'Stop quality max attempts:' '3')"
    CODEX_TURN_CONTENT_LIMIT_RESOLVED="$(resolve_value CODEX_TURN_CONTENT_LIMIT 'Stop quality transcript character limit:' '70000')"

    [[ "${SKIP_PREREQS}" == "1" ]] || check_prereqs

    section "Backups"
    backup_deploy_target

    section "Install"
    run_mkdir "${DEPLOY_TARGET}"
    copy_enforcement_tree
    write_runtime_env
    ensure_codex_hooks_enabled
    install_hooks_json
    install_exec_policy

    section "Validation"
    if [[ "${DRY_RUN}" == "0" ]]; then
        jq empty "${DEPLOY_TARGET}/hooks.json" "${DEPLOY_TARGET}/enforcement/rules/enforcement_rules.json"
        bash -n "${DEPLOY_TARGET}/enforcement/bin/common.sh" "${DEPLOY_TARGET}/enforcement/bin/codex-hook.sh" "${DEPLOY_TARGET}/enforcement/tests/run-fixtures.sh"
        ok "installed JSON and Bash syntax validated"
    else
        log "[dry-run] skipped installed-file validation"
    fi

    section "Done"
    ok "Codex harness deployed to ${DEPLOY_TARGET}"
    log "restart Codex so codex_hooks and hooks.json are loaded"
    log "run ${DEPLOY_TARGET}/enforcement/tests/run-fixtures.sh to verify enforcement behavior"
}

main "$@"
