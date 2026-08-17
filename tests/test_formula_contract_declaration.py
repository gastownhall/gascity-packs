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

The replacement floor is counted by **parsing** each formula and evaluating the
declared constraint the way the compiler does, not by grepping for the text
`formula_compiler =`. A text match counts the key inside a comment, inside a
formula's prose description, and when its value is `""` or `"banana"` — so the
floor could hold at 87 while none of the 87 actually opted into the v2 compiler.
The rule itself lives in `scripts/formula_compiler_requirement.py`.
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
)

DEPRECATED = re.compile(r'^\s*contract\s*=\s*"graph\.v2"', re.MULTILINE)

# Below this, the enumeration has broken rather than the repo having shrunk.
MINIMUM_FORMULAS = 50

# 87 formulas declare a formula_compiler requirement that actually selects the
# v2 compiler, as of 2026-08-17. Refute with:
#   grep -rl 'formula_compiler' */formulas | wc -l
MINIMUM_DECLARING = 87


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
        `gc.formula_contract` bead stamp with no error anywhere. This floor is
        the cheapest guard against that regression: it cannot rise by accident,
        and a drop means a declaration went away rather than being converted.
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
        self.assertGreaterEqual(
            len(declaring),
            MINIMUM_DECLARING,
            f"only {len(declaring)} formulas declare a formula_compiler "
            f"requirement that selects the v2 compiler, down from the floor of "
            f"{MINIMUM_DECLARING}; a declaration was removed rather than "
            "converted. Raise this floor deliberately when formulas are added, "
            "never to make it pass.",
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


if __name__ == "__main__":
    unittest.main()
