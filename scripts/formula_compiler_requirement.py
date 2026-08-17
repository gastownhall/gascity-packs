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
outcome we want over a guard that quietly guesses.

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

_VERSION = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?$")
_COMPARATOR = re.compile(r"^(>=|<=|!=|==|=|>|<|\^|~)?\s*(.+)$")


class UnsupportedConstraint(ValueError):
    """The constraint uses a form this evaluator will not guess at."""


def _version(text: str) -> tuple[int, int, int]:
    match = _VERSION.match(text.strip())
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


def satisfies(constraint: str, candidate: tuple[int, int, int]) -> bool:
    """Does `candidate` satisfy `constraint`? Raises on forms we do not model."""
    if not isinstance(constraint, str) or not constraint.strip():
        raise UnsupportedConstraint("empty constraint")

    for group in constraint.split("||"):  # OR across groups
        clauses = [c for c in re.split(r"[,\s]+", group.strip()) if c]
        if not clauses:
            raise UnsupportedConstraint(f"empty constraint group in {constraint!r}")
        if all(_clause_holds(clause, candidate) for clause in clauses):
            return True
    return False


def _clause_holds(clause: str, candidate: tuple[int, int, int]) -> bool:
    match = _COMPARATOR.match(clause)
    if not match:
        raise UnsupportedConstraint(f"not a comparator clause: {clause!r}")
    comparator, bound = match.groups()
    return _satisfies_one(comparator or "", _version(bound), candidate)


def _declared_constraints(formula: dict[str, Any]) -> list[str]:
    """Every formula_compiler constraint this formula declares.

    Both spellings are accepted, because the compiler accepts both: the
    supported `[requires] formula_compiler`, and the deprecated
    `contract = "graph.v2"`, which `directFormulaCompilerConstraints` maps to
    exactly `>=2.0.0`.
    """
    constraints: list[str] = []

    requires = formula.get("requires")
    if isinstance(requires, dict):
        declared = requires.get("formula_compiler")
        if isinstance(declared, str) and declared.strip():
            constraints.append(declared.strip())

    contract = formula.get("contract")
    if isinstance(contract, str) and contract.strip().lower() == "graph.v2":
        constraints.append(">=2.0.0")

    return constraints


def declares_graph_compiler(formula: dict[str, Any]) -> bool:
    """The packs-side mirror of Gas City's `UsesGraphCompiler`."""
    for constraint in _declared_constraints(formula):
        if (not satisfies(constraint, DEFAULT_COMPILER_CAPABILITY)
                and satisfies(constraint, CURRENT_COMPILER_CAPABILITY)):
            return True
    return False


def formulas_declaring_graph_compiler(
    parsed: Iterable[tuple[str, dict[str, Any]]],
) -> list[str]:
    """Names of the (label, parsed-formula) pairs that opt into the v2 compiler."""
    return [label for label, data in parsed if declares_graph_compiler(data)]
