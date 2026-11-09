"""One fake-hc terminal: a real child process, without a PTY, in its own session.

Pids, sessions and process trees are therefore true, so tests can check
what a kill or a holder loss does to them. The screen is a
capped tail of the program's output; typed text and keys are logged.
Records follow hc v0.1.19 (``crates/herdr-core/src``: ``terminals.rs``,
``runtime.rs``, ``kept.rs``, ``status.rs``): an exit resets the status and
finishes the record, which keeps its last pid; a kept terminal that loses its
program stays live with no pid, refuses input, and gets a new shell after
1.5 s, which clears the reason.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from typing import Any, Dict, IO, List, Mapping, Optional, Sequence

TAIL_BYTES = 64 << 10
SCREEN_ROWS = 120
SCREEN_COLS = 200

KEY_BYTES: Mapping[str, bytes] = {
    "enter": b"\n",
    "esc": b"\x1b",
    "tab": b"\t",
    "backspace": b"\x7f",
    "space": b" ",
    "up": b"\x1b[A",
    "down": b"\x1b[B",
    "right": b"\x1b[C",
    "left": b"\x1b[D",
    "home": b"\x1b[H",
    "end": b"\x1b[F",
    "delete": b"\x1b[3~",
    "pageup": b"\x1b[5~",
    "pagedown": b"\x1b[6~",
    **{f"f{n}": f"\x1b[{n}~".encode() for n in range(1, 13)},
}


def now_ms() -> int:
    return int(time.time() * 1000)


def key_bytes(key: str) -> Optional[bytes]:
    """The bytes a key types into a pipe, or None for an unknown key (ctrl+c is a signal)."""
    if key in KEY_BYTES:
        return KEY_BYTES[key]
    if key.startswith("ctrl+") and len(key) == 6 and key[5].isalpha():
        return bytes([ord(key[5].lower()) & 0x1F])
    if key.startswith("alt+") and len(key) == 5:
        return b"\x1b" + key[4].encode()
    if len(key) == 1 and key.isprintable():
        return key.encode()
    return None


def killpg(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


KEPT_RESTART_S = 1.5
"""hc's first wait before a lost kept terminal gets its new shell (KEEP_RETRY_MS)."""


class FakeTerminal:
    """A terminal record and the program behind it."""

    def __init__(
        self,
        *,
        address: str,
        name: Optional[str],
        labels: Dict[str, str],
        argv: Sequence[str],
        cwd: str,
        env: Mapping[str, str],
        keep: bool,
        restart_delay_s: float = KEPT_RESTART_S,
    ) -> None:
        self.address = address
        self.name = name
        self.labels = labels
        self.argv = list(argv)
        self.program = list(argv)  # what runs now: the command, or a kept terminal's new shell
        self.cwd = cwd
        self.env = dict(env)
        self.keep = keep
        self.created_ms = now_ms()
        self.state = "live"
        self.reason: Optional[str] = None
        self.exit_code: Optional[int] = None
        self.signal: Optional[int] = None
        self.finished_ms: Optional[int] = None
        self.screen = "exact"
        self.status: Optional[Dict[str, Any]] = None
        self.reported = False
        self.status_ms: Optional[int] = None
        self.turn = 0
        self.work_on_send = False
        self.held = False
        self.inputs: List[str] = []
        self.keys: List[str] = []
        self.tail = bytearray()
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        # hc's per-terminal input queue: send, keys and interrupt run one at a time.
        self.input_lock = threading.Lock()
        # The record's pid: the running program's, the last one's once the
        # record finished, None while a kept terminal waits for its new shell.
        self.pid: Optional[int] = None
        self._ending: Optional[str] = None
        self._incarnation = 0
        self._threads: List[threading.Thread] = []
        self._restart_delay_s = restart_delay_s
        self._restart: Optional[threading.Timer] = None
        self._reaped = False
        self.proc = self._spawn(self.argv)

    @property
    def lost(self) -> bool:
        """A kept terminal between losing its program and getting its new shell."""
        return self.state == "live" and self.pid is None and self.reason is not None

    # --- process ---------------------------------------------------------------

    def _spawn(self, argv: Sequence[str]) -> "subprocess.Popen[bytes]":
        proc = subprocess.Popen(
            list(argv),
            cwd=self.cwd,
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.pid = proc.pid
        incarnation = self._incarnation
        for target in (self._read_output, self._await_exit):
            thread = threading.Thread(target=target, args=(proc, incarnation), daemon=True)
            thread.start()
            self._threads.append(thread)
        return proc

    def _read_output(self, proc: "subprocess.Popen[bytes]", incarnation: int) -> None:
        stream: Optional[IO[bytes]] = proc.stdout
        if stream is None:
            return
        while True:
            try:
                chunk = os.read(stream.fileno(), 1 << 16)
            except OSError:
                return
            if not chunk:
                return
            with self.lock:
                self.tail += chunk
                del self.tail[: max(0, len(self.tail) - TAIL_BYTES)]
                self.changed.notify_all()

    def _await_exit(self, proc: "subprocess.Popen[bytes]", incarnation: int) -> None:
        code = proc.wait()
        with self.lock:
            if incarnation != self._incarnation or self.state != "live":
                return
            if self._ending is not None:
                self._finish(self._ending, code)
            elif self.keep and code < 0:
                # hc: a kept program killed by a signal, with no exit code, is
                # lost (reason "signaled"), not ended (runtime.rs record_finish).
                self._lose("signaled", code)
            else:
                self._finish("exited", code)

    def _reset_status(self) -> None:
        # hc status.rs reset: the record goes, a working turn ends with it, and
        # status_ms marks the word changing.
        was = None if self.status is None else str(self.status["state"])
        self.status = None
        if was == "working":
            self.turn += 1
        if was is not None:
            self.status_ms = now_ms()

    def _set_exit(self, code: Optional[int]) -> None:
        if code is None:
            self.exit_code, self.signal = None, None
        elif code >= 0:
            self.exit_code, self.signal = code, None
        else:
            self.exit_code, self.signal = None, -code

    def _finish(self, reason: str, code: Optional[int]) -> None:
        """The record ends. It keeps its last pid (hc terminals.rs finish)."""
        self._reset_status()
        self.state = "finished"
        self.reason = reason
        self.finished_ms = now_ms()
        self._set_exit(code)
        self._cancel_restart()
        self.changed.notify_all()

    def _lose(self, reason: str, code: Optional[int]) -> None:
        """A kept terminal loses its program: live, no pid, input refused until a new shell."""
        self._reset_status()
        self.reason = reason
        self.pid = None
        self.finished_ms = None
        self._set_exit(code)
        self._cancel_restart()
        timer = threading.Timer(self._restart_delay_s, self._restart_shell)
        timer.daemon = True
        self._restart = timer
        timer.start()
        self.changed.notify_all()

    def _cancel_restart(self) -> None:
        if self._restart is not None:
            self._restart.cancel()
            self._restart = None

    def _restart_shell(self) -> None:
        # hc runtime.rs spawn_result: the new program's pid, and the reason,
        # exit code and signal cleared.
        with self.lock:
            if self._reaped or not self.lost:
                return
            self._restart = None
            self._incarnation += 1
            self.program = ["/bin/sh"]
            self.proc = self._spawn(self.program)
            self.reason = None
            self.exit_code = None
            self.signal = None
            self.changed.notify_all()

    def kill(self, grace_s: float) -> None:
        """HUP, TERM, then KILL to the program's process group, waiting ``grace_s`` between."""
        with self.lock:
            if self.state != "live":
                return
            if self.lost:
                # Nothing runs to signal: the kill ends the record (hc runtime.rs kill).
                self._finish("killed", None)
                return
            self._ending = "killed"
            proc = self.proc
        for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGKILL):
            killpg(proc.pid, sig)
            try:
                proc.wait(timeout=grace_s if sig != signal.SIGKILL else 2.0)
                break
            except subprocess.TimeoutExpired:
                continue
        with self.lock:
            self.changed.wait_for(lambda: self.state != "live", timeout=2.0)

    def end(self, reason: str) -> None:
        """End the program with SIGKILL and finish the record with ``reason``."""
        with self.lock:
            if self.state != "live":
                return
            if self.lost:
                self._finish(reason, None)
                return
            self._incarnation += 1  # the old program's exit no longer finishes the record
            proc = self.proc
        killpg(proc.pid, signal.SIGKILL)
        code = proc.wait()
        with self.lock:
            self._finish(reason, code)

    def lose_holder(self) -> None:
        """The holder died: a kept terminal waits for a new shell, any other finishes."""
        with self.lock:
            if self.state != "live" or self.lost:
                return
            self._incarnation += 1  # the program's exit is recorded here, not by its waiter
            proc = self.proc
        killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        with self.lock:
            if self.state != "live":
                return
            if self.keep:
                self._lose("holder_lost", None)
            else:
                self._finish("holder_lost", None)

    def reap(self) -> None:
        """Kill the program's whole group and collect it (fake shutdown)."""
        with self.lock:
            self._reaped = True
            self._cancel_restart()
            self._incarnation += 1
            proc = self.proc
        killpg(proc.pid, signal.SIGKILL)
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pass
        for stream in (proc.stdin, proc.stdout):
            if stream is not None:
                stream.close()
        for thread in self._threads:
            thread.join(timeout=1.0)

    # --- input -------------------------------------------------------------------

    def type_bytes(self, data: bytes) -> bool:
        """Write to the program's stdin; False when it is gone."""
        stdin = self.proc.stdin
        if stdin is None:
            return False
        try:
            stdin.write(data)
            stdin.flush()
        except (BrokenPipeError, ValueError):
            return False
        return True

    def interrupt_signal(self) -> None:
        killpg(self.proc.pid, signal.SIGINT)

    # --- status --------------------------------------------------------------------

    def set_status(self, state: str, *, kind: Optional[str], app: str, progress: Optional[int]) -> None:
        # hc status.rs apply: the turn ends when the word leaves working;
        # status_ms changes only with the word.
        with self.lock:
            previous = None if self.status is None else self.status["state"]
            if previous == "working" and state != "working":
                self.turn += 1
            self.status = {"state": state, "kind": kind, "app": app, "progress": progress, "title": "", "msg": ""}
            self.reported = True
            if previous != state:
                self.status_ms = now_ms()
            self.changed.notify_all()

    def status_word(self) -> Optional[str]:
        with self.lock:
            return None if self.status is None else str(self.status["state"])

    # --- views -----------------------------------------------------------------------

    def screen_text(self, history_lines: int) -> str:
        with self.lock:
            lines = self.tail.decode("utf-8", "replace").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines[-(SCREEN_ROWS + history_lines) :])

    def record(self) -> Dict[str, Any]:
        """The terminal as hc's ``Terminal`` schema shapes it."""
        with self.lock:
            running = self.state == "live" and self.pid is not None
            return {
                "address": self.address,
                "name": self.name,
                "labels": dict(self.labels),
                "argv": list(self.argv),
                "cwd": self.cwd,
                "state": self.state,
                "created_ms": self.created_ms,
                "screen": self.screen,
                "cols": SCREEN_COLS,
                "rows": SCREEN_ROWS,
                "pid": self.pid,
                "foreground": (
                    {
                        "pid": self.proc.pid,
                        "name": os.path.basename(self.program[0]) if self.program else "sh",
                        "argv": list(self.program),
                        "cwd": self.cwd,
                    }
                    if running
                    else None
                ),
                "reason": self.reason,
                "exit_code": self.exit_code,
                "signal": self.signal,
                "finished_ms": self.finished_ms,
                "keep": self.keep,
                "rm": False,
                "parent": None,
                "notify": False,
                "template": None,
                "identity": "",
                "title": "",
                "status": None if self.status is None else dict(self.status),
                "records": {},
                "reported": self.reported,
                "status_ms": self.status_ms,
                "turn": self.turn,
            }
