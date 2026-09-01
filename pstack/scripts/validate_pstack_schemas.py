#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterator

try:
    import yaml
except ImportError:
    yaml = None

PACK_ROOT = Path(__file__).resolve().parents[1]
GAS_CITY_VALIDATOR = PACK_ROOT.parent / "gascity/assets/scripts/validate_build_artifact.py"
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
FORBIDDEN_FRONT_LEAVES = {"owner", "stage-owner", "stage_owner", "persona", "role"}


def load_gascity_validator():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gc_validate_build_artifact", GAS_CITY_VALIDATOR)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load {GAS_CITY_VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise ValueError("PyYAML is required. Run: uv run --with pyyaml python pstack/scripts/validate_pstack_schemas.py")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: schema must be a mapping")
    return data


def require_string_list(path: Path, data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{path}: {key} must be a non-empty list of non-empty strings")
    return value


def validate_schema_file(path: Path) -> None:
    data = load_yaml(path)
    expected_id = f"pstack.{path.stem}"
    if data.get("schema_id") != expected_id:
        raise ValueError(f"{path}: schema_id must be {expected_id!r}")
    front = data.get("required_front_matter")
    if not isinstance(front, list):
        raise ValueError(f"{path}: required_front_matter must be a list")
    for item in FRONT:
        if item not in front:
            raise ValueError(f"{path}: required_front_matter missing {item}")
    for field in front:
        leaf = str(field).split(".")[-1].lower()
        if leaf in FORBIDDEN_FRONT_LEAVES:
            raise ValueError(f"{path}: required_front_matter must not include {field!r}")
    coverage = require_string_list(path, data, "coverage_statuses")
    for status in COVERAGE:
        if status not in coverage:
            raise ValueError(f"{path}: coverage_statuses missing {status}")
    require_string_list(path, data, "required_fields")
    require_string_list(path, data, "evidence_fields")
    require_string_list(path, data, "allowed_statuses")
    enforcements = data.get("allowed_enforcements")
    if enforcements is not None:
        if (
            not isinstance(enforcements, list)
            or not enforcements
            or not all(isinstance(item, str) and item.strip() for item in enforcements)
            or len(set(enforcements)) != len(enforcements)
        ):
            raise ValueError(f"{path}: allowed_enforcements must be unique non-empty strings")
    gascity = load_gascity_validator()
    try:
        gascity.validate_schema_definition(data)
    except gascity.ValidationError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def iter_formula_nodes(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for child in node.get("children") or []:
            yield from iter_formula_nodes(child)
    elif isinstance(node, list):
        for item in node:
            yield from iter_formula_nodes(item)


def formula_schema_ids(step: dict[str, Any]) -> Iterator[str]:
    metadata = step.get("metadata") or {}
    for key in ("pstack.artifact_schema", "gc.build.artifact_schema"):
        value = metadata.get(key)
        if isinstance(value, str) and value.startswith("pstack."):
            yield value.strip()


def validate_formula_schema_refs(formulas_dir: Path, schema_ids: set[str]) -> None:
    import tomllib

    for path in sorted(formulas_dir.glob("*.formula.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        nodes = list(iter_formula_nodes(data.get("steps") or []))
        nodes.extend(iter_formula_nodes(data.get("template") or []))
        for step in nodes:
            for schema in formula_schema_ids(step):
                if schema not in schema_ids:
                    raise ValueError(f"{path}: unknown pstack schema {schema!r}")


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
