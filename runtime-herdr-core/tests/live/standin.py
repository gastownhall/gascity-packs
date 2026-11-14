"""City infrastructure stand-ins for the live tier. The harness copies this
file to names gc and bd give their processes, and runs each copy as
``<python> <name> ...`` from that directory, so ``argv[1]`` is exactly the
verb gc's ``IsCityInfrastructureArgv`` recognises:

* ``__gc-managed-dolt-scope-watchdog <socket> <pid file>``: starts the store
  (``dolt sql-server <socket>``) as its child, writes the store's pid, and
  waits on it, like gc's managed-store watchdog;
* ``dolt sql-server <socket>``: answers ``pong`` to every connection on a
  Unix socket, standing in for the store the city depends on;
* ``db-proxy-child``: sleeps, standing in for bd's proxy.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from typing import List


def _store(path: str) -> int:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(16)
    while True:
        conn, _ = server.accept()
        with conn:
            conn.sendall(b"pong\n")


def _watchdog(sock: str, pid_file: str) -> int:
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    child = subprocess.Popen([sys.executable, "dolt", "sql-server", sock], cwd=here)
    tmp = f"{pid_file}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(str(child.pid))
    os.replace(tmp, pid_file)
    child.wait()
    while True:  # a watchdog outlives its store; the test reads both
        time.sleep(3600)


def main(argv: List[str]) -> int:
    role = os.path.basename(argv[0])
    if role == "__gc-managed-dolt-scope-watchdog":
        return _watchdog(argv[1], argv[2])
    if role == "dolt":
        return _store(argv[2])
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
