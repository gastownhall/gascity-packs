"""rename-symbol — compile-aware cross-file symbol rename (Go via gopls).

A write-side op for "The AST as LLM Lens" (sec 5.5 plan/execute, sec 5.D op
catalogue, which describes rename as *"a thin wrapper over the LSP's
compile-aware rename"*). This module is clean-room in architecture but defers
the hard, semantics-bearing work to the language server, exactly as the paper
prescribes: it does NOT re-derive rename semantics.

Why a wrapper, and why conservative
-----------------------------------
A naive textual rename can break a program **semantically** without breaking
its syntax — shadowing, unrelated identifiers that merely share a name, a
method vs. a package-level func, etc. The compile gate downstream catches
*syntax* breakage but not all *semantic* breakage. So this op leans entirely
on gopls, whose ``textDocument/rename`` is type-aware (it renames exactly the
binding under the cursor and every reference to it, across files), and it is
deliberately CONSERVATIVE: anywhere the symbol cannot be pinned to a single,
unambiguous binding — or any tool/parse step is uncertain — it returns
``None`` rather than risk a wrong rename.

Scope (v1)
----------
* **Go (.go) via gopls** — the supported case. Drives the ``gopls rename``
  CLI in diff mode (``gopls rename -d <pos> <new>``), which prints a unified
  diff of every file it would touch *without writing anything*. The diff is
  parsed and applied to in-memory copies of the originals, yielding
  ``{relpath: new_full_content}`` for every changed file.
* **Anything else** (non-Go file, or gopls not installed, or no resolvable
  Go module) → ``None``. v1 does NOT attempt a textual / tree-sitter rename;
  that would forfeit the very semantic safety this op exists to provide.

Contract (shared across the write-side ops)::

    def compute_change(file_path: str, args: dict) -> dict | None

Returns ``{relpath: new_full_content}`` for EVERY file the rename touches
(relpaths anchored at the repo root = git root above ``file_path``, else its
dir), or ``None`` when there is nothing to change / it cannot be done safely.

``args`` carries:
  * ``symbol``   — the current identifier name (required).
  * ``new-name`` / ``new_name`` — the replacement identifier (required).
  * ``line`` / ``col`` (optional, 1-based) — pin the symbol to an exact
    position to disambiguate when several symbols in the file share a name.

This function is PURE: it reads ``file_path``, copies the surrounding Go module
into a throwaway temp tree, and shells out to gopls against that copy. It
NEVER writes or mutates the real file or the working tree.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

__all__ = ["compute_change"]

# Files this op understands.
_GO_EXTS = {".go"}

# Hard ceiling on any single gopls invocation (seconds). Renaming inside one
# small package is well under a second; this only guards a pathological hang so
# the op fails safe (returns None) rather than blocking the spine.
_TIMEOUT = 60


# --------------------------------------------------------------------------- #
# repo-root / relpath helpers (mirror the shared write-side contract; kept
# local so this op imports neither gate nor plan and stays a pure function)
# --------------------------------------------------------------------------- #
def _repo_root(file_path: str) -> str:
    """Return the git root *above* ``file_path``; else the file's own dir.

    relpaths in the returned dict are anchored here: the git worktree root
    containing the file, or — when the file is not inside a git repo (or
    ``git`` is unavailable) — the directory the file lives in. This keeps the
    op usable on loose files and in tests.
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


def _relpath_from_root(abs_path: str, root: str) -> str:
    """``abs_path`` relative to ``root`` (both absolute), with POSIX separators."""
    rel = os.path.relpath(os.path.realpath(abs_path), root)
    return rel.replace(os.sep, "/")


def _module_root(file_path: str) -> str | None:
    """Directory of the nearest ``go.mod`` at or above ``file_path``.

    gopls resolves a *workspace* from its working directory; running it at the
    module root (and passing a path relative to that root) is what lets it load
    the whole package and rename across files — running it elsewhere makes it
    see only the single file (observed behaviour). Returns ``None`` when no
    ``go.mod`` is found, in which case this op declines (returns ``None``):
    GOPATH-mode / loose-file Go is out of scope for v1.
    """
    d = os.path.dirname(os.path.realpath(os.path.abspath(file_path)))
    last = None
    while d and d != last:
        if os.path.isfile(os.path.join(d, "go.mod")):
            return d
        last, d = d, os.path.dirname(d)
    return None


# --------------------------------------------------------------------------- #
# symbol-position resolution (via `gopls symbols`, which is type-aware)
# --------------------------------------------------------------------------- #
# `gopls symbols <file>` lines look like:
#     Foo Function 7:6-7:9
#     T Struct 3:6-3:7
#     \t(T).Method Method 5:12-5:18      (nested members are tab-indented)
#     \tN Field 3:16-3:17
# We key on the trailing `line:col-line:col` selection range and the leading
# name token (for methods, the last dotted component, e.g. (T).Method -> Method).
_SYM_RE = re.compile(
    r"^(?P<indent>\s*)(?P<name>\S+)\s+(?P<kind>\w+)\s+"
    r"(?P<sl>\d+):(?P<sc>\d+)-(?P<el>\d+):(?P<ec>\d+)\s*$"
)


def _simple_name(raw: str) -> str:
    """Last identifier component of a gopls symbol name.

    ``(T).Method`` -> ``Method``; ``pkg.Thing`` -> ``Thing``; ``Foo`` -> ``Foo``.
    Strips a leading ``(...)`` receiver and any dotted qualifier.
    """
    name = re.sub(r"^\([^)]*\)\.", "", raw)  # drop a leading (Recv). receiver
    return name.rsplit(".", 1)[-1]


def _resolve_position(
    gopls: str, module_root: str, rel_to_module: str, symbol: str
) -> tuple[int, int] | None:
    """Resolve ``symbol`` to a 1-based ``(line, col)`` within one file.

    Uses ``gopls symbols`` on the file itself (not the whole workspace) so the
    match is scoped to ``file_path``. Returns the position iff EXACTLY ONE
    symbol in the file has that simple name; returns ``None`` on zero matches
    (symbol not a top-level/declared name here) or on more than one (ambiguous
    — the caller should pass ``line``/``col`` to disambiguate). Conservative by
    design: ambiguity is never resolved by guessing.
    """
    try:
        proc = subprocess.run(
            [gopls, "symbols", rel_to_module],
            cwd=module_root,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None

    matches: list[tuple[int, int]] = []
    for line in proc.stdout.splitlines():
        m = _SYM_RE.match(line)
        if not m:
            continue
        if _simple_name(m.group("name")) == symbol:
            matches.append((int(m.group("sl")), int(m.group("sc"))))
    if len(matches) == 1:
        return matches[0]
    return None  # 0 matches (not here) or >1 (ambiguous) -> decline


# --------------------------------------------------------------------------- #
# unified-diff parsing + application (reconstruct each changed file in memory)
# --------------------------------------------------------------------------- #
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _split_diff_by_file(diff: str) -> list[tuple[str, list[str]]]:
    """Split a multi-file unified diff into ``(target_path, [body lines])``.

    gopls emits, per file, a ``--- <path>.orig`` / ``+++ <path>`` header pair
    followed by ``@@`` hunks. The target path we care about is the ``+++``
    line (the post-edit file). Returns one entry per file, in order.
    """
    out: list[tuple[str, list[str]]] = []
    lines = diff.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if lines[i].startswith("--- ") and i + 1 < n and lines[i + 1].startswith("+++ "):
            target = lines[i + 1][4:].strip()
            # Some diff producers append a tab + timestamp to the path; strip it.
            target = target.split("\t", 1)[0]
            i += 2
            body: list[str] = []
            while i < n and not (
                lines[i].startswith("--- ")
                and i + 1 < n
                and lines[i + 1].startswith("+++ ")
            ):
                body.append(lines[i])
                i += 1
            out.append((target, body))
        else:
            i += 1
    return out


def _apply_hunks(original: str, body: list[str]) -> str | None:
    """Apply one file's unified-diff ``body`` (its ``@@`` hunks) to ``original``.

    Reconstructs the new file by walking the original line-by-line and, at each
    hunk, consuming context/deleted lines (verifying them against the original)
    and emitting context/added lines. gopls may group all ``-`` lines before
    all ``+`` lines within a logical change; that is still a valid unified diff
    — old-side = context+deletions, new-side = context+additions — so this
    reconstruction is order-tolerant within a hunk. Returns ``None`` if any
    expected context/deletion fails to match (we refuse to apply a diff that
    does not line up with the original we hold — fail safe).

    ``original`` is split with ``keepends`` so original line terminators are
    preserved exactly; diff lines (which arrive newline-stripped) are re-joined
    with ``\n`` only for lines the hunk *introduces*, while context/unchanged
    lines reuse the original's own bytes.
    """
    orig_lines = original.splitlines(keepends=True)
    out: list[str] = []
    pos = 0  # 0-based index into orig_lines (next original line to consume)

    i, n = 0, len(body)
    while i < n:
        line = body[i]
        m = _HUNK_RE.match(line)
        if not m:
            i += 1
            continue
        old_start = int(m.group(1))  # 1-based first original line of the hunk
        hunk_old_idx = old_start - 1  # 0-based

        # Emit untouched original lines before this hunk verbatim.
        if hunk_old_idx < pos:
            return None  # overlapping / out-of-order hunk -> refuse
        out.extend(orig_lines[pos:hunk_old_idx])
        pos = hunk_old_idx

        i += 1
        while i < n and not _HUNK_RE.match(body[i]) and not body[i].startswith("--- "):
            seg = body[i]
            if seg.startswith(" "):  # context: present on both sides
                if pos >= len(orig_lines) or orig_lines[pos].rstrip("\r\n") != seg[1:]:
                    return None
                out.append(orig_lines[pos])  # keep original bytes (eol intact)
                pos += 1
            elif seg.startswith("-"):  # deletion: consume from original, emit nothing
                if pos >= len(orig_lines) or orig_lines[pos].rstrip("\r\n") != seg[1:]:
                    return None
                pos += 1
            elif seg.startswith("+"):  # addition: emit, do not consume original
                out.append(seg[1:] + "\n")
            elif seg == "":
                # A bare empty body line denotes a blank context line ("" == " " minus marker
                # when the producer omits the leading space). Treat as blank context.
                if pos >= len(orig_lines) or orig_lines[pos].rstrip("\r\n") != "":
                    return None
                out.append(orig_lines[pos])
                pos += 1
            elif seg.startswith("\\"):
                # "\ No newline at end of file" marker: the previous emitted line
                # had no trailing newline. Strip the newline we just added.
                if out and out[-1].endswith("\n"):
                    out[-1] = out[-1][:-1]
            else:
                return None  # unrecognised diff line -> refuse
            i += 1

    # Emit any remaining original tail after the last hunk.
    out.extend(orig_lines[pos:])
    return "".join(out)


# --------------------------------------------------------------------------- #
# gopls driver
# --------------------------------------------------------------------------- #
def _run_gopls_rename(
    gopls: str, module_root: str, rel_to_module: str, line: int, col: int, new_name: str
) -> str | None:
    """Run ``gopls rename -d`` and return its unified diff, or ``None``.

    Diff mode (``-d``) is read-only: gopls prints what it *would* change and
    writes nothing. We pass the position as ``<relpath>:<line>:<col>`` and run
    with ``cwd=module_root`` so gopls loads the whole module (and thus renames
    across files). A non-zero exit — same-name, not-an-identifier, invalid new
    name, a conflict gopls detects, etc. — yields ``None`` (decline safely).
    """
    pos = f"{rel_to_module}:{line}:{col}"
    try:
        proc = subprocess.run(
            [gopls, "rename", "-d", pos, new_name],
            cwd=module_root,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    diff = proc.stdout
    if not diff.strip():
        return None  # no edits -> nothing to change
    return diff


# --------------------------------------------------------------------------- #
# public entrypoint
# --------------------------------------------------------------------------- #
def _is_ident(s: str) -> bool:
    """True if ``s`` is a syntactically valid Go identifier (ASCII subset)."""
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s or ""))


def _get_new_name(args: dict) -> str | None:
    for key in ("new-name", "new_name", "newName"):
        v = args.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def _int_arg(args: dict, *keys: str) -> int | None:
    for k in keys:
        v = args.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return None


def compute_change(file_path: str, args: dict) -> dict | None:
    """Compile-aware cross-file rename of a Go symbol via gopls.

    See the module docstring for scope and safety posture. Returns
    ``{relpath: new_full_content}`` for every file gopls would touch, or
    ``None`` when nothing should/can change safely (unsupported language,
    gopls/go.mod absent, ambiguous symbol, invalid names, or any uncertainty).
    """
    args = args or {}

    # --- language gate: Go only in v1 -----------------------------------------
    if os.path.splitext(file_path)[1].lower() not in _GO_EXTS:
        return None

    symbol = args.get("symbol")
    new_name = _get_new_name(args)
    if not isinstance(symbol, str) or not symbol:
        return None
    if not new_name:
        return None
    # Both must be valid Go identifiers, and a no-op rename is "nothing to do".
    if not _is_ident(symbol) or not _is_ident(new_name):
        return None
    if symbol == new_name:
        return None

    # --- tool + workspace availability ---------------------------------------
    gopls = shutil.which("gopls")
    if not gopls:
        return None  # gopls-backed rename only; no risky textual fallback in v1.

    abs_file = os.path.realpath(os.path.abspath(file_path))
    if not os.path.isfile(abs_file):
        return None
    module_root = _module_root(abs_file)
    if module_root is None:
        return None  # no go.mod -> can't drive a workspace rename safely.

    # --- operate on a throwaway COPY of the module (never touch the real tree)-
    # gopls -d does not write, but copying guarantees purity even against any
    # cache files gopls might drop, and lets us resolve relpaths cleanly.
    with tempfile.TemporaryDirectory(prefix="astlens-rename-") as tmp:
        dst_root = os.path.join(tmp, "mod")
        try:
            shutil.copytree(module_root, dst_root, symlinks=True)
        except (OSError, shutil.Error):
            return None

        rel_to_module = _relpath_from_root(abs_file, os.path.realpath(module_root))
        tmp_file = os.path.join(dst_root, rel_to_module)
        if not os.path.isfile(tmp_file):
            return None

        # --- resolve the symbol's position ----------------------------------
        line = _int_arg(args, "line")
        col = _int_arg(args, "col", "column")
        if line is None or col is None:
            resolved = _resolve_position(gopls, dst_root, rel_to_module, symbol)
            if resolved is None:
                return None  # not found here, or ambiguous -> decline
            line, col = resolved

        # --- drive the rename, read-only, on the copy -----------------------
        diff = _run_gopls_rename(gopls, dst_root, rel_to_module, line, col, new_name)
        if diff is None:
            return None

        # --- map the diff back to {repo-relpath: new_content} ---------------
        repo_root = _repo_root(file_path)
        result: dict[str, str] = {}
        for target, body in _split_diff_by_file(diff):
            # `target` is a path as gopls printed it: absolute (matches our
            # cwd-relative invocation against the temp tree) or, defensively,
            # relative to the temp module root.
            tgt_abs = target if os.path.isabs(target) else os.path.join(dst_root, target)
            tgt_abs = os.path.realpath(tgt_abs)
            # Recover the path RELATIVE TO THE TEMP MODULE ROOT, then re-root it
            # at the real module so the original source can be read & re-anchored.
            try:
                rel_in_mod = os.path.relpath(tgt_abs, os.path.realpath(dst_root))
            except ValueError:
                return None
            if rel_in_mod.startswith(".."):
                return None  # a path outside the module we copied -> refuse
            real_src = os.path.join(os.path.realpath(module_root), rel_in_mod)
            try:
                with open(real_src, encoding="utf-8") as fh:
                    original = fh.read()
            except (OSError, UnicodeDecodeError):
                return None
            new_content = _apply_hunks(original, body)
            if new_content is None or new_content == original:
                # A hunk that won't apply, or a claimed-but-empty change: bail
                # rather than emit a half-applied or no-op file.
                return None
            result[_relpath_from_root(real_src, repo_root)] = new_content

        return result or None
