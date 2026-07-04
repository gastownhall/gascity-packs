#!/usr/bin/env python3
"""Publish github-intake GitHub App identities to local JSON files.

Write-side mirror of ``file_identity_resolver.py``: the pack's identity
publish hook pipes the freshly captured app identity to this script on STDIN,
and it persists it to ``$GITHUB_INTAKE_IDENTITY_DIR/<identity>.json`` (0600) —
the exact file the resolver reads back. Together they give a portable,
dependency-free round-trip (create → publish to file → resolve from file);
a secret-store-backed publisher (Vault, a cloud secret manager, ...) is the
production variant of the same contract.

The identity name arrives as the only positional argument (symmetric with the
resolver invocation); ``GITHUB_INTAKE_APP_IDENTITY`` is the fallback for
manual use. The directory comes from ``GITHUB_INTAKE_IDENTITY_DIR`` (default
``config/github-intake/identities``), matching the resolver so both ends
agree.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any

SCHEMA_VERSION = "github-intake.github-app-identity.v1"
IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

# Fields the resolver expects; we persist whichever are present and merge over
# an existing file so operator-set values (permissions, repos, ...) survive a
# republish that only carries a subset (e.g. a later installation_id capture).
IDENTITY_FIELDS = (
    "app_id",
    "client_id",
    "client_secret",
    "webhook_secret",
    "slug",
    "html_url",
    "name",
    "installation_id",
    "owner",
    "private_key_pem",
    "permissions",
    "repos",
    "token_ttl_seconds",
    "ready",
)


def identity_dir() -> pathlib.Path:
    return pathlib.Path(
        os.environ.get("GITHUB_INTAKE_IDENTITY_DIR", "config/github-intake/identities")
    ).expanduser()


def validate_identity(identity: str) -> str:
    identity = identity.strip()
    if not IDENTITY_PATTERN.fullmatch(identity):
        raise ValueError("identity must match [A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
    return identity


def read_existing(path: pathlib.Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def is_ready(payload: dict[str, Any]) -> bool:
    return all(str(payload.get(key, "")).strip() for key in ("app_id", "private_key_pem", "webhook_secret"))


def atomic_write(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def publish(identity: str, incoming: dict[str, Any]) -> pathlib.Path:
    identity = validate_identity(identity)
    path = identity_dir() / f"{identity}.json"
    merged = read_existing(path)
    for key in IDENTITY_FIELDS:
        value = incoming.get(key)
        if value not in (None, ""):
            merged[key] = value
    merged["schema_version"] = SCHEMA_VERSION
    # ``ready`` is derived, not trusted from the caller, so a partial republish
    # can't falsely mark an incomplete identity ready.
    merged["ready"] = "true" if is_ready(merged) else "false"
    atomic_write(path, merged)
    return path


def main(argv: list[str]) -> int:
    identity = argv[0] if argv else os.environ.get("GITHUB_INTAKE_APP_IDENTITY", "").strip()
    if not identity:
        print(
            "github-intake identity publish failed: pass the identity as the only "
            "argument or set GITHUB_INTAKE_APP_IDENTITY",
            file=sys.stderr,
        )
        return 2
    try:
        incoming = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"github-intake identity publish failed: invalid identity JSON on stdin: {exc}", file=sys.stderr)
        return 1
    if not isinstance(incoming, dict):
        print("github-intake identity publish failed: identity payload must be a JSON object", file=sys.stderr)
        return 1
    try:
        path = publish(identity, incoming)
    except (OSError, ValueError) as exc:
        print(f"github-intake identity publish failed: {exc}", file=sys.stderr)
        return 1
    published = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps({"published": True, "path": str(path), "ready": published.get("ready") == "true"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
