from __future__ import annotations

import pathlib
import tomllib
import unittest


PACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
FORMULAS = PACK_ROOT / "formulas"

# Bare `issue` is a reserved formulas-v2 alias auto-bound to the routed work
# bead. A formula slung as a routed molecule must not declare its own `issue`
# var or the routed value clobbers it. mol-pr-from-issue is the one such
# formula in this pack; it renames its GitHub-issue input to `issue_number`.
RESERVED_VAR_ALIAS = "issue"


class MolPrFromIssueVarBindingTests(unittest.TestCase):
    """The gate-4 port of mol-pr-from-issue into pr-pipeline (gpk-b3ll)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.path = FORMULAS / "mol-pr-from-issue.formula.toml"
        cls.text = cls.path.read_text(encoding="utf-8")
        cls.data = tomllib.loads(cls.text)

    def test_formula_is_present_and_well_formed(self) -> None:
        self.assertTrue(self.path.exists(), "mol-pr-from-issue must live in the pr-pipeline pack")
        self.assertEqual(self.data["formula"], "mol-pr-from-issue")
        self.assertEqual(self.data["contract"], "graph.v2")

    def test_github_issue_input_is_named_issue_number(self) -> None:
        variables = self.data.get("vars", {})
        self.assertIn("issue_number", variables, "GitHub-issue input must be bound as issue_number")
        self.assertTrue(variables["issue_number"]["required"])

    def test_reserved_issue_alias_is_not_declared(self) -> None:
        variables = self.data.get("vars", {})
        self.assertNotIn(
            RESERVED_VAR_ALIAS,
            variables,
            "mol-pr-from-issue must not declare the reserved `issue` var — it is "
            "slung as a routed molecule and the alias would clobber the input",
        )

    def test_no_bare_issue_template_token_remains(self) -> None:
        # The rename must be complete: every {{issue}} became {{issue_number}}.
        self.assertNotIn("{{issue}}", self.text)
        self.assertIn("{{issue_number}}", self.text)

    def test_contract_doc_documents_issue_number(self) -> None:
        # The `## Contract` / `## Variables` prose drives how callers sling it.
        self.assertIn("--var issue_number=<number>", self.text)
        self.assertNotIn("--var issue=<number>", self.text)

    def test_companion_vars_survived_the_port(self) -> None:
        variables = self.data.get("vars", {})
        self.assertIn("skip_open_pr", variables)
        self.assertIn("auto_push", variables)


if __name__ == "__main__":
    unittest.main()
