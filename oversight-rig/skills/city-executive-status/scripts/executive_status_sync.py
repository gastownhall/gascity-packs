#!/usr/bin/env python3
"""Validate status inputs and maintain one deterministic executive brief."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import os
import pathlib
import re
import shlex
import string
import subprocess
import sys
import tempfile
from typing import NamedTuple


START = "<!-- executive-status:start -->"
END = "<!-- executive-status:end -->"
HEALTH_LABELS = {
    "on-track": "🟢 On track",
    "at-risk": "🟠 At risk",
    "blocked": "🔴 Blocked",
    "parked": "⚪ Parked",
}
REQUIRED_FIELDS = (
    "project",
    "owner",
    "updated",
    "health",
    "current",
    "next",
    "risk",
)
FIELD_LIMITS = {
    "project": 80,
    "owner": 80,
    "current": 240,
    "next": 240,
    "risk": 240,
}
DEFAULT_STALE_AFTER = dt.timedelta(hours=48)
DEFAULT_MAX_PUBLISH_LENGTH = 3500
MAX_INPUT_BYTES = 64 * 1024
PUBLISH_PLACEHOLDERS = frozenset({"body_file", "title"})


class Status(NamedTuple):
    project: str
    owner: str
    updated: dt.datetime
    health: str
    current: str
    next_step: str
    risk: str


class SyncConfig(NamedTuple):
    input_dir: pathlib.Path
    output: pathlib.Path
    title: str
    sentinel: pathlib.Path
    audit_log: pathlib.Path
    publish_command: str
    stale_after: dt.timedelta
    max_publish_length: int
    publish_timeout: float
    expected_owners: set[str]


def parse_fields(text: str) -> dict[str, str]:
    if START not in text or END not in text:
        raise ValueError("missing executive-status fence")
    block = text.split(START, 1)[1].split(END, 1)[0]
    fields: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError("invalid field line without a colon")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in fields:
            raise ValueError(f"duplicate field: {key}")
        fields[key] = value
    return fields


def parse_updated(value: str) -> dt.datetime:
    try:
        updated = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("updated must be an ISO-8601 timestamp") from exc
    if updated.tzinfo is None:
        raise ValueError("updated must include a timezone")
    return updated


def validate_fields(fields: dict[str, str], path: pathlib.Path) -> dt.datetime:
    for field in REQUIRED_FIELDS:
        if not fields.get(field):
            raise ValueError(f"missing required field: {field}")
    unexpected = sorted(set(fields) - set(REQUIRED_FIELDS))
    if unexpected:
        raise ValueError(f"unexpected field(s): {', '.join(unexpected)}")
    if fields["health"] not in HEALTH_LABELS:
        raise ValueError("invalid health; use on-track, at-risk, blocked, or parked")
    for field, limit in FIELD_LIMITS.items():
        if len(fields[field]) > limit:
            raise ValueError(f"{field} exceeds {limit} characters")
    if path.stem != fields["owner"]:
        raise ValueError("owner must match filename")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", fields["owner"]):
        raise ValueError("owner contains unsupported characters")

    return parse_updated(fields["updated"])


def parse_status(text: str, path: pathlib.Path) -> Status:
    fields = parse_fields(text)
    updated = validate_fields(fields, path)

    return Status(
        project=fields["project"],
        owner=fields["owner"],
        updated=updated,
        health=fields["health"],
        current=fields["current"],
        next_step=fields["next"],
        risk=fields["risk"],
    )


def read_status_input(path: pathlib.Path) -> str:
    if path.is_symlink():
        raise ValueError("symbolic links are not allowed")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"input exceeds {MAX_INPUT_BYTES} bytes")
    return path.read_text(encoding="utf-8")


def load_statuses(input_dir: pathlib.Path) -> tuple[list[Status], list[str]]:
    if not input_dir.is_dir():
        return [], [f"{input_dir}: input directory does not exist"]
    statuses: list[Status] = []
    errors: list[str] = []
    seen_owners: set[str] = set()
    for path in sorted(input_dir.glob("*.md")):
        try:
            status = parse_status(read_status_input(path), path)
            if status.owner in seen_owners:
                raise ValueError(f"duplicate owner: {status.owner}")
            seen_owners.add(status.owner)
            statuses.append(status)
        except (OSError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
    return statuses, errors


def is_stale(
    status: Status,
    now: dt.datetime,
    stale_after: dt.timedelta = DEFAULT_STALE_AFTER,
) -> bool:
    age = now.astimezone(dt.timezone.utc) - status.updated.astimezone(dt.timezone.utc)
    return age > stale_after


def display_health(
    status: Status,
    now: dt.datetime,
    stale_after: dt.timedelta = DEFAULT_STALE_AFTER,
) -> str:
    return (
        "⚪ Stale"
        if is_stale(status, now, stale_after)
        else HEALTH_LABELS[status.health]
    )


def markdown_text(value: str) -> str:
    return html.escape(value, quote=False).replace("\n", " ")


def markdown_cell(value: str) -> str:
    return markdown_text(value).replace("|", "\\|")


def stable_generated_at(statuses: list[Status]) -> str:
    return max(status.updated for status in statuses).isoformat(timespec="minutes")


def risks_to_watch(
    statuses: list[Status],
    now: dt.datetime,
    stale_after: dt.timedelta,
    *,
    include_stale: bool,
) -> list[Status]:
    return [
        status
        for status in statuses
        if status.risk.casefold() != "none"
        and (
            status.health in {"at-risk", "blocked"}
            or (include_stale and is_stale(status, now, stale_after))
        )
        and (include_stale or not is_stale(status, now, stale_after))
    ]


def brief_coverage_lines(
    reporting: int, missing: set[str], errors: list[str]
) -> list[str]:
    lines = [
        "",
        "## Reporting coverage",
        "",
        f"- {reporting} portfolio owners reporting.",
    ]
    if missing:
        lines.append("- Awaiting first update: " + ", ".join(sorted(missing)) + ".")
    if errors:
        lines.append(f"- {len(errors)} malformed input(s); see the sync audit log.")
    return lines


def render_brief(
    statuses: list[Status],
    now: dt.datetime,
    *,
    title: str,
    missing: set[str] | None = None,
    errors: list[str] | None = None,
    stale_after: dt.timedelta = DEFAULT_STALE_AFTER,
) -> str:
    missing = missing or set()
    errors = errors or []
    ordered = sorted(statuses, key=lambda item: item.project.casefold())
    lines = [
        "---",
        "tags: [executive-brief]",
        f"updated: {stable_generated_at(ordered)}",
        "---",
        "",
        f"# {markdown_text(title)}",
        "",
        "> One portfolio view of current focus, planned work, and material risk.",
        "",
        "## Portfolio",
        "",
        "| Project | Health | Current focus | Next |",
        "| --- | --- | --- | --- |",
    ]
    for status in ordered:
        lines.append(
            f"| {markdown_cell(status.project)} | "
            f"{display_health(status, now, stale_after)} | "
            f"{markdown_cell(status.current)} | "
            f"{markdown_cell(status.next_step)} |"
        )

    risks = risks_to_watch(ordered, now, stale_after, include_stale=True)
    lines.extend(["", "## Risks to watch", ""])
    if risks:
        lines.extend(
            f"- **{markdown_text(status.project)}:** {markdown_text(status.risk)}"
            for status in risks
        )
    else:
        lines.append("- No material risks reported.")

    lines.extend(brief_coverage_lines(len(ordered), missing, errors))
    lines.append("")
    return "\n".join(lines)


def shorten(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def health_counts(
    statuses: list[Status], now: dt.datetime, stale_after: dt.timedelta
) -> dict[str, int]:
    return {
        health: sum(
            not is_stale(status, now, stale_after) and status.health == health
            for status in statuses
        )
        for health in HEALTH_LABELS
    }


def summary_coverage_lines(missing: set[str], errors: list[str]) -> list[str]:
    if not missing and not errors:
        return []
    lines = ["", "Reporting coverage:"]
    if missing:
        lines.append(f"- {len(missing)} owner(s) have not reported.")
    if errors:
        lines.append(f"- {len(errors)} input(s) failed validation.")
    return lines


def render_publish_summary(
    statuses: list[Status],
    now: dt.datetime,
    *,
    title: str,
    missing: set[str] | None = None,
    errors: list[str] | None = None,
    stale_after: dt.timedelta = DEFAULT_STALE_AFTER,
    max_length: int = DEFAULT_MAX_PUBLISH_LENGTH,
) -> str:
    missing = missing or set()
    errors = errors or []
    ordered = sorted(statuses, key=lambda item: item.project.casefold())
    counts = health_counts(ordered, now, stale_after)
    stale_count = sum(is_stale(status, now, stale_after) for status in ordered)
    noun = "project" if len(ordered) == 1 else "projects"
    lines = [
        f"# {markdown_text(title)}",
        "",
        f"{len(ordered)} {noun} reporting: {counts['on-track']} on track, "
        f"{counts['at-risk']} at risk, {counts['blocked']} blocked, "
        f"{counts['parked']} parked, {stale_count} stale.",
        "",
    ]
    for status in ordered:
        icon = display_health(status, now, stale_after).split()[0]
        lines.append(
            f"- {icon} **{markdown_text(status.project)}** — "
            f"{markdown_text(shorten(status.current, 100))}"
        )
    risks = risks_to_watch(ordered, now, stale_after, include_stale=False)
    if risks:
        lines.extend(["", "Risks to watch:"])
        lines.extend(
            f"- **{markdown_text(status.project)}** — "
            f"{markdown_text(shorten(status.risk, 140))}"
            for status in risks[:4]
        )
    lines.extend(summary_coverage_lines(missing, errors))
    body = "\n".join(lines)
    return body if len(body) <= max_length else body[: max_length - 1].rstrip() + "…"


def write_if_changed(path: pathlib.Path, content: str) -> bool:
    try:
        if path.read_text(encoding="utf-8") == content:
            return False
    except FileNotFoundError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
        encoding="utf-8",
    ) as handle:
        handle.write(content)
        temporary = pathlib.Path(handle.name)
    temporary.replace(path)
    return True


def build_publish_command(
    template: str, *, body_file: pathlib.Path, title: str
) -> list[str]:
    formatter = string.Formatter()
    fields = {
        field_name for _, field_name, _, _ in formatter.parse(template) if field_name
    }
    unsupported = fields - PUBLISH_PLACEHOLDERS
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"unsupported publish placeholder(s): {names}")
    if "body_file" not in fields:
        raise ValueError("publish command requires {body_file}")
    values = {"body_file": str(body_file), "title": title}
    return [token.format_map(values) for token in shlex.split(template)]


def publish_summary(template: str, body: str, *, title: str, timeout: float) -> None:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(body)
        body_path = pathlib.Path(handle.name)
    try:
        command = build_publish_command(template, body_file=body_path, title=title)
        subprocess.run(command, timeout=timeout, check=True)
    finally:
        body_path.unlink(missing_ok=True)


def expected_owners(raw: str) -> set[str]:
    return {owner.strip() for owner in raw.split(",") if owner.strip()}


def log(path: pathlib.Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-publish", action="store_true")
    return parser.parse_args()


def load_config() -> SyncConfig:
    input_dir = pathlib.Path(
        os.environ.get("EXECUTIVE_STATUS_INPUT_DIR", "executive-status/inputs")
    )
    output = pathlib.Path(
        os.environ.get("EXECUTIVE_STATUS_OUTPUT", "executive-status/Executive Brief.md")
    )
    title = os.environ.get("EXECUTIVE_STATUS_TITLE", "Executive Status Brief").strip()
    if not title or len(title) > 120 or "\n" in title or "\r" in title:
        raise ValueError("EXECUTIVE_STATUS_TITLE must be one line of 1-120 characters")
    sentinel = pathlib.Path(
        os.environ.get(
            "EXECUTIVE_STATUS_SENTINEL", str(output.with_suffix(".summary.sha256"))
        )
    )
    audit_log = pathlib.Path(
        os.environ.get("EXECUTIVE_STATUS_LOG", str(output.with_suffix(".sync.log")))
    )
    publish_command = os.environ.get("EXECUTIVE_STATUS_PUBLISH_COMMAND", "")
    stale_after = dt.timedelta(
        hours=int(os.environ.get("EXECUTIVE_STATUS_STALE_HOURS", "48"))
    )
    max_length = int(
        os.environ.get(
            "EXECUTIVE_STATUS_MAX_PUBLISH_LENGTH",
            str(DEFAULT_MAX_PUBLISH_LENGTH),
        )
    )
    publish_timeout = float(os.environ.get("EXECUTIVE_STATUS_PUBLISH_TIMEOUT", "90"))
    if stale_after <= dt.timedelta(0):
        raise ValueError("EXECUTIVE_STATUS_STALE_HOURS must be positive")
    if max_length < 200:
        raise ValueError("EXECUTIVE_STATUS_MAX_PUBLISH_LENGTH must be at least 200")
    if publish_timeout <= 0:
        raise ValueError("EXECUTIVE_STATUS_PUBLISH_TIMEOUT must be positive")
    return SyncConfig(
        input_dir=input_dir,
        output=output,
        title=title,
        sentinel=sentinel,
        audit_log=audit_log,
        publish_command=publish_command,
        stale_after=stale_after,
        max_publish_length=max_length,
        publish_timeout=publish_timeout,
        expected_owners=expected_owners(
            os.environ.get("EXECUTIVE_STATUS_EXPECTED_OWNERS", "")
        ),
    )


def publish_if_changed(config: SyncConfig, summary: str, *, disabled: bool) -> bool:
    digest = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    try:
        previous_digest = config.sentinel.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        previous_digest = ""
    if disabled or not config.publish_command or digest == previous_digest:
        return False
    publish_summary(
        config.publish_command,
        summary,
        title=config.title,
        timeout=config.publish_timeout,
    )
    write_if_changed(config.sentinel, digest)
    return True


def run_sync(args: argparse.Namespace, config: SyncConfig) -> int:
    statuses, errors = load_statuses(config.input_dir)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
        log(config.audit_log, f"input_error={error}")
    if not statuses:
        raise ValueError("no valid executive status inputs; preserving existing brief")
    missing = config.expected_owners - {status.owner for status in statuses}
    now = dt.datetime.now().astimezone()
    brief = render_brief(
        statuses,
        now,
        title=config.title,
        missing=missing,
        errors=errors,
        stale_after=config.stale_after,
    )
    summary = render_publish_summary(
        statuses,
        now,
        title=config.title,
        missing=missing,
        errors=errors,
        stale_after=config.stale_after,
        max_length=config.max_publish_length,
    )
    if args.dry_run:
        print(brief)
        print("\n--- Publish preview ---\n")
        print(summary)
        return 1 if errors else 0

    changed = write_if_changed(config.output, brief)
    published = publish_if_changed(config, summary, disabled=args.no_publish)
    event = (
        f"reporting={len(statuses)} missing={len(missing)} errors={len(errors)} "
        f"brief_changed={str(changed).lower()} published={str(published).lower()}"
    )
    log(config.audit_log, event)
    print(event)
    return 1 if errors else 0


def main() -> int:
    args = parse_args()

    try:
        return run_sync(args, load_config())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
