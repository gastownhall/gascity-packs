#!/usr/bin/env python3
"""Verify shared-namespace ownership in a decomposition artifact.

When a decomposition splits one upstream namespace across several work items --
one provider family, one config block, one pinned counter -- exactly one of
those work items must create the shared scaffold and every sibling must add
leaves to it only. Left undeclared, four independently-green branches each
create their own copy and the collision surfaces at merge time, long after the
cheap moment to fix it.

The declaration lives in the artifact body (conventionally under or after the
Work Items section) and is any Markdown table whose header row includes both a
Namespace column and an Owner column:

| Namespace | Participants | Owner | Leaf-Only |
| --- | --- | --- | --- |
| `fal.geminiOmniFlash` | WI-1, WI-2, WI-3 | WI-1 | WI-2, WI-3 |

Cells are comma-separated work-item IDs drawn from the first column of the
artifact's work-item table; `-`, `none` or an empty cell is the empty set.
Column order is not significant and headers are matched after normalization,
so `Leaf-Only`, `leaf only` and `LEAF_ONLY` are one column. Namespaces are
opaque strings compared exactly: no case folding, no path normalization, no
splitting on dots, because the namespaces this guards (`fal.geminiOmniFlash`,
`PRICING.kie`) are case-significant dot paths. Two rows that are equal after
cleaning are a duplicate-row error rather than a silent merge.

The table must not carry a Status column: the build-artifact validator reads
any table with ID and Status columns as the coverage matrix, so a Status
column here would silently corrupt coverage rather than declare ownership.

Absence is dispositive, never silent. A single `| (none) | - | - | - |` row is
the cheap explicit discharge. With no ownership table at all, the check fails
only when the artifact carries the canonical `ID | Bead | Depends On`
work-item table with two or more rows -- the shape whose producing prompts
also carry this ownership contract. Every other artifact shape passes with a
line naming which branch it took.

This check verifies a declaration's *internal consistency*; it cannot detect
*undeclared* sharing. A decomposer that never noticed a namespace was shared
would emit the `(none)` sentinel and pass -- exactly what would have happened
to the `ac-c2cc4j` run whose four `geminiOmniFlash` slices motivated this
check, where the namespace is named nowhere in the artifact. Detecting
undeclared sharing stays the namespace-shape detector's job.

Exit status: 0 when the declaration is absent-and-permitted or fully
consistent, 1 with machine-readable `shared-namespace-check:` lines on stderr
otherwise. Parse-only: no `gc` invocation, no child process, no network.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from validate_build_artifact import clean_table_cell, is_separator_row, split_table_row

CHECK_PREFIX = "shared-namespace-check"
# A Namespace cell cleaning to one of these declares "nothing is shared".
SENTINEL_NAMESPACES = {"(none)", "none", "-"}
# The work-item table shape mandated by the decompose prompts that also carry
# the ownership contract; only this shape arms the missing-declaration failure.
CANONICAL_WORK_ITEM_HEADER = ("id", "bead", "depends on")


class NamespaceCheckError(Exception):
    pass


@dataclass(frozen=True)
class NamespaceRow:
    namespace: str
    participants: tuple[str, ...]
    owners: tuple[str, ...]
    leaf_only: tuple[str, ...]


def normalize_header_cell(cell: str) -> str:
    return " ".join(clean_table_cell(cell).lower().replace("_", " ").replace("-", " ").split())


def parse_id_list(raw: str) -> tuple[str, ...]:
    cleaned = clean_table_cell(raw)
    if cleaned in {"", "-", "none"}:
        return ()
    parts = [clean_table_cell(part) for part in cleaned.split(",")]
    return tuple(part for part in parts if part and part != "-")


def _dedupe(ids: tuple[str, ...]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in ids:
        seen.setdefault(item, None)
    return tuple(seen)


def parse_ownership_tables(body: str) -> list[NamespaceRow]:
    rows: list[NamespaceRow] = []
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        cells = split_table_row(lines[index])
        header = [normalize_header_cell(cell) for cell in cells]
        if not header or "namespace" not in header or "owner" not in header:
            index += 1
            continue
        if "status" in header:
            raise NamespaceCheckError(
                "ownership table must not carry a Status column; "
                "the build-artifact validator reads any ID/Status table as the coverage matrix"
            )
        namespace_index = header.index("namespace")
        owner_index = header.index("owner")
        participants_index = header.index("participants") if "participants" in header else -1
        leaf_index = header.index("leaf only") if "leaf only" in header else -1
        widest = max(namespace_index, owner_index, participants_index, leaf_index)
        index += 1
        if index < len(lines) and is_separator_row(lines[index]):
            index += 1
        while index < len(lines):
            row = split_table_row(lines[index])
            if not row or len(row) <= widest:
                break
            namespace = clean_table_cell(row[namespace_index])
            if namespace:
                owners = parse_id_list(row[owner_index])
                leaf_only = parse_id_list(row[leaf_index]) if leaf_index >= 0 else ()
                # A three-column declaration without an explicit Participants
                # column means the participants are exactly the owner plus the
                # leaf-only siblings, which is the requirements' straw-man shape.
                participants = (
                    parse_id_list(row[participants_index])
                    if participants_index >= 0
                    else _dedupe(owners + leaf_only)
                )
                rows.append(
                    NamespaceRow(
                        namespace=namespace,
                        participants=participants,
                        owners=owners,
                        leaf_only=leaf_only,
                    )
                )
            index += 1
    return rows


def parse_work_items(body: str) -> tuple[tuple[str, ...], str, bool]:
    """Return (work-item ids, header label, canonical-shape flag).

    The work-item table is the first body table whose normalized header carries
    a Bead column; its first column is the ID column. That covers both real
    shapes -- the canonical `ID | Bead | Depends On` and wider variants such as
    `Slice | Bead | Provider | Deliverable | Floor`.
    """
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        cells = split_table_row(lines[index])
        header = [normalize_header_cell(cell) for cell in cells]
        if not header or "bead" not in header:
            index += 1
            continue
        label = " | ".join(cells)
        canonical = all(column in header for column in CANONICAL_WORK_ITEM_HEADER)
        ids: list[str] = []
        index += 1
        if index < len(lines) and is_separator_row(lines[index]):
            index += 1
        while index < len(lines):
            row = split_table_row(lines[index])
            if not row or len(row) < len(header):
                break
            item_id = clean_table_cell(row[0])
            if item_id:
                ids.append(item_id)
            index += 1
        return tuple(_dedupe(tuple(ids))), label, canonical
    return (), "", False


def validate_rows(
    rows: list[NamespaceRow],
    work_item_ids: tuple[str, ...],
    cross_ref: bool,
) -> list[str]:
    errors: list[str] = []
    declared = set(work_item_ids)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.namespace] = counts.get(row.namespace, 0) + 1
    reported_duplicates: set[str] = set()
    for row in rows:
        if counts[row.namespace] > 1:
            if row.namespace not in reported_duplicates:
                reported_duplicates.add(row.namespace)
                errors.append(
                    f"namespace {row.namespace!r} is declared in {counts[row.namespace]} rows; "
                    "fix: merge them into one row"
                )
            continue
        if cross_ref:
            for item_id in _dedupe(row.participants + row.owners + row.leaf_only):
                if item_id not in declared:
                    errors.append(
                        f"namespace {row.namespace!r} references unknown work item {item_id!r}; "
                        f"declared work items are {', '.join(work_item_ids)}; "
                        "fix: correct the id or add the work item to the Work Items table"
                    )
        if not row.owners:
            participants = ", ".join(row.participants) if row.participants else "(none listed)"
            errors.append(
                f"namespace {row.namespace!r} names no owner among participants {participants}; "
                "fix: put the work item that creates the shared scaffold in the Owner column "
                "and list the rest under Leaf-Only"
            )
        elif len(row.owners) > 1:
            errors.append(
                f"namespace {row.namespace!r} names {len(row.owners)} owners "
                f"({', '.join(row.owners)}); exactly one work item may own a shared namespace; "
                f"fix: keep the item that creates the scaffold and move "
                f"{', '.join(row.owners[1:])} to Leaf-Only"
            )
        owners = set(row.owners)
        leaves = set(row.leaf_only)
        for participant in row.participants:
            # A row that names no owner already lists every participant and the
            # repair that covers them; re-reporting each one would bury the one
            # real defect under n lines of the same finding.
            if not owners:
                break
            if participant not in owners and participant not in leaves:
                errors.append(
                    f"namespace {row.namespace!r} participant {participant} is neither owner nor "
                    f"leaf-only; fix: add {participant} to Leaf-Only, or make it the Owner"
                )
        for owner in row.owners:
            if owner in leaves:
                errors.append(
                    f"namespace {row.namespace!r} owner {owner} is also listed under Leaf-Only; "
                    f"fix: remove {owner} from Leaf-Only"
                )
    return errors


def check_artifact(path: Path) -> tuple[int, str]:
    body = path.read_text(encoding="utf-8")
    rows = parse_ownership_tables(body)
    work_item_ids, work_item_label, canonical = parse_work_items(body)
    if not rows:
        if canonical and len(work_item_ids) > 1:
            print(
                f"{CHECK_PREFIX}: no shared-namespace ownership declaration; the Work Items table "
                f"(ID/Bead/Depends On) declares {len(work_item_ids)} work items; fix: add a Shared "
                'Namespaces table, or a single "| (none) | - | - | - |" row if nothing is shared',
                file=sys.stderr,
            )
            return 1, ""
        if canonical:
            return 0, (
                "shared namespace check: "
                f"{len(work_item_ids)} work item declared; a single slice cannot split a namespace"
            )
        if work_item_label:
            return 0, (
                f"shared namespace check: work-item table ({work_item_label}) is not the canonical "
                "ID/Bead/Depends On shape; skipping ownership verification"
            )
        return 0, (
            "shared namespace check: no work-item table with a Bead column; "
            "skipping ownership verification"
        )
    sentinels = [row for row in rows if row.namespace in SENTINEL_NAMESPACES]
    if sentinels:
        if len(rows) > 1:
            print(
                f'{CHECK_PREFIX}: the "(none)" sentinel must be the only row in the ownership '
                "table; fix: remove the sentinel or the other rows",
                file=sys.stderr,
            )
            return 1, ""
        return 0, 'shared namespace check: explicit "(none)" sentinel; nothing shared'
    cross_ref = bool(work_item_ids)
    errors = validate_rows(rows, work_item_ids, cross_ref)
    if errors:
        for error in errors:
            print(f"{CHECK_PREFIX}: {error}", file=sys.stderr)
        return 1, ""
    participants = _dedupe(
        tuple(item for row in rows for item in row.participants + row.owners + row.leaf_only)
    )
    namespace_word = "namespace" if len(rows) == 1 else "namespaces"
    participant_word = "participant" if len(participants) == 1 else "participants"
    message = (
        f"shared namespaces valid: {len(rows)} {namespace_word}, "
        f"{len(participants)} {participant_word} (declaration only)"
    )
    if not cross_ref:
        message += "; work-item cross-reference skipped: no Bead-column table"
    return 0, message


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify decomposition shared-namespace ownership")
    parser.add_argument("--path", required=True, type=Path, help="Decomposition artifact markdown path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        status, message = check_artifact(args.path)
    except (OSError, UnicodeDecodeError, NamespaceCheckError) as exc:
        print(f"{CHECK_PREFIX}: {exc}", file=sys.stderr)
        return 1
    if message:
        print(message)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
