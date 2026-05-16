#!/usr/bin/env bash
#
# Install / reinstall claude-cleanup LaunchAgents (macOS only).
# ==============================================================================
# Idempotent: unloads any existing matching agents, copies plists into
# ~/Library/LaunchAgents/, then loads them. Safe to run repeatedly.
# Discovers plists by glob so it works after deploy_harness.sh has renamed
# them to com.${USER}.claude-cleanup-*.plist.
# ==============================================================================
set -Eeuo pipefail
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly DEST="${HOME}/Library/LaunchAgents"
readonly LABEL_PREFIX="com.${USER}.claude-cleanup"
mkdir -p "${DEST}"
shopt -s nullglob
PLISTS=("${SCRIPT_DIR}"/${LABEL_PREFIX}-*.plist)
shopt -u nullglob
if [[ ${#PLISTS[@]} -eq 0 ]]; then
    printf 'ERROR: no plists matching %s-*.plist found in %s\n' "${LABEL_PREFIX}" "${SCRIPT_DIR}" >&2
    exit 1
fi
LAUNCHCTL_PATH="$(command -v launchctl || true)"
[[ -n "${LAUNCHCTL_PATH}" ]] || { printf 'ERROR: launchctl not found (macOS only)\n' >&2; exit 1; }
for src in "${PLISTS[@]}"; do
    p="$(basename "${src}")"
    dst="${DEST}/${p}"
    label="${p%.plist}"
    if launchctl list "${label}" >/dev/null 2>&1; then
        launchctl unload "${dst}" 2>&1 | grep -v "Could not find" || true
    fi
    cp -f "${src}" "${dst}"
    chmod 644 "${dst}"
    launchctl load -w "${dst}"
    printf 'loaded: %s\n' "${label}"
done
printf '\nActive cleanup agents:\n'
launchctl list | grep -E "${LABEL_PREFIX}" || true
