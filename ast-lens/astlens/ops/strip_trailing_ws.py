"""Demo op: strip trailing whitespace.

Language-agnostic on purpose — it is the op the spine uses to prove the
framework end-to-end across languages (Python, Go, JS, ...), exercising the
gate's full checker matrix without depending on any AST machinery.

Contract (shared across all ops):
    compute_change(file_path, args) -> {relpath: new_full_content} | None

Behaviour:
    - Strips trailing spaces/tabs from every line of ``file_path``.
    - Preserves the original line endings and the presence/absence of a final
      newline (so a clean file is genuinely a no-op).
    - Returns ``None`` when the file is already clean, unreadable, or binary —
      "nothing to change / can't do safely" per the contract.
    - ``relpath`` is computed relative to the git root above ``file_path`` if
      one exists, else relative to the file's own directory.

Args:
    none. (Accepts and ignores any ``args`` so the generic ``--k v`` CLI path
    never breaks this op.)
"""

from __future__ import annotations

import os
import subprocess

__all__ = ["compute_change", "repo_root_for", "relpath_for"]


def repo_root_for(file_path: str) -> str:
    """Git root above ``file_path``, else the file's own directory.

    Used to anchor relpaths. Falls back to the containing directory when the
    file is not in a git repo (or ``git`` is unavailable), which keeps ops
    usable on loose files and in tests.
    """
    start = os.path.dirname(os.path.abspath(file_path)) or os.getcwd()
    try:
        proc = subprocess.run(
            ["git", "-C", start, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            root = proc.stdout.strip()
            if root:
                return os.path.realpath(root)
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.realpath(start)


def relpath_for(file_path: str) -> str:
    """Path of ``file_path`` relative to its repo root (see :func:`repo_root_for`)."""
    root = repo_root_for(file_path)
    return os.path.relpath(os.path.realpath(os.path.abspath(file_path)), root)


def compute_change(file_path: str, args: dict) -> dict | None:
    """Strip trailing whitespace; return ``{relpath: new_content}`` or ``None``."""
    try:
        with open(file_path, encoding="utf-8") as fh:
            original = fh.read()
    except (OSError, UnicodeDecodeError):
        # Unreadable or non-UTF-8 (likely binary): cannot do safely -> no change.
        return None

    # Strip trailing spaces/tabs per line while preserving newline characters.
    # ``splitlines(keepends=True)`` keeps each line's terminator (\n, \r\n, \r,
    # or none on the last line), so we rstrip only the non-newline trailing ws.
    out_lines = []
    changed = False
    for line in original.splitlines(keepends=True):
        # Separate the trailing newline (if any) from the line body.
        body = line
        eol = ""
        for term in ("\r\n", "\n", "\r"):
            if line.endswith(term):
                body = line[: -len(term)]
                eol = term
                break
        stripped = body.rstrip(" \t")
        if stripped != body:
            changed = True
        out_lines.append(stripped + eol)

    if not changed:
        return None

    new_content = "".join(out_lines)
    if new_content == original:
        # Defensive: nothing actually differs after reassembly.
        return None

    return {relpath_for(file_path): new_content}
