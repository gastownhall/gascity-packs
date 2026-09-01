#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

PACK_ROOT = Path(__file__).resolve().parents[1]
COVERAGE = (
    "covered",
    "not_applicable",
    "deferred",
    "blocked",
    "out_of_scope",
    "superseded",
)
FRONT = (
    "schema",
    "workflow.id",
    "workflow.formula",
    "producer.formula",
    "producer.stage",
    "status",
    "producer.attempt",
    "trace",
)


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise SystemExit("PyYAML is required")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: schema must be a mapping")
    return data


def validate_schema_file(path: Path) -> None:
    data = load_yaml(path)
    expected_id = f"pstack.{path.stem}"
    if data.get("schema_id") != expected_id:
        raise ValueError(f"{path}: schema_id must be {expected_id!r}")
    front = data.get("required_front_matter")
    if not isinstance(front, list) or "producer.attempt" not in front:
        raise ValueError(f"{path}: required_front_matter must include producer.attempt")
    for item in FRONT:
        if item not in front:
            raise ValueError(f"{path}: required_front_matter missing {item}")
    coverage = data.get("coverage_statuses")
    if not isinstance(coverage, list):
        raise ValueError(f"{path}: coverage_statuses must be a list")
    for status in COVERAGE:
        if status not in coverage:
            raise ValueError(f"{path}: coverage_statuses missing {status}")
    fields = data.get("required_fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError(f"{path}: required_fields must be a non-empty list")
    evidence = data.get("evidence_fields")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{path}: evidence_fields must be a non-empty list")
    statuses = data.get("allowed_statuses")
    if not isinstance(statuses, list) or not statuses:
        raise ValueError(f"{path}: allowed_statuses must be a non-empty list")


def validate_formula_schema_refs(formulas_dir: Path, schema_ids: set[str]) -> None:
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore
    for path in sorted(formulas_dir.glob("*.formula.toml")):
        text = path.read_text(encoding="utf-8")
        data = tomllib.loads(text)
        for step in data.get("steps", []):
            schema = (step.get("metadata") or {}).get("pstack.artifact_schema")
            if not schema or not str(schema).startswith("pstack."):
                continue
            if schema not in schema_ids:
                raise ValueError(f"{path}: unknown pstack.artifact_schema {schema!r}")


def validate_all(schema_dir: Path, *, formulas_dir: Path | None = None) -> list[Path]:
    paths = sorted(schema_dir.glob("*.yaml"))
    if not paths:
        raise ValueError(f"{schema_dir}: no schema yaml files")
    ids: set[str] = set()
    for path in paths:
        validate_schema_file(path)
        ids.add(f"pstack.{path.stem}")
    if formulas_dir is not None:
        validate_formula_schema_refs(formulas_dir, ids)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schemas", type=Path, default=PACK_ROOT / "schemas")
    parser.add_argument("--formulas", type=Path, default=PACK_ROOT / "formulas")
    args = parser.parse_args()
    try:
        paths = validate_all(args.schemas, formulas_dir=args.formulas)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    for path in paths:
        print(f"ok {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
