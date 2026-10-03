#!/usr/bin/env python3
"""Request one structured executive-status input from each configured owner."""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shlex
import string
import subprocess
import sys


SUBJECT = "DIRECTIVE: EXECUTIVE_STATUS"
SUPPORTED_PLACEHOLDERS = frozenset({"agent", "subject", "message"})


def build_message(agent: str, input_dir: pathlib.Path) -> str:
    output = input_dir / f"{agent}.md"
    return (
        f"DIRECTIVE: EXECUTIVE_STATUS — update {output} now. "
        "Write one block fenced by '<!-- executive-status:start -->' and "
        "'<!-- executive-status:end -->' with exactly these one-line fields: "
        "project: plain project name; "
        f"owner: {agent}; "
        "updated: ISO-8601 with timezone; "
        "health: on-track|at-risk|blocked|parked; "
        "current: current outcome or focus; next: next planned outcome; "
        "risk: one material risk or none. Project and owner must be at most 80 "
        "characters. Current, next, and risk must be at most 240 characters. "
        "The executive-status-input frontmatter tag is recommended. Use "
        "CEO-level plain language: omit internal IDs, session names, branches, "
        "paths, formula names, queue counts, and operational incident detail. "
        "Write atomically and replace only your own file."
    )


def discover_agents(agents_dir: pathlib.Path) -> list[str]:
    if not agents_dir.is_dir():
        raise ValueError(f"agents directory does not exist: {agents_dir}")
    return sorted(path.parent.name for path in agents_dir.glob("*-pl/agent.toml"))


def build_dispatch_command(
    template: str,
    *,
    agent: str,
    subject: str,
    message: str,
) -> list[str]:
    formatter = string.Formatter()
    fields = {
        field_name for _, field_name, _, _ in formatter.parse(template) if field_name
    }
    unsupported = fields - SUPPORTED_PLACEHOLDERS
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"unsupported placeholder(s): {names}")
    if "message" not in fields or "agent" not in fields:
        raise ValueError("dispatch command requires {agent} and {message}")
    values = {"agent": agent, "subject": subject, "message": message}
    return [token.format_map(values) for token in shlex.split(template)]


def configured_agents(
    explicit: list[str], agents_dir: pathlib.Path | None
) -> list[str]:
    discovered = discover_agents(agents_dir) if agents_dir else []
    agents = sorted(set(explicit + discovered))
    if not agents:
        raise ValueError("no status owners configured")
    invalid = [
        agent
        for agent in agents
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", agent)
    ]
    if invalid:
        raise ValueError(f"invalid agent name(s): {', '.join(invalid)}")
    return agents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        action="append",
        default=[],
        help="status owner to request; repeat for multiple owners",
    )
    parser.add_argument(
        "--agents-dir",
        type=pathlib.Path,
        default=(
            pathlib.Path(os.environ["EXECUTIVE_STATUS_AGENTS_DIR"])
            if os.environ.get("EXECUTIVE_STATUS_AGENTS_DIR")
            else None
        ),
        help="discover owners from *-pl/agent.toml directories",
    )
    parser.add_argument(
        "--input-dir",
        type=pathlib.Path,
        default=pathlib.Path(
            os.environ.get(
                "EXECUTIVE_STATUS_INPUT_DIR",
                "executive-status/inputs",
            )
        ),
    )
    parser.add_argument(
        "--dispatch-command",
        default=os.environ.get("EXECUTIVE_STATUS_DISPATCH_COMMAND", ""),
        help="shell-free command template using {agent}, {subject}, and {message}",
    )
    parser.add_argument(
        "--subject",
        default=os.environ.get("EXECUTIVE_STATUS_SUBJECT", SUBJECT),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("EXECUTIVE_STATUS_DISPATCH_TIMEOUT", "30")),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print each request without invoking the dispatch command",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        agents = configured_agents(args.agent, args.agents_dir)
        if not args.dry_run and not args.dispatch_command:
            raise ValueError("set --dispatch-command or use --dry-run")

        sent = 0
        failures = 0
        for agent in agents:
            message = build_message(agent, args.input_dir)
            if args.dry_run:
                print(f"[{agent}]\n{message}\n")
                continue
            command = build_dispatch_command(
                args.dispatch_command,
                agent=agent,
                subject=args.subject,
                message=message,
            )
            try:
                subprocess.run(command, timeout=args.timeout, check=True)
                sent += 1
            except (OSError, subprocess.SubprocessError) as exc:
                print(f"ERROR: {agent}: {exc}", file=sys.stderr)
                failures += 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"owners={len(agents)} dispatched={sent} dry_run={str(args.dry_run).lower()}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
