from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

PACK_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACK_DIR / "scripts"))


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setenv("GC_CITY_NAME", "test-city")
    monkeypatch.delenv("SLACK_EVENTS_ECHO_GRACE_MIN", raising=False)


def _write_state(tmp_path: pathlib.Path, post: str, event: str | None) -> None:
    state = tmp_path / ".gc" / "slack"
    state.mkdir(parents=True)
    (state / "outbound-liveness.json").write_text(
        json.dumps({"last_outbound_at": post}), encoding="utf-8")
    if event is not None:
        (state / "event-liveness.json").write_text(
            json.dumps({"last_event_at": event, "last_event_type": "message", "count": 1}),
            encoding="utf-8")


def _module():
    sys.modules.pop("slack_events_health", None)
    import slack_events_health
    return slack_events_health


def test_callback_after_post_is_healthy(tmp_path: pathlib.Path, capsys) -> None:
    _write_state(tmp_path, "2026-10-08T12:00:00Z", "2026-10-08T12:01:00Z")
    assert _module().main_at("2026-10-08T12:02:00Z") == 0
    assert "HEALTHY" in capsys.readouterr().out


def test_old_post_without_callback_is_stale(tmp_path: pathlib.Path, capsys) -> None:
    _write_state(tmp_path, "2026-10-08T10:00:00Z", "2026-10-08T09:00:00Z")
    assert _module().main_at("2026-10-08T11:00:01Z") == 1
    assert "STALE" in capsys.readouterr().out


def test_recent_post_is_healthy(tmp_path: pathlib.Path) -> None:
    _write_state(tmp_path, "2026-10-08T11:00:00Z", "2026-10-08T09:00:00Z")
    assert _module().verdict(
        now="2026-10-08T11:00:01Z", grace_min=30,
    )[0] == 0


def test_missing_state_is_unreadable(tmp_path: pathlib.Path, capsys) -> None:
    assert _module().main([]) == 2
    assert "cannot measure" in capsys.readouterr().out


def test_grace_environment_is_honored(tmp_path: pathlib.Path, monkeypatch) -> None:
    _write_state(tmp_path, "2026-10-08T10:00:00Z", "2026-10-08T09:00:00Z")
    monkeypatch.setenv("SLACK_EVENTS_ECHO_GRACE_MIN", "90")
    assert _module().main_at("2026-10-08T11:00:01Z") == 0


def test_naive_timestamp_is_unreadable(tmp_path: pathlib.Path) -> None:
    _write_state(tmp_path, "2026-10-08T10:00:00", "2026-10-08T09:00:00Z")
    assert _module().verdict(now="2026-10-08T11:00:01Z")[0] == 2


def test_negative_grace_is_unreadable(tmp_path: pathlib.Path, monkeypatch) -> None:
    _write_state(tmp_path, "2026-10-08T10:00:00Z", "2026-10-08T09:00:00Z")
    monkeypatch.setenv("SLACK_EVENTS_ECHO_GRACE_MIN", "-1")
    assert _module().main_at("2026-10-08T11:00:01Z") == 2


def test_huge_grace_is_unreadable(tmp_path: pathlib.Path, monkeypatch) -> None:
    _write_state(tmp_path, "2026-10-08T10:00:00Z", "2026-10-08T09:00:00Z")
    monkeypatch.setenv("SLACK_EVENTS_ECHO_GRACE_MIN", "9" * 4000)
    assert _module().main_at("2026-10-08T11:00:01Z") == 2


def test_corrupt_state_is_unreadable(tmp_path: pathlib.Path) -> None:
    state = tmp_path / ".gc" / "slack"
    state.mkdir(parents=True)
    (state / "event-liveness.json").write_text("{", encoding="utf-8")
    (state / "outbound-liveness.json").write_text("{}", encoding="utf-8")
    assert _module().verdict()[0] == 2


def test_command_and_doctor_wrappers_run(tmp_path: pathlib.Path) -> None:
    _write_state(tmp_path, "2026-10-08T12:00:00Z", "2026-10-08T12:01:00Z")
    env = {**os.environ, "GC_PACK_DIR": str(PACK_DIR), "GC_CITY_PATH": str(tmp_path)}
    command = subprocess.run(
        [str(PACK_DIR / "commands/events-health.sh")], env=env,
        capture_output=True, text=True, check=False,
    )
    doctor = subprocess.run(
        [str(PACK_DIR / "doctor/check-events-health.sh")], env=env,
        capture_output=True, text=True, check=False,
    )
    assert command.returncode == doctor.returncode == 0


def test_status_exit_semantics_ignore_stale_health(tmp_path: pathlib.Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    _write_state(tmp_path, "2026-10-08T10:00:00Z", "2026-10-08T09:00:00Z")
    sys.modules.pop("slack_chat_status", None)
    import slack_chat_status

    def fake_request(method, url, body=None, *, csrf=True, timeout=30.0):
        if "/extmsg/adapters" in url:
            return {"items": []}
        return {"items": []}

    import slack_intake_common
    monkeypatch.setattr(slack_intake_common, "_request", fake_request)
    assert slack_chat_status.main([]) == 0


def test_old_post_with_no_callback_ever_is_stale(tmp_path: pathlib.Path, capsys) -> None:
    _write_state(tmp_path, "2026-10-08T10:00:00Z", None)
    assert _module().main_at("2026-10-08T11:00:01Z") == 1
    assert "callback never" in capsys.readouterr().out


def test_recent_post_with_no_callback_ever_is_healthy(tmp_path: pathlib.Path) -> None:
    _write_state(tmp_path, "2026-10-08T11:00:00Z", None)
    assert _module().verdict(now="2026-10-08T11:10:00Z", grace_min=30)[0] == 0
