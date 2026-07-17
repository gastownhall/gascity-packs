#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


FRONT_MATTER_RE = re.compile(r"\A---\n(?P<front>.*?)\n---(?:\n|\Z)(?P<body>.*)\Z", re.DOTALL)
SHA256_RE = re.compile(r"sha256:[0-9a-fA-F]{64}\Z")
SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas" / "build"
FORBIDDEN_REQUIRED_FIELD_NAMES = {"owner", "stage-owner", "stage_owner", "persona", "role"}


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


def validate_artifact_text(
    text: str,
    *,
    expected_schema: str = "",
    verify_absolute_upstreams: bool = False,
    enforce_review_status_coverage: bool = False,
    artifact_path: Path | None = None,
    upstream_roots: Iterable[Path] = (),
) -> BuildArtifact:
    schema_id, front_matter, body = parse_front_matter(text)
    if expected_schema and schema_id != expected_schema:
        raise ValidationError(f"schema must be {expected_schema!r}, got {schema_id!r}")

    schema = load_schema(schema_id)
    validate_required_front_matter(front_matter, schema)
    validate_status(front_matter, schema)
    trace = validate_trace(front_matter)
    upstream = validate_upstream(trace)
    if verify_absolute_upstreams:
        validate_absolute_sha256_upstreams(
            upstream,
            artifact_path=artifact_path,
            upstream_roots=upstream_roots,
        )
    coverage = validate_coverage(trace, schema)
    validate_coverage_completeness(upstream, coverage)
    if enforce_review_status_coverage:
        validate_status_coverage(front_matter, schema, coverage)
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
        raise ValidationError("PyYAML is required to parse build artifacts")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise ValidationError("build artifact must start with YAML front matter")
    data = yaml.safe_load(match.group("front")) or {}
    if not isinstance(data, dict):
        raise ValidationError("build artifact front matter must be a mapping")
    schema_id = required_string(data, "schema")
    return schema_id, data, match.group("body")


def load_schema(schema_id: str) -> dict[str, Any]:
    if yaml is None:
        raise ValidationError("PyYAML is required to parse build schemas")
    for path in sorted(SCHEMA_ROOT.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(raw, dict) and raw.get("schema_id") == schema_id:
            validate_schema_definition(raw)
            return raw
    raise ValidationError(f"unknown build artifact schema {schema_id!r}")


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
        if hash_value.lower().startswith("sha256:") and not SHA256_RE.fullmatch(hash_value):
            raise ValidationError(
                f"trace.upstream[{index}].hash with sha256 scheme must contain exactly 64 hexadecimal digits"
            )
        ids = raw.get("ids")
        if ids is not None:
            if not isinstance(ids, list) or not all(isinstance(item, str) and item.strip() for item in ids):
                raise ValidationError(f"trace.upstream[{index}].ids must be a list of non-empty strings")
        normalized = dict(raw)
        normalized["path"] = path
        normalized["hash"] = hash_value
        trace["upstream"][index] = normalized
        upstream.append(normalized)
    return upstream


def validate_absolute_sha256_upstreams(
    upstream: list[dict[str, Any]],
    *,
    artifact_path: Path | None = None,
    upstream_roots: Iterable[Path] = (),
) -> None:
    upstream_roots = tuple(upstream_roots)
    for index, entry in enumerate(upstream):
        hash_value = str(entry["hash"])
        if not hash_value.lower().startswith("sha256:"):
            continue
        path = Path(str(entry["path"]))
        if not path.is_absolute():
            path = resolve_relative_sha256_upstream(
                path,
                index=index,
                artifact_path=artifact_path,
                upstream_roots=upstream_roots,
            )
        if not path.is_file():
            raise ValidationError(
                f"trace.upstream[{index}] sha256 path is not a file: {path}"
            )
        actual = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        if actual.lower() != hash_value.lower():
            raise ValidationError(
                f"trace.upstream[{index}] sha256 digest does not match {path}: "
                f"expected {hash_value}, got {actual}"
            )


def resolve_relative_sha256_upstream(
    path: Path,
    *,
    index: int,
    artifact_path: Path | None,
    upstream_roots: Iterable[Path],
) -> Path:
    roots: list[Path] = []
    if artifact_path is not None:
        roots.append(Path(artifact_path).resolve(strict=False).parent)
    roots.extend(Path(root).resolve(strict=False) for root in upstream_roots)

    unique_roots = list(dict.fromkeys(roots))
    if not unique_roots:
        raise ValidationError(
            f"trace.upstream[{index}] relative sha256 path requires an artifact path or explicit upstream root: {path}"
        )

    matches: dict[Path, Path] = {}
    for root in unique_roots:
        if not root.is_dir():
            raise ValidationError(
                f"trace.upstream[{index}] sha256 upstream root is not a directory: {root}"
            )
        candidate = (root / path).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValidationError(
                f"trace.upstream[{index}] relative sha256 path escapes upstream root {root}: {path}"
            ) from exc
        if candidate.is_file():
            matches[candidate] = candidate

    if not matches:
        rendered_roots = ", ".join(str(root) for root in unique_roots)
        raise ValidationError(
            f"trace.upstream[{index}] relative sha256 path does not resolve to a file under approved roots "
            f"[{rendered_roots}]: {path}"
        )
    if len(matches) > 1:
        rendered_matches = ", ".join(str(candidate) for candidate in matches)
        raise ValidationError(
            f"trace.upstream[{index}] relative sha256 path is ambiguous across approved roots: "
            f"{path} -> [{rendered_matches}]"
        )
    return next(iter(matches.values()))


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


def validate_status_coverage(
    front_matter: dict[str, Any],
    schema: dict[str, Any],
    coverage: list[dict[str, Any]],
) -> None:
    if schema.get("artifact") != "review":
        return

    status = required_string(front_matter, "status")
    has_blocked_coverage = any(
        item.get("status") == "blocked" for item in coverage
    )
    if (
        status in {"changes_required", "blocked"}
        and coverage
        and not has_blocked_coverage
    ):
        raise ValidationError(
            f"review status {status!r} requires at least one blocked coverage entry"
        )
    if status == "approved" and has_blocked_coverage:
        raise ValidationError("approved review must not include blocked coverage")


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
    parser.add_argument(
        "--verify-absolute-upstreams",
        action="store_true",
        help="Require sha256 upstream paths to exist under approved roots and match their current bytes",
    )
    parser.add_argument(
        "--upstream-root",
        action="append",
        default=[],
        type=Path,
        help="Additional approved root for resolving relative sha256 upstream paths (repeatable)",
    )
    parser.add_argument(
        "--enforce-review-status-coverage",
        action="store_true",
        help="Apply producer policy requiring top-level review status to agree with blocked coverage",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        artifact = validate_artifact_text(
            args.path.read_text(encoding="utf-8"),
            expected_schema=args.schema,
            verify_absolute_upstreams=args.verify_absolute_upstreams,
            enforce_review_status_coverage=args.enforce_review_status_coverage,
            artifact_path=args.path,
            upstream_roots=args.upstream_root,
        )
    except CLI_ERROR_TYPES as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "schema": artifact.schema_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
