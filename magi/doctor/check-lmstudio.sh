#!/bin/sh
#
# magi/doctor/check-lmstudio.sh
# ==============================================================================
# Description: Doctor probe for LM Studio reachability. Resolves the OpenAI-
# compatible endpoint from PROJECT_ANALYZER_LM_URL, then LM_STUDIO_URL, then a
# default of http://localhost:1234. Issues GET /v1/models with bounded
# connect-timeout and total max-time. Writes the body and HTTP status to a
# per-run log under the city's runtime/packs/magi/logs directory. Warn-only:
# unreachable LM Studio is rc=2 (warn), not rc=1 (fail).
#
# USAGE:
#   ./check-lmstudio.sh
#
# ENVIRONMENT VARIABLES:
#   GC_CITY_PATH               Gas City root (logs derive from this path)
#   PROJECT_ANALYZER_LM_URL    Highest-precedence LM Studio URL
#   LM_STUDIO_URL              Fallback LM Studio URL
#
# DEPENDENCIES:
#   External: curl
# ==============================================================================
set -eu
VERB_LOG_DIR="${GC_CITY_PATH:-.}/.gc/runtime/packs/magi/logs"
mkdir -p "${VERB_LOG_DIR}"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
LOG_FILE="${VERB_LOG_DIR}/doctor-lmstudio-${STAMP}.log"
BODY_FILE="${VERB_LOG_DIR}/lmstudio-probe-${STAMP}.body"
URL=""
if [ -n "${PROJECT_ANALYZER_LM_URL:-}" ]; then
    URL="${PROJECT_ANALYZER_LM_URL}"
elif [ -n "${LM_STUDIO_URL:-}" ]; then
    URL="${LM_STUDIO_URL}"
else
    URL="http://localhost:1234"
fi
CURL_BIN="$(command -v curl || printf '')"
if [ -z "${CURL_BIN}" ]; then
    {
        printf 'check=lmstudio stamp=%s\n' "${STAMP}"
        printf 'url=%s\n' "${URL}"
        printf 'result=warn reason=curl-missing\n'
    } >> "${LOG_FILE}"
    printf 'curl not on PATH; cannot probe LM Studio\n' >&2
    printf 'lmstudio log=%s\n' "${LOG_FILE}" >&2
    exit 2
fi
HTTP_STATUS="$(${CURL_BIN} --fail --silent --show-error --connect-timeout 3 --max-time 10 --output "${BODY_FILE}" --write-out '%{http_code}' "${URL}/v1/models" || printf 'curl_error')"
{
    printf 'check=lmstudio stamp=%s\n' "${STAMP}"
    printf 'url=%s\n' "${URL}"
    printf 'http_status=%s\n' "${HTTP_STATUS}"
    printf 'body_file=%s\n' "${BODY_FILE}"
} >> "${LOG_FILE}"
if [ "${HTTP_STATUS}" = "200" ]; then
    printf 'result=ok\n' >> "${LOG_FILE}"
    printf 'LM Studio reachable at %s\n' "${URL}"
    printf 'lmstudio log=%s\n' "${LOG_FILE}"
    exit 0
fi
printf 'result=warn http_status=%s\n' "${HTTP_STATUS}" >> "${LOG_FILE}"
printf 'LM Studio unreachable (status=%s) at %s\n' "${HTTP_STATUS}" "${URL}" >&2
printf 'lmstudio log=%s\n' "${LOG_FILE}" >&2
exit 2
