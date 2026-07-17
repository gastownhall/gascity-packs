#!/usr/bin/env python3
"""Run model-backed inference gates for first-class Gas City packs.

The gate builds a disposable city and rig, imports a local pack at city scope,
imports gascity/roles at rig scope when needed, then runs real formulas against
known subjects. Review gates verify produced review artifacts. Build gates ask
the selected pack's build formula to make a code change and then execute the
fixture tests in the resulting implementation worktree. The Gastown gate checks
orchestration agents and runs a bounded review-leg workflow through polecat.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import math
import os
import re
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import yaml
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_GATE = "review"
BUILD_GATE = "build"
BUILD_BASIC_GATE = "build-basic"
GASTOWN_ORCHESTRATION_GATE = "gastown-orchestration"
ALL_GATE = "all"
GASCITY_PACK = "gascity"
GASTOWN_PACK = "gastown"
GASCITY_REMOTE_SOURCE = "https://github.com/gastownhall/gascity.git"
REVIEW_SUBJECT_PATH = Path(".gc/inference-gate/review-subject.diff")
REVIEW_REPORT_PATH = Path(".gc/inference-gate/review-report.md")
LOGICAL_CONTROL_KINDS = frozenset(
    {
        "check",
        "drain",
        "fanout",
        "ralph",
        "retry",
        "scope",
        "scope-check",
        "workflow-finalize",
    }
)
REVIEW_FORMULA = "review"
REVIEW_TITLE = "gascity pack inference gate: review"
BUILD_BASIC_FORMULA = "build-basic"
BUILD_ARTIFACT_ROOT = Path(".gc/inference-gate/build-basic")
BUILD_TITLE = "gascity pack inference gate: build-basic"
BUILD_SOURCE_TITLE = "Implement slugify and make pytest pass"
BUILD_BASIC_PRODUCT_PATHS = ("slugger.py", "tests/test_slugger.py")
GASTOWN_REVIEW_TITLE = "Gastown orchestration gate: review leg"
GASTOWN_REVIEW_ASSIGNMENT_TITLE = "Review Gastown orchestration gate fixture"
GASTOWN_ALWAYS_ON_AGENTS = ("mayor", "deacon", "boot", "witness")
GASTOWN_FORMULA_CONTRACTS = {
    "mol-review-leg": (
        "write the FULL report into the bead notes",
        "gc bd update \"$WORK_BEAD_ID\" --notes",
        "gc mail send \"$COORD\"",
        "gc bd update \"$WORK_BEAD_ID\" --status=closed",
    ),
    "mol-idea-to-plan": (
        "review task beads",
        "gc sling \"$REVIEW_TARGET\" \"$LEG_BEAD\" --on {{review_formula}}",
        "review_phase=<phase>",
        "Convert the refined plan into beads",
        "gc bd dep add",
    ),
    "mol-polecat-work": (
        'extends = ["mol-polecat-base"]',
        "git worktree add",
        "--set-metadata branch=\"$BRANCH\"",
        "{{test_command}}",
        "REFINERY_TARGET=\"${GC_RIG:+$GC_RIG/}{{binding_prefix}}refinery\"",
        "--assignee=\"$REFINERY_TARGET\"",
    ),
    "mol-refinery-patrol": (
        "metadata.branch",
        "fast-forward merge",
        "run tests before merging",
        "metadata.target",
        "closes the bead",
    ),
    "mol-witness-patrol": (
        "Orphaned bead recovery",
        "metadata.work_dir",
        "return beads to the pool",
        "gc session list --state=all --json",
    ),
}
GASTOWN_BUILD_WORKFLOW_CONTRACTS = {
    "mol-polecat-work": (
        "EXPECTED_BRANCH=\"polecat/$WORK_BEAD_ID\"",
        "{{typecheck_command}}",
        "{{lint_command}}",
        "{{build_command}}",
        "{{test_command}}",
        "git push origin HEAD",
        "gc bd update \"$WORK_BEAD_ID\" \\",
        "--set-metadata target={{base_branch}}",
        "--status=open --assignee=\"$REFINERY_TARGET\"",
        "gc session wake \"$REFINERY_TARGET\"",
        "gc runtime drain-ack",
    ),
    "mol-refinery-patrol": (
        "gc bd list ${GC_RIG:+--rig=\"$GC_RIG\"} --assignee=$GC_AGENT --status=open",
        "git rebase origin/$TARGET",
        "{{typecheck_command}}",
        "{{lint_command}}",
        "{{build_command}}",
        "{{test_command}}",
        "branch_has_real_change",
        'git worktree add --detach "$MERGE_WT" "origin/$TARGET"',
        'git -C "$MERGE_WT" merge --ff-only "$TEMP_SHA"',
        "--set-metadata merge_result=merged",
        '--set-metadata merged_sha="$MERGED_SHA"',
        'gc bd close "$WORK" --reason "Merged to $TARGET at $MERGED_SHORT"',
        "gh pr create",
        "--set-metadata pr_url=\"$PR_URL\"",
        "gc bd close $WORK --reason \"Pull request ready: $PR_URL\"",
    ),
    "mol-witness-patrol": (
        "LIVENESS_MAP=$(jq -n",
        "FAIL-SAFE: empty liveness map",
        "git push origin HEAD",
        "gc workflow delete-source <bead> --apply && gc workflow reopen-source <bead>",
        "gc bd update <bead> --set-metadata recovered=true",
        "gc session nudge <rig>/{{binding_prefix}}refinery",
        "--label=warrant",
        "\"gc.routed_to\":\"{{binding_prefix}}dog\"",
    ),
    "mol-deacon-patrol": (
        "Work-layer health",
        "queue-starvation-check",
        "gc agents list --json --active",
        "gc bd create --type=task --label=warrant",
        "\"gc.routed_to\":\"{{binding_prefix}}dog\"",
    ),
    "mol-idea-to-plan": (
        "Dispatch 6 PRD review legs in parallel",
        "Dispatch 6 design legs",
        "Run 3 PRD-alignment rounds",
        "Run 3 plan self-review rounds",
        "gc sling \"$REVIEW_TARGET\" \"$LEG_BEAD\" --on {{review_formula}}",
        "gc bd dep add",
    ),
}
METHODOLOGY_FLOW_CONTRACTS = {
    "superpowers": {
        "review_expansion": "superpowers-code-review",
        "build_steps": {
            "requirements": {
                "run_target": "superpowers.brainstorming",
                "artifact_schema": "gc.build.requirements.v1",
                "expand": "superpowers-brainstorming",
            },
            "plan": {
                "run_target": "superpowers.writing-plans",
                "artifact_schema": "gc.build.plan.v1",
                "check": "build-artifact-valid.sh",
            },
            "plan-review": {
                "run_target": "superpowers.plan-reviewer",
                "expand": "superpowers-plan-review",
            },
            "decompose": {
                "run_target": "gc.task-decomposer",
                "artifact_schema": "gc.build.decomposition.v1",
                "check": "build-artifact-valid.sh",
            },
            "implement": {
                "run_target": "{{implementation_target}}",
                "drain_formula": "superpowers-development",
                "drain_context": "separate",
            },
            "implement-same-session": {
                "run_target": "{{implementation_target}}",
                "drain_formula": "superpowers-development-item",
                "drain_context": "shared",
                "single_lane": True,
            },
            "review": {
                "run_target": "superpowers.code-reviewer",
                "artifact_schema": "gc.build.review.v1",
                "expand": "superpowers-code-review",
                "needs": ("summarize-implementation",),
            },
            "finalize": {
                "run_target": "superpowers.finisher",
                "artifact_schema": "gc.build.final-report.v1",
                "check": "build-artifact-valid.sh",
            },
        },
        "expansion_routes": {
            "superpowers-code-review": (
                "superpowers.code-reviewer",
                "superpowers.code-quality-reviewer",
                "{implementation_target}",
            ),
            "superpowers-plan-review": ("superpowers.plan-reviewer", "superpowers.writing-plans"),
            "superpowers-brainstorming": ("superpowers.brainstorming", "superpowers.spec-reviewer"),
        },
        "expansion_checks": {
            "superpowers-code-review": "implementation-review-approved.sh",
            "superpowers-plan-review": "design-review-approved.sh",
            "superpowers-brainstorming": "design-review-approved.sh",
        },
        "expansion_terminal_checks": {
            "superpowers-brainstorming": "build-requirements-source-valid.sh",
        },
    },
    "compound-engineering": {
        "review_expansion": "compound-code-review",
        "build_steps": {
            "requirements": {
                "run_target": "compound-engineering.ce-brainstorm",
                "artifact_schema": "gc.build.requirements.v1",
                "check": "build-requirements-source-valid.sh",
            },
            "plan": {
                "run_target": "compound-engineering.ce-plan",
                "artifact_schema": "gc.build.plan.v1",
                "check": "build-artifact-valid.sh",
            },
            "plan-review": {
                "run_target": "compound-engineering.ce-plan-review-synthesizer",
                "expand": "compound-plan-review",
            },
            "implement": {
                "run_target": "{{implementation_target}}",
                "drain_formula": "compound-work",
                "drain_context": "separate",
            },
            "implement-same-session": {
                "run_target": "{{implementation_target}}",
                "drain_formula": "compound-work-item",
                "drain_context": "shared",
                "single_lane": True,
            },
            "review": {
                "run_target": "compound-engineering.ce-code-review-synthesizer",
                "artifact_schema": "gc.build.review.v1",
                "expand": "compound-code-review",
                "needs": ("summarize-implementation",),
            },
            "finalize": {
                "run_target": "compound-engineering.ce-compound",
                "artifact_schema": "gc.build.final-report.v1",
                "expand": "compound-resolution",
            },
        },
        "expansion_routes": {
            "compound-code-review": (
                "compound-engineering.ce-code-review-selector",
                "compound-engineering.ce-correctness-reviewer",
                "compound-engineering.ce-testing-reviewer",
                "compound-engineering.ce-maintainability-reviewer",
                "compound-engineering.ce-security-reviewer",
                "compound-engineering.ce-code-review-synthesizer",
                "{implementation_target}",
            ),
            "compound-plan-review": (
                "compound-engineering.ce-coherence-reviewer",
                "compound-engineering.ce-feasibility-reviewer",
                "compound-engineering.ce-scope-guardian-reviewer",
                "compound-engineering.ce-architecture-strategist",
                "compound-engineering.ce-plan-review-synthesizer",
                "compound-engineering.ce-plan",
            ),
            "compound-resolution": (
                "compound-engineering.ce-pr-comment-resolver",
                "compound-engineering.ce-compound",
            ),
        },
        "expansion_checks": {
            "compound-code-review": "implementation-review-approved.sh",
            "compound-plan-review": "design-review-approved.sh",
        },
    },
    "gstack": {
        "review_expansion": "gstack-code-review",
        "build_steps": {
            "requirements": {
                "run_target": "gstack.office-hours",
                "artifact_schema": "gc.build.requirements.v1",
                "check": "gstack-build-state-valid.sh",
            },
            "plan": {
                "run_target": "gstack.founder-reviewer",
                "artifact_schema": "gc.build.plan.v1",
                "check": "build-artifact-valid.sh",
            },
            "plan-review": {
                "run_target": "gstack.review-synthesizer",
                "expand": "gstack-plan-review",
            },
            "decompose": {
                "run_target": "gstack.decomposer",
                "artifact_schema": "gc.build.decomposition.v1",
                "check": "gstack-build-state-valid.sh",
            },
            "implement": {
                "run_target": "{{implementation_target}}",
                "drain_formula": "gstack-work",
                "drain_context": "separate",
            },
            "implement-same-session": {
                "run_target": "{{implementation_target}}",
                "drain_formula": "gstack-work-item",
                "drain_context": "shared",
                "single_lane": True,
            },
            "summarize-implementation": {
                "run_target": "gc.run-operator",
                "artifact_schema": "gc.build.implementation-summary.v1",
                "needs": ("implement", "implement-same-session"),
                "check": "gstack-build-state-valid.sh",
            },
            "review": {
                "run_target": "gstack.review-synthesizer",
                "artifact_schema": "gc.build.review.v1",
                "expand": "gstack-code-review",
                "needs": ("summarize-implementation",),
            },
            "qa": {
                "run_target": "gstack.qa-lead",
                "expand": "gstack-qa-review",
                "needs": ("review",),
            },
            "release-readiness": {
                "run_target": "gstack.release-engineer",
                "expand": "gstack-release-readiness",
                "needs": ("qa",),
            },
            "finalize": {
                "run_target": "gstack.release-engineer",
                "artifact_schema": "gc.build.final-report.v1",
                "needs": ("release-readiness",),
                "check": "gstack-build-state-valid.sh",
            },
            "publish": {
                "run_target": "gc.publisher",
                "needs": ("finalize",),
            },
        },
        "expansion_routes": {
            "gstack-code-review": (
                "gstack.staff-reviewer",
                "gstack.qa-lead",
                "gstack.security-officer",
                "gstack.review-synthesizer",
                "{implementation_target}",
            ),
            "gstack-plan-review": (
                "gstack.founder-reviewer",
                "gstack.design-reviewer",
                "gstack.eng-reviewer",
                "gstack.devex-reviewer",
                "gstack.review-synthesizer",
            ),
            "gstack-qa-review": (
                "gstack.qa-lead",
                "gstack.staff-reviewer",
                "gstack.review-synthesizer",
                "{implementation_target}",
            ),
            "gstack-release-readiness": (
                "gstack.docs-engineer",
                "gstack.release-engineer",
                "gstack.review-synthesizer",
            ),
        },
        "expansion_checks": {
            "gstack-code-review": "implementation-review-approved.sh",
            "gstack-plan-review": "design-review-approved.sh",
            "gstack-qa-review": "implementation-review-approved.sh",
            "gstack-release-readiness": "implementation-review-approved.sh",
        },
    },
    "bmad": {
        "review_expansion": "bmad-code-review-flow",
        "build_steps": {
            "requirements": {
                "run_target": "bmad.prd-writer",
                "artifact_schema": "gc.build.requirements.v1",
                "check": "build-requirements-source-valid.sh",
            },
            "plan": {
                "run_target": "bmad.architect",
                "artifact_schema": "gc.build.plan.v1",
                "check": "build-artifact-valid.sh",
            },
            "plan-review": {
                "run_target": "bmad.architect",
                "needs": ("plan",),
            },
            "decompose": {
                "run_target": "bmad.epic-story-decomposer",
                "artifact_schema": "gc.build.decomposition.v1",
                "check": "build-artifact-valid.sh",
            },
            "implementation-readiness": {
                "run_target": "bmad.readiness-reviewer",
                "needs": ("decompose",),
            },
            "implement": {
                "run_target": "{{implementation_target}}",
                "drain_formula": "bmad-story-development",
                "drain_context": "separate",
                "needs": ("implementation-readiness",),
            },
            "implement-same-session": {
                "run_target": "{{implementation_target}}",
                "drain_formula": "bmad-story-development-item",
                "drain_context": "shared",
                "single_lane": True,
                "needs": ("implementation-readiness",),
            },
            "review": {
                "run_target": "bmad.bmad-review-synthesizer",
                "artifact_schema": "gc.build.review.v1",
                "expand": "bmad-code-review-flow",
                "needs": ("summarize-implementation",),
            },
        },
        "expansion_routes": {
            "bmad-code-review-flow": (
                "bmad.blind-hunter-reviewer",
                "bmad.edge-case-reviewer",
                "bmad.acceptance-auditor",
                "bmad.story-self-checker",
                "bmad.bmad-review-synthesizer",
                "{implementation_target}",
            ),
        },
        "expansion_checks": {
            "bmad-code-review-flow": "implementation-review-approved.sh",
        },
    },
}
BUILD_BASIC_ARTIFACT_CONTRACTS = (
    ("gc.build.requirements_path", "gc.build.requirements.v1"),
    ("gc.build.plan_path", "gc.build.plan.v1"),
    ("gc.build.decomposition_path", "gc.build.decomposition.v1"),
    ("gc.build.implementation_summary_path", "gc.build.implementation-summary.v1"),
    ("gc.build.review_report_path", "gc.build.review.v1"),
    ("gc.build.final_report_path", "gc.build.final-report.v1"),
)
BUILD_ARTIFACT_STAGE_BY_KEY = {
    "gc.build.requirements_path": "requirements",
    "gc.build.plan_path": "plan",
    "gc.build.decomposition_path": "decompose",
    "gc.build.implementation_summary_path": "summarize-implementation",
    "gc.build.review_report_path": "review",
    "gc.build.final_report_path": "finalize",
}
BUILD_ARTIFACT_IDENTITY_PROFILES = {
    "gascity": {
        "build_formula": "build-basic",
        "review_attempt": {
            "source": "loop",
            "ralph_step_id": "review.build-basic-review-loop",
            "terminal_step_id": "review.report-review-findings",
            "terminal_report_name": "apply-review-findings-report.md",
        },
        "methodology_names": {},
        "workflow_formulas": {},
        "producer_formulas": {
            "gc.build.review_report_path": "build-basic-review",
        },
        "producer_stages": {},
    },
    "superpowers": {
        "build_formula": "superpowers-build",
        "review_attempt": {"source": "stage", "step_id": "review"},
        "methodology_names": {
            "gc.build.requirements_path": "superpowers-brainstorming",
            "gc.build.plan_path": "writing-plans",
            "gc.build.decomposition_path": "superpowers-decomposition",
            "gc.build.review_report_path": "superpowers-code-review",
        },
        "workflow_formulas": {},
        "producer_formulas": {
            "gc.build.requirements_path": "superpowers-brainstorming",
            "gc.build.review_report_path": "superpowers-code-review",
        },
        "producer_stages": {
            "gc.build.review_report_path": "adapter-report",
        },
    },
    "compound-engineering": {
        "build_formula": "compound-build",
        "review_attempt": {"source": "stage", "step_id": "review"},
        "methodology_names": {
            "gc.build.requirements_path": "ce-brainstorm",
            "gc.build.plan_path": "ce-plan",
            "gc.build.decomposition_path": "compound-decomposition",
            "gc.build.review_report_path": "compound-review",
            "gc.build.final_report_path": "ce-compound",
        },
        "workflow_formulas": {
            "gc.build.review_report_path": "compound-review",
        },
        "producer_formulas": {
            "gc.build.review_report_path": "compound-code-review",
            "gc.build.final_report_path": "compound-resolution",
        },
        "producer_stages": {
            "gc.build.review_report_path": "synthesize-code-review",
            "gc.build.final_report_path": "synthesize-resolution",
        },
    },
    "gstack": {
        "build_formula": "gstack-build",
        "review_attempt": {"source": "stage", "step_id": "review"},
        "methodology_names": {
            "gc.build.requirements_path": "office-hours",
            "gc.build.plan_path": "autoplan",
            "gc.build.decomposition_path": "gstack-decomposition",
            "gc.build.review_report_path": "gstack-review",
        },
        "workflow_formulas": {
            "gc.build.review_report_path": "gstack-review",
        },
        "producer_formulas": {
            "gc.build.review_report_path": "gstack-code-review",
        },
        "producer_stages": {
            "gc.build.review_report_path": "adapter-report",
        },
    },
    "bmad": {
        "build_formula": "bmad-build",
        "review_attempt": {"source": "stage", "step_id": "review"},
        "methodology_names": {
            "gc.build.requirements_path": "bmad-prd",
            "gc.build.plan_path": "bmad-create-architecture",
            "gc.build.decomposition_path": "bmad-create-epics-and-stories",
            "gc.build.review_report_path": "bmad-review",
        },
        "workflow_formulas": {
            "gc.build.review_report_path": "bmad-review",
        },
        "producer_formulas": {
            "gc.build.review_report_path": "bmad-code-review-flow",
        },
        "producer_stages": {
            "gc.build.review_report_path": "synthesize-bmad-review",
        },
    },
}
BUILD_BASIC_STAGE_STEPS = {
    "gc.build.requirements_path": "requirements",
    "gc.build.plan_path": "plan",
    "gc.build.decomposition_path": "decompose",
    "gc.build.implementation_summary_path": "summarize-implementation",
    "gc.build.final_report_path": "finalize",
}
BUILD_BASIC_PRE_REVIEW_ARTIFACT_KEYS = (
    "gc.build.requirements_path",
    "gc.build.plan_path",
    "gc.build.decomposition_path",
    "gc.build.implementation_summary_path",
)
BUILD_BASIC_SUCCESS_LIFECYCLE = {
    "gc.outcome": "pass",
    "gc.build.status": "completed",
    "gc.build.finalize_status": "completed",
    "gc.build.finalize_outcome": "success",
}
BUILD_BASIC_BLOCKED_LIFECYCLE = {
    "gc.outcome": "fail",
    "gc.build.status": "blocked",
    "gc.build.finalize_status": "failed",
    "gc.build.finalize_outcome": "failure",
}
DEFAULT_GATE = "all"
DEFAULT_TIMEOUT = "75m"
DEFAULT_POLL_INTERVAL = "5s"
# Gas City's progress recycler intentionally excludes sessions with live claims.
# Reset only known non-resumable malformed-tool history, and fail current-workflow
# sessions promptly when their provider transcript proves a permanent outage.
TERMINAL_PROVIDER_SCAN_INTERVAL = 30.0
TERMINAL_PROVIDER_STALE_AFTER = 60.0
TERMINAL_PROVIDER_RECOVERY_TIMEOUT = 300.0
TERMINAL_PROVIDER_MAX_SESSION_CACHE_AGE = 60.0
RAW_CLAUDE_MAX_TRANSCRIPT_FILES = 128
RAW_CLAUDE_MAX_TRANSCRIPT_BYTES = 64 * 1024 * 1024
RAW_CLAUDE_MAX_SCAN_BYTES = 256 * 1024 * 1024
RAW_CLAUDE_MAX_CLOCK_SKEW = 300.0
TERMINAL_PROVIDER_ERROR_SIGNATURES = (
    "tool_use block missing required 'name' field",
)
FATAL_PROVIDER_ERROR_SIGNATURES = (
    ("provider_quota_exhausted", ("reached your weekly usage limit",)),
    (
        "provider_authentication_failed",
        ("request rejected (401)", "api error: 401", "http 401", "status code 401"),
    ),
    (
        "provider_authorization_failed",
        ("request rejected (403)", "api error: 403", "http 403", "status code 403"),
    ),
)
BD_LIST_LIMIT = "1000"
INHERITED_ENV_KEYS = (
    "PATH",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "USER",
    "HOME",
    "SHELL",
    "SSH_AUTH_SOCK",
    "TERM",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    "CLAUDE_CODE_EFFORT_LEVEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "OLLAMA_API_KEY",
)
REQUIRED_INFERENCE_ENV_KEYS = (
    "OLLAMA_API_KEY",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
)


@dataclass(frozen=True)
class GateWorkspace:
    root: Path
    city_dir: Path
    rig_dir: Path
    gc_home: Path
    runtime_dir: Path
    claude_config_dir: Path
    city_name: str
    rig_name: str


@dataclass(frozen=True)
class PackSpec:
    name: str
    binding: str
    source: Path
    roles_source: Path
    validator_source: Path
    review_formula: str | None
    build_formula: str | None
    default_gates: tuple[str, ...]
    setup_formulas: tuple[str, ...]
    required_review_routes: tuple[str, ...] = ()
    required_build_routes: tuple[str, ...] = ()
    gastown: bool = False


class GateError(RuntimeError):
    pass


@dataclass
class TerminalProviderReset:
    requested_at: float
    source_transcript_path: str
    claim_ids: tuple[str, ...]
    session_identities: tuple[str, ...]
    recovery_evidence: str = ""
    requested_at_utc: datetime | None = None
    source_conversation_started_at: datetime | None = None


@dataclass(frozen=True)
class ProviderLogTip:
    transcript_path: str
    entry_id: str
    synthetic: bool
    terminal_error: bool
    fatal_error: str
    entry_at: datetime | None = None
    conversation_started_at: datetime | None = None


@dataclass(frozen=True)
class RawClaudeTranscript:
    work_dir: str
    conversation_started_at: datetime
    tip: ProviderLogTip | None


RawClaudeTranscriptCache = dict[
    Path,
    tuple[tuple[int, int, int, int, int, int], RawClaudeTranscript | None],
]


def make_pack_specs() -> dict[str, PackSpec]:
    roles_source = REPO_ROOT / "gascity" / "roles"
    validator_source = REPO_ROOT / "gascity"
    return {
        GASCITY_PACK: PackSpec(
            name=GASCITY_PACK,
            binding="gc",
            source=REPO_ROOT / "gascity",
            roles_source=roles_source,
            validator_source=validator_source,
            review_formula=REVIEW_FORMULA,
            build_formula=BUILD_BASIC_FORMULA,
            default_gates=(REVIEW_GATE, BUILD_BASIC_GATE),
            setup_formulas=(REVIEW_FORMULA, BUILD_BASIC_FORMULA),
            required_review_routes=("gc.implementation-reviewer",),
            required_build_routes=(
                "gc.requirements-planner",
                "gc.design-author",
                "gc.task-decomposer",
                "gc.implementation-worker",
                "gc.implementation-reviewer",
                "gc.review-synthesizer",
            ),
        ),
        "superpowers": PackSpec(
            name="superpowers",
            binding="superpowers",
            source=REPO_ROOT / "superpowers",
            roles_source=roles_source,
            validator_source=validator_source,
            review_formula="superpowers-review",
            build_formula="superpowers-build",
            default_gates=(REVIEW_GATE, BUILD_GATE),
            setup_formulas=("superpowers-review", "superpowers-build"),
            required_review_routes=(
                "superpowers.code-reviewer",
                "superpowers.code-quality-reviewer",
            ),
            required_build_routes=(
                "superpowers.brainstorming",
                "superpowers.writing-plans",
                "superpowers.plan-reviewer",
                "gc.task-decomposer",
                "superpowers.implementer",
                "superpowers.code-reviewer",
                "superpowers.code-quality-reviewer",
                "superpowers.finisher",
            ),
        ),
        "compound-engineering": PackSpec(
            name="compound-engineering",
            binding="compound-engineering",
            source=REPO_ROOT / "compound-engineering",
            roles_source=roles_source,
            validator_source=validator_source,
            review_formula="compound-review",
            build_formula="compound-build",
            default_gates=(REVIEW_GATE, BUILD_GATE),
            setup_formulas=("compound-review", "compound-build"),
            required_review_routes=(
                "compound-engineering.ce-code-review-selector",
                "compound-engineering.ce-correctness-reviewer",
                "compound-engineering.ce-testing-reviewer",
                "compound-engineering.ce-maintainability-reviewer",
                "compound-engineering.ce-code-review-synthesizer",
            ),
            required_build_routes=(
                "compound-engineering.ce-brainstorm",
                "compound-engineering.ce-plan",
                "compound-engineering.ce-plan-review-synthesizer",
                "compound-engineering.ce-work",
                "compound-engineering.ce-code-review-synthesizer",
                "compound-engineering.ce-compound",
            ),
        ),
        "gstack": PackSpec(
            name="gstack",
            binding="gstack",
            source=REPO_ROOT / "gstack",
            roles_source=roles_source,
            validator_source=validator_source,
            review_formula="gstack-review",
            build_formula="gstack-build",
            default_gates=(REVIEW_GATE, BUILD_GATE),
            setup_formulas=("gstack-review", "gstack-build"),
            required_review_routes=(
                "gstack.staff-reviewer",
                "gstack.qa-lead",
                "gstack.security-officer",
                "gstack.review-synthesizer",
            ),
            required_build_routes=(
                "gstack.office-hours",
                "gstack.founder-reviewer",
                "gstack.decomposer",
                "gstack.implementer",
                "gstack.review-synthesizer",
                "gstack.qa-lead",
                "gstack.security-officer",
                "gstack.release-engineer",
            ),
        ),
        "bmad": PackSpec(
            name="bmad",
            binding="bmad",
            source=REPO_ROOT / "bmad",
            roles_source=roles_source,
            validator_source=validator_source,
            review_formula="bmad-review",
            build_formula="bmad-build",
            default_gates=(REVIEW_GATE, BUILD_GATE),
            setup_formulas=("bmad-review", "bmad-build"),
            required_review_routes=(
                "bmad.blind-hunter-reviewer",
                "bmad.edge-case-reviewer",
                "bmad.acceptance-auditor",
                "bmad.story-self-checker",
                "bmad.bmad-review-synthesizer",
            ),
            required_build_routes=(
                "bmad.prd-writer",
                "bmad.architect",
                "bmad.epic-story-decomposer",
                "bmad.readiness-reviewer",
                "bmad.story-implementer",
                "bmad.bmad-review-synthesizer",
            ),
        ),
        GASTOWN_PACK: PackSpec(
            name=GASTOWN_PACK,
            binding=GASTOWN_PACK,
            source=REPO_ROOT / "gastown",
            roles_source=roles_source,
            validator_source=validator_source,
            review_formula=None,
            build_formula=None,
            default_gates=(GASTOWN_ORCHESTRATION_GATE,),
            setup_formulas=(
                "mol-review-leg",
                "mol-idea-to-plan",
                "mol-polecat-work",
                "mol-refinery-patrol",
                "mol-witness-patrol",
                "mol-deacon-patrol",
                "mol-shutdown-dance",
            ),
            gastown=True,
        ),
    }


PACK_SPECS = make_pack_specs()
METHODOLOGY_PACKS = ("superpowers", "compound-engineering", "gstack", "bmad")
SUPPORTED_PACK_CHOICES = (*PACK_SPECS.keys(), "methodology", "all-supported")


def toml_string(value: str | Path) -> str:
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def builtin_pack_sources() -> dict[str, str | Path]:
    gascity_root = discover_gascity_source_root()
    if gascity_root is not None:
        return {
            "core": gascity_root / "internal" / "bootstrap" / "packs" / "core",
            "bd": gascity_root / "examples" / "bd",
        }
    return {
        "core": f"{GASCITY_REMOTE_SOURCE}//internal/bootstrap/packs/core",
        "bd": f"{GASCITY_REMOTE_SOURCE}//examples/bd",
    }


def discover_gascity_source_root() -> Path | None:
    candidates: list[Path] = []
    env_root = os.environ.get("GASCITY_SOURCE_ROOT") or os.environ.get("GASCITY_REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    candidates.extend(
        [
            REPO_ROOT / ".gascity-ci",
            REPO_ROOT.parent / "gascity",
            Path("/data/projects/gascity"),
        ]
    )
    for candidate in candidates:
        root = candidate.expanduser().resolve()
        if (
            (root / "internal" / "bootstrap" / "packs" / "core" / "pack.toml").is_file()
            and (root / "examples" / "bd" / "pack.toml").is_file()
        ):
            return root
    return None


def parse_duration(value: str) -> float:
    value = value.strip()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([smh]?)", value)
    if not match:
        raise ValueError(f"invalid duration {value!r}; use seconds, 30s, 5m, or 1h")
    amount = float(match.group(1))
    unit = match.group(2) or "s"
    return amount * {"s": 1, "m": 60, "h": 3600}[unit]


def expand_gate_selection(selection: str, pack_spec: PackSpec | None = None) -> list[str]:
    spec = pack_spec or PACK_SPECS[GASCITY_PACK]
    if selection == ALL_GATE:
        return list(spec.default_gates)
    if selection == BUILD_GATE and spec.name == GASCITY_PACK:
        return [BUILD_BASIC_GATE]
    if selection == BUILD_BASIC_GATE and spec.name != GASCITY_PACK:
        raise ValueError(f"{selection!r} is only valid for the gascity pack; use 'build' for {spec.name}")
    if selection in spec.default_gates:
        return [selection]
    allowed = sorted({*spec.default_gates, ALL_GATE, *(("build",) if spec.build_formula else ())})
    raise ValueError(f"invalid gate {selection!r} for pack {spec.name}; choose one of {', '.join(allowed)}")


def write_gate_workspace(
    work_root: Path,
    *,
    pack_source: Path,
    roles_source: Path,
    validator_source: Path | None = None,
    pack_binding: str = "gc",
    pack_name: str = GASCITY_PACK,
    gastown: bool = False,
    city_name: str,
    rig_name: str,
) -> GateWorkspace:
    root = work_root.resolve()
    city_dir = root / "city"
    rig_dir = root / rig_name
    gc_home = root / "gc-home"
    runtime_dir = root / "runtime"
    claude_config_dir = gc_home / ".claude"

    for path in (city_dir, rig_dir, gc_home, runtime_dir, claude_config_dir):
        path.mkdir(parents=True, exist_ok=False)
    (city_dir / ".gc").mkdir(exist_ok=True)
    (rig_dir / ".gc" / "inference-gate").mkdir(parents=True, exist_ok=True)

    pack_source = pack_source.resolve()
    roles_source = roles_source.resolve()
    validator_source = (validator_source or pack_source).resolve()

    city_lines = [
        "[workspace]",
        'provider = "claude"',
    ]
    if gastown:
        city_lines.append('global_fragments = ["command-glossary", "operational-awareness"]')
    city_lines.extend(
        [
            "",
            "[workspace.env]",
            f"HOME = {toml_string(gc_home)}",
            'PYTHONDONTWRITEBYTECODE = "1"',
            "",
            "[providers.claude]",
            'base = "builtin:claude"',
            "",
            "[session]",
            'startup_timeout = "3m"',
            'progress_stall_timeout = "10m"',
            "",
            "[daemon]",
            "formula_v2 = true",
            'patrol_interval = "1s"',
            f"observe_paths = [{toml_string(claude_config_dir / 'projects')}]",
            "",
        ]
    )
    city_lines.extend(
        [
            "[[rigs]]",
            f"name = {toml_string(rig_name)}",
        ]
    )
    if gastown:
        city_lines.extend(
            [
                "",
                "[rigs.imports.gastown]",
                f"source = {toml_string(pack_source)}",
            ]
        )
    else:
        city_lines.extend(
            [
                "",
                "[rigs.imports.gc]",
                f"source = {toml_string(roles_source)}",
            ]
        )
        if pack_binding != "gc":
            city_lines.extend(
                [
                    "",
                    f"[rigs.imports.{pack_binding}]",
                    f"source = {toml_string(pack_source)}",
                ]
            )
    city_lines.append("")
    (city_dir / "city.toml").write_text("\n".join(city_lines), encoding="utf-8")
    (city_dir / ".gc" / "site.toml").write_text(
        "\n".join(
            [
                f"workspace_name = {toml_string(city_name)}",
                "",
                "[[rig]]",
                f"name = {toml_string(rig_name)}",
                f"path = {toml_string(rig_dir)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    pack_lines = [
        "[pack]",
        f"name = {toml_string(f'{pack_name}-pack-inference-gate')}",
        "schema = 2",
        "",
    ]
    for binding, source in builtin_pack_sources().items():
        pack_lines.extend([f"[imports.{binding}]", f"source = {toml_string(source)}", ""])
    pack_lines.extend([f"[imports.{pack_binding}]", f"source = {toml_string(pack_source)}", ""])
    (city_dir / "pack.toml").write_text("\n".join(pack_lines), encoding="utf-8")

    materialize_pack_check_scripts(validator_source, rig_dir)
    write_build_basic_fixture(rig_dir)
    return GateWorkspace(
        root=root,
        city_dir=city_dir,
        rig_dir=rig_dir,
        gc_home=gc_home,
        runtime_dir=runtime_dir,
        claude_config_dir=claude_config_dir,
        city_name=city_name,
        rig_name=rig_name,
    )


def materialize_pack_check_scripts(pack_source: Path, rig_dir: Path) -> None:
    """Install formula check scripts and their local validation schemas."""

    scripts_source = pack_source / "assets" / "scripts"
    checks_source = scripts_source / "checks"
    if not checks_source.is_dir():
        return

    scripts_target = rig_dir / ".gc" / "scripts"
    checks_target = scripts_target / "checks"
    checks_target.mkdir(parents=True, exist_ok=True)
    for script in sorted(checks_source.glob("*.sh")):
        shutil.copy2(script, checks_target / script.name)

    for helper_name in (
        "validate_build_artifact.py",
        "verify_implementation_provenance.py",
    ):
        helper_source = scripts_source / helper_name
        if not helper_source.is_file():
            raise GateError(f"pack check runtime helper is missing: {helper_source}")
        shutil.copy2(helper_source, scripts_target / helper_name)

    schemas_source = pack_source / "schemas" / "build"
    if schemas_source.is_dir():
        schemas_target = rig_dir / "schemas" / "build"
        schemas_target.mkdir(parents=True, exist_ok=True)
        for schema in sorted(schemas_source.glob("*.yaml")):
            shutil.copy2(schema, schemas_target / schema.name)


def review_subject() -> str:
    return """\
# Review subject

Review the following implementation diff as a production code review. The
function accepts user-controlled `destination` and writes an archive.

```diff
diff --git a/exporter.py b/exporter.py
index 1111111..2222222 100644
--- a/exporter.py
+++ b/exporter.py
@@
+import subprocess
+
+def export_user_archive(user_id: str, destination: str) -> None:
+    source = f"/srv/users/{user_id}"
+    subprocess.run(f"tar czf {destination} {source}", shell=True, check=True)
```

Expected security property: user-controlled paths must not be interpolated
into a shell command. The review report should call out the command-injection
or shell-injection risk and require a safer argument-vector based invocation.
"""


def write_review_subject(root: Path) -> Path:
    subject_path = root / REVIEW_SUBJECT_PATH
    subject_path.parent.mkdir(parents=True, exist_ok=True)
    subject_path.write_text(review_subject(), encoding="utf-8")
    return subject_path


def write_build_basic_fixture(root: Path) -> None:
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (root / "slugger.py").write_text(
        '''\
"""Small fixture module for the gascity pack build-basic inference gate."""


def slugify(value: str) -> str:
    """Return a URL slug for value."""
    raise NotImplementedError("slugify is intentionally missing")
''',
        encoding="utf-8",
    )
    (tests_dir / "test_slugger.py").write_text(
        '''\
from slugger import slugify


def test_slugify_basic_phrase() -> None:
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_collapses_separators() -> None:
    assert slugify("  Multiple---spaces___OK  ") == "multiple-spaces-ok"


def test_slugify_handles_no_alphanumerics() -> None:
    assert slugify("!!!") == ""
''',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        """\
[tool.pytest.ini_options]
testpaths = ["tests"]
""",
        encoding="utf-8",
    )


def build_basic_work_item() -> str:
    return f"""\
{BUILD_SOURCE_TITLE}

The repository contains a deliberately failing Python fixture. Implement
`slugify` in `slugger.py` so the existing tests pass.

Expected behavior:
- Lowercase ASCII alphanumeric words.
- Treat any run of non-alphanumeric characters as a separator.
- Join non-empty groups with single hyphens.
- Return an empty string when the input contains no alphanumeric characters.

Constraints:
- Do not change tests/test_slugger.py.
- Keep the implementation small and deterministic.
- Run `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider`
  from the repository root and record that proof.
"""


def install_service_manager_shims(gc_home: Path) -> Path:
    shim_dir = gc_home / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    body = "#!/bin/sh\n# inference-gate shim: force bare supervisor startup.\nexit 1\n"
    for name in ("launchctl", "systemctl"):
        path = shim_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    return shim_dir


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def write_supervisor_config(gc_home: Path) -> None:
    port = reserve_port()
    (gc_home / "supervisor.toml").write_text(
        f'[supervisor]\nport = {port}\nbind = "127.0.0.1"\n',
        encoding="utf-8",
    )


def build_gate_env(gc_bin: str, workspace: GateWorkspace, inherited: Mapping[str, str] | None = None) -> dict[str, str]:
    source = dict(inherited or os.environ)
    env = {key: source[key] for key in INHERITED_ENV_KEYS if source.get(key)}
    if not env.get("HOME"):
        env["HOME"] = str(Path.home())

    shim_dir = install_service_manager_shims(workspace.gc_home)
    gc_bin_dir = str(Path(gc_bin).resolve().parent)
    env["PATH"] = os.pathsep.join(part for part in (str(shim_dir), gc_bin_dir, env.get("PATH", "")) if part)
    env["GC_ACCEPTANCE_GC_BIN"] = gc_bin
    env["GC_HOME"] = str(workspace.gc_home)
    env["XDG_RUNTIME_DIR"] = str(workspace.runtime_dir)
    env["DOLT_ROOT_PATH"] = str(workspace.gc_home)
    env["CLAUDE_CONFIG_DIR"] = str(workspace.claude_config_dir)
    pythonpath = pythonpath_with_host_modules(source.get("PYTHONPATH"), ("pytest",))
    if pythonpath:
        env["PYTHONPATH"] = pythonpath
    env.setdefault("CLAUDE_CODE_EFFORT_LEVEL", "auto")
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    write_dolt_global_config(workspace.gc_home)

    if env.get("OLLAMA_API_KEY"):
        env.setdefault("ANTHROPIC_BASE_URL", "https://ollama.com")
        env.setdefault("ANTHROPIC_AUTH_TOKEN", env["OLLAMA_API_KEY"])
    return env


def pythonpath_with_host_modules(existing: str | None, module_names: Sequence[str]) -> str:
    parts: list[str] = []
    if existing:
        parts.extend(part for part in existing.split(os.pathsep) if part)
    for root in host_python_import_roots(module_names):
        parts.append(str(root))
    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part in seen:
            continue
        seen.add(part)
        deduped.append(part)
    return os.pathsep.join(deduped)


def host_python_import_roots(module_names: Sequence[str]) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for module_name in module_names:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            continue
        candidates: list[Path] = []
        if spec.submodule_search_locations:
            candidates.extend(Path(location).resolve().parent for location in spec.submodule_search_locations)
        elif spec.origin and spec.origin not in {"built-in", "frozen"}:
            candidates.append(Path(spec.origin).resolve().parent)
        for candidate in candidates:
            if not candidate.is_dir() or candidate in seen:
                continue
            roots.append(candidate)
            seen.add(candidate)
    return roots


def write_dolt_global_config(gc_home: Path) -> None:
    dolt_dir = gc_home / ".dolt"
    dolt_dir.mkdir(parents=True, exist_ok=True)
    config_path = dolt_dir / "config_global.json"
    if config_path.exists():
        return
    save_json_object(
        config_path,
        {
            "user.name": "Gas City Pack Gate",
            "user.email": "gascity-pack-gate@example.invalid",
        },
    )


def seed_claude_project_state(*, home: Path, config_dir: Path, project_paths: Sequence[Path]) -> None:
    for state_path in claude_state_paths(home, config_dir):
        state = load_json_object(state_path)
        state["hasCompletedOnboarding"] = True
        if not str(state.get("theme") or "").strip():
            state["theme"] = "light"
        projects = state.get("projects")
        if not isinstance(projects, dict):
            projects = {}
            state["projects"] = projects
        for project_path in project_paths:
            key = str(project_path.resolve())
            entry = projects.get(key)
            if not isinstance(entry, dict):
                entry = {}
            entry["hasCompletedProjectOnboarding"] = True
            entry["hasTrustDialogAccepted"] = True
            entry.setdefault("projectOnboardingSeenCount", 1)
            projects[key] = entry
        save_json_object(state_path, state)


def claude_state_paths(home: Path, config_dir: Path) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for path in (home / ".claude.json", config_dir / ".claude.json"):
        resolved = path.resolve()
        if resolved not in seen:
            paths.append(path)
            seen.add(resolved)
    return paths


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GateError(f"{path} must contain a JSON object")
    return data


def save_json_object(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def validate_inference_env(env: Mapping[str, str]) -> None:
    missing = [key for key in REQUIRED_INFERENCE_ENV_KEYS if not str(env.get(key) or "").strip()]
    if missing:
        raise GateError(
            "missing inference environment variable(s): "
            + ", ".join(missing)
            + ". Configure the same Ollama-backed Claude variables used by Gas City's nightly Tier C workflow."
        )


def run_checked(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    log_output: bool = False,
    input_text: str | None = None,
) -> str:
    print("+ " + shlex.join(command), flush=True)
    result = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env is not None else None,
        text=True,
        input=input_text,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if log_output and output:
        print(output, end="" if output.endswith("\n") else "\n")
    if result.returncode == 0:
        return output
    if output:
        print(output, file=sys.stderr, end="" if output.endswith("\n") else "\n")
    raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)


def initialize_rig_git(rig_dir: Path, *, env: Mapping[str, str]) -> None:
    if (rig_dir / ".git").exists():
        return
    try:
        run_checked(["git", "init", "-b", "main"], cwd=rig_dir, env=env)
    except subprocess.CalledProcessError:
        run_checked(["git", "init"], cwd=rig_dir, env=env)
        run_checked(["git", "checkout", "-B", "main"], cwd=rig_dir, env=env)
    run_checked(["git", "config", "user.email", "gascity-pack-gate@example.invalid"], cwd=rig_dir, env=env)
    run_checked(["git", "config", "user.name", "Gas City Pack Gate"], cwd=rig_dir, env=env)
    run_checked(["git", "add", "."], cwd=rig_dir, env=env)
    run_checked(["git", "commit", "-m", "Add inference gate fixtures"], cwd=rig_dir, env=env)


def initialize_city(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    pack_spec: PackSpec,
    gates: Sequence[str],
    env: Mapping[str, str],
) -> None:
    write_supervisor_config(workspace.gc_home)
    seed_claude_project_state(
        home=Path(env["HOME"]),
        config_dir=Path(env["CLAUDE_CONFIG_DIR"]),
        project_paths=[workspace.city_dir, workspace.rig_dir],
    )
    initialize_rig_git(workspace.rig_dir, env=env)

    run_checked(
        [
            gc_bin,
            "init",
            "--skip-provider-readiness",
            "--name",
            workspace.city_name,
            "--file",
            str(workspace.city_dir / "city.toml"),
            "--preserve-existing",
            "--yes",
            str(workspace.city_dir),
        ],
        env=env,
        timeout=parse_duration("5m"),
        log_output=True,
    )
    run_checked([gc_bin, "--city", str(workspace.city_dir), "import", "install"], env=env, timeout=parse_duration("5m"))
    run_checked([gc_bin, "--city", str(workspace.city_dir), "import", "check"], env=env, timeout=parse_duration("5m"))
    run_checked([gc_bin, "--city", str(workspace.city_dir), "config", "show"], env=env, timeout=parse_duration("2m"))
    formulas = selected_setup_formulas(pack_spec, gates)
    for formula in formulas:
        run_checked(
            [gc_bin, "--city", str(workspace.city_dir), "--rig", workspace.rig_name, "formula", "show", formula],
            env=env,
            timeout=parse_duration("2m"),
        )
    if pack_spec.gastown:
        validate_gastown_orchestration_contract(pack_spec.source)
    else:
        validate_methodology_flow_contract(pack_spec)


def start_city(gc_bin: str, workspace: GateWorkspace, *, env: Mapping[str, str]) -> None:
    run_checked([gc_bin, "start", str(workspace.city_dir), "--verbose"], env=env, timeout=parse_duration("5m"), log_output=True)


def selected_setup_formulas(pack_spec: PackSpec, gates: Sequence[str]) -> list[str]:
    selected: list[str] = []
    if pack_spec.gastown:
        return list(pack_spec.setup_formulas)
    if REVIEW_GATE in gates and pack_spec.review_formula:
        selected.append(pack_spec.review_formula)
    if any(gate in gates for gate in (BUILD_GATE, BUILD_BASIC_GATE)) and pack_spec.build_formula:
        selected.append(pack_spec.build_formula)
    return selected


def review_title(pack_spec: PackSpec) -> str:
    if pack_spec.name == GASCITY_PACK:
        return REVIEW_TITLE
    return f"{pack_spec.name} pack inference gate: review"


def build_title(pack_spec: PackSpec) -> str:
    if pack_spec.name == GASCITY_PACK:
        return BUILD_TITLE
    if not pack_spec.build_formula:
        raise GateError(f"pack {pack_spec.name} does not define a build formula")
    return f"{pack_spec.name} pack inference gate: {pack_spec.build_formula}"


def build_artifact_root(pack_spec: PackSpec) -> Path:
    if pack_spec.name == GASCITY_PACK:
        return BUILD_ARTIFACT_ROOT
    if not pack_spec.build_formula:
        raise GateError(f"pack {pack_spec.name} does not define a build formula")
    return Path(".gc/inference-gate") / pack_spec.name / pack_spec.build_formula


def launch_review_formula(gc_bin: str, workspace: GateWorkspace, *, env: Mapping[str, str], pack_spec: PackSpec) -> str:
    if not pack_spec.review_formula:
        raise GateError(f"pack {pack_spec.name} does not define a review formula")
    subject_path = write_review_subject(workspace.rig_dir).resolve()
    report_path = (workspace.rig_dir / REVIEW_REPORT_PATH).resolve()
    command = [
        gc_bin,
        "--city",
        str(workspace.city_dir),
        "--rig",
        workspace.rig_name,
        "sling",
        "gc.run-operator",
        pack_spec.review_formula,
        "--formula",
        "--title",
        review_title(pack_spec),
        "--var",
        f"subject_path={subject_path}",
        "--var",
        f"report_path={report_path}",
        "--var",
        "interaction_mode=headless",
        "--var",
        "review_mode=report",
        "--nudge",
        "--json",
    ]
    output = run_checked(command, cwd=workspace.rig_dir, env=env, timeout=parse_duration("5m"), log_output=True)
    root_id = extract_sling_root_id(output)
    if root_id:
        return root_id
    bead = wait_for_root_by_title(gc_bin, workspace, env=env, title=review_title(pack_spec), timeout=parse_duration("30s"))
    if bead and bead.get("id"):
        return str(bead["id"])
    raise GateError(f"could not determine review workflow root from sling output:\n{output}")


def launch_build_formula(gc_bin: str, workspace: GateWorkspace, *, env: Mapping[str, str], pack_spec: PackSpec) -> str:
    if not pack_spec.build_formula:
        raise GateError(f"pack {pack_spec.name} does not define a build formula")
    command = [
        gc_bin,
        "--city",
        str(workspace.city_dir),
        "--rig",
        workspace.rig_name,
        "sling",
        "gc.run-operator",
        "--stdin",
        "--force",
        "--on",
        pack_spec.build_formula,
        "--title",
        build_title(pack_spec),
        "--var",
        f"artifact_root={(workspace.rig_dir / build_artifact_root(pack_spec)).resolve()}",
        "--var",
        "interaction_mode=headless",
        "--var",
        "review_mode=report",
        "--var",
        "drain_policy=separate",
        "--var",
        "push=false",
        "--var",
        "open_pr=false",
        "--var",
        "max_iterations=2",
        "--nudge",
        "--json",
    ]
    output = run_checked(
        command,
        cwd=workspace.rig_dir,
        env=env,
        timeout=parse_duration("5m"),
        log_output=True,
        input_text=build_basic_work_item(),
    )
    root_id = resolve_workflow_root_id(
        gc_bin,
        workspace,
        env=env,
        candidate_id=extract_sling_root_id(output),
        title=build_title(pack_spec),
        source_title=BUILD_SOURCE_TITLE,
        timeout=parse_duration("30s"),
    )
    if root_id:
        return root_id
    raise GateError(f"could not determine build-basic workflow root from sling output:\n{output}")


def extract_json_payload(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped:
        return None
    for index, char in enumerate(stripped):
        if char not in "[{":
            continue
        candidate = stripped[index:]
        try:
            payload, _ = json.JSONDecoder().raw_decode(candidate)
            return payload
        except json.JSONDecodeError:
            continue
    return None


def extract_sling_root_id(output: str) -> str | None:
    payload = extract_json_payload(output)
    if payload is None:
        return None
    return find_first_key(payload, ("root_bead_id", "workflow_id", "root_id", "bead_id", "id"))


def find_first_key(value: Any, keys: Sequence[str]) -> str | None:
    if isinstance(value, dict):
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        for raw in value.values():
            found = find_first_key(raw, keys)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_first_key(item, keys)
            if found:
                return found
    return None


def list_beads(gc_bin: str, workspace: GateWorkspace, *, env: Mapping[str, str]) -> list[dict[str, Any]]:
    try:
        output = run_checked(
            [
                gc_bin,
                "--city",
                str(workspace.city_dir),
                "--rig",
                workspace.rig_name,
                "bd",
                "list",
                "--all",
                "--json",
                "--limit",
                BD_LIST_LIMIT,
            ],
            env=env,
            timeout=parse_duration("30s"),
        )
        payload = extract_json_payload(output)
        if isinstance(payload, list):
            beads = [item for item in payload if isinstance(item, dict)]
            if beads:
                return append_event_route_history(beads, workspace)
            event_beads = list_beads_from_event_log(workspace)
            if event_beads:
                return event_beads
            return beads
        if payload is not None:
            raise GateError(f"unexpected gc bd list --json payload: {payload!r}")
    except Exception:
        event_beads = list_beads_from_event_log(workspace)
        if event_beads:
            return event_beads
        if not (workspace.rig_dir / ".gc" / "beads.json").exists():
            raise

    path = workspace.rig_dir / ".gc" / "beads.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GateError(f"{path} must contain a JSON object")
    beads = payload.get("beads")
    if not isinstance(beads, list):
        raise GateError(f"{path} missing beads array")
    return [item for item in beads if isinstance(item, dict)]


def list_beads_from_event_log(workspace: GateWorkspace) -> list[dict[str, Any]]:
    path = workspace.city_dir / ".gc" / "events.jsonl"
    if not path.is_file():
        return []

    beads: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        bead = event_payload_bead(event)
        if not isinstance(bead, dict):
            continue
        bead_id = bead.get("id")
        if isinstance(bead_id, str) and bead_id:
            beads[bead_id] = bead
    return list(beads.values())


def event_payload_bead(event: Mapping[str, Any]) -> dict[str, Any] | None:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    bead = payload.get("bead")
    if isinstance(bead, dict):
        return bead
    if isinstance(payload.get("id"), str) and isinstance(payload.get("title"), str):
        return payload
    return None


def append_event_route_history(beads: Sequence[dict[str, Any]], workspace: GateWorkspace) -> list[dict[str, Any]]:
    routes = event_route_history_targets(workspace)
    if not routes:
        return list(beads)
    return [
        *beads,
        {
            "id": "__gc_event_route_history__",
            "title": "__gc_event_route_history__",
            "status": "closed",
            "metadata": {"gc.event.routed_to": routes},
        },
    ]


def event_route_history_targets(workspace: GateWorkspace) -> list[str]:
    path = workspace.city_dir / ".gc" / "events.jsonl"
    if not path.is_file():
        return []

    routes: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        bead = event_payload_bead(event)
        if isinstance(bead, dict):
            routes.extend(bead_route_targets(bead))
    return dedupe_strings(routes)


def find_unique_bead_by_title(beads: Sequence[Mapping[str, Any]], title: str) -> Mapping[str, Any] | None:
    matches = [bead for bead in beads if bead.get("title") == title]
    if len(matches) == 1:
        return matches[0]
    return None


def build_basic_source_id(beads: Sequence[Mapping[str, Any]]) -> str:
    matches = [bead for bead in beads if bead.get("title") == BUILD_SOURCE_TITLE]
    source_ids = [str(bead.get("id") or "").strip() for bead in matches]
    if len(source_ids) != 1 or not source_ids[0]:
        raise GateError(
            "build-basic gate requires exactly one launcher source bead titled "
            f"{BUILD_SOURCE_TITLE!r}; observed={source_ids}"
        )
    return source_ids[0]


def find_bead_by_id(beads: Sequence[Mapping[str, Any]], bead_id: str) -> Mapping[str, Any] | None:
    for bead in beads:
        if bead.get("id") == bead_id:
            return bead
    return None


def wait_for_root_by_title(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    title: str,
    timeout: float,
) -> Mapping[str, Any] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        bead = find_unique_bead_by_title(list_beads(gc_bin, workspace, env=env), title)
        if bead is not None:
            return bead
        time.sleep(1)
    return None


def resolve_workflow_root_id(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    candidate_id: str | None,
    title: str,
    source_title: str | None = None,
    timeout: float,
) -> str | None:
    metadata_keys = (
        "gc.root_bead_id",
        "gc.workflow_root_id",
        "gc.attached_workflow_id",
        "root_bead_id",
        "workflow_id",
        "root_id",
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        beads = list_beads(gc_bin, workspace, env=env)
        root = find_unique_bead_by_title(beads, title)
        if root and root.get("id"):
            return str(root["id"])

        for bead in candidate_beads(beads, candidate_id, source_title):
            if bead.get("title") == title and bead.get("id"):
                return str(bead["id"])
            for key in metadata_keys:
                value = metadata_value(bead, key)
                if not value:
                    continue
                candidate_root = find_bead_by_id(beads, value)
                if candidate_root and candidate_root.get("title") == title:
                    return value
        time.sleep(1)
    return None


def candidate_beads(
    beads: Sequence[Mapping[str, Any]],
    candidate_id: str | None,
    source_title: str | None,
) -> list[Mapping[str, Any]]:
    candidates: list[Mapping[str, Any]] = []
    if candidate_id:
        bead = find_bead_by_id(beads, candidate_id)
        if bead is not None:
            candidates.append(bead)
    if source_title:
        bead = find_unique_bead_by_title(beads, source_title)
        if bead is not None and bead not in candidates:
            candidates.append(bead)
    return candidates


def show_bead(gc_bin: str, workspace: GateWorkspace, bead_id: str, *, env: Mapping[str, str]) -> dict[str, Any]:
    try:
        output = run_checked(
            [
                gc_bin,
                "--city",
                str(workspace.city_dir),
                "--rig",
                workspace.rig_name,
                "bd",
                "show",
                bead_id,
                "--json",
            ],
            env=env,
            timeout=parse_duration("30s"),
        )
        payload = extract_json_payload(output)
        if isinstance(payload, dict):
            if payload.get("id") == bead_id:
                return payload
            raise GateError(f"unexpected gc bd show --json payload for {bead_id}: {payload!r}")
        if isinstance(payload, list):
            matches = [item for item in payload if isinstance(item, dict) and item.get("id") == bead_id]
            if len(matches) == 1:
                return matches[0]
            raise GateError(f"unexpected gc bd show --json payload for {bead_id}: {payload!r}")
        if payload is not None:
            raise GateError(f"unexpected gc bd show --json payload for {bead_id}: {payload!r}")
    except Exception:
        if not (workspace.rig_dir / ".gc" / "beads.json").exists():
            raise

    for bead in list_beads(gc_bin, workspace, env=env):
        if bead.get("id") == bead_id:
            return bead
    raise GateError(f"bead {bead_id} not found in gc bd show --json or gc bd list --json output")


def metadata_value(bead: Mapping[str, Any], key: str) -> str:
    metadata = bead.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    value = metadata.get(key)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def drain_manifest_root_ids(bead: Mapping[str, Any]) -> list[str]:
    raw_manifest = metadata_value(bead, "gc.drain_manifest.v1").strip()
    drain_id = str(bead.get("id") or "<unknown>")
    if not raw_manifest:
        raise GateError(f"workflow lineage drain {drain_id} is missing gc.drain_manifest.v1")
    rows = drain_manifest_rows(bead)
    if rows is None:
        raise GateError(f"workflow lineage drain {drain_id} has malformed manifest")
    if metadata_value(bead, "gc.drain_state") != "succeeded":
        raise GateError(f"workflow lineage drain {drain_id} must record gc.drain_state=succeeded")
    raw_count = metadata_value(bead, "gc.drain_count")
    try:
        drain_count = int(raw_count)
    except ValueError as exc:
        raise GateError(
            f"workflow lineage drain {drain_id} has invalid gc.drain_count={raw_count!r}"
        ) from exc
    if drain_count != len(rows):
        raise GateError(
            f"workflow lineage drain {drain_id} gc.drain_count does not match manifest rows: "
            f"count={drain_count} rows={len(rows)}"
        )

    root_ids: list[str] = []
    for index, row in enumerate(rows):
        row_root_ids: list[str] = []
        if isinstance(row, Mapping):
            row_root_ids = [
                value.strip()
                for key in ("item_root_id", "outcome_bead_id")
                if isinstance((value := row.get(key)), str) and value.strip()
            ]
        if not row_root_ids:
            raise GateError(
                f"workflow lineage drain {drain_id} has malformed manifest row {index}: "
                "expected non-empty item_root_id or outcome_bead_id"
            )
        if row.get("status") != "succeeded":
            raise GateError(
                f"workflow lineage drain {drain_id} manifest row {index} must record status=succeeded"
            )
        if row.get("outcome_kind") != "pass":
            raise GateError(
                f"workflow lineage drain {drain_id} manifest row {index} must record outcome_kind=pass"
            )
        root_ids.extend(row_root_ids)
    return dedupe_strings(root_ids)


def drain_manifest_rows(bead: Mapping[str, Any]) -> list[Any] | None:
    try:
        manifest = json.loads(metadata_value(bead, "gc.drain_manifest.v1"))
    except (json.JSONDecodeError, TypeError):
        return None
    rows = manifest.get("rows") if isinstance(manifest, Mapping) else None
    return rows if isinstance(rows, list) else None


def validate_workflow_lineage(beads: Sequence[Mapping[str, Any]], root_id: str) -> None:
    by_id: dict[str, list[Mapping[str, Any]]] = {}
    for bead in beads:
        bead_id = bead.get("id")
        if isinstance(bead_id, str) and bead_id:
            by_id.setdefault(bead_id, []).append(bead)

    lineage = {root_id}
    nested_roots: set[str] = set()
    pending = [root_id]
    while pending:
        parent_id = pending.pop()
        drains = [
            bead
            for bead in beads
            if metadata_value(bead, "gc.root_bead_id") == parent_id
            and metadata_value(bead, "gc.kind") == "drain"
            and not metadata_value(bead, "gc.attempt")
        ]
        for drain in drains:
            for nested_id in drain_manifest_root_ids(drain):
                matches = by_id.get(nested_id, [])
                if len(matches) != 1:
                    raise GateError(f"workflow lineage root {nested_id} must be present exactly one time")
                nested = matches[0]
                if metadata_value(nested, "gc.kind") != "workflow":
                    raise GateError(f"workflow lineage root {nested_id} must record gc.kind=workflow")
                if nested_id not in lineage:
                    lineage.add(nested_id)
                    nested_roots.add(nested_id)
                    pending.append(nested_id)

    for nested_id in sorted(nested_roots):
        nested = by_id[nested_id][0]
        require_closed_pass_lineage_bead(nested, f"workflow lineage root {nested_id}")

    for lineage_root_id in sorted(lineage):
        controls = [
            bead
            for bead in beads
            if metadata_value(bead, "gc.root_bead_id") == lineage_root_id
            and metadata_value(bead, "gc.kind") in LOGICAL_CONTROL_KINDS
            and not metadata_value(bead, "gc.attempt")
        ]
        finalizers = [bead for bead in controls if metadata_value(bead, "gc.kind") == "workflow-finalize"]
        if not finalizers:
            raise GateError(f"workflow lineage root {lineage_root_id} is missing workflow-finalize control")
        for control in controls:
            control_id = str(control.get("id") or "").strip()
            if not control_id or len(by_id.get(control_id, [])) != 1:
                raise GateError(
                    f"logical control beneath workflow lineage root {lineage_root_id} must be uniquely present"
                )
            step_ref = metadata_value(control, "gc.step_ref") or str(control.get("title") or "<untitled>")
            require_closed_pass_lineage_bead(
                control,
                f"logical workflow control failed or incomplete: {control_id} ({step_ref})",
            )


CLOSED_PASS_EMPTY_METADATA = (
    "gc.blocked_reason",
    "gc.failure_class",
    "gc.restart.entrypoint",
    "gc.restart.reason",
    "gc.restart.review_report_path",
    "gc.restart.review_fix_formula",
    "gc.restart.implementation_target",
)
CLOSED_PASS_ALLOWED_STATES = {
    "gc.build.status": {"completed"},
    "gc.build.finalize_status": {"completed"},
    "gc.build.finalize_outcome": {"success"},
    "gc.build.repair_status": {"not_needed", "approved"},
}


def closed_pass_failure_metadata(bead: Mapping[str, Any]) -> list[tuple[str, str]]:
    stale = [
        (key, metadata_value(bead, key))
        for key in CLOSED_PASS_EMPTY_METADATA
        if metadata_value(bead, key).strip()
    ]
    for key, allowed in CLOSED_PASS_ALLOWED_STATES.items():
        value = metadata_value(bead, key).strip()
        if value and value not in allowed:
            stale.append((key, value))
    return stale


def require_closed_pass_lineage_bead(bead: Mapping[str, Any], context: str) -> None:
    if str(bead.get("status") or "") != "closed" or metadata_value(bead, "gc.outcome") != "pass":
        raise GateError(f"{context} must be closed/pass")
    stale = closed_pass_failure_metadata(bead)
    if stale:
        details = ", ".join(f"{key}={value!r}" for key, value in stale)
        raise GateError(f"{context} has stale failure metadata: {details}")


def workflow_finalizers(
    beads: Sequence[Mapping[str, Any]],
    root_id: str,
) -> list[Mapping[str, Any]]:
    return sorted(
        (
            bead
            for bead in beads
            if metadata_value(bead, "gc.root_bead_id") == root_id
            and metadata_value(bead, "gc.kind") == "workflow-finalize"
            and not metadata_value(bead, "gc.attempt")
        ),
        key=lambda bead: str(bead.get("id") or ""),
    )


def terminal_nonpassing_workflow_controls(
    beads: Sequence[Mapping[str, Any]],
    root_id: str,
) -> list[Mapping[str, Any]]:
    return sorted(
        (
            bead
            for bead in beads
            if metadata_value(bead, "gc.root_bead_id") == root_id
            and metadata_value(bead, "gc.kind") in LOGICAL_CONTROL_KINDS
            and not metadata_value(bead, "gc.attempt")
            and str(bead.get("status") or "") == "closed"
            and metadata_value(bead, "gc.outcome") != "pass"
        ),
        key=lambda bead: str(bead.get("id") or ""),
    )


def session_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        payload = payload.get("sessions")
    if not isinstance(payload, list):
        return []
    return [session for session in payload if isinstance(session, Mapping)]


def session_cache_age(payload: Any) -> float:
    if not isinstance(payload, Mapping) or "_cache_age_s" not in payload:
        return 0.0
    try:
        age = float(payload["_cache_age_s"])
    except (TypeError, ValueError):
        return math.inf
    if not math.isfinite(age) or age < 0:
        return math.inf
    return age


def provider_activity_age(last_active: str, *, now: datetime | None = None) -> float | None:
    raw = last_active.strip()
    if not raw:
        return None
    try:
        observed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return max(0.0, (current - observed.astimezone(timezone.utc)).total_seconds())


def provider_log_tip(output: str) -> ProviderLogTip | None:
    payload = extract_json_payload(output)
    if not isinstance(payload, Mapping):
        return None
    transcript_path = str(payload.get("transcript_path") or "").strip()
    entries = payload.get("entries")
    if not transcript_path or not isinstance(entries, list):
        return None

    latest: Mapping[str, Any] | None = None
    for entry in reversed(entries):
        if isinstance(entry, Mapping) and str(entry.get("type") or "").strip() == "assistant":
            latest = entry
            break
    if latest is None:
        return None

    message = latest.get("message")
    model = str(message.get("model") or "").strip() if isinstance(message, Mapping) else ""
    serialized = json.dumps(latest, sort_keys=True, default=str).lower()
    terminal_error = model == "<synthetic>" and any(
        signature in serialized for signature in TERMINAL_PROVIDER_ERROR_SIGNATURES
    )
    fatal_error = ""
    if model == "<synthetic>":
        fatal_error = next(
            (
                error_class
                for error_class, signatures in FATAL_PROVIDER_ERROR_SIGNATURES
                if any(signature in serialized for signature in signatures)
            ),
            "",
        )
    entry_id = str(latest.get("uuid") or latest.get("timestamp") or "").strip()
    if not entry_id:
        entry_id = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return ProviderLogTip(
        transcript_path=transcript_path,
        entry_id=entry_id,
        synthetic=model == "<synthetic>",
        terminal_error=terminal_error,
        fatal_error=fatal_error,
        entry_at=provider_timestamp(latest.get("timestamp")),
    )


def provider_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        observed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return observed.astimezone(timezone.utc)


def raw_claude_file_fingerprint(path: Path) -> tuple[int, int, int, int, int, int] | None:
    try:
        info = path.lstat()
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o444 == 0:
        return None
    if info.st_size <= 0 or info.st_size > RAW_CLAUDE_MAX_TRANSCRIPT_BYTES:
        return None
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_mode,
    )


def raw_claude_active_branch(
    entries: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]] | None:
    nodes: dict[str, tuple[Mapping[str, Any], int]] = {}
    children: dict[str, list[str]] = {}
    for index, entry in enumerate(entries):
        entry_id = str(entry.get("uuid") or "").strip()
        if not entry_id:
            continue
        if entry_id in nodes:
            return None
        parent_value = entry.get("parentUuid")
        logical_value = entry.get("logicalParentUuid")
        if parent_value is not None and not isinstance(parent_value, str):
            return None
        if logical_value is not None and not isinstance(logical_value, str):
            return None
        nodes[entry_id] = (entry, index)
        parent_id = str(parent_value or "").strip()
        children.setdefault(parent_id, []).append(entry_id)
    if not nodes:
        return None

    def next_id(entry: Mapping[str, Any]) -> str:
        return str(entry.get("parentUuid") or entry.get("logicalParentUuid") or "").strip()

    def fallback_parent(before_index: int, visited: set[str]) -> str:
        eligible = [
            (index, entry_id)
            for entry_id, (_, index) in nodes.items()
            if index < before_index and entry_id not in visited
        ]
        return max(eligible, default=(-1, ""))[1]

    def branch_length(tip_id: str) -> int:
        count = 0
        visited: set[str] = set()
        current_id = tip_id
        while current_id and current_id not in visited:
            visited.add(current_id)
            node = nodes.get(current_id)
            if node is None:
                break
            entry, index = node
            if str(entry.get("type") or "").strip() in {"user", "assistant"}:
                count += 1
            parent_id = next_id(entry)
            if parent_id and parent_id not in nodes and entry.get("logicalParentUuid"):
                parent_id = fallback_parent(index, visited)
            current_id = parent_id
        return count

    tips = [entry_id for entry_id in nodes if not children.get(entry_id)]
    if not tips:
        return None
    tip_keys: list[tuple[datetime, int, int, str]] = []
    for entry_id in tips:
        entry, index = nodes[entry_id]
        observed = provider_timestamp(entry.get("timestamp"))
        if observed is None:
            return None
        tip_keys.append((observed, branch_length(entry_id), index, entry_id))
    active_id = max(tip_keys)[3]

    branch: list[Mapping[str, Any]] = []
    visited: set[str] = set()
    while active_id:
        if active_id in visited:
            return None
        visited.add(active_id)
        node = nodes.get(active_id)
        if node is None:
            break
        entry, index = node
        branch.append(entry)
        parent_id = next_id(entry)
        if parent_id and parent_id not in nodes and entry.get("logicalParentUuid"):
            parent_id = fallback_parent(index, visited)
        active_id = parent_id
    branch.reverse()
    return branch


def read_raw_claude_transcript(
    path: Path,
    expected_fingerprint: tuple[int, int, int, int, int, int],
) -> RawClaudeTranscript | None:
    if raw_claude_file_fingerprint(path) != expected_fingerprint:
        return None
    try:
        entries: list[Mapping[str, Any]] = []
        with path.open("r", encoding="utf-8", errors="strict") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if not isinstance(entry, Mapping):
                    return None
                entries.append(entry)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not entries or raw_claude_file_fingerprint(path) != expected_fingerprint:
        return None

    expected_session_id = path.stem
    session_ids = {
        str(entry.get("sessionId") or "").strip()
        for entry in entries
        if str(entry.get("sessionId") or "").strip()
    }
    if session_ids != {expected_session_id}:
        return None

    work_dirs = {
        str(entry.get("cwd") or "").strip()
        for entry in entries
        if str(entry.get("cwd") or "").strip()
    }
    if len(work_dirs) != 1:
        return None
    work_dir = next(iter(work_dirs))

    conversation_timestamps = [
        observed
        for entry in entries
        if str(entry.get("cwd") or "").strip() == work_dir
        for observed in (provider_timestamp(entry.get("timestamp")),)
        if observed is not None
    ]
    if not conversation_timestamps:
        return None
    conversation_started_at = min(conversation_timestamps)
    if conversation_started_at > datetime.now(timezone.utc) + timedelta(
        seconds=RAW_CLAUDE_MAX_CLOCK_SKEW
    ):
        return None

    active_branch = raw_claude_active_branch(entries)
    if active_branch is None:
        return None
    latest_assistant = next(
        (
            entry
            for entry in reversed(active_branch)
            if str(entry.get("type") or "").strip() == "assistant"
        ),
        None,
    )
    if latest_assistant is None:
        return RawClaudeTranscript(
            work_dir=work_dir,
            conversation_started_at=conversation_started_at,
            tip=None,
        )
    if str(latest_assistant.get("cwd") or "").strip() != work_dir:
        return None
    assistant_at = provider_timestamp(latest_assistant.get("timestamp"))
    if assistant_at is None or assistant_at < conversation_started_at:
        return None
    if assistant_at > datetime.now(timezone.utc) + timedelta(
        seconds=RAW_CLAUDE_MAX_CLOCK_SKEW
    ):
        return None
    tip = provider_log_tip(
        json.dumps(
            {
                "schema_version": "1",
                "transcript_path": str(path),
                "entries": [latest_assistant],
            }
        )
    )
    if tip is None:
        return None
    return RawClaudeTranscript(
        work_dir=work_dir,
        conversation_started_at=conversation_started_at,
        tip=replace(tip, conversation_started_at=conversation_started_at),
    )


def claude_project_slug(work_dir: str) -> str:
    return re.sub(r"[^A-Za-z0-9-]", "-", work_dir)


def raw_claude_transcript_paths(projects_root: Path, work_dir: str) -> list[Path] | None:
    project_dir = projects_root / claude_project_slug(work_dir)
    try:
        project_info = project_dir.lstat()
    except FileNotFoundError:
        return []
    except OSError:
        return None
    if not stat.S_ISDIR(project_info.st_mode) or project_dir.is_symlink():
        return None

    try:
        entries = sorted(project_dir.iterdir(), key=lambda candidate: candidate.name)
    except OSError:
        return None
    paths: list[Path] = []
    total_bytes = 0
    for path in entries:
        if path.suffix != ".jsonl":
            continue
        fingerprint = raw_claude_file_fingerprint(path)
        if fingerprint is None:
            return None
        total_bytes += fingerprint[2]
        if total_bytes > RAW_CLAUDE_MAX_SCAN_BYTES:
            return None
        paths.append(path)
        if len(paths) > RAW_CLAUDE_MAX_TRANSCRIPT_FILES:
            return None
    return paths


def raw_claude_session_log_tip(
    workspace: GateWorkspace,
    session: Mapping[str, Any],
    session_bead: Mapping[str, Any],
    *,
    sessions: Sequence[Mapping[str, Any]],
    cache: RawClaudeTranscriptCache,
    not_before: datetime | None = None,
) -> ProviderLogTip | None:
    if str(session_bead.get("issue_type") or "").strip() != "session":
        return None
    if metadata_value(session_bead, "provider").strip().lower() != "claude":
        return None
    session_template = str(session.get("template") or "").strip()
    if not session_template or metadata_value(session_bead, "template").strip() != session_template:
        return None

    work_dirs = {
        value
        for key in ("gc.work_dir", "work_dir")
        for value in (metadata_value(session_bead, key).strip(),)
        if value
    }
    if len(work_dirs) != 1:
        return None
    work_dir = next(iter(work_dirs))
    listed_work_dir = str(session.get("work_dir") or "").strip()
    if not listed_work_dir or listed_work_dir != work_dir:
        return None

    normalized_work_dir = os.path.normpath(work_dir)
    same_work_dir_sessions = [
        candidate
        for candidate in sessions
        if candidate.get("closed") is not True
        and str(candidate.get("state") or "").strip().lower() != "closed"
        and os.path.normpath(str(candidate.get("work_dir") or "").strip())
        == normalized_work_dir
    ]
    session_id = str(session.get("id") or "").strip()
    if (
        len(same_work_dir_sessions) != 1
        or str(same_work_dir_sessions[0].get("id") or "").strip() != session_id
    ):
        return None

    session_created_at = provider_timestamp(session_bead.get("created_at"))
    if session_created_at is None:
        return None
    paths = raw_claude_transcript_paths(
        workspace.claude_config_dir / "projects",
        work_dir,
    )
    if paths is None:
        return None

    candidates: list[RawClaudeTranscript] = []
    for path in paths:
        try:
            fingerprint = raw_claude_file_fingerprint(path)
        except OSError:
            return None
        if fingerprint is None:
            return None
        cached = cache.get(path)
        if cached is None or cached[0] != fingerprint:
            transcript = read_raw_claude_transcript(path, fingerprint)
            cache[path] = (fingerprint, transcript)
        else:
            transcript = cached[1]
        if transcript is None:
            return None
        if (
            transcript.work_dir == work_dir
            and transcript.conversation_started_at >= session_created_at
            and (not_before is None or transcript.conversation_started_at >= not_before)
        ):
            candidates.append(transcript)
    if not candidates:
        return None

    newest_started_at = max(
        transcript.conversation_started_at for transcript in candidates
    )
    newest = [
        transcript
        for transcript in candidates
        if transcript.conversation_started_at == newest_started_at
    ]
    if len(newest) != 1:
        return None
    return newest[0].tip


def workflow_lineage_root_ids(beads: Sequence[Mapping[str, Any]], root_id: str) -> set[str]:
    roots = {root_id}
    pending = [root_id]
    while pending:
        parent_id = pending.pop()
        for bead in beads:
            if (
                metadata_value(bead, "gc.root_bead_id") != parent_id
                or metadata_value(bead, "gc.kind") != "drain"
            ):
                continue
            rows = drain_manifest_rows(bead)
            if rows is None:
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                for key in ("item_root_id", "outcome_bead_id"):
                    nested_id = str(row.get(key) or "").strip()
                    if nested_id and nested_id not in roots:
                        roots.add(nested_id)
                        pending.append(nested_id)
    return roots


def workflow_preclaim_bead_ids(
    beads: Sequence[Mapping[str, Any]], workflow_roots: set[str]
) -> set[str]:
    bead_ids: set[str] = set()
    for bead in beads:
        bead_id = str(bead.get("id") or "").strip()
        if not bead_id or str(bead.get("status") or "").strip() != "open":
            continue
        if str(bead.get("assignee") or "").strip():
            continue
        if bead_id in workflow_roots or metadata_value(bead, "gc.root_bead_id") in workflow_roots:
            bead_ids.add(bead_id)
    return bead_ids


def session_assignment_identities(session: Mapping[str, Any]) -> tuple[str, ...]:
    identities = tuple(
        str(session.get(key) or "").strip()
        for key in ("id", "session_id", "session_name")
        if str(session.get(key) or "").strip()
    )
    return tuple(dedupe_strings(identities))


def workflow_claims_for_identities(
    beads: Sequence[Mapping[str, Any]],
    workflow_roots: set[str],
    identities: Sequence[str],
) -> list[Mapping[str, Any]]:
    expected = {identity.strip() for identity in identities if identity.strip()}
    if not expected:
        return []
    claims: list[Mapping[str, Any]] = []
    for bead in beads:
        if str(bead.get("status") or "").strip() != "in_progress":
            continue
        if metadata_value(bead, "gc.root_bead_id") not in workflow_roots:
            continue
        assignee = str(bead.get("assignee") or "").strip()
        session_name = metadata_value(bead, "gc.session_name").strip()
        if assignee in expected or (not assignee and session_name in expected):
            claims.append(bead)
    return claims


def run_gc_session(
    gc_bin: str,
    workspace: GateWorkspace,
    *args: str,
    env: Mapping[str, str],
    log_output: bool = False,
) -> str:
    return run_checked(
        [gc_bin, "--city", str(workspace.city_dir), "session", *args],
        env=env,
        timeout=parse_duration("30s"),
        log_output=log_output,
    )


def session_log_tip(
    gc_bin: str,
    workspace: GateWorkspace,
    session_id: str,
    *,
    env: Mapping[str, str],
) -> ProviderLogTip | None:
    try:
        output = run_gc_session(
            gc_bin, workspace, "logs", session_id, "--tail", "10", "--json", env=env
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return provider_log_tip(output)


def session_bead_snapshot(
    gc_bin: str,
    workspace: GateWorkspace,
    session_id: str,
    *,
    env: Mapping[str, str],
    event_beads_loader: Callable[[], Sequence[Mapping[str, Any]]] | None = None,
) -> Mapping[str, Any] | None:
    payload: Any | None = None
    try:
        output = run_checked(
            [
                gc_bin,
                "--city",
                str(workspace.city_dir),
                "bd",
                "show",
                session_id,
                "--json",
            ],
            env=env,
            timeout=parse_duration("30s"),
        )
        payload = extract_json_payload(output)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    candidates: Sequence[Any]
    if isinstance(payload, Mapping):
        candidates = (payload,)
    elif isinstance(payload, list):
        candidates = payload
    else:
        candidates = ()
    matches = [
        candidate
        for candidate in candidates
        if isinstance(candidate, Mapping)
        and str(candidate.get("id") or "").strip() == session_id
    ]
    if len(matches) == 1:
        return matches[0]
    event_beads = (
        event_beads_loader()
        if event_beads_loader is not None
        else list_beads_from_event_log(workspace)
    )
    return find_bead_by_id(event_beads, session_id)


def session_has_current_preclaim_trigger(
    session: Mapping[str, Any],
    session_bead: Mapping[str, Any] | None,
    beads: Sequence[Mapping[str, Any]],
    workflow_bead_ids: set[str],
    *,
    expected_store_ref: str,
) -> bool:
    if session_bead is None or str(session_bead.get("issue_type") or "").strip() != "session":
        return False
    session_template = str(session.get("template") or "").strip()
    if not session_template:
        return False
    if metadata_value(session_bead, "provider").strip().lower() != "claude":
        return False
    if metadata_value(session_bead, "template").strip() != session_template:
        return False

    trigger_bead_id = metadata_value(session_bead, "gc.trigger_bead_id").strip()
    trigger_store_ref = metadata_value(session_bead, "gc.trigger_bead_store_ref").strip()
    if trigger_store_ref != expected_store_ref or trigger_bead_id not in workflow_bead_ids:
        return False
    trigger = find_bead_by_id(beads, trigger_bead_id)
    if trigger is None:
        return False
    return (
        metadata_value(trigger, "gc.root_store_ref").strip() == expected_store_ref
        and metadata_value(trigger, "gc.routed_to").strip() == session_template
    )


def reconcile_terminal_provider_resets(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    beads: Sequence[Mapping[str, Any]],
    workflow_roots: set[str],
    sessions_by_id: Mapping[str, Mapping[str, Any]],
    resets: Mapping[str, TerminalProviderReset],
    now: float,
    raw_claude_cache: RawClaudeTranscriptCache | None = None,
    allow_raw_fallback: bool = True,
) -> None:
    if raw_claude_cache is None:
        raw_claude_cache = {}
    for session_id, reset in resets.items():
        if reset.recovery_evidence:
            continue
        remaining_claims = workflow_claims_for_identities(
            beads,
            workflow_roots,
            reset.session_identities,
        )
        remaining_ids = {str(bead.get("id") or "").strip() for bead in remaining_claims}
        if not remaining_ids.intersection(reset.claim_ids):
            reset.recovery_evidence = "claimed work completed or was released"
            continue

        tip = session_log_tip(gc_bin, workspace, session_id, env=env)
        session = sessions_by_id.get(session_id)
        if tip is None and session is not None and allow_raw_fallback:
            session_bead = session_bead_snapshot(
                gc_bin,
                workspace,
                session_id,
                env=env,
            )
            if session_bead is not None:
                tip = raw_claude_session_log_tip(
                    workspace,
                    session,
                    session_bead,
                    sessions=tuple(sessions_by_id.values()),
                    cache=raw_claude_cache,
                    not_before=reset.requested_at_utc,
                )
        observed_after_reset = tip and (
            reset.requested_at_utc is None
            or (
                (tip.conversation_started_at or tip.entry_at) is not None
                and (tip.conversation_started_at or tip.entry_at)
                >= reset.requested_at_utc
            )
        )
        if (
            tip
            and observed_after_reset
            and tip.transcript_path != reset.source_transcript_path
        ):
            if tip.fatal_error:
                raise GateError(
                    f"session {session_id} hit fatal provider error {tip.fatal_error} "
                    f"in its fresh conversation transcript {tip.transcript_path}"
                )
            if tip.terminal_error:
                raise GateError(
                    f"session {session_id} hit the same terminal provider error in its fresh conversation"
                )
            if not tip.synthetic:
                reset.recovery_evidence = (
                    f"fresh provider transcript {tip.transcript_path} at {tip.entry_id}"
                )
                continue

        if now - reset.requested_at >= TERMINAL_PROVIDER_RECOVERY_TIMEOUT:
            session_state = str((sessions_by_id.get(session_id) or {}).get("state") or "missing")
            raise GateError(
                f"session {session_id} did not produce fresh provider progress within "
                f"{TERMINAL_PROVIDER_RECOVERY_TIMEOUT:.0f}s after reset; state={session_state}"
            )


def recover_terminal_provider_sessions(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    beads: Sequence[Mapping[str, Any]],
    root_id: str,
    resets: dict[str, TerminalProviderReset],
    now: float,
    raw_claude_cache: RawClaudeTranscriptCache | None = None,
) -> None:
    if raw_claude_cache is None:
        raw_claude_cache = {}
    workflow_roots = workflow_lineage_root_ids(beads, root_id)
    workflow_bead_ids = workflow_preclaim_bead_ids(beads, workflow_roots)
    sessions: list[Mapping[str, Any]] = []
    cache_age = math.inf
    try:
        output = run_gc_session(gc_bin, workspace, "list", "--state", "all", "--json", env=env)
        payload = extract_json_payload(output)
        sessions = session_rows(payload)
        cache_age = session_cache_age(payload)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"terminal-provider watchdog could not list active sessions: {exc}", file=sys.stderr)

    sessions_by_id = {
        str(session.get("id") or "").strip(): session
        for session in sessions
        if str(session.get("id") or "").strip()
    }
    reconcile_terminal_provider_resets(
        gc_bin,
        workspace,
        env=env,
        beads=beads,
        workflow_roots=workflow_roots,
        sessions_by_id=sessions_by_id,
        resets=resets,
        now=now,
        raw_claude_cache=raw_claude_cache,
        allow_raw_fallback=cache_age <= TERMINAL_PROVIDER_MAX_SESSION_CACHE_AGE,
    )

    if cache_age > TERMINAL_PROVIDER_MAX_SESSION_CACHE_AGE:
        print(
            f"terminal-provider watchdog skipped new resets because session cache age is {cache_age:.1f}s",
            file=sys.stderr,
        )
        return

    event_beads: Sequence[Mapping[str, Any]] | None = None

    def load_event_beads_once() -> Sequence[Mapping[str, Any]]:
        nonlocal event_beads
        if event_beads is None:
            try:
                event_beads = list_beads_from_event_log(workspace)
            except OSError as exc:
                print(
                    f"terminal-provider watchdog could not read event-log session fallback: {exc}",
                    file=sys.stderr,
                )
                event_beads = ()
        return event_beads

    for session in sessions:
        session_id = str(session.get("id") or "").strip()
        state = str(session.get("state") or "").strip().lower()
        last_active = str(session.get("last_active") or "").strip()
        if (
            not session_id
            or session_id in resets
            or state not in {"active", "awake"}
            or session.get("attached") is True
        ):
            continue

        identities = session_assignment_identities(session)
        claims = workflow_claims_for_identities(beads, workflow_roots, identities)
        age = provider_activity_age(last_active)
        if age is None or age < TERMINAL_PROVIDER_STALE_AFTER:
            continue
        session_bead: Mapping[str, Any] | None = None
        if not claims:
            session_bead = session_bead_snapshot(
                gc_bin,
                workspace,
                session_id,
                env=env,
                event_beads_loader=load_event_beads_once,
            )
            if not session_has_current_preclaim_trigger(
                session,
                session_bead,
                beads,
                workflow_bead_ids,
                expected_store_ref=f"rig:{workspace.rig_name}",
            ):
                continue

        tip = session_log_tip(gc_bin, workspace, session_id, env=env)
        if tip is None:
            if session_bead is None:
                session_bead = session_bead_snapshot(
                    gc_bin,
                    workspace,
                    session_id,
                    env=env,
                    event_beads_loader=load_event_beads_once,
                )
            if session_bead is not None:
                tip = raw_claude_session_log_tip(
                    workspace,
                    session,
                    session_bead,
                    sessions=sessions,
                    cache=raw_claude_cache,
                )
        if tip is None:
            continue
        if tip.fatal_error:
            raise GateError(
                f"session {session_id} hit fatal provider error {tip.fatal_error} "
                f"in transcript {tip.transcript_path}"
            )
        if not claims or not tip.terminal_error:
            continue

        try:
            run_gc_session(
                gc_bin, workspace, "reset", session_id, "--json", env=env, log_output=True
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise GateError(f"could not fresh-reset terminal provider session {session_id}: {exc}") from exc
        resets[session_id] = TerminalProviderReset(
            requested_at=now,
            source_transcript_path=tip.transcript_path,
            claim_ids=tuple(str(bead.get("id") or "").strip() for bead in claims),
            session_identities=identities,
            requested_at_utc=datetime.now(timezone.utc),
            source_conversation_started_at=tip.conversation_started_at,
        )
        print(
            f"terminal-provider watchdog: requested one fresh reset for session {session_id}",
            flush=True,
        )


def wait_for_workflow_pass(
    gc_bin: str,
    workspace: GateWorkspace,
    root_id: str,
    *,
    env: Mapping[str, str],
    timeout: float,
    poll_interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_bead: dict[str, Any] | None = None
    terminal_provider_resets: dict[str, TerminalProviderReset] = {}
    raw_claude_cache: RawClaudeTranscriptCache = {}
    next_terminal_provider_scan = 0.0
    while time.monotonic() < deadline:
        last_bead = show_bead(gc_bin, workspace, root_id, env=env)
        status = str(last_bead.get("status") or "")
        outcome = metadata_value(last_bead, "gc.outcome")
        print(f"workflow {root_id}: status={status or '<unset>'} outcome={outcome or '<unset>'}", flush=True)
        beads = list_beads(gc_bin, workspace, env=env)
        failed_controls = terminal_nonpassing_workflow_controls(beads, root_id)
        if failed_controls:
            failures = ", ".join(
                f"{bead.get('id', '<unknown>')} "
                f"({metadata_value(bead, 'gc.step_ref') or bead.get('title', '<untitled>')})"
                for bead in failed_controls
            )
            raise GateError(
                f"workflow {root_id} cannot pass: logical workflow control failed: {failures}\n"
                + collect_diagnostics(gc_bin, workspace, env=env)
            )
        if status == "closed":
            if outcome == "pass":
                finalizers = workflow_finalizers(beads, root_id)
                if not finalizers:
                    print(f"workflow {root_id}: waiting for workflow-finalize control", flush=True)
                elif any(str(bead.get("status") or "") != "closed" for bead in finalizers):
                    states = ", ".join(
                        f"{bead.get('id', '<unknown>')}={bead.get('status', '<unset>')}" for bead in finalizers
                    )
                    print(f"workflow {root_id}: waiting for workflow-finalize controls ({states})", flush=True)
                else:
                    try:
                        validate_workflow_lineage(beads, root_id)
                    except GateError as exc:
                        raise GateError(
                            f"{exc}\n"
                            + collect_diagnostics(gc_bin, workspace, env=env)
                        ) from exc

                    stale_markers = closed_pass_failure_metadata(last_bead)
                    if stale_markers:
                        details = ", ".join(f"{key}={value!r}" for key, value in stale_markers)
                        raise GateError(
                            f"workflow {root_id} closed/pass with stale failure metadata: {details}\n"
                            + collect_diagnostics(gc_bin, workspace, env=env)
                        )
                    return last_bead
                now = time.monotonic()
                if now >= next_terminal_provider_scan:
                    recover_terminal_provider_sessions(
                        gc_bin,
                        workspace,
                        env=env,
                        beads=beads,
                        root_id=root_id,
                        resets=terminal_provider_resets,
                        now=now,
                        raw_claude_cache=raw_claude_cache,
                    )
                    next_terminal_provider_scan = now + TERMINAL_PROVIDER_SCAN_INTERVAL
                time.sleep(poll_interval)
                continue
            raise GateError(
                f"workflow {root_id} closed with gc.outcome={outcome!r}, want 'pass'\n"
                + collect_diagnostics(gc_bin, workspace, env=env)
            )
        now = time.monotonic()
        if now >= next_terminal_provider_scan:
            recover_terminal_provider_sessions(
                gc_bin,
                workspace,
                env=env,
                beads=beads,
                root_id=root_id,
                resets=terminal_provider_resets,
                now=now,
                raw_claude_cache=raw_claude_cache,
            )
            next_terminal_provider_scan = now + TERMINAL_PROVIDER_SCAN_INTERVAL
        time.sleep(poll_interval)
    raise GateError(
        f"timed out after {timeout:.0f}s waiting for workflow {root_id} and its finalizer to pass; "
        f"last bead={last_bead!r}\n"
        + collect_diagnostics(gc_bin, workspace, env=env)
    )


def collect_diagnostics(gc_bin: str, workspace: GateWorkspace, *, env: Mapping[str, str]) -> str:
    sections: list[str] = []
    commands = [
        ("sessions", [gc_bin, "--city", str(workspace.city_dir), "session", "list", "--state", "all"]),
        (
            "rig beads",
            [
                gc_bin,
                "--city",
                str(workspace.city_dir),
                "--rig",
                workspace.rig_name,
                "bd",
                "list",
                "--all",
                "--json",
                "--limit",
                BD_LIST_LIMIT,
            ],
        ),
    ]
    for label, command in commands:
        try:
            output = run_checked(command, env=env, timeout=parse_duration("30s"))
        except Exception as exc:  # pragma: no cover - diagnostic best effort
            output = f"{type(exc).__name__}: {exc}"
        sections.append(f"== {label} ==\n{output}")
    beads_path = workspace.rig_dir / ".gc" / "beads.json"
    if beads_path.exists():
        sections.append(f"== {beads_path} ==\n{beads_path.read_text(encoding='utf-8', errors='replace')}")
    for path in (
        workspace.city_dir / ".gc" / "runtime" / "control-dispatcher-trace.log",
        workspace.city_dir / "graph-workflow-trace.log",
        workspace.gc_home / "supervisor.log",
    ):
        if path.exists():
            sections.append(f"== {path} ==\n{path.read_text(encoding='utf-8', errors='replace')[-12000:]}")
    return "\n".join(sections)


def validate_review_report(
    root_bead: Mapping[str, Any],
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    pack_spec: PackSpec,
) -> None:
    validator = pack_spec.validator_source / "assets" / "scripts" / "validate_build_artifact.py"
    if not validator.is_file():
        raise GateError(f"review artifact validator was not found: {validator}")

    requested_report_path = (workspace.rig_dir / REVIEW_REPORT_PATH).resolve()
    root_report_path_raw = metadata_value(root_bead, "gc.var.report_path")
    root_report_path = Path(root_report_path_raw)
    if not root_report_path.is_absolute():
        raise GateError(
            "review workflow root gc.var.report_path must be the absolute adapter report path; "
            f"got {root_report_path_raw!r}"
        )
    if root_report_path != requested_report_path:
        raise GateError(
            f"review workflow root gc.var.report_path {root_report_path} does not match requested adapter report "
            f"{requested_report_path}"
        )
    if not requested_report_path.is_file():
        raise GateError(f"requested review report is missing: {requested_report_path}")

    allow_approved = pack_spec.name != GASCITY_PACK
    validate_review_artifact_file(
        requested_report_path,
        label="requested review report",
        validator=validator,
        env=env,
        allow_approved=allow_approved,
        upstream_roots=(workspace.rig_dir,),
    )

    subject_path = (workspace.rig_dir / REVIEW_SUBJECT_PATH).resolve()
    require_canonical_review_subject_trace(requested_report_path, subject_path)

    if pack_spec.name in METHODOLOGY_FLOW_CONTRACTS:
        internal_path_raw = metadata_value(root_bead, "gc.build.code_review_report_path")
        if not internal_path_raw:
            raise GateError(
                "methodology review root is missing internal review report metadata "
                "gc.build.code_review_report_path"
            )
        internal_path = resolve_artifact_path(internal_path_raw, base=workspace.rig_dir)
        internal_path = internal_path.resolve()
        if internal_path == requested_report_path:
            raise GateError(
                "methodology internal and adapter review report paths must be distinct: "
                f"internal={internal_path} adapter={requested_report_path}"
            )
        try:
            internal_path.relative_to(workspace.rig_dir.resolve())
        except ValueError as exc:
            raise GateError(
                "methodology internal review report must stay inside the nightly rig: "
                f"internal={internal_path} rig={workspace.rig_dir.resolve()}"
            ) from exc
        if not internal_path.is_file():
            raise GateError(f"internal review report is missing: {internal_path}")
        if os.path.samefile(internal_path, requested_report_path):
            raise GateError(
                "methodology internal and adapter review report paths must be distinct: "
                f"internal={internal_path} adapter={requested_report_path}"
            )
        validate_review_artifact_file(
            internal_path,
            label="internal review report",
            validator=validator,
            env=env,
            allow_approved=allow_approved,
            upstream_roots=(workspace.rig_dir,),
        )
        require_canonical_review_subject_trace(internal_path, subject_path)
        if internal_path.read_bytes() != requested_report_path.read_bytes():
            raise GateError(
                "methodology internal and adapter review reports must be byte-identical: "
                f"internal={internal_path} adapter={requested_report_path}"
            )
    print(f"validated review report: {requested_report_path}", flush=True)


def validate_review_artifact_file(
    report_path: Path,
    *,
    label: str,
    validator: Path,
    env: Mapping[str, str],
    allow_approved: bool,
    upstream_roots: Sequence[Path],
) -> None:
    try:
        command = [
            sys.executable,
            str(validator),
            "--schema",
            "gc.build.review.v1",
            "--path",
            str(report_path),
            "--verify-absolute-upstreams",
        ]
        for root in upstream_roots:
            command.extend(("--upstream-root", str(root.resolve(strict=True))))
        run_checked(
            command,
            env=env,
            timeout=parse_duration("1m"),
            log_output=True,
        )
        require_expected_review_signal(report_path, allow_approved=allow_approved)
    except (GateError, subprocess.CalledProcessError) as exc:
        raise GateError(
            f"review gate did not produce a valid expected review artifact at {label} {report_path}: {exc}"
        ) from exc


def artifact_front_matter(artifact_path: Path, *, label: str) -> Mapping[str, Any]:
    text = artifact_path.read_text(encoding="utf-8", errors="strict")
    match = re.match(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        raise GateError(f"{label} has no parseable front matter: {artifact_path}")
    try:
        front_matter = yaml.safe_load(match.group("front")) or {}
    except yaml.YAMLError as exc:
        raise GateError(f"{label} front matter is invalid at {artifact_path}: {exc}") from exc
    if not isinstance(front_matter, Mapping):
        raise GateError(f"{label} front matter must be a mapping at {artifact_path}")
    return front_matter


def require_canonical_review_subject_trace(report_path: Path, subject_path: Path) -> None:
    if not subject_path.is_file():
        raise GateError(f"canonical review subject is missing: {subject_path}")

    front_matter = artifact_front_matter(report_path, label="review report")
    trace = front_matter.get("trace")
    upstream = trace.get("upstream") if isinstance(trace, dict) else None
    if not isinstance(upstream, list):
        raise GateError(f"review report trace.upstream is missing at {report_path}")

    expected_hash = f"sha256:{hashlib.sha256(subject_path.read_bytes()).hexdigest()}"
    matching_entries: list[Mapping[str, Any]] = []
    for entry in upstream:
        if not isinstance(entry, Mapping):
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        traced_path = Path(raw_path.strip())
        path_matches = traced_path.is_absolute() and traced_path.resolve() == subject_path
        if path_matches:
            matching_entries.append(entry)

    observed_hashes = [str(entry.get("hash") or "") for entry in matching_entries]
    if expected_hash not in observed_hashes:
        raise GateError(
            "review report must trace the canonical review subject digest exactly: "
            f"report={report_path} subject={subject_path} expected={expected_hash} observed={observed_hashes}"
        )


def require_expected_review_signal(report_path: Path, *, allow_approved: bool = False) -> None:
    text = report_path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    has_risk = "shell" in lower and "injection" in lower and "subprocess" in lower
    has_blocking_status = re.search(r"(?m)^status:\s*(changes_required|blocked)\s*$", text) is not None
    has_approved_status = re.search(r"(?m)^status:\s*approved\s*$", text) is not None
    has_resolution = any(
        marker in lower
        for marker in (
            "shell=false",
            "argument-vector",
            "argument vector",
            "argument list",
            "resolved",
            "covered",
            "fixed",
        )
    )
    has_status = has_blocking_status or (allow_approved and has_approved_status and has_resolution)
    if not has_status or not has_risk:
        raise GateError(
            "review report did not identify and handle the expected shell-injection risk. "
            f"status_ok={has_status} risk_ok={has_risk} resolution_ok={has_resolution} report={report_path}"
        )


def validate_build_basic_result(
    rig_dir: Path,
    beads: Sequence[Mapping[str, Any]],
    *,
    root_bead: Mapping[str, Any],
    expected_member_ids: Sequence[str],
    launcher_commit: str,
    env: Mapping[str, str],
    timeout: float,
    validator_source: Path,
) -> list[Path]:
    validated: list[tuple[str, str, Path, Path]] = []
    observed_commits: set[str] = set()
    observed_summaries: set[Path] = set()
    observed_worktrees: set[Path] = set()
    rig_root = rig_dir.resolve()
    launcher_common_dir = git_common_dir(rig_root, context="launcher rig")
    baseline_tests = launcher_baseline_tests(rig_root, launcher_commit)
    for member_id, workflow_root_id in build_basic_implementation_members(
        root_bead, beads, expected_member_ids
    ):
        matches = [bead for bead in beads if bead.get("id") == member_id]
        if len(matches) != 1:
            raise GateError(
                f"implementation member {member_id} must have exactly one authoritative bead; "
                f"observed {len(matches)}"
            )
        member = matches[0]
        if str(member.get("status") or "") != "closed" or metadata_value(member, "gc.outcome") != "pass":
            raise GateError(
                f"implementation member {member_id} must be closed/pass; "
                f"status={member.get('status')!r} outcome={metadata_value(member, 'gc.outcome')!r}"
            )

        worktree = authoritative_member_worktree(member, member_id, rig_root, launcher_common_dir)
        if worktree in observed_worktrees:
            raise GateError(
                "authoritative implementation worktrees must be distinct: "
                f"member={member_id} worktree={worktree}"
            )
        observed_worktrees.add(worktree)
        commit = resolved_member_commit(member, member_id, worktree)
        if commit in observed_commits:
            raise GateError(
                "authoritative implementation commits must be distinct: "
                f"member={member_id} commit={commit}"
            )
        observed_commits.add(commit)
        committed_products = validate_committed_product_bytes(
            member_id,
            worktree,
            commit,
            baseline_tests=baseline_tests,
        )

        slugger = worktree / "slugger.py"
        if "NotImplementedError" in slugger.read_text(encoding="utf-8", errors="replace"):
            raise GateError(f"implementation member {member_id} slugger.py still contains NotImplementedError")

        summary_path = member_summary_path(member, member_id, worktree)
        if summary_path in observed_summaries:
            raise GateError(
                f"implementation member {member_id} must use a distinct gc.implementation.summary_path: "
                f"{summary_path}"
            )
        observed_summaries.add(summary_path)
        validate_build_artifact_schema(
            summary_path,
            schema="gc.build.implementation-summary.v1",
            validator_source=validator_source,
            env=env,
            context=f"implementation member {member_id} summary",
            upstream_roots=(worktree,),
        )
        validate_member_implementation_summary(
            summary_path,
            member_id=member_id,
            workflow_root_id=workflow_root_id,
        )

        validate_committed_pytest(member_id, committed_products, commit, env=env, timeout=timeout)

        validated.append((member_id, workflow_root_id, worktree, summary_path))
        print(f"validated build-basic implementation member {member_id}: {worktree}", flush=True)

    validate_canonical_implementation_summary(
        root_bead,
        validated,
        rig_dir=rig_dir,
    )
    return [worktree for _, _, worktree, _ in validated]


def implementation_convoy_member_ids(
    gc_bin: str,
    workspace: GateWorkspace,
    root_bead: Mapping[str, Any],
    *,
    env: Mapping[str, str],
) -> list[str]:
    convoy_id = metadata_value(root_bead, "gc.build.implementation_convoy_id").strip()
    if not convoy_id:
        raise GateError("build-basic root is missing gc.build.implementation_convoy_id")
    output = run_checked(
        [
            gc_bin,
            "--city",
            str(workspace.city_dir),
            "--rig",
            workspace.rig_name,
            "convoy",
            "status",
            convoy_id,
            "--json",
        ],
        env=env,
        timeout=parse_duration("30s"),
    )
    return convoy_status_member_ids(extract_json_payload(output), convoy_id)


def convoy_status_member_ids(payload: Any, convoy_id: str) -> list[str]:
    if not isinstance(payload, Mapping):
        raise GateError(f"gc convoy status {convoy_id} did not return an object")
    convoy = payload.get("convoy")
    if not isinstance(convoy, Mapping) or str(convoy.get("id") or "") != convoy_id:
        raise GateError(f"gc convoy status {convoy_id} returned a different convoy")
    if str(convoy.get("status") or "") != "closed":
        raise GateError(f"implementation convoy {convoy_id} must have status=closed")

    children = payload.get("children")
    if not isinstance(children, list) or not children:
        raise GateError(f"implementation convoy {convoy_id} must have non-empty children")
    member_ids: list[str] = []
    for index, child in enumerate(children):
        member_id = str(child.get("id") or "").strip() if isinstance(child, Mapping) else ""
        if not member_id:
            raise GateError(f"implementation convoy child {index} must have a non-empty id")
        if str(child.get("status") or "") != "closed":
            raise GateError(f"implementation convoy child {member_id} must be closed")
        if child.get("dangling_track") is True:
            raise GateError(f"implementation convoy child {member_id} has a dangling track")
        member_ids.append(member_id)
    if len(set(member_ids)) != len(member_ids):
        raise GateError(f"implementation convoy must have unique child ids: {member_ids}")

    progress = payload.get("progress")
    if not isinstance(progress, Mapping):
        raise GateError(f"implementation convoy {convoy_id} omitted progress")
    if progress.get("dangling_tracks", 0) != 0:
        raise GateError(f"implementation convoy {convoy_id} has dangling tracks")
    if progress.get("total") != len(member_ids):
        raise GateError(
            f"implementation convoy progress.total must equal child count {len(member_ids)}: "
            f"{progress.get('total')!r}"
        )
    if progress.get("closed") != len(member_ids):
        raise GateError(
            f"implementation convoy progress.closed must equal child count {len(member_ids)}: "
            f"{progress.get('closed')!r}"
        )
    return member_ids


def build_basic_implementation_members(
    root_bead: Mapping[str, Any],
    beads: Sequence[Mapping[str, Any]],
    expected_member_ids: Sequence[str],
) -> list[tuple[str, str]]:
    expected_ids = [str(member_id).strip() for member_id in expected_member_ids]
    if any(not member_id for member_id in expected_ids) or len(set(expected_ids)) != len(expected_ids):
        raise GateError(f"implementation convoy child ids must be non-empty and unique: {expected_ids}")
    root_id = str(root_bead.get("id") or "").strip()
    convoy_id = metadata_value(root_bead, "gc.build.implementation_convoy_id").strip()
    if not root_id or not convoy_id:
        raise GateError("build-basic root requires id and gc.build.implementation_convoy_id")

    drains = [
        bead
        for bead in beads
        if metadata_value(bead, "gc.root_bead_id") == root_id
        and metadata_value(bead, "gc.kind") == "drain"
        and metadata_value(bead, "gc.drain_parent_convoy_id") == convoy_id
    ]
    if len(drains) != 1:
        raise GateError(
            f"build-basic root {root_id} requires exactly one drain manifest for implementation convoy "
            f"{convoy_id}; observed {len(drains)}"
        )
    drain = drains[0]
    if str(drain.get("status") or "") != "closed" or metadata_value(drain, "gc.outcome") != "pass":
        raise GateError(f"implementation drain {drain.get('id', '<unknown>')} must be closed/pass")
    if metadata_value(drain, "gc.drain_state") != "succeeded":
        raise GateError("implementation drain must record gc.drain_state=succeeded")

    rows = drain_manifest_rows(drain)
    if not rows:
        raise GateError("implementation drain must have a valid non-empty gc.drain_manifest.v1")
    raw_count = metadata_value(drain, "gc.drain_count")
    try:
        drain_count = int(raw_count)
    except ValueError as exc:
        raise GateError(f"implementation drain has invalid gc.drain_count={raw_count!r}") from exc
    if drain_count != len(rows) or drain_count != len(expected_ids):
        raise GateError(
            f"implementation drain gc.drain_count must match manifest and convoy: "
            f"count={drain_count} rows={len(rows)} convoy={len(expected_ids)}"
        )

    members: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise GateError(f"implementation drain manifest row {index} must be an object")
        member_id = str(row.get("member_id") or "").strip()
        if not member_id:
            raise GateError(f"implementation drain manifest row {index} is missing member_id")
        if str(row.get("status") or "") != "succeeded":
            raise GateError(f"implementation drain manifest row {index} must have status=succeeded")
        if str(row.get("outcome_kind") or "") != "pass":
            raise GateError(f"implementation drain manifest row {index} must have outcome_kind=pass")
        root_ids = {
            str(row.get(key) or "").strip()
            for key in ("item_root_id", "outcome_bead_id")
            if str(row.get(key) or "").strip()
        }
        if len(root_ids) != 1:
            raise GateError(
                f"implementation drain manifest row {index} must identify one consistent workflow root"
            )
        members.append((member_id, root_ids.pop()))

    manifest_ids = [member_id for member_id, _ in members]
    if len(set(manifest_ids)) != len(manifest_ids):
        raise GateError(f"implementation drain manifest member ids must be unique: {manifest_ids}")
    if set(manifest_ids) != set(expected_ids):
        raise GateError(
            f"implementation convoy children do not match drain manifest members: "
            f"convoy={expected_ids} manifest={manifest_ids}"
        )
    workflow_ids = [workflow_id for _, workflow_id in members]
    if len(set(workflow_ids)) != len(workflow_ids):
        raise GateError(
            f"implementation drain manifest workflow root ids must be unique: {workflow_ids}"
        )

    drain_id = str(drain.get("id") or "").strip()
    for member_id, workflow_id in members:
        workflow_matches = [bead for bead in beads if bead.get("id") == workflow_id]
        if len(workflow_matches) != 1:
            raise GateError(
                f"implementation workflow root {workflow_id} must be present exactly once; "
                f"observed {len(workflow_matches)}"
            )
        workflow = workflow_matches[0]
        if metadata_value(workflow, "gc.kind") != "workflow":
            raise GateError(f"implementation workflow root {workflow_id} must record gc.kind=workflow")
        workflow_member_id = metadata_value(workflow, "gc.drain_member_id").strip()
        if workflow_member_id != member_id:
            raise GateError(
                f"implementation workflow root {workflow_id} gc.drain_member_id={workflow_member_id!r} "
                f"does not match manifest member {member_id}"
            )
        workflow_drain_id = metadata_value(workflow, "gc.drain_control_id").strip()
        if workflow_drain_id != drain_id:
            raise GateError(
                f"implementation workflow root {workflow_id} gc.drain_control_id={workflow_drain_id!r} "
                f"does not match implementation drain {drain_id}"
            )

    by_id = {member_id: workflow_id for member_id, workflow_id in members}
    return [(member_id, by_id[member_id]) for member_id in expected_ids]


def authoritative_member_worktree(
    member: Mapping[str, Any],
    member_id: str,
    rig_dir: Path,
    launcher_common_dir: Path,
) -> Path:
    worktree = required_member_path(member, member_id, "work_dir")
    if not worktree.is_dir():
        raise GateError(f"implementation member {member_id} work_dir is not a directory: {worktree}")
    if worktree == rig_dir:
        raise GateError(f"implementation member {member_id} work_dir must differ from launcher rig: {worktree}")
    try:
        worktree.relative_to(rig_dir)
    except ValueError as exc:
        raise GateError(
            f"implementation member {member_id} worktree must stay inside launcher rig: {worktree}"
        ) from exc

    for key in (
        "gc.implementation.work_dir",
        "gc.implementation.worktree_path",
        "gc.build.implementation_worktree_path",
    ):
        explicit = metadata_value(member, key).strip()
        if not explicit:
            continue
        if not Path(explicit).is_absolute() or Path(explicit).resolve() != worktree:
            raise GateError(
                f"implementation member {member_id} explicit {key} does not agree with authoritative work_dir: "
                f"{explicit!r} != {worktree}"
            )

    repository_root = git_output(worktree, "rev-parse", "--show-toplevel", context=f"member {member_id} worktree")
    if Path(repository_root.strip()).resolve() != worktree:
        raise GateError(
            f"implementation member {member_id} work_dir is not the root of its git worktree: "
            f"{worktree} != {repository_root.strip()}"
        )
    worktree_common_dir = git_common_dir(worktree, context=f"implementation member {member_id}")
    if worktree_common_dir != launcher_common_dir:
        raise GateError(
            f"implementation member {member_id} worktree is not linked to launcher repository: "
            f"worktree={worktree_common_dir} launcher={launcher_common_dir}"
        )
    expected_suffix = Path("worktrees") / member_id
    if worktree.parent.name != "worktrees" or worktree.name != member_id:
        raise GateError(
            f"implementation member {member_id} worktree must end with runtime-issued path {expected_suffix}: "
            f"observed={worktree}"
        )
    return worktree


def required_member_path(member: Mapping[str, Any], member_id: str, key: str) -> Path:
    raw = metadata_value(member, key).strip()
    if not raw:
        raise GateError(f"implementation member {member_id} is missing {key}")
    path = Path(raw)
    if not path.is_absolute():
        raise GateError(f"implementation member {member_id} {key} must be absolute: {raw!r}")
    try:
        return path.resolve(strict=True)
    except OSError as exc:
        raise GateError(f"implementation member {member_id} {key} cannot be resolved: {raw!r}") from exc


def resolved_member_commit(member: Mapping[str, Any], member_id: str, worktree: Path) -> str:
    recorded = metadata_value(member, "gc.implementation.commit").strip()
    if not recorded:
        raise GateError(f"implementation member {member_id} is missing gc.implementation.commit")
    if re.fullmatch(r"[0-9a-fA-F]+", recorded) is None:
        raise GateError(
            f"implementation member {member_id} gc.implementation.commit must be a hexadecimal commit id: "
            f"{recorded!r}"
        )
    head = git_output(worktree, "rev-parse", "HEAD", context=f"member {member_id} HEAD").strip()
    if recorded != head:
        raise GateError(
            f"implementation member {member_id} gc.implementation.commit must equal the full worktree HEAD: "
            f"recorded={recorded} HEAD={head}"
        )
    return head


def launcher_baseline_tests(rig_dir: Path, launcher_commit: str) -> bytes:
    current_head = git_output(rig_dir, "rev-parse", "HEAD", context="launcher HEAD").strip()
    if current_head != launcher_commit:
        raise GateError(
            f"launcher HEAD changed after launch: expected={launcher_commit} observed={current_head}"
        )
    relative_path = "tests/test_slugger.py"
    baseline = git_output_bytes(
        rig_dir,
        "show",
        f"{launcher_commit}:{relative_path}",
        context=f"launcher baseline {relative_path}",
    )
    test_path = rig_dir / relative_path
    if not test_path.is_file() or test_path.read_bytes() != baseline:
        raise GateError(f"launcher baseline {relative_path} bytes differ from launcher HEAD {launcher_commit}")
    return baseline


def validate_committed_product_bytes(
    member_id: str,
    worktree: Path,
    commit: str,
    *,
    baseline_tests: bytes,
) -> dict[str, bytes]:
    committed_products: dict[str, bytes] = {}
    for relative_path in BUILD_BASIC_PRODUCT_PATHS:
        product_path = worktree / relative_path
        if not product_path.is_file():
            raise GateError(f"implementation member {member_id} is missing {relative_path} in {worktree}")
        committed = git_output_bytes(
            worktree,
            "show",
            f"{commit}:{relative_path}",
            context=f"member {member_id} committed {relative_path}",
        )
        if product_path.read_bytes() != committed:
            raise GateError(
                f"implementation member {member_id} {relative_path} bytes differ from recorded commit {commit}"
            )
        if relative_path == "tests/test_slugger.py" and committed != baseline_tests:
            raise GateError(
                f"implementation member {member_id} committed tests/test_slugger.py differs from launcher baseline"
            )
        committed_products[relative_path] = committed
    return committed_products


def validate_committed_pytest(
    member_id: str,
    committed_products: Mapping[str, bytes],
    commit: str,
    *,
    env: Mapping[str, str],
    timeout: float,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"gascity-build-proof-{member_id}-") as raw_fixture:
        fixture = Path(raw_fixture)
        for relative_path, contents in committed_products.items():
            target = fixture / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)
        proof_env = dict(env)
        proof_env["PYTHONDONTWRITEBYTECODE"] = "1"
        proof_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        try:
            run_checked(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-c",
                    os.devnull,
                    f"--rootdir={fixture}",
                    f"--confcutdir={fixture}",
                    "-p",
                    "no:cacheprovider",
                ],
                cwd=fixture,
                env=proof_env,
                timeout=timeout,
                log_output=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise GateError(f"implementation member {member_id} pytest failed at recorded commit {commit}: {exc}") from exc


def member_summary_path(member: Mapping[str, Any], member_id: str, worktree: Path) -> Path:
    summary_path = required_member_path(member, member_id, "gc.implementation.summary_path")
    if not summary_path.is_file():
        raise GateError(f"implementation member {member_id} summary is not a file: {summary_path}")
    try:
        summary_path.relative_to(worktree)
    except ValueError as exc:
        raise GateError(
            f"implementation member {member_id} summary must be inside its authoritative worktree: "
            f"summary={summary_path} worktree={worktree}"
        ) from exc
    return summary_path


def git_output(worktree: Path, *args: str, context: str) -> str:
    return git_output_bytes(worktree, *args, context=context).decode("utf-8", errors="strict")


def git_common_dir(worktree: Path, *, context: str) -> Path:
    raw = git_output(
        worktree,
        "rev-parse",
        "--path-format=absolute",
        "--git-common-dir",
        context=f"{context} git common dir",
    ).strip()
    return Path(raw).resolve(strict=True)


def git_output_bytes(worktree: Path, *args: str, context: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=worktree,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GateError(f"git failed while validating {context}: {detail or f'exit {result.returncode}'}")
    return result.stdout


def validate_build_artifact_schema(
    artifact_path: Path,
    *,
    schema: str,
    validator_source: Path,
    env: Mapping[str, str],
    context: str,
    upstream_roots: Sequence[Path] = (),
    enforce_review_status_coverage: bool = False,
) -> None:
    validator = validator_source / "assets" / "scripts" / "validate_build_artifact.py"
    if not validator.is_file():
        raise GateError(f"build artifact validator was not found: {validator}")
    try:
        command = [
            sys.executable,
            str(validator),
            "--schema",
            schema,
            "--path",
            str(artifact_path),
            "--verify-absolute-upstreams",
        ]
        if enforce_review_status_coverage:
            command.append("--enforce-review-status-coverage")
        for root in upstream_roots:
            command.extend(("--upstream-root", str(root.resolve(strict=True))))
        run_checked(
            command,
            env=env,
            timeout=parse_duration("1m"),
            log_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise GateError(f"{context} failed validation for schema {schema} at {artifact_path}: {exc}") from exc


def validate_canonical_implementation_summary(
    root_bead: Mapping[str, Any],
    members: Sequence[tuple[str, str, Path, Path]],
    *,
    rig_dir: Path,
) -> None:
    root_id = str(root_bead.get("id") or "<unknown>")
    raw_path = metadata_value(root_bead, "gc.build.implementation_summary_path").strip()
    if not raw_path:
        raise GateError(f"build-basic root {root_id} is missing gc.build.implementation_summary_path")
    summary_path = resolve_artifact_path(raw_path, base=rig_dir).resolve()
    if not summary_path.is_file():
        raise GateError(f"canonical implementation summary is missing: {summary_path}")
    upstream = build_artifact_upstream(summary_path)

    for member_id, _, _, member_summary in members:
        exact_path = str(member_summary)
        matching = [entry for entry in upstream if entry.get("path") == exact_path]
        if len(matching) != 1:
            observed_paths = [str(entry.get("path") or "") for entry in upstream]
            raise GateError(
                f"implementation member {member_id} canonical implementation summary must trace "
                f"its summary at the exact path {exact_path}; observed={observed_paths}"
            )
        expected_digest = f"sha256:{hashlib.sha256(member_summary.read_bytes()).hexdigest()}"
        observed_digest = str(matching[0].get("hash") or "")
        if observed_digest != expected_digest:
            raise GateError(
                f"implementation member {member_id} canonical implementation summary digest mismatch: "
                f"path={exact_path} expected={expected_digest} observed={observed_digest!r}"
            )


def validate_member_implementation_summary(
    summary_path: Path,
    *,
    member_id: str,
    workflow_root_id: str,
) -> None:
    front_matter = artifact_front_matter(
        summary_path,
        label=f"implementation member {member_id} summary",
    )
    workflow = front_matter.get("workflow")
    observed_workflow_id = workflow.get("id") if isinstance(workflow, Mapping) else None
    if observed_workflow_id != workflow_root_id:
        raise GateError(
            f"implementation member {member_id} summary workflow.id must equal {workflow_root_id}; "
            f"observed={observed_workflow_id!r}"
        )

    upstream = artifact_upstream(
        front_matter,
        artifact_path=summary_path,
        label=f"implementation member {member_id} summary",
    )
    expected_path = f"beads/{member_id}"
    expected_hash = f"bead:{member_id}"
    identity_entries = [
        entry
        for entry in upstream
        if entry.get("path") == expected_path or entry.get("hash") == expected_hash
    ]
    identity = identity_entries[0] if len(identity_entries) == 1 else None
    if identity is None or (identity.get("path"), identity.get("hash")) != (expected_path, expected_hash):
        observed = [(entry.get("path"), entry.get("hash")) for entry in upstream]
        raise GateError(
            f"implementation member {member_id} summary must trace exactly one identity entry with "
            f"path {expected_path} and hash {expected_hash}; observed={observed}"
        )


def build_artifact_upstream(artifact_path: Path) -> list[Mapping[str, Any]]:
    return artifact_upstream(
        artifact_front_matter(artifact_path, label="build artifact"),
        artifact_path=artifact_path,
        label="build artifact",
    )


def artifact_upstream(
    front_matter: Mapping[str, Any],
    *,
    artifact_path: Path,
    label: str,
) -> list[Mapping[str, Any]]:
    trace = front_matter.get("trace")
    upstream = trace.get("upstream") if isinstance(trace, Mapping) else None
    if not isinstance(upstream, list):
        raise GateError(f"{label} trace.upstream is missing at {artifact_path}")
    return [entry for entry in upstream if isinstance(entry, Mapping)]


def validate_build_basic_source_provenance(
    root_bead: Mapping[str, Any],
    *,
    source_id: str,
    rig_dir: Path,
) -> None:
    root_id = str(root_bead.get("id") or "<unknown>")
    raw_path = metadata_value(root_bead, "gc.build.requirements_path").strip()
    if not raw_path:
        raw_path = metadata_value(root_bead, "gc.var.requirements_path").strip()
    if not raw_path:
        raise GateError(f"build-basic root {root_id} is missing gc.build.requirements_path")
    requirements_path = resolve_artifact_path(raw_path, base=rig_dir).resolve()
    if not requirements_path.is_file():
        raise GateError(f"build-basic requirements artifact is missing: {requirements_path}")

    upstream = build_artifact_upstream(requirements_path)
    expected_path = f"beads/{source_id}"
    expected_hash = f"bead:{source_id}"
    identity_entries = [
        entry
        for entry in upstream
        if entry.get("path") == expected_path or entry.get("hash") == expected_hash
    ]
    identity = identity_entries[0] if len(identity_entries) == 1 else None
    if identity is None or (identity.get("path"), identity.get("hash")) != (
        expected_path,
        expected_hash,
    ):
        observed = [(entry.get("path"), entry.get("hash")) for entry in upstream]
        raise GateError(
            f"build-basic source {source_id} requirements must trace exactly one identity entry with "
            f"path {expected_path} and hash {expected_hash}; observed={observed}"
        )

    print(
        f"validated build-basic launcher source provenance: source={source_id} path={requirements_path}",
        flush=True,
    )


def validate_build_basic_artifacts(
    root_bead: Mapping[str, Any],
    *,
    rig_dir: Path,
    env: Mapping[str, str],
    validator_source: Path,
    beads: Sequence[Mapping[str, Any]] | None = None,
    expected_artifact_root: Path | None = None,
    pack_spec: PackSpec | None = None,
) -> None:
    selected_pack = pack_spec or PACK_SPECS[GASCITY_PACK]
    root_id = str(root_bead.get("id") or "").strip()
    if not root_id:
        raise GateError("build-basic artifact validation requires a workflow root id")
    artifact_root = resolve_build_basic_artifact_root(
        root_bead,
        rig_dir=rig_dir,
        expected_artifact_root=expected_artifact_root,
    )
    statuses: dict[str, str] = {}
    artifact_paths: dict[str, Path] = {}
    front_matters: dict[str, Mapping[str, Any]] = {}
    for metadata_key, schema in BUILD_BASIC_ARTIFACT_CONTRACTS:
        raw_path = metadata_value(root_bead, metadata_key)
        if not raw_path:
            raise GateError(f"build-basic root missing required artifact metadata {metadata_key}")
        artifact_path = resolve_current_build_basic_artifact(
            raw_path,
            metadata_key=metadata_key,
            artifact_root=artifact_root,
        )
        validate_build_artifact_schema(
            artifact_path,
            schema=schema,
            validator_source=validator_source,
            env=env,
            context=f"build-basic artifact from {metadata_key}",
            upstream_roots=(rig_dir,),
            enforce_review_status_coverage=schema == "gc.build.review.v1",
        )
        front_matter = artifact_front_matter(
            artifact_path,
            label=f"build-basic artifact from {metadata_key}",
        )
        validate_build_basic_artifact_identity(
            front_matter,
            metadata_key=metadata_key,
            root_id=root_id,
            pack_name=selected_pack.name,
        )
        status = front_matter.get("status")
        statuses[metadata_key] = status.strip() if isinstance(status, str) else ""
        artifact_paths[metadata_key] = artifact_path
        front_matters[metadata_key] = front_matter
        print(f"validated build-basic artifact: {metadata_key} schema={schema} path={artifact_path}", flush=True)

    validate_build_basic_artifact_lineage(
        root_bead,
        artifact_paths=artifact_paths,
        front_matters=front_matters,
        beads=beads,
        pack_name=selected_pack.name,
    )
    validate_build_basic_stage_statuses(root_bead, statuses)


def resolve_build_basic_artifact_root(
    root_bead: Mapping[str, Any],
    *,
    rig_dir: Path,
    expected_artifact_root: Path | None,
) -> Path:
    raw_root = metadata_value(root_bead, "gc.build.artifact_root").strip()
    if not raw_root:
        raise GateError("build-basic root is missing gc.build.artifact_root")
    declared_root = Path(raw_root)
    if not declared_root.is_absolute():
        raise GateError(
            f"build-basic gc.build.artifact_root must be absolute: {raw_root!r}"
        )
    try:
        artifact_root = declared_root.resolve(strict=True)
    except OSError as exc:
        raise GateError(
            f"build-basic gc.build.artifact_root does not resolve: {raw_root!r}: {exc}"
        ) from exc
    if not artifact_root.is_dir() or artifact_root != declared_root:
        raise GateError(
            "build-basic gc.build.artifact_root must name its canonical directory: "
            f"declared={declared_root} canonical={artifact_root}"
        )
    rig_root = rig_dir.resolve(strict=True)
    try:
        artifact_root.relative_to(rig_root)
    except ValueError as exc:
        raise GateError(
            "build-basic gc.build.artifact_root must stay inside the launcher rig: "
            f"root={artifact_root} rig={rig_root}"
        ) from exc
    if expected_artifact_root is not None:
        expected = expected_artifact_root.resolve(strict=True)
        if artifact_root != expected:
            raise GateError(
                "build-basic gc.build.artifact_root does not match the current launch: "
                f"observed={artifact_root} expected={expected}"
            )
    return artifact_root


def resolve_current_build_basic_artifact(
    raw_path: str,
    *,
    metadata_key: str,
    artifact_root: Path,
) -> Path:
    declared = Path(raw_path)
    if not declared.is_absolute():
        raise GateError(
            f"build-basic artifact {metadata_key} must be absolute: {raw_path!r}"
        )
    try:
        mode = declared.lstat().st_mode
        artifact_path = declared.resolve(strict=True)
    except OSError as exc:
        raise GateError(
            f"build-basic artifact from {metadata_key} does not resolve: {declared}: {exc}"
        ) from exc
    if not stat.S_ISREG(mode) or artifact_path != declared:
        raise GateError(
            f"build-basic artifact {metadata_key} must be a canonical regular non-symlink file: "
            f"declared={declared} canonical={artifact_path}"
        )
    try:
        artifact_path.relative_to(artifact_root)
    except ValueError as exc:
        raise GateError(
            f"build-basic artifact {metadata_key} must stay under the current artifact root: "
            f"artifact={artifact_path} root={artifact_root}"
        ) from exc
    return artifact_path


def validate_build_basic_artifact_identity(
    front_matter: Mapping[str, Any],
    *,
    metadata_key: str,
    root_id: str,
    pack_name: str,
) -> None:
    profile = BUILD_ARTIFACT_IDENTITY_PROFILES.get(pack_name)
    default_stage = BUILD_ARTIFACT_STAGE_BY_KEY.get(metadata_key)
    if profile is None or default_stage is None:
        raise GateError(
            f"build artifact identity contract is missing for pack={pack_name} key={metadata_key}"
        )
    build_formula = str(profile["build_formula"])
    expected_workflow_formula = profile["workflow_formulas"].get(
        metadata_key, build_formula
    )
    expected_methodology_pack = pack_name
    expected_methodology_name = profile["methodology_names"].get(
        metadata_key, build_formula
    )
    expected_producer_formula = profile["producer_formulas"].get(
        metadata_key, build_formula
    )
    expected_producer_stage = profile["producer_stages"].get(
        metadata_key, default_stage
    )
    workflow = front_matter.get("workflow")
    methodology = front_matter.get("methodology")
    producer = front_matter.get("producer")
    expected = {
        "workflow.id": root_id,
        "workflow.formula": expected_workflow_formula,
        "methodology.pack": expected_methodology_pack,
        "methodology.name": expected_methodology_name,
        "producer.formula": expected_producer_formula,
        "producer.stage": expected_producer_stage,
    }
    observed = {
        "workflow.id": workflow.get("id") if isinstance(workflow, Mapping) else None,
        "workflow.formula": workflow.get("formula") if isinstance(workflow, Mapping) else None,
        "methodology.pack": methodology.get("pack") if isinstance(methodology, Mapping) else None,
        "methodology.name": methodology.get("name") if isinstance(methodology, Mapping) else None,
        "producer.formula": producer.get("formula") if isinstance(producer, Mapping) else None,
        "producer.stage": producer.get("stage") if isinstance(producer, Mapping) else None,
    }
    for field, expected_value in expected.items():
        if observed[field] != expected_value:
            raise GateError(
                f"build-basic artifact {metadata_key} {field} must equal {expected_value!r}; "
                f"observed={observed[field]!r}"
            )


def require_exact_build_basic_upstream(
    front_matter: Mapping[str, Any],
    *,
    artifact_key: str,
    artifact_path: Path,
    upstream_key: str,
    upstream_path: Path,
) -> None:
    entries = artifact_upstream(
        front_matter,
        artifact_path=artifact_path,
        label=f"build-basic artifact {artifact_key}",
    )
    expected_path = str(upstream_path)
    expected_digest = f"sha256:{hashlib.sha256(upstream_path.read_bytes()).hexdigest()}"
    observed = [
        str(entry.get("hash") or "")
        for entry in entries
        if entry.get("path") == expected_path
    ]
    if observed != [expected_digest]:
        raise GateError(
            f"build-basic artifact {artifact_key} must trace exact current {upstream_key} once: "
            f"path={expected_path} expected={expected_digest} observed={observed}"
        )


def build_basic_stage_attempt(
    beads: Sequence[Mapping[str, Any]],
    *,
    root_id: str,
    step_id: str,
) -> int:
    controls = [
        bead
        for bead in beads
        if metadata_value(bead, "gc.root_bead_id") == root_id
        and metadata_value(bead, "gc.kind") == "ralph"
        and metadata_value(bead, "gc.step_id") == step_id
    ]
    if len(controls) != 1:
        raise GateError(
            f"build-basic current stage {step_id} must have exactly one logical control; "
            f"observed={len(controls)}"
        )
    control = controls[0]
    if str(control.get("status") or "") != "closed" or metadata_value(control, "gc.outcome") != "pass":
        raise GateError(
            f"build-basic current stage {step_id} control must be closed/pass"
        )
    raw_attempt = metadata_value(control, "gc.control_epoch").strip()
    if not re.fullmatch(r"[1-9][0-9]*", raw_attempt):
        raise GateError(
            f"build-basic current stage {step_id} has invalid gc.control_epoch={raw_attempt!r}"
        )
    return int(raw_attempt)


def build_basic_review_attempt(
    beads: Sequence[Mapping[str, Any]],
    *,
    root_id: str,
    review_path: Path,
    pack_name: str,
    ralph_step_id: str,
    terminal_step_id: str,
    terminal_report_name: str,
) -> int:
    member_rows = [
        bead
        for bead in beads
        if metadata_value(bead, "gc.root_bead_id") == root_id
        and metadata_value(bead, "gc.ralph_step_id") == ralph_step_id
        and metadata_value(bead, "gc.scope_role") == "member"
    ]
    if not member_rows:
        raise GateError(
            f"build-basic {pack_name} review has no member rows from which to determine "
            "the current attempt"
        )
    attempts: list[int] = []
    for bead in member_rows:
        raw_attempt = metadata_value(bead, "gc.attempt").strip()
        if not re.fullmatch(r"[1-9][0-9]*", raw_attempt):
            raise GateError(
                "build-basic review member has invalid gc.attempt: "
                f"bead={bead.get('id') or '<unknown>'} attempt={raw_attempt or '<missing>'}"
            )
        attempts.append(int(raw_attempt))
    current_attempt = max(attempts)
    report_terminal_path = review_path.parent / terminal_report_name
    terminals = [
        bead
        for bead in member_rows
        if metadata_value(bead, "gc.attempt") == str(current_attempt)
        and metadata_value(bead, "gc.step_id") == terminal_step_id
        and str(bead.get("status") or "") == "closed"
        and metadata_value(bead, "gc.outcome") == "pass"
        and metadata_value(bead, "code_review.verdict") == "reported"
        and metadata_value(bead, "code_review.report_path") == str(report_terminal_path)
        and metadata_value(bead, "code_review.output_path") == str(report_terminal_path)
    ]
    if len(terminals) != 1:
        raise GateError(
            f"build-basic current review attempt {current_attempt} must have exactly one "
            f"closed/pass reported terminal at {report_terminal_path}; "
            f"observed={[str(bead.get('id') or '<unknown>') for bead in terminals]}"
        )
    return current_attempt


def validate_build_basic_artifact_lineage(
    root_bead: Mapping[str, Any],
    *,
    artifact_paths: Mapping[str, Path],
    front_matters: Mapping[str, Mapping[str, Any]],
    beads: Sequence[Mapping[str, Any]] | None,
    pack_name: str,
) -> None:
    root_id = str(root_bead.get("id") or "").strip()
    review_key = "gc.build.review_report_path"
    final_key = "gc.build.final_report_path"
    summary_key = "gc.build.implementation_summary_path"
    require_exact_build_basic_upstream(
        front_matters[review_key],
        artifact_key=review_key,
        artifact_path=artifact_paths[review_key],
        upstream_key=summary_key,
        upstream_path=artifact_paths[summary_key],
    )
    require_exact_build_basic_upstream(
        front_matters[final_key],
        artifact_key=final_key,
        artifact_path=artifact_paths[final_key],
        upstream_key=summary_key,
        upstream_path=artifact_paths[summary_key],
    )
    require_exact_build_basic_upstream(
        front_matters[final_key],
        artifact_key=final_key,
        artifact_path=artifact_paths[final_key],
        upstream_key=review_key,
        upstream_path=artifact_paths[review_key],
    )

    if beads is None:
        return
    profile = BUILD_ARTIFACT_IDENTITY_PROFILES.get(pack_name)
    review_attempt_contract = (
        profile.get("review_attempt") if isinstance(profile, Mapping) else None
    )
    if not isinstance(review_attempt_contract, Mapping):
        raise GateError(
            f"build artifact review attempt contract is missing for pack={pack_name}"
        )
    expected_attempts = {
        key: build_basic_stage_attempt(
            beads,
            root_id=root_id,
            step_id=step_id,
        )
        for key, step_id in BUILD_BASIC_STAGE_STEPS.items()
    }
    review_attempt_source = review_attempt_contract.get("source")
    if review_attempt_source == "stage":
        review_step_id = str(review_attempt_contract.get("step_id") or "").strip()
        if not review_step_id:
            raise GateError(
                f"build artifact review stage attempt contract is invalid for pack={pack_name}"
            )
        expected_attempts[review_key] = build_basic_stage_attempt(
            beads,
            root_id=root_id,
            step_id=review_step_id,
        )
    elif review_attempt_source == "loop":
        loop_fields = {
            field: str(review_attempt_contract.get(field) or "").strip()
            for field in (
                "ralph_step_id",
                "terminal_step_id",
                "terminal_report_name",
            )
        }
        if not all(loop_fields.values()):
            raise GateError(
                f"build artifact review loop attempt contract is invalid for pack={pack_name}"
            )
        expected_attempts[review_key] = build_basic_review_attempt(
            beads,
            root_id=root_id,
            review_path=artifact_paths[review_key],
            pack_name=pack_name,
            **loop_fields,
        )
    else:
        raise GateError(
            f"build artifact review attempt source is invalid for pack={pack_name}: "
            f"{review_attempt_source!r}"
        )

    for metadata_key, expected_attempt in expected_attempts.items():
        producer = front_matters[metadata_key].get("producer")
        observed = producer.get("attempt") if isinstance(producer, Mapping) else None
        if observed != expected_attempt:
            raise GateError(
                f"build-basic artifact {metadata_key} producer.attempt must equal current "
                f"stage attempt {expected_attempt}; observed={observed!r}"
            )


def validate_build_basic_stage_statuses(
    root_bead: Mapping[str, Any],
    statuses: Mapping[str, str],
) -> None:
    for metadata_key in BUILD_BASIC_PRE_REVIEW_ARTIFACT_KEYS:
        status = statuses.get(metadata_key, "")
        if status != "approved":
            raise GateError(
                f"build-basic pre-review artifact {metadata_key} must have status=approved; "
                f"observed={status or '<missing>'}"
            )

    review_mode = metadata_value(root_bead, "gc.var.review_mode").strip()
    if review_mode != "report":
        raise GateError(
            "build-basic inference gate requires review mode=report; "
            f"observed={review_mode or '<missing>'}"
        )

    review_status = statuses.get("gc.build.review_report_path", "")
    final_status = statuses.get("gc.build.final_report_path", "")
    if review_status == "approved":
        expected_final_status = "approved"
        lifecycle = BUILD_BASIC_SUCCESS_LIFECYCLE
        lifecycle_context = "approved final report"
    elif review_status in {"changes_required", "blocked"}:
        expected_final_status = "blocked"
        lifecycle = BUILD_BASIC_BLOCKED_LIFECYCLE
        lifecycle_context = (
            f"report-mode review status={review_status} with blocked final report"
        )
    else:
        raise GateError(
            f"build-basic report-mode review status={review_status or '<missing>'} "
            "cannot finalize"
        )

    if final_status != expected_final_status:
        raise GateError(
            f"build-basic report-mode review status={review_status} must map to "
            f"final status={expected_final_status}; observed final status={final_status or '<missing>'}"
        )

    root_status = str(root_bead.get("status") or "")
    if root_status != "closed":
        raise GateError(
            f"build-basic {lifecycle_context} requires root status=closed; "
            f"observed={root_status or '<missing>'}"
        )
    for metadata_key, expected in lifecycle.items():
        observed = metadata_value(root_bead, metadata_key).strip()
        if observed != expected:
            raise GateError(
                f"build-basic {lifecycle_context} requires {metadata_key}={expected}; "
                f"observed={observed or '<missing>'}"
            )


def resolve_artifact_path(value: str, *, base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def bead_route_targets(bead: Mapping[str, Any]) -> list[str]:
    targets: list[str] = []
    for key in ("assignee", "owner", "agent", "agent_id", "session", "target"):
        value = bead.get(key)
        if isinstance(value, str) and value.strip():
            targets.append(value.strip())

    metadata = bead.get("metadata")
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if not route_metadata_key(key):
                continue
            for target in string_values(value):
                targets.append(target)
    return dedupe_strings(targets)


def route_metadata_key(key: str) -> bool:
    return (
        key in {
            "gc.run_target",
            "gc.routed_to",
            "gc.target",
            "gc.assignee",
            "run_target",
            "routed_to",
            "target",
            "assignee",
        }
        or key.endswith(".run_target")
        or key.endswith(".routed_to")
        or key.endswith("_run_target")
        or key.endswith("_routed_to")
    )


def string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(string_values(item))
        return values
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(string_values(item))
        return values
    return []


def dedupe_strings(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def route_matches(actual: str, expected: str) -> bool:
    actual = actual.strip()
    expected = expected.strip()
    if not actual or not expected:
        return False
    if actual == expected:
        return True
    return actual.endswith(f"/{expected}")


def validate_required_routes(
    beads: Sequence[Mapping[str, Any]],
    required_routes: Sequence[str],
    *,
    context: str,
) -> None:
    if not required_routes:
        return
    observed = sorted({target for bead in beads for target in bead_route_targets(bead)})
    missing = [
        expected
        for expected in required_routes
        if not any(route_matches(actual, expected) for actual in observed)
    ]
    if missing:
        raise GateError(
            f"{context} did not route through expected agent(s): {', '.join(missing)}. "
            f"Observed routes: {', '.join(observed) if observed else '<none>'}"
        )


def list_sessions(gc_bin: str, workspace: GateWorkspace, *, env: Mapping[str, str]) -> list[dict[str, Any]]:
    output = run_checked(
        [gc_bin, "--city", str(workspace.city_dir), "session", "list", "--state", "all", "--json"],
        env=env,
        timeout=parse_duration("30s"),
    )
    payload = extract_json_payload(output)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("sessions", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    if payload is None:
        return []
    raise GateError(f"unexpected gc session list --json payload: {payload!r}")


def session_identity_strings(session: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "id",
        "name",
        "session",
        "session_id",
        "agent",
        "agent_id",
        "agent_name",
        "template",
        "template_name",
        "display_name",
    ):
        value = session.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    metadata = session.get("metadata")
    if isinstance(metadata, dict):
        for key in ("agent", "agent_id", "template", "name"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
    return dedupe_strings(values)


def identity_matches_agent(identity: str, agent: str) -> bool:
    identity = identity.strip()
    if identity == agent:
        return True
    base = identity.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
    return base == agent


def wait_for_gastown_sessions(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    required_agents: Sequence[str],
    timeout: float,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    last_sessions: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        last_sessions = list_sessions(gc_bin, workspace, env=env)
        missing = missing_session_agents(last_sessions, required_agents)
        if not missing:
            print(
                "validated Gastown sessions: "
                + ", ".join(sorted(required_agents)),
                flush=True,
            )
            return last_sessions
        print(f"waiting for Gastown sessions: missing {', '.join(missing)}", flush=True)
        time.sleep(2)
    identities = sorted({value for session in last_sessions for value in session_identity_strings(session)})
    raise GateError(
        f"Gastown always-on sessions did not appear: {', '.join(missing_session_agents(last_sessions, required_agents))}. "
        f"Observed session identities: {', '.join(identities) if identities else '<none>'}"
    )


def missing_session_agents(sessions: Sequence[Mapping[str, Any]], required_agents: Sequence[str]) -> list[str]:
    identities = [value for session in sessions for value in session_identity_strings(session)]
    return [
        agent
        for agent in required_agents
        if not any(identity_matches_agent(identity, agent) for identity in identities)
    ]


def gastown_review_assignment_description() -> str:
    return """\
Run a bounded Gastown orchestration review-leg gate.

Review the following tiny release-gate plan as written. Do not execute the
plan, start another city, spawn sessions, or route extra work; the numbered
steps are the subject of the review.

1. Start a disposable Gastown city.
2. Require mayor, deacon, boot, and witness sessions to exist after startup.
3. Do not require refinery to be active at startup because refinery is configured on-demand.
4. Route a review assignment through the Gastown polecat pool and persist the report to bead notes.

Write the report in the bead notes with these sections:

## Summary
## Findings
## Recommendation

The expected finding is that the gate must check refinery availability by
configuration/formula surface rather than by active session presence.
"""


def create_gastown_review_assignment(gc_bin: str, workspace: GateWorkspace, *, env: Mapping[str, str]) -> str:
    metadata = {
        "coordinator": "mayor",
        "review_id": "gastown-inference-gate",
        "review_phase": "orchestration",
        "review_leg": "polecat-review-leg",
    }
    output = run_checked(
        [
            gc_bin,
            "--city",
            str(workspace.city_dir),
            "--rig",
            workspace.rig_name,
            "bd",
            "create",
            GASTOWN_REVIEW_ASSIGNMENT_TITLE,
            "--type",
            "task",
            "--description",
            gastown_review_assignment_description(),
            "--metadata",
            json.dumps(metadata, sort_keys=True),
            "--json",
        ],
        cwd=workspace.rig_dir,
        env=env,
        timeout=parse_duration("1m"),
        log_output=True,
    )
    bead_id = find_first_key(extract_json_payload(output), ("id", "bead_id"))
    if bead_id:
        return bead_id
    raise GateError(f"could not determine Gastown review assignment bead id from gc bd create output:\n{output}")


def launch_gastown_review_leg(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    pack_spec: PackSpec,
    assignment_id: str,
) -> None:
    target = f"{workspace.rig_name}/{pack_spec.binding}.polecat"
    run_checked(
        [
            gc_bin,
            "--city",
            str(workspace.city_dir),
            "--rig",
            workspace.rig_name,
            "sling",
            target,
            assignment_id,
            "--force",
            "--on",
            "mol-review-leg",
            "--title",
            GASTOWN_REVIEW_TITLE,
            "--var",
            f"binding_prefix={pack_spec.binding}.",
            "--nudge",
            "--json",
        ],
        cwd=workspace.rig_dir,
        env=env,
        timeout=parse_duration("5m"),
        log_output=True,
    )


def wait_for_bead_closed(
    gc_bin: str,
    workspace: GateWorkspace,
    bead_id: str,
    *,
    env: Mapping[str, str],
    timeout: float,
    poll_interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_bead: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last_bead = show_bead(gc_bin, workspace, bead_id, env=env)
        status = str(last_bead.get("status") or "")
        print(f"bead {bead_id}: status={status or '<unset>'}", flush=True)
        if status == "closed":
            return last_bead
        time.sleep(poll_interval)
    raise GateError(
        f"timed out after {timeout:.0f}s waiting for bead {bead_id} to close; last bead={last_bead!r}\n"
        + collect_diagnostics(gc_bin, workspace, env=env)
    )


def bead_notes_text(bead: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("notes", "note", "comments"):
        value = bead.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.extend(string_values(item))
    return "\n".join(parts)


def require_gastown_review_report(bead: Mapping[str, Any]) -> None:
    notes = bead_notes_text(bead)
    lower = notes.lower()
    required = ("## summary", "## findings", "## recommendation")
    missing = [section for section in required if section not in lower]
    if missing:
        raise GateError(
            "Gastown review-leg assignment closed without the expected structured report notes. "
            f"Missing sections: {', '.join(missing)}"
        )
    if "refinery" not in lower or "on-demand" not in lower.replace("on demand", "on-demand"):
        raise GateError(
            "Gastown review-leg report did not identify the expected on-demand refinery assertion. "
            f"Notes: {notes[:1000]}"
        )


def all_gastown_formula_contracts() -> dict[str, tuple[str, ...]]:
    contracts: dict[str, list[str]] = {}
    for group in (GASTOWN_FORMULA_CONTRACTS, GASTOWN_BUILD_WORKFLOW_CONTRACTS):
        for formula_name, fragments in group.items():
            contracts.setdefault(formula_name, []).extend(fragments)
    return {formula_name: tuple(fragments) for formula_name, fragments in contracts.items()}


def validate_methodology_flow_contract(pack_spec: PackSpec) -> None:
    contract = METHODOLOGY_FLOW_CONTRACTS.get(pack_spec.name)
    if contract is None:
        return
    missing: list[str] = []

    build_document = load_methodology_formula(pack_spec.source, pack_spec.build_formula, missing)
    review_document = load_methodology_formula(pack_spec.source, pack_spec.review_formula, missing)
    if build_document:
        validate_methodology_build_formula(pack_spec, build_document, contract, missing)
    if review_document:
        validate_methodology_review_formula(pack_spec, review_document, contract, missing)

    expansion_routes = contract.get("expansion_routes", {})
    expansion_checks = contract.get("expansion_checks", {})
    expansion_terminal_checks = contract.get("expansion_terminal_checks", {})
    if isinstance(expansion_routes, dict):
        for expansion_name, required_routes in expansion_routes.items():
            expansion_document = load_methodology_formula(pack_spec.source, str(expansion_name), missing)
            if expansion_document:
                validate_methodology_expansion(
                    pack_spec,
                    str(expansion_name),
                    expansion_document,
                    tuple(str(route) for route in required_routes),
                    str(expansion_checks.get(expansion_name, ""))
                    if isinstance(expansion_checks, Mapping)
                    else "",
                    str(expansion_terminal_checks.get(expansion_name, ""))
                    if isinstance(expansion_terminal_checks, Mapping)
                    else "",
                    missing,
                )

    if missing:
        raise GateError(
            f"{pack_spec.name} methodology flow contract drifted:\n"
            + "\n".join(f"- {item}" for item in missing)
        )


def load_methodology_formula(pack_source: Path, formula_name: str | None, missing: list[str]) -> dict[str, Any] | None:
    if not formula_name:
        missing.append("missing formula name in pack spec")
        return None
    path = pack_source / "formulas" / f"{formula_name}.formula.toml"
    if not path.is_file():
        missing.append(f"{formula_name}: missing formula file {path}")
        return None
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        missing.append(f"{formula_name}: invalid TOML: {exc}")
        return None
    if not isinstance(payload, dict):
        missing.append(f"{formula_name}: formula TOML did not parse to a table")
        return None
    if payload.get("formula") != formula_name:
        missing.append(f"{formula_name}: formula field is {payload.get('formula')!r}, want {formula_name!r}")
    if payload.get("contract") != "graph.v2":
        missing.append(f"{formula_name}: contract is {payload.get('contract')!r}, want 'graph.v2'")
    return payload


def validate_methodology_build_formula(
    pack_spec: PackSpec,
    document: Mapping[str, Any],
    contract: Mapping[str, Any],
    missing: list[str],
) -> None:
    if "build-base" not in list_values(document.get("extends")):
        missing.append(f"{pack_spec.build_formula}: must extend build-base")
    if document.get("target_required") is not True:
        missing.append(f"{pack_spec.build_formula}: target_required must be true")

    methodology = nested_mapping(document, "metadata", "gc", "methodology")
    for mode_key, expected in (
        ("allowed_drain_policies", ("separate", "same-session")),
        ("interaction_modes", ("headless",)),
        ("review_modes", ("report",)),
    ):
        observed = list_values(methodology.get(mode_key))
        for value in expected:
            if value not in observed:
                missing.append(f"{pack_spec.build_formula}: metadata.gc.methodology.{mode_key} missing {value!r}")

    steps = steps_by_id(document)
    build_steps = contract.get("build_steps", {})
    if not isinstance(build_steps, dict):
        missing.append(f"{pack_spec.name}: build_steps contract must be a table")
        return
    for step_id, expectations in build_steps.items():
        if not isinstance(expectations, Mapping):
            missing.append(f"{pack_spec.name}: invalid build step contract for {step_id}")
            continue
        step = steps.get(str(step_id))
        if not step:
            missing.append(f"{pack_spec.build_formula}: missing step {step_id}")
            continue
        validate_step_contract(pack_spec.build_formula or pack_spec.name, str(step_id), step, expectations, missing)


def validate_methodology_review_formula(
    pack_spec: PackSpec,
    document: Mapping[str, Any],
    contract: Mapping[str, Any],
    missing: list[str],
) -> None:
    if "code-review-base" not in list_values(document.get("extends")):
        missing.append(f"{pack_spec.review_formula}: must extend code-review-base")
    if document.get("mode") != "report":
        missing.append(f"{pack_spec.review_formula}: mode must be report")
    if document.get("internal") is not True:
        missing.append(f"{pack_spec.review_formula}: internal must be true")

    steps = steps_by_id(document)
    write_report = steps.get("write-report")
    if not write_report:
        missing.append(f"{pack_spec.review_formula}: missing step write-report")
        return
    validate_step_contract(
        pack_spec.review_formula or pack_spec.name,
        "write-report",
        write_report,
        {
            "artifact_schema": "gc.build.review.v1",
            "artifact_path_key": "gc.var.report_path",
            "expand": str(contract.get("review_expansion", "")),
        },
        missing,
    )


def validate_methodology_expansion(
    pack_spec: PackSpec,
    formula_name: str,
    document: Mapping[str, Any],
    required_routes: Sequence[str],
    required_check: str,
    required_terminal_check: str,
    missing: list[str],
) -> None:
    if document.get("type") != "expansion":
        missing.append(f"{formula_name}: type must be expansion")
    observed = expansion_route_targets(document)
    for expected in required_routes:
        if not any(route_matches(actual, expected) for actual in observed):
            missing.append(
                f"{formula_name}: missing expected route {expected!r}. "
                f"Observed routes: {', '.join(observed) if observed else '<none>'}"
            )

    loop_templates = [
        template
        for template in list_dicts(document.get("template"))
        if str(template.get("id") or "").endswith("-loop")
    ]
    if required_check and not any(step_check_path(template).endswith(required_check) for template in loop_templates):
        missing.append(f"{formula_name}: loop template missing {required_check}")

    terminal_templates = [
        template
        for template in list_dicts(document.get("template"))
        if not list_dicts(template.get("children"))
    ]
    if required_terminal_check and not any(
        step_check_path(template).endswith(required_terminal_check)
        for template in terminal_templates
    ):
        missing.append(f"{formula_name}: terminal template missing {required_terminal_check}")


def validate_step_contract(
    formula_name: str,
    step_id: str,
    step: Mapping[str, Any],
    expectations: Mapping[str, Any],
    missing: list[str],
) -> None:
    metadata = mapping_value(step.get("metadata"))
    expected_run_target = expectations.get("run_target")
    if expected_run_target is not None and metadata.get("gc.run_target") != expected_run_target:
        missing.append(
            f"{formula_name}:{step_id}: gc.run_target is {metadata.get('gc.run_target')!r}, "
            f"want {expected_run_target!r}"
        )

    expected_schema = expectations.get("artifact_schema")
    if expected_schema is not None and metadata.get("gc.build.artifact_schema") != expected_schema:
        missing.append(
            f"{formula_name}:{step_id}: gc.build.artifact_schema is "
            f"{metadata.get('gc.build.artifact_schema')!r}, want {expected_schema!r}"
        )

    expected_path_key = expectations.get("artifact_path_key")
    if expected_path_key is not None:
        keys = [part.strip() for part in str(metadata.get("gc.build.artifact_path_keys") or "").split(",")]
        if expected_path_key not in keys:
            missing.append(f"{formula_name}:{step_id}: artifact path keys missing {expected_path_key!r}")

    expected_expand = expectations.get("expand")
    if expected_expand is not None and step.get("expand") != expected_expand:
        missing.append(f"{formula_name}:{step_id}: expand is {step.get('expand')!r}, want {expected_expand!r}")

    expected_drain_formula = expectations.get("drain_formula")
    drain = mapping_value(step.get("drain"))
    if expected_drain_formula is not None and drain.get("formula") != expected_drain_formula:
        missing.append(
            f"{formula_name}:{step_id}: drain formula is {drain.get('formula')!r}, "
            f"want {expected_drain_formula!r}"
        )

    expected_drain_context = expectations.get("drain_context")
    if expected_drain_context is not None and drain.get("context") != expected_drain_context:
        missing.append(
            f"{formula_name}:{step_id}: drain context is {drain.get('context')!r}, "
            f"want {expected_drain_context!r}"
        )

    if expectations.get("single_lane") is True and mapping_value(drain.get("item")).get("single_lane") is not True:
        missing.append(f"{formula_name}:{step_id}: drain.item.single_lane must be true")

    expected_needs = expectations.get("needs")
    if expected_needs is not None:
        observed_needs = list_values(step.get("needs"))
        for need in expected_needs:
            if need not in observed_needs:
                missing.append(f"{formula_name}:{step_id}: needs missing {need!r}")

    expected_check = expectations.get("check")
    if expected_check is not None and not step_check_path(step).endswith(str(expected_check)):
        missing.append(f"{formula_name}:{step_id}: check path missing {expected_check!r}")


def steps_by_id(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(step["id"]): step
        for step in list_dicts(document.get("steps"))
        if isinstance(step.get("id"), str)
    }


def expansion_route_targets(document: Mapping[str, Any]) -> list[str]:
    targets: list[str] = []
    for template in list_dicts(document.get("template")):
        targets.extend(metadata_route_targets(template))
        for child in list_dicts(template.get("children")):
            targets.extend(metadata_route_targets(child))
    return dedupe_strings(targets)


def metadata_route_targets(table: Mapping[str, Any]) -> list[str]:
    metadata = mapping_value(table.get("metadata"))
    target = metadata.get("gc.run_target")
    return [target] if isinstance(target, str) and target.strip() else []


def step_check_path(table: Mapping[str, Any]) -> str:
    check = mapping_value(mapping_value(table.get("check")).get("check"))
    path = check.get("path")
    return path if isinstance(path, str) else ""


def nested_mapping(value: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = value
    for key in keys:
        current = mapping_value(current).get(key)
    return mapping_value(current)


def mapping_value(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def list_dicts(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def list_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def validate_gastown_orchestration_contract(pack_source: Path) -> None:
    missing: list[str] = []
    for formula_name, required_fragments in all_gastown_formula_contracts().items():
        path = pack_source / "formulas" / f"{formula_name}.toml"
        if not path.is_file():
            missing.append(f"{formula_name}: missing formula file {path}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for fragment in required_fragments:
            if fragment not in text:
                missing.append(f"{formula_name}: missing contract fragment {fragment!r}")
    if missing:
        raise GateError("Gastown orchestration contract drifted:\n" + "\n".join(f"- {item}" for item in missing))


def stop_city(gc_bin: str, workspace: GateWorkspace, *, env: Mapping[str, str]) -> None:
    for command in (
        [gc_bin, "stop", str(workspace.city_dir), "--force", "--timeout", "30s"],
        [gc_bin, "supervisor", "stop", "--wait", "--wait-timeout", "30s"],
    ):
        try:
            run_checked(command, env=env, timeout=parse_duration("1m"))
        except Exception as exc:  # pragma: no cover - cleanup best effort
            print(f"cleanup command failed ({shlex.join(command)}): {exc}", file=sys.stderr)


def run_review_gate(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    pack_spec: PackSpec,
    timeout: float,
    poll_interval: float,
) -> None:
    root_id = launch_review_formula(gc_bin, workspace, env=env, pack_spec=pack_spec)
    root_bead = wait_for_workflow_pass(
        gc_bin,
        workspace,
        root_id,
        env=env,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    validate_review_report(root_bead, workspace, env=env, pack_spec=pack_spec)
    validate_required_routes(
        list_beads(gc_bin, workspace, env=env),
        pack_spec.required_review_routes,
        context=f"{pack_spec.name} review gate",
    )


def run_build_gate(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    pack_spec: PackSpec,
    timeout: float,
    poll_interval: float,
) -> None:
    launcher_commit = git_output(
        workspace.rig_dir,
        "rev-parse",
        "HEAD",
        context="pre-launch launcher HEAD",
    ).strip()
    root_id = launch_build_formula(gc_bin, workspace, env=env, pack_spec=pack_spec)
    root_bead = wait_for_workflow_pass(
        gc_bin,
        workspace,
        root_id,
        env=env,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    beads = list_beads(gc_bin, workspace, env=env)
    source_id = build_basic_source_id(beads)
    expected_member_ids = implementation_convoy_member_ids(gc_bin, workspace, root_bead, env=env)
    validate_build_basic_artifacts(
        root_bead,
        rig_dir=workspace.rig_dir,
        env=env,
        validator_source=pack_spec.validator_source,
        beads=beads,
        expected_artifact_root=(
            workspace.rig_dir / build_artifact_root(pack_spec)
        ),
        pack_spec=pack_spec,
    )
    validate_build_basic_source_provenance(
        root_bead,
        source_id=source_id,
        rig_dir=workspace.rig_dir,
    )
    validate_build_basic_result(
        workspace.rig_dir,
        beads,
        root_bead=root_bead,
        expected_member_ids=expected_member_ids,
        launcher_commit=launcher_commit,
        env=env,
        timeout=parse_duration("2m"),
        validator_source=pack_spec.validator_source,
    )
    validate_required_routes(
        beads,
        pack_spec.required_build_routes,
        context=f"{pack_spec.name} build gate",
    )


def run_gastown_orchestration_gate(
    gc_bin: str,
    workspace: GateWorkspace,
    *,
    env: Mapping[str, str],
    pack_spec: PackSpec,
    timeout: float,
    poll_interval: float,
) -> None:
    if not pack_spec.gastown:
        raise GateError(f"pack {pack_spec.name} is not a Gastown orchestration pack")
    wait_for_gastown_sessions(
        gc_bin,
        workspace,
        env=env,
        required_agents=GASTOWN_ALWAYS_ON_AGENTS,
        timeout=min(timeout, parse_duration("5m")),
    )
    assignment_id = create_gastown_review_assignment(gc_bin, workspace, env=env)
    launch_gastown_review_leg(gc_bin, workspace, env=env, pack_spec=pack_spec, assignment_id=assignment_id)
    assignment = wait_for_bead_closed(
        gc_bin,
        workspace,
        assignment_id,
        env=env,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    require_gastown_review_report(assignment)


def expand_pack_selection(selection: str) -> list[str]:
    if selection == "all-supported":
        return list(PACK_SPECS.keys())
    if selection == "methodology":
        return list(METHODOLOGY_PACKS)
    if selection in PACK_SPECS:
        return [selection]
    raise GateError(f"unknown pack selection: {selection}")


def resolve_pack_spec(args: argparse.Namespace, pack_name: str) -> PackSpec:
    base = PACK_SPECS[pack_name]
    pack_source = args.pack_source.resolve() if args.pack_source else base.source.resolve()
    roles_source = args.roles_source.resolve() if args.roles_source else base.roles_source.resolve()
    validator_source = args.validator_source.resolve() if args.validator_source else base.validator_source.resolve()
    pack_spec = replace(base, source=pack_source, roles_source=roles_source, validator_source=validator_source)
    if not (pack_spec.source / "pack.toml").is_file():
        raise GateError(f"pack source does not contain pack.toml for {pack_spec.name}: {pack_spec.source}")
    if not pack_spec.gastown and not (pack_spec.roles_source / "pack.toml").is_file():
        raise GateError(f"roles source does not contain pack.toml for {pack_spec.name}: {pack_spec.roles_source}")
    return pack_spec


def run_gate(args: argparse.Namespace, *, pack_name: str | None = None, workdir: Path | None = None) -> None:
    gc_bin = resolve_binary(args.gc_bin)
    selected_pack = pack_name or args.pack
    pack_spec = resolve_pack_spec(args, selected_pack)

    gates = expand_gate_selection(args.gate, pack_spec)
    timeout = parse_duration(args.timeout)
    poll_interval = parse_duration(args.poll_interval)

    selected_workdir = workdir or args.workdir
    if selected_workdir:
        work_root = selected_workdir.resolve()
        if work_root.exists() and any(work_root.iterdir()):
            raise GateError(f"--workdir must be empty or absent: {work_root}")
        cleanup = False
    else:
        work_root = Path(tempfile.mkdtemp(prefix=f"{pack_spec.name}-pack-inference-"))
        cleanup = not args.keep_workdir

    workspace = write_gate_workspace(
        work_root,
        pack_source=pack_spec.source,
        roles_source=pack_spec.roles_source,
        validator_source=pack_spec.validator_source,
        pack_binding=pack_spec.binding,
        pack_name=pack_spec.name,
        gastown=pack_spec.gastown,
        city_name=city_name_for_pack(args, pack_spec),
        rig_name=args.rig_name,
    )
    env = build_gate_env(gc_bin, workspace)
    should_stop = False
    try:
        if not args.skip_inference_env_check and not args.setup_only:
            validate_inference_env(env)
        should_stop = True
        initialize_city(gc_bin, workspace, pack_spec=pack_spec, gates=gates, env=env)
        if args.setup_only:
            print(f"setup-only gate passed for {pack_spec.name}; workdir: {workspace.root}", flush=True)
            return
        start_city(gc_bin, workspace, env=env)
        for gate in gates:
            print(f"running {pack_spec.name} pack inference gate: {gate}", flush=True)
            if gate == REVIEW_GATE:
                run_review_gate(
                    gc_bin,
                    workspace,
                    env=env,
                    pack_spec=pack_spec,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            elif gate in (BUILD_GATE, BUILD_BASIC_GATE):
                run_build_gate(
                    gc_bin,
                    workspace,
                    env=env,
                    pack_spec=pack_spec,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            elif gate == GASTOWN_ORCHESTRATION_GATE:
                run_gastown_orchestration_gate(
                    gc_bin,
                    workspace,
                    env=env,
                    pack_spec=pack_spec,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            else:  # pragma: no cover - guarded by expand_gate_selection
                raise GateError(f"unsupported gate: {gate}")
        print(f"{pack_spec.name} pack inference gate passed: {', '.join(gates)}", flush=True)
        if args.keep_workdir or args.workdir:
            print(f"inference gate workdir: {workspace.root}", flush=True)
    finally:
        if should_stop:
            stop_city(gc_bin, workspace, env=env)
        if cleanup:
            shutil.rmtree(workspace.root, ignore_errors=True)


def city_name_for_pack(args: argparse.Namespace, pack_spec: PackSpec) -> str:
    if args.city_name != "gascity-pack-inference-gate" or pack_spec.name == GASCITY_PACK:
        return args.city_name
    return f"{pack_spec.name}-pack-inference-gate"


def resolve_binary(value: str) -> str:
    if os.path.sep in value:
        path = Path(value).resolve()
        if path.is_file():
            return str(path)
        raise GateError(f"binary not found: {value}")
    resolved = shutil.which(value)
    if not resolved:
        raise GateError(f"binary not found on PATH: {value}")
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gc-bin", default=os.environ.get("GC_BIN", "gc"), help="gc binary to exercise")
    parser.add_argument(
        "--pack",
        choices=SUPPORTED_PACK_CHOICES,
        default=GASCITY_PACK,
        help="supported pack or pack group to exercise",
    )
    parser.add_argument("--pack-source", type=Path, help="override local pack root; valid only with a single --pack")
    parser.add_argument(
        "--roles-source",
        type=Path,
        help="override local gascity roles pack root used by non-Gastown packs",
    )
    parser.add_argument(
        "--validator-source",
        type=Path,
        help="override local pack root that provides build artifact validators and schemas",
    )
    parser.add_argument("--workdir", type=Path, help="directory for the disposable gate city and rig")
    parser.add_argument("--keep-workdir", action="store_true", help="keep the generated workdir after success")
    parser.add_argument("--city-name", default="gascity-pack-inference-gate", help="disposable city name")
    parser.add_argument("--rig-name", default="fixture", help="disposable rig name")
    parser.add_argument(
        "--gate",
        choices=(ALL_GATE, REVIEW_GATE, BUILD_GATE, BUILD_BASIC_GATE, GASTOWN_ORCHESTRATION_GATE),
        default=DEFAULT_GATE,
        help="which inference gate to run",
    )
    parser.add_argument("--timeout", default=DEFAULT_TIMEOUT, help="workflow completion timeout")
    parser.add_argument("--poll-interval", default=DEFAULT_POLL_INTERVAL, help="workflow polling interval")
    parser.add_argument("--setup-only", action="store_true", help="initialize imports/config without launching inference")
    parser.add_argument(
        "--skip-inference-env-check",
        action="store_true",
        help="skip Ollama/Claude env validation; intended only with --setup-only",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        pack_names = expand_pack_selection(args.pack)
        if len(pack_names) > 1 and args.pack_source:
            raise GateError("--pack-source can only be used when --pack selects a single pack")
        if len(pack_names) > 1 and args.workdir:
            args.workdir.mkdir(parents=True, exist_ok=True)
        for pack_name in pack_names:
            workdir = args.workdir / pack_name if len(pack_names) > 1 and args.workdir else None
            run_gate(args, pack_name=pack_name, workdir=workdir)
    except (GateError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
