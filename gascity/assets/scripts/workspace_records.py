#!/usr/bin/env python3
"""Read-only validation and identity helpers for pack workspace records."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "workspace" / "records.v1.json"


class RecordError(ValueError):
    pass


def parse_record(text: str) -> dict[str, Any]:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RecordError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        record = json.loads(text, object_pairs_hook=unique_object)
    except ValueError as exc:
        raise RecordError(str(exc)) from exc
    if not isinstance(record, dict):
        raise RecordError("record must be one JSON object")
    return record


@lru_cache(maxsize=1)
def schema_bundle() -> dict[str, Any]:
    return parse_record(SCHEMA_PATH.read_text(encoding="utf-8"))


def contracts() -> dict[str, Any]:
    return schema_bundle()["x-records"]


def record_schema(kind: str) -> dict[str, Any]:
    if kind not in contracts():
        raise RecordError(f"unknown record kind: {kind}")
    return schema_bundle()["$defs"][kind]


def validate_record(kind: str, record: dict[str, Any]) -> dict[str, Any]:
    record_schema(kind)
    canonical_bytes(record)
    schema = {"$defs": schema_bundle()["$defs"], "$ref": f"#/$defs/{kind}"}
    try:
        jsonschema.Draft202012Validator(schema).validate(record)
    except jsonschema.ValidationError as exc:
        location = ".".join(map(str, exc.absolute_path)) or kind
        raise RecordError(f"{location}: {exc.message}") from exc
    if type(record["version"]) is not int or type(record["generation"]) is not int:
        raise RecordError("version and generation must be integers")
    if kind == "member-result":
        source_in, source_out = record["input_oid"], record["output_oid"]
        if record["status"] == "no_change" and (source_in != source_out or record["commit_oids"]):
            raise RecordError("no_change requires equal input/output and no commits")
        if record["status"] == "changed" and (source_in == source_out or record["commit_oids"][-1] != source_out):
            raise RecordError("changed requires a different output and its final commit")
        acceptance = record["acceptance"]
        if acceptance["subject_oid"] != source_out:
            raise RecordError("acceptance subject_oid must equal output_oid")
        if acceptance["status"] == "accepted":
            review = acceptance["independent_review"]
            if (not acceptance["project_checks"] or any(check["exit_code"] != 0 or check["subject_oid"] != source_out for check in acceptance["project_checks"])
                or review["status"] != "passed" or review["reviewed_oid"] != source_out
                or not review["report_path"] or not review["report_sha256"] or not review["reviewer"] or review["reviewer"] == record["writer_step_id"]):
                raise RecordError("accepted requires successful project checks and independent review of output_oid")
    if kind == "workspace":
        if any(record["claim_binding"][field] != record[field] for field in ("workflow_root_id", "generation", "workspace_owner_id", "writer_step_id", "writer_attempt_id")):
            raise RecordError("identity conflict: claim binding must retain the run, generation, stable owner, and exact writer attempt")
    if kind == "publish" and record["status"] == "observed" and record["observed_oid"] != record["output_oid"]:
        raise RecordError("observed_oid must equal the intended output_oid")
    return record


def canonical_bytes(record: Any) -> bytes:
    try:
        return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RecordError(f"invalid canonical JSON: {exc}") from exc


def record_sha256(record: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(record)).hexdigest()


def record_identity(kind: str, record: dict[str, Any]) -> tuple[Any, ...]:
    validate_record(kind, record)
    return tuple(record[field] for field in contracts()[kind]["identity"])


def verify_replay(kind: str, stored: dict[str, Any], candidate: dict[str, Any]) -> bool:
    if record_identity(kind, stored) != record_identity(kind, candidate):
        raise RecordError("identity conflict: a different run, generation, or owner cannot reuse this record")
    if canonical_bytes(stored) != canonical_bytes(candidate):
        raise RecordError("conflicting replay: same identity has a different payload")
    return True


def resolve_record_id(kind: str, record: dict[str, Any], references: list[dict[str, Any]]) -> str:
    identity = list(record_identity(kind, record))
    if any(not isinstance(ref, dict) for ref in references):
        raise RecordError("record reference must be an object")
    matches = [ref for ref in references if ref.get("kind") == kind and ref.get("identity") == identity]
    if not matches:
        raise RecordError("missing record reference")
    if len(matches) != 1:
        raise RecordError("ambiguous record reference")
    bead_id = matches[0].get("bead_id")
    if not isinstance(bead_id, str) or not bead_id.strip():
        raise RecordError("record reference requires a physical bead_id")
    if kind == "workspace" and bead_id != record["workspace_bead_id"]:
        raise RecordError("record reference conflicts with physical workspace bead_id")
    return bead_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True, choices=contracts())
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--stored", type=Path, help="Require an exact replay of this existing record")
    args = parser.parse_args(argv)
    try:
        record = validate_record(args.kind, parse_record(args.path.read_text(encoding="utf-8")))
        if args.stored is not None:
            verify_replay(args.kind, parse_record(args.stored.read_text(encoding="utf-8")), record)
        print(json.dumps({"ok": True, "kind": args.kind, "identity": record_identity(args.kind, record), "sha256": record_sha256(record)}, sort_keys=True))
        return 0
    except (RecordError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
