"""Decide whether a formula opts into the graph (v2) compiler.

This mirrors `UsesGraphCompiler` in Gas City's `internal/formula/requirements.go`
rather than approximating it. The real rule is not "a formula_compiler
constraint is present": it is that at least one declared constraint **excludes**
the default compiler capability 1.0.0 and **admits** the current capability
2.0.0. `>=2.0.0` satisfies that; `>=1.0.0` does not (it admits both), and
`>=999.0.0` does not (it admits neither).

The distinction matters because the predicate routes real behaviour. A checker
that only asks "is this key non-empty" reports graph-v2 for
`formula_compiler = "banana"` and for a constraint that no compiler will ever
satisfy, which is the shape where a guard agrees with a typo forever.

Constraint parsing is deliberately narrow and **fails closed**. Gas City uses
Masterminds semver, whose grammar is larger than what this repository's packs
actually use; rather than half-implement it and silently mis-evaluate an
unsupported form, `parse_constraint` raises `UnsupportedConstraint`. A pack that
introduces a new constraint shape makes the guard fail loudly, which is the
outcome we want over a guard that quietly guesses. Prereleases are refused for
that reason rather than accepted-and-truncated, and the whole expression is
parsed before any of it is evaluated, so an unsupported group cannot be skipped
because an earlier group already decided the answer.

Refute the rule this file encodes:

    grep -n "declaresGraphCompilerRequirement" -A 25 \
      <gascity checkout>/internal/formula/requirements.go
    grep -n "FormulaCompilerCapability *=" \
      <gascity checkout>/internal/formula/requirements.go
"""

from __future__ import annotations

import re
from typing import Any, Iterable


# The two capabilities the real predicate tests every constraint against.
DEFAULT_COMPILER_CAPABILITY = (1, 0, 0)
CURRENT_COMPILER_CAPABILITY = (2, 0, 0)

# Build metadata is ignored for precedence by the semver spec and by
# Masterminds, so it is accepted and dropped. A PRERELEASE is not: Masterminds
# orders `1.0.0-alpha` below stable `1.0.0`, and a three-integer tuple cannot
# represent that. Modelling it as `1.0.0` inverts `>1.0.0-alpha` (Python would
# exclude 1.0.0 and admit 2.0.0, selecting graph-v2; Go admits 1.0.0 and does
# not), so the form is refused rather than approximated.
_VERSION = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\+[0-9A-Za-z.\-]+)?$")

# One comparator clause. The version must start with a digit, so `banana` is a
# parse failure rather than a silently-false clause, and the comparator may be
# separated from its version by whitespace (`>= 2.0.0`), which Masterminds
# accepts.
_CLAUSE = re.compile(r"(>=|<=|!=|==|=|>|<|\^|~)?\s*([0-9][^\s,]*)")

_SEPARATORS = ", \t"


class UnsupportedConstraint(ValueError):
    """The constraint uses a form this evaluator will not guess at."""


def _version(text: str) -> tuple[int, int, int]:
    stripped = text.strip()
    # `_VERSION` already refuses a prerelease, so this branch changes the
    # message and not the outcome. It is here because the message is the whole
    # value: "not a version: '1.0.0-alpha'" reads like a typo and invites
    # widening the regex, which is the truncating evaluator this module refuses
    # to be. Removing this branch alone is not the regression; widening
    # `_VERSION` to admit `-alpha` is, and `ConstraintEvaluatorTest` catches it.
    if "-" in stripped.split("+", 1)[0]:
        raise UnsupportedConstraint(
            f"prerelease versions are not modelled: {text!r}"
        )
    match = _VERSION.match(stripped)
    if not match:
        raise UnsupportedConstraint(f"not a version: {text!r}")
    major, minor, patch = match.groups()
    return (int(major), int(minor or 0), int(patch or 0))


def _satisfies_one(comparator: str, bound: tuple[int, int, int],
                   candidate: tuple[int, int, int]) -> bool:
    if comparator in ("", "=", "=="):
        return candidate == bound
    if comparator == "!=":
        return candidate != bound
    if comparator == ">":
        return candidate > bound
    if comparator == ">=":
        return candidate >= bound
    if comparator == "<":
        return candidate < bound
    if comparator == "<=":
        return candidate <= bound
    if comparator == "^":
        # ^1.2.3 := >=1.2.3 <2.0.0 (and ^0.x pins the minor, per semver).
        if bound[0] > 0:
            upper = (bound[0] + 1, 0, 0)
        else:
            upper = (0, bound[1] + 1, 0)
        return bound <= candidate < upper
    if comparator == "~":
        # ~1.2.3 := >=1.2.3 <1.3.0
        return bound <= candidate < (bound[0], bound[1] + 1, 0)
    raise UnsupportedConstraint(f"unsupported comparator: {comparator!r}")


def parse_constraint(constraint: str) -> list[list[tuple[str, tuple[int, int, int]]]]:
    """`constraint` as OR groups of AND clauses. Raises on forms we do not model.

    The WHOLE expression is parsed before anything is evaluated. Parsing
    lazily, group by group, made the fail-closed promise conditional on the
    candidate version: `"<=1.0.0 || banana"` would return False for 1.0.0
    without ever looking at `banana`, while `semver.NewConstraint` rejects the
    entire expression. An evaluator that is only strict on some inputs is the
    guard-agrees-with-a-typo shape this module exists to avoid.
    """
    if not isinstance(constraint, str) or not constraint.strip():
        raise UnsupportedConstraint("empty constraint")

    groups: list[list[tuple[str, tuple[int, int, int]]]] = []
    for group in constraint.split("||"):
        text = group.strip()
        clauses: list[tuple[str, tuple[int, int, int]]] = []
        position = 0
        while position < len(text):
            if text[position] in _SEPARATORS:
                position += 1
                continue
            match = _CLAUSE.match(text, position)
            if not match:
                raise UnsupportedConstraint(
                    f"not a comparator clause at offset {position} of {group!r}"
                )
            comparator, bound = match.groups()
            clauses.append((comparator or "", _version(bound)))
            position = match.end()
        if not clauses:
            raise UnsupportedConstraint(f"empty constraint group in {constraint!r}")
        groups.append(clauses)
    return groups


def satisfies(constraint: str, candidate: tuple[int, int, int]) -> bool:
    """Does `candidate` satisfy `constraint`? Raises on forms we do not model."""
    return any(
        all(_satisfies_one(comparator, bound, candidate) for comparator, bound in group)
        for group in parse_constraint(constraint)
    )


def _declared_constraints(formula: dict[str, Any]) -> list[str]:
    """Every formula_compiler constraint this formula declares.

    Both spellings are accepted, because the compiler accepts both: the
    supported `[requires] formula_compiler`, and the deprecated
    `contract = "graph.v2"`, which `directFormulaCompilerConstraints` maps to
    exactly `>=2.0.0`.
    """
    constraints: list[str] = []

    # Order mirrors `directFormulaCompilerConstraints`: contract, then
    # [requires]. It does not change the outcome (the set is conjunctive) but
    # keeps the two implementations comparable line for line.
    contract = formula.get("contract")
    if isinstance(contract, str) and contract.strip().lower() == "graph.v2":
        constraints.append(">=2.0.0")

    requires = formula.get("requires")
    if isinstance(requires, dict):
        declared = requires.get("formula_compiler")
        if isinstance(declared, str) and declared.strip():
            constraints.append(declared.strip())

    return constraints


def declared_constraints(formula: dict[str, Any]) -> list[str]:
    """The formula_compiler constraints one formula declares, in gc's order."""
    return _declared_constraints(formula)


def joined_constraints(constraints: Iterable[str]) -> str:
    """Combine constraints the way `setFormulaCompilerConstraints` does.

    gc does NOT let a child's `[requires]` replace its parents'. `Resolve`
    accumulates `formulaCompilerConstraints` down the whole `extends` chain and
    then overwrites `merged.Requires` with the comma-joined set, so a child
    declaring `">=1.0.0"` over a parent declaring `">=2.0.0"` still compiles as
    graph-v2. A resolver that merges the field child-wins reaches the opposite
    answer.

    This is the SERIALISED form only. gc keeps the constraints separate in
    `compilerRequirementSources` and evaluates them one at a time; re-reading
    this joined string as a single conjunctive constraint is not equivalent.
    Decide with `declares_graph_compiler_from(constraints)`.
    """
    return ", ".join(
        constraint.strip()
        for constraint in constraints
        if isinstance(constraint, str) and constraint.strip()
    )


def declares_graph_compiler_from(constraints: Iterable[str]) -> bool:
    """`UsesGraphCompiler` over an already-accumulated constraint LIST.

    Take the list, never a joined string. `declaresGraphCompilerRequirement`
    walks `compilerRequirementSources` and returns true as soon as ONE
    constraint excludes 1.0.0 and admits 2.0.0; the comma-joined
    `Requires.FormulaCompiler` string is a serialisation of that list, not the
    thing evaluated. The two disagree: a child requiring `>=2.0.0` under a
    parent requiring `!=2.0.0` is graph-v2 in Go (the child qualifies on its
    own), and not graph-v2 when the pair is re-read as the single conjunctive
    constraint `">=2.0.0, !=2.0.0"`, which admits neither 1.0.0 nor 2.0.0.
    """
    for constraint in constraints:
        if (not satisfies(constraint, DEFAULT_COMPILER_CAPABILITY)
                and satisfies(constraint, CURRENT_COMPILER_CAPABILITY)):
            return True
    return False


def declares_graph_compiler(formula: dict[str, Any]) -> bool:
    """The packs-side mirror of Gas City's `UsesGraphCompiler`.

    For a formula read straight off disk, which is what every guard in this
    repository does. `formulaCompilerConstraints` falls back to
    `directFormulaCompilerConstraints` when nothing has been accumulated, so
    the unresolved case is exactly `contract` plus `[requires]` as two
    constraints. For a RESOLVED `extends` chain use
    `declares_graph_compiler_from` with the accumulated list.
    """
    return declares_graph_compiler_from(_declared_constraints(formula))


def formulas_declaring_graph_compiler(
    parsed: Iterable[tuple[str, dict[str, Any]]],
) -> list[str]:
    """Names of the (label, parsed-formula) pairs that opt into the v2 compiler."""
    return [label for label, data in parsed if declares_graph_compiler(data)]
