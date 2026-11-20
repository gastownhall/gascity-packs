#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


FRONT_MATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---(?:\n|\Z)", re.DOTALL)
VALID_KINDS = {"gap-analysis", "review"}
VALID_VERDICTS = {"pass", "fail"}
VALID_SEVERITIES = {"none", "minor", "major", "blocker"}
SEVERITY_ORDER = {"none": 0, "minor": 1, "major": 2, "blocker": 3}
REQUIRED_FINDING_FIELDS = {"id", "severity", "title", "evidence", "required_fix"}


class ValidationError(Exception):
    pass


class DependencyError(Exception):
    """A module this validator needs is not importable by the running interpreter.

    Deliberately not a ValidationError: the report was never examined, so the
    CLI must report it as an environment problem (exit EX_CONFIG) rather than a
    content verdict (exit 1).
    """


# EX_CONFIG from sysexits.h: the check cannot run on this machine as it is
# configured. The orchestrator holds the step open on this status instead of
# grading it, so a missing dependency never costs a producer attempt.
EX_CONFIG = 78

YAML_ERROR_TYPES = (yaml.YAMLError,) if yaml is not None else ()
CLI_ERROR_TYPES = (OSError, UnicodeDecodeError, ValidationError) + YAML_ERROR_TYPES


def require_yaml(purpose: str) -> None:
    """Raise DependencyError when PyYAML is not importable, naming the interpreter
    that was used and the environment that selected it, so the operator who reads
    the hold reason can tell which Python to fix."""
    if yaml is not None:
        return
    import os
    import site  # local: only needed on the failure path

    # Line 1 is what an operator sees in a hold reason, and the orchestrator
    # keeps about 256 bytes of it: facts first, nothing else. Line 2 carries
    # the derived path and the remedy.
    user_site = site.getusersitepackages()
    if site.ENABLE_USER_SITE is False:
        user_site += " (user site disabled)"
    raise DependencyError(
        f"PyYAML not importable by {sys.executable} (Python {sys.version.split()[0]}) "
        f"for {purpose}; HOME={os.environ.get('HOME', '')!r} "
        f"PYTHONUSERBASE={os.environ.get('PYTHONUSERBASE', '')!r}\n"
        f"user site searched: {user_site}. Install PyYAML for this interpreter; "
        "this is an environment problem, not a content problem"
    )


@dataclass(frozen=True)
class VerdictReport:
    schema: str
    kind: str
    verdict: str
    severity: str
    findings: list[dict[str, Any]]


def validate_report_text(text: str, *, expected_kind: str = "") -> VerdictReport:
    require_yaml("verdict reports")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise ValidationError("verdict report must start with YAML front matter")
    data = yaml.safe_load(match.group("body")) or {}
    if not isinstance(data, dict):
        raise ValidationError("verdict report front matter must be a mapping")

    schema = required_string(data, "schema")
    kind = required_string(data, "kind")
    verdict = required_string(data, "verdict")
    severity = required_string(data, "severity")
    findings = data.get("findings", [])

    if schema != "gc.verdict-report.v1":
        raise ValidationError(f"schema must be gc.verdict-report.v1, got {schema!r}")
    if kind not in VALID_KINDS:
        raise ValidationError(f"kind must be one of {sorted(VALID_KINDS)}, got {kind!r}")
    if expected_kind and kind != expected_kind:
        raise ValidationError(f"kind must be {expected_kind!r}, got {kind!r}")
    if verdict not in VALID_VERDICTS:
        raise ValidationError(f"verdict must be pass or fail, got {verdict!r}")
    if severity not in VALID_SEVERITIES:
        raise ValidationError(f"severity must be one of {sorted(VALID_SEVERITIES)}, got {severity!r}")
    if not isinstance(findings, list):
        raise ValidationError("findings must be a list")
    if verdict == "pass" and severity != "none":
        raise ValidationError("pass reports must use severity: none")
    if verdict == "fail" and severity == "none":
        raise ValidationError("fail reports must use a non-none severity")
    if verdict == "fail" and not findings:
        raise ValidationError("fail reports must include structured findings")

    finding_severities: list[str] = []
    for index, finding in enumerate(findings):
        finding_severities.append(validate_finding(finding, index))
    max_severity = max(finding_severities, key=lambda value: SEVERITY_ORDER[value]) if finding_severities else "none"
    if severity != max_severity:
        raise ValidationError(f"severity must be maximum finding severity {max_severity!r}, got {severity!r}")
    return VerdictReport(schema=schema, kind=kind, verdict=verdict, severity=severity, findings=findings)


def required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{key} must be a non-empty string")
    return value.strip()


def validate_finding(raw: Any, index: int) -> str:
    if not isinstance(raw, dict):
        raise ValidationError(f"findings[{index}] must be a mapping")
    missing = []
    for field in sorted(REQUIRED_FINDING_FIELDS):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    if missing:
        raise ValidationError(f"findings[{index}] missing fields: {missing}")
    severity = raw["severity"].strip()
    if severity not in VALID_SEVERITIES - {"none"}:
        raise ValidationError(f"findings[{index}].severity must be minor, major, or blocker")
    return severity


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a gc verdict report")
    parser.add_argument("path", type=Path)
    parser.add_argument("--kind", choices=sorted(VALID_KINDS), default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        report = validate_report_text(args.path.read_text(encoding="utf-8"), expected_kind=args.kind)
    except DependencyError as exc:
        print(f"environment error: {exc}", file=sys.stderr)
        return EX_CONFIG
    except CLI_ERROR_TYPES as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "kind": report.kind, "verdict": report.verdict}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
