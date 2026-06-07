"""personas — equip-on-task-pickup integration tests (the gas-town seam).

Owns the integration contract for pers-o27 (epic pers-0c9): a polecat equips a
best-fit principal-engineer persona as it picks up its work. Two surfaces:

  * ``overlay/per-provider/claude/.claude/settings.json`` — the SessionStart hook
    ``gc reload`` deep-merges into projected agent settings. It is
    convention-discovered (mirrors model-advisor's Stop/SubagentStop overlay), so
    nothing registers it but its own existence; these tests validate it as data:
    a well-formed SessionStart *command* hook whose command walks
    ``$CLAUDE_PROJECT_DIR`` up to ``packs/personas/hooks/equip-on-task-pickup.sh``
    (the exact marker ``install.sh`` greps projected settings for) and always
    exits clean. One test runs the command against a stub hook in a fake city tree
    to prove the walk-up + stdout pass-through end to end.

  * ``hooks/equip-on-task-pickup.sh`` — run as a real subprocess against a *fake*
    ``bd`` (so nothing touches the live ledger) and a tmp warm cache. Asserts the
    always-exit-0, strictly-best-effort contract: the escape hatch, silence when
    there is no work, a well-formed SessionStart payload for a resolvable bead, and
    graceful no-op when bead resolution fails or ``bd`` is absent.

Hermetic: no live ``bd`` / ``.beads`` / warm cache is touched — every external
dependency is a fake on PATH or a tmp file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parents[1]
HOOK_PATH = PACK_DIR / "hooks" / "equip-on-task-pickup.sh"
OVERLAY_PATH = (
    PACK_DIR / "overlay" / "per-provider" / "claude" / ".claude" / "settings.json"
)

#: The exact substring install.sh's HOOK_MARKER greps projected settings for.
HOOK_MARKER = "personas/hooks/equip-on-task-pickup.sh"

#: A PATH carrying the real coreutils / jq / python3 the hook + engine need.
STD_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

#: Resolve bash once so the executable lookup never depends on the (deliberately
#: minimal) PATH we hand the hook under test.
BASH = shutil.which("bash") or "bash"


# --------------------------------------------------------------------------- #
# helpers                                                                       #
# --------------------------------------------------------------------------- #


def _overlay_command() -> str:
    doc = json.loads(OVERLAY_PATH.read_text())
    return doc["hooks"]["SessionStart"][0]["hooks"][0]["command"]


def _write_fake_bd(bin_dir: Path) -> None:
    """Drop an executable fake ``bd`` that answers ``list`` / ``show`` from env.

    ``bd list ... --json``  -> ``$FAKE_BD_LIST`` (the in-progress lookup the hook does).
    ``bd show <id> --json`` -> ``$FAKE_BD_SHOW`` (what bin/personas builds the task from);
    an unset ``$FAKE_BD_SHOW`` makes ``bd show`` exit 1, simulating a resolution failure.

    Outputs travel as env values, never embedded in the script, so no shell quoting
    of JSON is involved.
    """
    bd = bin_dir / "bd"
    bd.write_text(
        "#!/usr/bin/env bash\n"
        'case "$1" in\n'
        '  list) printf "%s" "${FAKE_BD_LIST:-[]}" ;;\n'
        '  show) [ -n "${FAKE_BD_SHOW:-}" ] && printf "%s" "$FAKE_BD_SHOW" || exit 1 ;;\n'
        '  *) printf "%s" "[]" ;;\n'
        "esac\n"
    )
    bd.chmod(0o755)


def _run_hook(payload: str, env_extra: dict, path: str) -> subprocess.CompletedProcess:
    """Run the real hook script as Claude Code would, with a controlled environment."""
    env = dict(os.environ)
    # Drop any inherited polecat identity / cache so each test controls resolution.
    for k in ("GC_SESSION_NAME", "GC_SESSION_ID", "GC_ALIAS", "PERSONAS_CACHE_FILE",
              "PERSONAS_CACHE_DIR", "PERSONAS_DISABLE_EQUIP"):
        env.pop(k, None)
    env.update(env_extra)
    env["PATH"] = path
    return subprocess.run(
        [BASH, str(HOOK_PATH)],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
    )


# --------------------------------------------------------------------------- #
# the overlay: well-formed, correctly targeted, deep-merge-friendly             #
# --------------------------------------------------------------------------- #


def test_overlay_is_wellformed_sessionstart_command_hook():
    doc = json.loads(OVERLAY_PATH.read_text())  # must be valid JSON for gc reload
    sessionstart = doc["hooks"]["SessionStart"]
    assert isinstance(sessionstart, list) and sessionstart
    inner = sessionstart[0]["hooks"]
    assert isinstance(inner, list) and inner
    entry = inner[0]
    assert entry["type"] == "command"
    assert isinstance(entry["command"], str) and entry["command"].strip()


def test_overlay_only_registers_sessionstart():
    # Equip is a SessionStart concern; keeping the overlay to that single event is
    # what lets it deep-merge cleanly alongside e.g. model-advisor's Stop hooks.
    doc = json.loads(OVERLAY_PATH.read_text())
    assert list(doc["hooks"].keys()) == ["SessionStart"]


def test_overlay_command_targets_pack_hook_and_is_best_effort():
    cmd = _overlay_command()
    assert HOOK_MARKER in cmd  # exactly what install.sh verifies got projected
    assert "packs/personas/hooks/equip-on-task-pickup.sh" in cmd
    assert "$CLAUDE_PROJECT_DIR" in cmd  # resolves from the agent's project dir
    # The trailing `; true` guarantees the command never fails a session start even
    # if the walk-up finds nothing — equip is strictly best-effort.
    assert cmd.rstrip().endswith("true")


def test_overlay_command_walks_up_to_hook_and_passes_stdout_through(tmp_path):
    """Lay out <root>/packs/personas/hooks/<hook> and a deeply nested project dir;
    the overlay command must walk up, run the hook, and surface its stdout."""
    hook = tmp_path / "packs" / "personas" / "hooks" / "equip-on-task-pickup.sh"
    hook.parent.mkdir(parents=True)
    hook.write_text(
        "#!/usr/bin/env bash\n"
        "cat >/dev/null\n"  # drain stdin, like the real hook
        'printf "%s\\n" '
        "'{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\","
        '"additionalContext":"STUB"}}\'\n'
    )
    hook.chmod(0o755)
    deep = tmp_path / "rig" / "wt" / "a" / "b"
    deep.mkdir(parents=True)

    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(deep)
    env["PATH"] = STD_PATH
    proc = subprocess.run(
        [BASH, "-c", _overlay_command()],
        input="{}",
        text=True,
        capture_output=True,
        env=env,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert payload["hookSpecificOutput"]["additionalContext"] == "STUB"


def test_overlay_command_is_silent_noop_without_project_dir():
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env["PATH"] = STD_PATH
    proc = subprocess.run(
        [BASH, "-c", _overlay_command()],
        input="{}",
        text=True,
        capture_output=True,
        env=env,
    )
    assert proc.returncode == 0
    assert proc.stdout == ""


# --------------------------------------------------------------------------- #
# the hook: best-effort, always exit 0, emits a SessionStart payload on a hit   #
# --------------------------------------------------------------------------- #


def test_hook_escape_hatch_writes_nothing():
    proc = _run_hook("{}", {"PERSONAS_DISABLE_EQUIP": "1"}, STD_PATH)
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_hook_no_in_progress_bead_is_silent(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_bd(bin_dir)
    proc = _run_hook(
        "{}",
        {"GC_SESSION_NAME": "agent-x", "FAKE_BD_LIST": "[]"},
        f"{bin_dir}:{STD_PATH}",
    )
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_hook_emits_sessionstart_payload_for_resolved_bead(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_bd(bin_dir)
    cache = tmp_path / "warm-cache.json"
    proc = _run_hook(
        "{}",
        {
            "GC_SESSION_NAME": "agent-x",
            "FAKE_BD_LIST": '[{"id":"hooktest-1"}]',
            "FAKE_BD_SHOW": (
                '[{"id":"hooktest-1",'
                '"title":"Refactor the database query layer for performance",'
                '"description":"backend service hot path"}]'
            ),
            "PERSONAS_CACHE_FILE": str(cache),
        },
        f"{bin_dir}:{STD_PATH}",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    hso = payload["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "Equipped persona" in hso["additionalContext"]
    # Equip materialized into the *tmp* warm cache, never the live one.
    assert cache.exists()


def test_hook_resolves_bead_via_session_id_when_name_unset(tmp_path):
    """The identity loop falls through name -> id -> alias; with only GC_SESSION_ID
    set it must still resolve and emit."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_bd(bin_dir)
    cache = tmp_path / "warm-cache.json"
    proc = _run_hook(
        "{}",
        {
            "GC_SESSION_ID": "bh-wisp-x",
            "FAKE_BD_LIST": '[{"id":"hooktest-2"}]',
            "FAKE_BD_SHOW": (
                '[{"id":"hooktest-2","title":"Write API reference docs",'
                '"description":"documentation for the public endpoints"}]'
            ),
            "PERSONAS_CACHE_FILE": str(cache),
        },
        f"{bin_dir}:{STD_PATH}",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_hook_exits_zero_when_bead_show_fails(tmp_path):
    """A resolvable in-progress bead whose `bd show` fails: equip --from-bead can't
    build a task, prints nothing, and the hook still exits 0 (never blocks)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_bd(bin_dir)  # FAKE_BD_SHOW unset -> `bd show` exits 1
    cache = tmp_path / "warm-cache.json"
    proc = _run_hook(
        "{}",
        {
            "GC_SESSION_NAME": "agent-x",
            "FAKE_BD_LIST": '[{"id":"hooktest-1"}]',
            "PERSONAS_CACHE_FILE": str(cache),
        },
        f"{bin_dir}:{STD_PATH}",
    )
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_hook_exits_zero_when_bd_unavailable(tmp_path):
    """No `bd` on PATH at all: the hook's `command -v bd` guard short-circuits to a
    clean exit 0 with no output."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # A PATH with just enough coreutils for the hook to run up to the bd guard.
    for tool in ("cat", "dirname"):
        src = shutil.which(tool)
        if src:
            os.symlink(src, bin_dir / tool)
    proc = _run_hook("{}", {"GC_SESSION_NAME": "agent-x"}, str(bin_dir))
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_hook_script_is_executable_and_documents_the_contract():
    assert HOOK_PATH.exists()
    assert os.access(HOOK_PATH, os.X_OK), "hook must be executable for the overlay to run it"
    text = HOOK_PATH.read_text()
    # The contract the overlay and tests depend on.
    assert "PERSONAS_DISABLE_EQUIP" in text
    assert "--emit-context" in text
    assert "exit 0" in text
