#!/usr/bin/env bash
#
# Clear Per-Turn Enforcement Fired-Tracking
# ==============================================================================
# Runs on UserPromptSubmit. Resets per-turn enforcement state so that:
#
#   1. extensionless-file warnings (enforce-file-extension.sh) emit at most
#      once per path per turn -- cleared via extensionless_warned_<sid>.
#   2. guideline BLOCK messages (enforce-guidelines.sh: cat-bash, cat-python,
#      and lang-<key> blocks) fire at most once per category per turn --
#      cleared via claude_guidelines_fired_<sid>.
#
# Without this reset, both hooks would degrade to one-warning-per-session
# (extensionless) or hammer the agent on every Write/Edit when something
# upstream clears the read-tracking (guidelines) -- the latter being the
# bug this companion fix addresses.
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly SHARED_UTILS="${SCRIPT_DIR}/../shared/utils"
[[ -f "${SHARED_UTILS}/project-key.sh" ]] || exit 0
source "${SHARED_UTILS}/project-key.sh"
INPUT="$(cat)"
SESSION_ID="$(printf '%s' "${INPUT}" | jq -r '.session_id // "default"')"
CWD="$(printf '%s' "${INPUT}" | jq -r '.cwd // ""')"
resolve_project_paths "${CWD}"
WARN_FILE="${PROJECT_TRACKING_DIR}/extensionless_warned_${SESSION_ID}"
FIRED_FILE="${PROJECT_TRACKING_DIR}/claude_guidelines_fired_${SESSION_ID}"
[[ -f "${WARN_FILE}" ]] && rm -f "${WARN_FILE}"
[[ -f "${FIRED_FILE}" ]] && rm -f "${FIRED_FILE}"
exit 0
