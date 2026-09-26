#!/usr/bin/env python3
"""Exact GC hook onboarding for disposable Codex 0.153.4 acceptance cities.

Uses native per-handler trust, never the invocation-wide bypass. Hashes were
reviewed in Codex's /hooks UI and checked against rust-v0.153.4:
codex-rs/hooks/src/engine/discovery.rs (hook_hash) and src/lib.rs (hook_key).
The hash excludes the source path; the persisted key includes it.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import sys

CODEX_VERSION = "codex-cli 0.153.4"
PREFIX = 'export PATH="$HOME/go/bin:$HOME/.local/bin:$PATH" && '
REVIEWED = (
    ("PreCompact", "pre_compact", 0,
     'gc handoff --auto --hook-format codex "context cycle"',
     "bee211b62b8da88e328988459beb14de6916eaa426323994d9a7ea9a25d8e386"),
    ("SessionStart", "session_start", 0,
     "GC_MANAGED_SESSION_HOOK=1 GC_HOOK_EVENT_NAME=SessionStart gc prime --hook --hook-format codex",
     "10ff376f8efe2e535077b7600c0cda5dea8539e872fa2ca1f0e8a5455c50fdf6"),
    ("UserPromptSubmit", "user_prompt_submit", 0,
     "gc hook run --timeout 15s --timeout-exit-code 0 -- nudge drain --inject --hook-format codex",
     "4fa9de4c2dfb3774df70354a095e680c079f451e46074894b0b53b8a7fcd708e"),
    ("UserPromptSubmit", "user_prompt_submit", 1,
     "gc hook run --timeout 15s --timeout-exit-code 0 -- mail check --inject --hook-format codex",
     "e6c6f7c552feb7aaf44febe3d3bbe447407537db3f88ea318606025328b184d3"),
)


def expected_hooks():
    events = {}
    for event, _, _, command, _ in REVIEWED:
        group = events.setdefault(event, [{"matcher": "", "hooks": []}])[0]
        group["hooks"].append({"command": PREFIX + command, "type": "command"})
    return {"hooks": events}


def verify_gc_hooks(workspace):
    directory = Path(workspace) / ".codex"
    source = directory / "hooks.json"
    if directory.is_symlink() or source.is_symlink():
        raise ValueError("Reviewed GC hooks must be regular files in the test workspace")
    value = json.loads(source.read_text())
    if value != expected_hooks():
        raise ValueError("Generated Codex hooks differ from the four reviewed GC hooks")
    return value


def trust_config(workspaces, codex_version):
    if codex_version != CODEX_VERSION:
        raise ValueError("Native hook trust requires reviewed Codex 0.153.4")
    text = []
    for workspace in workspaces:
        source = Path(workspace).resolve() / ".codex/hooks.json"
        for _, event_key, handler_index, _, digest in REVIEWED:
            key = f"{source}:{event_key}:0:{handler_index}"
            text.append(f'[hooks.state.{json.dumps(key)}]\ntrusted_hash = "sha256:{digest}"\n')
    return "".join(text)


def verify_launch(workspace, codex_home, workspaces, env):
    workspace = Path(workspace).resolve()
    if workspace not in {Path(p).resolve() for p in workspaces}:
        raise ValueError("Codex hook onboarding is restricted to its test workspaces")
    if not env.get("CODEX_HOME") or Path(env["CODEX_HOME"]).resolve() != Path(codex_home).resolve():
        raise ValueError("Codex hook onboarding requires its isolated CODEX_HOME")
    verify_gc_hooks(workspace)


def write_provider_commands(root, codex_bin, codex_home, workspaces):
    """Write the executable GC resolves and its explicit wrapped resume command."""
    wrapper = [sys.executable, str(Path(__file__).resolve()),
               "--codex-bin", str(codex_bin), "--codex-home", str(codex_home)]
    for workspace in workspaces:
        wrapper.extend(["--workspace", str(workspace)])
    wrapper.append("--")
    launcher = Path(root) / "codex-verified"
    with launcher.open("x") as stream:
        stream.write('#!/bin/sh\nexec ' + shlex.join(wrapper) + ' "$@"\n')
    launcher.chmod(0o700)
    return (f'command = {json.dumps(str(launcher))}\n'
            f'resume_command = {json.dumps(shlex.quote(str(launcher)) + " resume {{.SessionKey}}")}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--codex-home", required=True)
    parser.add_argument("--workspace", action="append", required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        verify_launch(Path.cwd(), args.codex_home, args.workspace, os.environ)
    except (OSError, ValueError) as error:
        print(f"Codex acceptance hook verification failed: {error}", file=sys.stderr)
        return 1
    forwarded = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    # Native trust remains enabled. Only the exact four hashes at the known
    # source paths were seeded; other hooks retain Codex's normal review gate.
    os.execv(args.codex_bin, [args.codex_bin, *forwarded])


if __name__ == "__main__":
    sys.exit(main())
