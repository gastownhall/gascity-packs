"""The hc client against fake-hc: typed methods, the budget table (with and
without GC_EXEC_DEADLINE_MS), retry rules and the `written` and `partial` contract."""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path
from typing import Callable, cast

import pytest

from fakehc import FakeHc
from gc_runtime_herdr_core.hc.client import CallTimeouts, CoreEndpoint, HcClient
from gc_runtime_herdr_core.hc.errors import (
    HcCancelled,
    HcConnectionLost,
    HcGateError,
    HcProtocolError,
    HcRpcError,
    HcTimeout,
    HcUnreachable,
)
from gc_runtime_herdr_core.hc.types import RunSpec, Terminal
from gc_runtime_herdr_core.hc.version import VersionPolicy
from gc_runtime_herdr_core.rpp.jsonval import dumps
from gc_runtime_herdr_core.rpp.cancel import CancelToken, Cancelled, Deadline

ClientFactory = Callable[..., HcClient]

ECHO_LOOP = 'echo ready; while IFS= read -r line; do printf "got:%s\\n" "$line"; done'


def spec(name: str, workdir: Path, **labels: str) -> RunSpec:
    return RunSpec(
        argv=("/bin/sh", "-c", ECHO_LOOP),
        cwd=str(workdir),
        env={"TERM": "xterm-256color"},
        labels={"gc.city": "c0ffee", "gc.session": name, **labels},
        name=name,
    )


def wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


def started(client: HcClient, name: str, workdir: Path) -> Terminal:
    term = client.run(spec(name, workdir))
    wait_for(lambda: "ready" in client.read_screen(term.address).text)
    return term


# --- typed methods -----------------------------------------------------------


def test_typed_methods_round_trip(make_client: ClientFactory, short_tmp: Path) -> None:
    client = make_client()
    term = started(client, "ga", short_tmp)
    assert term.is_live and term.name == "ga" and term.pid is not None
    assert dict(term.labels) == {"gc.city": "c0ffee", "gc.session": "ga"}

    assert client.get(term.address).address == term.address
    listed = client.list_terminals(labels={"gc.city": "c0ffee"})
    assert [t.address for t in listed.terminals] == [term.address]
    assert client.list_terminals(labels={"gc.city": "other"}).terminals == ()

    labelled = client.label(term.address, {"gc.pid": str(term.pid)})
    assert labelled.labels["gc.pid"] == str(term.pid)

    sent = client.send(term.address, "hello")
    assert sent.started is None  # the program never reports status
    wait_for(lambda: "got:hello" in client.read_screen(term.address).text)

    assert client.keys(term.address, ["enter"]).turn >= 0
    assert client.interrupt(term.address).key in ("esc", "ctrl+c")

    killed = client.kill(term.address)
    assert killed.is_finished
    assert client.remove(term.address).removed == term.address
    assert client.list_terminals(include_finished=True).terminals == ()

    status = client.server_status()
    assert status.version == "0.1.19" and status.live == 0


def test_run_detaches_and_never_names_a_caller_or_parent(
    make_client: ClientFactory, fake_hc: FakeHc, short_tmp: Path
) -> None:
    make_client().run(spec("ga", short_tmp))
    (params,) = [c.params for c in fake_hc.calls if c.method == "terminal.run"]
    assert params["no_parent"] is True
    assert params["no_notify"] is True
    assert params["keep"] is False
    assert "caller" not in params and "parent" not in params and "line" not in params


def test_send_read_and_interrupt_send_only_their_fixed_params(
    make_client: ClientFactory, fake_hc: FakeHc, short_tmp: Path
) -> None:
    client = make_client()
    term = started(client, "ga", short_tmp)
    client.send(term.address, "x")
    client.interrupt(term.address)
    sends = [c.params for c in fake_hc.calls if c.method == "terminal.send"]
    reads = [c.params for c in fake_hc.calls if c.method == "terminal.read"]
    interrupts = [c.params for c in fake_hc.calls if c.method == "terminal.interrupt"]
    assert sends == [{"terminal": term.address, "text": "x"}]  # no `if`, no `caller`
    assert reads and all(p == {"terminal": term.address, "lines": 0} for p in reads)  # screen only
    assert interrupts == [{"terminal": term.address, "timeout": 3.0}]


# --- the gate ----------------------------------------------------------------


def test_every_call_gates_the_connection_it_is_sent_on(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    client = make_client()
    client.list_terminals()
    client.list_terminals()
    assert [c.method for c in fake_hc.calls] == ["hello", "terminal.list", "hello", "terminal.list"]
    assert [c.params for c in fake_hc.calls if c.method == "hello"] == [{"generation": 1}] * 2
    assert fake_hc.connections == 2  # each hello shares its call's connection


def test_an_old_core_is_refused_before_any_call(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    fake_hc.set_version("0.1.18")
    with pytest.raises(HcGateError) as caught:
        make_client().list_terminals()
    assert caught.value.written is False
    assert fake_hc.call_count("terminal.list") == 0


def test_another_generation_is_refused(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    fake_hc.set_generation(2)
    with pytest.raises(HcGateError) as caught:
        make_client().list_terminals()
    assert caught.value.written is False
    assert fake_hc.call_count("terminal.list") == 0


def test_a_newer_untested_core_passes_with_a_warning(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    fake_hc.set_version("0.1.20")
    client = make_client()
    client.list_terminals()
    assert any("0.1.20" in w for w in client.gate_warnings)


@pytest.mark.parametrize("same_client", [True, False], ids=["same-client", "new-client"])
@pytest.mark.parametrize("method", ["terminal.list", "terminal.run"])
def test_a_core_restarted_while_idle_is_gated_before_the_next_call(
    make_client: ClientFactory,
    fake_hc: FakeHc,
    gate_policy: VersionPolicy,
    short_tmp: Path,
    method: str,
    same_client: bool,
) -> None:
    endpoint = CoreEndpoint(fake_hc.socket_path, policy=gate_policy)
    first = make_client(endpoint=endpoint)
    first.list_terminals()  # gated at 0.1.19
    # Downgraded with no connection open: no call sees the old core go.
    fake_hc.restart_core(version="0.1.18")
    client = first if same_client else make_client(endpoint=endpoint)
    before = fake_hc.call_count(method)
    with pytest.raises(HcGateError) as caught:
        if method == "terminal.run":
            client.run(spec("ga", short_tmp))
        else:
            client.list_terminals()
    assert caught.value.written is False
    assert fake_hc.call_count(method) == before


def test_a_core_that_changed_generation_while_idle_is_refused(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    client = make_client()
    client.list_terminals()
    fake_hc.set_generation(2)
    with pytest.raises(HcGateError) as caught:
        client.list_terminals()
    assert caught.value.written is False
    assert fake_hc.call_count("terminal.list") == 1


def test_a_retried_read_gates_its_fresh_connection(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    fake_hc.drop_reply("terminal.list")
    make_client().list_terminals()
    assert [c.method for c in fake_hc.calls] == ["hello", "terminal.list", "hello", "terminal.list"]
    assert fake_hc.connections == 2


def test_a_core_restarted_under_a_read_is_gated_before_the_retry(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    client = make_client()
    fake_hc.delay_reply("terminal.list", 1.0)
    # The core goes down with the read in flight and comes back downgraded.
    threading.Timer(0.3, fake_hc.restart_core, kwargs={"version": "0.1.18"}).start()
    with pytest.raises(HcGateError):
        client.list_terminals()
    assert [c.method for c in fake_hc.calls] == ["hello", "terminal.list", "hello"]


# --- the budget table ----------------------------------------------------------


def test_reads_on_4s_ops_get_1_5s(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    client = make_client(deadline_s=4.0, read=True, probe=True)
    fake_hc.delay_reply("terminal.list", 0.6)
    client.list_terminals()
    fake_hc.delay_reply("terminal.list", 2.5)
    begun = time.monotonic()
    with pytest.raises(HcTimeout) as caught:
        client.list_terminals()
    assert caught.value.written is True
    assert 1.3 <= time.monotonic() - begun < 2.0


def test_reads_on_other_ops_get_3s(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    fake_hc.delay_reply("terminal.list", 2.0)
    make_client(deadline_s=30.0, read=True).list_terminals()


def test_inner_calls_end_a_second_before_the_op_deadline(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    # As if gc sent GC_EXEC_DEADLINE_MS=2500: the 3 s table value shrinks to
    # what is left less the 1 s margin.
    client = make_client(deadline_s=2.5)
    fake_hc.delay_reply("terminal.list", 2.0)
    begun = time.monotonic()
    with pytest.raises(HcTimeout):
        client.list_terminals()
    assert time.monotonic() - begun < 2.0  # about 1.5 s: not the 3 s table value


def test_without_an_op_deadline_the_per_op_default_applies(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    fake_hc.delay_reply("terminal.list", 2.0)
    make_client(deadline_s=30.0).list_terminals()


def test_send_gets_the_op_deadline_less_two_seconds(
    make_client: ClientFactory, fake_hc: FakeHc, short_tmp: Path
) -> None:
    term = started(make_client(), "ga", short_tmp)
    fake_hc.hold_input(term.address)  # a human keeps typing: hc withholds the send
    client = make_client(deadline_s=4.0)
    begun = time.monotonic()
    with pytest.raises(HcTimeout) as caught:
        client.send(term.address, "nudge-1")
    elapsed = time.monotonic() - begun
    assert caught.value.written is True  # hc may still type it: the outcome is unknown
    assert 1.6 <= elapsed < 2.6
    fake_hc.release_input(term.address)
    wait_for(lambda: fake_hc.input_log(term.address) == ["nudge-1"])
    time.sleep(0.1)
    assert fake_hc.input_log(term.address) == ["nudge-1"]


def test_no_time_left_writes_nothing(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    with pytest.raises(HcTimeout) as caught:
        make_client(deadline_s=0.9).list_terminals()
    assert caught.value.written is False
    assert fake_hc.connections == 0


class CutShort:
    """A connection whose core stops reading after ``room`` bytes of the request."""

    def __init__(self, room: int) -> None:
        self.room = room
        self.got = b""
        self.wait = 0.0

    def settimeout(self, timeout: float) -> None:
        self.wait = timeout

    def send(self, data: bytes) -> int:
        taken = data[: self.room - len(self.got)]
        if not taken:
            time.sleep(self.wait)
            raise socket.timeout("timed out")
        self.got += taken
        return len(taken)


@pytest.mark.parametrize("unsent, partial", [(2, True), (1, False)], ids=["short-of-its-brace", "short-of-its-newline"])
def test_a_send_cut_short_is_partial_unless_only_its_newline_is_missing(
    make_client: ClientFactory, fake_hc: FakeHc, short_tmp: Path, unsent: int, partial: bool
) -> None:
    # hc parses a request only as a whole line, but runs the last line it reads
    # when the connection ends: a send short only of its newline is typed.
    term = started(make_client(), "ga", short_tmp)
    request = {"jsonrpc": "2.0", "id": 1, "method": "terminal.send", "params": {"terminal": term.address, "text": "cut"}}
    line = (dumps(request) + "\n").encode("ascii")
    conn = CutShort(len(line) - unsent)
    with pytest.raises(HcTimeout) as caught:
        make_client()._send_line(cast(socket.socket, conn), "terminal.send", line, time.monotonic() + 0.3, 0.3)
    assert caught.value.written is True
    assert caught.value.partial is partial
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as core:  # the core reads what reached it
        core.settimeout(5.0)
        core.connect(fake_hc.socket_path)
        core.sendall(conn.got)
        core.shutdown(socket.SHUT_WR)
        assert core.recv(1 << 16)  # its answer: the send's result, or a parse error
    assert fake_hc.input_log(term.address) == ([] if partial else ["cut"])


def test_timeout_table_values() -> None:
    probe = CallTimeouts.for_op(read=True, probe=True)
    read = CallTimeouts.for_op(read=True, probe=False)
    mutate = CallTimeouts.for_op(read=False, probe=False)
    assert (probe.hello, probe.query) == (1.0, 1.5)
    assert (read.hello, read.query) == (1.0, 3.0)
    assert (mutate.hello, mutate.query) == (2.0, 3.0)
    assert (mutate.connect, mutate.run, mutate.keys, mutate.interrupt, mutate.kill) == (1.0, 15.0, 10.0, 5.0, 5.0)
    assert mutate.send_reserve == 2.0


# --- retries ---------------------------------------------------------------------


@pytest.mark.parametrize("method", ["hello", "terminal.list", "terminal.get", "terminal.read"])
def test_idempotent_methods_retry_once_on_eof(
    make_client: ClientFactory, fake_hc: FakeHc, short_tmp: Path, method: str
) -> None:
    term = started(make_client(), "ga", short_tmp)
    client = make_client()
    before = fake_hc.call_count(method)
    fake_hc.drop_reply(method)
    if method == "terminal.get":
        client.get(term.address)
    elif method == "terminal.read":
        client.read_screen(term.address)
    else:
        client.list_terminals()
    assert fake_hc.call_count(method) - before == 2


def test_an_idempotent_retry_happens_only_once(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    client = make_client()
    client.list_terminals()
    fake_hc.drop_reply("terminal.list", count=2)
    with pytest.raises(HcConnectionLost) as caught:
        client.list_terminals()
    assert caught.value.written is True
    assert fake_hc.call_count("terminal.list") == 3


def test_a_hello_dropped_before_a_mutation_is_retried_once(
    make_client: ClientFactory, fake_hc: FakeHc, short_tmp: Path
) -> None:
    client = make_client()
    term = started(client, "ga", short_tmp)
    fake_hc.drop_reply("hello")
    client.send(term.address, "once")  # nothing of the send went out on the dropped connection
    fake_hc.drop_reply("hello", count=2)
    with pytest.raises(HcConnectionLost) as caught:
        client.send(term.address, "never")
    assert caught.value.written is False
    assert fake_hc.call_count("terminal.send") == 1
    assert fake_hc.input_log(term.address) == ["once"]


@pytest.mark.parametrize(
    "method",
    ["terminal.send", "terminal.keys", "terminal.interrupt", "terminal.label", "terminal.kill", "terminal.rm", "terminal.run"],
)
def test_mutations_are_never_retried(make_client: ClientFactory, fake_hc: FakeHc, short_tmp: Path, method: str) -> None:
    client = make_client()
    term = started(client, "ga", short_tmp)
    if method == "terminal.rm":
        client.kill(term.address)
    fake_hc.drop_reply(method)
    before = fake_hc.call_count(method)
    with pytest.raises(HcConnectionLost) as caught:
        if method == "terminal.send":
            client.send(term.address, "once")
        elif method == "terminal.keys":
            client.keys(term.address, ["enter"])
        elif method == "terminal.interrupt":
            client.interrupt(term.address)
        elif method == "terminal.label":
            client.label(term.address, {"gc.pid": "1"})
        elif method == "terminal.kill":
            client.kill(term.address)
        elif method == "terminal.rm":
            client.remove(term.address)
        else:
            client.run(spec("gb", short_tmp))
    assert caught.value.written is True
    assert fake_hc.call_count(method) - before == 1
    if method == "terminal.send":
        assert fake_hc.input_log(term.address) == ["once"]
    if method == "terminal.run":
        names = [t.name for t in make_client().list_terminals().terminals]
        assert sorted(n for n in names if n) == ["ga", "gb"]


# --- reachability, errors, cancellation ------------------------------------------


def test_a_missing_socket_is_unreachable_before_writing(short_tmp: Path, gate_policy: VersionPolicy) -> None:
    client = HcClient(
        CoreEndpoint(str(short_tmp / "absent.sock"), policy=gate_policy),
        deadline=Deadline.after(4.0),
        cancel=CancelToken(),
        timeouts=CallTimeouts.for_op(read=True, probe=True),
    )
    with pytest.raises(HcUnreachable) as caught:
        client.list_terminals()
    assert caught.value.written is False


def test_a_refused_socket_is_unreachable(short_tmp: Path, gate_policy: VersionPolicy) -> None:
    path = str(short_tmp / "dead.sock")
    dead = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    dead.bind(path)
    dead.close()  # the file stays; nothing listens
    client = HcClient(
        CoreEndpoint(path, policy=gate_policy),
        deadline=Deadline.after(4.0),
        cancel=CancelToken(),
        timeouts=CallTimeouts.for_op(read=False, probe=False),
    )
    with pytest.raises(HcUnreachable):
        client.send("t1", "x")


def test_core_errors_keep_their_kind(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    fake_hc.fail_next("terminal.get", "not_found", message="no terminal t9")
    with pytest.raises(HcRpcError) as caught:
        make_client().get("t9")
    assert caught.value.kind == "not_found"
    assert caught.value.known_kind == "not_found"
    assert caught.value.written is True


def test_unknown_error_kinds_are_kept_verbatim(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    fake_hc.fail_next("terminal.get", "frobnicated")
    with pytest.raises(HcRpcError) as caught:
        make_client().get("t1")
    assert caught.value.kind == "frobnicated"
    assert caught.value.known_kind is None


def test_a_malformed_reply_is_a_protocol_error(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    client = make_client()
    client.list_terminals()
    fake_hc.garble_reply("terminal.list")
    with pytest.raises(HcProtocolError):
        client.list_terminals()


def test_cancel_interrupts_an_in_flight_call(make_client: ClientFactory, fake_hc: FakeHc, short_tmp: Path) -> None:
    term = started(make_client(), "ga", short_tmp)
    fake_hc.hold_input(term.address)
    token = CancelToken()
    client = make_client(cancel=token)
    threading.Timer(0.2, token.cancel, args=("terminated",)).start()
    begun = time.monotonic()
    with pytest.raises(HcCancelled) as caught:
        client.send(term.address, "x")
    assert time.monotonic() - begun < 1.0
    assert caught.value.written is True
    assert isinstance(caught.value, Cancelled)
    fake_hc.release_input(term.address)


def test_the_conformance_fault_fails_calls_at_the_call_site(make_client: ClientFactory, fake_hc: FakeHc) -> None:
    with pytest.raises(HcUnreachable) as caught:
        make_client(fault="unavailable").list_terminals()
    assert caught.value.written is False
    assert fake_hc.connections == 0


def test_client_reads_no_environment(make_client: ClientFactory, fake_hc: FakeHc, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HC_SOCKET", "/nonexistent/hc.sock")
    monkeypatch.setenv("HC_SESSION", "default")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/nonexistent")
    make_client().list_terminals()  # the endpoint's socket, not the caller's
    assert os.environ["HC_SOCKET"] == "/nonexistent/hc.sock"
