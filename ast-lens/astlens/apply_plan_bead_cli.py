"""CLI driver for ``bin/apply-plan-bead`` (the refinery / merge-queue glue).

Surface (the ``bin/apply-plan-bead`` wrapper hands argv straight to :func:`main`)::

    apply-plan-bead <bead-id> [--repo DIR] [--stage|--no-stage] [--dry-run] [--gc-bin GC]
    apply-plan-bead --metadata-json @file.json|-   [--repo DIR] [...]

What it does, in order:

  1. Source the bead's metadata — from the live store via ``gc bd show <id>
     --json`` (default), or from an explicit JSON payload via ``--metadata-json``
     (``@path`` reads a file, ``-`` reads stdin; for CI and the demo).
  2. Parse the plan-bead convention (``gc.symbolic_op`` / ``gc.op_file`` /
     ``gc.op_token`` / ``gc.op_args``) into a :class:`astlens.bead.PlanBead`.
  3. Run the GATED execute by shelling out to ``bin/op <op>! <file> <token> ...``.
     The spine owns recompute -> token-check -> gate -> write-iff-accept.
  4. Report the gate verdict. On ACCEPT, ``git add`` the written file(s) (unless
     ``--no-stage``) so the change is staged for gc's normal merge path. On
     REJECT / stale token, write nothing and exit non-zero.

Exit codes mirror ``bin/op`` so a formula step can branch on them: ``0`` accept,
``3`` reject/stale, ``2`` usage / unreadable bead / malformed plan.
"""

from __future__ import annotations

import os
import subprocess
import sys

from . import bead as _bead

__all__ = ["main"]

_USAGE = """\
ast-lens — apply a symbolic-edit PLAN carried by a bead, gated, for the merge queue

usage:
  apply-plan-bead <bead-id> [options]            read the plan-bead from the live store
  apply-plan-bead --metadata-json @f.json [opts] read the plan-bead from a JSON payload
  apply-plan-bead --metadata-json -    [opts]    ... from stdin

options:
  --repo DIR           repo root the op_file is resolved against (default: cwd)
  --stage / --no-stage git add the written file(s) on accept (default: --stage)
  --dry-run            print the bin/op command that WOULD run; do not execute
  --gc-bin GC          the gc binary to call for 'bd show' (default: gc)
  -h, --help           this message

The plan-bead metadata convention:
  gc.symbolic_op  <op>            bare op name (e.g. strip-trailing-ws)
  gc.op_file      <relpath>       file to transform, relative to the repo root
  gc.op_token     <64-hex>        the plan token from `bin/op <op> <file>`
  gc.op_args      <json-object>   optional op args, e.g. {"old":"a","new":"b"}

exit codes: 0 accept (written + staged), 3 reject/stale (nothing written),
            2 usage / unreadable bead / malformed plan payload.
"""


class _Args:
    __slots__ = ("bead_id", "metadata_json", "repo", "stage", "dry_run", "gc_bin")

    def __init__(self) -> None:
        self.bead_id: str | None = None
        self.metadata_json: str | None = None
        self.repo: str = os.getcwd()
        self.stage: bool = True
        self.dry_run: bool = False
        self.gc_bin: str = "gc"


def _parse_argv(argv: list[str]) -> _Args | int:
    """Parse argv into :class:`_Args`, or return an int exit code for help/usage."""
    args = _Args()
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("-h", "--help"):
            sys.stdout.write(_USAGE)
            return 0
        elif tok == "--metadata-json":
            if i + 1 >= len(argv):
                return _usage_err("--metadata-json needs a value (@file.json, -, or inline JSON)")
            args.metadata_json = argv[i + 1]
            i += 2
        elif tok == "--repo":
            if i + 1 >= len(argv):
                return _usage_err("--repo needs a directory")
            args.repo = argv[i + 1]
            i += 2
        elif tok == "--gc-bin":
            if i + 1 >= len(argv):
                return _usage_err("--gc-bin needs a value")
            args.gc_bin = argv[i + 1]
            i += 2
        elif tok == "--stage":
            args.stage = True
            i += 1
        elif tok == "--no-stage":
            args.stage = False
            i += 1
        elif tok == "--dry-run":
            args.dry_run = True
            i += 1
        elif tok.startswith("-"):
            return _usage_err(f"unknown option {tok!r}")
        else:
            if args.bead_id is not None:
                return _usage_err(f"unexpected extra argument {tok!r}")
            args.bead_id = tok
            i += 1

    if args.bead_id is None and args.metadata_json is None:
        return _usage_err("need a <bead-id> or --metadata-json")
    return args


def _usage_err(msg: str) -> int:
    print(f"apply-plan-bead: {msg}\n", file=sys.stderr)
    sys.stderr.write(_USAGE)
    return 2


def _read_metadata_blob(spec: str) -> str:
    """Resolve a --metadata-json spec: ``@path`` -> file, ``-`` -> stdin, else literal."""
    if spec == "-":
        return sys.stdin.read()
    if spec.startswith("@"):
        path = spec[1:]
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            raise _bead.BeadError(f"could not read --metadata-json file {path!r}: {exc}") from exc
    return spec


def _stage(paths: list[str], repo_root: str) -> tuple[list[str], str | None]:
    """``git add`` each path under ``repo_root``. Returns (staged_ok, error|None).

    Staging is best-effort *reporting*: the file is already correctly written by
    the spine on accept, so a staging hiccup (e.g. not a git repo) must not turn
    a successful gated write into a failure. We report it instead.
    """
    staged: list[str] = []
    for path in paths:
        try:
            proc = subprocess.run(
                ["git", "-C", repo_root, "add", "--", path],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return staged, f"git add failed to launch: {exc}"
        if proc.returncode != 0:
            return staged, (proc.stderr.strip() or proc.stdout.strip() or "git add failed")
        staged.append(path)
    return staged, None


def _written_paths(stdout: str) -> list[str]:
    """Extract the ``  wrote <abs-path>`` lines bin/op prints on accept."""
    out: list[str] = []
    for line in stdout.splitlines():
        s = line.strip()
        if s.startswith("wrote "):
            out.append(s[len("wrote ") :].strip())
    return out


def main(argv: list[str]) -> int:
    parsed = _parse_argv(argv)
    if isinstance(parsed, int):
        return parsed
    args = parsed

    repo_root = os.path.abspath(args.repo)

    # 1. Source the metadata.
    try:
        if args.metadata_json is not None:
            blob = _read_metadata_blob(args.metadata_json)
            metadata = _bead.metadata_from_json(blob)
            source_desc = "metadata payload"
        else:
            metadata = _bead.metadata_from_gc(args.bead_id, gc_bin=args.gc_bin)
            source_desc = f"bead {args.bead_id}"
        # 2. Parse the convention.
        plan = _bead.parse_plan_bead(metadata, bead_id=args.bead_id)
    except _bead.BeadError as exc:
        print(f"apply-plan-bead: {exc}", file=sys.stderr)
        return 2

    arg_summary = "" if not plan.args else f" args={plan.args}"
    print(f"plan-bead {source_desc}: op={plan.op} file={plan.op_file}{arg_summary}")
    print(f"  token {plan.token}")

    # 3. Run the gated execute via bin/op (dry-run stops at the assembled command).
    try:
        result = _bead.execute_plan_bead(plan, repo_root, dry_run=args.dry_run)
    except _bead.BeadError as exc:
        print(f"apply-plan-bead: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print("DRY-RUN — would execute:")
        print("  " + " ".join(result["command"]))
        return 0

    verdict = result["verdict"]
    op_stdout = result["stdout"].rstrip("\n")

    if verdict == "reject":
        # Stale token or gate reject. Surface bin/op's reason; write nothing.
        print("REJECT — plan not applied (stale token or gate rejected); nothing written")
        if op_stdout:
            for line in op_stdout.splitlines():
                print(f"  | {line}")
        if result["stderr"].strip():
            print(f"  | {result['stderr'].strip()}")
        return 3

    # 4. ACCEPT: the spine wrote the file(s); echo and optionally stage them.
    written = _written_paths(result["stdout"]) or [result["abs_file"]]
    print("ACCEPT — gate passed; file written by the spine")
    for path in written:
        print(f"  wrote {path}")

    if not args.stage:
        print("  (--no-stage: leaving the change unstaged)")
        return 0

    staged, stage_err = _stage(written, repo_root)
    for path in staged:
        print(f"  staged {path}")
    if stage_err is not None:
        # The gated write succeeded; only staging hit a snag. Report, do not fail
        # the accept — the file is already correct on disk.
        print(f"  note: could not stage for merge ({stage_err}); the change is written, stage manually")
    return 0
