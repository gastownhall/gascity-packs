#!/usr/bin/env bash
#
# Canonical path constants for the enforcement infrastructure.
# ==============================================================================
# Source this file from any enforcement hook to get consistent path constants.
# All MAGI_* names point at the post-reorg locations under ${MAGI_PACK_DIR}/enforcement/.
# ==============================================================================
readonly MAGI_CLAUDE_DIR="${MAGI_PACK_DIR}"
readonly MAGI_ENFORCEMENT_DIR="${MAGI_CLAUDE_DIR}/enforcement"
readonly MAGI_GUIDELINES_DIR="${MAGI_ENFORCEMENT_DIR}/guidelines/guideline_documents"
readonly MAGI_GUIDELINES_XML_DIR="${MAGI_GUIDELINES_DIR}/xml"
readonly MAGI_GUIDELINES_GSL_DIR="${MAGI_GUIDELINES_DIR}/gsl"
readonly MAGI_GUIDELINES_MARKDOWN_DIR="${MAGI_GUIDELINES_DIR}/markdown"
readonly MAGI_RULES_DIR="${MAGI_ENFORCEMENT_DIR}/rules"
readonly MAGI_RULES_FILE="${MAGI_RULES_DIR}/enforcement_rules.json"
readonly MAGI_LIFECYCLE_DIR="${MAGI_ENFORCEMENT_DIR}/lifecycle"
readonly MAGI_SHARED_DIR="${MAGI_ENFORCEMENT_DIR}/shared"
readonly MAGI_SHARED_UTILS_DIR="${MAGI_SHARED_DIR}/utils"
readonly MAGI_AGENTS_DIR="${MAGI_CLAUDE_DIR}/agents"
readonly MAGI_PROJECTS_DIR="${MAGI_CLAUDE_DIR}/projects"
readonly MAGI_SESSIONS_DIR="${MAGI_CLAUDE_DIR}/sessions"
readonly MAGI_SESSION_LOG="${MAGI_SESSIONS_DIR}/session-log.tsv"
readonly MAGI_MEMORY_DIR="${MAGI_CLAUDE_DIR}/memory"
readonly MAGI_OLD_DIR="${MAGI_CLAUDE_DIR}/_OLD"
readonly MAGI_ARCHIVED_DIR="${MAGI_CLAUDE_DIR}/archived"
