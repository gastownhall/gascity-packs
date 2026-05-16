#!/usr/bin/env python3
"""project_analyzer engine.

Walks a target project bottom-up. For every directory, produces a
standardized `_DIRECTORY_OVERVIEW.md` file by sending the directory's
tree, immediate file contents, and (for non-leaf directories) child
overview files to a local LM Studio server.

Invoked by ``analyze_project.sh``. Uses LM Studio's
``POST /api/v1/chat`` endpoint (non-streaming).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import re
import subprocess
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
GENERATION_MARKER = "<!-- project_analyzer:generated -->"
SOURCE_HASH_PREFIX = "<!-- project_analyzer:source-sha256="

TREE_IGNORE_PATTERNS: tuple[str, ...] = (
    "_*", "build", "coverage", "DS_Store", "next", "nox", "npm", "nuxt",
    "pnpm-store", "pytest_cache", "ruff_cache", "scratch", "Spotlight-V100",
    "svelte-kit", "TemporaryItems", "tmp", "tox", "Trash*", "turbo", "venv",
    "work", "*.log", "*.tmp", "bin", "dist", "htmlcov", "node_modules", "obj",
    "target", "__pycache__", ".git", ".idea", ".vscode", ".DS_Store",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".nox", ".next",
    ".nuxt", ".turbo", ".svelte-kit", ".pnpm-store", ".venv", ".cache",
    "Trashes", ".Trashes", ".claude", ".errors", ".review_logs", ".scratch"
    ".utilities", "__OLD", "_logs", ".work", ".logs"
)

WALK_IGNORE_DIR_NAMES: frozenset[str] = frozenset({
    "__pycache__", "node_modules", "dist", "build", "target", "venv", ".venv",
    ".git", ".idea", ".vscode", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".tox", ".nox", ".next", ".nuxt", ".turbo", ".svelte-kit", ".pnpm-store",
    "coverage", "htmlcov", "obj", "bin", ".cache",
    "scratch", "tmp", "work", ".work", ".logs", "__OLD"
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

MAX_FILE_BYTES = 6000
MAX_FILES_PER_DIR = 40
MAX_CHILD_OVERVIEWS = 40
MAX_CHILD_OVERVIEW_BYTES = 4000
MAX_TOTAL_INPUT_CHARS = 90_000
TREE_DEPTH_LEAF = 2
TREE_DEPTH_INNER = 3

HTTP_READ_TIMEOUT_SECONDS = 1500
MAX_RETRIES = 4
INITIAL_RETRY_DELAY_SECONDS = 5
MAX_RETRY_DELAY_SECONDS = 60

DEFAULT_MODEL = "qwen/qwen3-coder-next"
DEFAULT_LM_URL = "http://localhost:1234"
DEFAULT_CONTEXT_LENGTH = 65536
DEFAULT_MAX_OUTPUT_TOKENS = 32768

SYSTEM_PROMPT = """You are an expert code archaeologist and technical writer.

You produce concise, factual, production-grade overviews of directories
inside a software project. Your output is consumed by other LLMs that are
navigating the project, so it MUST be:

- Strictly factual: describe only what is present in the supplied content;
  never invent functions, parameters, return values, types, flags, or
  behaviour. If a fact is not in the supplied material, do not state it.
- Standardized: follow the exact section structure the user supplies, in
  order, with no additions or omissions.
- Concise: short, dense sentences; no marketing language; no filler;
  no rhetorical questions; no "this directory contains..." padding.
- Symbol-rich: name the actual classes, functions, constants, types,
  endpoints, environment variables, and CLI flags that appear in the
  source. Quote identifiers in backticks.
- Contract-aware: when visible, include parameter names and types,
  return values, exit codes, side effects, and error paths.
- Subtree-aware: when summarising a directory that has child directories
  with their own overviews, reference those overviews by relative path
  and do NOT duplicate their detail.

Never invent file names. Never claim a function or class exists unless it
appears in the supplied content. Binary or unreadable files: say so plainly.
Unclear purpose: say so plainly. Do not apologise. Do not editorialise.
Do not include a preamble or trailing summary outside the supplied
section structure. Output raw GitHub-flavoured Markdown only.
"""

LEAF_TEMPLATE = """## Purpose

A 1-3 sentence statement of what this directory exists to do, grounded in
the supplied files.

## Files

For each file in this directory, produce a `### <filename>` subsection with
the following bullets, in order. Omit a bullet only when the underlying
fact is not visible in the file.

- **Type**: language / format / role (e.g., "Python module", "Bash entrypoint
  script", "JSON config", "XML guideline document").
- **Purpose**: one sentence.
- **Public surface**: list every defined function/class/constant/type with a
  one-line description. For functions include signature parameters and
  return type when visible. For shell scripts list functions and the main
  flow. For config/markup list the top-level keys/sections.
- **Inputs / arguments / environment**: CLI args, environment variables,
  required files, stdin contracts.
- **Outputs / side effects**: stdout/stderr behaviour, files written,
  network calls, exit codes.
- **Notable dependencies**: imports/requires of note (skip stdlib).
- **Notes**: anything else load-bearing for an LLM consumer (failure modes,
  invariants, gotchas).

## How to use this directory

A short paragraph (2-4 sentences) describing how an LLM should approach
modifying or extending code in this directory: extension points, ordering
constraints, files that must change together.
"""

INNER_TEMPLATE = """## Purpose

A 1-3 sentence statement of what this subtree exists to do, grounded in
the supplied tree, files, and child overviews.

## Files in this directory

For each file directly in this directory (not in subdirectories), produce
a `### <filename>` subsection with bullets:

- **Type**: language / format / role.
- **Purpose**: one sentence.
- **Public surface**: a brief listing of major symbols, sections, or
  configuration keys. Less detail than a leaf overview - just enough to
  orient an LLM.
- **Notes**: anything load-bearing.

If there are no files directly in this directory (only subdirectories),
state that explicitly and skip the per-file detail.

## Subdirectories

For each immediate subdirectory, produce a `### <subdir>/` subsection with:

- **Summary**: one or two sentences describing the role of that subtree,
  drawn from its overview file.
- **See**: `<subdir>/_DIRECTORY_OVERVIEW.md` for full detail.

Do NOT duplicate the detail of child overviews here. Higher-level
synthesis only.

## How this subtree fits together

A short paragraph (2-5 sentences) explaining how the subdirectories and
top-level files relate to each other: data flow, dependency direction,
ordering constraints, shared contracts.
"""


class AnalyzerError(Exception):
    """Base exception for project_analyzer."""


class LMStudioError(AnalyzerError):
    """LM Studio communication failed."""


class ModelNotAvailableError(AnalyzerError):
    """Requested model is not available in LM Studio."""


class ModelEntry(BaseModel):
    """Single model entry from ``GET /api/v1/models``."""

    model_config = ConfigDict(extra="allow")
    key: str = Field(..., description="Unique model identifier")


class ModelListResponse(BaseModel):
    """Response from ``GET /api/v1/models``."""

    model_config = ConfigDict(extra="allow")
    models: list[ModelEntry] = Field(default_factory=list, description="Available models")


class ModelLoadResponse(BaseModel):
    """Response from ``POST /api/v1/models/load``."""

    model_config = ConfigDict(extra="allow")
    instance_id: str | None = Field(default=None, description="Loaded instance identifier")
    load_time_seconds: float | None = Field(default=None, description="Model load wall-clock time")
    status: str | None = Field(default=None, description="Load status")


class ChatStats(BaseModel):
    """Token-usage statistics on a chat response."""

    model_config = ConfigDict(extra="allow")
    input_tokens: int | None = Field(default=None, description="Input tokens consumed")
    total_output_tokens: int | None = Field(default=None, description="Output tokens generated")
    tokens_per_second: float | None = Field(default=None, description="Generation throughput")


class ChatOutputItem(BaseModel):
    """One item in a chat response ``output`` array."""

    model_config = ConfigDict(extra="allow")
    type: str = Field(..., description="Output item discriminator")
    content: str | None = Field(default=None, description="Message content for type=message")


class ChatResponse(BaseModel):
    """Response from ``POST /api/v1/chat`` (non-streaming)."""

    model_config = ConfigDict(extra="allow")
    output: list[ChatOutputItem] = Field(default_factory=list, description="Output items in order")
    stats: ChatStats | None = Field(default=None, description="Generation statistics")


@dataclass(frozen=True, slots=True)
class DirectoryRecord:
    """Snapshot of a single directory's content for prompt construction."""

    path: Path
    relative: str
    files: tuple[Path, ...]
    subdirs: tuple[Path, ...]
    has_child_overviews: bool


def configure_logging(log_path: Path) -> logging.Logger:
    """Wire structured logging to both stderr and a project-local log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    project_logger = logging.getLogger("project_analyzer")
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
    """POST JSON body, return raw response bytes; retry with exponential backoff."""
    payload = body.model_dump_json(exclude_none=True).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    delay = INITIAL_RETRY_DELAY_SECONDS
    last_error: Exception = RuntimeError("no attempt made")
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
            detail = detail_bytes.decode("utf-8", errors="replace")[:500]
            logger.warning("http.post.http_error url=%s attempt=%d/%d code=%s detail=%s", url, attempt, MAX_RETRIES, exc.code, detail)
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
    raise LMStudioError(f"POST {url} failed after {MAX_RETRIES} attempts: {last_error}")


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


class ModelLoadRequest(BaseModel):
    """Body for ``POST /api/v1/models/load``."""

    model_config = ConfigDict(extra="forbid")
    model: str = Field(..., description="Model key to load")
    context_length: int = Field(..., gt=0, description="Tokens of context to enable")
    echo_load_config: bool = Field(default=True, description="Return final load config in response")


class ChatInputItem(BaseModel):
    """Text input item for the chat request."""

    model_config = ConfigDict(extra="forbid")
    type: str = Field(default="text", description="Input item type")
    content: str = Field(..., description="Text content")


class ChatRequest(BaseModel):
    """Body for ``POST /api/v1/chat``."""

    model_config = ConfigDict(extra="forbid")
    model: str = Field(..., description="Model key")
    input: str = Field(..., description="User input as a plain string")
    system_prompt: str = Field(..., description="System message")
    stream: bool = Field(default=False, description="Stream SSE if true")
    store: bool = Field(default=False, description="Persist response thread server-side")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="Sampling temperature")
    context_length: int = Field(..., gt=0, description="Context window for this request")
    max_output_tokens: int = Field(..., gt=0, description="Cap on generated tokens")


def ensure_lm_studio_ready(lm_url: str, token: str, model: str, context_length: int, logger: logging.Logger) -> None:
    """Confirm the server is reachable, the model exists, and trigger a load."""
    logger.info("lmstudio.check url=%s model=%s", lm_url, model)
    raw = http_get_bytes(f"{lm_url}/api/v1/models", token, logger)
    try:
        models_response = ModelListResponse.model_validate_json(raw)
    except ValueError as exc:
        raise LMStudioError(f"GET /api/v1/models returned invalid JSON: {exc}") from exc
    available = {entry.key for entry in models_response.models}
    if model not in available:
        raise ModelNotAvailableError(f"Model '{model}' not present in LM Studio. Available keys: {sorted(available)}")
    load_request = ModelLoadRequest(model=model, context_length=context_length, echo_load_config=True)
    raw_load = http_post_json(f"{lm_url}/api/v1/models/load", load_request, token, logger)
    try:
        load_response = ModelLoadResponse.model_validate_json(raw_load)
    except ValueError as exc:
        raise LMStudioError(f"POST /api/v1/models/load returned invalid JSON: {exc}") from exc
    load_seconds = load_response.load_time_seconds if load_response.load_time_seconds is not None else 0.0
    logger.info("lmstudio.loaded model=%s instance_id=%s load_seconds=%.2f", model, load_response.instance_id, load_seconds)


def chat_complete(lm_url: str, token: str, model: str, system_prompt: str, user_input: str, context_length: int, logger: logging.Logger) -> tuple[str, ChatStats]:
    """Send a non-streaming chat request; return (assembled message text, stats)."""
    request = ChatRequest(model=model, input=user_input, system_prompt=system_prompt, context_length=context_length, max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS)
    raw = http_post_json(f"{lm_url}/api/v1/chat", request, token, logger)
    try:
        response = ChatResponse.model_validate_json(raw)
    except ValueError as exc:
        snippet = raw[:500].decode("utf-8", errors="replace")
        raise LMStudioError(f"POST /api/v1/chat returned invalid JSON: {exc} body_snippet={snippet!r}") from exc
    text_parts = [item.content for item in response.output if item.type == "message" and item.content]
    text = "\n".join(text_parts).strip()
    if not text:
        raise LMStudioError(f"LM Studio returned no message content. Raw output items: {[item.model_dump() for item in response.output]}")
    stats = response.stats or ChatStats()
    return text, stats


def is_text_file(path: Path) -> bool:
    """Heuristic: read the first 4 KiB and reject if it contains NUL bytes."""
    try:
        with path.open("rb") as handle:
            chunk = handle.read(4096)
    except OSError:
        return False
    if not chunk:
        return True
    return b"\x00" not in chunk


def read_text_truncated(path: Path, max_bytes: int) -> tuple[str, bool]:
    """Read up to ``max_bytes`` of text. Return (content, truncated)."""
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
    """Return True if a file basename is on any skip list."""
    if name in WALK_IGNORE_FILE_NAMES:
        return True
    if name.endswith(WALK_IGNORE_FILE_SUFFIXES):
        return True
    if name == OVERVIEW_FILENAME:
        return True
    return False


def directory_should_be_skipped(name: str) -> bool:
    """Return True if a directory basename is on the skip list."""
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
    """Sorted list of non-skipped immediate subdirectories of ``directory``."""
    subs: list[Path] = []
    try:
        for entry in directory.iterdir():
            if entry.is_dir() and not directory_should_be_skipped(entry.name):
                subs.append(entry)
    except OSError:
        return []
    subs.sort(key=lambda p: p.name.lower())
    return subs


def run_tree(directory: Path, depth: int, logger: logging.Logger) -> str:
    """Run ``tree`` with the standardized ignore set; return stdout text."""
    pattern = "|".join(TREE_IGNORE_PATTERNS)
    cmd = ["tree", "-a", "-F", "--noreport", "-L", str(depth), "-I", pattern, str(directory)]
    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
    except FileNotFoundError as exc:
        logger.warning("tree.missing path=%s error=%s", directory, exc)
        return f"[tree binary missing: {exc}]"
    except subprocess.TimeoutExpired as exc:
        logger.warning("tree.timeout path=%s error=%s", directory, exc)
        return f"[tree timed out: {exc}]"
    except subprocess.CalledProcessError as exc:
        logger.warning("tree.failed path=%s rc=%d stderr=%s", directory, exc.returncode, (exc.stderr or "").strip())
        return exc.stdout.strip() if exc.stdout else f"[tree failed rc={exc.returncode}]"
    return completed.stdout.strip() or "[empty]"


def gather_directory_record(directory: Path, project_root: Path) -> DirectoryRecord:
    """Collect immediate files/subdirs and detect whether children have overviews."""
    files = tuple(list_immediate_files(directory))
    subdirs = tuple(list_immediate_subdirs(directory))
    has_overviews = any((sub / OVERVIEW_FILENAME).exists() for sub in subdirs)
    if directory == project_root:
        relative = "."
    else:
        relative = str(directory.relative_to(project_root))
    return DirectoryRecord(path=directory, relative=relative, files=files, subdirs=subdirs, has_child_overviews=has_overviews)


def build_file_blocks(files: Iterable[Path]) -> tuple[list[str], int]:
    """Render each file as a fenced markdown block; honour size caps."""
    blocks: list[str] = []
    used = 0
    count = 0
    for file_path in files:
        if count >= MAX_FILES_PER_DIR:
            blocks.append(f"_(additional files in this directory were not included; cap of {MAX_FILES_PER_DIR} files reached.)_\n")
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
            blocks.append(f"_(remaining files truncated; aggregate input cap of {MAX_TOTAL_INPUT_CHARS} chars reached.)_\n")
            break
        suffix = file_path.suffix.lstrip(".") or "txt"
        marker = " [truncated]" if truncated else ""
        blocks.append(f"#### `{file_path.name}`{marker}\n\n```{suffix}\n{content}\n```\n")
    return blocks, used


def build_child_blocks(subdirs: Iterable[Path], used_so_far: int) -> list[str]:
    """Render each child overview file as a markdown block; honour size caps."""
    blocks: list[str] = []
    used = used_so_far
    count = 0
    for sub in subdirs:
        overview = sub / OVERVIEW_FILENAME
        if not overview.exists():
            continue
        if count >= MAX_CHILD_OVERVIEWS:
            blocks.append(f"_(additional child overviews not included; cap of {MAX_CHILD_OVERVIEWS} reached.)_\n")
            break
        count += 1
        content, _ = read_text_truncated(overview, MAX_CHILD_OVERVIEW_BYTES)
        used += len(content)
        if used > MAX_TOTAL_INPUT_CHARS:
            blocks.append("_(remaining child overviews truncated; aggregate cap reached.)_\n")
            break
        blocks.append(f"#### `{sub.name}/_DIRECTORY_OVERVIEW.md`\n\n{content}\n")
    return blocks


def build_user_prompt(record: DirectoryRecord, project_root: Path, tree_text: str, file_blocks: list[str], child_blocks: list[str], template: str) -> str:
    """Assemble the full user prompt for a single directory."""
    header = (
        f"You are analysing the directory `{record.relative}` of the project rooted at `{project_root.name}`.\n\n"
        f"Produce a `_DIRECTORY_OVERVIEW.md` for this directory, using EXACTLY the section structure below. "
        f"Use GitHub-flavoured Markdown. Do not add a top-level `# Title` heading - the wrapper writes the title "
        f"and provenance metadata. Begin your output with the first `## ` heading from the template.\n\n"
        f"### Required section structure\n\n{template}\n"
    )
    parts: list[str] = [header, "### Tree of this directory\n\n```\n" + tree_text + "\n```\n"]
    if file_blocks:
        parts.append("### Files in this directory\n")
        parts.extend(file_blocks)
    else:
        parts.append("### Files in this directory\n\n(none)\n")
    if child_blocks:
        parts.append("### Child directory overviews\n")
        parts.extend(child_blocks)
    else:
        parts.append("### Child directory overviews\n\n(none)\n")
    parts.append("Now produce the overview. Output Markdown only - no preamble, no trailing commentary, no code fence around the whole document.")
    return "\n".join(parts)


def compute_source_hash(record: DirectoryRecord) -> str:
    """Hash filenames + sizes + mtimes of inputs for idempotency stamping."""
    hasher = hashlib.sha256()
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
        hasher.update(b"\x01")
    for sub in record.subdirs:
        overview = sub / OVERVIEW_FILENAME
        if not overview.exists():
            continue
        try:
            stat = overview.stat()
        except OSError:
            continue
        hasher.update(sub.name.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(str(stat.st_size).encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(str(int(stat.st_mtime)).encode("utf-8"))
        hasher.update(b"\x02")
    return hasher.hexdigest()


def existing_overview_hash(overview_path: Path) -> str | None:
    """Read the recorded source-sha256 from an existing overview, if present."""
    if not overview_path.exists():
        return None
    try:
        with overview_path.open("r", encoding="utf-8", errors="replace") as handle:
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


def render_overview(record: DirectoryRecord, project_root: Path, body: str, model: str, source_hash: str, stats: ChatStats) -> str:
    """Wrap the model body with deterministic title, provenance, and hash header."""
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    title_path = record.relative if record.relative != "." else project_root.name
    stat_line = f"input_tokens={stats.input_tokens} output_tokens={stats.total_output_tokens} tokens_per_second={stats.tokens_per_second}"
    header = (
        f"# Directory Overview: `{title_path}`\n\n"
        f"{GENERATION_MARKER}\n"
        f"<!-- generated_at={timestamp} -->\n"
        f"<!-- model={model} -->\n"
        f"<!-- {stat_line} -->\n"
        f"{SOURCE_HASH_PREFIX}{source_hash} -->\n\n"
    )
    return header + body.strip() + "\n"


def write_atomic(path: Path, content: str) -> None:
    """Write to a sibling tmp file, then ``os.replace`` for atomic update."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(tmp, path)


def process_directory(directory: Path, project_root: Path, lm_url: str, token: str, model: str, context_length: int, force: bool, logger: logging.Logger) -> str:
    """Generate a single directory's overview file. Return outcome string."""
    record = gather_directory_record(directory, project_root)
    overview_path = directory / OVERVIEW_FILENAME
    source_hash = compute_source_hash(record)
    if not force:
        prior = existing_overview_hash(overview_path)
        if prior == source_hash:
            logger.info("skip relative=%s reason=hash_match", record.relative)
            return "skipped"
    is_inner = record.has_child_overviews
    template = INNER_TEMPLATE if is_inner else LEAF_TEMPLATE
    depth = TREE_DEPTH_INNER if is_inner else TREE_DEPTH_LEAF
    tree_text = run_tree(directory, depth, logger)
    file_blocks, used = build_file_blocks(record.files)
    child_blocks = build_child_blocks(record.subdirs, used) if is_inner else []
    prompt = build_user_prompt(record=record, project_root=project_root, tree_text=tree_text, file_blocks=file_blocks, child_blocks=child_blocks, template=template)
    kind = "inner" if is_inner else "leaf"
    logger.info("analysing relative=%s kind=%s files=%d child_overviews=%d prompt_chars=%d", record.relative, kind, len(record.files), len(child_blocks), len(prompt))
    started = time.monotonic()
    body, stats = chat_complete(lm_url=lm_url, token=token, model=model, system_prompt=SYSTEM_PROMPT, user_input=prompt, context_length=context_length, logger=logger)
    elapsed = time.monotonic() - started
    logger.info("completed relative=%s elapsed=%.1fs input_tokens=%s output_tokens=%s tps=%s", record.relative, elapsed, stats.input_tokens, stats.total_output_tokens, stats.tokens_per_second)
    rendered = render_overview(record=record, project_root=project_root, body=body, model=model, source_hash=source_hash, stats=stats)
    write_atomic(overview_path, rendered)
    return "written"


def collect_directories(project_root: Path) -> list[Path]:
    """Return every directory under ``project_root`` (inclusive), bottom-up."""
    ordered: list[Path] = []
    for current, dirs, _files in os.walk(project_root, topdown=True):
        dirs[:] = [d for d in dirs if not directory_should_be_skipped(d)]
        ordered.append(Path(current))
    ordered.sort(key=lambda p: (-len(p.parts), str(p).lower()))
    return ordered


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse engine CLI arguments."""
    parser = argparse.ArgumentParser(description="project_analyzer engine")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--lm-url", default=DEFAULT_LM_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--context-length", type=int, default=DEFAULT_CONTEXT_LENGTH)
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="Regenerate even when source hash matches.")
    return parser.parse_args(argv)


def main() -> int:
    """Entry point. Returns process exit code."""
    args = parse_args(sys.argv[1:])
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        sys.stderr.write(f"ERROR: not a directory: {project_root}\n")
        return 2
    logger = configure_logging(args.log_file)
    token = os.environ.get("LM_API_TOKEN", "")
    logger.info("=" * 72)
    logger.info("project_analyzer.start project=%s model=%s log=%s", project_root, args.model, args.log_file)
    try:
        ensure_lm_studio_ready(args.lm_url, token, args.model, args.context_length, logger)
    except LMStudioError as exc:
        logger.exception("lmstudio.readiness_failed error=%s", exc)
        return 3
    except ModelNotAvailableError as exc:
        logger.exception("lmstudio.model_unavailable error=%s", exc)
        return 3
    directories = collect_directories(project_root)
    logger.info("walk.discovered count=%d", len(directories))
    written = 0
    skipped = 0
    failed = 0
    for index, directory in enumerate(directories, start=1):
        if directory == project_root:
            relative = "."
        else:
            relative = str(directory.relative_to(project_root))
        logger.info("progress index=%d/%d path=%s", index, len(directories), relative)
        try:
            outcome = process_directory(
                directory=directory,
                project_root=project_root,
                lm_url=args.lm_url,
                token=token,
                model=args.model,
                context_length=args.context_length,
                force=args.force,
                logger=logger
            )
        except (LMStudioError, AnalyzerError, OSError) as exc:
            failed += 1
            logger.exception("directory.failed path=%s error=%s", relative, exc)
            continue
        if outcome == "written":
            written += 1
        elif outcome == "skipped":
            skipped += 1
    logger.info("project_analyzer.done total=%d written=%d skipped=%d failed=%d", len(directories), written, skipped, failed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
