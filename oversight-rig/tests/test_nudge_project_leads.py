from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

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


# Stub gc: serves the payload for `session list --json` and records every
# `session nudge` as "<id>\t<delivery>\t<message>". It parses `session nudge`
# like the real CLI (`gc session nudge <id-or-alias> <message...> [--delivery
# mode]`) and rejects unknown flags and missing arguments, so a call the real
# gc would refuse fails here too. Ids in NUDGE_STUB_FAIL_IDS fail on stderr.
STUB_GC = """\
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1-} ${2-}" == "session list" ]]; then
  cat "$NUDGE_STUB_PAYLOAD"
elif [[ "${1-} ${2-}" == "session nudge" ]]; then
  shift 2
  delivery="wait-idle"
  args=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --delivery)
        if [[ $# -lt 2 ]]; then
          echo "gc: flag needs an argument: --delivery" >&2
          exit 1
        fi
        delivery="$2"
        shift 2
        ;;
      --delivery=*)
        delivery="${1#--delivery=}"
        shift
        ;;
      -*)
        echo "gc: unknown flag: $1" >&2
        exit 1
        ;;
      *)
        args+=("$1")
        shift
        ;;
    esac
  done
  case "$delivery" in
    immediate | wait-idle | queue) ;;
    *)
      echo "gc: invalid delivery mode: $delivery" >&2
      exit 1
      ;;
  esac
  if [[ ${#args[@]} -lt 2 ]]; then
    echo "gc: requires at least 2 arg(s), only received ${#args[@]}" >&2
    exit 1
  fi
  if [[ " ${NUDGE_STUB_FAIL_IDS-} " == *" ${args[0]} "* ]]; then
    echo "gc: session ${args[0]} is not running" >&2
    exit 1
  fi
  printf '%s\t%s\t%s\n' "${args[0]}" "$delivery" "${args[*]:1}" >> "$NUDGE_STUB_LOG"
else
  echo "unexpected gc call: $*" >&2
  exit 2
fi
"""


def run_nudge(
    tmp_path: Path, payload: dict[str, object], fail_ids: tuple[str, ...] = ()
) -> tuple[subprocess.CompletedProcess[str], list[tuple[str, str, str]]]:
    if shutil.which("jq") is None:
        # A skip in CI would let the suite go green without exercising the
        # script, so only local runs may skip.
        if os.environ.get("CI"):
            pytest.fail("jq is required to run nudge-project-leads.sh and CI is set")
        pytest.skip("jq is required to run nudge-project-leads.sh")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    payload_file = tmp_path / "sessions.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")
    nudge_log = tmp_path / "nudges.log"

    stub = bin_dir / "gc"
    stub.write_text(STUB_GC, encoding="utf-8")
    stub.chmod(0o755)

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GC_", "BEADS_"))
    }
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["NUDGE_STUB_PAYLOAD"] = str(payload_file)
    env["NUDGE_STUB_LOG"] = str(nudge_log)
    env["NUDGE_STUB_FAIL_IDS"] = " ".join(fail_ids)

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    lines = nudge_log.read_text(encoding="utf-8").splitlines() if nudge_log.exists() else []
    nudges = [tuple(line.split("\t", 2)) for line in lines]
    return result, nudges


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

    result, nudges = run_nudge(tmp_path, payload)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert sorted(sid for sid, _, _ in nudges) == ["city-lead", "rig-lead"]
    for _, delivery, message in nudges:
        # queue, so a busy lead cannot hold the order past its timeout.
        assert delivery == "queue"
        assert message.startswith("Triage tick:")
    assert "nudged 2 project-lead session(s)" in result.stdout


def test_reports_when_no_project_lead_is_active(tmp_path: Path) -> None:
    payload = session_list_payload(
        [
            session("sleeping-lead", "rematu/oversight-rig.project-lead", state="asleep"),
            session("worker", "rematu/gc.implementation-worker"),
        ]
    )

    result, nudges = run_nudge(tmp_path, payload)

    assert result.returncode == 0, result.stderr
    assert nudges == []
    assert "no active project-lead sessions" in result.stdout


def test_reports_why_a_nudge_failed(tmp_path: Path) -> None:
    payload = session_list_payload(
        [
            session("rig-lead", "rematu/oversight-rig.project-lead"),
            session("gone-lead", "feedlot/oversight-rig.project-lead"),
        ]
    )

    result, nudges = run_nudge(tmp_path, payload, fail_ids=("gone-lead",))

    assert result.returncode == 0, result.stderr
    assert [sid for sid, _, _ in nudges] == ["rig-lead"]
    assert "nudge failed for gone-lead: gc: session gone-lead is not running" in result.stderr
    assert "nudged 1 project-lead session(s)" in result.stdout
