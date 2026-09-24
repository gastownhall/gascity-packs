"""No shipped formula may declare the deprecated `contract = "graph.v2"`.

`gc doctor`'s formula-requirements check emits one blocking warning per formula
that still carries it, in every city that imports the pack. The supported
declaration is:

    [requires]
    formula_compiler = ">=2.0.0"

The two forms are equivalent at the compiler. `directFormulaCompilerConstraints`
in gascity core maps `contract = "graph.v2"` to exactly the constraint the
`[requires]` key produces, and every consumer of the graph-v2 contract keys off
the resulting constraint set rather than the literal field, so the bead stamp
`gc.formula_contract=graph.v2` is unaffected by the migration.

Both rails are asserted. `test_no_deprecated_contract_declaration` is the deny
check; `test_the_guard_has_something_to_check` is its discovery control, so a
glob that stops matching cannot turn this file into a vacuous pass.

The replacement set is derived by **parsing** each formula and evaluating the
declared constraint the way the compiler does, not by grepping for the text
`formula_compiler =`. A text match counts the key inside a comment, inside a
formula's prose description, and when its value is `""` or `"banana"`, so a
grep-based check would agree with 87 formulas that opted into nothing. The rule
itself lives in `scripts/formula_compiler_requirement.py`, and the expected set
in `tests/graph_v2_formulas.txt`.
"""

from __future__ import annotations

import pathlib
import re
import sys
import tomllib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from formula_compiler_requirement import (  # noqa: E402
    UnsupportedConstraint,
    declares_graph_compiler,
    declares_graph_compiler_from,
    satisfies,
)

DEPRECATED = re.compile(r'^\s*contract\s*=\s*"graph\.v2"', re.MULTILINE)

# Below this, the enumeration has broken rather than the repo having shrunk.
MINIMUM_FORMULAS = 50

# The formulas that declare a constraint selecting the v2 compiler, as a SET.
# A floor on the count cannot separate "one declaration removed, one formula
# added" from "nothing changed", so the identities are pinned instead.
DECLARING_FIXTURE = REPO_ROOT / "tests" / "graph_v2_formulas.txt"


def expected_declaring() -> set[str]:
    """The pinned set, from the fixture file."""
    return {
        line.strip()
        for line in DECLARING_FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def formula_files() -> list[pathlib.Path]:
    """Every shipped formula definition, from the tree rather than a list."""
    return sorted(
        path
        for path in REPO_ROOT.glob("*/formulas/**/*.toml")
        if "__pycache__" not in path.parts
    )


class FormulaContractDeclarationTest(unittest.TestCase):
    def test_the_guard_has_something_to_check(self) -> None:
        found = formula_files()
        self.assertGreaterEqual(
            len(found),
            MINIMUM_FORMULAS,
            f"only {len(found)} formula files found under {REPO_ROOT}; the "
            "enumeration is broken, so the deny check below would pass "
            "vacuously",
        )

    def test_no_deprecated_contract_declaration(self) -> None:
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in formula_files()
            if DEPRECATED.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(
            offenders,
            [],
            "these formulas declare the deprecated contract key; replace each "
            'with a [requires] table carrying formula_compiler = ">=2.0.0": '
            + ", ".join(offenders),
        )

    def test_the_declaration_was_replaced_and_not_merely_deleted(self) -> None:
        """The deny check alone would accept deleting the declaration.

        A graph-v2 formula stripped of both forms does not fail to compile. It
        silently takes the v1 path (`isGraphWorkflow` returns false and
        `compile` skips the graph stages), losing graph validation and the
        `gc.formula_contract` bead stamp with no error anywhere.

        Named formulas, not a count. A floor of 87 holds while one formula
        loses its declaration and an unrelated one gains it, which is the
        realistic shape of the regression: a migration touches many files and
        misses one. The fixture makes the miss a named diff.
        """
        declaring = []
        unparseable = []
        for path in formula_files():
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as exc:
                unparseable.append(f"{path.relative_to(REPO_ROOT)}: {exc}")
                continue
            try:
                if declares_graph_compiler(data):
                    declaring.append(path)
            except UnsupportedConstraint as exc:
                unparseable.append(f"{path.relative_to(REPO_ROOT)}: {exc}")

        self.assertEqual(
            unparseable,
            [],
            "these formulas could not be evaluated, so they are neither "
            "counted nor cleared; fix the file or teach "
            "scripts/formula_compiler_requirement.py the constraint form:\n  "
            + "\n  ".join(unparseable),
        )
        found = {str(path.relative_to(REPO_ROOT)) for path in declaring}
        expected = expected_declaring()
        self.assertEqual(
            sorted(expected - found),
            [],
            "these formulas are pinned in tests/graph_v2_formulas.txt as "
            "requiring the v2 graph compiler and no longer declare it, so they "
            "now compile down the v1 path with no error anywhere. Restore the "
            "declaration; edit the fixture only when the formula was deleted "
            "or genuinely stopped needing v2.",
        )
        self.assertEqual(
            sorted(found - expected),
            [],
            "these formulas declare the v2 compiler and are not in "
            "tests/graph_v2_formulas.txt. Add them, so the next removal is a "
            "named diff rather than a count that still adds up.",
        )

    def test_the_count_rejects_a_constraint_that_selects_nothing(self) -> None:
        """Mutation control for the counter itself.

        A text-matching version of the check above counts every one of these,
        which is how a floor of 87 can hold over 87 formulas that opted into
        nothing. The predicate must separate them.
        """
        selects = {"formula_compiler": ">=2.0.0"}
        for rejected in (">=1.0.0", ">=999.0.0", "", "   ", "^1.0.0"):
            self.assertFalse(
                declares_graph_compiler({"requires": {"formula_compiler": rejected}}),
                f"{rejected!r} does not select the v2 compiler, but the "
                "predicate accepted it",
            )
        self.assertTrue(declares_graph_compiler({"requires": selects}))
        self.assertTrue(declares_graph_compiler({"contract": "graph.v2"}))
        with self.assertRaises(UnsupportedConstraint):
            declares_graph_compiler({"requires": {"formula_compiler": "banana"}})


class ConstraintEvaluatorTest(unittest.TestCase):
    """The evaluator's own edges, where it can disagree with Masterminds.

    Each of these is a way a hand-written mirror silently returns the opposite
    answer to the Go it mirrors. They live here rather than in a comment
    because the divergence is invisible in the packs' real formulas, which all
    declare plain `">=2.0.0"` -- the guard would stay green through every one.
    """

    def test_a_prerelease_bound_is_refused_not_truncated(self) -> None:
        # Dropping `-alpha` makes `>1.0.0-alpha` exclude 1.0.0 and admit 2.0.0,
        # so the truncating version reports graph-v2. Masterminds orders
        # stable 1.0.0 ABOVE 1.0.0-alpha, admits it, and reports v1.
        with self.assertRaises(UnsupportedConstraint):
            satisfies(">1.0.0-alpha", (1, 0, 0))
        # Build metadata does not affect precedence and is accepted.
        self.assertTrue(satisfies(">=2.0.0+build.7", (2, 0, 0)))

    def test_an_unsupported_group_is_refused_even_when_an_earlier_one_answers(self) -> None:
        # `semver.NewConstraint` rejects the whole expression. An evaluator
        # that stops at the first satisfied group is strict only for the
        # candidate versions that happen to reach the bad group.
        with self.assertRaises(UnsupportedConstraint):
            satisfies("<=1.0.0 || banana", (1, 0, 0))
        self.assertTrue(satisfies(">=2.0.0 || >=3.0.0", (2, 0, 0)))

    def test_whitespace_between_comparator_and_version_is_accepted(self) -> None:
        # Masterminds accepts it, so refusing it would fail a valid pack.
        self.assertTrue(satisfies(">= 2.0.0", (2, 0, 0)))
        self.assertFalse(satisfies(">= 2.0.0", (1, 0, 0)))

    def test_accumulated_constraints_are_evaluated_one_at_a_time(self) -> None:
        # `declaresGraphCompilerRequirement` walks the constraint list and
        # returns true on the first that qualifies. The comma-joined
        # serialisation is conjunctive and reaches the opposite answer.
        self.assertTrue(declares_graph_compiler_from([">=2.0.0", "!=2.0.0"]))
        self.assertFalse(
            declares_graph_compiler({"requires": {"formula_compiler": ">=2.0.0, !=2.0.0"}}),
            "the joined form is the wrong thing to evaluate; if it starts "
            "agreeing, the assertion above stops distinguishing anything",
        )


if __name__ == "__main__":
    unittest.main()
