"""Pin the executable that negative-authentication cases launch directly."""
import hashlib
import os
from pathlib import Path
import re

from live_assertions import AcceptanceFailure


def require_claude_session_id(binary, command):
    """Qualify the actual CLI capability instead of guessing from a version."""
    help_text = command(str(binary), "--help")
    if not re.search(r"(?m)^\s*--session-id\s+<uuid>(?:\s|$)", help_text):
        raise AcceptanceFailure("Claude acceptance requires documented --session-id <uuid> support for exact transcript identity")


def runtime_artifact(path, expected_version, command):
    candidate = Path(path)
    if not candidate.is_absolute():
        raise AcceptanceFailure("Raw runtime executable must be an absolute path")
    try:
        binary = candidate.resolve(strict=True)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise AcceptanceFailure("Raw runtime executable must be an executable regular file")
        before = hashlib.sha256(binary.read_bytes()).hexdigest()
        version = command(str(binary), "--version").strip()
        after = hashlib.sha256(binary.read_bytes()).hexdigest()
    except OSError as error:
        raise AcceptanceFailure("Raw runtime executable is unavailable") from error
    if version != expected_version:
        raise AcceptanceFailure("Raw runtime version differs from the artifact under test")
    if before != after:
        raise AcceptanceFailure("Raw runtime executable changed while verifying its identity")
    return {"path": str(binary), "version": version, "sha256": after}


def verified_runtime_artifact(runner):
    expected = runner.manifest.get("runtimeArtifact")
    if not isinstance(expected, dict) or set(expected) != {"path", "version", "sha256"}:
        raise AcceptanceFailure("Error fixtures require a pinned raw runtimeArtifact; prepare with --runtime-raw-bin")
    actual = runtime_artifact(expected["path"], runner.manifest["versions"][runner.runtime], runner.command)
    if actual != expected:
        raise AcceptanceFailure("Raw runtime executable differs from the prepared artifact")
    return actual
