#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from typing import Any

def _timestamp(value: Any) -> dt.datetime:
    text = str(value).strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp has no timezone")
    return parsed


def _read(path: pathlib.Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"state is not an object: {path}")
    return value


def _paths() -> tuple[pathlib.Path, pathlib.Path]:
    city = os.environ.get("GC_CITY_PATH", "").strip()
    directory = pathlib.Path(city) / ".gc" / "slack" if city else pathlib.Path(
        "/tmp/gc-slack-adapter")
    return directory / "event-liveness.json", directory / "outbound-liveness.json"


def _outbound_at(record: dict[str, Any]) -> str:
    if not record.get("last_outbound_at"):
        raise ValueError("outbound state has no post timestamp")
    return str(record["last_outbound_at"])


def _event_at(path: pathlib.Path) -> tuple[str, dt.datetime | None]:
    if not path.exists():
        return "never", None
    event_at = str(_read(path)["last_event_at"])
    return event_at, _timestamp(event_at)


def verdict(*, now: str | None = None, grace_min: int | None = None) -> tuple[int, str]:
    event_path, outbound_path = _paths()
    if not outbound_path.exists():
        return 0, "SLACK EVENTS: no post recorded yet, nothing to compare"
    try:
        outbound = _read(outbound_path)
        post_at = _outbound_at(outbound)
        event_at, event_time = _event_at(event_path)
        post_time = _timestamp(post_at)
        current = _timestamp(now) if now else dt.datetime.now(dt.timezone.utc)
        raw_grace = (str(grace_min) if grace_min is not None else
                     os.environ.get("SLACK_EVENTS_ECHO_GRACE_MIN", "30"))
        grace = int(raw_grace)
        if grace < 0:
            raise ValueError("grace must be nonnegative")
        window = dt.timedelta(minutes=grace)
    except (OSError, OverflowError, ValueError, KeyError, TypeError) as exc:
        return 2, f"SLACK EVENTS: cannot measure ({exc})"
    if event_time is not None and event_time >= post_time:
        return 0, f"SLACK EVENTS HEALTHY: post {post_at}; callback {event_at}"
    if current - post_time <= window:
        return 0, f"SLACK EVENTS HEALTHY: post {post_at}; callback {event_at}"
    return 1, (
        f"SLACK EVENTS STALE: post {post_at}; callback {event_at}; Slack is not "
        "delivering event callbacks; check the Event Subscriptions page on the Slack app config"
    )


def main_at(now: str | None = None) -> int:
    code, line = verdict(now=now)
    print(line)
    return code


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check Slack event callback liveness")
    parser.parse_args(argv)
    return main_at()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
