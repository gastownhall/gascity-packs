#!/usr/bin/env python3
"""Real BB -> GC -> Claude/Codex smoke gate. Never uses an existing city or BB store.

All state and raw logs stay in a new private /tmp directory. Only the explicit
report directory is suitable for CI upload; provider state can contain secrets.
Missing credentials, incomplete turns and setup/cleanup failures are failures.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

PACK = Path(__file__).resolve().parents[1]
CORE_COMMITS = {
    "1.4.0": "a7297c511d637a3609947386f3389d76ddb2f23b",
    "1.4.1": "58ef17e3bd685fd5cf7f21286277b208d3324590",
}


class GateError(Exception):
    pass


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    path.chmod(0o600)


def ports():
    sockets = [socket.socket() for _ in range(3)]
    try:
        for sock in sockets:
            sock.bind(("127.0.0.1", 0))
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, choices=["claude", "codex"])
    parser.add_argument("--gc-bin", required=True)
    parser.add_argument("--bb-bin", required=True)
    parser.add_argument("--bb-app-bin", required=True)
    parser.add_argument("--report-dir", required=True, type=Path,
                        help="New directory for safe CI reports, never raw state")
    parser.add_argument("--timeout", type=int, default=240, help="Seconds per model turn")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    args.report_dir = args.report_dir.resolve()
    args.report_dir.mkdir(parents=True, exist_ok=False)
    os.umask(0o077)
    # /tmp + an alphabetic suffix avoids known GC 1.4/Claude slug disagreement.
    root = Path(tempfile.mkdtemp(prefix="bb-live-", dir="/tmp")).resolve()
    if "_" in str(root):
        # mkdtemp can generate underscores; create a separate unused child path
        # outside that root for workspaces (only workspaces are slug encoded).
        workspace_root = Path("/tmp").resolve() / ("bb-work-" + root.name.replace("_", "-"))
        workspace_root.mkdir(exist_ok=False, mode=0o700)
    else:
        workspace_root = root / "workspaces"
        workspace_root.mkdir()
    city = root / "city"
    city.mkdir()
    gc_port, bb_port, host_port = ports()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GC_", "BB_", "BEADS_", "CODEX_", "CLAUDE_"))}
    # Explicit credential inputs only; never copy a user's normal runtime store.
    for key in ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_SUBAGENT_MODEL",
                "CLAUDE_CODE_EFFORT_LEVEL"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    env.update({
        "GC_HOME": str(root / "gc-home"), "GC_DISABLE_USAGE_METRICS": "1",
        "GC_BB_CONFIG": str(root / "config/bb.json"),
        "GC_BB_INSTALL_DIR": str(root / "installed-plugin"),
        "XDG_CONFIG_HOME": str(root / "config"), "XDG_STATE_HOME": str(root / "state"),
        "XDG_DATA_HOME": str(root / "data"), "BB_DATA_DIR": str(root / "bb-data"),
        "BB_SERVER_PORT": str(bb_port), "BB_HOST_DAEMON_PORT": str(host_port),
        "BB_SERVER_URL": f"http://127.0.0.1:{bb_port}", "BB_SERVER_BIND_HOST": "127.0.0.1",
        "CLAUDE_CONFIG_DIR": str(root / "claude-config"),
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CODEX_HOME": str(root / "codex-config"),
        "PATH": os.pathsep.join([str(Path(args.gc_bin).absolute().parent),
                                  str(Path(args.bb_bin).absolute().parent), os.environ["PATH"]]),
    })
    commands = {"gc": str(Path(args.gc_bin).absolute()),
                "bb": str(Path(args.bb_bin).absolute()),
                "app": str(Path(args.bb_app_bin).absolute())}
    report = {"runtime": args.runtime, "status": "failed", "stages": [], "scopes": [],
              "commit": os.environ.get("GITHUB_SHA"), "coverage": "two-turn-tool-smoke"}
    started_gc = started_bb = False
    app_process = None
    command_count = 0

    def progress(stage):
        report["stages"].append(stage)
        print(f"[{args.runtime}] {stage}", flush=True)

    def run(program, *argv, timeout=60, check=True):
        nonlocal command_count
        command_count += 1
        # Arguments and model/server output are private, not CI console output.
        log = root / f"command-{command_count:03d}.log"
        try:
            result = subprocess.run([commands.get(program, program), *map(str, argv)],
                                    env=env, cwd=city if program == "gc" else root,
                                    text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise GateError(f"{program} command {command_count} timed out") from error
        log.write_text(result.stdout + "\n" + result.stderr)
        if check and result.returncode:
            raise GateError(f"{program} command {command_count} failed (exit {result.returncode}); private log {log.name}")
        return result

    def wait_for(label, probe, timeout=90):
        deadline = time.monotonic() + timeout
        last_update = 0
        while time.monotonic() < deadline:
            result = probe()
            if result:
                return result
            if time.monotonic() - last_update >= 15:
                print(f"[{args.runtime}] waiting for {label}", flush=True)
                last_update = time.monotonic()
            time.sleep(2)
        raise GateError(f"Timed out waiting for {label}")

    try:
        progress("Checking credentials and exact installed versions")
        if args.runtime == "claude" and not any(env.get(k) for k in
                ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")):
            raise GateError("Missing Claude inference credentials; this gate cannot pass without inference")
        if args.runtime == "codex":
            auth_file = os.environ.get("BB_ACCEPTANCE_CODEX_AUTH_FILE")
            if auth_file:
                save_new(root / "codex-config/auth.json", json.loads(Path(auth_file).read_text()))
            elif env.get("OPENAI_API_KEY"):
                save_new(root / "codex-config/auth.json", {"OPENAI_API_KEY": env["OPENAI_API_KEY"]})
            else:
                raise GateError("Missing OPENAI_API_KEY (CI: BB_CODEX_API_KEY) or BB_ACCEPTANCE_CODEX_AUTH_FILE; Codex inference is required")
        for binary in ("node", "tmux", args.runtime):
            if not shutil.which(binary, path=env["PATH"]):
                raise GateError(f"Missing required executable: {binary}")
        gc_version = run("gc", "version").stdout.strip().split()[0]
        if gc_version not in CORE_COMMITS:
            raise GateError("Live acceptance requires released GC 1.4.0 or 1.4.1")
        report["versions"] = {"gc": gc_version,
                              "bb": run("bb", "--version").stdout.strip(),
                              args.runtime: run(args.runtime, "--version").stdout.strip()}
        workspaces = {scope: workspace_root / scope for scope in ("global", "rig")}
        for workspace in workspaces.values():
            workspace.mkdir()
            run("git", "init", str(workspace))
        projects = {str(p): {"hasTrustDialogAccepted": True,
                            "hasCompletedProjectOnboarding": True,
                            "projectOnboardingSeenCount": 1} for p in workspaces.values()}
        save_new(root / "claude-config/.claude.json", {
            "hasCompletedOnboarding": True, "theme": "dark", "projects": projects})
        (root / "codex-config").mkdir(exist_ok=True)
        with (root / "codex-config/config.toml").open("x") as stream:
            for workspace in workspaces.values():
                stream.write(f'[projects.{json.dumps(str(workspace))}]\ntrust_level = "trusted"\n')
        (city / ".gc").mkdir()
        (root / "gc-home").mkdir()
        (root / "gc-home/supervisor.toml").write_text(
            f'[supervisor]\nport = {gc_port}\nbind = "127.0.0.1"\nallow_mutations = true\n')
        city_name = root.name.replace("_", "-")
        (city / ".gc/site.toml").write_text(
            f'workspace_name = {json.dumps(city_name)}\n[[rig]]\nname = "sample"\n'
            f'path = {json.dumps(str(workspaces["rig"]))}\n')
        (city / "pack.toml").write_text(
            '[pack]\nname = "bb-live-acceptance"\nschema = 2\n'
            f'[imports.bb]\nsource = {json.dumps(str(PACK))}\n'
            f'[imports.core]\nsource = "https://github.com/gastownhall/gascity/tree/v{gc_version}/internal/bootstrap/packs/core"\n'
            f'version = "sha:{CORE_COMMITS[gc_version]}"\n')
        (city / "city.toml").write_text(
            f'[workspace]\nprovider = "{args.runtime}"\n[beads]\nprovider = "file"\n'
            f'[session]\nprovider = "tmux"\nsocket = "{city_name}"\n'
            f'[providers.{args.runtime}]\nbase = "builtin:{args.runtime}"\n'
            '[[rigs]]\nname = "sample"\n[daemon]\n'
            f'observe_paths = {json.dumps([str(root / "claude-config/projects"), str(root / "codex-config/sessions")])}\n')
        for scope, workspace in workspaces.items():
            agent_dir = city / "agents" / scope
            agent_dir.mkdir(parents=True)
            (agent_dir / "agent.toml").write_text(
                ('dir = "sample"\n' if scope == "rig" else '') +
                f'name = "{scope}"\nprovider = "{args.runtime}"\n'
                f'work_dir = {json.dumps(str(workspace))}\nmin_active_sessions = 0\nmax_active_sessions = 2\n'
                f'[env]\nCLAUDE_CONFIG_DIR = {json.dumps(env["CLAUDE_CONFIG_DIR"])}\n'
                f'CODEX_HOME = {json.dumps(env["CODEX_HOME"])}\n')
        progress("Starting disposable GC supervisor and released BB server/host")
        run("gc", "import", "install", timeout=180)
        started_gc = True  # cleanup also handles a partial start
        run("gc", "start", timeout=180)
        started_bb = True
        app_log = (root / "bb-app.log").open("x")
        app_process = subprocess.Popen([commands["app"]], env=env, cwd=root,
                                       stdout=app_log, stderr=subprocess.STDOUT)
        app_log.close()
        # Reap concurrently: bb-app stop checks PID existence. An unreaped
        # child looks alive to it even after a successful shutdown.
        threading.Thread(target=app_process.wait, daemon=True).start()

        def hosts():
            if app_process.poll() is not None:
                raise GateError("BB launcher exited before its host connected")
            result = run("bb", "machine", "list", "--json", timeout=20, check=False)
            if result.returncode:
                return None
            return [host for host in json.loads(result.stdout) if host["status"] == "connected"]

        connected = wait_for("BB execution host", hosts)
        if len(connected) != 1:
            raise GateError("Fresh BB store must have exactly one connected execution host")
        host = connected[0]["id"]
        progress("Installing this checkout and binding the exact standard project")
        project = json.loads(run("bb", "project", "create", "--name", "BB live acceptance",
                                 "--root", workspace_root, "--host", host, "--json").stdout)["id"]
        run("gc", "bb", "install", "--yes", timeout=180)
        run("gc", "bb", "connect", "--id", "local", "--url", f"http://127.0.0.1:{gc_port}")
        run("gc", "bb", "bind", "--project", project, "--city", city_name,
            "--rig", "sample", "--path", workspace_root)
        catalog = json.loads(run("gc", "bb", "agents", "--project", project, "--json").stdout)
        for scope, workspace in workspaces.items():
            progress(f"Running real {scope} agent: full prompt, two completions, tool artifact")
            name = "sample/rig" if scope == "rig" else "global"
            targets = [agent for agent in catalog["agents"] if agent["agent"] == name]
            if len(targets) != 1:
                raise GateError(f"Expected one exact {scope} agent in the discovered catalog")
            result = subprocess.run([
                sys.executable, str(PACK / "tests/live_assertions.py"),
                "--bb-bin", commands["bb"], "--host", host, "--project", project,
                "--model", targets[0]["id"], "--workspace", str(workspace),
                "--artifacts", str(args.report_dir / scope), "--timeout", str(args.timeout),
            ], env=env, cwd=root, timeout=args.timeout * 2 + 180)
            report["scopes"].append({"scope": scope, "status": "passed" if result.returncode == 0 else "failed"})
        if len(report["scopes"]) != 2 or any(row["status"] != "passed" for row in report["scopes"]):
            raise GateError("Real conversation acceptance failed; inspect scope reports")
        report["status"] = "passed"
    except (GateError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        report["failure"] = str(error) if isinstance(error, GateError) else type(error).__name__
        print(f'[{args.runtime}] FAIL: {report["failure"]}', flush=True)
    finally:
        progress("Stopping only the disposable services; preserving private state")
        if started_gc:
            try:
                panes = run("tmux", "-L", city_name, "list-panes", "-a", "-F", "#{pane_id}", check=False)
                if panes.returncode == 0:
                    for pane in panes.stdout.splitlines():
                        run("tmux", "-L", city_name, "capture-pane", "-p", "-t", pane, "-S", "-", check=False)
            except (GateError, OSError):
                report["status"] = "failed"
                report.setdefault("cleanupFailures", []).append("Could not capture disposable tmux evidence")
        for started, program, argv in (
            (started_bb, "app", ["stop"]),
            (started_gc, "gc", ["stop", "--timeout", "30s"]),
            (started_gc, "gc", ["supervisor", "stop", "--wait", "--wait-timeout", "30s"]),
        ):
            if started:
                try:
                    run(program, *argv, timeout=45)
                except (GateError, OSError) as error:
                    report["status"] = "failed"
                    report.setdefault("cleanupFailures", []).append(str(error))
        if app_process:
            try:
                app_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                report["status"] = "failed"
                report.setdefault("cleanupFailures", []).append("BB launcher did not exit after stop")
        save_new(args.report_dir / "summary.json", report)
        print(f'[{args.runtime}] {report["status"].upper()}; report: {args.report_dir}; private state: {root}', flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
