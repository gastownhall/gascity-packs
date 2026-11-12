"""Check the pack's infrastructure argv table against gc's.

    python tests/infra_argv_drift.py <gascity>/internal/runtime/proctable/infrastructure_argv.go

The pack never kills city infrastructure with a session, and recognises it
by argv exactly as gc's ``IsCityInfrastructureArgv`` does
(``assets/gc_runtime_herdr_core/herdrcore/infra_argv.py``). This reads that
Go function at the gascity commit CI pins and fails when the two disagree.

The Go source is read, not run, and only the shape the function has always
had is understood: a length guard, one ``switch argv[1]`` whose cases either
``return true`` or require one more word with
``return len(argv) > 2 && argv[2] == <word>``, and ``return false``. Any
other shape fails too, so a change to gc's logic is looked at rather than
half-understood.

Exit 0: the tables match. Exit 1: they differ. Exit 2: the Go source could
not be read or has a shape this check does not understand.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Dict, FrozenSet, List, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "assets"))

from gc_runtime_herdr_core.herdrcore.infra_argv import INFRASTRUCTURE_ARGV  # noqa: E402

FUNCTION = "IsCityInfrastructureArgv"

_CONST = re.compile(r'^\s*(?:const\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"\\]*)"\s*$', re.MULTILINE)
_ONE_MORE = re.compile(r"return len\(argv\) > 2 && argv\[2\] == (\S+)")


class ShapeError(Exception):
    """The Go source is not the shape this check understands."""


def _strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", source)


def _body(source: str, name: str) -> str:
    match = re.search(r"func " + re.escape(name) + r"\(argv \[\]string\) bool \{", source)
    if match is None:
        raise ShapeError(f"no func {name}(argv []string) bool")
    depth = 1
    at = match.end()
    while at < len(source) and depth:
        if source[at] == "{":
            depth += 1
        elif source[at] == "}":
            depth -= 1
        at += 1
    if depth:
        raise ShapeError(f"unbalanced braces in {name}")
    return source[match.end() : at - 1]


def _word(token: str, consts: Dict[str, str]) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] == '"':
        return token[1:-1]
    if token not in consts:
        raise ShapeError(f"{token!r} is not a string constant of the file")
    return consts[token]


def go_table(source: str) -> FrozenSet[Tuple[str, ...]]:
    """The argv[1:] prefixes gc's ``IsCityInfrastructureArgv`` accepts."""
    source = _strip_comments(source)
    consts = dict(_CONST.findall(source))
    body = " ".join(_body(source, FUNCTION).split())
    head = "if len(argv) < 2 { return false } switch argv[1] { "
    tail = " } return false"
    if not (body.startswith(head) and body.endswith(tail)):
        raise ShapeError(f"{FUNCTION} is no longer a length guard, one switch on argv[1] and return false")
    switch = body[len(head) : -len(tail)]
    clauses = re.split(r"(?:^| )case ", switch)
    if clauses[0].strip():
        raise ShapeError(f"unexpected code before the first case: {clauses[0].strip()!r}")
    found: List[Tuple[str, ...]] = []
    for clause in clauses[1:]:
        labels, sep, action = clause.partition(":")
        if not sep:
            raise ShapeError(f"a case without a colon: {clause!r}")
        words = [_word(label, consts) for label in labels.split(",")]
        action = action.strip()
        if action == "return true":
            found.extend((word,) for word in words)
            continue
        more = _ONE_MORE.fullmatch(action)
        if more is None:
            raise ShapeError(f"a case this check does not understand: {action!r}")
        second = _word(more.group(1), consts)
        found.extend((word, second) for word in words)
    if not found:
        raise ShapeError(f"{FUNCTION} accepts nothing")
    return frozenset(found)


def compare(source: str, pack: Sequence[Tuple[str, ...]] = INFRASTRUCTURE_ARGV) -> List[str]:
    """The differences between gc's table in ``source`` and ``pack``; empty when equal."""
    gc = go_table(source)
    mine = frozenset(tuple(entry) for entry in pack)
    problems = [f"gc treats {' '.join(entry)!r} as infrastructure; the pack does not" for entry in sorted(gc - mine)]
    problems += [f"the pack treats {' '.join(entry)!r} as infrastructure; gc does not" for entry in sorted(mine - gc)]
    return problems


def main(argv: Sequence[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <path to infrastructure_argv.go>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as handle:
            source = handle.read()
        problems = compare(source)
    except (OSError, ShapeError) as err:
        print(f"infra-argv drift: {err}", file=sys.stderr)
        return 2
    if problems:
        print("infra-argv drift: the pack's infrastructure argv table differs from gc's:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print("update assets/gc_runtime_herdr_core/herdrcore/infra_argv.py to match", file=sys.stderr)
        return 1
    print(f"infra-argv: the pack matches gc ({len(INFRASTRUCTURE_ARGV)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
