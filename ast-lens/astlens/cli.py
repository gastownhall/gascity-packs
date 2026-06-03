"""``bin/op`` CLI driver.

Surface (the ``bin/op`` wrapper hands argv straight to :func:`main`):

    op <op>  <file> [--k v ...]          print the PLAN (read-only)
    op <op>! <file> <token> [--k v ...]  EXECUTE the plan (trailing ! = execute)
    op --list                            list registered ops + availability
    op --matrix                          print the gate's checker matrix
    op -h | --help                       usage

The trailing ``!`` on the op name is the execute selector (paper's ``<op, op!>``
pair). In plan mode the command prints the five-section Markdown and exits 0
(exit 3 if the predicted verdict is reject, so a script can branch). In execute
mode it prints the verdict line and exits 0 on accept, 3 on reject/stale.

Generic ``--k v`` pairs become the op's ``args`` dict; a bare ``--flag`` with no
following value is treated as ``flag=True``.
"""

from __future__ import annotations

import sys

from . import gate as _gate
from . import plan as _plan
from . import registry as _registry

__all__ = ["main"]

_USAGE = """\
ast-lens write-side op CLI

usage:
  op <op>  <file> [--k v ...]          print the PLAN for <op> on <file> (read-only)
  op <op>! <file> <token> [--k v ...]  EXECUTE the plan identified by <token>
  op --list                            list registered ops and availability
  op --matrix                          print the gate's checker matrix
  op -h | --help                       this message

notes:
  - a trailing '!' on the op name selects execute (the <op, op!> pair).
  - --k v pairs become the op's args dict; a bare --flag means flag=True.
  - plan mode never writes; execute writes iff the compile gate accepts.
"""


def _parse_args(rest: list[str]) -> dict:
    """Parse generic ``--k v`` (and bare ``--flag``) pairs into an args dict."""
    args: dict = {}
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok.startswith("--"):
            key = tok[2:]
            if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
                args[key] = rest[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            # Positional after the fixed slots is unexpected; surface it as an
            # arg keyed by position so nothing is silently dropped.
            args[f"_pos{i}"] = tok
            i += 1
    return args


def _cmd_list() -> int:
    avail = _registry.available()
    print("registered ops:")
    # Prefer the combined listing (Python ops + pattern-DSL intents) when the
    # registry exposes it; fall back to the canonical Python-op names otherwise
    # (keeps the CLI working against an older registry).
    names = getattr(_registry, "listing_names", _registry.all_op_names)()
    for name in names:
        is_intent = getattr(_registry, "is_intent", lambda _n: False)(name)
        if avail.get(name):
            mark = "available"
        elif is_intent:
            mark = "UNAVAILABLE (intent failed to load)"
        else:
            mark = "MISSING (sibling op not built)"
        # Pattern-DSL intents carry a one-line description; annotate them so the
        # listing distinguishes a YAML intent from a hand-written Python op.
        suffix = ""
        if is_intent:
            desc = getattr(_registry, "describe", lambda _n: "")(name)
            suffix = f"  [pattern] {desc}".rstrip()
        print(f"  {name:<20} {mark}{suffix}")
    # Surface which pattern-DSL backend is live (paper §4.E two-backend design).
    try:
        from . import pattern as _pattern

        print(f"\npattern-DSL backend: {_pattern.active_backend()}")
    except Exception:  # noqa: BLE001 - engine optional; listing must not fail
        pass
    return 0


def _cmd_matrix() -> int:
    print(_gate.describe_matrix())
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(_USAGE)
        return 0
    if argv[0] == "--list":
        return _cmd_list()
    if argv[0] == "--matrix":
        return _cmd_matrix()

    op_token = argv[0]
    execute_mode = op_token.endswith("!")
    op = op_token[:-1] if execute_mode else op_token

    if len(argv) < 2:
        print(f"op: missing <file> for '{op_token}'\n", file=sys.stderr)
        sys.stdout.write(_USAGE)
        return 2
    file_path = argv[1]

    if execute_mode:
        # op! <file> <token> [--k v ...]
        if len(argv) < 3:
            print(f"op: execute needs a <token>: op {op_token} <file> <token>", file=sys.stderr)
            return 2
        token = argv[2]
        args = _parse_args(argv[3:])
        try:
            result = _plan.execute(op, file_path, args, token)
        except _plan.PlanError as exc:
            print(f"op: {exc}", file=sys.stderr)
            return 2
        v = result.get("verdict")
        reason = result.get("reason", "")
        if v == "accept":
            written = result.get("written", [])
            print(f"ACCEPT — {reason}")
            for path in written:
                print(f"  wrote {path}")
            return 0
        print(f"REJECT — {reason}")
        return 3

    # Plan mode: op <file> [--k v ...]
    args = _parse_args(argv[2:])
    try:
        plan = _plan.make_plan(op, file_path, args)
    except _plan.PlanError as exc:
        print(f"op: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(_plan.render_plan(plan))
    # Exit 3 if the predicted verdict is a reject (or there is nothing to do),
    # so a caller can branch without parsing the Markdown.
    verdict = plan.get("verdict") or {}
    if plan.get("no_change") or verdict.get("verdict") != "accept":
        return 3
    return 0
