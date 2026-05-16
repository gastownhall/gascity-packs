#!/usr/bin/env bash
#
# Guideline Read-Tracking + Pre-Write Enforcement
# ==============================================================================
# Tracks guideline-file reads (Read tool / Bash cat) and gates Write/Edit on
# corresponding language guideline having been read this session.
#
# Authoritative format: XML under ${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/
# GSL and markdown mirrors live alongside; reads of any of the three count.
# ==============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
source "${SHARED_UTILS}/project-key.sh"
source "${SHARED_UTILS}/block-policy.sh"
INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // "unknown"')
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""')
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""')
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // "default"')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""')
resolve_project_paths "${CWD}"
block_policy_init
TRACKING_FILE="${PROJECT_TRACKING_DIR}/claude_guidelines_read_${SESSION_ID}"
TIMESTAMP_FILE="${PROJECT_TRACKING_DIR}/claude_guidelines_timestamp_${SESSION_ID}"
FIRED_FILE="${PROJECT_TRACKING_DIR}/claude_guidelines_fired_${SESSION_ID}"
already_fired_this_turn() {
    local key="$1"
    [[ -f "${FIRED_FILE}" ]] || return 1
    grep -qxE "^${key}$" "${FIRED_FILE}"
}
mark_fired_this_turn() {
    local key="$1"
    printf '%s\n' "${key}" >> "${FIRED_FILE}"
}
declare -A KEY_MAP=(
    [angular_guidelines]=angular
    [angular_js_guidelines]=angular_js
    [api_guidelines]=api
    [auth_guidelines]=auth
    [automation_principles]=automation
    [azure_variable_guidelines]=azure_variables
    [bash_guidelines]=bash
    [bicep_guidelines]=bicep
    [cicd_guidelines]=cicd
    [cosmosdb_guidelines]=cosmosdb
    [csharp_guidelines]=csharp
    [datadog_observability]=datadog
    [docker_guidelines]=docker
    [domain_infrastructure_guidelines]=domain_infrastructure
    [email_authentication_guidelines]=email_authentication
    [frontend_guidelines]=frontend
    [kafka_guidelines]=kafka
    [kubernetes_guidelines]=kubernetes
    [lxc_guidelines]=lxc
    [maven_guidelines]=maven
    [netlify_guidelines]=netlify
    [nginx_guidelines]=nginx
    [powerquery_guidelines]=powerquery
    [powershell_guidelines]=powershell
    [prohibited_behavior]=prohibited
    [python_guidelines]=python
    [rabbit_mq_guidelines]=rabbitmq
    [redis_guidelines]=redis
    [rust_guidelines]=rust
    [session_recording_guidelines]=session_recording
    [snowflake_guidelines]=snowflake
    [sql_guidelines]=sql
    [storage_and_messaging_principles]=storage_messaging
    [stripe_guidelines]=stripe
    [swift_guidelines]=swift
    [utilities_guidelines]=utilities
    [vue_nuxt_guidelines]=vue_nuxt
    [woocommerce_guidelines]=woocommerce
    [wordpress_guidelines]=wordpress
    [yew_guidelines]=yew
    [zenfolio_integration_guidelines]=zenfolio_integration
)
get_tracking_key_for_path() {
    local path="$1"
    case "$path" in
        */enforcement/guidelines/guideline_documents/xml/*.xml|\
        */enforcement/guidelines/guideline_documents/gsl/*.gsl|\
        */enforcement/guidelines/guideline_documents/markdown/*.md|\
        */guidelines/GSL/*.gsl|\
        */guidelines/markdown/*.md|\
        */guidelines/*.xml) ;;
        *) printf ''; return ;;
    esac
    local base="${path##*/}"
    base="${base%.*}"
    printf '%s' "${KEY_MAP[${base}]:-}"
}
get_language() {
    local path="$1"
    case "$path" in
        *.py) printf 'python' ;;
        *.sh|*.bash) printf 'bash' ;;
        *.cs|*.csproj) printf 'csharp' ;;
        *.rs) printf 'rust' ;;
        pom.xml|*.java) printf 'maven' ;;
        *.tsx|*.ts|*.jsx|*.js) printf 'frontend' ;;
        *.ps1|*.psm1) printf 'powershell' ;;
        *.swift) printf 'swift' ;;
        *.sql) printf 'sql' ;;
        *.bicep) printf 'bicep' ;;
        *.vue) printf 'vue_nuxt' ;;
        *.pq|*.pqm) printf 'powerquery' ;;
        *.php) printf 'wordpress' ;;
        Dockerfile*|*.dockerfile) printf 'docker' ;;
        *) printf 'unknown' ;;
    esac
}
xml_path_for() {
    local fname="$1"
    printf '%s/.claude/enforcement/guidelines/guideline_documents/xml/%s.xml' "${HOME}" "${fname}"
}
check_stale_guidelines() {
    [[ -f "$TIMESTAMP_FILE" ]] || return 0
    local last_read current_time time_diff
    last_read=$(cat "$TIMESTAMP_FILE")
    current_time=$(date +%s)
    time_diff=$((current_time - last_read))
    if (( time_diff > 3600 )); then
        printf '[%s] Guidelines stale after %s seconds, clearing tracking\n' \
            "$(date)" "${time_diff}" >> "${PROJECT_ENFORCEMENT_LOG}"
        rm -f "$TRACKING_FILE" "$TIMESTAMP_FILE" || true
    fi
}
check_rust_forbidden_content() {
    local content="$1"
    local filepath="$2"
    local errors=""
    test_pattern() {
        local pat="$1"
        local match
        match="$(printf '%s' "$content" | grep -E "${pat}" || true)"
        [[ -n "${match}" ]]
    }
    test_pattern '#!?\[allow\s*\(|#!?\[expect\s*\(' && errors+="  LINT SUPPRESSION: #[allow()] / #![allow()] / #[expect()] -- fix the root cause, never suppress\n"
    test_pattern '\bunsafe\s*(\{|fn\s|impl\s|trait\s)' && errors+="  UNSAFE CODE: unsafe{} / unsafe fn / unsafe impl / unsafe trait\n"
    test_pattern 'extern\s+"(C|C\+\+|system|stdcall|fastcall|win64|sysv64|aapcs|cdecl|Rust)"' && errors+="  EXTERN FFI: extern \"C\" / extern \"system\" / etc.\n"
    test_pattern '\bmem::transmute\b|\bstd::mem::transmute\b|\bMaybeUninit\b|\bManuallyDrop\b|\bstatic\s+mut\s' && errors+="  UNSAFE PRIMITIVES: mem::transmute / MaybeUninit / ManuallyDrop / static mut\n"
    test_pattern '\.unwrap\s*\(|\.expect\s*\(|\bpanic!\s*\(|\btodo!\s*\(|\bunimplemented!\s*\(|\bunreachable!\s*\(' && errors+="  PANIC PATTERNS: .unwrap() / .expect() / panic!() / todo!() / unimplemented!() / unreachable!()\n"
    test_pattern '\bdbg!\s*\(|\bprintln!\s*\(|\beprintln!\s*\(|\bprint!\s*\(' && errors+="  DEBUG MACROS: dbg!() / println!() / eprintln!() / print!() -- use tracing crate\n"
    test_pattern '(std::)?process::exit\s*\(|(std::)?thread::sleep\s*\(' && errors+="  RUNTIME BLOCKING: process::exit() / thread::sleep() -- use Result propagation / tokio::time::sleep\n"
    test_pattern '#!\[feature\s*\(' && errors+="  NIGHTLY FEATURES: #![feature(...)] -- stable Rust only\n"
    test_pattern '#!\[(no_std|no_main)\]' && errors+="  NO_STD/NO_MAIN: #![no_std] / #![no_main] -- application code requires std\n"
    test_pattern '#\[(panic_handler|global_allocator|alloc_error_handler)\]' && errors+="  SYSTEM HOOKS: #[panic_handler] / #[global_allocator] / #[alloc_error_handler]\n"
    test_pattern '#\[no_mangle\]|#\[export_name\s*=|#\[repr\s*\(\s*packed|#\[link\s*\(|#\[link_name\s*=|#\[link_ordinal\s*\(|#\[link_section\s*=|#\[used\]' && errors+="  ABI/LINKER: #[no_mangle] / #[export_name] / #[repr(packed)] / #[link*] / #[used]\n"
    test_pattern '#\[repr\s*\(\s*(C\b|transparent\b|align\s*\()' && errors+="  REPR LAYOUT: #[repr(C)] / #[repr(transparent)] / #[repr(align(...))] -- requires user authorization\n"
    test_pattern '#\[inline\s*\(\s*(always|never)\s*\)\]|#\[target_feature\s*\(|#\[naked\]|#\[cold\]|#\[instruction_set\s*\(|#\[track_caller\]' && errors+="  CODEGEN OVERRIDES: #[inline(always/never)] / #[target_feature] / #[naked] / #[cold] / #[track_caller]\n"
    test_pattern '#!?\[rustfmt::skip\]' && errors+="  FORMAT BYPASS: #[rustfmt::skip] -- format your code properly\n"
    test_pattern '#\[macro_use\]' && errors+="  MACRO POLLUTION: #[macro_use] -- use explicit macro imports\n"
    test_pattern '#!?\[cfg\s*\((?!test[,) ])|#!?\[cfg_attr\s*\(' && errors+="  CFG CONDITIONAL: #[cfg(...)] (non-test) / #[cfg_attr(...)] -- must be tested across all configurations\n"
    test_pattern '```\s*(ignore|no_run|compile_fail|should_panic)' && errors+="  DOCTEST ESCAPE: \`\`\`ignore / \`\`\`no_run / \`\`\`compile_fail / \`\`\`should_panic -- examples must compile\n"
    test_pattern '#\[windows_subsystem\s*=' && errors+="  WINDOWS_SUBSYSTEM: #[windows_subsystem=...]\n"
    test_pattern '#!?\[clippy::' && errors+="  CLIPPY INLINE: #[clippy::...] -- configure Clippy in Cargo.toml [lints], not inline\n"
    if [[ -n "$errors" ]]; then
        printf 'BLOCKED: Forbidden Rust patterns detected in %s:\n' "${filepath}" >&2
        printf '%b' "$errors" >&2
        printf '\n' >&2
        printf 'Fix the underlying issues -- do NOT silence them with pragmas or leave placeholder code.\n' >&2
        printf 'Refer to: %s (禁用属性&危险API section)\n' "$(xml_path_for rust_guidelines)" >&2
        exit 2
    fi
}
if [[ "$TOOL_NAME" == "Read" ]]; then
    KEY="$(get_tracking_key_for_path "$FILE_PATH")"
    if [[ -n "${KEY}" ]]; then
        printf '%s\n' "$KEY" >> "$TRACKING_FILE"
        date +%s > "$TIMESTAMP_FILE"
    fi
fi
if [[ "$TOOL_NAME" == "Bash" ]]; then
    GUIDELINE_BYPASS="$(printf '%s' "$COMMAND" | grep -E '(^cat\s+|head\s+|tail\s+|less\s+|more\s+|grep\s+).*(guidelines|guideline_documents)(/(GSL|gsl|markdown|xml))?/[a-z_]+\.(md|xml|gsl)' || true)"
    if [[ -n "${GUIDELINE_BYPASS}" ]]; then
        printf '[%s] BLOCKED CAT BYPASS: %s\n' "$(date)" "$COMMAND" >> "${PROJECT_SECURITY_LOG}"
        printf 'BLOCKED: You MUST use the Read tool to read guideline files, NOT Bash commands!\n' >&2
        printf 'Use: Read tool with file_path pointing at ${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/<name>.xml\n' >&2
        printf 'Do NOT use: cat, head, tail, less, more, grep on guideline files\n' >&2
        exit 2
    fi
    GUIDELINE_HINT="$(printf '%s' "$COMMAND" | grep -E '(guidelines|guideline_documents).*\.(md|xml|gsl|txt)' || true)"
    if [[ -n "${GUIDELINE_HINT}" ]]; then
        printf '[%s] POTENTIAL BYPASS: Bash command on guidelines: %s\n' "$(date)" "$COMMAND" >> "${PROJECT_SECURITY_LOG}"
        printf 'WARNING: Use the Read tool for guideline files, not Bash commands\n' >&2
    fi
    SH_CAT="$(printf '%s' "$COMMAND" | grep -E '^cat\s+.*\.sh$' || true)"
    if [[ -n "${SH_CAT}" ]]; then
        if [[ ! -f "$TRACKING_FILE" ]] || ! grep -qE '^bash$' "$TRACKING_FILE"; then
            if already_fired_this_turn "cat-bash"; then
                printf '[%s] SKIP cat-.sh block (already fired this turn): %s\n' "$(date)" "$COMMAND" >> "${PROJECT_ENFORCEMENT_LOG}"
            else
                mark_fired_this_turn "cat-bash"
                printf '[%s] BLOCKED: Attempted to cat .sh file before reading bash_guidelines\n' "$(date)" >> "${PROJECT_SECURITY_LOG}"
                CAT_BASH_MSG="You must read $(xml_path_for bash_guidelines) BEFORE examining shell scripts.\nUse the Read tool with file_path: $(xml_path_for bash_guidelines)\n(This block fires at most once per turn.)"
                block_policy_emit_full "guideline:cat-bash" "${CAT_BASH_MSG}" "${TOOL_NAME}" "${COMMAND}"
                exit 2
            fi
        fi
    fi
    PY_CAT="$(printf '%s' "$COMMAND" | grep -E '^cat\s+.*\.py$' || true)"
    if [[ -n "${PY_CAT}" ]]; then
        if [[ ! -f "$TRACKING_FILE" ]] || ! grep -qE '^python$' "$TRACKING_FILE"; then
            if already_fired_this_turn "cat-python"; then
                printf '[%s] SKIP cat-.py block (already fired this turn): %s\n' "$(date)" "$COMMAND" >> "${PROJECT_ENFORCEMENT_LOG}"
            else
                mark_fired_this_turn "cat-python"
                printf '[%s] BLOCKED: Attempted to cat .py file before reading python_guidelines\n' "$(date)" >> "${PROJECT_SECURITY_LOG}"
                CAT_PY_MSG="You must read $(xml_path_for python_guidelines) BEFORE examining Python files.\nUse the Read tool with file_path: $(xml_path_for python_guidelines)\n(This block fires at most once per turn.)"
                block_policy_emit_full "guideline:cat-python" "${CAT_PY_MSG}" "${TOOL_NAME}" "${COMMAND}"
                exit 2
            fi
        fi
    fi
fi
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
    check_stale_guidelines
    LANG_KEY=$(get_language "$FILE_PATH")
    if [[ "$LANG_KEY" != "unknown" ]]; then
        if [[ ! -f "$TRACKING_FILE" ]] || ! grep -qE "^${LANG_KEY}$" "$TRACKING_FILE"; then
            if already_fired_this_turn "lang-${LANG_KEY}"; then
                printf '[%s] SKIP lang block (already fired this turn): %s on %s\n' "$(date)" "${LANG_KEY}" "${FILE_PATH}" >> "${PROJECT_ENFORCEMENT_LOG}"
            else
                mark_fired_this_turn "lang-${LANG_KEY}"
                XML_NAME="${LANG_KEY}_guidelines"
                case "$LANG_KEY" in
                    automation)        XML_NAME="automation_principles" ;;
                    prohibited)        XML_NAME="prohibited_behavior" ;;
                    datadog)           XML_NAME="datadog_observability" ;;
                    storage_messaging) XML_NAME="storage_and_messaging_principles" ;;
                esac
                LANG_MSG="You must read $(xml_path_for "${XML_NAME}") before writing ${LANG_KEY} code.\nUse the Read tool with file_path: $(xml_path_for "${XML_NAME}")\nXML guideline files are the authoritative enforcement source -- read the entire file (no limit parameter).\n(This block fires at most once per turn for ${LANG_KEY}. Subsequent ${LANG_KEY} writes this turn will pass through.)"
                block_policy_emit_full "guideline:lang-${LANG_KEY}" "${LANG_MSG}" "${TOOL_NAME}" "${FILE_PATH}"
                exit 2
            fi
        fi
    fi
    if [[ "$LANG_KEY" == "rust" ]]; then
        if [[ "$TOOL_NAME" == "Write" ]]; then
            RUST_CONTENT=$(printf '%s' "$INPUT" | jq -r '.tool_input.content // ""')
        else
            RUST_CONTENT=$(printf '%s' "$INPUT" | jq -r '.tool_input.new_string // ""')
        fi
        check_rust_forbidden_content "$RUST_CONTENT" "$FILE_PATH"
    fi
fi
printf '[%s] Tool: %s, File: %s\n' "$(date)" "$TOOL_NAME" "$FILE_PATH" >> "${PROJECT_ENFORCEMENT_LOG}"
