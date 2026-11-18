from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


PACK_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PACK_ROOT / "assets" / "scripts" / "nudge-project-leads.sh"


def session(session_id: str, template: str, state: str = "active") -> dict[str, object]:
    rig = template.split("/", 1)[0] if "/" in template else ""
    return {
        "id": session_id,
        "name": f"session-{session_id}",
        "template": template,
        "provider": "claude",
        "state": state,
        "rig": rig,
        "agent_name": template,
        "attached": False,
        "closed": False,
    }


def session_list_payload(sessions: list[dict[str, object]]) -> dict[str, object]:
    # The shape `gc session list --json` emits: an object, not a bare array.
    return {
        "schema_version": 1,
        "ok": True,
        "filters": {},
        "sessions": sessions,
        "summary": {"total": len(sessions)},
    }


def run_nudge(tmp_path: Path, payload: dict[str, object]) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    if shutil.which("jq") is None:
        pytest.skip("jq is required to run nudge-project-leads.sh")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    payload_file = tmp_path / "sessions.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")
    nudge_log = tmp_path / "nudges.log"

    # Stub gc: serves the payload for `session list --json` and records every
    # `session nudge <id>` target.
    stub = bin_dir / "gc"
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            if [[ "$1 $2" == "session list" ]]; then
              cat {json.dumps(str(payload_file))}
            elif [[ "$1 $2" == "session nudge" ]]; then
              printf '%s\\n' "$3" >> {json.dumps(str(nudge_log))}
            else
              echo "unexpected gc call: $*" >&2
              exit 2
            fi
            """
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GC_", "BEADS_"))
    }
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    nudged = nudge_log.read_text(encoding="utf-8").splitlines() if nudge_log.exists() else []
    return result, nudged


def test_nudges_active_project_leads_with_and_without_rig_prefix(tmp_path: Path) -> None:
    payload = session_list_payload(
        [
            session("rig-lead", "rematu/oversight-rig.project-lead"),
            session("city-lead", "oversight-rig.project-lead"),
            session("sleeping-lead", "feedlot/oversight-rig.project-lead", state="asleep"),
            session("worker", "rematu/gc.implementation-worker"),
            session("lookalike", "rematu/not-oversight-rig.project-lead"),
        ]
    )

    result, nudged = run_nudge(tmp_path, payload)

    assert result.returncode == 0, result.stderr
    assert sorted(nudged) == ["city-lead", "rig-lead"]
    assert "nudged 2 project-lead session(s)" in result.stdout


def test_reports_when_no_project_lead_is_active(tmp_path: Path) -> None:
    payload = session_list_payload(
        [
            session("sleeping-lead", "rematu/oversight-rig.project-lead", state="asleep"),
            session("worker", "rematu/gc.implementation-worker"),
        ]
    )

    result, nudged = run_nudge(tmp_path, payload)

    assert result.returncode == 0, result.stderr
    assert nudged == []
    assert "no active project-lead sessions" in result.stdout
