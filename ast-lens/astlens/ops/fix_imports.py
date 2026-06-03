"""fix-imports — re-canonicalise a file's import block.

A write-side op for "The AST as LLM Lens" (sec 5.5 plan/execute, sec 5.D
op catalogue). It re-canonicalises the imports of a single source file:
removing unused imports and sorting/grouping the remainder into the
language's canonical form.

Like the paper's rename op (which wraps the LSP rather than re-deriving
rename semantics), this op is *clean-room in architecture but defers the
hard, battle-tested work to the language's own formatter*:

  * Go (``.go``):     ``goimports`` (groups + sorts + drops unused). Falls
                      back to ``gofmt`` when ``goimports`` is absent (gofmt
                      sorts within an import group but does not drop unused).
  * Python (``.py``): ``ruff`` (``--select F401,I --fix`` removes unused
                      imports and sorts them). Falls back to
                      ``autoflake`` + ``isort`` when ruff is absent.

Contract (shared across the write-side ops):

    def compute_change(file_path: str, args: dict) -> dict | None

Returns ``{relpath: new_full_content}`` for the single file when its content
actually changes; returns ``None`` when the file is already canonical, the
language is unsupported (only Go + Python here), or no suitable tool is
available. ``args`` is unused — fix-imports operates on the whole file — and
is accepted and ignored.

This function is PURE: it reads ``file_path`` and shells out to the formatter
against a *temp copy* (or stdin), but it NEVER writes or mutates the real file
or the working tree. The spine wraps and gates the returned content.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

# Languages this op understands, keyed by file extension.
_GO_EXTS = {".go"}
_PY_EXTS = {".py"}

# Hard ceiling on how long any one formatter may run (seconds). Formatting a
# single source file is sub-second in practice; this only guards against a
# pathological hang so the op fails safe (returns None) rather than blocking
# the spine.
_TIMEOUT = 30


# --------------------------------------------------------------------------- #
# repo-root / relpath helpers
# --------------------------------------------------------------------------- #
def _repo_root(file_path: str) -> str:
    """Return the git root *above* ``file_path``; else the file's own dir.

    Mirrors the shared write-side contract: relpaths in the returned dict are
    relative to the repo root, defined as the git worktree root containing the
    file, or — when the file is not inside a git repo — the directory the file
    lives in.
    """
    start = os.path.dirname(os.path.abspath(file_path))
    try:
        out = subprocess.run(
            ["git", "-C", start, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        if out.returncode == 0:
            root = out.stdout.strip()
            if root:
                return os.path.abspath(root)
    except (OSError, subprocess.SubprocessError):
        pass
    return start


def _relpath(file_path: str, root: str) -> str:
    """relpath of ``file_path`` under ``root``, with forward slashes."""
    rel = os.path.relpath(os.path.abspath(file_path), root)
    return rel.replace(os.sep, "/")


# --------------------------------------------------------------------------- #
# tool discovery
# --------------------------------------------------------------------------- #
def _which(name: str) -> str | None:
    """``command -v <name>`` — the resolved path, or None if not on PATH."""
    return shutil.which(name)


# --------------------------------------------------------------------------- #
# language back-ends
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], *, stdin: str | None = None) -> tuple[int, str, str]:
    """Run ``cmd``, optionally feeding ``stdin``. Returns (rc, stdout, stderr).

    Decoding is UTF-8 with ``errors='replace'`` so an odd byte in a source
    file degrades to a replacement char rather than raising — consistent with
    the read side's robust handling of non-UTF-8 sources.
    """
    proc = subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        timeout=_TIMEOUT,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def _canonicalise_go(source: str) -> str | None:
    """Canonical Go imports via goimports (preferred) or gofmt (fallback).

    goimports both *removes* unused imports and groups/sorts them; gofmt only
    sorts within an existing import group (it will not drop an unused import),
    so it is a strictly weaker fallback used only when goimports is unavailable.

    Returns the canonical file content, or None when neither tool is present or
    the tool fails (e.g. the file does not parse — fail safe, change nothing).
    """
    tool = _which("goimports")
    if tool is None:
        tool = _which("gofmt")
    if tool is None:
        return None

    # Both goimports and gofmt read source on stdin and write the formatted
    # result to stdout, leaving stderr for diagnostics. Feeding via stdin keeps
    # us from ever touching a file on disk.
    rc, out, _err = _run([tool], stdin=source)
    if rc != 0:
        # Non-zero means the formatter rejected the input (typically a syntax
        # error). Changing nothing is the safe outcome.
        return None
    return out


def _canonicalise_python(source: str, filename: str) -> str | None:
    """Canonical Python imports via ruff (preferred) or autoflake+isort.

    ruff path: ``ruff check --select F401,I --fix`` removes unused imports
    (F401) and sorts/groups the import block (I), reading the source on stdin
    and emitting the fixed source on stdout — the real file is never touched.
    The ``--stdin-filename`` makes ruff resolve project config and first-party
    package detection as if the bytes came from ``filename``.

    Fallback path (no ruff): ``autoflake --remove-all-unused-imports`` to drop
    unused imports, then ``isort`` to sort them — both run against a temp copy
    so the real file is untouched.

    Returns the canonical content, or None when no tool is available or a tool
    fails.
    """
    ruff = _which("ruff")
    if ruff is not None:
        # ruff prints the fixed file to stdout and its "Found N errors" summary
        # to stderr. With --fix + a fixable selection, a clean exit (0) means
        # the stdout buffer is the canonical content. A non-zero exit signals
        # unfixable lint (e.g. a syntax error) — change nothing.
        rc, out, _err = _run(
            [
                ruff,
                "check",
                "--select",
                "F401,I",
                "--fix",
                "--stdin-filename",
                filename,
                "-",
            ],
            stdin=source,
        )
        if rc != 0:
            return None
        return out

    # ---- fallback: autoflake (+ isort) against a temp copy ---------------- #
    autoflake = _which("autoflake")
    isort = _which("isort")
    if autoflake is None and isort is None:
        return None

    tmpdir = tempfile.mkdtemp(prefix="astlens-fiximports-")
    try:
        # Preserve the basename so isort's first-party heuristics and any
        # per-file config keyed on the name behave as they would in place.
        tmp = os.path.join(tmpdir, os.path.basename(filename) or "module.py")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(source)

        if autoflake is not None:
            rc, _out, _err = _run(
                [autoflake, "--in-place", "--remove-all-unused-imports", tmp]
            )
            if rc != 0:
                return None
        if isort is not None:
            rc, _out, _err = _run([isort, tmp])
            if rc != 0:
                return None

        with open(tmp, encoding="utf-8") as fh:
            return fh.read()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# public op
# --------------------------------------------------------------------------- #
def compute_change(file_path: str, args: dict) -> dict | None:
    """Re-canonicalise the imports of ``file_path``.

    See the module docstring for the full contract. ``args`` is accepted and
    ignored (fix-imports operates on the whole file, not a sub-range).

    Returns ``{relpath: new_content}`` for the single file when its content
    actually changes, else ``None`` (already canonical, unsupported language,
    no tool available, or the formatter failed / the file does not parse).
    """
    del args  # unused for fix-imports; declared for the shared op signature.

    path = os.path.abspath(file_path)
    if not os.path.isfile(path):
        return None

    ext = os.path.splitext(path)[1].lower()
    if ext not in _GO_EXTS and ext not in _PY_EXTS:
        return None  # only Go + Python are supported in this op.

    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return None

    if ext in _GO_EXTS:
        new_content = _canonicalise_go(source)
    else:
        new_content = _canonicalise_python(source, os.path.basename(path))

    if new_content is None:
        return None  # no tool, or the formatter rejected the input.
    if new_content == source:
        return None  # already canonical — nothing to change.

    root = _repo_root(path)
    return {_relpath(path, root): new_content}
