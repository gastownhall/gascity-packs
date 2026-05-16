#!/usr/bin/env bash
[[ -n "${__FILESYSTEM_UTILS_LOADED:-}" ]] && return 0
__FILESYSTEM_UTILS_LOADED=1
resolve_symlink() {
    local path="$1"
    local resolved_path
    if [[ ! -e "${path}" ]]; then
        printf '%s' "${path}"
        return 0
    fi
    if [[ -L "${path}" ]]; then
        if command -v readlink >/dev/null 2>&1; then
            if [[ "$(uname -s)" == "Darwin" ]]; then
                resolved_path="$(readlink "${path}" 2>/dev/null)" || resolved_path="${path}"
                if [[ "${resolved_path}" != /* ]]; then
                    resolved_path="$(dirname "${path}")/${resolved_path}"
                fi
                while [[ -L "${resolved_path}" ]]; do
                    local next_link
                    next_link="$(readlink "${resolved_path}" 2>/dev/null)" || break
                    if [[ "${next_link}" != /* ]]; then
                        resolved_path="$(dirname "${resolved_path}")/${next_link}"
                    else
                        resolved_path="${next_link}"
                    fi
                done
                if [[ -e "${resolved_path}" ]]; then
                    resolved_path="$(cd -P "$(dirname "${resolved_path}")" 2>/dev/null && pwd)/$(basename "${resolved_path}")"
                fi
            else
                resolved_path="$(readlink -f "${path}" 2>/dev/null)" || resolved_path="${path}"
            fi
        else
            resolved_path="${path}"
        fi
    else
        resolved_path="${path}"
    fi
    printf '%s' "${resolved_path}"
}
compute_file_hash() {
    local path="$1"
    local resolved_path
    resolved_path="$(resolve_symlink "${path}")"
    if [[ ! -f "${resolved_path}" ]]; then
        printf 'NOFILE'
        return 0
    fi
    if [[ ! -r "${resolved_path}" ]]; then
        printf 'UNREADABLE'
        return 0
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "${resolved_path}" 2>/dev/null | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "${resolved_path}" 2>/dev/null | cut -d' ' -f1
    else
        stat -f%z "${resolved_path}" 2>/dev/null || stat -c%s "${resolved_path}" 2>/dev/null || printf '0'
    fi
}
read_file_limited() {
    local path="$1"
    local max_lines="${2:-5000}"
    local resolved_path
    resolved_path="$(resolve_symlink "${path}")"
    if [[ ! -f "${resolved_path}" ]]; then
        printf '(File not found: %s)\n' "${path}"
        return 0
    fi
    if [[ ! -r "${resolved_path}" ]]; then
        printf '(File not readable: %s)\n' "${path}"
        return 0
    fi
    local file_size
    file_size="$(stat -f%z "${resolved_path}" 2>/dev/null || stat -c%s "${resolved_path}" 2>/dev/null || printf '0')"
    if [[ "${file_size}" -gt $((10 * 1024 * 1024)) ]]; then
        printf '(File too large: %s bytes, showing first %d lines)\n' "${file_size}" "${max_lines}"
        head -n "${max_lines}" "${resolved_path}" 2>/dev/null
    else
        cat "${resolved_path}" 2>/dev/null || printf '(Could not read file: %s)\n' "${path}"
    fi
}
store_file_hashes() {
    local hash_file="$1"
    shift
    local scan_dirs=("$@")
    : > "${hash_file}"
    for dir in "${scan_dirs[@]}"; do
        [[ ! -d "${dir}" ]] && continue
        while IFS= read -r -d '' file; do
            local resolved_file
            resolved_file="$(resolve_symlink "${file}")"
            local hash
            hash="$(compute_file_hash "${resolved_file}")"
            printf '%s:%s\n' "${file}" "${hash}" >> "${hash_file}"
        done < <(find "${dir}" -maxdepth 3 -type f \
            \( -name "*.sh" -o -name "*.py" -o -name "*.js" -o -name "*.json" \
               -o -name "*.md" -o -name "*.txt" -o -name "*.yaml" -o -name "*.yml" \
               -o -name "*.rs" -o -name "*.go" -o -name "*.cs" -o -name "*.java" \
               -o -name "*.tsx" -o -name "*.ts" -o -name "*.jsx" -o -name "*.css" \
               -o -name "*.html" -o -name "*.xml" -o -name "*.toml" -o -name "*.ini" \
               -o -name "*.cfg" -o -name "*.conf" -o -name "*.env" -o -name ".env.*" \
               -o -name "Makefile" -o -name "Dockerfile" -o -name "*.sql" \) \
            -print0 2>/dev/null)
        while IFS= read -r -d '' symlink; do
            local target resolved_target hash
            target="$(readlink "${symlink}" 2>/dev/null)" || continue
            if [[ "${target}" != /* ]]; then
                target="$(dirname "${symlink}")/${target}"
            fi
            resolved_target="$(resolve_symlink "${target}")"
            if [[ -f "${resolved_target}" ]]; then
                hash="$(compute_file_hash "${resolved_target}")"
                printf '%s:%s\n' "${symlink}" "${hash}" >> "${hash_file}"
            fi
        done < <(find "${dir}" -maxdepth 3 -type l -print0 2>/dev/null)
    done
}
detect_file_changes() {
    local hash_file="$1"
    shift
    local scan_dirs=("$@")
    local changed_files=()
    local new_files=()
    local deleted_files=()
    declare -A stored_hashes
    if [[ -f "${hash_file}" ]]; then
        while IFS=: read -r file hash; do
            [[ -n "${file}" ]] && stored_hashes["${file}"]="${hash}"
        done < "${hash_file}"
    fi
    declare -A current_files
    for dir in "${scan_dirs[@]}"; do
        [[ ! -d "${dir}" ]] && continue
        while IFS= read -r -d '' file; do
            local resolved_file current_hash
            resolved_file="$(resolve_symlink "${file}")"
            current_hash="$(compute_file_hash "${resolved_file}")"
            current_files["${file}"]=1
            if [[ -z "${stored_hashes["${file}"]:-}" ]]; then
                new_files+=("${file}")
            elif [[ "${current_hash}" != "${stored_hashes["${file}"]}" ]]; then
                changed_files+=("${file}")
            fi
        done < <(find "${dir}" -maxdepth 3 \( -type f -o -type l \) \
            \( -name "*.sh" -o -name "*.py" -o -name "*.js" -o -name "*.json" \
               -o -name "*.md" -o -name "*.txt" -o -name "*.yaml" -o -name "*.yml" \
               -o -name "*.rs" -o -name "*.go" -o -name "*.cs" -o -name "*.java" \
               -o -name "*.tsx" -o -name "*.ts" -o -name "*.jsx" -o -name "*.css" \
               -o -name "*.html" -o -name "*.xml" -o -name "*.toml" -o -name "*.ini" \
               -o -name "*.cfg" -o -name "*.conf" -o -name "*.env" -o -name ".env.*" \
               -o -name "Makefile" -o -name "Dockerfile" -o -name "*.sql" \) \
            -print0 2>/dev/null)
    done
    for file in "${!stored_hashes[@]}"; do
        if [[ -z "${current_files["${file}"]:-}" ]]; then
            deleted_files+=("${file}")
        fi
    done
    if [[ ${#changed_files[@]} -gt 0 ]]; then
        printf 'CHANGED:'
        printf '%s ' "${changed_files[@]}"
        printf '\n'
    fi
    if [[ ${#new_files[@]} -gt 0 ]]; then
        printf 'NEW:'
        printf '%s ' "${new_files[@]}"
        printf '\n'
    fi
    if [[ ${#deleted_files[@]} -gt 0 ]]; then
        printf 'DELETED:'
        printf '%s ' "${deleted_files[@]}"
        printf '\n'
    fi
}
file_in_array() {
    local needle="$1"
    shift
    local haystack=("$@")
    for item in "${haystack[@]}"; do
        [[ "${item}" == "${needle}" ]] && return 0
    done
    return 1
}