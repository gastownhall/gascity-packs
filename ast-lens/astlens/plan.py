"""Plan / execute pair (paper sec 5.5; Alg. "plan/execute pair contract").

A compound op is exposed as a pair ``<op, op!>``:

  - ``make_plan(op, file, args)`` runs the op's ``compute_change`` against the
    CURRENT file content and returns a structured plan: target, scope, per-file
    unified diff, the predicted gate verdict, and a content-addressed *plan
    token*. ``render_plan`` turns that into the five-section Markdown the agent
    reads. Planning is READ-ONLY — it writes nothing.

  - ``execute(op, file, args, token)`` recomputes ``compute_change`` from the
    CURRENT file content, derives the token afresh, and aborts with
    "stale plan, re-plan" if it differs from the caller's token (the file
    changed since the plan was emitted — a real conflict, not a spurious one).
    On a matching token it submits to the :func:`astlens.gate.gate` and writes
    the new contents to the REAL files iff the verdict is ``accept``. It returns
    the verdict either way.

The plan token is the trade-off from the paper made concrete. It is::

    token = sha256( op
                    + for each changed relpath (sorted):
                          sha256(current bytes of that file)
                        + sha256(new content) )

i.e. content-addressed over (intent, every from-state, every to-state). This
makes plans *stateless* — no server-side cookie, no session — so any agent can
emit a plan now and any other agent can execute it later, and a drifted file is
caught deterministically rather than silently re-applied. That statelessness is
exactly what lets a plan ride a gc bead payload (see ``docs/WRITE-SIDE.md``).
"""

from __future__ import annotations

import difflib
import hashlib
import os

from . import gate as _gate
from . import registry as _registry

__all__ = [
    "make_plan",
    "render_plan",
    "execute",
    "PlanError",
    "compute_token",
]


class PlanError(Exception):
    """Raised for unresolvable ops or other plan-time failures."""


def _read_current(file_path: str) -> bytes:
    """Current bytes of ``file_path``, or empty bytes if it does not exist."""
    try:
        with open(file_path, "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repo_root_for(file_path: str) -> str:
    """Repo root used to resolve a changed file's real path on execute.

    Mirrors the op-side anchoring (git root above the file, else its dir) so a
    relpath the op emitted round-trips back to the same absolute path here.
    Reuses the demo op's helper when available, with a local fallback so plan
    does not hard-depend on any single op module.
    """
    try:
        from .ops.strip_trailing_ws import repo_root_for

        return repo_root_for(file_path)
    except Exception:  # noqa: BLE001 - any failure -> safe local fallback
        import subprocess

        start = os.path.dirname(os.path.abspath(file_path)) or os.getcwd()
        try:
            proc = subprocess.run(
                ["git", "-C", start, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return os.path.realpath(proc.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
        return os.path.realpath(start)


def compute_token(op: str, changes: dict, current: dict[str, bytes]) -> str:
    """Content-addressed plan token over (op, from-states, to-states).

    Args:
        op: the op name (intent).
        changes: ``{relpath: new_full_content}`` from ``compute_change``.
        current: ``{relpath: current_bytes}`` for each changed relpath.

    The relpaths are processed in sorted order so the token is independent of
    dict iteration order. A relpath absent from ``current`` hashes the empty
    string (a new file's from-state).
    """
    h = hashlib.sha256()
    h.update(op.encode("utf-8"))
    for relpath in sorted(changes):
        cur = current.get(relpath, b"")
        new = changes[relpath]
        if isinstance(new, str):
            new = new.encode("utf-8")
        h.update(_sha(cur).encode("ascii"))
        h.update(_sha(new).encode("ascii"))
    return h.hexdigest()


def _changes_and_token(op: str, file_path: str, args: dict):
    """Run ``compute_change`` and derive (changes, current_bytes, token).

    Returns ``(None, {}, None)`` when the op declines (no change / unsafe).
    """
    try:
        compute_change = _registry.resolve(op)
    except _registry.OpError as exc:
        raise PlanError(str(exc)) from exc

    changes = compute_change(file_path, args or {})
    if not changes:
        return None, {}, None

    root = _repo_root_for(file_path)
    current: dict[str, bytes] = {}
    for relpath in changes:
        abs_path = os.path.join(root, relpath)
        current[relpath] = _read_current(abs_path)

    token = compute_token(op, changes, current)
    return changes, current, token


def make_plan(op: str, file_path: str, args: dict | None = None) -> dict:
    """Build a structured plan for ``op`` on ``file_path`` (read-only).

    Returns a dict with keys:
        op, file_path, repo_root, args, changes (or None), current (bytes),
        token (or None), verdict (gate result or None), no_change (bool).

    When the op declines, ``no_change`` is True and ``changes``/``token`` are
    None. Otherwise the predicted gate verdict is computed by running the real
    gate against the materialised change (in a temp dir — still no real writes).
    """
    args = args or {}
    changes, current, token = _changes_and_token(op, file_path, args)
    root = _repo_root_for(file_path)

    if not changes:
        return {
            "op": op,
            "file_path": os.path.abspath(file_path),
            "repo_root": root,
            "args": args,
            "changes": None,
            "current": {},
            "token": None,
            "verdict": None,
            "no_change": True,
        }

    verdict = _gate.gate(changes, root)
    return {
        "op": op,
        "file_path": os.path.abspath(file_path),
        "repo_root": root,
        "args": args,
        "changes": changes,
        "current": current,
        "token": token,
        "verdict": verdict,
        "no_change": False,
    }


def _unified_diff(relpath: str, old: str, new: str) -> str:
    """difflib unified diff of one file (old vs new), labelled by relpath.

    Lines are split WITHOUT keepends and ``lineterm=""`` so difflib does not
    emit embedded newlines; the caller fences the result and joins on newline,
    giving a clean one-line-per-diff-line hunk.
    """
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{relpath}",
        tofile=f"b/{relpath}",
        lineterm="",
    )
    return "\n".join(diff)


def render_plan(plan: dict) -> str:
    """Render a plan dict as the five-section Markdown contract surface.

    Sections: Target, Scope, Diff, Predicted verdict, Plan token. When the op
    declines, a clear "no change" plan is rendered (no token, no diff) so the
    CLI still produces a legible, executable-by-nothing result.
    """
    op = plan["op"]
    file_path = plan["file_path"]
    root = plan["repo_root"]

    lines: list[str] = []
    lines.append(f"# Plan: {op}")
    lines.append("")

    # 1. Target
    lines.append("## Target")
    lines.append(f"- op: `{op}`")
    lines.append(f"- file: `{file_path}`")
    lines.append(f"- repo root: `{root}`")
    if plan.get("args"):
        arg_s = ", ".join(f"{k}={v!r}" for k, v in plan["args"].items())
        lines.append(f"- args: {arg_s}")
    lines.append("")

    if plan.get("no_change"):
        lines.append("## Scope")
        lines.append("- (no change) the op declined: nothing to change or not safe to.")
        lines.append("")
        lines.append("## Diff")
        lines.append("_(empty)_")
        lines.append("")
        lines.append("## Predicted verdict")
        lines.append("- **n/a** — no diff to gate.")
        lines.append("")
        lines.append("## Plan token")
        lines.append("- (none) — nothing to execute.")
        lines.append("")
        return "\n".join(lines)

    changes = plan["changes"]
    current = plan["current"]

    # 2. Scope
    lines.append("## Scope")
    n = len(changes)
    plural = "file" if n == 1 else "files"
    lines.append(f"- {n} {plural} changed (relative to repo root):")
    for relpath in sorted(changes):
        lines.append(f"  - `{relpath}`")
    lines.append("")

    # 3. Diff (difflib unified, old vs new, per file)
    lines.append("## Diff")
    for relpath in sorted(changes):
        old = current.get(relpath, b"")
        old_text = old.decode("utf-8", errors="replace") if isinstance(old, bytes) else old
        new_text = changes[relpath]
        diff = _unified_diff(relpath, old_text, new_text)
        lines.append("```diff")
        lines.append(diff if diff else f"# (no textual diff for {relpath})")
        lines.append("```")
    lines.append("")

    # 4. Predicted verdict (run the gate)
    verdict = plan["verdict"] or {}
    v = verdict.get("verdict", "unknown")
    reason = verdict.get("reason", "")
    marker = "ACCEPT" if v == "accept" else "REJECT"
    lines.append("## Predicted verdict")
    lines.append(f"- **{marker}** — {reason}")
    lines.append("")

    # 5. Plan token
    lines.append("## Plan token")
    lines.append(f"- `{plan['token']}`")
    lines.append("")
    lines.append(f"Execute with: `bin/op {op}! {file_path} {plan['token']}`")
    lines.append("")

    return "\n".join(lines)


def execute(op: str, file_path: str, args: dict | None, token: str) -> dict:
    """Recompute, verify the token, gate, and write iff accept.

    Returns ``{"verdict", "reason", ...}``:
        - stale plan      -> ``{"verdict": "reject", "reason": "stale plan, re-plan", ...}``
                             and NOTHING is written.
        - gate reject     -> the gate's reject verdict; nothing written.
        - gate accept     -> the gate's accept verdict; new contents written to
                             the real files; ``"written"`` lists the abs paths.

    The token check happens BEFORE the gate and before any write, so a drifted
    file can never be committed against a stale plan.
    """
    args = args or {}

    changes, current, fresh_token = _changes_and_token(op, file_path, args)

    if not changes:
        # The file no longer needs changing (e.g. someone else already applied
        # it). That is a drift relative to the plan that produced `token`.
        return {
            "verdict": "reject",
            "reason": "stale plan, re-plan (op now declines: nothing to change)",
            "written": [],
        }

    if fresh_token != token:
        return {
            "verdict": "reject",
            "reason": "stale plan, re-plan (file changed since the plan was emitted)",
            "written": [],
        }

    root = _repo_root_for(file_path)
    verdict = _gate.gate(changes, root)

    if verdict.get("verdict") != "accept":
        # Reject: write nothing, surface the gate's reason verbatim.
        return {**verdict, "written": []}

    # Accept: commit to the REAL tree. Write every changed file in full.
    written: list[str] = []
    for relpath in sorted(changes):
        abs_path = os.path.join(root, relpath)
        os.makedirs(os.path.dirname(abs_path) or root, exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as fh:
            fh.write(changes[relpath])
        written.append(abs_path)

    return {**verdict, "written": written}
