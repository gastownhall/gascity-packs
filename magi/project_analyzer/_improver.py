#!/usr/bin/env python3
"""project_analyzer improver engine.

Runs AFTER ``analyze_project.sh``. Produces per-directory ``_IMPROVEMENTS.md``
through a three-model pipeline plus a project-wide
``_PROJECT_IMPROVEMENT_BACKLOG.md`` synthesis at the project root.

Pipeline:

1. **Draft**     -- ``nvidia/nemotron-3-nano-omni``.
2. **Verify**    -- ``nvidia/nemotron-3-super``.
3. **Aggregate** -- ``minimax/minimax-m2.7``.

Phases run in strict sequence with proper model rotation: each phase loads its
model only if no instance is currently loaded, and unloads at end of phase
ONLY the instances this run created. Drafts are staged on disk so Phase B
can be re-run alone via ``--resume``.

Invoked by ``improve_project_analysis.sh``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

OVERVIEW_FILENAME = "_DIRECTORY_OVERVIEW.md"
IMPROVEMENTS_FILENAME = "_IMPROVEMENTS.md"
BACKLOG_FILENAME = "_PROJECT_IMPROVEMENT_BACKLOG.md"

GENERATION_MARKER = "<!-- project_analyzer:improvements -->"
BACKLOG_MARKER = "<!-- project_analyzer:backlog -->"
SOURCE_HASH_PREFIX = "<!-- project_analyzer:source-sha256="

WALK_IGNORE_DIR_NAMES: frozenset[str] = frozenset({
    "__pycache__", "node_modules", "dist", "build", "target", "venv", ".venv",
    ".git", ".idea", ".vscode", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".tox", ".nox", ".next", ".nuxt", ".turbo", ".svelte-kit", ".pnpm-store",
    "coverage", "htmlcov", "obj", "bin", ".cache",
    "scratch", "tmp", "work",
    "Spotlight-V100", "TemporaryItems", "Trashes", ".Trashes"
})

WALK_IGNORE_FILE_NAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db", ".gitkeep"})

WALK_IGNORE_FILE_SUFFIXES: tuple[str, ...] = (
    ".log", ".tmp", ".pyc", ".pyo", ".min.js", ".min.css", ".lock",
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp",
    ".tiff", ".mp3", ".mp4", ".mov", ".wav", ".zip", ".tar", ".gz", ".tgz",
    ".bz2", ".xz", ".7z", ".rar", ".dmg", ".exe", ".dll", ".so", ".dylib",
    ".o", ".a", ".class", ".jar", ".war"
)

MAX_FILE_BYTES = 12000
MAX_FILES_PER_DIR = 30
MAX_TOTAL_INPUT_CHARS = 110_000
MAX_OVERVIEW_CONTEXT_CHARS = 4000
MAX_IMPROVEMENT_CONTEXT_CHARS = 8000

HTTP_READ_TIMEOUT_SECONDS = 1800
MAX_RETRIES = 3
INITIAL_RETRY_DELAY_SECONDS = 5
MAX_RETRY_DELAY_SECONDS = 60

DEFAULT_DRAFT_MODEL = "nvidia/nemotron-3-nano-omni"
DEFAULT_VERIFY_MODEL = "nvidia/nemotron-3-super"
DEFAULT_AGGREGATE_MODEL = "minimax/minimax-m2.7"
DEFAULT_LM_URL = "http://localhost:1234"
DEFAULT_CONTEXT_LENGTH = 32768
DEFAULT_DRAFT_MAX_OUTPUT = 8192
DEFAULT_VERIFY_MAX_OUTPUT = 16384
DEFAULT_AGGREGATE_MAX_OUTPUT = 16384

RUN_DIR_PREFIX = "improver_run_"

DRAFT_SYSTEM_PROMPT = """You are a Senior Staff Engineer doing a rigorous code review for an LLM-readable improvements file.

Your output is a draft that another model will verify. Be MAXIMALLY SPECIFIC. Every item must be defensible by quoting the supplied source content. Generic advice is useless and will be DELETED during verification — do not waste tokens on it.

Hard rules:
- Never invent files, functions, or behaviour not in the supplied content.
- Quote concrete identifiers in backticks. Cite file path + approximate line numbers (e.g. `script.sh:42`) when the source is large.
- Skip stylistic preferences. Skip "add tests" and "add docstrings" unless an unambiguous public surface is undocumented.
- Skip suggestions to "add comments". Skip vague "consider refactoring" without a concrete refactor proposal.
- Each item MUST include a concrete fix snippet (working code, not pseudocode).
- Score Effort honestly: S = under 30 min, M = under half a day, L = day+.
- Score Confidence honestly: High = literally visible in the code; Med = reasonable inference; Low = guess.
- DO NOT flag the following as findings:
  - Quoted shell variables passed to external binaries (`sshpass`, `ssh`, `curl`, `psql`, etc.) as "command injection" — these are arguments to non-shell programs, not shell expansions.
  - `StrictHostKeyChecking=no` in scripts that explicitly target a controlled internal host pinned by env var. Mention it ONLY if the script is reused across untrusted hosts.
  - "Add input validation" on values that are sourced from `.env` or environment variables the operator controls. They are inputs FROM the operator, not from an attacker.
  - Patterns that are clearly DELIBERATE obfuscation against a regex deny rule (e.g., a literal string assembled as `'$''TMPDIR'`). Recognise the intent. If there is an inline comment or contextual clue indicating "evade hook", treat it as deliberate.
  - "Missing trap on EXIT" when the script is intentionally a one-shot exec replacement (`exec ...` at the end).
- Confidence=High REQUIRES that the issue is verifiable from the supplied source alone, with no assumed attacker model that is not visible in the code. Otherwise downgrade to Med or Low.

Categories to look for (focus on these in priority order):
- **Correctness**: bugs, race conditions, off-by-ones, error swallowing, wrong exit codes, broken idempotency, misuse of tools.
- **Reliability**: missing retries, missing timeouts, no atomic writes, no cleanup on failure, race-prone tempfile creation, unhandled signals.
- **Security (real ones)**: hardcoded secrets in source, unquoted variables in `eval`/`$(...)`/backticks, world-writable artefacts, predictable temp-file names, broken-by-design auth.
- **Observability**: missing structured logs at decision points, opaque failures, no correlation context, no run-summary record.
- **Hidden coupling**: magic strings shared across files, implicit ordering between scripts, undocumented contract between caller and callee.
- **Performance**: clearly inefficient patterns (O(n^2) where O(n) is trivial; redundant subprocesses in tight loops; needless re-parsing).
- **Maintainability**: dead code paths, copy-pasted blocks that drift, configuration that should be externalized, file/function size disasters.
- **Architecture**: dependency direction violations, layering breaks, circular imports, misplaced concerns.

Output format -- EXACT structure, no preamble, no closing summary outside the structure:

The structure is FIXED. The headings `## Summary`, `## Critical`, `## High`, `## Medium`, `## Low`, `## Already-good patterns` MUST appear in this order, exactly. Do NOT introduce topic-themed headings (`## Azure Cosmos DB`, `## Performance Tuning`, etc.). Do NOT split the structure across topical groupings. If the directory is non-code (prescriptive documentation, configuration data, guideline files, vendored references, JSON manifests), the correct output is:
- `## Summary`: one sentence stating the directory is non-code documentation/config; name the topics covered.
- `## Critical`, `## High`, `## Medium`, `## Low`: each contains the literal text `None.` (with the period).
- `## Already-good patterns`: 1-3 bullets describing the doc/config collection's deliberate strengths.

## Summary
2-3 sentences naming the highest-leverage finding for this directory. Concrete; mention specific files.

## Critical
### C1: <one-line title>
- **Where**: `<file>:<lines>` (or `<file>` if file-level)
- **Why**: <one or two sentences rooted in source>
- **How**:
  ```<lang>
  <concrete fix snippet>
  ```
- **Effort**: S | M | L
- **Confidence**: High | Med | Low

(repeat ### Cn for each Critical item; if none, write "None.")

## High
### H1: ...
(same structure)

## Medium
### M1: ...

## Low
### L1: ...

## Already-good patterns
- `<file>` — <one-line note on a deliberate strength worth preserving>
- (one bullet each; 0-5 items; skip if nothing notable)

If a severity has no items, write "None." in that section. Do not skip sections. Empty Critical sections are EXPECTED for most directories — do not invent a Critical item to fill the slot.

Output Markdown only. Begin with the `## Summary` heading.
"""

VERIFY_SYSTEM_PROMPT = """You are a Senior Staff Engineer running a strict verification pass on a draft code-review file. Your default disposition is SKEPTICAL: when in doubt, drop the item.

You receive:
1. A draft `_IMPROVEMENTS.md` produced by another model.
2. The actual directory overview and source content the draft is grounded in.

Your job:
- For each item in the draft, confirm the cited file/line and the claimed code behaviour exist in the supplied content. If you cannot defend the item from the source ALONE, DELETE it.
- Fix wrong file/line citations; correct identifier names that the draft mis-spelled.
- Downgrade severity when overstated (a missing trace log is NOT Critical; a `StrictHostKeyChecking=no` against a pinned internal host is NOT High).
- Consolidate duplicates across severities.
- Tighten the fix snippet so it compiles/parses and is actually applicable to the file as written.
- Add up to three items the draft missed if they are obviously and demonstrably present in the source — but only with the same evidence bar.
- Update the `Already-good patterns` section to ONLY include patterns visible in the source.
- Renumber items so each section starts at 1.

Common false-positive classes to AGGRESSIVELY DROP (the draft model is biased toward these and most are wrong):

1. **Fake "command injection" via quoted shell variables passed to external binaries.** `sshpass -p "${PASS}"` is NOT shell injection; the value is an argv to sshpass, not a shell expansion. Same for `curl -H "Authorization: Bearer ${TOKEN}"`, `psql -c "${SQL}"`, etc. Drop these unless the variable is unquoted in `eval`, `$(...)`, backticks, or a here-string fed to `bash -c`.

2. **"StrictHostKeyChecking=no enables MITM"** against a host pinned by an environment variable controlled by the operator. The script's threat model is internal automation, not zero-trust. Drop unless the script is documented as exposing untrusted host discovery.

3. **Misreading deliberate hook-evasion or deny-rule-bypass patterns as bugs.** If the source contains a literal like `'$''TMPDIR'` or `printf '/dev/' && printf 'null'`, that is intentional regex evasion for a documented test. Drop the finding.

4. **"Validate input from `.env`"** when the values come from operator-controlled config, not user/network input. Drop.

5. **"Missing trap on EXIT"** in a script whose final statement is `exec <something>`. exec replaces the process; traps are irrelevant. Drop.

6. **"Add tests for this script"** without a specific contract to test. Drop.

7. **Severity inflation.** A missing log line is at most Medium. A missing retry on a one-shot script is Low. A `set -Eeuo pipefail` script that doesn't `trap ERR` for diagnostics is Low. A purely cosmetic suggestion is dropped.

Hard rules:
- Output the FINAL `_IMPROVEMENTS.md` only. No commentary, no explanation, no "I removed X because Y" notes.
- Preserve the EXACT structure: the headings `## Summary`, `## Critical`, `## High`, `## Medium`, `## Low`, `## Already-good patterns` MUST appear in this order, exactly. Do NOT introduce topic-themed headings (e.g., `## Azure Cosmos DB`, `## Indexing Policy`, `## Performance`). If the draft contains topic-themed headings, REWRITE it into the strict severity structure and place each item under the appropriate severity (use Med/Low if the underlying claim is real, drop otherwise).
- Use "None." in any empty severity section. Do not skip sections.
- Every remaining item must quote a real identifier or path from the supplied source. If you cannot quote it verbatim, drop it.
- Do not invent file paths. Do not hallucinate symbols.
- If the draft's `Critical` is full of false positives, the verified Critical can and SHOULD be empty ("None."). Empty Critical is the correct answer for most directories.
- If the directory contains ONLY documentation, configuration data, or prescriptive guideline files (no executable scripts, no source code, no build artefacts), the correct output is: a one-sentence Summary noting the directory is documentation/config and naming the topics, then `None.` in each of `## Critical`, `## High`, `## Medium`, `## Low`, then 1-3 bullets in `## Already-good patterns` about the collection's strengths. Do NOT generate per-topic improvement guidance for prescriptive docs — that is content paraphrasing, not code review.
- Stay BRIEF. The verify pass MUST shrink the draft, not expand it. If your output is longer than the draft, you are violating this rule.

Output Markdown only. Begin with the `## Summary` heading.
"""

AGGREGATE_SYSTEM_PROMPT = """You are a Senior Engineering Director producing a project-wide improvement backlog from per-directory review files.

You receive:
1. Each directory's `_IMPROVEMENTS.md` (already verified).
2. The project root `_DIRECTORY_OVERVIEW.md`.
3. A directory tree of the project.

Your job is to produce ONE file: a prioritised backlog the user actually opens when planning work. NOT a copy-paste of the per-directory items.

Hard rules:
- Aggregate, do not invent. Every entry in your backlog must trace back to at least one per-directory item.
- Identify cross-cutting themes (the same class of issue appearing in multiple directories) and surface them as themes, not duplicate per-directory entries.
- Quote specific paths in backticks. Anchor every claim with `<dir>/_IMPROVEMENTS.md#<id>` references where possible.
- Severity hierarchy in aggregation: Critical > High > Medium > Low. A theme inherits the highest severity of its constituent items.
- Quick Wins = High-or-better impact AND Effort=S in the underlying item.
- Long-term Refactors = High-or-better impact AND Effort=L in the underlying item.

Output format -- EXACT structure, no preamble:

# Project Improvement Backlog

## Executive Summary
One paragraph (4-7 sentences) describing the overall improvement landscape: the dominant risk classes, where the project is strong, and what the single most important push for the next sprint will be.

## Top 10 Highest-Leverage Items
A numbered list of the ten most impactful items across the project. Each entry:
1. **<title>** — <one-sentence impact>. Affects: `<dir1>/`, `<dir2>/`, ... See: `<dir1>/_IMPROVEMENTS.md#<id>`.

## Cross-cutting Themes
For each theme that touches 2+ directories, a `### <theme name>` subsection containing:
- **Severity**: Critical | High | Medium | Low
- **Pattern**: 1-2 sentences naming the recurring issue concretely.
- **Affected directories**: bulleted list of `<dir>/` entries.
- **Recommended fix**: a concrete project-wide remediation, not a vague aspiration.

## Quick Wins (High Impact × Low Effort)
Bulleted list. Each: `<dir>/_IMPROVEMENTS.md#<id>` — <one-line title>.

## Long-term Refactors (High Impact × High Effort)
Bulleted list. Same anchor format.

## All Findings by Severity
For each of `### Critical`, `### High`, `### Medium`, `### Low`: a flat bulleted list of `<dir>/_IMPROVEMENTS.md#<id>` — <title> entries.

Output Markdown only. Begin with the `# Project Improvement Backlog` heading.
"""


class ImproverError(Exception):
    """Base exception for the improver engine."""


class LMStudioError(ImproverError):
    """LM Studio communication failed."""


class LMStudioClientError(LMStudioError):
    """LM Studio returned a 4xx response. Carries the response body for inspection."""

    def __init__(self, message: str, status: int, body: str) -> None:
        super().__init__(f"{message} | http_status={status} | body={body[:600]}")
        self.status = status
        self.body = body


class ModelNotAvailableError(ImproverError):
    """Requested model is not available in LM Studio."""


class LoadedInstance(BaseModel):
    """One loaded instance of a model in LM Studio."""

    model_config = ConfigDict(extra="allow")
    id: str = Field(..., description="Instance identifier")


class ModelEntry(BaseModel):
    """Single model entry from ``GET /api/v1/models``."""

    model_config = ConfigDict(extra="allow")
    key: str = Field(..., description="Unique model identifier")
    loaded_instances: list[LoadedInstance] = Field(default_factory=list, description="Currently-loaded instances")


class ModelListResponse(BaseModel):
    """Response from ``GET /api/v1/models``."""

    model_config = ConfigDict(extra="allow")
    models: list[ModelEntry] = Field(default_factory=list, description="Available models")


class ModelLoadRequest(BaseModel):
    """Body for ``POST /api/v1/models/load``."""

    model_config = ConfigDict(extra="forbid")
    model: str = Field(..., description="Model key to load")
    context_length: int = Field(..., gt=0, description="Tokens of context to enable")
    echo_load_config: bool = Field(default=True, description="Return final load config")


class ModelLoadResponse(BaseModel):
    """Response from ``POST /api/v1/models/load``."""

    model_config = ConfigDict(extra="allow")
    instance_id: str | None = Field(default=None, description="Loaded instance identifier")
    load_time_seconds: float | None = Field(default=None, description="Wall-clock load time")
    status: str | None = Field(default=None, description="Load status")


class ModelUnloadRequest(BaseModel):
    """Body for ``POST /api/v1/models/unload``."""

    model_config = ConfigDict(extra="forbid")
    instance_id: str = Field(..., description="Instance to unload")


class ChatRequest(BaseModel):
    """Body for ``POST /api/v1/chat``."""

    model_config = ConfigDict(extra="forbid")
    model: str = Field(..., description="Model key")
    input: str = Field(..., description="User input")
    system_prompt: str = Field(..., description="System message")
    stream: bool = Field(default=False, description="SSE if true")
    store: bool = Field(default=False, description="Persist server-side")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="Sampling temperature")
    context_length: int | None = Field(default=None, gt=0, description="Context window (omit to honour loaded instance)")
    max_output_tokens: int = Field(..., gt=0, description="Output cap")
    reasoning: str | None = Field(default=None, description="Reasoning level: off|low|medium|high|on")


class ChatStats(BaseModel):
    """Token-usage statistics."""

    model_config = ConfigDict(extra="allow")
    input_tokens: int | None = Field(default=None, description="Input tokens")
    total_output_tokens: int | None = Field(default=None, description="Output tokens")
    tokens_per_second: float | None = Field(default=None, description="Throughput")


class ChatOutputItem(BaseModel):
    """One item in a chat ``output`` array."""

    model_config = ConfigDict(extra="allow")
    type: str = Field(..., description="Output item discriminator")
    content: str | None = Field(default=None, description="Text payload")


class ChatResponse(BaseModel):
    """Response from ``POST /api/v1/chat``."""

    model_config = ConfigDict(extra="allow")
    output: list[ChatOutputItem] = Field(default_factory=list, description="Output items")
    stats: ChatStats | None = Field(default=None, description="Generation stats")


@dataclass(frozen=True, slots=True)
class DirectoryRecord:
    """Snapshot of a single directory's content for prompt construction."""

    path: Path
    relative: str
    files: tuple[Path, ...]
    subdirs: tuple[Path, ...]
    overview_path: Path
    parent: Path | None


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure dual stderr + file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    project_logger = logging.getLogger("project_analyzer.improver")
    project_logger.setLevel(logging.INFO)
    project_logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(fmt)
    project_logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    project_logger.addHandler(stream_handler)
    return project_logger


def http_post_json(url: str, body: BaseModel, token: str, logger: logging.Logger) -> bytes:
    """POST JSON body, return raw response bytes.

    4xx responses raise ``LMStudioClientError`` immediately (no retry) with the response
    body. 5xx and transport errors retry with exponential backoff.
    """
    payload = body.model_dump_json(exclude_none=True).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    delay = INITIAL_RETRY_DELAY_SECONDS
    last_error: Exception = RuntimeError("no attempt made")
    last_detail = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=HTTP_READ_TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            try:
                detail_bytes = exc.read()
            except OSError:
                detail_bytes = b""
            last_detail = detail_bytes.decode("utf-8", errors="replace")
            logger.warning("http.post.http_error url=%s attempt=%d/%d code=%s detail=%s", url, attempt, MAX_RETRIES, exc.code, last_detail[:600])
            if 400 <= exc.code < 500:
                raise LMStudioClientError(f"POST {url} client error", exc.code, last_detail) from exc
            if attempt == MAX_RETRIES:
                break
            time.sleep(delay)
            delay = min(delay * 2, MAX_RETRY_DELAY_SECONDS)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            logger.warning("http.post.transport_error url=%s attempt=%d/%d error=%s", url, attempt, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES:
                break
            time.sleep(delay)
            delay = min(delay * 2, MAX_RETRY_DELAY_SECONDS)
    raise LMStudioError(f"POST {url} failed after {MAX_RETRIES} attempts: {last_error} | last_body={last_detail[:300]}")


def http_get_bytes(url: str, token: str, logger: logging.Logger) -> bytes:
    """GET single attempt; return raw response bytes."""
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_READ_TIMEOUT_SECONDS) as response:
            return response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        logger.error("http.get.failed url=%s error=%s", url, exc)
        raise LMStudioError(f"GET {url} failed: {exc}") from exc


def fetch_catalogue(lm_url: str, token: str, logger: logging.Logger) -> ModelListResponse:
    """Single GET /api/v1/models, parsed."""
    raw = http_get_bytes(f"{lm_url}/api/v1/models", token, logger)
    try:
        return ModelListResponse.model_validate_json(raw)
    except ValueError as exc:
        raise LMStudioError(f"GET /api/v1/models invalid JSON: {exc}") from exc


def ensure_models_available(lm_url: str, token: str, models: Iterable[str], logger: logging.Logger) -> None:
    """Confirm every requested model key exists in LM Studio's catalogue."""
    catalogue = fetch_catalogue(lm_url, token, logger)
    available = {entry.key for entry in catalogue.models}
    requested = set(models)
    missing = requested - available
    if missing:
        raise ModelNotAvailableError(f"Models not present in LM Studio: {sorted(missing)}. Available: {sorted(available)}")
    logger.info("models.confirmed requested=%s", sorted(requested))


def discover_loaded_instances(lm_url: str, token: str, logger: logging.Logger) -> dict[str, str]:
    """Return ``{model_key: instance_id}`` for every model that already has a loaded instance."""
    catalogue = fetch_catalogue(lm_url, token, logger)
    loaded: dict[str, str] = {}
    for entry in catalogue.models:
        if entry.loaded_instances:
            loaded[entry.key] = entry.loaded_instances[0].id
    return loaded


def load_model(lm_url: str, token: str, model: str, context_length: int, logger: logging.Logger) -> str:
    """Issue ``POST /api/v1/models/load``; return new ``instance_id``."""
    request = ModelLoadRequest(model=model, context_length=context_length, echo_load_config=True)
    raw = http_post_json(f"{lm_url}/api/v1/models/load", request, token, logger)
    try:
        response = ModelLoadResponse.model_validate_json(raw)
    except ValueError as exc:
        raise LMStudioError(f"POST /api/v1/models/load invalid JSON: {exc}") from exc
    if not response.instance_id:
        raise LMStudioError(f"Model load did not return instance_id for {model}")
    seconds = response.load_time_seconds if response.load_time_seconds is not None else 0.0
    logger.info("model.loaded key=%s instance_id=%s load_seconds=%.2f", model, response.instance_id, seconds)
    return response.instance_id


def unload_model(lm_url: str, token: str, instance_id: str, logger: logging.Logger) -> None:
    """Best-effort unload of a single instance."""
    request = ModelUnloadRequest(instance_id=instance_id)
    try:
        http_post_json(f"{lm_url}/api/v1/models/unload", request, token, logger)
        logger.info("model.unloaded instance_id=%s", instance_id)
    except LMStudioError as exc:
        logger.warning("model.unload_failed instance_id=%s error=%s", instance_id, exc)


def ensure_model_loaded(lm_url: str, token: str, model: str, context_length: int, logger: logging.Logger) -> tuple[str, bool, int | None]:
    """Ensure ``model`` is loaded. Return ``(instance_id, loaded_by_us, request_context_length)``.

    When the instance is pre-existing, ``request_context_length`` is ``None`` so that subsequent
    chat requests omit the ``context_length`` field and honour the loaded instance's settings
    (avoids LM Studio forcibly reloading the instance with a different context).
    """
    loaded = discover_loaded_instances(lm_url, token, logger)
    if model in loaded:
        instance_id = loaded[model]
        logger.info("model.already_loaded key=%s instance_id=%s request_context_length=None", model, instance_id)
        return instance_id, False, None
    logger.info("model.loading key=%s context_length=%d", model, context_length)
    instance_id = load_model(lm_url, token, model, context_length, logger)
    return instance_id, True, context_length


def maybe_unload(lm_url: str, token: str, instance_id: str, loaded_by_us: bool, logger: logging.Logger) -> None:
    """Unload ``instance_id`` only if this run created it."""
    if not loaded_by_us:
        logger.info("model.unload_skipped reason=preexisting instance_id=%s", instance_id)
        return
    unload_model(lm_url, token, instance_id, logger)


def chat_complete(lm_url: str, token: str, model: str, system_prompt: str, user_input: str, context_length: int | None, max_output_tokens: int, logger: logging.Logger, reasoning: str | None = "off") -> tuple[str, ChatStats]:
    """Send a non-streaming chat request; return ``(message_text, stats)``.

    On 4xx ``reasoning`` rejection (model does not support the chosen setting), retries with
    the model's first supported reasoning value, then with no reasoning param. Falls back to
    concatenated reasoning content if the model only emits ``reasoning`` items.
    """
    fallback_chain: list[str | None] = [reasoning]
    if reasoning != "on":
        fallback_chain.append("on")
    if reasoning is not None:
        fallback_chain.append(None)
    raw: bytes | None = None
    last_client_error: LMStudioClientError | None = None
    for attempt_reasoning in fallback_chain:
        request = ChatRequest(model=model, input=user_input, system_prompt=system_prompt, context_length=context_length, max_output_tokens=max_output_tokens, reasoning=attempt_reasoning)
        try:
            raw = http_post_json(f"{lm_url}/api/v1/chat", request, token, logger)
            if attempt_reasoning != reasoning:
                logger.info("chat.reasoning_fallback_used model=%s reasoning=%s", model, attempt_reasoning)
            break
        except LMStudioClientError as exc:
            last_client_error = exc
            if "reasoning" in exc.body.lower():
                logger.info("chat.reasoning_rejected model=%s attempted=%s body_snippet=%s", model, attempt_reasoning, exc.body[:200])
                continue
            raise
    if raw is None:
        if last_client_error is not None:
            raise last_client_error
        raise LMStudioError(f"chat_complete exhausted reasoning fallback chain for model {model}")
    try:
        response = ChatResponse.model_validate_json(raw)
    except ValueError as exc:
        snippet = raw[:500].decode("utf-8", errors="replace")
        raise LMStudioError(f"POST /api/v1/chat invalid JSON: {exc} body_snippet={snippet!r}") from exc
    message_parts = [item.content for item in response.output if item.type == "message" and item.content]
    message_text = "\n".join(message_parts).strip()
    if not message_text:
        reasoning_parts = [item.content for item in response.output if item.type == "reasoning" and item.content]
        reasoning_text = "\n".join(reasoning_parts).strip()
        if reasoning_text:
            logger.warning("chat.no_message fallback_to_reasoning model=%s reasoning_chars=%d", model, len(reasoning_text))
            message_text = reasoning_text
    if not message_text:
        raise LMStudioError(f"LM Studio returned no usable content. Raw output items: {[item.model_dump() for item in response.output]}")
    stats = response.stats or ChatStats()
    return message_text, stats


def is_text_file(path: Path) -> bool:
    """Heuristic: read 4 KiB; reject if NUL byte found."""
    try:
        with path.open("rb") as handle:
            chunk = handle.read(4096)
    except OSError:
        return False
    if not chunk:
        return True
    return b"\x00" not in chunk


def read_text_truncated(path: Path, max_bytes: int) -> tuple[str, bool]:
    """Read up to ``max_bytes`` of text. Return ``(content, truncated)``."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        return f"[unreadable: {exc}]", False
    truncated = size > max_bytes
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            data = handle.read(max_bytes)
    except OSError as exc:
        return f"[unreadable: {exc}]", False
    if truncated:
        data += f"\n\n... [truncated; full size {size} bytes] ..."
    return data, truncated


def file_should_be_skipped(name: str) -> bool:
    """Skip junk basenames, generated outputs, and binary suffixes."""
    if name in WALK_IGNORE_FILE_NAMES:
        return True
    if name.endswith(WALK_IGNORE_FILE_SUFFIXES):
        return True
    if name in {OVERVIEW_FILENAME, IMPROVEMENTS_FILENAME, BACKLOG_FILENAME}:
        return True
    return False


DOCUMENTATION_FILE_SUFFIXES: tuple[str, ...] = (
    ".md", ".markdown", ".rst", ".txt", ".gsl", ".xml", ".html", ".adoc"
)


def is_documentation_only_dir(record: DirectoryRecord) -> bool:
    """Return True when every immediate file is a documentation/text artefact.

    Documentation directories (mirror trees of XML/GSL/Markdown guidelines, vendored
    references, etc.) confuse the LLM-driven review pipeline because the source
    material is prescriptive prose rather than code with reviewable behaviour. For
    these directories the engine writes a deterministic stub `_IMPROVEMENTS.md` so
    the structural contract holds.
    """
    if not record.files:
        return False
    return all(file_path.name.endswith(DOCUMENTATION_FILE_SUFFIXES) for file_path in record.files)


def build_documentation_stub_body(record: DirectoryRecord) -> str:
    """Build a deterministic `_IMPROVEMENTS.md` body for a documentation-only directory."""
    file_count = len(record.files)
    suffix_counts: dict[str, int] = {}
    for file_path in record.files:
        suffix = file_path.suffix or "(none)"
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
    suffix_summary = ", ".join(f"{count}× `{suffix}`" for suffix, count in sorted(suffix_counts.items()))
    summary_line = (
        f"This directory contains {file_count} documentation file(s) ({suffix_summary}); the contents are prescriptive "
        f"prose rather than executable code. No code-review findings apply."
    )
    return (
        f"## Summary\n\n{summary_line}\n\n"
        f"## Critical\n\nNone.\n\n"
        f"## High\n\nNone.\n\n"
        f"## Medium\n\nNone.\n\n"
        f"## Low\n\nNone.\n\n"
        f"## Already-good patterns\n\n"
        f"- Documentation collection ({suffix_summary}); review and refresh on the cadence used by the source "
        f"(this engine does not generate code-review findings for documentation-only directories).\n"
    )


def directory_should_be_skipped(name: str) -> bool:
    """Skip junk directory names."""
    return name in WALK_IGNORE_DIR_NAMES


def list_immediate_files(directory: Path) -> list[Path]:
    """Sorted list of non-skipped files directly in ``directory``."""
    files: list[Path] = []
    try:
        for entry in directory.iterdir():
            if entry.is_file() and not file_should_be_skipped(entry.name):
                files.append(entry)
    except OSError:
        return []
    files.sort(key=lambda p: p.name.lower())
    return files


def list_immediate_subdirs(directory: Path) -> list[Path]:
    """Sorted list of non-skipped immediate subdirectories."""
    subs: list[Path] = []
    try:
        for entry in directory.iterdir():
            if entry.is_dir() and not directory_should_be_skipped(entry.name):
                subs.append(entry)
    except OSError:
        return []
    subs.sort(key=lambda p: p.name.lower())
    return subs


def gather_directory_record(directory: Path, project_root: Path) -> DirectoryRecord:
    """Build a ``DirectoryRecord``."""
    files = tuple(list_immediate_files(directory))
    subdirs = tuple(list_immediate_subdirs(directory))
    overview_path = directory / OVERVIEW_FILENAME
    if directory == project_root:
        relative = "."
        parent: Path | None = None
    else:
        relative = str(directory.relative_to(project_root))
        parent = directory.parent
    return DirectoryRecord(path=directory, relative=relative, files=files, subdirs=subdirs, overview_path=overview_path, parent=parent)


def build_file_blocks(files: Iterable[Path]) -> tuple[list[str], int]:
    """Render the directory's immediate files as fenced markdown blocks."""
    blocks: list[str] = []
    used = 0
    count = 0
    for file_path in files:
        if count >= MAX_FILES_PER_DIR:
            blocks.append(f"_(remaining files not included; cap of {MAX_FILES_PER_DIR} reached.)_\n")
            break
        count += 1
        if not is_text_file(file_path):
            try:
                size = file_path.stat().st_size
            except OSError:
                size = -1
            blocks.append(f"#### `{file_path.name}`\n\n_Binary or non-text file; size {size} bytes._\n")
            continue
        content, truncated = read_text_truncated(file_path, MAX_FILE_BYTES)
        used += len(content)
        if used > MAX_TOTAL_INPUT_CHARS:
            blocks.append(f"_(remaining files truncated; aggregate cap {MAX_TOTAL_INPUT_CHARS} reached.)_\n")
            break
        suffix = file_path.suffix.lstrip(".") or "txt"
        marker = " [truncated]" if truncated else ""
        blocks.append(f"#### `{file_path.name}`{marker}\n\n```{suffix}\n{content}\n```\n")
    return blocks, used


def read_overview(directory: Path, max_bytes: int) -> str:
    """Read the directory's ``_DIRECTORY_OVERVIEW.md`` (truncated)."""
    overview = directory / OVERVIEW_FILENAME
    if not overview.exists():
        return "(missing _DIRECTORY_OVERVIEW.md)"
    content, _ = read_text_truncated(overview, max_bytes)
    return content


def build_context_block(record: DirectoryRecord, project_root: Path) -> str:
    """Assemble overview + parent + sibling/child overview context."""
    parts: list[str] = []
    parts.append("### This directory's overview\n")
    parts.append(read_overview(record.path, MAX_OVERVIEW_CONTEXT_CHARS * 2))
    parts.append("")
    if record.parent is not None and record.parent != project_root.parent:
        parent_overview = record.parent / OVERVIEW_FILENAME
        if parent_overview.exists():
            parts.append("### Parent directory overview (for context)\n")
            parts.append(read_overview(record.parent, MAX_OVERVIEW_CONTEXT_CHARS))
            parts.append("")
    if record.subdirs:
        child_chunks: list[str] = []
        for sub in record.subdirs:
            sub_overview = sub / OVERVIEW_FILENAME
            if sub_overview.exists():
                child_chunks.append(f"#### `{sub.name}/_DIRECTORY_OVERVIEW.md`\n\n{read_overview(sub, MAX_OVERVIEW_CONTEXT_CHARS)}\n")
        if child_chunks:
            parts.append("### Child directory overviews (for context)\n")
            parts.extend(child_chunks)
    if record.parent is not None:
        siblings: list[Path] = [s for s in list_immediate_subdirs(record.parent) if s != record.path]
        sibling_chunks: list[str] = []
        for sib in siblings[:6]:
            sib_overview = sib / OVERVIEW_FILENAME
            if sib_overview.exists():
                sibling_chunks.append(f"#### `../{sib.name}/_DIRECTORY_OVERVIEW.md`\n\n{read_overview(sib, MAX_OVERVIEW_CONTEXT_CHARS // 2)}\n")
        if sibling_chunks:
            parts.append("### Sibling directory overviews (for context)\n")
            parts.extend(sibling_chunks)
    return "\n".join(parts)


def build_draft_prompt(record: DirectoryRecord, project_root: Path, file_blocks: list[str], context_block: str) -> str:
    """Construct the user prompt for the draft pass."""
    header = (
        f"You are reviewing the directory `{record.relative}` of project `{project_root.name}`.\n\n"
        f"Produce the body of `_IMPROVEMENTS.md` for this directory using the EXACT structure required by the system prompt. "
        f"Do not add a top-level `# Title` heading -- the wrapper writes title and provenance metadata. Begin with `## Summary`.\n\n"
    )
    parts: list[str] = [header, context_block, "\n### Source files in this directory\n"]
    if file_blocks:
        parts.extend(file_blocks)
    else:
        parts.append("(none)\n")
    parts.append(
        "\nReview ONLY the content of THIS directory. Use parent/sibling/child overviews only as context to understand "
        "this directory's role; do NOT issue findings about files in other directories.\n\n"
        "Output Markdown only -- no preamble, no closing summary outside the section structure. Begin with `## Summary`."
    )
    return "\n".join(parts)


def build_verify_prompt(record: DirectoryRecord, project_root: Path, draft: str, file_blocks: list[str]) -> str:
    """Construct the user prompt for the verification pass."""
    header = (
        f"You are verifying the draft `_IMPROVEMENTS.md` for directory `{record.relative}` of project `{project_root.name}`.\n\n"
        f"You will receive the draft followed by the directory overview and the actual source files. Verify each item against "
        f"the source. Drop unsupported items. Fix citations. Output the FINAL `_IMPROVEMENTS.md` body (no preamble, begin with "
        f"`## Summary`).\n\n"
        f"### Draft to verify\n\n{draft}\n\n"
        f"### Directory overview\n\n{read_overview(record.path, MAX_OVERVIEW_CONTEXT_CHARS * 2)}\n\n"
        f"### Source files in this directory\n"
    )
    parts: list[str] = [header]
    if file_blocks:
        parts.extend(file_blocks)
    else:
        parts.append("(none)\n")
    parts.append(
        "\nProduce the final `_IMPROVEMENTS.md` body. Preserve the exact section structure. Output Markdown only. "
        "Begin with `## Summary`."
    )
    return "\n".join(parts)


def render_improvements_file(record: DirectoryRecord, project_root: Path, body: str, draft_model: str, verify_model: str, source_hash: str, draft_stats: ChatStats, verify_stats: ChatStats) -> str:
    """Wrap the verified body with deterministic provenance header."""
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    title_path = record.relative if record.relative != "." else project_root.name
    stats_line = (
        f"draft_in={draft_stats.input_tokens} draft_out={draft_stats.total_output_tokens} "
        f"verify_in={verify_stats.input_tokens} verify_out={verify_stats.total_output_tokens}"
    )
    header = (
        f"# Directory Improvements: `{title_path}`\n\n"
        f"{GENERATION_MARKER}\n"
        f"<!-- generated_at={timestamp} -->\n"
        f"<!-- draft_model={draft_model} -->\n"
        f"<!-- verify_model={verify_model} -->\n"
        f"<!-- {stats_line} -->\n"
        f"{SOURCE_HASH_PREFIX}{source_hash} -->\n\n"
    )
    return header + body.strip() + "\n"


def write_atomic(path: Path, content: str) -> None:
    """Write to a sibling tmp, then ``os.replace`` for atomic update."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(tmp, path)


def compute_source_hash(record: DirectoryRecord) -> str:
    """Hash the directory's overview + immediate files for idempotency."""
    hasher = hashlib.sha256()
    overview = record.path / OVERVIEW_FILENAME
    if overview.exists():
        try:
            stat = overview.stat()
            hasher.update(b"OVERVIEW\x00")
            hasher.update(str(stat.st_size).encode("utf-8"))
            hasher.update(b"\x00")
            hasher.update(str(int(stat.st_mtime)).encode("utf-8"))
            hasher.update(b"\x01")
        except OSError:
            pass
    for file_path in record.files:
        try:
            stat = file_path.stat()
        except OSError:
            continue
        hasher.update(file_path.name.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(str(stat.st_size).encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(str(int(stat.st_mtime)).encode("utf-8"))
        hasher.update(b"\x02")
    return hasher.hexdigest()


def existing_improvements_hash(path: Path) -> str | None:
    """Read recorded ``source-sha256`` from an existing improvements file."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle):
                if line_number > 20:
                    break
                if line.startswith(SOURCE_HASH_PREFIX):
                    match = re.search(r"sha256=([0-9a-f]{64})", line)
                    if match:
                        return match.group(1)
    except OSError:
        return None
    return None


def collect_directories_with_overviews(project_root: Path) -> list[Path]:
    """Every non-ignored directory that has an ``_DIRECTORY_OVERVIEW.md``."""
    selected: list[Path] = []
    for current, dirs, files in os.walk(project_root, topdown=True):
        dirs[:] = [d for d in dirs if not directory_should_be_skipped(d)]
        if OVERVIEW_FILENAME in files:
            selected.append(Path(current))
    selected.sort(key=lambda p: str(p).lower())
    return selected


def collect_improvements_files(project_root: Path) -> list[Path]:
    """All ``_IMPROVEMENTS.md`` files under the project root, sorted."""
    selected: list[Path] = []
    for current, dirs, files in os.walk(project_root, topdown=True):
        dirs[:] = [d for d in dirs if not directory_should_be_skipped(d)]
        if IMPROVEMENTS_FILENAME in files:
            selected.append(Path(current) / IMPROVEMENTS_FILENAME)
    selected.sort(key=lambda p: str(p).lower())
    return selected


def build_directory_tree(project_root: Path, max_depth: int = 4) -> str:
    """Produce a simple ASCII tree (no `tree` binary required)."""
    lines: list[str] = [project_root.name + "/"]

    def walk(current: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        subdirs = list_immediate_subdirs(current)
        for index, sub in enumerate(subdirs):
            connector = "└── " if index == len(subdirs) - 1 else "├── "
            lines.append(prefix + connector + sub.name + "/")
            child_prefix = prefix + ("    " if index == len(subdirs) - 1 else "│   ")
            walk(sub, child_prefix, depth + 1)

    walk(project_root, "", 1)
    return "\n".join(lines)


def build_aggregate_prompt(project_root: Path, improvements_files: list[Path]) -> str:
    """Assemble the aggregator user prompt."""
    tree_text = build_directory_tree(project_root)
    root_overview_text = read_overview(project_root, MAX_OVERVIEW_CONTEXT_CHARS * 2)
    parts: list[str] = [
        f"You are aggregating per-directory `_IMPROVEMENTS.md` files for project `{project_root.name}` into a single project-wide backlog.\n",
        "### Project tree\n",
        "```\n" + tree_text + "\n```\n",
        "### Project root `_DIRECTORY_OVERVIEW.md`\n\n" + root_overview_text + "\n"
    ]
    used = sum(len(p) for p in parts)
    parts.append("### All per-directory `_IMPROVEMENTS.md` files\n")
    for path in improvements_files:
        relative = path.relative_to(project_root) if path.is_relative_to(project_root) else path
        body, _ = read_text_truncated(path, MAX_IMPROVEMENT_CONTEXT_CHARS)
        chunk = f"#### `{relative}`\n\n{body}\n"
        if used + len(chunk) > MAX_TOTAL_INPUT_CHARS * 2:
            parts.append("_(remaining improvements files truncated due to context cap)_\n")
            break
        parts.append(chunk)
        used += len(chunk)
    parts.append(
        "\nProduce the project backlog using the EXACT structure from the system prompt. "
        "Output Markdown only. Begin with `# Project Improvement Backlog`."
    )
    return "\n".join(parts)


def render_backlog_file(project_root: Path, body: str, models: tuple[str, str, str], stats: ChatStats) -> str:
    """Wrap aggregator output with provenance header."""
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    draft_model, verify_model, aggregate_model = models
    body_clean = body.strip()
    if body_clean.startswith("# Project Improvement Backlog"):
        body_clean = body_clean[len("# Project Improvement Backlog"):].lstrip("\n")
    header = (
        f"# Project Improvement Backlog -- `{project_root.name}`\n\n"
        f"{BACKLOG_MARKER}\n"
        f"<!-- generated_at={timestamp} -->\n"
        f"<!-- draft_model={draft_model} -->\n"
        f"<!-- verify_model={verify_model} -->\n"
        f"<!-- aggregator_model={aggregate_model} -->\n"
        f"<!-- aggregator_in={stats.input_tokens} aggregator_out={stats.total_output_tokens} aggregator_tps={stats.tokens_per_second} -->\n\n"
    )
    return header + body_clean + "\n"


def relative_path_digest(relative: str) -> str:
    """Stable short identifier for a relative path used in draft filenames."""
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]


def select_run_dir(work_root: Path, run_id: str | None, resume: bool, logger: logging.Logger) -> tuple[Path, str]:
    """Resolve the per-run scratch dir. Honour ``--resume`` by selecting the latest existing run."""
    base = work_root / "improver"
    base.mkdir(parents=True, exist_ok=True)
    if resume:
        existing = sorted(d for d in base.iterdir() if d.is_dir() and d.name.startswith(RUN_DIR_PREFIX))
        if not existing:
            raise ImproverError(f"--resume requested but no prior run directories under {base}")
        chosen = existing[-1]
        chosen_id = chosen.name[len(RUN_DIR_PREFIX):]
        logger.info("run.resume id=%s dir=%s", chosen_id, chosen)
        return chosen, chosen_id
    chosen_id = run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    chosen = base / f"{RUN_DIR_PREFIX}{chosen_id}"
    chosen.mkdir(parents=True, exist_ok=True)
    logger.info("run.new id=%s dir=%s", chosen_id, chosen)
    return chosen, chosen_id


def append_manifest(manifest_path: Path, entry: dict[str, str | int | float | None]) -> None:
    """Append one JSONL record to the run manifest."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def read_manifest(manifest_path: Path) -> list[dict[str, str | int | float | None]]:
    """Read all JSONL manifest entries."""
    if not manifest_path.exists():
        return []
    out: list[dict[str, str | int | float | None]] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def write_documentation_stub(record: DirectoryRecord, project_root: Path, draft_model: str, verify_model: str, source_hash: str, logger: logging.Logger) -> None:
    """Write a deterministic `_IMPROVEMENTS.md` for a documentation-only directory."""
    body = build_documentation_stub_body(record)
    rendered = render_improvements_file(
        record=record,
        project_root=project_root,
        body=body,
        draft_model=f"{draft_model} (bypassed)",
        verify_model=f"{verify_model} (bypassed)",
        source_hash=source_hash,
        draft_stats=ChatStats(),
        verify_stats=ChatStats()
    )
    write_atomic(record.path / IMPROVEMENTS_FILENAME, rendered)
    logger.info("documentation_stub.written relative=%s files=%d", record.relative, len(record.files))


def run_phase_drafts(directories: list[Path], project_root: Path, run_dir: Path, lm_url: str, token: str, draft_model: str, verify_model: str, context_length: int, force: bool, logger: logging.Logger) -> tuple[int, int, int, int]:
    """Phase A: produce drafts (or documentation stubs) for every directory.

    Return ``(drafted, skipped, failed, doc_stubs_written)``.
    """
    drafted = 0
    skipped = 0
    failed = 0
    doc_stubs = 0
    instance_id, ours, request_context_length = ensure_model_loaded(lm_url, token, draft_model, context_length, logger)
    manifest_path = run_dir / "manifest.jsonl"
    try:
        for index, directory in enumerate(directories, start=1):
            relative = "." if directory == project_root else str(directory.relative_to(project_root))
            record = gather_directory_record(directory, project_root)
            improvements_path = directory / IMPROVEMENTS_FILENAME
            source_hash = compute_source_hash(record)
            if not force:
                prior = existing_improvements_hash(improvements_path)
                if prior == source_hash:
                    logger.info("draft.skip_existing index=%d/%d relative=%s reason=hash_match", index, len(directories), relative)
                    skipped += 1
                    continue
            if is_documentation_only_dir(record):
                logger.info("documentation_stub.dispatch index=%d/%d relative=%s files=%d", index, len(directories), relative, len(record.files))
                write_documentation_stub(record, project_root, draft_model, verify_model, source_hash, logger)
                doc_stubs += 1
                continue
            digest = relative_path_digest(relative)
            draft_path = run_dir / f"{digest}.draft.md"
            if not force and draft_path.exists():
                logger.info("draft.skip_existing_draft index=%d/%d relative=%s path=%s", index, len(directories), relative, draft_path)
                skipped += 1
                continue
            file_blocks, _ = build_file_blocks(record.files)
            context_block = build_context_block(record, project_root)
            draft_prompt = build_draft_prompt(record, project_root, file_blocks, context_block)
            logger.info("draft.start index=%d/%d relative=%s prompt_chars=%d", index, len(directories), relative, len(draft_prompt))
            started = time.monotonic()
            try:
                draft_body, draft_stats = chat_complete(
                    lm_url=lm_url,
                    token=token,
                    model=draft_model,
                    system_prompt=DRAFT_SYSTEM_PROMPT,
                    user_input=draft_prompt,
                    context_length=request_context_length,
                    max_output_tokens=DEFAULT_DRAFT_MAX_OUTPUT,
                    logger=logger
                )
            except (LMStudioError, ImproverError, OSError) as exc:
                failed += 1
                logger.exception("draft.failed relative=%s error=%s", relative, exc)
                continue
            elapsed = time.monotonic() - started
            logger.info("draft.done relative=%s elapsed=%.1fs in=%s out=%s tps=%s", relative, elapsed, draft_stats.input_tokens, draft_stats.total_output_tokens, draft_stats.tokens_per_second)
            write_atomic(draft_path, draft_body.strip() + "\n")
            entry: dict[str, str | int | float | None] = {
                "relative": relative,
                "directory": str(directory),
                "draft_path": str(draft_path),
                "source_hash": source_hash,
                "draft_in_tokens": draft_stats.input_tokens,
                "draft_out_tokens": draft_stats.total_output_tokens,
                "draft_tps": draft_stats.tokens_per_second
            }
            append_manifest(manifest_path, entry)
            drafted += 1
    finally:
        maybe_unload(lm_url, token, instance_id, ours, logger)
    logger.info("phase.draft.done drafted=%d skipped=%d failed=%d doc_stubs=%d", drafted, skipped, failed, doc_stubs)
    return drafted, skipped, failed, doc_stubs


def run_phase_verify(project_root: Path, run_dir: Path, lm_url: str, token: str, draft_model: str, verify_model: str, context_length: int, logger: logging.Logger) -> tuple[int, int]:
    """Phase B: verify each staged draft and write the per-directory ``_IMPROVEMENTS.md``. Return (written, failed)."""
    manifest_path = run_dir / "manifest.jsonl"
    entries = read_manifest(manifest_path)
    if not entries:
        logger.info("phase.verify.no_entries reason=manifest_empty")
        return 0, 0
    written = 0
    failed = 0
    instance_id, ours, request_context_length = ensure_model_loaded(lm_url, token, verify_model, context_length, logger)
    try:
        total = len(entries)
        for index, entry in enumerate(entries, start=1):
            relative = str(entry.get("relative") or "")
            directory_str = str(entry.get("directory") or "")
            draft_path_str = str(entry.get("draft_path") or "")
            source_hash = str(entry.get("source_hash") or "")
            if not relative or not directory_str or not draft_path_str:
                failed += 1
                logger.warning("verify.skip_malformed_entry entry=%s", entry)
                continue
            directory = Path(directory_str)
            draft_path = Path(draft_path_str)
            if not draft_path.exists():
                failed += 1
                logger.warning("verify.draft_missing relative=%s path=%s", relative, draft_path)
                continue
            draft_body = draft_path.read_text(encoding="utf-8")
            draft_in = entry.get("draft_in_tokens")
            draft_out = entry.get("draft_out_tokens")
            draft_tps = entry.get("draft_tps")
            draft_stats = ChatStats(
                input_tokens=int(draft_in) if isinstance(draft_in, (int, float)) else None,
                total_output_tokens=int(draft_out) if isinstance(draft_out, (int, float)) else None,
                tokens_per_second=float(draft_tps) if isinstance(draft_tps, (int, float)) else None
            )
            record = gather_directory_record(directory, project_root)
            file_blocks, _ = build_file_blocks(record.files)
            verify_prompt = build_verify_prompt(record, project_root, draft_body, file_blocks)
            logger.info("verify.start index=%d/%d relative=%s prompt_chars=%d", index, total, relative, len(verify_prompt))
            started = time.monotonic()
            try:
                verified_body, verify_stats = chat_complete(
                    lm_url=lm_url,
                    token=token,
                    model=verify_model,
                    system_prompt=VERIFY_SYSTEM_PROMPT,
                    user_input=verify_prompt,
                    context_length=request_context_length,
                    max_output_tokens=DEFAULT_VERIFY_MAX_OUTPUT,
                    logger=logger
                )
            except (LMStudioError, ImproverError, OSError) as exc:
                failed += 1
                logger.exception("verify.failed relative=%s error=%s", relative, exc)
                continue
            elapsed = time.monotonic() - started
            logger.info("verify.done relative=%s elapsed=%.1fs in=%s out=%s tps=%s", relative, elapsed, verify_stats.input_tokens, verify_stats.total_output_tokens, verify_stats.tokens_per_second)
            improvements_path = directory / IMPROVEMENTS_FILENAME
            rendered = render_improvements_file(
                record=record,
                project_root=project_root,
                body=verified_body,
                draft_model=draft_model,
                verify_model=verify_model,
                source_hash=source_hash,
                draft_stats=draft_stats,
                verify_stats=verify_stats
            )
            write_atomic(improvements_path, rendered)
            written += 1
            try:
                draft_path.unlink()
            except OSError as exc:
                logger.warning("verify.draft_cleanup_failed path=%s error=%s", draft_path, exc)
    finally:
        maybe_unload(lm_url, token, instance_id, ours, logger)
    logger.info("phase.verify.done written=%d failed=%d", written, failed)
    return written, failed


def run_phase_aggregate(project_root: Path, lm_url: str, token: str, models: tuple[str, str, str], context_length: int, logger: logging.Logger) -> Path:
    """Phase C: build the project-wide backlog using the aggregate model.

    Honours whatever ``context_length`` the loaded instance has by omitting the field
    from the chat request when the instance is pre-loaded.
    """
    aggregate_model = models[2]
    instance_id, ours, request_context_length = ensure_model_loaded(lm_url, token, aggregate_model, context_length, logger)
    try:
        improvements_files = collect_improvements_files(project_root)
        if not improvements_files:
            raise ImproverError(f"No `{IMPROVEMENTS_FILENAME}` files found under {project_root}")
        logger.info("aggregate.gather count=%d", len(improvements_files))
        user_prompt = build_aggregate_prompt(project_root, improvements_files)
        logger.info("aggregate.start prompt_chars=%d request_context_length=%s", len(user_prompt), request_context_length)
        started = time.monotonic()
        body, stats = chat_complete(
            lm_url=lm_url,
            token=token,
            model=aggregate_model,
            system_prompt=AGGREGATE_SYSTEM_PROMPT,
            user_input=user_prompt,
            context_length=request_context_length,
            max_output_tokens=DEFAULT_AGGREGATE_MAX_OUTPUT,
            logger=logger,
            reasoning="on"
        )
        elapsed = time.monotonic() - started
        logger.info("aggregate.done elapsed=%.1fs in=%s out=%s tps=%s", elapsed, stats.input_tokens, stats.total_output_tokens, stats.tokens_per_second)
        rendered = render_backlog_file(project_root, body, models, stats)
        backlog_path = project_root / BACKLOG_FILENAME
        write_atomic(backlog_path, rendered)
        return backlog_path
    finally:
        maybe_unload(lm_url, token, instance_id, ours, logger)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse engine CLI arguments."""
    parser = argparse.ArgumentParser(description="project_analyzer improver engine")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--lm-url", default=DEFAULT_LM_URL)
    parser.add_argument("--draft-model", default=DEFAULT_DRAFT_MODEL)
    parser.add_argument("--verify-model", default=DEFAULT_VERIFY_MODEL)
    parser.add_argument("--aggregate-model", default=DEFAULT_AGGREGATE_MODEL)
    parser.add_argument("--context-length", type=int, default=DEFAULT_CONTEXT_LENGTH)
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="Regenerate even when source hash matches.")
    parser.add_argument("--skip-aggregate", action="store_true", help="Run only per-directory phases.")
    parser.add_argument("--only-aggregate", action="store_true", help="Run only the project backlog phase.")
    parser.add_argument("--resume", action="store_true", help="Reuse the latest run's drafts; skip Phase A.")
    return parser.parse_args(argv)


def main() -> int:
    """Entry point. Returns process exit code."""
    args = parse_args(sys.argv[1:])
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        sys.stderr.write(f"ERROR: not a directory: {project_root}\n")
        return 2
    if not (project_root / OVERVIEW_FILENAME).exists():
        sys.stderr.write(f"ERROR: project root has no {OVERVIEW_FILENAME}. Run analyze_project.sh first.\n")
        return 3
    logger = configure_logging(args.log_file)
    token = os.environ.get("LM_API_TOKEN", "")
    logger.info("=" * 72)
    logger.info("improver.start project=%s draft=%s verify=%s aggregate=%s log=%s resume=%s force=%s skip_aggregate=%s only_aggregate=%s", project_root, args.draft_model, args.verify_model, args.aggregate_model, args.log_file, args.resume, args.force, args.skip_aggregate, args.only_aggregate)
    requested_models = [args.draft_model, args.verify_model, args.aggregate_model]
    try:
        ensure_models_available(args.lm_url, token, requested_models, logger)
    except (LMStudioError, ModelNotAvailableError) as exc:
        logger.exception("lmstudio.readiness_failed error=%s", exc)
        return 3
    drafted = 0
    skipped = 0
    draft_failed = 0
    verify_written = 0
    verify_failed = 0
    aggregate_failed = 0
    if not args.only_aggregate:
        directories = collect_directories_with_overviews(project_root)
        logger.info("walk.discovered count=%d", len(directories))
        if not directories:
            logger.error("no directories with %s found; analyzer must run first", OVERVIEW_FILENAME)
            return 3
        try:
            run_dir, run_id = select_run_dir(args.work_root, None, args.resume, logger)
        except ImproverError as exc:
            logger.exception("run_dir.failed error=%s", exc)
            return 3
        if not args.resume:
            try:
                drafted, skipped, draft_failed, doc_stubs = run_phase_drafts(
                    directories=directories,
                    project_root=project_root,
                    run_dir=run_dir,
                    lm_url=args.lm_url,
                    token=token,
                    draft_model=args.draft_model,
                    verify_model=args.verify_model,
                    context_length=args.context_length,
                    force=args.force,
                    logger=logger
                )
                logger.info("phase.draft.summary drafted=%d skipped=%d failed=%d doc_stubs=%d", drafted, skipped, draft_failed, doc_stubs)
            except (LMStudioError, ImproverError, OSError) as exc:
                logger.exception("phase.draft.failed error=%s", exc)
                return 3
        else:
            logger.info("phase.draft.skipped reason=resume run_id=%s", run_id)
        try:
            verify_written, verify_failed = run_phase_verify(
                project_root=project_root,
                run_dir=run_dir,
                lm_url=args.lm_url,
                token=token,
                draft_model=args.draft_model,
                verify_model=args.verify_model,
                context_length=args.context_length,
                logger=logger
            )
        except (LMStudioError, ImproverError, OSError) as exc:
            logger.exception("phase.verify.failed error=%s", exc)
            return 3
    if not args.skip_aggregate:
        try:
            backlog_path = run_phase_aggregate(
                project_root=project_root,
                lm_url=args.lm_url,
                token=token,
                models=(args.draft_model, args.verify_model, args.aggregate_model),
                context_length=args.context_length,
                logger=logger
            )
            logger.info("aggregate.written path=%s", backlog_path)
        except (LMStudioError, ImproverError, OSError) as exc:
            aggregate_failed = 1
            logger.exception("phase.aggregate.failed error=%s", exc)
    total_failed = draft_failed + verify_failed + aggregate_failed
    logger.info("improver.done drafted=%d skipped=%d verify_written=%d draft_failed=%d verify_failed=%d aggregate_failed=%d", drafted, skipped, verify_written, draft_failed, verify_failed, aggregate_failed)
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
