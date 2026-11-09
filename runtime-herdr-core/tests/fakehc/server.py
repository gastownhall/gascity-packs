"""fake-hc: an in-process herdr-core for the unit tier.

A stdlib ``ThreadingUnixStreamServer`` speaking hc's plain-mode JSON-RPC 2.0
(one message per line) on a real Unix socket, so the pack's client is tested
over the same transport it uses in production. Programs are real child
processes (:mod:`.terminal`).

Faults the tests script, per method: an error of any kind (including kinds
hc does not have), a reply lost after its side effect, a delayed or garbled
reply; per terminal, a human-quiet hold that withholds a ``send`` (it is typed
only when released), scripted OSC 7501 status and holder loss; per core, a
restart that drops every connection, and a version or generation change.

Every request's params and every result pass the :mod:`.schema` guard; the
violations are collected in :attr:`FakeHc.schema_violations`, which the
unit tier's fixture requires to be empty.
"""

from __future__ import annotations

import io
import json
import os
import re
import socket
import socketserver
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple, cast

from .schema import SchemaGuard
from .terminal import KEPT_RESTART_S, FakeTerminal, key_bytes

METHODS: Tuple[str, ...] = (
    "hello",
    "server.status",
    "server.stop",
    "terminal.run",
    "terminal.get",
    "terminal.list",
    "terminal.send",
    "terminal.keys",
    "terminal.interrupt",
    "terminal.read",
    "terminal.kill",
    "terminal.rm",
    "terminal.label",
    "terminal.keep",
)

FEATURES: Tuple[str, ...] = ("framed", "attach", "events", "status", "shell", "resize_notifications", "automatic_input")
"""hello's ``features`` at v0.1.19 (hc ``src/api.rs``)."""

_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,31}")
_ID_SHAPED = re.compile(r"t[1-9][0-9bcdfghjkmnpqrstvwxyz]*")
_SYMBOLS = "0123456789bcdfghjkmnpqrstvwxyz"


def hc_address(n: int) -> str:
    """hc ``terminals.rs`` ``address``: t1..t9, t10..t9z (30 symbols after the first digit)."""
    rest, size, length = n - 1, 9, 0
    while rest >= size:
        rest -= size
        size *= 30
        length += 1
    tail = ""
    for _ in range(length):
        tail = _SYMBOLS[rest % 30] + tail
        rest //= 30
    return f"t{rest + 1}{tail}"
_STRIPPED_FROM_CORE_ENV = ("TERM", "TERM_PROGRAM", "TERM_PROGRAM_VERSION", "COLORTERM", "HC_TERMINAL_ID", "HC_SCOPE", "HC_RUNTIME")

Params = Dict[str, Any]


@dataclass(frozen=True)
class Call:
    """One request as fake-hc received it."""

    method: str
    params: Params


class RpcFailure(Exception):
    """An hc error reply: ``{"code", "message", "data": {"kind", "hint"}}``."""

    def __init__(self, kind: str, message: str, code: int = -32000) -> None:
        Exception.__init__(self, message)
        self.kind = kind
        self.message = message
        self.code = code


@dataclass(frozen=True)
class _Fault:
    action: str  # error | lose | drop | delay | garble
    kind: str = ""
    message: str = ""
    code: int = -32000
    seconds: float = 0.0
    after_exit: bool = False


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, path: str, fake: FakeHc) -> None:
        self.fake = fake
        socketserver.ThreadingUnixStreamServer.__init__(self, path, _Handler)


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        cast(_Server, self.server).fake._serve(self.connection, self.rfile)


class FakeHc:
    """A herdr-core double on ``socket_path``."""

    METHODS = METHODS

    def __init__(
        self,
        socket_path: str,
        *,
        version: str = "0.1.19",
        generation: int = 1,
        core_name: str = "fakehost",
        started_window_s: float = 0.3,
        kill_grace_s: float = 0.05,
        kept_restart_s: float = KEPT_RESTART_S,
        base_env: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.socket_path = socket_path
        self._version = version
        self._generation = generation
        self._core = {"id": uuid.uuid4().hex, "name": core_name}
        self._started_window_s = started_window_s
        self._kill_grace_s = kill_grace_s
        self._kept_restart_s = kept_restart_s
        self._base_env = {
            key: value
            for key, value in (
                base_env
                if base_env is not None
                else {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", "/"), "LANG": "C.UTF-8"}
            ).items()
            if key not in _STRIPPED_FROM_CORE_ENV
        }
        self._guard = SchemaGuard.vendored()
        self._lock = threading.RLock()
        self._terminals: Dict[str, FakeTerminal] = {}
        self._removed: List[FakeTerminal] = []
        self._closing = False
        self._next_id = 1
        self._faults: Dict[str, List[_Fault]] = {}
        self._calls: List[Call] = []
        self._conns: Set[socket.socket] = set()
        self._accepted = 0
        self._started_at = time.monotonic()
        self._server: Optional[_Server] = None
        self._thread: Optional[threading.Thread] = None
        # Set once server.stop has answered: a standalone core then exits.
        self.stopped = threading.Event()
        # Requests or results that left the vendored schema (must stay empty),
        # and the methods whose results the guard has checked.
        self.schema_violations: List[str] = []
        self.guarded_methods: Set[str] = set()

    # --- lifecycle -------------------------------------------------------------

    def start(self) -> None:
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        server = _Server(self.socket_path, self)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        self._server, self._thread = server, thread

    def close(self) -> None:
        """Stop serving and kill every program (idempotent)."""
        with self._lock:
            self._closing = True
            terminals = list(self._terminals.values()) + self._removed
        for terminal in terminals:
            with terminal.lock:
                terminal.changed.notify_all()  # wake sends held by hold_input
        self._stop_listening()
        for terminal in terminals:
            terminal.reap()

    def _close_listener(self) -> None:
        """Stop accepting connections; open ones stay until dropped."""
        with self._lock:
            server, self._server = self._server, None
            thread, self._thread = self._thread, None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2.0)
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass

    def _stop_listening(self) -> None:
        self._close_listener()
        self._drop_connections()

    def _drop_connections(self) -> None:
        with self._lock:
            conns = list(self._conns)
        for conn in conns:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    # --- observation -------------------------------------------------------------

    @property
    def calls(self) -> List[Call]:
        with self._lock:
            return list(self._calls)

    def call_count(self, method: str) -> int:
        with self._lock:
            return sum(1 for call in self._calls if call.method == method)

    @property
    def connections(self) -> int:
        """Connections accepted so far."""
        with self._lock:
            return self._accepted

    @property
    def open_connections(self) -> int:
        with self._lock:
            return len(self._conns)

    def _terminal(self, address: str) -> FakeTerminal:
        with self._lock:
            return self._terminals[address]

    def input_log(self, address: str) -> List[str]:
        """Every text typed into the terminal by ``terminal.send``, in order."""
        terminal = self._terminal(address)
        with terminal.lock:
            return list(terminal.inputs)

    def key_log(self, address: str) -> List[str]:
        terminal = self._terminal(address)
        with terminal.lock:
            return list(terminal.keys)

    def terminal_env(self, address: str) -> Dict[str, str]:
        """The environment the terminal's program was started with."""
        return dict(self._terminal(address).env)

    # --- scripting ---------------------------------------------------------------

    def set_version(self, version: str) -> None:
        with self._lock:
            self._version = version

    def set_generation(self, generation: int) -> None:
        with self._lock:
            self._generation = generation

    def _queue(self, method: str, fault: _Fault, count: int) -> None:
        with self._lock:
            self._faults.setdefault(method, []).extend([fault] * count)

    def fail_next(self, method: str, kind: str, *, message: str = "", code: int = -32000, count: int = 1) -> None:
        """Answer the next ``count`` calls of ``method`` with an hc error, doing nothing."""
        self._queue(method, _Fault("error", kind=kind, message=message or kind, code=code), count)

    def lose_request(self, method: str, *, count: int = 1) -> None:
        """Close the connection on the next ``count`` calls of ``method`` unanswered, doing nothing."""
        self._queue(method, _Fault("lose"), count)

    def drop_reply(self, method: str, *, count: int = 1, after_exit: bool = False) -> None:
        """Do the next ``count`` calls of ``method``, then close the connection
        unanswered; ``after_exit``: once the terminal the call started has exited."""
        self._queue(method, _Fault("drop", after_exit=after_exit), count)

    def delay_reply(self, method: str, seconds: float, *, count: int = 1) -> None:
        self._queue(method, _Fault("delay", seconds=seconds), count)

    def garble_reply(self, method: str, *, count: int = 1) -> None:
        self._queue(method, _Fault("garble"), count)

    def hold_input(self, address: str) -> None:
        """A person keeps typing: send and keys wait (the input queue with them)."""
        terminal = self._terminal(address)
        with terminal.lock:
            terminal.held = True

    def release_input(self, address: str) -> None:
        terminal = self._terminal(address)
        with terminal.lock:
            terminal.held = False
            terminal.changed.notify_all()

    def set_status(
        self, address: str, state: str, *, kind: Optional[str] = None, app: str = "", progress: Optional[int] = None
    ) -> None:
        """The program reports an OSC 7501 status word."""
        self._terminal(address).set_status(state, kind=kind, app=app, progress=progress)

    def work_on_send(self, address: str, enabled: bool = True) -> None:
        """Typed text starts a turn (the program goes ``working``)."""
        terminal = self._terminal(address)
        with terminal.lock:
            terminal.work_on_send = enabled

    def lose_holder(self, address: str) -> None:
        self._terminal(address).lose_holder()

    def restart_core(self, *, version: Optional[str] = None) -> None:
        """The core process restarts: connections drop, programs and records survive."""
        with self._lock:
            if version is not None:
                self._version = version
            terminals = list(self._terminals.values())
        for terminal in terminals:
            with terminal.lock:
                terminal.screen = "inexact"
        self._drop_connections()

    # --- transport ---------------------------------------------------------------

    def _serve(self, conn: socket.socket, rfile: io.BufferedIOBase) -> None:
        with self._lock:
            self._conns.add(conn)
            self._accepted += 1
        try:
            while True:
                line = rfile.readline()
                if not line:
                    return
                reply, after = self._handle_line(line)
                if reply is not None:
                    conn.sendall(reply)
                if after is not None:
                    after()
                if reply is None or after is not None:
                    return  # a lost reply closes unanswered; a stopped core closes too
        except OSError:
            return
        finally:
            with self._lock:
                self._conns.discard(conn)

    def _handle_line(self, line: bytes) -> Tuple[Optional[bytes], Optional[Callable[[], None]]]:
        try:
            request = json.loads(line)
        except ValueError:
            return self._reply(None, error=(-32700, "parse error", "invalid_params")), None
        if not isinstance(request, dict):
            return self._reply(None, error=(-32600, "invalid request", "invalid_params")), None
        request_id = request.get("id")
        method = str(request.get("method"))
        raw_params = request.get("params")
        if raw_params is not None and not isinstance(raw_params, dict):
            return self._reply(request_id, error=(-32602, "params must be an object", "invalid_params")), None
        params: Params = raw_params or {}
        with self._lock:
            self._calls.append(Call(method, dict(params)))
            queued = self._faults.get(method)
            fault = queued.pop(0) if queued else None
        if method in self._guard.methods:
            self._violations(self._guard.check_params(method, params))
        if fault is not None and fault.action == "error":
            return self._reply(request_id, error=(fault.code, fault.message, fault.kind)), None
        if fault is not None and fault.action == "lose":
            return None, None
        handler = self._handlers().get(method)
        if handler is None:
            return self._reply(request_id, error=(-32601, f"no method {method}", "invalid_params")), None
        try:
            result = handler(params)
        except RpcFailure as failure:
            return self._reply(request_id, error=(failure.code, failure.message, failure.kind)), None
        self._violations(self._guard.check_result(method, result))
        with self._lock:
            self.guarded_methods.add(method)
        after = self._drop_connections if method == "server.stop" else None
        if fault is not None:
            if fault.action == "drop":
                self._await_exit(fault, result)
                return None, after
            if fault.action == "delay":
                time.sleep(fault.seconds)
            if fault.action == "garble":
                return b'{"jsonrpc":"2.0","id":' + json.dumps(request_id).encode() + b',"result":{\n', after
        return self._reply(request_id, result=result), after

    def _await_exit(self, fault: _Fault, result: Dict[str, Any]) -> None:
        if not fault.after_exit:
            return
        with self._lock:
            terminal = self._terminals.get(str(result.get("address")))
        if terminal is not None:
            with terminal.lock:
                terminal.changed.wait_for(lambda: terminal.state != "live", timeout=10.0)

    def _violations(self, found: List[str]) -> None:
        if found:
            with self._lock:
                self.schema_violations.extend(found)

    @staticmethod
    def _reply(
        request_id: object, *, result: object = None, error: Optional[Tuple[int, str, str]] = None
    ) -> bytes:
        message: Dict[str, object] = {"jsonrpc": "2.0", "id": request_id}
        if error is not None:
            code, text, kind = error
            message["error"] = {"code": code, "message": text, "data": {"kind": kind, "hint": ""}}
        else:
            message["result"] = result
        return (json.dumps(message) + "\n").encode("utf-8")

    def _handlers(self) -> Dict[str, Callable[[Params], Dict[str, Any]]]:
        return {
            "hello": self._hello,
            "server.status": self._server_status,
            "server.stop": self._server_stop,
            "terminal.run": self._run,
            "terminal.get": lambda p: self._lookup(p).record(),
            "terminal.list": self._list,
            "terminal.send": self._send,
            "terminal.keys": self._keys,
            "terminal.interrupt": self._interrupt,
            "terminal.read": self._read,
            "terminal.kill": self._kill,
            "terminal.rm": self._rm,
            "terminal.label": self._label,
            "terminal.keep": self._keep,
        }

    # --- methods -----------------------------------------------------------------

    def _hello(self, params: Params) -> Dict[str, Any]:
        with self._lock:
            requested = params.get("generation")
            if requested is not None and requested != self._generation:
                raise RpcFailure("unsupported_generation", f"this core speaks protocol generation {self._generation}")
            return {
                "generation": self._generation,
                "version": self._version,
                "core": dict(self._core),
                "framed": False,
                "methods": list(METHODS),
                "features": list(FEATURES),
            }

    def _server_status(self, params: Params) -> Dict[str, Any]:
        with self._lock:
            terminals = list(self._terminals.values())
            version = self._version
        live = sum(1 for t in terminals if t.state == "live")
        holder = {"pid": os.getpid(), "instance": self._core["id"][:8], "current": True, "terminals": live}
        return {
            "core": dict(self._core),
            "version": version,
            "pid": os.getpid(),
            "uptime_ms": int((time.monotonic() - self._started_at) * 1000),
            "holder": holder,
            "holders": [holder],
            "live": live,
            "finished": len(terminals) - live,
            "installed_by": None,
        }

    def _server_stop(self, params: Params) -> Dict[str, Any]:
        with self._lock:
            terminals = list(self._terminals.values())
        for terminal in terminals:
            terminal.end("server_stop")
        # The core is gone once it answers: nothing accepts a connection
        # after the reply. The reply's own connection closes after it.
        self._close_listener()
        self.stopped.set()
        return {"stopped": True}

    def _run(self, params: Params) -> Dict[str, Any]:
        argv = list(params.get("argv") or [])
        if params.get("line"):
            argv = ["/bin/sh", "-c", str(params["line"])]
        if not argv:
            argv = ["/bin/sh"]
        name = params.get("name")
        labels = {str(k): str(v) for k, v in (params.get("labels") or {}).items()}
        self._check_labels(labels)
        with self._lock:
            if name is not None:
                if not _NAME.fullmatch(name) or _ID_SHAPED.fullmatch(name):
                    raise RpcFailure("invalid_params", f"bad terminal name {name!r}", code=-32602)
                if any(t.name == name and t.state == "live" for t in self._terminals.values()):
                    raise RpcFailure("name_taken", f"a live terminal is named {name}")
            address = hc_address(self._next_id)
            self._next_id += 1
            cwd = str(params.get("cwd") or "/")
            env = dict(self._base_env)
            env.update({str(k): str(v) for k, v in (params.get("env") or {}).items()})
            env.update(
                {
                    "HC_TERMINAL_ID": address,
                    "HC_TERMINAL_SOCKET": self.socket_path,
                    "HC_SCOPE": f"{int(time.monotonic() * 100)}-{uuid.uuid4().hex[:12]}",
                    "PWD": cwd,
                }
            )
            env.setdefault("TERM", "xterm-256color")
            env.setdefault("COLORTERM", "truecolor")
            try:
                terminal = FakeTerminal(
                    address=address,
                    name=name,
                    labels=labels,
                    argv=argv,
                    cwd=cwd,
                    env=env,
                    keep=bool(params.get("keep")),
                    restart_delay_s=self._kept_restart_s,
                )
            except OSError as err:
                raise RpcFailure("spawn_failed", f"cannot start {argv[0]}: {err.strerror}") from None
            terminal.created_seq = self._next_id - 1
            self._terminals[address] = terminal
        return terminal.record()

    def _lookup(self, params: Params) -> FakeTerminal:
        # hc terminals.rs resolve: an address is that terminal forever; a name
        # is whoever holds it now, else the most recent finished one that had it.
        target = str(params.get("terminal", ""))
        with self._lock:
            if target in self._terminals:
                return self._terminals[target]
            named = sorted(
                (t for t in self._terminals.values() if t.name == target),
                key=lambda t: t.created_seq,
                reverse=True,
            )
        for terminal in named:
            if terminal.state == "live":
                return terminal
        if named:
            return named[0]
        raise RpcFailure("not_found", f"no terminal {target}")

    def _list(self, params: Params) -> Dict[str, Any]:
        wanted = {str(k): str(v) for k, v in (params.get("labels") or {}).items()}
        include_finished = bool(params.get("all"))
        with self._lock:
            terminals = sorted(self._terminals.values(), key=lambda t: t.created_seq)
        listed, hidden = [], 0
        for terminal in terminals:
            record = terminal.record()
            if any(record["labels"].get(k) != v for k, v in wanted.items()):
                continue
            if record["state"] != "live" and not include_finished:
                hidden += 1
                continue
            listed.append(record)
        return {"terminals": listed, "hidden_finished": hidden}  # no "machines" when empty (hc #190)

    def _live(self, params: Params) -> FakeTerminal:
        terminal = self._lookup(params)
        self._check_program(terminal)
        return terminal

    @staticmethod
    def _check_program(terminal: FakeTerminal) -> None:
        # hc input.rs / terminals.rs check_program: input needs a live record
        # with a program; a kept terminal waiting for its new shell has none.
        with terminal.lock:
            if terminal.state != "live":
                raise RpcFailure("finished", f"{terminal.address} has finished")
            if terminal.lost:
                raise RpcFailure("unavailable", f"{terminal.address} is lost, waiting for its new shell")

    def _wait_quiet(self, terminal: FakeTerminal) -> None:
        with terminal.lock:
            terminal.changed.wait_for(lambda: not terminal.held or self._closing)

    def _send(self, params: Params) -> Dict[str, Any]:
        terminal = self._live(params)
        text = str(params.get("text", ""))
        with terminal.input_lock:
            self._wait_quiet(terminal)
            with terminal.lock:
                self._check_program(terminal)
                word = None if terminal.status is None else str(terminal.status["state"])
                if word == "blocked" and not params.get("force"):
                    raise RpcFailure("blocked", f"{terminal.address} is waiting on its own question; nothing was typed")
                condition = params.get("if")
                if condition is not None and condition != word:
                    raise RpcFailure("status_mismatch", f"{terminal.address} is {word}; nothing was typed")
                turn = terminal.turn
                reported = terminal.reported
                if not terminal.type_bytes(text.encode("utf-8") + b"\n"):
                    raise RpcFailure("finished", f"{terminal.address} has finished")
                terminal.inputs.append(text)
                if reported and terminal.work_on_send:
                    terminal.set_status("working", kind=None, app=terminal.status["app"] if terminal.status else "", progress=None)
            started: Optional[bool] = None
            if reported:
                with terminal.lock:
                    started = terminal.changed.wait_for(
                        lambda: terminal.turn > turn
                        or (terminal.status is not None and terminal.status["state"] == "working"),
                        timeout=self._started_window_s,
                    )
        return {"turn": turn, "status": word, "started": started}

    def _keys(self, params: Params) -> Dict[str, Any]:
        terminal = self._live(params)
        keys = [str(k) for k in params.get("keys") or []]
        with terminal.input_lock:
            self._wait_quiet(terminal)
            self._check_program(terminal)
            for key in keys:
                if key == "ctrl+c":
                    terminal.interrupt_signal()
                else:
                    data = key_bytes(key)
                    if data is None:
                        raise RpcFailure("invalid_params", f"unknown key {key!r}", code=-32602)
                    terminal.type_bytes(data)
                with terminal.lock:
                    terminal.keys.append(key)
            with terminal.lock:
                return {"turn": terminal.turn, "status": terminal.status_word()}

    def _interrupt(self, params: Params) -> Dict[str, Any]:
        terminal = self._live(params)
        wait_s = float(params.get("timeout") or 10.0)
        with terminal.input_lock:
            if terminal.reported:
                terminal.type_bytes(b"\x1b")
                if terminal.status_word() == "working":
                    terminal.set_status("idle", kind=None, app="", progress=None)
                    return {"outcome": "stopped", "key": "esc"}
                return {"outcome": "still_working", "key": "esc"}
            terminal.interrupt_signal()
            with terminal.lock:
                exited = terminal.changed.wait_for(lambda: terminal.state != "live", timeout=min(wait_s, 1.0))
            return {"outcome": "exited" if exited else "unknown", "key": "ctrl+c"}

    def _read(self, params: Params) -> Dict[str, Any]:
        terminal = self._lookup(params)
        lines = int(params.get("lines") or 0)
        return {
            "text": terminal.screen_text(lines),
            "how": "history" if lines > 0 else "screen",
            "complete": True,
            "why": None,
        }

    def _kill(self, params: Params) -> Dict[str, Any]:
        terminal = self._lookup(params)
        terminal.kill(self._kill_grace_s)
        return terminal.record()

    def _rm(self, params: Params) -> Dict[str, Any]:
        terminal = self._lookup(params)
        with self._lock:
            if terminal.state == "live":
                raise RpcFailure("live", f"{terminal.address} is still running")
            del self._terminals[terminal.address]
            self._removed.append(terminal)  # hc kills nothing on rm; close() still reaps leftovers
        return {"removed": terminal.address}

    @staticmethod
    def _check_labels(labels: Mapping[str, str]) -> None:
        for key in labels:
            if not key or "=" in key:
                raise RpcFailure("invalid_params", f"bad label key {key!r}", code=-32602)

    def _label(self, params: Params) -> Dict[str, Any]:
        terminal = self._lookup(params)
        labels = {str(k): str(v) for k, v in (params.get("labels") or {}).items()}
        self._check_labels(labels)
        with terminal.lock:
            for key, value in labels.items():
                if value:
                    terminal.labels[key] = value
                else:
                    terminal.labels.pop(key, None)
        return terminal.record()

    def _keep(self, params: Params) -> Dict[str, Any]:
        terminal = self._lookup(params)
        with terminal.lock:
            terminal.keep = bool(params.get("keep"))
        return terminal.record()
