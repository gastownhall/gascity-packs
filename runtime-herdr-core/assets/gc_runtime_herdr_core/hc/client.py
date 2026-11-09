"""The herdr-core JSON-RPC client, over hc's plain mode (one JSON-RPC message
per line; hc ``schema/README.md`` "Connecting").

* One plain-mode connection per call. A plain connection answers one request
  at a time (hc ``crates/herdr-core/src/server.rs``, ``connection``), and a
  ``send`` waits until nobody has typed for about 3 s (hc.openrpc.json
  ``terminal.send``), so concurrent calls never share a connection.
* A call's timeout is its table value (:class:`CallTimeouts`) cut to end one
  second before the op's deadline (:meth:`~..rpp.cancel.Deadline.budget`);
  ``send`` gets the deadline less two seconds. A call with no time left is
  not sent at all.
* ``hello``, ``terminal.get``, ``terminal.list`` and ``terminal.read`` are
  retried once, on a fresh connection, when the core drops the first before
  replying. Nothing else is: ``run``, ``send``, ``keys``, ``interrupt`` and
  ``kill`` are not idempotent, and hc has no request ids to dedupe them.
* The core is gated by its ``hello`` (:func:`.version.gate`) before the first
  call and again after any lost or refused connection: that is how an
  out-of-band restart or upgrade of the core shows itself.
* Every failure is an :class:`~.errors.HcError` that says whether the request
  may have reached the core.
"""

from __future__ import annotations

import itertools
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Final, Mapping, Optional, Sequence, Tuple, TypeVar

from ..rpp.cancel import DEADLINE_MARGIN_S, POLL_INTERVAL_S, CancelToken, Deadline
from ..rpp.jsonval import JsonObject, JsonShapeError, dumps, loads
from .errors import (
    HcCancelled,
    HcConnectionLost,
    HcError,
    HcGateError,
    HcProtocolError,
    HcRpcError,
    HcTimeout,
    HcUnreachable,
)
from .parse import (
    parse_hello,
    parse_interrupt,
    parse_keys,
    parse_list,
    parse_read,
    parse_remove,
    parse_send,
    parse_status,
    parse_stop,
    parse_terminal,
)
from .types import (
    HelloResult,
    InterruptResult,
    KeysResult,
    ListResult,
    ReadResult,
    RemoveResult,
    RunSpec,
    SendResult,
    StatusResult,
    StopResult,
    Terminal,
)
from .version import GENERATION, GateResult, VersionPolicy, gate

T = TypeVar("T")

IDEMPOTENT_METHODS: Final = frozenset({"hello", "terminal.get", "terminal.list", "terminal.read"})
"""The only methods retried, once, when a connection drops before the reply."""

INTERRUPT_WAIT_S: Final = 3.0
"""hc's own wait for an interrupted program to settle (``interrupt {timeout:3}``)."""

MAX_REPLY_BYTES: Final = 16 << 20
_RECV_BYTES: Final = 1 << 16


@dataclass(frozen=True)
class _Budget:
    """A call's timeout rule: at most ``cap``, ending ``margin`` before the op's deadline."""

    cap: float
    margin: float = DEADLINE_MARGIN_S


@dataclass(frozen=True)
class CallTimeouts:
    """Per-call timeout caps, before the deadline cut.

    ``run`` covers hc starting the program, ``interrupt`` the 3 s hc is asked
    to watch for an effect, ``kill`` hc's hangup, terminate, kill escalation
    (hc.openrpc.json ``terminal.kill``). ``send`` has no cap of its own: it
    may wait as long as a person keeps typing.
    """

    hello: float
    query: float
    """``terminal.get``, ``list``, ``read``, ``label``, ``rm`` and ``server.status``."""
    connect: float = 1.0
    run: float = 15.0
    keys: float = 10.0
    interrupt: float = 5.0
    kill: float = 5.0
    server_stop: float = 10.0
    send_reserve: float = 2.0
    """``send`` may use the op's remaining time less this."""

    @classmethod
    def for_op(cls, *, read: bool, probe: bool) -> CallTimeouts:
        """The table for one op.

        ``read`` ops (observe, inventory, is-attached, peek, get-last-activity,
        is-running, process-alive) gate within 1 s, others within 2 s;
        ``probe`` ops (observe and is-attached, which gc stops at 4 s) query
        within 1.5 s, others within 3 s.
        """
        return cls(hello=1.0 if read else 2.0, query=1.5 if probe else 3.0)


class CoreEndpoint:
    """One core as this process sees it: its socket and its gate.

    Every client of the core in the process shares the endpoint (a
    long-lived process may run many at once), so the core is gated once per
    connection generation. The generation moves on whenever a connection is
    lost or refused.
    """

    def __init__(self, socket_path: str, *, policy: VersionPolicy) -> None:
        self.socket_path = socket_path
        self.policy = policy
        self._lock = threading.Lock()
        self._generation = 0
        self._gate: Optional[Tuple[int, GateResult]] = None
        self._ids = itertools.count(1)

    def next_id(self) -> int:
        with self._lock:
            return next(self._ids)

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def current_gate(self) -> Optional[GateResult]:
        """The gate passed in the current generation, if any."""
        with self._lock:
            if self._gate is not None and self._gate[0] == self._generation:
                return self._gate[1]
            return None

    def record_gate(self, generation: int, result: GateResult) -> None:
        with self._lock:
            if generation == self._generation:
                self._gate = (generation, result)

    def connection_lost(self, generation: int) -> None:
        """A connection made in ``generation`` failed: the next call gates again."""
        with self._lock:
            if generation == self._generation:
                self._generation += 1


class HcClient:
    """Typed calls to one core for one op, within the op's deadline and cancel token."""

    def __init__(
        self,
        endpoint: CoreEndpoint,
        *,
        deadline: Deadline,
        cancel: CancelToken,
        timeouts: CallTimeouts,
        inject_unavailable: bool = False,
    ) -> None:
        """``inject_unavailable`` is the ``conformance-faults`` knob
        (``GC_RPP_FAULT=unavailable``): every call fails at its call site, as
        if the core were down, before anything is written."""
        self._endpoint = endpoint
        self._deadline = deadline
        self._cancel = cancel
        self._timeouts = timeouts
        self._inject_unavailable = inject_unavailable

    @property
    def gate_warnings(self) -> Tuple[str, ...]:
        """Warnings from the current gate (a newer core outside the tested list)."""
        result = self._endpoint.current_gate()
        return () if result is None else result.warnings

    # --- typed methods ------------------------------------------------------

    def hello(self) -> HelloResult:
        """The gated core's hello (sent only when the generation has none)."""
        return self._gate().hello

    def server_status(self) -> StatusResult:
        return self._typed("server.status", {}, _Budget(self._timeouts.query), parse_status)

    def server_stop(self) -> StopResult:
        """Stop the core and every program it runs."""
        return self._typed("server.stop", {}, _Budget(self._timeouts.server_stop), parse_stop)

    def run(self, spec: RunSpec) -> Terminal:
        """Start a program, detached from any caller (never ``caller``/``parent``)."""
        params: Dict[str, object] = {
            "argv": list(spec.argv),
            "cwd": spec.cwd,
            "env": dict(spec.env),
            "labels": dict(spec.labels),
            "name": spec.name,
            "keep": False,
            "no_parent": True,
            "no_notify": True,
        }
        return self._typed("terminal.run", params, _Budget(self._timeouts.run), parse_terminal)

    def get(self, terminal: str) -> Terminal:
        return self._typed("terminal.get", {"terminal": terminal}, _Budget(self._timeouts.query), parse_terminal)

    def list_terminals(
        self, *, labels: Optional[Mapping[str, str]] = None, include_finished: bool = False
    ) -> ListResult:
        """Terminals matching every label in ``labels``; finished ones only on request."""
        params: Dict[str, object] = {}
        if include_finished:
            params["all"] = True
        if labels:
            params["labels"] = dict(labels)
        return self._typed("terminal.list", params, _Budget(self._timeouts.query), parse_list)

    def label(self, terminal: str, labels: Mapping[str, str]) -> Terminal:
        """Set labels; an empty value removes one."""
        params: Dict[str, object] = {"terminal": terminal, "labels": dict(labels)}
        return self._typed("terminal.label", params, _Budget(self._timeouts.query), parse_terminal)

    def read_screen(self, terminal: str) -> ReadResult:
        """The screen only: a full-screen program's history is read by
        scrolling it, which sends it input (hc.openrpc.json ``ReadResult.how``)."""
        params: Dict[str, object] = {"terminal": terminal, "lines": 0}
        return self._typed("terminal.read", params, _Budget(self._timeouts.query), parse_read)

    def send(self, terminal: str, text: str) -> SendResult:
        """Type ``text`` and submit it, with no ``if`` precondition and no ``caller``."""
        params: Dict[str, object] = {"terminal": terminal, "text": text}
        # hc may hold a send for as long as a person types: it gets all the
        # time the op has left, less the reserve.
        budget = _Budget(float("inf"), margin=self._timeouts.send_reserve)
        return self._typed("terminal.send", params, budget, parse_send)

    def keys(self, terminal: str, keys: Sequence[str]) -> KeysResult:
        params: Dict[str, object] = {"terminal": terminal, "keys": list(keys)}
        return self._typed("terminal.keys", params, _Budget(self._timeouts.keys), parse_keys)

    def interrupt(self, terminal: str) -> InterruptResult:
        params: Dict[str, object] = {"terminal": terminal, "timeout": INTERRUPT_WAIT_S}
        return self._typed("terminal.interrupt", params, _Budget(self._timeouts.interrupt), parse_interrupt)

    def kill(self, terminal: str) -> Terminal:
        """HUP, TERM, then KILL to the program's and the foreground process groups."""
        return self._typed("terminal.kill", {"terminal": terminal}, _Budget(self._timeouts.kill), parse_terminal)

    def remove(self, terminal: str) -> RemoveResult:
        """Remove a finished record (``terminal.rm``)."""
        return self._typed("terminal.rm", {"terminal": terminal}, _Budget(self._timeouts.query), parse_remove)

    # --- machinery ------------------------------------------------------------

    def _typed(self, method: str, params: Dict[str, object], budget: _Budget, parser: Callable[[object], T]) -> T:
        try:
            self._gate()
        except HcError as err:
            err.written = False  # the caller's own request was never sent
            raise
        raw, _ = self._call(method, params, budget)
        try:
            return parser(raw)
        except JsonShapeError as err:
            raise HcProtocolError(method, f"malformed result: {err}", written=True) from None

    def _gate(self) -> GateResult:
        cached = self._endpoint.current_gate()
        if cached is not None:
            return cached
        try:
            raw, generation = self._call("hello", {"generation": GENERATION}, _Budget(self._timeouts.hello))
        except HcRpcError as err:
            raise HcGateError("hello", f"hc version unsupported: the core refused hello ({err.kind}) (run gc doctor)") from None
        try:
            hello = parse_hello(raw)
        except JsonShapeError as err:
            raise HcProtocolError("hello", f"malformed result: {err}", written=True) from None
        result = gate(hello, self._endpoint.policy)
        self._endpoint.record_gate(generation, result)
        return result

    def _call(self, method: str, params: Dict[str, object], budget: _Budget) -> Tuple[object, int]:
        """One exchange, plus one retry of an idempotent read whose connection dropped."""
        generation = self._endpoint.generation
        try:
            return self._exchange(method, params, budget), generation
        except HcUnreachable:
            self._endpoint.connection_lost(generation)
            raise
        except HcConnectionLost:
            self._endpoint.connection_lost(generation)
            if method not in IDEMPOTENT_METHODS:
                raise
        if method != "hello":
            self._gate()  # the drop may have been a core restart: gate the new core first
        generation = self._endpoint.generation
        try:
            return self._exchange(method, params, budget), generation
        except (HcUnreachable, HcConnectionLost):
            self._endpoint.connection_lost(generation)
            raise

    def _exchange(self, method: str, params: Dict[str, object], budget: _Budget) -> object:
        if self._inject_unavailable:
            raise HcUnreachable(method, "the backend is unavailable (GC_RPP_FAULT=unavailable)")
        if self._cancel.cancelled:
            raise HcCancelled(method, self._cancel.reason, written=False)
        timeout = self._deadline.budget(budget.cap, margin=budget.margin)
        if timeout <= 0:
            raise HcTimeout(method, "no time left before the op's deadline", written=False)
        ends = time.monotonic() + timeout
        request_id = self._endpoint.next_id()
        line = dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n"
        conn = self._connect(method, min(self._timeouts.connect, timeout))
        try:
            self._send_line(conn, method, line.encode("ascii"), ends, timeout)
            reply = self._read_line(conn, method, ends, timeout)
        finally:
            conn.close()
        return self._result(method, request_id, reply)

    def _connect(self, method: str, timeout: float) -> socket.socket:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            conn.settimeout(timeout)
            conn.connect(self._endpoint.socket_path)
        except socket.timeout:
            conn.close()
            raise HcUnreachable(method, f"the core accepted no connection within {timeout:.1f}s") from None
        except OSError as err:
            conn.close()
            raise HcUnreachable(method, f"no core answers its socket ({err.strerror or type(err).__name__})") from None
        return conn

    def _arm(self, conn: socket.socket, method: str, ends: float, timeout: float, *, written: bool) -> None:
        # Socket waits run in POLL_INTERVAL_S steps so a cancel lands promptly.
        if self._cancel.cancelled:
            raise HcCancelled(method, self._cancel.reason, written=written)
        left = ends - time.monotonic()
        if left <= 0:
            raise HcTimeout(method, f"timed out after {timeout:.1f}s", written=written)
        conn.settimeout(min(POLL_INTERVAL_S, left))

    def _send_line(self, conn: socket.socket, method: str, line: bytes, ends: float, timeout: float) -> None:
        sent = 0
        while sent < len(line):
            # Once any byte is out, hc may have the request: it counts as written.
            self._arm(conn, method, ends, timeout, written=sent > 0)
            try:
                sent += conn.send(line[sent:])
            except socket.timeout:
                continue
            except OSError:
                raise HcConnectionLost(
                    method, "the core closed the connection while the request was sent", written=sent > 0
                ) from None

    def _read_line(self, conn: socket.socket, method: str, ends: float, timeout: float) -> bytes:
        reply = bytearray()
        while True:
            self._arm(conn, method, ends, timeout, written=True)
            try:
                chunk = conn.recv(_RECV_BYTES)
            except socket.timeout:
                continue
            except OSError:
                raise HcConnectionLost(method, "the core reset the connection before replying", written=True) from None
            if not chunk:
                raise HcConnectionLost(method, "the core closed the connection before replying", written=True)
            end = chunk.find(b"\n")
            if end >= 0:
                reply += chunk[:end]
                return bytes(reply)
            reply += chunk
            if len(reply) > MAX_REPLY_BYTES:
                raise HcProtocolError(method, f"reply over {MAX_REPLY_BYTES} bytes", written=True)

    def _result(self, method: str, request_id: int, line: bytes) -> object:
        try:
            envelope = JsonObject.of(loads(line))
            if envelope.raw("jsonrpc") != "2.0" or envelope.opt_int("id") != request_id:
                raise HcProtocolError(method, "the reply does not answer this request", written=True)
            error = envelope.opt_obj("error")
            if error is not None:
                data = error.opt_obj("data")
                raise HcRpcError(
                    method,
                    kind="" if data is None else data.str_or("kind", ""),
                    code=error.int_or("code", 0),
                    message=error.str_or("message", ""),
                    hint="" if data is None else data.str_or("hint", ""),
                )
            if not envelope.has("result"):
                raise HcProtocolError(method, "the reply has neither a result nor an error", written=True)
            return envelope.raw("result")
        except JsonShapeError as err:
            raise HcProtocolError(method, f"malformed reply: {err}", written=True) from None
