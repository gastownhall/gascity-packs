"""Plain JSON-RPC calls to a city core, for what the harness does beside the
pack: read the holders, keep a terminal, run a program with no launcher."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import BinaryIO, Dict, Mapping, Optional, Sequence, Tuple

from gc_runtime_herdr_core.rpp.jsonval import JsonObject, loads


class HcRpcError(Exception):
    """hc answered with an error."""

    def __init__(self, method: str, kind: str, message: str) -> None:
        super().__init__(f"{method}: {kind}: {message}")
        self.kind = kind


@dataclass(frozen=True)
class CoreStatus:
    pid: int
    version: str
    holders: Tuple[int, ...]


@dataclass(frozen=True)
class TerminalView:
    address: str
    state: str
    pid: Optional[int]
    keep: bool
    reason: Optional[str]


class HcRpc:
    def __init__(self, socket_path: str, *, timeout_s: float = 10.0) -> None:
        self.socket_path = socket_path
        self.timeout_s = timeout_s

    def call(self, method: str, params: Mapping[str, object]) -> JsonObject:
        """One request on a fresh connection, after the ``hello`` the pack's
        own client sends first on every connection; the result object."""
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(self.timeout_s)
            conn.connect(self.socket_path)
            reader = conn.makefile("rb")
            if method != "hello":
                _result(_exchange(conn, reader, 0, "hello", {}), "hello")
            return _result(_exchange(conn, reader, 1, method, params), method)

    def status(self) -> CoreStatus:
        result = self.call("server.status", {})
        return CoreStatus(
            pid=result.req_int("pid"),
            version=result.req_str("version"),
            holders=tuple(h.req_int("pid") for h in result.obj_tuple("holders", required=True)),
        )

    def terminal(self, address: str) -> TerminalView:
        return _view(self.call("terminal.get", {"terminal": address}))

    def has_terminal(self, name: str) -> bool:
        """Whether hc has a terminal (live or finished) by that name or address."""
        try:
            self.terminal(name)
        except HcRpcError as err:
            if err.kind == "not_found":
                return False
            raise
        return True

    def keep(self, address: str, keep: bool) -> None:
        self.call("terminal.keep", {"terminal": address, "keep": keep})

    def run(self, argv: Sequence[str], *, cwd: str, env: Mapping[str, str], name: str) -> TerminalView:
        """A program hc runs directly: no pack launcher, so it keeps ``HC_SCOPE``
        and stays in the holder's cgroup."""
        params: Dict[str, object] = {
            "argv": list(argv),
            "cwd": cwd,
            "env": dict(env),
            "name": name,
            "keep": False,
            "no_parent": True,
            "no_notify": True,
        }
        return _view(self.call("terminal.run", params))

    def kill(self, address: str) -> None:
        self.call("terminal.kill", {"terminal": address})

    def answers(self) -> bool:
        try:
            self.call("hello", {})
        except (OSError, ValueError, HcRpcError):
            return False
        return True


def _exchange(conn: socket.socket, reader: "BinaryIO", rid: int, method: str, params: Mapping[str, object]) -> JsonObject:
    request = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": dict(params)}) + "\n"
    conn.sendall(request.encode("utf-8"))
    while True:
        line = reader.readline(1 << 24)
        if not line.endswith(b"\n"):
            raise ConnectionError(f"{method}: the core closed the connection")
        doc = JsonObject.of(loads(line))
        if doc.opt_int("id") == rid:  # anything else is a notification
            return doc


def _result(doc: JsonObject, method: str) -> JsonObject:
    error = doc.opt_obj("error")
    if error is not None:
        data = error.opt_obj("data")
        kind = "" if data is None else data.str_or("kind", "")
        raise HcRpcError(method, kind, error.str_or("message", ""))
    return doc.req_obj("result")


def _view(doc: JsonObject) -> TerminalView:
    return TerminalView(
        address=doc.req_str("address"),
        state=doc.req_str("state"),
        pid=doc.opt_int("pid"),
        keep=doc.bool_or("keep", False),
        reason=doc.opt_str("reason"),
    )
