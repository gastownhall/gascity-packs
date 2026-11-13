"""The herdr-core JSON-RPC client, over hc's plain mode (one JSON-RPC message
per line; hc ``schema/README.md`` "Connecting").

* One plain-mode connection per call. A plain connection answers one request
  at a time (hc ``crates/herdr-core/src/server.rs``, ``connection``), and a
  ``send`` waits until nobody has typed for about 3 s (hc.openrpc.json
  ``terminal.send``), so concurrent calls never share a connection.
* Every connection opens with the core's ``hello``, gated
  (:func:`.version.gate`) before the call is written on that same
  connection. A connection ends with the core that accepted it, so a core
  restarted, upgraded or replaced between two calls, idle or not, is gated
  before it is sent anything, and a core the gate refuses is never sent the
  call.
* A call's timeout is its table value (:class:`CallTimeouts`) cut to end one
  second before the op's deadline (:meth:`~..rpp.cancel.Deadline.budget`);
  ``send`` gets the deadline less two seconds. A call with no time left is
  not sent at all.
* A connection the core drops during the hello is replaced once, gated
  again. ``terminal.get``, ``terminal.list`` and ``terminal.read`` are also
  retried once, on a fresh gated connection, when the core drops the first
  before replying. Nothing else is: ``run``, ``send``, ``keys``,
  ``interrupt`` and ``kill`` are not idempotent, and hc has no request ids to
  dedupe them.
* Every failure is an :class:`~.errors.HcError` that says whether the request
  may have reached the core.
* ``conformance-faults`` (:data:`BackendFault`, ``GC_RPP_FAULT``) are injected
  here, at the backend call, so every op takes its real path from the
  failure: ``unavailable`` fails every call before anything is written;
  ``blocked`` has the core refuse a ``send`` as hc refuses a program waiting
  on its own question; ``lose_reply`` and ``hold_send`` let an input call
  (and ``terminal.get``, ``clear-scrollback``'s own call) reach the core
  and be done, then drop its reply, as a lost connection or a send held past
  the op's deadline does; ``dead`` reads every record as finished, as the
  core does once the box's program has ended.
"""

from __future__ import annotations

import itertools
import socket
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, Final, FrozenSet, Literal, Mapping, Optional, Sequence, Tuple, TypeVar

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
"""The only methods retried, once, when a connection drops before the reply
(any call is, when the connection drops during its hello)."""

BackendFault = Literal["unavailable", "blocked", "lose_reply", "hold_send", "dead"]
"""The ``GC_RPP_FAULT`` values ``conformance-faults`` injects (gascity
``exec-session-provider.md``, "Protocol Handshake" and "Typed input outcomes")."""

INPUT_METHODS: Final[FrozenSet[str]] = frozenset({"terminal.send", "terminal.keys", "terminal.interrupt"})
"""The calls that put input into a terminal."""

_REPLY_LOST_METHODS: Final[FrozenSet[str]] = INPUT_METHODS | {"terminal.get"}
"""The calls ``lose_reply`` and ``hold_send`` drop the reply of: the input
calls, and ``terminal.get``, the call ``clear-scrollback`` delivers with."""

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
    """One core as this process sees it: its socket and its version policy.

    Every client of the core in the process shares the endpoint (a
    long-lived process may run many at once), and with it the request ids.
    It keeps no gate: a gate holds only for the connection it was passed on,
    and every call gates its own.
    """

    def __init__(self, socket_path: str, *, policy: VersionPolicy) -> None:
        self.socket_path = socket_path
        self.policy = policy
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def next_id(self) -> int:
        with self._lock:
            return next(self._ids)


class HcClient:
    """Typed calls to one core for one op, within the op's deadline and cancel token."""

    def __init__(
        self,
        endpoint: CoreEndpoint,
        *,
        deadline: Deadline,
        cancel: CancelToken,
        timeouts: CallTimeouts,
        fault: Optional[BackendFault] = None,
    ) -> None:
        """``fault`` is the ``conformance-faults`` knob (``GC_RPP_FAULT``),
        injected at each call (see the module's docstring)."""
        self._endpoint = endpoint
        self._deadline = deadline
        self._cancel = cancel
        self._timeouts = timeouts
        self._fault = fault
        self._last_gate: Optional[GateResult] = None

    @property
    def gate_warnings(self) -> Tuple[str, ...]:
        """Warnings from the last gate passed (a newer core outside the tested list)."""
        return () if self._last_gate is None else self._last_gate.warnings

    # --- typed methods ------------------------------------------------------

    def hello(self) -> HelloResult:
        """The core's hello, gated, on a connection that carries nothing else."""
        return self._typed("hello", {}, _Budget(self._timeouts.hello), parse_hello)

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
        return self._as_found(
            self._typed("terminal.get", {"terminal": terminal}, _Budget(self._timeouts.query), parse_terminal)
        )

    def list_terminals(
        self, *, labels: Optional[Mapping[str, str]] = None, include_finished: bool = False
    ) -> ListResult:
        """Terminals matching every label in ``labels``; finished ones only on request."""
        params: Dict[str, object] = {}
        if include_finished:
            params["all"] = True
        if labels:
            params["labels"] = dict(labels)
        listed = self._typed("terminal.list", params, _Budget(self._timeouts.query), parse_list)
        if self._fault != "dead":
            return listed
        found = tuple(self._as_found(t) for t in listed.terminals)
        shown = found if include_finished else tuple(t for t in found if t.is_live)
        return replace(listed, terminals=shown, hidden_finished=listed.hidden_finished + len(found) - len(shown))

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

    def _as_found(self, terminal: Terminal) -> Terminal:
        """``terminal`` as the core reports it: under ``dead``, a live record
        is finished, as when its program has exited."""
        if self._fault != "dead" or not terminal.is_live:
            return terminal
        return replace(terminal, state="finished", reason="exited", exit_code=0, finished_ms=terminal.created_ms)

    def _typed(self, method: str, params: Dict[str, object], budget: _Budget, parser: Callable[[object], T]) -> T:
        raw = self._call(method, params, budget)
        try:
            return parser(raw)
        except JsonShapeError as err:
            raise HcProtocolError(method, f"malformed result: {err}", written=True) from None

    def _call(self, method: str, params: Dict[str, object], budget: _Budget) -> object:
        """One gated connection, plus one more when the first drops during its
        hello or, for an idempotent method, before the reply."""
        try:
            return self._gated_call(method, params, budget)
        except HcConnectionLost as err:
            # A drop during the hello wrote nothing of the call; after it, the
            # call may have reached the core, and only a read is sent twice.
            if err.method != "hello" and method not in IDEMPOTENT_METHODS:
                raise
        return self._gated_call(method, params, budget)

    def _gated_call(self, method: str, params: Dict[str, object], budget: _Budget) -> object:
        """Connect, gate the core on its hello, then send ``method`` on the same
        connection (a ``hello`` call is the gate alone)."""
        if self._fault == "unavailable":
            raise HcUnreachable(method, "the backend is unavailable (GC_RPP_FAULT=unavailable)")
        if self._fault == "blocked" and method == "terminal.send" and not params.get("force"):
            raise HcRpcError(
                method,
                kind="blocked",
                code=-32000,
                message="the program is waiting on its own question; nothing was typed (GC_RPP_FAULT=blocked)",
                hint="",
            )
        self._timeout(method, budget)  # a call with no time left opens no connection
        hello_timeout = self._timeout("hello", _Budget(self._timeouts.hello))
        hello_ends = time.monotonic() + hello_timeout
        conn = self._connect(method, min(self._timeouts.connect, hello_timeout))
        try:
            try:
                hello = self._gate(conn, hello_ends, hello_timeout)
            except HcError as err:
                if method != "hello":
                    err.written = False  # the call itself was never sent
                raise
            if method == "hello":
                return hello
            timeout = self._timeout(method, budget)
            reply = self._exchange(conn, method, params, time.monotonic() + timeout, timeout)
            self._drop_reply(method)
            return reply
        finally:
            conn.close()

    def _drop_reply(self, method: str) -> None:
        """Under ``lose_reply`` and ``hold_send``, the core did the call, and
        its reply never arrives."""
        if method not in _REPLY_LOST_METHODS:
            return
        if self._fault == "lose_reply":
            raise HcConnectionLost(method, "the reply was lost (GC_RPP_FAULT=lose_reply)", written=True)
        if self._fault == "hold_send":
            raise HcTimeout(method, "held past the op's deadline (GC_RPP_FAULT=hold_send)", written=True)

    def _gate(self, conn: socket.socket, ends: float, timeout: float) -> object:
        """The core's hello on ``conn``, once the gate has passed it."""
        try:
            raw = self._exchange(conn, "hello", {"generation": GENERATION}, ends, timeout)
        except HcRpcError as err:
            raise HcGateError("hello", f"hc version unsupported: the core refused hello ({err.kind}) (run gc doctor)") from None
        try:
            hello = parse_hello(raw)
        except JsonShapeError as err:
            raise HcProtocolError("hello", f"malformed result: {err}", written=True) from None
        self._last_gate = gate(hello, self._endpoint.policy)
        return raw

    def _timeout(self, method: str, budget: _Budget) -> float:
        """``budget`` from now; a call that is canceled or has no time left is not sent."""
        if self._cancel.cancelled:
            raise HcCancelled(method, self._cancel.reason, written=False)
        timeout = self._deadline.budget(budget.cap, margin=budget.margin)
        if timeout <= 0:
            raise HcTimeout(method, "no time left before the op's deadline", written=False)
        return timeout

    def _exchange(
        self, conn: socket.socket, method: str, params: Dict[str, object], ends: float, timeout: float
    ) -> object:
        """One request and its reply on ``conn``."""
        request_id = self._endpoint.next_id()
        line = dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n"
        self._send_line(conn, method, line.encode("ascii"), ends, timeout)
        reply = self._read_line(conn, method, ends, timeout)
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

    def _arm(
        self, conn: socket.socket, method: str, ends: float, timeout: float, *, written: bool, partial: bool = False
    ) -> None:
        # Socket waits run in POLL_INTERVAL_S steps so a cancel lands promptly.
        if self._cancel.cancelled:
            raise HcCancelled(method, self._cancel.reason, written=written, partial=partial)
        left = ends - time.monotonic()
        if left <= 0:
            raise HcTimeout(method, f"timed out after {timeout:.1f}s", written=written, partial=partial)
        conn.settimeout(min(POLL_INTERVAL_S, left))

    def _send_line(self, conn: socket.socket, method: str, line: bytes, ends: float, timeout: float) -> None:
        sent = 0
        while sent < len(line):
            # Once any byte is out, hc may have the request: it counts as written.
            # Short of the JSON's last byte it is partial: hc parses none of it.
            written, partial = sent > 0, 0 < sent < len(line) - 1
            self._arm(conn, method, ends, timeout, written=written, partial=partial)
            try:
                sent += conn.send(line[sent:])
            except socket.timeout:
                continue
            except OSError:
                raise HcConnectionLost(
                    method, "the core closed the connection while the request was sent", written=written, partial=partial
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
