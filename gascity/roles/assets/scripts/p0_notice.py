#!/usr/bin/env python3
"""Durable, role-addressed notice receipts.

The JSON file is deliberately only an idempotency/reconciliation cache.  Mail
and its lifecycle remain the audit source of truth, allowing a lost cache to be
reconstructed from the deterministic notice id in the mail subject.
"""
from __future__ import annotations

import argparse
import calendar
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:@+-]{0,127}$")
DISPOSITIONS = {"accepted", "dismissed", "superseded"}
TERMINAL = {"dismissed", "superseded", "undeliverable", "escalated"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def index_path() -> Path:
    configured = os.environ.get("GC_P0_NOTICE_INDEX")
    if configured:
        return Path(configured)
    city = os.environ.get("GC_CITY") or os.environ.get("GC_CITY_PATH")
    if city:
        return Path(city) / ".gc" / "runtime" / "p0-notices.json"
    # Commands normally run with GC_CITY set. Keep the fallback per-user so an
    # ad-hoc invocation cannot collide with another user's notices on the host.
    return Path(tempfile.gettempdir()) / f"gc-p0-notices-{os.getuid()}.json"


def check(value: str, field: str, max_len: int = 128) -> str:
    if not value or len(value) > max_len or not SAFE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def notice_id(role: str, work: str, fingerprint: str) -> str:
    material = "\0".join((role, work, fingerprint)).encode()
    return hashlib.sha256(material).hexdigest()[:24]


@contextmanager
def locked_index() -> Any:
    path = index_path()
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        os.chmod(lock_path, 0o640)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                data = {"schema_version": 1, "notices": {}}
            except json.JSONDecodeError:
                # A torn cache is non-authoritative. Preserve it for forensics
                # and recover on the next durable-mail observation.
                data = {"schema_version": 1, "notices": {}}
            yield data
            encoded = json.dumps(data, sort_keys=True, indent=2) + "\n"
            with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False,
                                             encoding="utf-8") as replacement:
                replacement.write(encoded)
                replacement.flush()
                os.fsync(replacement.fileno())
                temp_name = replacement.name
            os.chmod(temp_name, 0o640)
            os.replace(temp_name, path)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def run_gc(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, shell=False,
                          check=False)


def mail_id(output: str) -> str | None:
    try:
        decoded = json.loads(output)
    except json.JSONDecodeError:
        return None
    if isinstance(decoded, dict):
        messages = decoded.get("messages")
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            candidate = messages[0].get("id")
            if isinstance(candidate, str) and candidate:
                return candidate
        for key in ("mail_id", "id", "bead_id"):
            if isinstance(decoded.get(key), str) and decoded[key]:
                return decoded[key]
    return None


def recover_mail_id(nid: str) -> str | None:
    """Recover a receipt after an index loss from the deterministic subject."""
    result = run_gc(["gc", "bd", "query", "--json", "--all", f"title=notice:{nid}"])
    if result.returncode:
        return None
    try:
        matches = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(matches, list) and len(matches) == 1 and isinstance(matches[0], dict):
        candidate = matches[0].get("id")
        return candidate if isinstance(candidate, str) else None
    return None


def configured_role(role: str) -> bool | None:
    """Return whether an exact canonical role remains configured.

    ``gc agent list`` reads resolved configuration only. Unlike ``gc session
    wake``, it neither starts a dormant role nor clears a user hold or
    crash-loop quarantine. A configured role is therefore still a valid notice
    destination even while it is dormant or intentionally held. ``None``
    distinguishes an unreadable control plane from a genuinely unknown role.
    """
    result = run_gc(["gc", "agent", "list", "--json"])
    if result.returncode:
        return None
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    agents = decoded.get("agents") if isinstance(decoded, dict) else None
    if not isinstance(agents, list):
        return None
    return any(
        isinstance(agent, dict) and agent.get("qualified_name") == role
        for agent in agents
    )


def send(args: argparse.Namespace) -> int:
    role = check(args.to_role, "role")
    work = check(args.work_ref, "work reference")
    fingerprint = check(args.state_fingerprint, "state fingerprint")
    if len(args.subject) > 200 or len(args.message) > 4000:
        raise ValueError("subject or message too long")
    nid = notice_id(role, work, fingerprint)
    with locked_index() as data:
        notices = data.setdefault("notices", {})
        record = notices.get(nid)
        if record and not record.get("processed_at") and record.get("disposition") not in TERMINAL:
            record["occurrence_count"] = int(record.get("occurrence_count", 1)) + 1
            record["last_seen_at"] = now()
            print(json.dumps({"notice_id": nid, "disposition": "duplicate"}))
            return 0
        notices[nid] = {"notice_id": nid, "idempotency_key": nid,
            "recipient_role": role, "work_reference": work,
            "state_fingerprint": fingerprint, "occurrence_count": 1,
            "first_seen_at": now(), "last_seen_at": now(), "queued_at": now(),
            "disposition": "sending"}
    # The reservation is persisted before releasing the lock. Concurrent callers
    # see it and cannot generate another mail or nudge.
    recovered = recover_mail_id(nid)
    if recovered:
        with locked_index() as data:
            record = data["notices"][nid]
            record.update({"mail_id": recovered, "accepted_at": now(),
                           "disposition": "accepted"})
        print(json.dumps({"notice_id": nid, "disposition": "duplicate"}))
        return 0
    subject = f"[notice:{nid}] {args.subject}"
    result = run_gc(["gc", "mail", "send", role, "--notify", "--json", "-s", subject,
                     "-m", args.message])
    with locked_index() as data:
        record = data["notices"][nid]
        receipt = mail_id(result.stdout)
        if result.returncode == 0 and receipt:
            record.update({"mail_id": receipt, "accepted_at": now(),
                           "disposition": "accepted"})
        elif result.returncode == 0:
            record.update({"disposition": "undeliverable",
                           "terminal_reason": "mail send returned no durable receipt id"})
        else:
            # CLI output can reflect the caller's subject/message. Never copy it
            # into the reconstructable index.
            record.update({"disposition": "undeliverable",
                           "terminal_reason": "durable mail send failed"})
        print(json.dumps({"notice_id": nid, "disposition": record["disposition"]}))
        return result.returncode or (0 if receipt else 1)


def ack(args: argparse.Namespace) -> int:
    nid = check(args.notice_id, "notice id")
    actor = check(os.environ.get("GC_CANONICAL_ROLE", ""), "actor role")
    if args.disposition not in DISPOSITIONS:
        raise ValueError("invalid disposition")
    with locked_index() as data:
        record = data.get("notices", {}).get(nid)
        if not record:
            raise ValueError("unknown notice")
        if actor != record["recipient_role"]:
            raise PermissionError("only the recipient role may acknowledge")
        linked_mail = record.get("mail_id")
        if not linked_mail:
            raise ValueError("notice has no durable mail receipt")
    for command in (["gc", "mail", "read", linked_mail], ["gc", "mail", "archive", linked_mail]):
        result = run_gc(command)
        if result.returncode:
            sys.stderr.write(result.stderr or result.stdout)
            return result.returncode
    with locked_index() as data:
        record = data["notices"][nid]
        record.update({"processed_at": now(), "disposition": args.disposition})
    print(json.dumps({"notice_id": nid, "disposition": args.disposition}))
    return 0


def reconcile(args: argparse.Namespace) -> int:
    if args.limit < 1 or args.limit > 100:
        raise ValueError("limit must be between 1 and 100")
    cutoff = time.time() - args.retention_seconds
    escalated = 0
    with locked_index() as data:
        notices = data.setdefault("notices", {})
        notice_ids = list(notices)
        offset = data.get("reconcile_offset", 0)
        if not isinstance(offset, int):
            offset = 0
        if notice_ids:
            offset %= len(notice_ids)
            selected_ids = (notice_ids[offset:] + notice_ids[:offset])[:args.limit]
        else:
            offset = 0
            selected_ids = []
        for nid in selected_ids:
            record = notices.get(nid)
            if record is None:
                continue
            if record.get("processed_at") or record.get("disposition") in TERMINAL:
                terminal_at = record.get("processed_at") or record.get("last_seen_at", "")
                parsed_terminal_at = _parse_time(terminal_at)
                if parsed_terminal_at is not None and parsed_terminal_at < cutoff:
                    del notices[nid]
                    continue
            # This bounded operation observes receipt state only. It deliberately
            # does not evaluate dependency readiness or create repair work.
            if record.get("disposition") == "sending" and not record.get("escalated_at"):
                queued_at = _parse_time(record.get("queued_at", ""))
                if queued_at is not None and time.time() - queued_at >= 300:
                    role = record["recipient_role"]
                    routable = configured_role(role)
                    if routable is None:
                        # An unreadable config is not evidence that a canonical
                        # role disappeared; retry on the next bounded pass.
                        record["routability_error"] = "unable to read configured canonical roles"
                    elif not routable:
                        escalation = run_gc(["gc", "mail", "send", "human", "--notify", "--json", "-s",
                                             f"[notice:{nid}] role unavailable", "-m", role])
                        if escalation.returncode == 0 and mail_id(escalation.stdout):
                            record["escalated_at"] = now()
                            record["disposition"] = "escalated"
                            record["terminal_reason"] = "no routable role after five minutes"
                            escalated += 1
                        else:
                            # Do not claim a human saw the escalation. Leaving the
                            # receipt in `sending` makes the bounded next run retry.
                            record["escalation_error"] = "human escalation was not durably accepted"
        remaining = len(notices)
        data["reconcile_offset"] = (
            (offset + len(selected_ids)) % remaining if remaining else 0
        )
    print(json.dumps({"processed": min(args.limit, len(notices)), "escalated": escalated}))
    return 0


def _parse_time(value: str) -> float | None:
    try:
        return calendar.timegm(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("send")
    p.add_argument("--to-role", required=True); p.add_argument("--work-ref", required=True)
    p.add_argument("--state-fingerprint", required=True); p.add_argument("--subject", required=True)
    p.add_argument("--message", required=True); p.set_defaults(handler=send)
    p = sub.add_parser("ack")
    p.add_argument("notice_id"); p.add_argument("--disposition", required=True)
    p.set_defaults(handler=ack)
    p = sub.add_parser("reconcile")
    p.add_argument("--limit", type=int, default=50); p.add_argument("--retention-seconds", type=int, default=604800)
    p.set_defaults(handler=reconcile)
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (ValueError, PermissionError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
