"""Plan-bead glue: read a symbolic-edit PLAN off a gc bead and execute it gated.

This is the *refinery / merge-queue integration* for the ast-lens write side. It
realises the paper's "a plan is a bead payload" idea (``docs/WRITE-SIDE.md`` §5):
a content-addressed PLAN emitted by ``bin/op`` is stateless, so it can be filed
as a bead now and executed *later, by a different agent*, through gc's normal
merge path.

The module is deliberately thin. It does three things and nothing else:

  1. Parse the plan-bead metadata convention (``gc.symbolic_op``, ``gc.op_file``,
     ``gc.op_token``, ``gc.op_args``) out of a bead's metadata dict.
  2. Source that metadata either from the live store (``gc bd show <id> --json``)
     or from an explicit JSON blob (for offline / CI use and the demo), so the
     helper never has to touch a live city to be exercised.
  3. Re-derive and run the gated execute by shelling out to the pack's own
     ``bin/op <op>! <file> <token> [--k v ...]`` — the *same* spine CLI a human
     would run, so there is exactly one execute code path and the compile gate
     stays the single, non-bypassable check before anything reaches disk.

It does **not** import :mod:`astlens.plan` directly: going through ``bin/op``
keeps the executor honest (token re-derivation, gate, write-iff-accept all live
in the spine, which this integration must not reimplement) and means a future
change to the spine's execute semantics is picked up for free.

The bead-metadata convention
----------------------------

A *plan-bead* is an ordinary gc work bead that additionally carries:

    gc.symbolic_op   <op>           e.g. "strip-trailing-ws", "rename-symbol"
    gc.op_file       <relpath>      file to transform, RELATIVE to the repo root
    gc.op_token      <64-hex>       the plan token from `bin/op <op> <file>`
    gc.op_args       <json-object>  optional; op args, e.g. {"old":"a","new":"b"}

``gc.op_file`` is stored repo-relative on purpose: a plan-bead filed by a polecat
in one worktree must execute against the refinery's checkout of the same repo,
where absolute paths differ. The helper resolves it against ``--repo`` (default:
cwd). The token still pins the *content* (from-state + to-state), so a relative
path that resolves to a drifted file is caught by the spine's stale-plan check,
not silently applied.

These live under the reserved ``gc.`` metadata namespace alongside gc's own
routing fields (``gc.routed_to`` &c.), which keeps them clearly framework-owned
and lets the existing refinery metadata reads coexist untouched.
"""

from __future__ import annotations

import json
import os
import subprocess

__all__ = [
    "BeadError",
    "PlanBead",
    "META_OP",
    "META_FILE",
    "META_TOKEN",
    "META_ARGS",
    "metadata_from_gc",
    "metadata_from_json",
    "parse_plan_bead",
    "op_cli_path",
    "args_to_cli",
    "execute_plan_bead",
]

# --- the metadata convention (single source of truth) -----------------------

META_OP = "gc.symbolic_op"
META_FILE = "gc.op_file"
META_TOKEN = "gc.op_token"
META_ARGS = "gc.op_args"


class BeadError(Exception):
    """Raised for an unreadable bead, a malformed plan payload, or a bad arg."""


class PlanBead:
    """A parsed symbolic-edit plan-bead: the four fields plus the source bead id.

    ``args`` is always a dict (empty when ``gc.op_args`` is absent). ``bead_id``
    is informational (None for an inline-metadata source).
    """

    __slots__ = ("op", "op_file", "token", "args", "bead_id")

    def __init__(
        self,
        op: str,
        op_file: str,
        token: str,
        args: dict | None = None,
        bead_id: str | None = None,
    ) -> None:
        self.op = op
        self.op_file = op_file
        self.token = token
        self.args = args or {}
        self.bead_id = bead_id

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (
            f"PlanBead(op={self.op!r}, op_file={self.op_file!r}, "
            f"token={self.token[:12]+'…' if self.token else self.token!r}, "
            f"args={self.args!r}, bead_id={self.bead_id!r})"
        )


# --- sourcing the metadata --------------------------------------------------


def metadata_from_gc(bead_id: str, gc_bin: str = "gc") -> dict:
    """Return a bead's metadata dict via ``gc bd show <id> --json``.

    ``gc bd show --json`` emits a one-element array of bead objects; the metadata
    lives under ``[0].metadata`` (mirroring how the refinery reads
    ``.[0].metadata.branch``). A missing ``metadata`` key yields ``{}``.

    Raises :class:`BeadError` if ``gc`` is absent, the command fails, or the
    output is not the expected shape — the caller must not proceed on a bead it
    could not actually read.
    """
    try:
        proc = subprocess.run(
            [gc_bin, "bd", "show", bead_id, "--json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise BeadError(
            f"could not run '{gc_bin} bd show {bead_id} --json': {exc}. "
            f"Pass --metadata-json to supply the bead payload without gc."
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise BeadError(f"'{gc_bin} bd show {bead_id}' failed to launch: {exc}") from exc

    if proc.returncode != 0:
        raise BeadError(
            f"'{gc_bin} bd show {bead_id} --json' exited {proc.returncode}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return _metadata_from_show_json(proc.stdout, source=f"{gc_bin} bd show {bead_id}")


def metadata_from_json(blob: str) -> dict:
    """Return a metadata dict from an explicit JSON ``blob``.

    Accepts either of two shapes so it is forgiving of how a caller captured it:

      * a bare metadata object, e.g. ``{"gc.symbolic_op": "...", ...}``; or
      * the full ``gc bd show --json`` envelope (a list, or a single bead object
        with a ``metadata`` key), from which ``metadata`` is extracted.

    This is the offline path used by CI and the end-to-end demo: it lets the
    helper be driven from a captured payload with no live city.
    """
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise BeadError(f"--metadata-json is not valid JSON: {exc}") from exc
    return _coerce_metadata(data, source="--metadata-json")


def _metadata_from_show_json(stdout: str, source: str) -> dict:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise BeadError(f"'{source} --json' did not return JSON: {exc}") from exc
    return _coerce_metadata(data, source=source)


def _coerce_metadata(data: object, source: str) -> dict:
    """Normalise a parsed JSON value to a metadata dict (or raise BeadError)."""
    # Full envelope: gc bd show --json -> [ { ..., "metadata": {...} } ]
    if isinstance(data, list):
        if not data:
            raise BeadError(f"'{source}' returned an empty result (no such bead?)")
        data = data[0]
    if isinstance(data, dict):
        if "metadata" in data and isinstance(data["metadata"], dict):
            return data["metadata"]
        if "metadata" in data and data["metadata"] is None:
            return {}
        # A bare metadata object: looks like our convention if it has the keys,
        # otherwise treat the whole dict as the metadata map.
        return data
    raise BeadError(f"'{source}' metadata was not a JSON object: {type(data).__name__}")


# --- parsing the convention -------------------------------------------------


def parse_plan_bead(metadata: dict, bead_id: str | None = None) -> PlanBead:
    """Validate ``metadata`` against the convention and build a :class:`PlanBead`.

    Required: ``gc.symbolic_op``, ``gc.op_file``, ``gc.op_token``. Optional:
    ``gc.op_args`` (a JSON object, or already-decoded dict; anything else is an
    error). Raises :class:`BeadError` with an actionable message on any miss so
    a caller never runs ``bin/op`` with a half-formed plan.
    """
    missing = [k for k in (META_OP, META_FILE, META_TOKEN) if not _present(metadata.get(k))]
    if missing:
        raise BeadError(
            "bead is not a symbolic-edit plan-bead: missing metadata "
            + ", ".join(missing)
            + f". A plan-bead needs {META_OP}, {META_FILE}, {META_TOKEN} "
            f"(and optionally {META_ARGS})."
        )

    op = str(metadata[META_OP]).strip()
    op_file = str(metadata[META_FILE]).strip()
    token = str(metadata[META_TOKEN]).strip()

    if op.endswith("!"):
        # The bead carries the bare op name; the '!' execute selector is applied
        # by this helper. A stored '!' is almost certainly a mistake.
        raise BeadError(
            f"{META_OP}={op!r} must be the bare op name without a trailing '!' "
            f"(the execute selector is applied by the helper)."
        )

    args = _parse_args_field(metadata.get(META_ARGS))
    return PlanBead(op=op, op_file=op_file, token=token, args=args, bead_id=bead_id)


def _present(value: object) -> bool:
    """True if a metadata value is a non-empty string (gc stores strings)."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _parse_args_field(raw: object) -> dict:
    """Decode ``gc.op_args`` into a dict. Absent -> ``{}``; non-object -> error."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BeadError(
                f"{META_ARGS} is not valid JSON: {exc}. "
                f"Store it as a JSON object string, e.g. '{{\"old\":\"a\",\"new\":\"b\"}}'."
            ) from exc
        if not isinstance(decoded, dict):
            raise BeadError(f"{META_ARGS} must be a JSON object, got {type(decoded).__name__}.")
        return decoded
    raise BeadError(f"{META_ARGS} must be a JSON object string, got {type(raw).__name__}.")


# --- invoking the spine -----------------------------------------------------


def op_cli_path() -> str:
    """Absolute path to the pack's ``bin/op`` CLI (this file is ``<pack>/astlens``)."""
    pack_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(pack_dir, "bin", "op")


def args_to_cli(args: dict) -> list[str]:
    """Flatten an op ``args`` dict into the spine's ``--k v`` / bare-``--flag`` form.

    Mirrors :func:`astlens.cli._parse_args` so a round-trip
    (bead args -> CLI -> parsed args) is faithful:

      * ``True``  -> bare ``--flag``     (cli parses a flag-with-no-value as True)
      * ``False`` -> omitted             (a bare ``--flag`` can only encode True;
                                          emitting nothing is the honest inverse)
      * other     -> ``--k`` ``str(v)``

    Values are passed as separate argv elements (never shell-interpolated), so
    spaces and shell metacharacters in an arg value are safe.
    """
    out: list[str] = []
    for key, value in args.items():
        flag = f"--{key}"
        if value is True:
            out.append(flag)
        elif value is False:
            continue
        else:
            out.extend([flag, str(value)])
    return out


def execute_plan_bead(
    plan: PlanBead,
    repo_root: str,
    *,
    op_bin: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the gated execute for ``plan`` via ``bin/op <op>! <file> <token> ...``.

    ``op_file`` is resolved against ``repo_root`` (it is stored repo-relative).
    Returns a dict::

        {
          "verdict": "accept" | "reject",
          "exit_code": int,        # bin/op exit (0 accept, 3 reject/stale, 2 usage)
          "stdout": str,
          "stderr": str,
          "command": [str, ...],   # the exact argv invoked (or that would be)
          "abs_file": str,         # resolved absolute target path
        }

    No writes happen here: ``bin/op`` owns the recompute -> token-check -> gate ->
    write-iff-accept sequence. On ``dry_run`` the command is assembled and
    returned with ``verdict="dry-run"`` and ``exit_code=-1`` without launching it.
    """
    op_bin = op_bin or op_cli_path()
    abs_file = os.path.normpath(os.path.join(repo_root, plan.op_file))

    command = [op_bin, f"{plan.op}!", abs_file, plan.token, *args_to_cli(plan.args)]

    if dry_run:
        return {
            "verdict": "dry-run",
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "command": command,
            "abs_file": abs_file,
        }

    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except FileNotFoundError as exc:
        raise BeadError(f"could not run bin/op at {op_bin!r}: {exc}") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise BeadError(f"bin/op failed to launch: {exc}") from exc

    # bin/op exit codes: 0 accept, 3 reject/stale, 2 usage/op-resolution error.
    if proc.returncode == 0:
        verdict = "accept"
    elif proc.returncode == 3:
        verdict = "reject"
    else:
        # A usage / resolution failure is not a gate verdict; surface it as such
        # so the caller does not misreport it as a normal "reject".
        raise BeadError(
            f"bin/op did not run the plan (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )

    return {
        "verdict": verdict,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "command": command,
        "abs_file": abs_file,
    }
