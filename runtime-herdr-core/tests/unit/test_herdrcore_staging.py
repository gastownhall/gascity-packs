"""Staging what the start config names into the work directory, setup
commands, watch-startup and copy-to."""

from __future__ import annotations

import io
import json
import os
import stat
import threading
import time
from pathlib import Path
from typing import List

import pytest
from cityharness import City

from gc_runtime_herdr_core.herdrcore.staging import StagingError, copy_overlay, stage, stage_path
from gc_runtime_herdr_core.rpp.wire import parse_start_config


def tree(root: Path) -> List[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def overlay(root: Path) -> Path:
    files = {
        "AGENTS.md": "universal",
        ".gc/runtime-mirror": "never staged",
        "per-provider/claude/.claude/settings.json": "claude",
        "per-provider/codex/.codex/hooks.json": "codex",
        "per-provider/codex/.gc/x": "never staged",
        "bin/tool": "#!/bin/sh\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (root / "bin/tool").chmod(0o755)
    return root


def test_overlay_stages_only_the_sessions_provider(tmp_path: Path) -> None:
    src = overlay(tmp_path / "overlay")
    work = tmp_path / "work"
    copy_overlay(str(src), str(work), "codex")
    assert tree(work) == [".codex/hooks.json", "AGENTS.md", "bin/tool"]
    assert stat.S_IMODE((work / "bin/tool").stat().st_mode) == 0o755
    other = tmp_path / "work2"
    copy_overlay(str(src), str(other), "")
    assert tree(other) == ["AGENTS.md", "bin/tool"]


def test_stage_layers_pack_overlays_then_the_agents_then_copy_files(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    (pack / "per-provider/claude").mkdir(parents=True)
    (pack / "AGENTS.md").write_text("pack")
    (pack / "per-provider/claude/CLAUDE.md").write_text("pack-claude")
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "AGENTS.md").write_text("agent")
    extra = tmp_path / "extra.txt"
    extra.write_text("copied")
    work = tmp_path / "work"
    cfg = parse_start_config(
        json.dumps(
            {
                "work_dir": str(work),
                "pack_overlay_dirs": [str(pack), str(tmp_path / "missing")],
                "overlay_dir": str(agent),
                "copy_files": [{"src": str(extra), "rel_dst": "docs"}, {"src": str(extra)}],
            }
        ).encode()
    )
    (work / "docs").mkdir(parents=True)
    stage(cfg, "claude")
    assert (work / "AGENTS.md").read_text() == "agent"
    assert (work / "CLAUDE.md").read_text() == "pack-claude"
    assert (work / "docs/extra.txt").read_text() == "copied"
    assert (work / "extra.txt").read_text() == "copied"


def test_stage_path_merges_directories(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "a/b.txt").write_text("b")
    dst = tmp_path / "dst"
    stage_path(str(src), str(dst))
    assert (dst / "a/b.txt").read_text() == "b"


def test_stage_refuses_a_relative_work_dir() -> None:
    cfg = parse_start_config(b'{"work_dir":"rel","overlay_dir":"/x"}')
    try:
        stage(cfg, "")
    except StagingError as err:
        assert "absolute" in str(err)
    else:
        raise AssertionError("staging into a relative work dir")


def test_start_stages_from_gc_provider_and_runs_setup(city: City) -> None:
    src = overlay(city.root / "overlay")
    work = city.root / "work"
    marker = city.root / "setup.txt"
    config = {
        "command": "cat",
        "work_dir": str(work),
        "overlay_dir": str(src),
        "env": {"GC_PROVIDER": "claude", "GC_AGENT": "mayor", "DROP": ""},
        "pre_start": [f"mkdir -p {work} && echo pre > {work}/pre.txt"],
        "session_setup": [f'echo "$GC_SESSION $GC_AGENT ${{DROP:-unset}}" > {marker}', "exit 7"],
    }
    done = city.run("start", "mc-a", stdin=json.dumps(config).encode(), extra={"DROP": "was-set"})
    assert done.code == 0, done.stderr
    assert "session_setup[1] exited 7" in done.stderr
    assert (work / ".claude/settings.json").read_text() == "claude"
    assert not (work / ".codex").exists()
    assert (work / "pre.txt").read_text().strip() == "pre"
    assert marker.read_text().split() == ["mc-a", "mayor", "unset"]


def test_a_failing_pre_start_fails_the_start_before_any_terminal(city: City) -> None:
    done = city.start("mc-a", json.dumps({"command": "cat", "pre_start": ["exit 3"]}))
    assert done.code == 1 and "pre_start[0] exited 3" in done.stderr
    assert city.terminals() == []


def test_watch_startup_streams_the_screen_on_change(city: City) -> None:
    assert city.start("mc-a", json.dumps({"command": "echo one; sleep 0.5; echo two; exec cat"})).code == 0
    out = io.BytesIO()
    lines: List[str] = []

    from gc_runtime_herdr_core.herdrcore.ops_table import build_ops
    from gc_runtime_herdr_core.rpp.perop import run_per_op

    def watch() -> None:
        env = dict(city.env, GC_EXEC_DEADLINE_MS="3500")
        run_per_op(
            ["x", "watch-startup", "mc-a"],
            env,
            build_ops(city.host),
            started=time.monotonic(),
            stdin=io.BytesIO(),
            stdout=out,
            stderr=io.StringIO(),
            install_signals=False,
        )

    worker = threading.Thread(target=watch, daemon=True)
    worker.start()
    worker.join(timeout=15)
    lines = [json.loads(line)["content"] for line in out.getvalue().decode().splitlines()]
    assert lines and "two" in lines[-1]
    assert len(lines) == len(set(lines)), "a line per change, never a repeat"


def test_copy_to_stays_in_the_work_dir(city: City) -> None:
    work = city.root / "w"
    work.mkdir()
    assert city.start("mc-a", json.dumps({"command": "cat", "work_dir": str(work)})).code == 0
    src = city.root / "f.txt"
    src.write_text("x")
    assert city.run("copy-to", "mc-a", str(src), "sub").code == 0
    assert (work / "sub").read_text() == "x"
    escaped = city.run("copy-to", "mc-a", str(src), "../outside")
    assert escaped.code == 1 and not (city.root / "outside").exists()
    assert os.path.exists(work / "sub")


@pytest.mark.parametrize(
    "rel",
    [".claude/settings.json", ".gemini/settings.json", ".codex/hooks.json", ".cursor/hooks.json", ".agents/hooks.json", ".github/hooks/gascity.json"],
)
def test_files_gc_merges_are_preserved_when_present(tmp_path: Path, rel: str) -> None:
    src = tmp_path / "overlay"
    (src / "per-provider" / "p" / rel).parent.mkdir(parents=True)
    (src / "per-provider" / "p" / rel).write_text('{"from":"overlay"}')
    (src / rel).parent.mkdir(parents=True, exist_ok=True)
    (src / rel).write_text('{"from":"universal"}')
    work = tmp_path / "work"
    (work / rel).parent.mkdir(parents=True)
    (work / rel).write_text('{"mine":true}')
    warnings = copy_overlay(str(src), str(work), "p")
    assert (work / rel).read_text() == '{"mine":true}'
    assert warnings and rel in warnings[0]
    fresh = tmp_path / "fresh"
    assert copy_overlay(str(src), str(fresh), "p") == []
    assert (fresh / rel).read_text() == '{"from":"overlay"}'


def test_an_existing_agents_md_is_kept_from_the_kiro_overlay(tmp_path: Path) -> None:
    src = tmp_path / "overlay"
    (src / "per-provider" / "kiro").mkdir(parents=True)
    (src / "per-provider" / "kiro" / "AGENTS.md").write_text("kiro fallback")
    (src / "AGENTS.md").write_text("universal")
    work = tmp_path / "work"
    work.mkdir()
    (work / "AGENTS.md").write_text("the repo's own")
    copy_overlay(str(src), str(work), "kiro")
    assert (work / "AGENTS.md").read_text() == "universal"  # a universal overlay still overrides, as in gc


def test_setup_commands_never_inherit_hc_scope(city: City) -> None:
    marker = city.root / "scope.txt"
    config = {"command": "cat", "session_setup": [f'echo "${{HC_SCOPE:-none}}" > {marker}']}
    done = city.run("start", "mc-a", stdin=json.dumps(config).encode(), extra={"HC_SCOPE": "1-abc"})
    assert done.code == 0, done.stderr
    assert marker.read_text().strip() == "none"


def test_a_pre_start_may_create_the_work_dir(city: City) -> None:
    work = city.root / "worktree"
    config = {"command": "cat", "work_dir": str(work), "pre_start": [f"mkdir -p {work}"]}
    done = city.start("mc-a", json.dumps(config))
    assert done.code == 0, done.stderr
    missing = city.start("mc-b", json.dumps({"command": "cat", "work_dir": str(city.root / "never")}))
    assert missing.code == 1 and "work_dir" in missing.stderr


def test_session_live_runs_after_the_first_turn_with_warnings_only(city: City) -> None:
    marker = city.root / "live.txt"
    config = {"command": "cat", "session_live": [f'echo "$GC_SESSION" > {marker}', "exit 4"]}
    done = city.start("mc-a", json.dumps(config))
    assert done.code == 0, done.stderr
    assert "session_live[1] exited 4" in done.stderr
    assert marker.read_text().strip() == "mc-a"
