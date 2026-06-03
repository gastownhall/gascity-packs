"""The compile gate (paper Alg. 2; sec 3 false-negative-only contract).

The gate takes a candidate change set ``{relpath: new_full_content}`` and a
repo root, materialises the change into a TEMP copy of *only the touched
files*, runs each file's NATIVE syntax checker, and accepts iff ALL checks
pass.

False-negative-only (paper Def. "false-negative-only contract")::

    gate(changes, root) == accept  =>  the change does not corrupt valid programs

The contract is asymmetric on purpose. Rejecting a safe diff (false negative)
is an inconvenience the agent recovers from by re-planning with a smaller
scope. Accepting a diff that silently breaks the program (false positive) is
the failure mode we cannot tolerate — it poisons the downstream task with a
quietly-broken codebase. Two consequences fall out of that asymmetry, and both
are enforced here:

  1. If NO checker is available for a file's language, the gate REJECTS. A
     language we cannot verify is, by the contract, a language we will not
     accept. (Concretely: ``.ts``/``.tsx`` reject when ``tsc`` is not on PATH.)

  2. The gate NEVER touches the real working tree. The candidate is written to
     a scratch directory under a fresh ``tempfile.mkdtemp`` and discarded after
     the verdict, so a reject leaves the disk untouched and a checker that
     writes side artefacts (e.g. ``py_compile`` ``.pyc``) lands in scratch.

The checker matrix below is the *floor* the paper describes (native syntax
check). The opt-in LSP-diagnose step for typed languages is out of scope for
the spine; absence of that stronger gate only ever makes the gate stricter,
which the contract permits.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

__all__ = ["gate", "checker_for", "CHECKER_MATRIX", "describe_matrix"]

# How long any single native checker may run before we treat it as a failure.
# A checker that hangs is, for the contract's purposes, a checker that did not
# return "pass" — so a timeout rejects (false-negative-safe).
_CHECK_TIMEOUT_S = 30


def _check_python(path: str) -> bool:
    """`.py` -> ``python -m py_compile``. Uses THIS interpreter (the pack venv)."""
    import sys

    proc = _run([sys.executable, "-m", "py_compile", path])
    return proc is not None and proc.returncode == 0


def _check_go(path: str) -> bool:
    """`.go` -> ``gofmt -e`` (parse + format check; nonzero on parse error)."""
    proc = _run(["gofmt", "-e", path])
    return proc is not None and proc.returncode == 0


def _check_node(path: str) -> bool:
    """`.js/.jsx/.mjs/.cjs` -> ``node --check`` (parse-only, no execution)."""
    proc = _run(["node", "--check", path])
    return proc is not None and proc.returncode == 0


def _check_tsc(path: str) -> bool:
    """`.ts/.tsx` -> ``tsc --noEmit`` IF available, else reject.

    Returns False when ``tsc`` is not on PATH, which routes the language to a
    reject per the false-negative-only contract: no checker => no accept.
    """
    if shutil.which("tsc") is None:
        return False
    # ``--noEmit`` typechecks without writing output; we run it on the single
    # materialised file. A nonzero exit (syntax or type error) rejects.
    proc = _run(["tsc", "--noEmit", "--skipLibCheck", path])
    return proc is not None and proc.returncode == 0


# Extension -> (human label, checker callable). The callable returns True iff
# the file at `path` passes that language's native syntax check.
#
# An extension ABSENT from this table has no available checker and therefore
# rejects (handled in `checker_for` -> `gate`). `.ts`/`.tsx` are PRESENT but
# their checker self-rejects when `tsc` is missing — the distinction matters
# only for `describe_matrix`, which reports them as "conditional".
CHECKER_MATRIX: dict[str, tuple[str, object]] = {
    ".py": ("python -m py_compile", _check_python),
    ".go": ("gofmt -e", _check_go),
    ".js": ("node --check", _check_node),
    ".jsx": ("node --check", _check_node),
    ".mjs": ("node --check", _check_node),
    ".cjs": ("node --check", _check_node),
    ".ts": ("tsc --noEmit", _check_tsc),
    ".tsx": ("tsc --noEmit", _check_tsc),
}


def _run(cmd: list[str]) -> subprocess.CompletedProcess | None:
    """Run a checker, swallowing launch/timeout failures into None.

    A None return is treated by callers as "did not pass" — never as a pass —
    keeping the gate false-negative-safe even when a checker binary is broken.
    """
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_CHECK_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def checker_for(relpath: str):
    """Return the checker callable for `relpath`'s extension, or None.

    None means "no checker registered for this language" — which the gate
    converts into a reject.
    """
    ext = os.path.splitext(relpath)[1].lower()
    entry = CHECKER_MATRIX.get(ext)
    return entry[1] if entry is not None else None


def gate(changes: dict, repo_root: str) -> dict:
    """Compile gate: accept iff EVERY touched file passes its native check.

    Args:
        changes: ``{relpath: new_full_content}`` — the full proposed content of
            every file the op would write.
        repo_root: root the relpaths are relative to (only used to make the
            scratch layout legible; the gate never reads or writes under it).

    Returns:
        ``{"verdict": "accept" | "reject", "reason": str}``.

    Guarantees:
        - Real tree untouched: all I/O happens under a fresh temp dir.
        - False-negative-only: an unknown language, a missing checker, an empty
          change set, or any checker error all REJECT.
    """
    if not changes:
        return {"verdict": "reject", "reason": "empty change set: nothing to gate"}

    scratch = tempfile.mkdtemp(prefix="astlens-gate-")
    try:
        for relpath, content in changes.items():
            checker = checker_for(relpath)
            if checker is None:
                ext = os.path.splitext(relpath)[1].lower() or "(none)"
                return {
                    "verdict": "reject",
                    "reason": (
                        f"no syntax checker available for '{ext}' "
                        f"({relpath}); false-negative-only contract rejects "
                        f"languages it cannot verify"
                    ),
                }

            # Materialise into scratch, preserving the relpath so the checker's
            # error messages reference a path that mirrors the real one and so
            # multi-file changes that reference siblings keep their layout.
            target = os.path.join(scratch, relpath)
            os.makedirs(os.path.dirname(target) or scratch, exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(content)

            label = CHECKER_MATRIX[os.path.splitext(relpath)[1].lower()][0]
            if not checker(target):
                return {
                    "verdict": "reject",
                    "reason": f"native syntax check failed ({label}) for {relpath}",
                }

        n = len(changes)
        plural = "file" if n == 1 else "files"
        return {
            "verdict": "accept",
            "reason": f"all {n} touched {plural} passed native syntax check",
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def describe_matrix() -> str:
    """Human-readable checker matrix: which languages verify vs reject *now*.

    Used by docs and by `bin/op --matrix` so an operator can see, on this host,
    which languages the gate can actually accept (a missing ``tsc`` flips
    ``.ts``/``.tsx`` from verifiable to reject).
    """
    rows = []
    seen: dict[str, list[str]] = {}
    for ext, (label, _fn) in CHECKER_MATRIX.items():
        seen.setdefault(label, []).append(ext)
    for label, exts in seen.items():
        exts_s = " ".join(sorted(exts))
        if label.startswith("tsc"):
            ok = shutil.which("tsc") is not None
            status = "VERIFIED" if ok else "REJECT (tsc not on PATH)"
        else:
            # py_compile is the running interpreter; gofmt/node resolved on PATH.
            bin_name = label.split()[0]
            if bin_name == "python":
                status = "VERIFIED"
            else:
                status = "VERIFIED" if shutil.which(bin_name) else f"REJECT ({bin_name} not on PATH)"
        rows.append(f"  {exts_s:<24} {label:<22} {status}")
    rows.append("  (any other extension)   -                      REJECT (no checker)")
    return "Gate checker matrix (false-negative-only):\n" + "\n".join(rows)
