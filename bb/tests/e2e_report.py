"""Fail-closed, scrubbed case ledger for real BB/GC end-to-end runs.

Callers declare the full required matrix before execution. Each case can settle
once. Missing, blocked and failed cases prevent an overall pass. Public files
contain only validated artifact identities, stable codes and evidence hashes;
exception details and provider output belong exclusively in private evidence.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import time
import traceback


class ReportFailure(RuntimeError):
    pass


_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_VERSION = re.compile(r"v?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?(?:\+[a-zA-Z0-9.-]+)?\Z")
_REASONS = {"assertion_failed", "command_failed", "timeout", "missing_credentials",
            "provider_unavailable", "unavailable_surface", "unsupported_runtime",
            "artifact_mismatch", "startup_failed", "recovery_failed", "not_implemented",
            "manual_step_required", "transport_failed", "dependency_failed", "skipped_case"}


def validate_artifacts(artifacts):
    required = {"gc_commit", "gc_binary_sha256", "pack_sha256", "bb_version", "runtime", "runtime_version"}
    optional = {"gc_version", "bb_binary_sha256", "runtime_binary_sha256", "verification_mode", "model_route"}
    if not isinstance(artifacts, dict) or not required <= artifacts.keys() or artifacts.keys() - required - optional:
        raise ReportFailure("E2E reports require exact, recognized artifact identities")
    for key, value in artifacts.items():
        valid = isinstance(value, str)
        if key == "gc_commit":
            valid = valid and _COMMIT.fullmatch(value) is not None
        elif key.endswith("sha256"):
            valid = valid and _SHA256.fullmatch(value) is not None
        elif key.endswith("version"):
            valid = valid and _VERSION.fullmatch(value) is not None
        elif key == "runtime":
            valid = value in {"claude", "codex"}
        elif key == "verification_mode":
            valid = value in {"release", "development"}
        elif key == "model_route":
            valid = valid and _ID.fullmatch(value) is not None
        if not valid:
            raise ReportFailure("An artifact identity is missing, ambiguous, or unsafe to publish")
    return dict(artifacts)


class E2ELedger:
    def __init__(self, artifacts_dir, *, required_cases, artifacts):
        if (not isinstance(required_cases, (list, tuple)) or not required_cases
                or any(not isinstance(value, str) or not _ID.fullmatch(value) for value in required_cases)
                or len(set(required_cases)) != len(required_cases)):
            raise ReportFailure("The required E2E matrix must contain unique stable case IDs")
        self.artifacts = validate_artifacts(artifacts)
        self.required_cases = list(required_cases)
        self.root = Path(artifacts_dir)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.root = self.root.resolve(strict=True)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self._events = (self.root / "cases.jsonl").open("xb")
        os.fchmod(self._events.fileno(), 0o600)
        self._cases = {case: {"id": case, "status": "not_run"} for case in self.required_cases}
        self._finalized = False
        self._write_event({"event": "matrix_declared", "required_cases": self.required_cases,
                           "artifacts": self.artifacts})

    def _write_event(self, event):
        self._events.write(json.dumps({"at": time.time(), **event}, sort_keys=True).encode() + b"\n")
        self._events.flush()
        os.fsync(self._events.fileno())

    def _check_case(self, case_id):
        if self._finalized:
            raise ReportFailure("The E2E report is already finalized")
        if case_id not in self._cases:
            raise ReportFailure("The case was not declared in the required E2E matrix")
        if self._cases[case_id]["status"] != "not_run":
            raise ReportFailure("A settled case cannot be replaced or silently retried")

    def _evidence(self, files):
        evidence = []
        for value in files:
            path = Path(value)
            if path.is_symlink():
                raise ReportFailure("Evidence cannot be a symlink")
            path = path.resolve(strict=True)
            if not path.is_relative_to(self.root) or not path.is_file():
                raise ReportFailure("Evidence must be a file in this run's private scratch tree")
            before = path.stat()
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            after = path.stat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ReportFailure("Evidence changed while being hashed; capture a stable snapshot first")
            evidence.append({"sha256": digest.hexdigest(), "bytes": after.st_size})
        return evidence

    def record(self, case_id, status, *, reason_code=None, assertions=(), evidence_files=()):
        self._check_case(case_id)
        if status not in {"passed", "failed", "blocked"}:
            raise ReportFailure("A case must explicitly pass, fail or remain blocked")
        if status == "passed":
            if reason_code is not None or not assertions or not evidence_files:
                raise ReportFailure("A passed case requires assertions and real evidence, without a failure reason")
        elif reason_code not in _REASONS:
            raise ReportFailure("Failures and blockers require a recognized public reason code")
        if (not isinstance(assertions, (tuple, list))
                or any(not isinstance(value, str) or not _ID.fullmatch(value) for value in assertions)):
            raise ReportFailure("Assertions must use stable public identifiers")
        row = {"id": case_id, "status": status, "assertions": list(assertions),
               "evidence": self._evidence(evidence_files)}
        if reason_code is not None:
            row["reason_code"] = reason_code
        self._write_event({"event": "case_settled", "case": row})
        self._cases[case_id] = row
        return dict(row)

    def record_error(self, case_id, error, *, reason_code="assertion_failed", status="failed"):
        """Keep the complete exception private; publish only the supplied code."""
        self._check_case(case_id)
        if not isinstance(error, BaseException):
            raise ReportFailure("Error capture requires an actual exception")
        if status not in {"failed", "blocked"} or reason_code not in _REASONS:
            raise ReportFailure("Exception outcomes need a recognized failure or blocker code")
        index = self.required_cases.index(case_id) + 1
        path = self.private / f"case-{index:04d}-exception.txt"
        with path.open("x") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write("".join(traceback.format_exception(type(error), error, error.__traceback__)))
        return self.record(case_id, status, reason_code=reason_code, evidence_files=[path])

    def block_remaining(self, reason_code):
        if reason_code not in _REASONS:
            raise ReportFailure("Blockers require a recognized public reason code")
        for case in self.required_cases:
            if self._cases[case]["status"] == "not_run":
                self.record(case, "blocked", reason_code=reason_code)

    def summary(self):
        statuses = [self._cases[case]["status"] for case in self.required_cases]
        status = ("failed" if "failed" in statuses else "blocked" if "blocked" in statuses
                  else "incomplete" if "not_run" in statuses else "passed")
        return {"schema_version": 1, "status": status, "artifacts": dict(self.artifacts),
                "required_cases": list(self.required_cases),
                "counts": {value: statuses.count(value) for value in ("passed", "failed", "blocked", "not_run")},
                "cases": [dict(self._cases[case]) for case in self.required_cases]}

    def finalize(self):
        if self._finalized:
            raise ReportFailure("The E2E report is already finalized")
        report = self.summary()
        # Never replace a preexisting report or erase the append-only events.
        with (self.root / "summary.json").open("x") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(report, stream, indent=2)
            stream.write("\n")
        self._write_event({"event": "run_finalized", "status": report["status"]})
        self._events.close()
        self._finalized = True
        return report

    finish = finalize
