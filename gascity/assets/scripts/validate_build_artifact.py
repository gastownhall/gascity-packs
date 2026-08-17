#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

def _site_packages_roots() -> list[str]:
    import site

    roots: list[str] = []
    for candidate in [site.getusersitepackages(), *site.getsitepackages()]:
        if candidate and candidate not in roots:
            roots.append(candidate)
    return roots


def _import_yaml() -> tuple[Any, list[str]]:
    """Import PyYAML, retrying with site-packages roots that launchers can
    strip from sys.path (e.g. PYTHONNOUSERSITE=1 hiding a user-site install).
    Returns the module (or None) and the roots appended before the retry."""
    try:
        import yaml as module
    except ImportError:
        pass
    else:
        return module, []
    roots = _site_packages_roots()
    for root in roots:
        if root not in sys.path:
            sys.path.append(root)
    try:
        import yaml as module
    except ImportError:
        return None, roots
    return module, roots


yaml, YAML_SITE_ROOTS_CHECKED = _import_yaml()


FRONT_MATTER_RE = re.compile(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)(?P<body>.*)\Z", re.DOTALL)
FORBIDDEN_REQUIRED_FIELD_NAMES = {"owner", "stage-owner", "stage_owner", "persona", "role"}

# Embedded copies of gascity/schemas/build/*.yaml so this script stays
# self-contained when consumers vendor only the scripts/ subtree (no sibling
# schemas/ directory at any depth). Those YAML files remain the source of
# truth; test_validators.py fails if the two drift apart.
_BUILD_REQUIRED_FRONT_MATTER = [
    "schema",
    "workflow.id",
    "workflow.formula",
    "methodology.pack",
    "methodology.name",
    "producer.formula",
    "producer.stage",
    "producer.attempt",
    "status",
    "trace",
]
_BUILD_COVERAGE_STATUSES = [
    "covered",
    "not_applicable",
    "deferred",
    "blocked",
    "out_of_scope",
    "superseded",
]
_REVIEWED_STATUSES = ["draft", "questions", "approved", "changes_required", "blocked", "superseded"]
_REPORT_STATUSES = ["draft", "approved", "blocked", "superseded"]

EMBEDDED_SCHEMAS: dict[str, dict[str, Any]] = {
    "gc.build.requirements.v1": {
        "schema_id": "gc.build.requirements.v1",
        "artifact": "requirements",
        "allowed_statuses": _REVIEWED_STATUSES,
        "required_front_matter": _BUILD_REQUIRED_FRONT_MATTER,
        "coverage_statuses": _BUILD_COVERAGE_STATUSES,
        "required_sections": [
            "Problem Statement",
            "W6H",
            "User Stories",
            "Technical Stories",
            "Behavior Requirements",
            "Example Mapping",
            "Acceptance Criteria",
            "Out Of Scope",
            "Open Questions",
        ],
    },
    "gc.build.plan.v1": {
        "schema_id": "gc.build.plan.v1",
        "artifact": "plan",
        "allowed_statuses": _REVIEWED_STATUSES,
        "required_front_matter": _BUILD_REQUIRED_FRONT_MATTER,
        "coverage_statuses": _BUILD_COVERAGE_STATUSES,
        "required_sections": [
            "Summary",
            "Current System",
            "Proposed Implementation",
            "Non-Goals",
            "Verification",
        ],
    },
    "gc.build.decomposition.v1": {
        "schema_id": "gc.build.decomposition.v1",
        "artifact": "decomposition",
        "allowed_statuses": _REVIEWED_STATUSES,
        "required_front_matter": _BUILD_REQUIRED_FRONT_MATTER,
        "coverage_statuses": _BUILD_COVERAGE_STATUSES,
        "required_sections": [
            "Summary",
            "Selected Downstream Formulas",
            "Implementation Convoy",
            "Work Items",
        ],
    },
    "gc.build.implementation-summary.v1": {
        "schema_id": "gc.build.implementation-summary.v1",
        "artifact": "implementation-summary",
        "allowed_statuses": _REPORT_STATUSES,
        "required_front_matter": _BUILD_REQUIRED_FRONT_MATTER,
        "coverage_statuses": _BUILD_COVERAGE_STATUSES,
        "required_sections": [
            "Summary",
            "Intended Behavior",
            "Changed Files",
            "Verification",
            "Remaining Risks",
        ],
    },
    "gc.build.review.v1": {
        "schema_id": "gc.build.review.v1",
        "artifact": "review",
        "allowed_statuses": _REVIEWED_STATUSES,
        "required_front_matter": _BUILD_REQUIRED_FRONT_MATTER,
        "coverage_statuses": _BUILD_COVERAGE_STATUSES,
        "required_sections": [
            "Verdict",
            "Findings",
            "Verification",
        ],
    },
    "gc.build.final-report.v1": {
        "schema_id": "gc.build.final-report.v1",
        "artifact": "final-report",
        "allowed_statuses": _REPORT_STATUSES,
        "required_front_matter": _BUILD_REQUIRED_FRONT_MATTER,
        "coverage_statuses": _BUILD_COVERAGE_STATUSES,
        "required_sections": [
            "Summary",
            "Outcome",
            "Artifacts",
            "Remaining Risks",
        ],
    },
}


class ValidationError(Exception):
    pass


YAML_ERROR_TYPES = (yaml.YAMLError,) if yaml is not None else ()
CLI_ERROR_TYPES = (OSError, UnicodeDecodeError, ValidationError) + YAML_ERROR_TYPES


@dataclass(frozen=True)
class BuildArtifact:
    schema_id: str
    front_matter: dict[str, Any]
    body: str
    upstream: list[dict[str, Any]]
    coverage: list[dict[str, Any]]


def validate_artifact_text(text: str, *, expected_schema: str = "") -> BuildArtifact:
    schema_id, front_matter, body = parse_front_matter(text)
    if expected_schema and schema_id != expected_schema:
        raise ValidationError(f"schema must be {expected_schema!r}, got {schema_id!r}")

    schema = load_schema(schema_id)
    validate_required_front_matter(front_matter, schema)
    validate_status(front_matter, schema)
    trace = validate_trace(front_matter)
    upstream = validate_upstream(trace)
    coverage = validate_coverage(trace, schema)
    validate_coverage_completeness(upstream, coverage)
    validate_markdown_coverage(body, coverage)
    validate_required_sections(body, schema)
    return BuildArtifact(
        schema_id=schema_id,
        front_matter=front_matter,
        body=body,
        upstream=upstream,
        coverage=coverage,
    )


def parse_front_matter(text: str) -> tuple[str, dict[str, Any], str]:
    if yaml is None:
        raise ValidationError(
            "PyYAML is required to parse build artifacts; import failed even after "
            f"appending these site-packages roots to sys.path: {', '.join(YAML_SITE_ROOTS_CHECKED)}. "
            "Install PyYAML for this interpreter or into one of those roots."
        )
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise ValidationError("build artifact must start with YAML front matter")
    data = yaml.safe_load(match.group("front")) or {}
    if not isinstance(data, dict):
        raise ValidationError("build artifact front matter must be a mapping")
    schema_id = required_string(data, "schema")
    return schema_id, data, match.group("body")


def load_schema(schema_id: str) -> dict[str, Any]:
    schema = EMBEDDED_SCHEMAS.get(schema_id)
    if schema is None:
        raise ValidationError(f"unknown build artifact schema {schema_id!r}")
    validate_schema_definition(schema)
    return schema


def validate_schema_definition(schema: dict[str, Any]) -> None:
    schema_id = schema.get("schema_id", "<unknown>")
    fields = schema.get("required_front_matter", [])
    if not isinstance(fields, list):
        raise ValidationError(f"schema {schema_id}: required_front_matter must be a list")
    for field in fields:
        leaf = str(field).split(".")[-1].lower()
        if leaf in FORBIDDEN_REQUIRED_FIELD_NAMES:
            raise ValidationError(
                f"schema {schema_id}: base schemas must not require owner, stage-owner, persona, or role fields, got {field!r}"
            )


def validate_required_front_matter(front_matter: dict[str, Any], schema: dict[str, Any]) -> None:
    fields = schema.get("required_front_matter", [])
    if not isinstance(fields, list):
        raise ValidationError(f"schema {schema.get('schema_id', '<unknown>')}: required_front_matter must be a list")
    missing = [field for field in fields if get_path(front_matter, str(field)) is None]
    if missing:
        raise ValidationError(f"front matter missing required fields: {missing}")
    for field in fields:
        value = get_path(front_matter, str(field))
        if isinstance(value, str) and not value.strip():
            raise ValidationError(f"front matter field {field} must be non-empty")
    attempt = get_path(front_matter, "producer.attempt")
    if not isinstance(attempt, int) or attempt < 1:
        raise ValidationError("producer.attempt must be a positive integer")


def validate_status(front_matter: dict[str, Any], schema: dict[str, Any]) -> None:
    status = required_string(front_matter, "status")
    allowed = schema.get("allowed_statuses", [])
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise ValidationError(f"schema {schema.get('schema_id', '<unknown>')}: allowed_statuses must be strings")
    if status not in allowed:
        raise ValidationError(f"status must be one of {sorted(allowed)}, got {status!r}")


def validate_trace(front_matter: dict[str, Any]) -> dict[str, Any]:
    trace = front_matter.get("trace")
    if not isinstance(trace, dict):
        raise ValidationError("trace must be a mapping")
    if "upstream" not in trace:
        raise ValidationError("trace.upstream must be present")
    if "coverage" not in trace:
        raise ValidationError("trace.coverage must be present")
    if not isinstance(trace["upstream"], list):
        raise ValidationError("trace.upstream must be a list")
    if not isinstance(trace["coverage"], list):
        raise ValidationError("trace.coverage must be a list")
    return trace


def validate_upstream(trace: dict[str, Any]) -> list[dict[str, Any]]:
    upstream: list[dict[str, Any]] = []
    for index, raw in enumerate(trace["upstream"]):
        if not isinstance(raw, dict):
            raise ValidationError(f"trace.upstream[{index}] must be a mapping")
        path = required_string(raw, "path", prefix=f"trace.upstream[{index}]")
        hash_value = required_string(raw, "hash", prefix=f"trace.upstream[{index}]")
        validate_upstream_path(path, index)
        if ":" not in hash_value:
            raise ValidationError(f"trace.upstream[{index}].hash must include a hash or revision scheme")
        ids = raw.get("ids")
        if ids is not None:
            if not isinstance(ids, list) or not all(isinstance(item, str) and item.strip() for item in ids):
                raise ValidationError(f"trace.upstream[{index}].ids must be a list of non-empty strings")
        upstream.append(raw)
    return upstream


def validate_coverage_completeness(upstream: list[dict[str, Any]], coverage: list[dict[str, Any]]) -> None:
    covered_ids = {str(entry["id"]) for entry in coverage}
    missing = [
        item_id
        for entry in upstream
        for item_id in entry.get("ids") or []
        if str(item_id).strip() not in covered_ids
    ]
    if missing:
        raise ValidationError(f"coverage must account for every upstream ID, missing: {missing}")


def validate_upstream_path(path: str, index: int) -> None:
    parsed = Path(path)
    if not parsed.is_absolute() and ".." in parsed.parts:
        raise ValidationError(f"trace.upstream[{index}].path must not escape the artifact root")


def validate_coverage(trace: dict[str, Any], schema: dict[str, Any]) -> list[dict[str, Any]]:
    allowed = schema.get("coverage_statuses", [])
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise ValidationError(f"schema {schema.get('schema_id', '<unknown>')}: coverage_statuses must be strings")
    allowed_set = set(allowed)
    seen: set[str] = set()
    coverage: list[dict[str, Any]] = []
    for index, raw in enumerate(trace["coverage"]):
        if not isinstance(raw, dict):
            raise ValidationError(f"trace.coverage[{index}] must be a mapping")
        item_id = required_string(raw, "id", prefix=f"trace.coverage[{index}]")
        status = required_string(raw, "status", prefix=f"trace.coverage[{index}]")
        if item_id in seen:
            raise ValidationError(f"trace.coverage[{index}].id duplicates {item_id!r}")
        seen.add(item_id)
        if status not in allowed_set:
            raise ValidationError(f"trace.coverage[{index}].status must be one of {sorted(allowed_set)}, got {status!r}")
        if status != "covered":
            required_string(raw, "rationale", prefix=f"trace.coverage[{index}]")
        coverage.append(raw)
    return coverage


def validate_markdown_coverage(body: str, coverage: list[dict[str, Any]]) -> None:
    expected = {str(item["id"]): str(item["status"]) for item in coverage}
    if not expected:
        return
    actual = parse_markdown_coverage(body)
    if not actual:
        raise ValidationError("markdown coverage matrix is missing")
    if actual != expected:
        raise ValidationError(f"markdown coverage matrix must match YAML coverage, got {actual!r}, expected {expected!r}")


def parse_markdown_coverage(body: str) -> dict[str, str]:
    coverage: dict[str, str] = {}
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        cells = split_table_row(lines[index])
        header = [cell.lower() for cell in cells]
        if header and "id" in header and "status" in header:
            id_index = header.index("id")
            status_index = header.index("status")
            index += 1
            if index < len(lines) and is_separator_row(lines[index]):
                index += 1
            while index < len(lines):
                row = split_table_row(lines[index])
                if not row or len(row) <= max(id_index, status_index):
                    break
                item_id = clean_table_cell(row[id_index])
                status = clean_table_cell(row[status_index])
                if item_id and status:
                    coverage[item_id] = status
                index += 1
            continue
        index += 1
    return coverage


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [clean_table_cell(cell) for cell in stripped.strip("|").split("|")]


def is_separator_row(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def clean_table_cell(value: str) -> str:
    return value.strip().strip("`").strip()


def validate_required_sections(body: str, schema: dict[str, Any]) -> None:
    required = schema.get("required_sections", [])
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValidationError(f"schema {schema.get('schema_id', '<unknown>')}: required_sections must be strings")
    positions: list[tuple[str, int]] = []
    for section in required:
        match = re.search(rf"^##\s+{re.escape(section)}\s*$", body, re.MULTILINE)
        if not match:
            raise ValidationError(f"missing required body section {section!r}")
        positions.append((section, match.start()))
    for (left_name, left_pos), (right_name, right_pos) in zip(positions, positions[1:]):
        if left_pos >= right_pos:
            raise ValidationError(f"body section {left_name!r} must appear before {right_name!r}")


def required_string(data: dict[str, Any], key: str, *, prefix: str = "") -> str:
    value = data.get(key)
    field = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    return value.strip()


def get_path(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a gc build artifact")
    parser.add_argument("--schema", required=True, help="Expected schema id")
    parser.add_argument("--path", required=True, type=Path, help="Artifact markdown path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        artifact = validate_artifact_text(args.path.read_text(encoding="utf-8"), expected_schema=args.schema)
    except CLI_ERROR_TYPES as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "schema": artifact.schema_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
