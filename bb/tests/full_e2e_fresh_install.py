"""Fresh BB installation against the already running, owned Gas City controller.

This case starts only another isolated BB server/host. It never starts, stops,
reconfigures, or installs a pack into the existing GC controller or BB store.
All new processes, settings, receipts and outputs remain available afterward.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error

from full_e2e import Runner, read_json
from full_e2e_fault_cases import require_owned_config
from live_assertions import AcceptanceFailure


def fresh_environment(original, root, directory, bb_port, host_port):
    root, directory = Path(root).resolve(), Path(directory).resolve()
    if not directory.is_relative_to(root) or directory == root:
        raise AcceptanceFailure("Fresh installation escapes the existing owned root")
    if (bb_port == host_port or any(type(port) is not int or not 1024 <= port <= 65535
                                   or port in {38886, 8372} for port in (bb_port, host_port))):
        raise AcceptanceFailure("Fresh BB requires separate nonstandard ports")
    env = dict(original)
    # Reuse the already installed test browser executable. Moving application
    # cache storage must not silently select an empty Playwright installation.
    if not env.get("PLAYWRIGHT_BROWSERS_PATH"):
        home = Path(original.get("HOME") or Path.home())
        cache = home / "Library/Caches" if sys.platform == "darwin" else Path(original.get("XDG_CACHE_HOME") or home / ".cache")
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(cache / "ms-playwright")
    env.update(BB_DATA_DIR=str(directory / "bb-data"), BB_SERVER_PORT=str(bb_port),
        BB_HOST_DAEMON_PORT=str(host_port), BB_SERVER_URL=f"http://127.0.0.1:{bb_port}",
        BB_SERVER_BIND_HOST="127.0.0.1", GC_BB_CONFIG=str(directory / "config/bb.json"),
        GC_BB_INSTALL_DIR=str(directory / "installed-plugin"), XDG_CONFIG_HOME=str(directory / "config"),
        XDG_STATE_HOME=str(directory / "state"), XDG_DATA_HOME=str(directory / "data"),
        XDG_CACHE_HOME=str(directory / "cache"))
    # GC_HOME and runtime credential/config inputs continue to refer to the
    # same isolated controller and its existing agent definitions.
    if env["GC_HOME"] != original["GC_HOME"] or env.get("HOME") != original.get("HOME"):
        raise AcceptanceFailure("Fresh BB must preserve GC and home environments")
    return env


def check_gc_read_or_pack_command(args):
    if tuple(args[:2]) not in {("bb", "install"), ("bb", "connect"), ("bb", "agents"), ("supervisor", "status")}:
        raise AcceptanceFailure("Fresh BB setup cannot mutate the GC controller lifecycle")


def new_json(path, value):
    with Path(path).open("x") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(value, output, indent=2); output.write("\n")


def unused_ports():
    sockets = [socket.socket(), socket.socket()]
    try:
        for sock in sockets: sock.bind(("127.0.0.1", 0))
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets: sock.close()


def prepare_fresh(runner):
    require_owned_config(runner)
    directory = runner.root / ("fresh-install-" + runner.runtime + "-" + secrets.token_hex(6))
    directory.mkdir(mode=0o700, exist_ok=False)
    bb_port, host_port = unused_ports()
    env = fresh_environment(runner.env, runner.root, directory, bb_port, host_port)
    state = Path(env["BB_DATA_DIR"])
    if state.exists(): raise AcceptanceFailure("Fresh BB store already exists")
    new_json(directory / "environment.json", env)
    count = 0
    def run(kind, *args, timeout=90, parse_json=True):
        nonlocal count
        if kind == "gc": check_gc_read_or_pack_command(args)
        count += 1
        output, errors = directory / f"setup-{count:03}.stdout", directory / f"setup-{count:03}.stderr"
        with output.open("x") as stdout, errors.open("x") as stderr:
            process = subprocess.Popen([runner.manifest["commands"][kind], *map(str, args)], env=env,
                cwd=runner.manifest["city"] if kind == "gc" else directory, stdout=stdout, stderr=stderr)
            started = time.monotonic()
            while process.poll() is None:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    process.terminate()
                    raise AcceptanceFailure("Fresh installation command timed out; output retained")
                try: process.wait(timeout=min(15, remaining))
                except subprocess.TimeoutExpired: runner.progress(f"fresh BB setup {count}: running for {int(time.monotonic()-started)}s")
        if process.returncode: raise AcceptanceFailure(f"Fresh installation command {count} failed; private output retained")
        return json.loads(output.read_text()) if parse_json else output.read_text()

    before_gc = run("gc", "supervisor", "status", "--json")
    if before_gc.get("pid_source") != "control_socket" or not before_gc.get("running"):
        raise AcceptanceFailure("Fresh setup could not verify its existing GC controller")
    runner.progress("installation.fresh: starting only a new BB server/host with an empty store")
    log = (directory / "bb-app.log").open("x")
    try:
        app = subprocess.Popen([runner.manifest["commands"]["app"], "--data-dir", str(state),
            "--server-bind-host", "127.0.0.1", "--server-port", str(bb_port), "--host-daemon-port", str(host_port)],
            env=env, cwd=directory, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    finally: log.close()
    if not hasattr(runner, "retained_fresh_installs"): runner.retained_fresh_installs = []
    runner.retained_fresh_installs.append({"directory": directory, "process": app})
    new_json(directory / "bb-process.json", {"pid": app.pid, "bbUrl": env["BB_SERVER_URL"], "bbDataDir": str(state), "gcPid": before_gc["pid"]})
    deadline = time.monotonic() + 90
    last = 0
    while time.monotonic() < deadline:
        if app.poll() is not None: raise AcceptanceFailure("Fresh BB exited during startup")
        try:
            version = read_json(env["BB_SERVER_URL"] + "/api/v1/system/version")
            hosts = read_json(env["BB_SERVER_URL"] + "/api/v1/hosts")
            connected = [host for host in hosts if host.get("status") == "connected"]
            if connected:
                if len(connected) != 1 or version.get("currentVersion") != runner.manifest["versions"]["bb"]:
                    raise AcceptanceFailure("Fresh store has another host or BB release")
                host = connected[0]["id"]
                break
        except (urllib.error.URLError, OSError): pass
        if time.monotonic() - last >= 15:
            runner.progress("installation.fresh: waiting for its new BB host")
            last = time.monotonic()
        time.sleep(1)
    else: raise AcceptanceFailure("Fresh BB host did not connect")
    # These reads establish a blank pre-install store, rather than trusting an
    # existing installation with a freshly named report directory.
    plugins = run("bb", "plugin", "list", "--json")
    rows = plugins if isinstance(plugins, list) else plugins.get("plugins", [])
    if any(row.get("id") == "gas-city" for row in rows):
        raise AcceptanceFailure("Gas City was already installed in the purportedly fresh BB store")
    before = {"bbPid": app.pid, "hostId": host, "gcPid": before_gc["pid"], "gasCityInstalled": False}
    new_json(directory / "before-install.json", before)
    runner.progress("installation.fresh: installing this exact pack into the fresh BB store")
    # install/connect print human output; only their status is relevant here.
    def text_command(*args):
        return run(*args, timeout=180, parse_json=False)
    text_command("gc", "bb", "install", "--yes")
    target = runner.agent("global")
    text_command("gc", "bb", "connect", "--id", target["connection"], "--url", runner.manifest["gcUrl"])
    catalog = run("gc", "bb", "agents", "--json")
    selected = [agent for agent in catalog["agents"] if all(agent.get(key) == target[key] for key in ("connection", "city", "agent"))]
    if len(selected) != 1: raise AcceptanceFailure("Fresh provider did not discover the exact existing GC agent")
    manifest = {**runner.manifest, "envFile": str(directory / "environment.json"), "bbUrl": env["BB_SERVER_URL"],
        "appPid": app.pid, "hostId": host, "agents": selected}
    manifest.pop("desktopSpec", None)
    new_json(directory / "manifest.json", manifest)
    reports = runner.private / ("installation.fresh-" + secrets.token_hex(5))
    child = Runner(manifest, reports, runner.timeout, runner.channel)
    reports.mkdir(mode=0o700); child.private.mkdir(mode=0o700)
    return child, directory, before_gc, run


def verify_fresh_reply(child, directory, before_gc, read_gc_status):
    marker = "FRESH_INSTALL_" + secrets.token_hex(8)
    prompt = "This is the fresh-install browser acceptance check.\nDo not use tools.\nEnd your final response with exactly this standalone line:\n" + marker
    agent = child.agent("global")
    result = child.browser("first-reply", agent, "proj_personal", child.manifest["workspaces"]["global"],
                           prompt, expected=marker, reasoning="medium")
    harness = child.new_harness("first-reply", agent, "proj_personal", child.manifest["workspaces"]["global"], result["threadId"])
    child.verify_turn(harness, result, prompt, marker, no_tools=True)
    after_gc = read_gc_status()
    if (after_gc.get("pid") != before_gc["pid"] or after_gc.get("pid_source") != "control_socket"
            or not after_gc.get("running")):
        raise AcceptanceFailure("Fresh BB installation did not retain the same running GC controller")
    proof = {"thread_id": result["threadId"], "fresh_bb_pid": child.manifest["appPid"], "same_gc_pid": after_gc["pid"],
             "pack_sha256": child.artifacts["pack_sha256"], "rendered_reply_verified": True,
             "browser_result_sha256": hashlib.sha256((child.private / "first-reply/result.json").read_bytes()).hexdigest(),
             "gc_proof_sha256": hashlib.sha256((child.private / "first-reply-proof/report.json").read_bytes()).hexdigest()}
    new_json(directory / "fresh-install-result.json", proof)
    return proof


def fresh(runner):
    child, directory, before_gc, run = prepare_fresh(runner)
    return verify_fresh_reply(child, directory, before_gc,
                              lambda: run("gc", "supervisor", "status", "--json"))


def case_functions(runner):
    return {"installation.fresh": lambda: fresh(runner)}
