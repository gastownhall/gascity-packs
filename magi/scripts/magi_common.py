"""Foundation module for the magi pack.

Provides shared constants, filesystem layout helpers, state management,
secret redaction, bd subprocess wrappers, policy loading, and orphan
reconciliation. Every magi script imports from this module and from
nothing else first-party.

Std-lib only. No PyYAML. No Pydantic. Subprocess to bd is always bounded
by an explicit timeout; reads degrade gracefully when bd is missing.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

BD_DEFAULT_TIMEOUT_SECONDS: int = 10
BD_CLOSE_TIMEOUT_SECONDS: int = 20
BD_PUSH_TIMEOUT_SECONDS: int = 60
IDEMPOTENT_WINDOW_SECONDS: int = 300
ORPHAN_THRESHOLD_SECONDS: int = 3600
SHAKEDOWN_INTERVAL_SECONDS: int = 3600
SHAKEDOWN_TRIGGER_FILENAME: str = "shakedown_trigger"
_DOCTOR_TUNABLE_ENV_KEYS: tuple[str, ...] = (
    "GC_CITY_PATH",
    "GC_CITY_ROOT",
    "GC_PACK_STATE_DIR",
    "MAGI_UTILITIES_SOURCE",
    "LM_STUDIO_URL",
    "LM_STUDIO_HOST",
    "LM_STUDIO_PORT",
    "INSTALL_REMOTE_MCP",
)

PACK_NAME: str = "magi"
PACK_LABEL: str = "pack:magi"
STATE_SCHEMA_VERSION: int = 4

# ---------------------------------------------------------------------------
# Substitution / install constants (single source of truth per plan v3 §0.2)
# ---------------------------------------------------------------------------

# Canonical pack-source placeholder. Phase D pack-source rewrites produce
# this literal token; the Phase F deployer substitutes it to the resolved
# deploy_home at install time. The 12th shakedown check uses it as the
# positive-control grep target.
PACK_DIR_PLACEHOLDER: str = "${MAGI_PACK_DIR}"

# File-extension allowlist for placeholder substitution. Files outside
# this set are rsynced byte-exact and never sed-substituted. The set is
# consumed by Phase D pack-source rewrites and the Phase F deployer
# stage-walk; both surfaces share the same allowlist by design.
SUBSTITUTABLE_EXTENSIONS: frozenset[str] = frozenset({
    ".sh",
    ".py",
    ".json",
    ".toml",
    ".md",
    ".plist",
    ".xml",
    ".gsl",
    ".conf",
    ".yaml",
    ".yml",
})

# Files whose deployed mode is 0600. The Phase F deployer applies the
# mode to the staging copy BEFORE the atomic rename so the deployed
# inode is never readable at a wider mode. Paths are relative to the
# deploy_home root (or the staging root, which is renamed onto
# deploy_home atomically).
SECRET_BEARING_FILES: frozenset[str] = frozenset({
    ".mcp.json",
    "settings.json",
    "enforcement/env",
})

# Deployed-runtime path prefixes that legitimately stay as
# `~/.claude/<state>/` under the deploy_home root. The Phase D rewrite
# preserves these paths in pack source; the 12th-check allowlist
# consults this constant. Leading slash is the marker that the path is
# absolute relative to the deploy_home root.
RUNTIME_STATE_PATHS: tuple[str, ...] = (
    "/.claude/projects/",
    "/.claude/memory/",
    "/.claude/_logs/",
    "/.claude/archived/",
    "/.claude/backups/",
    "/.claude/.beads/",
)

# Sibling-runtime install destinations the deployer legitimately
# references (codex, gemini, openai, lm-studio-magi). The 12th-check
# exempts pack-source files that reference these paths only as install
# destinations.
CROSS_RUNTIME_EXEMPTIONS: tuple[str, ...] = (
    "/.claude",
    "/.codex",
    "/.gemini",
    "/.openai",
    "/.lm-studio-magi",
    "/.config/lm-studio-magi",
)

# Targets that receive `.utilities/` at deploy time and trigger the
# post-deploy setup_utilities.sh invocation. Renamed from
# _TARGETS_WITH_UTILITIES per plan v3 §7.4 to clarify the semantic:
# membership means "this target receives .utilities/ at deploy time."
_UTILITIES_AWARE_TARGETS: frozenset[str] = frozenset({"claude", "codex"})

# Every `__PLACEHOLDER__` the Phase F deployer substitutes at install
# time. Order matches the §0.1 canonical placeholder table. The
# deployer iterates this tuple once; no duplicate enumeration in
# magi_install.py.
INSTALL_PLACEHOLDERS: tuple[str, ...] = (
    "__USER_HOME__",
    "__USER_NAME__",
    "__CLAUDE_HOME__",
    "__LSP_PASS__",
    "__LSP_USER__",
    "__LSP_IP__",
    "__LSP_REMOTE_HOME__",
    "__BRAVE_API_KEY__",
    "__GITHUB_PERSONAL_ACCESS_TOKEN__",
    "__MY_GITEA_API_TOKEN__",
    "__MY_GITEA_HOST__",
    "__MY_GITEA_PORT__",
    "__LM_STUDIO_HOST__",
    "__LM_STUDIO_PORT__",
    "__LM_STUDIO_URL__",
)

# Patterns whose env-var or dict-key name signals secret content. Matched
# case-insensitively against the full key. Single source of truth for
# every redaction site (logs, state.json, bd write bodies, fingerprint
# inputs).
SECRET_KEY_PATTERNS: tuple[str, ...] = (
    "PASSWORD",
    "PASSWD",
    "PASS",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "APIKEY",
    "BEARER",
    "PRIVATE_KEY",
    "PRIVATEKEY",
    "CREDENTIAL",
    "CREDENTIALS",
    "AUTH",
    "ACCESS_KEY",
    "ACCESSKEY",
    "BRAVE_API_KEY",
    "GITHUB_PERSONAL_ACCESS_TOKEN",
    "MY_GITEA_API_TOKEN",
    "OPENAI_API_KEY",
    "LSP_PASS",
    "LM_API_TOKEN",
    "SLACK_BOT_TOKEN"
)

# Inline secret pattern for free-form text (logs, bd bodies). Catches
# "KEY=value" / "KEY: value" / "KEY value" pairings where KEY matches a
# secret key pattern.
_SECRET_INLINE_REGEX: re.Pattern[str] = re.compile(
    r"((?i:" + "|".join(SECRET_KEY_PATTERNS) + r"))\s*[:=]\s*([^\s,;]+)"
)
_ENV_ASSIGNMENT_REGEX: re.Pattern[str] = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_ENV_EXPANSION_REGEX: re.Pattern[str] = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_PACK_ENV_LOADED: bool = False

# Canonical bd label schema. bd_label() raises ValueError on any key not
# in this dict or any value not in the declared domain. Adding a new label
# key requires an edit here AND a test update.
MAGI_LABEL_SCHEMA: dict[str, tuple[str, ...]] = {
    "pack": ("magi",),
    "verb": (
        "install",
        "uninstall",
        "analyze",
        "improve",
        "status",
        "doctor",
        "molecule",
        "bootstrap-project",
        "remember",
        "recall",
        "ready",
        "formulas"
    ),
    "target": ("claude", "codex", "gemini", "openai", "project", "all"),
    "outcome": ("0", "1", "2", "interrupted", "orphaned", "partial"),
    "role": ("root", "child", "hook-trigger", "uninstall-closure")
}

# Install-target registry. Keys are target names exposed via --target.
# `dir` is the relative directory under the pack root; `script` is the
# deployer to invoke; `env` enumerates the env vars the orchestrator
# passes through to the deployer; `default_home` is the deployment
# target when no --home is supplied.
TARGET_REGISTRY: dict[str, dict[str, object]] = {
    "claude": {
        "dir": "claude",
        "script": "deploy_harness.sh",
        "env": (
            "INSTALL_GLOBAL_CLAUDE_MD",
            "INSTALL_REMOTE_MCP",
            "INSTALL_LAUNCHD",
            "INSTALL_LM_STUDIO",
            "INSTALL_LSP_BINARIES",
            "LSP_IP",
            "LSP_USER",
            "LSP_PASS",
            "LSP_REMOTE_HOME",
            "LM_STUDIO_HOST",
            "LM_STUDIO_PORT",
            "LM_STUDIO_URL",
            "BRAVE_API_KEY",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            "MY_GITEA_API_TOKEN",
            "MY_GITEA_HOST",
            "MY_GITEA_PORT"
        ),
        "default_home": "~/.claude"
    },
    "codex": {
        "dir": "codex",
        "script": "deploy_harness.sh",
        "env": (
            "CODEX_HOME",
            "INSTALL_CODEX_HOOKS",
            "INSTALL_EXEC_POLICY",
            "INSTALL_LM_STUDIO",
            "LM_STUDIO_HOST",
            "LM_STUDIO_PORT",
            "LM_STUDIO_MODEL",
            "LM_STUDIO_CONNECT_TIMEOUT",
            "LM_STUDIO_MAX_TIME",
            "CODEX_MAX_QUALITY_ATTEMPTS",
            "CODEX_TURN_CONTENT_LIMIT"
        ),
        "default_home": "~/.codex"
    },
    "gemini": {
        "dir": "gemini",
        "script": "deploy_gemini.sh",
        "env": (
            "GEMINI_HOME",
            "INSTALL_GEMINI_HOOKS",
            "INSTALL_LM_STUDIO",
            "LM_STUDIO_HOST",
            "LM_STUDIO_PORT",
            "LM_STUDIO_MODEL",
            "GEMINI_TURN_CONTENT_LIMIT"
        ),
        "default_home": "~/.gemini"
    },
    "openai": {
        "dir": "openai",
        "script": "deploy_openai.sh",
        "env": (
            "OPENAI_TARGET_HOME",
            "LM_STUDIO_HOST",
            "LM_STUDIO_PORT",
            "LM_STUDIO_MODEL",
            "LM_STUDIO_CONTEXT",
            "LM_STUDIO_AUTOLOAD_MODELS",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL"
        ),
        "default_home": "~/.config/lm-studio-magi"
    }
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class CLIError(RuntimeError):
    """Raised by a verb when CLI parsing or precondition fails."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------

def pack_root() -> Path:
    """Return the magi pack root directory (parent of `scripts/`)."""
    return Path(__file__).resolve().parent.parent


def city_root() -> Path:
    """Return the Gas City root from GC_CITY_PATH or GC_CITY_ROOT.

    Raises CLIError when neither is set.
    """
    raw = os.environ.get("GC_CITY_PATH") or os.environ.get("GC_CITY_ROOT")
    if not raw: raise CLIError("Missing GC_CITY_PATH / GC_CITY_ROOT in environment.", exit_code=2)
    return Path(raw).expanduser().resolve()


def runtime_dir() -> Path:
    """Return the per-city magi runtime directory under .gc/runtime/packs/magi."""
    override = os.environ.get("GC_PACK_STATE_DIR")
    if override: return Path(override).expanduser().resolve()
    return city_root() / ".gc" / "runtime" / "packs" / PACK_NAME


def state_path() -> Path:
    """Return the path to state.json under the city runtime dir."""
    return runtime_dir() / "state.json"


def inflight_path() -> Path:
    """Return the inflight sentinel directory under the city runtime dir."""
    return runtime_dir() / "inflight"


def logs_dir() -> Path:
    """Return the per-verb logs directory under the city runtime dir."""
    return runtime_dir() / "logs"


def log_path(verb: str, target: str | None = None) -> Path:
    """Return a unique log path for a verb invocation."""
    stamp = now_utc_iso().replace(":", "").replace("-", "")
    suffix = f"-{target}" if target else ""
    return logs_dir() / f"{verb}{suffix}-{stamp}.log"


# ---------------------------------------------------------------------------
# Pack-local environment
# ---------------------------------------------------------------------------

def pack_env_path() -> Path:
    """Return the pack-local dotenv file path."""
    return pack_root() / ".env"


def _strip_env_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    if " #" in stripped:
        return stripped.split(" #", 1)[0].rstrip()
    return stripped


def _expand_env_value(value: str, merged_env: dict[str, str]) -> str:
    def replace_var(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        return merged_env.get(name, "")
    return _ENV_EXPANSION_REGEX.sub(replace_var, value)


def _parse_pack_env_line(raw: str) -> tuple[str, str] | None:
    line = raw.strip()
    if not line or line.startswith("#"): return None
    match = _ENV_ASSIGNMENT_REGEX.match(line)
    if match is None: return None
    return match.group(1), _strip_env_quotes(match.group(2))


def load_pack_env() -> dict[str, str]:
    """Load pack-root .env values into os.environ without overriding callers."""
    global _PACK_ENV_LOADED
    if _PACK_ENV_LOADED: return {}
    _PACK_ENV_LOADED = True
    env_path = pack_env_path()
    if not env_path.is_file(): return {}
    loaded: dict[str, str] = {}
    merged_env: dict[str, str] = dict(os.environ)
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_pack_env_line(raw)
        if parsed is None: continue
        name, value = parsed
        if name in os.environ: continue
        if value == "": continue
        expanded = _expand_env_value(value, merged_env)
        os.environ[name] = expanded
        merged_env[name] = expanded
        loaded[name] = expanded
    return loaded


def _ensure_runtime_layout() -> None:
    """Create the runtime, logs, and inflight directories if absent."""
    runtime_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    inflight_path().mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Time and identity
# ---------------------------------------------------------------------------

def now_utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (seconds)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

def _is_secret_key(key: str) -> bool:
    upper = key.upper()
    return any(pattern in upper for pattern in SECRET_KEY_PATTERNS)


def _redact_structure(payload: object) -> object:
    if isinstance(payload, dict):
        out: dict[str, object] = {}
        for k, v in payload.items():
            key_str = str(k)
            if _is_secret_key(key_str):
                out[key_str] = "<redacted>" if v is not None else None
            else:
                out[key_str] = _redact_structure(v)
        return out
    if isinstance(payload, list): return [_redact_structure(item) for item in payload]
    if isinstance(payload, tuple): return tuple(_redact_structure(item) for item in payload)
    if isinstance(payload, str): return _SECRET_INLINE_REGEX.sub(r"\1=<redacted>", payload)
    return payload


def redact_secrets(text: object) -> object:
    """Redact secrets from any string, dict, list, or tuple structure.

    Strings are scanned with the inline regex. Dicts/lists/tuples are
    walked and per-key matched against SECRET_KEY_PATTERNS. Other types
    are returned unchanged.
    """
    return _redact_structure(text)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=64)
def _verb_logger(verb: str) -> logging.Logger:
    logger = logging.getLogger(f"magi.{verb}")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    return logger


def attach_file_log(verb: str, log_file: Path) -> None:
    """Attach a file handler for the verb's log file."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(log_file), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger = _verb_logger(verb)
    logger.addHandler(handler)


def log_event(verb: str, message: str, level: int = logging.INFO) -> None:
    """Log an event for a verb. The message is redacted before emission."""
    redacted = redact_secrets(message)
    _verb_logger(verb).log(level, "%s", redacted)


# ---------------------------------------------------------------------------
# State and run records
# ---------------------------------------------------------------------------

def _default_state() -> dict[str, object]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "pack_version": "0.1.0",
        "bd_available": False,
        "installs": {
            "claude": _default_install_entry(),
            "codex": _default_install_entry(),
            "gemini": _default_install_entry(),
            "openai": _default_install_entry()
        },
        "analyze": {},
        "improve": {},
        "doctor": {"shakedown": default_shakedown_entry()},
        "molecule": {"bootstrap_root_id": None, "child_ids": []},
        "bootstrap_project": {
            "last_project_path": None,
            "last_run_timestamp": None,
            "last_run_rc": None,
            "bead_id": None
        },
        "failures": [],
        "last_uninstall_timestamp": None,
        "magi_utilities_source": None
    }


def _default_install_entry() -> dict[str, object]:
    return {
        "installed": False,
        "target": None,
        "last_run_timestamp": None,
        "last_run_rc": None,
        "last_log": None,
        "bead_id": None,
        "feature_flags": {},
        "utilities_linked": False,
        "flag_fingerprint": None
    }


def default_shakedown_entry() -> dict[str, object]:
    """Return the default shakedown sub-state structure."""
    return {
        "last_run_at": None,
        "last_run_rc": None,
        "script_mtime_ns": None,
        "script_sha256": None,
        "tunable_fingerprint": None,
        "triggers_fired": [],
        "last_findings": []
    }


def read_state() -> dict[str, object]:
    """Return the current state.json contents, or a default skeleton if absent."""
    path = state_path()
    if not path.exists(): return _default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_state()
    if not isinstance(raw, dict): return _default_state()
    return raw


def write_state(state: dict[str, object]) -> None:
    """Persist state to disk after redacting any secret-keyed values."""
    _ensure_runtime_layout()
    redacted = _redact_structure(state)
    path = state_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(redacted, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def record_run(section: str, key: str, payload: dict[str, object]) -> None:
    """Record a structured run summary under state[section][key]."""
    state = read_state()
    bucket = state.setdefault(section, {})
    if not isinstance(bucket, dict): bucket = {}
    bucket[key] = payload
    state[section] = bucket
    write_state(state)


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

def flag_fingerprint(argv: list[str], env_keys: list[str]) -> str:
    """Return a SHA-256 hex digest over argv + sorted env keys (redacted).

    Secrets are redacted *before* hashing so the hash input never holds
    a secret in clear form.
    """
    load_pack_env()
    env = os.environ
    parts: list[str] = []
    for token in argv: parts.append(f"argv={token}")
    for name in sorted(set(env_keys)):
        raw = env.get(name)
        if raw is None: continue
        value = "<redacted>" if _is_secret_key(name) else raw
        parts.append(f"env:{name}={value}")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest


def shakedown_tunable_fingerprint() -> str:
    """Return a SHA-256 hex digest over the doctor-tunable env values.

    Secrets are redacted before hashing. Unset keys are skipped.
    """
    load_pack_env()
    parts: list[str] = []
    for name in sorted(_DOCTOR_TUNABLE_ENV_KEYS):
        raw = os.environ.get(name)
        if raw is None: continue
        value = "<redacted>" if _is_secret_key(name) else raw
        parts.append(f"{name}={value}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Policy loading (YAML frontmatter, std-lib only)
# ---------------------------------------------------------------------------

_FRONTMATTER_DELIM: str = "---"


def _parse_frontmatter_scalar(raw: str) -> object:
    value = raw.strip()
    if value == "": return ""
    if value.lower() in {"true", "yes", "on"}: return True
    if value.lower() in {"false", "no", "off"}: return False
    if value.lower() in {"null", "~"}: return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner: return []
        items = [item.strip().strip("'\"") for item in inner.split(",")]
        return items
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _parse_frontmatter_block(block: str) -> dict[str, object]:
    """Parse a minimal YAML-like block: scalars, simple lists, one level of nesting."""
    result: dict[str, object] = {}
    current_key: str | None = None
    nested: dict[str, object] = {}
    list_buffer: list[object] = []
    list_key: str | None = None
    lines = block.splitlines()
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"): continue
        if line.startswith("  ") and current_key is not None:
            stripped = line.strip()
            if stripped.startswith("- "):
                if list_key != current_key:
                    list_key = current_key
                    list_buffer = []
                list_buffer.append(_parse_frontmatter_scalar(stripped[2:]))
                result[current_key] = list(list_buffer)
                continue
            if ":" in stripped:
                sub_key, sub_val = stripped.split(":", 1)
                nested.setdefault(current_key, {})
                bucket = result.setdefault(current_key, {})
                if isinstance(bucket, dict):
                    bucket[sub_key.strip()] = _parse_frontmatter_scalar(sub_val)
                continue
        if ":" in line:
            key, val = line.split(":", 1)
            current_key = key.strip()
            list_key = None
            list_buffer = []
            value_part = val.strip()
            if value_part == "":
                result.setdefault(current_key, {})
            else:
                result[current_key] = _parse_frontmatter_scalar(value_part)
    return result


@functools.lru_cache(maxsize=32)
def load_policy(topic: str) -> dict[str, object]:
    """Load the YAML frontmatter from guidelines/markdown_library/magi/<topic>.md.

    Returns an empty dict when the file is missing or has no frontmatter.
    """
    path = pack_root() / "guidelines" / "markdown_library" / PACK_NAME / f"{topic}.md"
    if not path.exists(): return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith(_FRONTMATTER_DELIM): return {}
    rest = text[len(_FRONTMATTER_DELIM):]
    end_idx = rest.find(f"\n{_FRONTMATTER_DELIM}")
    if end_idx < 0: return {}
    block = rest[:end_idx].lstrip("\n")
    return _parse_frontmatter_block(block)


# ---------------------------------------------------------------------------
# .utilities/ portability
# ---------------------------------------------------------------------------

def _candidate_utilities_dir(candidate: Path) -> Path | None:
    """Return candidate when it is a directory whose setup_utilities.sh is executable, else None."""
    if not candidate.is_dir(): return None
    setup = candidate / "setup_utilities.sh"
    if not setup.is_file(): return None
    if not os.access(str(setup), os.X_OK): return None
    return candidate


def magi_utilities_source(verb: str = "utilities") -> Path | None:
    """Return the resolved .utilities source directory.

    Precedence (per plan v3 §8.1):
    1. ``MAGI_UTILITIES_SOURCE`` environment variable (when set and the
       resolved path passes the directory + executable setup script
       probes).
    2. ``pack_root() / ".utilities"`` — pack-internal canonical source.
    3. ``Path.home() / ".scripts" / ".utilities"`` — legacy fallback for
       installs that still ship the user-shipped per-machine utilities
       tree outside the pack.
    4. ``None`` — no usable utilities source resolves.

    Every resolution attempt is recorded via ``log_event(verb, ...)``
    so the verb-log file contains the audit trail consumed by
    ``doctor/check-utilities.sh``. The function does not write to
    stdout.
    """
    load_pack_env()
    chain: list[str] = []
    chosen: Path | None = None

    env_raw = os.environ.get("MAGI_UTILITIES_SOURCE")
    if env_raw:
        env_candidate = Path(env_raw).expanduser().resolve()
        chain.append(f"env={env_candidate}")
        resolved = _candidate_utilities_dir(env_candidate)
        if resolved is not None: chosen = resolved
    else:
        chain.append("env=<unset>")

    if chosen is None:
        internal = pack_root() / ".utilities"
        chain.append(f"pack_internal={internal}")
        resolved = _candidate_utilities_dir(internal)
        if resolved is not None: chosen = resolved

    if chosen is None:
        legacy = Path.home() / ".scripts" / ".utilities"
        chain.append(f"legacy={legacy}")
        resolved = _candidate_utilities_dir(legacy)
        if resolved is not None: chosen = resolved

    chain_str = " -> ".join(chain)
    chosen_str = str(chosen) if chosen is not None else "<none>"
    log_event(
        verb,
        f"source_resolved chain={chain_str} chosen={chosen_str} final={chosen_str}"
    )
    return chosen


# ---------------------------------------------------------------------------
# bd availability + invocation
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=8)
def bd_available(path_signature: str = "") -> bool:
    """Return True when `bd` is on PATH.

    The `path_signature` parameter is the lru_cache key so tests that
    mutate PATH can use `bd_available_current()` for an up-to-date probe
    without explicitly clearing the cache.
    """
    del path_signature
    return shutil.which("bd") is not None


def bd_available_current() -> bool:
    """Probe bd availability against the current PATH."""
    return bd_available(os.environ.get("PATH", ""))


def _is_hook_reentrant() -> bool:
    return os.environ.get("MAGI_HOOK_REENTRANT") == "1"


def _is_bd_degraded_stderr(stderr: str) -> bool:
    """Return True when stderr indicates an expected bd-degraded condition.

    Three known degraded-state classes are treated as INFO instead of
    WARNING because they are operational facts (server not running,
    database not initialized, transient connection failure), not bugs.
    Markers:

    - ``Dolt server unreachable`` — auto-start disabled or server died.
    - ``failed to open database`` — Dolt store unreachable or corrupt.
    - ``no beads database found`` — bd binary present but never `bd init`-ed.
    """
    try:
        trimmed = stderr.strip()
        if not trimmed: return False
        markers = (
            "Dolt server unreachable",
            "failed to open database",
            "no beads database found",
        )
        if any(marker in stderr for marker in markers): return True
        try:
            payload = json.loads(trimmed)
        except json.JSONDecodeError:
            return False
        if not isinstance(payload, dict): return False
        error_text = payload.get("error", "")
        if not isinstance(error_text, str): return False
        return any(marker in error_text for marker in markers)
    except Exception:
        return False


def try_bd(
    args: list[str],
    timeout: int = BD_DEFAULT_TIMEOUT_SECONDS,
    verb: str = "bd"
) -> subprocess.CompletedProcess[str] | None:
    """Invoke `bd` with the given args. Returns None on missing-bd or timeout.

    Output is captured and decoded to text. The caller inspects
    completedprocess.returncode and stdout. Errors are logged but never
    raise out of this helper.
    """
    if not bd_available_current():
        log_event(verb, "bd_unavailable op=" + " ".join(args[:2]))
        return None
    try:
        result = subprocess.run(
            ["bd", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
    except subprocess.TimeoutExpired:
        log_event(verb, f"bd_timeout op={' '.join(args[:2])} seconds={timeout}", level=logging.WARNING)
        return None
    except FileNotFoundError:
        log_event(verb, "bd_missing_at_invoke", level=logging.WARNING)
        return None
    if result.returncode != 0:
        degraded = _is_bd_degraded_stderr(result.stderr)
        level = logging.INFO if degraded else logging.WARNING
        if degraded:
            message = f"bd_degraded op={' '.join(args[:2])} rc={result.returncode}"
        else:
            message = (
                f"bd_nonzero op={' '.join(args[:2])} rc={result.returncode} "
                f"stderr={result.stderr.strip()}"
            )
        log_event(verb, message, level=level)
    return result


def _label_args(labels: dict[str, str]) -> list[str]:
    out: list[str] = []
    for key, value in labels.items():
        _validate_label(key, value)
        out.extend(["--label", f"{key}:{redact_secrets(value)}"])
    return out


def _validate_label(key: str, value: str) -> None:
    domain = MAGI_LABEL_SCHEMA.get(key)
    if domain is None: raise ValueError(f"bd_label: unknown label key {key!r}")
    if value not in domain: raise ValueError(f"bd_label: value {value!r} not in domain for {key!r}: {domain!r}")


def bd_create(
    title: str,
    body: str,
    labels: dict[str, str],
    verb: str = "bd",
    timeout: int = BD_DEFAULT_TIMEOUT_SECONDS
) -> str | None:
    """Create a bd bead. Returns the bead id on success, None on degraded path."""
    if _is_hook_reentrant():
        log_event(verb, "bd_skipped_reentrant op=create")
        return None
    safe_title = str(redact_secrets(title))
    safe_body = str(redact_secrets(body))
    args = ["create", "--title", safe_title, "--body", safe_body, *_label_args(labels), "--json"]
    result = try_bd(args, timeout=timeout, verb=verb)
    if result is None or result.returncode != 0: return None
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        log_event(verb, "bd_create_unparseable_stdout", level=logging.WARNING)
        return None
    bead_id = payload.get("id") if isinstance(payload, dict) else None
    return str(bead_id) if bead_id else None


def bd_update(
    bead_id: str,
    body: str | None = None,
    labels: dict[str, str] | None = None,
    claim: bool = False,
    verb: str = "bd",
    timeout: int = BD_DEFAULT_TIMEOUT_SECONDS
) -> bool:
    """Update a bd bead (body, labels, or claim). Returns True on success."""
    if _is_hook_reentrant():
        log_event(verb, "bd_skipped_reentrant op=update")
        return False
    args: list[str] = ["update", bead_id]
    if body is not None: args.extend(["--body", str(redact_secrets(body))])
    if labels: args.extend(_label_args(labels))
    if claim: args.append("--claim")
    result = try_bd(args, timeout=timeout, verb=verb)
    return result is not None and result.returncode == 0


def bd_close(
    bead_id: str,
    outcome: str,
    labels: dict[str, str] | None = None,
    verb: str = "bd",
    timeout: int = BD_CLOSE_TIMEOUT_SECONDS
) -> bool:
    """Close a bd bead with an outcome label. Returns True on success."""
    if _is_hook_reentrant():
        log_event(verb, "bd_skipped_reentrant op=close")
        return False
    _validate_label("outcome", outcome)
    composite: dict[str, str] = {"outcome": outcome}
    if labels:
        for key, value in labels.items(): composite[key] = value
    add_label_args: list[str] = []
    for key, value in composite.items():
        _validate_label(key, value)
        add_label_args.extend(["--add-label", f"{key}:{redact_secrets(value)}"])
    update_result = try_bd(["update", bead_id, *add_label_args], timeout=timeout, verb=verb)
    if update_result is None or update_result.returncode != 0: return False
    result = try_bd(["close", bead_id], timeout=timeout, verb=verb)
    return result is not None and result.returncode == 0


def bd_remember(
    key: str,
    value: str,
    verb: str = "bd",
    timeout: int = BD_DEFAULT_TIMEOUT_SECONDS
) -> bool:
    """Persist a bd memory entry. Returns True on success."""
    if _is_hook_reentrant():
        log_event(verb, "bd_skipped_reentrant op=remember")
        return False
    safe_value = str(redact_secrets(value))
    args = ["remember", "--key", f"magi:{key}", safe_value]
    result = try_bd(args, timeout=timeout, verb=verb)
    return result is not None and result.returncode == 0


def bd_label(
    bead_id: str,
    key: str,
    value: str,
    verb: str = "bd",
    timeout: int = BD_DEFAULT_TIMEOUT_SECONDS
) -> bool:
    """Add a label to a bead. Raises ValueError on schema violation."""
    if _is_hook_reentrant():
        log_event(verb, "bd_skipped_reentrant op=label")
        return False
    _validate_label(key, value)
    safe_value = str(redact_secrets(value))
    args = ["label", bead_id, "--add", f"{key}:{safe_value}"]
    result = try_bd(args, timeout=timeout, verb=verb)
    return result is not None and result.returncode == 0


def bd_dep(
    parent_id: str,
    child_id: str,
    verb: str = "bd",
    timeout: int = BD_DEFAULT_TIMEOUT_SECONDS
) -> bool:
    """Create a parent->child dependency edge. Returns True on success."""
    if _is_hook_reentrant():
        log_event(verb, "bd_skipped_reentrant op=dep")
        return False
    args = ["dep", "add", parent_id, child_id]
    result = try_bd(args, timeout=timeout, verb=verb)
    return result is not None and result.returncode == 0


def bd_show(
    bead_id: str,
    verb: str = "bd",
    timeout: int = BD_DEFAULT_TIMEOUT_SECONDS
) -> dict[str, object] | None:
    """Read a single bead by id. Returns parsed JSON dict or None."""
    result = try_bd(["show", bead_id, "--json"], timeout=timeout, verb=verb)
    if result is None or result.returncode != 0: return None
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def bd_list_pack(
    status: str | None = None,
    extra_labels: list[str] | None = None,
    verb: str = "bd",
    timeout: int = BD_DEFAULT_TIMEOUT_SECONDS
) -> list[dict[str, object]]:
    """List bd beads tagged pack:magi. Returns [] on degraded paths."""
    args: list[str] = ["list", "--label", PACK_LABEL, "--json"]
    if status: args.extend(["--status", status])
    if extra_labels:
        for label in extra_labels: args.extend(["--label", label])
    result = try_bd(args, timeout=timeout, verb=verb)
    if result is None or result.returncode != 0: return []
    try:
        payload = json.loads(result.stdout.strip() or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list): return []
    return [item for item in payload if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# Inflight sentinels and orphan reconciliation
# ---------------------------------------------------------------------------

def write_inflight_sentinel(bead_id: str, verb: str, target: str | None = None) -> Path:
    """Record an in-flight bead so SIGKILL/OOM crashes can be reconciled later."""
    _ensure_runtime_layout()
    payload = {
        "bead_id": bead_id,
        "verb": verb,
        "target": target,
        "pid": os.getpid(),
        "started_at": now_utc_iso()
    }
    path = inflight_path() / f"{bead_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def clear_inflight_sentinel(bead_id: str) -> None:
    """Remove the sentinel for a closed bead. Idempotent."""
    path = inflight_path() / f"{bead_id}.json"
    try:
        path.unlink()
    except FileNotFoundError:
        return


_reconciled_in_process: bool = False


def reconcile_orphans(verb: str = "reconcile") -> int:
    """Close orphan beads recorded in inflight sentinels. Memoized per process.

    Returns the count of orphan beads reconciled. Bounded by bd timeouts.
    Safe to call when bd is unavailable; degrades to a no-op.
    """
    global _reconciled_in_process
    if _reconciled_in_process: return 0
    _reconciled_in_process = True
    sentinels = inflight_path()
    if not sentinels.is_dir(): return 0
    closed = 0
    for sentinel in sorted(sentinels.glob("*.json")):
        try:
            data = json.loads(sentinel.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            try:
                sentinel.unlink()
            except FileNotFoundError:
                pass
            continue
        bead_id = data.get("bead_id") if isinstance(data, dict) else None
        if not isinstance(bead_id, str) or not bead_id:
            try:
                sentinel.unlink()
            except FileNotFoundError:
                pass
            continue
        if bd_close(bead_id, outcome="orphaned", verb=verb):
            log_event(verb, f"reconciled_orphan bead={bead_id}")
        try:
            sentinel.unlink()
        except FileNotFoundError:
            pass
        closed += 1
    return closed
