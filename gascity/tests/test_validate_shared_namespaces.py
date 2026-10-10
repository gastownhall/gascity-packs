from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "assets" / "scripts"))

import validate_build_artifact as build_artifact
import validate_shared_namespaces as namespaces


def ownership_table(rows: list[tuple[str, str, str, str]], header: str | None = None) -> str:
    lines = [
        "## Shared Namespaces",
        "",
        header or "| Namespace | Participants | Owner | Leaf-Only |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {namespace} | {participants} | {owner} | {leaf_only} |"
        for namespace, participants, owner, leaf_only in rows
    )
    return "\n".join(lines) + "\n"


def work_item_table(rows: list[tuple[str, str, str]]) -> str:
    lines = [
        "## Work Items",
        "",
        "| ID | Bead | Depends On |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item_id} | {bead} | {depends} |" for item_id, bead, depends in rows)
    return "\n".join(lines) + "\n\n"


def slice_table(rows: list[tuple[str, str, str]]) -> str:
    """The `ac-c2cc4j` work-item shape: a Bead column, no canonical triple."""
    lines = [
        "## Work Items",
        "",
        "| Slice | Bead | Provider |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item_id} | `{bead}` | {provider} |" for item_id, bead, provider in rows)
    return "\n".join(lines) + "\n\n"


FOUR_ITEMS = [
    ("WI-1", "gc-aaa111", "-"),
    ("WI-2", "gc-bbb222", "WI-1"),
    ("WI-3", "gc-ccc333", "WI-1"),
    ("WI-4", "gc-ddd444", "WI-1"),
]


class SharedNamespaceCheckTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def write_artifact(self, body: str) -> pathlib.Path:
        path = self.root / "decomposition.md"
        path.write_text(body, encoding="utf-8")
        return path

    def run_main(self, body: str) -> tuple[int, str, str]:
        path = self.write_artifact(body)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = namespaces.main(["--path", str(path)])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_skips_artifact_without_work_item_table(self) -> None:
        status, stdout, stderr = self.run_main("## Work Items\n\nProse only, no table.\n")
        self.assertEqual(status, 0)
        self.assertIn("no work-item table with a Bead column", stdout)
        self.assertEqual(stderr, "")

    def test_missing_declaration_with_several_work_items_fails(self) -> None:
        status, _, stderr = self.run_main(work_item_table(FOUR_ITEMS))
        self.assertEqual(status, 1)
        self.assertIn("no shared-namespace ownership declaration", stderr)
        self.assertIn("declares 4 work items", stderr)
        self.assertIn("add a Shared Namespaces table", stderr)
        self.assertIn("| (none) | - | - | - |", stderr)

    def test_missing_declaration_with_one_work_item_passes(self) -> None:
        status, stdout, stderr = self.run_main(work_item_table(FOUR_ITEMS[:1]))
        self.assertEqual(status, 0, stderr)
        self.assertIn("a single slice cannot split a namespace", stdout)

    def test_missing_declaration_with_non_canonical_table_passes(self) -> None:
        # PR-1 option 1: only the canonical ID/Bead/Depends On shape, whose
        # producing prompts also carry the ownership contract, arms the failure.
        body = slice_table([("S1", "ac-111aaa", "fal"), ("S2", "ac-222bbb", "fal")])
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn("is not the canonical ID/Bead/Depends On shape", stdout)
        self.assertIn("Slice | Bead | Provider", stdout)

    def test_earlier_bead_table_does_not_suppress_the_gate(self) -> None:
        # RQ-1: a per-slice summary table above the canonical Work Items table
        # must not switch the missing-declaration failure off. 6 of 110 live
        # artifacts carry two or more Bead-column tables, so returning at the
        # first one disarmed the check's headline guarantee for that shape.
        body = slice_table(
            [("S1", "ac-111aaa", "fal"), ("S2", "ac-222bbb", "fal")]
        ) + work_item_table(FOUR_ITEMS)
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("no shared-namespace ownership declaration", stderr)
        self.assertIn("declares 4 work items", stderr)

    def test_canonical_table_wins_over_an_earlier_bead_table(self) -> None:
        # The canonical table also supplies the ID vocabulary once it is found,
        # so a declaration naming its ids cross-references cleanly.
        body = (
            slice_table([("S1", "ac-111aaa", "fal"), ("S2", "ac-222bbb", "fal")])
            + work_item_table(FOUR_ITEMS)
            + ownership_table([("PRICING.kie", "WI-1, WI-2", "WI-1", "WI-2")])
        )
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn("shared namespaces valid: 1 namespace, 2 participants", stdout)

    def test_first_bead_table_wins_when_none_is_canonical(self) -> None:
        # Unchanged behaviour: with no canonical table anywhere, the first
        # Bead-column table still supplies the ids and the skip message label.
        body = slice_table(
            [("S1", "ac-111aaa", "fal"), ("S2", "ac-222bbb", "fal")]
        ) + (
            "## Rollout\n\n"
            "| Phase | Bead | Owner |\n"
            "| --- | --- | --- |\n"
            "| P1 | `ac-333ccc` | team |\n"
        )
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn("is not the canonical ID/Bead/Depends On shape", stdout)
        self.assertIn("Slice | Bead | Provider", stdout)

    def test_sentinel_row_passes(self) -> None:
        body = work_item_table(FOUR_ITEMS) + ownership_table([("(none)", "-", "-", "-")])
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn('explicit "(none)" sentinel', stdout)

    def test_sentinel_beside_real_rows_fails(self) -> None:
        body = work_item_table(FOUR_ITEMS) + ownership_table(
            [
                ("(none)", "-", "-", "-"),
                ("`fal.geminiOmniFlash`", "WI-1, WI-2", "WI-1", "WI-2"),
            ]
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("must be the only row in the ownership table", stderr)

    def test_zero_owners_fails_naming_participants(self) -> None:
        body = work_item_table(FOUR_ITEMS) + ownership_table(
            [("`fal.geminiOmniFlash`", "WI-1, WI-2, WI-3, WI-4", "-", "-")]
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("'fal.geminiOmniFlash' names no owner", stderr)
        self.assertIn("WI-1, WI-2, WI-3, WI-4", stderr)
        self.assertIn("put the work item that creates the shared scaffold in the Owner column", stderr)
        # One defect, one line: a row with no owner must not also emit a
        # "neither owner nor leaf-only" line for each of its participants.
        self.assertEqual(len(stderr.strip().splitlines()), 1, stderr)

    def test_two_owners_fails_naming_both(self) -> None:
        body = work_item_table(FOUR_ITEMS) + ownership_table(
            [("PRICING.kie", "WI-1, WI-2, WI-3", "WI-1, WI-3", "WI-2")]
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("names 2 owners (WI-1, WI-3)", stderr)
        self.assertIn("move WI-3 to Leaf-Only", stderr)

    def test_participant_that_is_neither_owner_nor_leaf_only_fails(self) -> None:
        body = work_item_table(FOUR_ITEMS) + ownership_table(
            [("PRICING.kie", "WI-1, WI-2, WI-3", "WI-1", "WI-3")]
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("participant WI-2 is neither owner nor leaf-only", stderr)
        self.assertIn("add WI-2 to Leaf-Only, or make it the Owner", stderr)

    def test_owner_listed_under_leaf_only_fails(self) -> None:
        body = work_item_table(FOUR_ITEMS) + ownership_table(
            [("PRICING.kie", "WI-1, WI-2", "WI-1", "WI-1, WI-2")]
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("owner WI-1 is also listed under Leaf-Only", stderr)

    def test_single_participant_that_is_the_owner_passes(self) -> None:
        # BR-05: a family that did not actually split needs no sibling contract.
        body = work_item_table(FOUR_ITEMS) + ownership_table(
            [("`fal.minimaxH3`", "WI-2", "WI-2", "-")]
        )
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn("shared namespaces valid: 1 namespace, 1 participant", stdout)

    def test_unknown_work_item_fails(self) -> None:
        body = work_item_table(FOUR_ITEMS) + ownership_table(
            [("PRICING.kie", "WI-9, WI-2", "WI-9", "WI-2")]
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("references unknown work item 'WI-9'", stderr)
        self.assertIn("declared work items are WI-1, WI-2, WI-3, WI-4", stderr)

    def test_duplicate_namespace_rows_fail(self) -> None:
        body = work_item_table(FOUR_ITEMS) + ownership_table(
            [
                ("`fal.geminiOmniFlash`", "WI-1, WI-2", "WI-1", "WI-2"),
                ("fal.geminiOmniFlash", "WI-3, WI-4", "WI-3", "WI-4"),
            ]
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("is declared in 2 rows", stderr)
        self.assertIn("merge them into one row", stderr)

    def test_status_column_is_a_dedicated_error(self) -> None:
        body = work_item_table(FOUR_ITEMS) + (
            "## Shared Namespaces\n\n"
            "| Namespace | Owner | Status |\n"
            "| --- | --- | --- |\n"
            "| PRICING.kie | WI-1 | covered |\n"
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("must not carry a Status column", stderr)
        self.assertIn("coverage matrix", stderr)

    def test_id_status_ownership_table_is_a_dedicated_error(self) -> None:
        # RQ-2 / AC-08 / BR-12: the shape the requirement actually names. It
        # carries no Owner column, so gating the Status check on Namespace+Owner
        # let it fall through to the generic missing-declaration message -- or,
        # beside a valid ownership table, past the check entirely and into the
        # coverage matrix.
        table = (
            "## Shared Namespaces\n\n"
            "| ID | Namespace | Status |\n"
            "| --- | --- | --- |\n"
            "| WI-1 | PRICING.kie | covered |\n"
        )
        status, _, stderr = self.run_main(work_item_table(FOUR_ITEMS) + table)
        self.assertEqual(status, 1)
        self.assertIn("must not carry a Status column", stderr)
        self.assertIn("coverage matrix", stderr)
        self.assertIn("fix: drop the Status column", stderr)

        # ...and it is still caught when a valid declaration sits above it.
        beside_valid = (
            work_item_table(FOUR_ITEMS)
            + ownership_table([("PRICING.kie", "WI-1, WI-2", "WI-1", "WI-2")])
            + "\n"
            + table
        )
        # The shape corrupts coverage: the base validator reads it as one.
        self.assertEqual(
            build_artifact.parse_markdown_coverage(beside_valid), {"WI-1": "covered"}
        )
        status, _, stderr = self.run_main(beside_valid)
        self.assertEqual(status, 1)
        self.assertIn("must not carry a Status column", stderr)

    def test_coverage_matrix_without_a_namespace_column_is_left_alone(self) -> None:
        # The other half of AC-08: a real ID/Status coverage matrix carries no
        # Namespace column and must stay this check's business to ignore.
        body = (
            "## Coverage\n\n"
            "| ID | Status |\n"
            "| --- | --- |\n"
            "| REQ-001 | covered |\n\n"
            + work_item_table(FOUR_ITEMS)
            + ownership_table([("PRICING.kie", "WI-1, WI-2", "WI-1", "WI-2")])
        )
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn("shared namespaces valid", stdout)

    def test_ownership_table_does_not_pollute_coverage_matrix(self) -> None:
        body = (
            "## Coverage\n\n"
            "| ID | Status |\n"
            "| --- | --- |\n"
            "| REQ-001 | covered |\n\n"
            + work_item_table(FOUR_ITEMS)
            + ownership_table([("PRICING.kie", "WI-1, WI-2", "WI-1", "WI-2")])
        )
        coverage = build_artifact.parse_markdown_coverage(body)
        self.assertEqual(coverage, {"REQ-001": "covered"})
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)

    def test_backtest_ac_c2cc4j_shape_fails(self) -> None:
        # BR-19: the four `google/gemini-omni-flash` slices of the ac-c2cc4j
        # decomposition, declared truthfully with no owner named.
        body = (
            slice_table(
                [
                    ("S16", "ac-6811ea", "fal"),
                    ("S17", "ac-akefx2", "fal"),
                    ("S18", "ac-avlwzd", "fal"),
                    ("S19", "ac-u2qf6h", "fal"),
                ]
            )
            + work_item_table(
                [
                    ("S16", "ac-6811ea", "-"),
                    ("S17", "ac-akefx2", "S16"),
                    ("S18", "ac-avlwzd", "S16"),
                    ("S19", "ac-u2qf6h", "S16"),
                ]
            )
            + ownership_table([("`fal.geminiOmniFlash`", "S16, S17, S18, S19", "-", "-")])
        )
        status, _, stderr = self.run_main(body)
        self.assertEqual(status, 1)
        self.assertIn("names no owner among participants S16, S17, S18, S19", stderr)

    def test_backtest_ac_j4z1t1_shape_passes(self) -> None:
        # BR-20: the hand-written ownership prose of the ac-j4z1t1
        # decomposition, rendered as the declared table.
        body = (
            "## Work Items\n\n"
            "| Unit | Bead | Deliverable | Gate |\n"
            "| --- | --- | --- | --- |\n"
            "| U1 | `ac-uc3kzk` | namespace-shape detector | preflight |\n"
            "| U2+U3 | `ac-4hs4sw` | comparison script and contract | ci:local |\n\n"
            + ownership_table(
                [
                    ("`CLAUDE.md`", "U1, U2+U3", "U1", "U2+U3"),
                    ("`scripts/lib/namespace-shape.mjs`", "U1, U2+U3", "U1", "U2+U3"),
                ]
            )
        )
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn("shared namespaces valid: 2 namespaces, 2 participants", stdout)

    def test_alternate_id_column_resolves_cross_reference(self) -> None:
        body = slice_table(
            [("S16", "ac-6811ea", "fal"), ("S17", "ac-akefx2", "fal")]
        ) + ownership_table([("`fal.geminiOmniFlash`", "S16, S17", "S16", "S17")])
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn("shared namespaces valid: 1 namespace, 2 participants", stdout)

        unknown = slice_table(
            [("S16", "ac-6811ea", "fal"), ("S17", "ac-akefx2", "fal")]
        ) + ownership_table([("`fal.geminiOmniFlash`", "S16, S99", "S16", "S99")])
        status, _, stderr = self.run_main(unknown)
        self.assertEqual(status, 1)
        self.assertIn("references unknown work item 'S99'", stderr)
        self.assertIn("declared work items are S16, S17", stderr)

    def test_header_normalization_accepts_case_and_separator_variants(self) -> None:
        rows = [("PRICING.kie", "WI-1, WI-2", "WI-1", "WI-2")]
        canonical = self.run_main(work_item_table(FOUR_ITEMS) + ownership_table(rows))
        shouty = self.run_main(
            work_item_table(FOUR_ITEMS)
            + ownership_table(rows, header="| NAMESPACE | Participants | OWNER | LEAF_ONLY |")
        )
        spaced = self.run_main(
            work_item_table(FOUR_ITEMS)
            + ownership_table(rows, header="|  namespace  | participants | owner | leaf only |")
        )
        self.assertEqual(canonical, shouty)
        self.assertEqual(canonical, spaced)
        self.assertEqual(canonical[0], 0, canonical[2])

    def test_three_column_declaration_infers_participants(self) -> None:
        body = work_item_table(FOUR_ITEMS) + (
            "## Shared Namespaces\n\n"
            "| Namespace | Owner | Leaf-Only |\n"
            "| --- | --- | --- |\n"
            "| PRICING.kie | WI-1 | WI-2, WI-3 |\n"
        )
        status, stdout, stderr = self.run_main(body)
        self.assertEqual(status, 0, stderr)
        self.assertIn("shared namespaces valid: 1 namespace, 3 participants", stdout)

    def test_check_is_hermetic(self) -> None:
        source = (
            pathlib.Path(namespaces.__file__).resolve().read_text(encoding="utf-8")
        )
        for forbidden in ("import subprocess", "import requests", "import urllib"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
