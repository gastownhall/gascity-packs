"""Stub herdr-core releases for the install tests: an archive holding a
stub binary (never executed by these tests), its manifest, and a pin."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

from gc_runtime_herdr_core.herdrcore.pin import HcPin, parse_pin

RELEASES = "https://releases.example.invalid/core"
TARGET = "linux-x86_64"
STUB = b"#!/bin/sh\necho stub\n"


def archive(binary: bytes = STUB, *, name: str = "herdr-core", extra: Sequence[Tuple[str, bytes]] = (), link: bool = False) -> bytes:
    """A ``.tar.gz`` holding ``binary`` as ``name`` (a symlink instead with ``link``)."""
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        members = [(name, binary)] + list(extra)
        for member, data in members:
            info = tarfile.TarInfo(member)
            if link and member == name:
                info.type = tarfile.SYMTYPE
                info.linkname = "/bin/sh"
                tar.addfile(info)
                continue
            info.size = len(data)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pin_doc(version: str, digest: str, *, min_version: Optional[str] = None) -> Dict[str, object]:
    return {
        "version": version,
        "generation": 1,
        "min_version": min_version or version,
        "tested": [version],
        "releases": RELEASES,
        "binary": "herdr-core",
        "targets": {TARGET: {"asset": f"herdr-core-{TARGET}.tar.gz", "sha256": digest}},
    }


def make_pin(version: str, digest: str, **kwargs: str) -> HcPin:
    return parse_pin(json.dumps(pin_doc(version, digest, **kwargs)).encode())


def publish(directory: Path, version: str, data: bytes, *, manifest_sha: Optional[str] = None) -> None:
    """Put ``data`` and its manifest where :func:`directory_fetch` reads ``<RELEASES>/<version>/``."""
    where = directory / version
    where.mkdir(parents=True, exist_ok=True)
    asset = f"herdr-core-{TARGET}.tar.gz"
    (where / asset).write_bytes(data)
    manifest = {
        "version": version,
        "generation": 1,
        "targets": {TARGET: {"url": f"{RELEASES}/{version}/{asset}", "sha256": manifest_sha or sha(data)}},
    }
    (where / "manifest.json").write_text(json.dumps(manifest))
