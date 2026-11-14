"""The live tier's deterministic agent: what a session runs in place of a
coding agent.

    <python> agent.py          (configured by the environment below)

It reads its input a line at a time and appends each line, with the time it
arrived, to ``<dir>/<agent>.input.log`` (one JSON object per line), so a test
can count exactly how often a nudge was typed. It never reports OSC 7501
status. On request it starts, the way a coding agent's shell does:

* ``infra``: city infrastructure stand-ins, detached in sessions of their
  own (as gc's managed store autostart and bd's proxy are): a watchdog with
  gc's ``__gc-managed-dolt-scope-watchdog`` argv that starts a store which
  answers on a Unix socket, and a proxy with bd's ``db-proxy-child`` argv.
  With ``GC_HC_LIVE_INFRA_UNIT`` and a reachable user manager, the watchdog
  is started in a transient scope of that name under ``gascity-infra.slice``,
  with the ``systemd-run`` argv gc wraps infrastructure in;
* ``orphan``: ``setsid sleep 9999``, and a fenced proxy stand-in;
* ``witness``: ``setsid sleep 9999`` with ``HC_SCOPE`` removed from its
  environment and re-parented out of the agent's tree, so hc's holder-loss
  sweep (a carrier and its descendants) cannot reach it and only a
  cgroup-wide kill of the agent's cgroup can.

Everything it reports goes to ``<dir>/<agent>.json``, written atomically once
all of it runs. Touching ``<dir>/<agent>.run-hc`` makes it run ``hc ls`` from
its own ``PATH`` (the pack's shim comes first there) and write the outcome to
``<dir>/<agent>.hc.json``.

Environment: ``GC_HC_LIVE_DIR``, ``GC_HC_LIVE_AGENT``, ``GC_HC_LIVE_STANDINS``
(the stand-in directory), ``GC_HC_LIVE_PYTHON``, optional
``GC_HC_LIVE_SPAWN`` (comma list), ``GC_HC_LIVE_INFRA_UNIT`` and
``GC_HC_LIVE_ECHO`` (printed to the screen once).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional

INFRA_SLICE = "gascity-infra.slice"


def _write_json(path: str, doc: Dict[str, object]) -> None:
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(doc, handle)
    os.replace(tmp, path)


def _detached(argv: List[str], cwd: str) -> int:
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc.pid


def _user_manager() -> bool:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    return bool(runtime) and os.path.exists(os.path.join(runtime, "systemd", "private"))


def _wait_for_pid_file(path: str, timeout_s: float = 15.0) -> int:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read().strip()
            if text:
                return int(text)
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    raise RuntimeError(f"no pid in {path}")


def spawn_infra(work: str, name: str, standins: str, python: str, errors: List[str]) -> Dict[str, object]:
    store = os.path.join(work, f"{name}.store.sock")
    dolt_pid_file = os.path.join(work, f"{name}.dolt.pid")
    watchdog = [python, "__gc-managed-dolt-scope-watchdog", store, dolt_pid_file]
    unit = os.environ.get("GC_HC_LIVE_INFRA_UNIT", "")
    if unit:
        if not _user_manager():
            errors.append("infrastructure scope asked for, but no user manager is reachable")
        else:
            watchdog = [
                "systemd-run", "--user", "--scope", f"--slice={INFRA_SLICE}", f"--unit={unit}",
                "--collect", "--quiet", "--", *watchdog,
            ]
    out: Dict[str, object] = {"store_socket": store}
    out["watchdog"] = _detached(watchdog, standins)
    out["proxy"] = _detached([python, "db-proxy-child"], standins)
    try:
        out["dolt"] = _wait_for_pid_file(dolt_pid_file)
    except RuntimeError as err:
        errors.append(str(err))
    return out


def spawn_orphans(standins: str, python: str) -> Dict[str, object]:
    sleep = shutil.which("sleep") or "/bin/sleep"
    return {
        "sleep": _detached([sleep, "9999"], standins),
        "fenced": _detached([python, "db-proxy-child"], standins),
    }


_WITNESS = (
    "import subprocess, sys\n"
    "p = subprocess.Popen([sys.argv[1], '9999'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,"
    " stderr=subprocess.DEVNULL, start_new_session=True)\n"
    "print(p.pid)\n"
)


def spawn_witness(standins: str, python: str) -> int:
    """A sleep with no ``HC_SCOPE`` that is not the agent's descendant either
    (hc's sweep takes a carrier's descendants too): an intermediate process
    starts it and exits, so it is re-parented away from the agent's tree."""
    sleep = shutil.which("sleep") or "/bin/sleep"
    env = {k: v for k, v in os.environ.items() if k != "HC_SCOPE"}
    done = subprocess.run(
        [python, "-c", _WITNESS, sleep],
        cwd=standins,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return int(done.stdout.strip())


def _probe_hc(work: str, name: str) -> None:
    trigger = os.path.join(work, f"{name}.run-hc")
    while not os.path.exists(trigger):
        time.sleep(0.1)
    found = shutil.which("hc") or ""
    doc: Dict[str, object] = {"argv0": found}
    if not found:
        doc.update(code=127, stdout="", stderr="no hc on PATH")
    else:
        try:
            done = subprocess.run([found, "ls"], capture_output=True, text=True, timeout=30, check=False)
            doc.update(code=done.returncode, stdout=done.stdout[-4000:], stderr=done.stderr[-4000:])
        except subprocess.TimeoutExpired:
            doc.update(code=124, stdout="", stderr="hc ls hung for 30 s")
    _write_json(os.path.join(work, f"{name}.hc.json"), doc)


def main() -> int:
    work = os.environ["GC_HC_LIVE_DIR"]
    name = os.environ["GC_HC_LIVE_AGENT"]
    standins = os.environ.get("GC_HC_LIVE_STANDINS", "")
    python = os.environ.get("GC_HC_LIVE_PYTHON", "") or sys.executable
    wanted = [w for w in os.environ.get("GC_HC_LIVE_SPAWN", "").split(",") if w]
    errors: List[str] = []
    report: Dict[str, object] = {"pid": os.getpid(), "errors": errors}
    if "infra" in wanted:
        report["infra"] = spawn_infra(work, name, standins, python, errors)
    if "orphan" in wanted:
        report["orphan"] = spawn_orphans(standins, python)
    if "witness" in wanted:
        report["witness"] = spawn_witness(standins, python)
    echo: Optional[str] = os.environ.get("GC_HC_LIVE_ECHO")
    if echo:
        print(echo, flush=True)
    threading.Thread(target=_probe_hc, args=(work, name), daemon=True).start()
    _write_json(os.path.join(work, f"{name}.json"), report)
    print(f"{name} ready", flush=True)
    log = os.path.join(work, f"{name}.input.log")
    stdin = sys.stdin.buffer
    while True:
        line = stdin.readline()
        if not line:
            return 0
        entry = {"at": time.time(), "text": line.rstrip(b"\r\n").decode("utf-8", "replace")}
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    sys.exit(main())
