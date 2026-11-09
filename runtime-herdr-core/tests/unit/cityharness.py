"""An in-process city for the op tests: the pack's op table, an in-process
fake-hc on the city's own socket, and a process table whose only fiction is
the core's environment (an in-process fake-hc's pid is the test's own).

``run(op, *args, stdin=...)`` runs one op through the per-op runner, exactly
as the executable would, and returns its exit code, stdout and stderr.
"""

from __future__ import annotations

import io
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from fakehc import FakeHc
from fakehc.cli import write_launcher
from gc_runtime_herdr_core.hc.address import parse_address
from gc_runtime_herdr_core.hc.paths import HcPaths, ensure_dirs, resolve_paths
from gc_runtime_herdr_core.herdrcore.context import Host, OpContext
from gc_runtime_herdr_core.herdrcore.core import core_env
from gc_runtime_herdr_core.herdrcore.ops_table import build_ops
from gc_runtime_herdr_core.herdrcore.procs import LinuxProcs, Proc, ProcSource
from gc_runtime_herdr_core.rpp.cancel import CancelToken, Cancelled, Deadline
from gc_runtime_herdr_core.rpp.ops import OpError, OpRequest
from gc_runtime_herdr_core.rpp.perop import run_per_op
from gc_runtime_herdr_core.rpp.redact import Redactor
from gc_runtime_herdr_core.rpp.statedir import machine_identity

PACK_ROOT = Path(__file__).resolve().parents[2]
MACHINE = machine_identity()
"""The host's own identity: a detached helper the pack spawns (a kicked core
start) resolves the city with it too."""


class CoreEnvProcs(ProcSource):
    """The live process table, except that the in-process core's pid (this
    process) reads as having ``core_environ``."""

    def __init__(self, inner: ProcSource) -> None:
        self.inner = inner
        self.core_environ: Optional[Dict[str, str]] = None

    def snapshot(self) -> Dict[int, Proc]:
        return self.inner.snapshot()

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        if pid == os.getpid():
            return None if self.core_environ is None else dict(self.core_environ)
        return self.inner.environ(pid)


@dataclass
class Result:
    code: int
    stdout: bytes
    stderr: str

    @property
    def text(self) -> str:
        return self.stdout.decode("utf-8", "surrogateescape")


@dataclass
class City:
    root: Path
    home: Path
    env: Dict[str, str]
    paths: HcPaths
    host: Host
    procs: CoreEnvProcs
    fake: Optional[FakeHc] = None
    now_ms: List[int] = field(default_factory=list)

    def context(self, *, deadline_s: float = 30.0, extra: Optional[Mapping[str, str]] = None) -> OpContext:
        env = dict(self.env)
        env.update(extra or {})
        request = OpRequest(
            op="test",
            args=(),
            stdin=b"",
            env=env,
            cancel=CancelToken(),
            deadline=Deadline.after(deadline_s),
            redactor=Redactor(),
        )
        return OpContext(request, self.host)

    def start_core(self, **kwargs: object) -> FakeHc:
        """Serve the city's socket with an in-process fake-hc the pack accepts as its own."""
        ensure_dirs(self.paths)
        fake = FakeHc(self.paths.socket, **kwargs)  # type: ignore[arg-type]
        fake.start()
        self.fake = fake
        self.procs.core_environ = core_env(self.context(), self.env["GC_HC_TEST_BIN"])
        return fake

    def run(
        self,
        op: str,
        *args: str,
        stdin: bytes = b"",
        extra: Optional[Mapping[str, str]] = None,
        cancel: Optional[CancelToken] = None,
        deadline_ms: Optional[int] = None,
    ) -> Result:
        env = dict(self.env)
        env.update(extra or {})
        if deadline_ms is not None:
            env["GC_EXEC_DEADLINE_MS"] = str(deadline_ms)
        if cancel is not None:
            return self._run_with(op, args, stdin, env, cancel)
        out = io.BytesIO()
        err = io.StringIO()
        code = run_per_op(
            ["gc-runtime-herdr-core", op, *args],
            env,
            build_ops(self.host),
            started=time.monotonic(),
            stdin=io.BytesIO(stdin),
            stdout=out,
            stderr=err,
            install_signals=False,
        )
        return Result(code, out.getvalue(), err.getvalue())

    def _run_with(self, op: str, args: "tuple[str, ...]", stdin: bytes, env: Dict[str, str], cancel: CancelToken) -> Result:
        """Run ``op``'s handler with a cancel token the test controls."""
        spec = build_ops(self.host)[op]
        request = OpRequest(
            op=op, args=args, stdin=stdin, env=env, cancel=cancel, deadline=Deadline.after(120.0), redactor=Redactor()
        )
        try:
            result = spec.handler(request)
        except OpError as err:
            return Result(int(err.code), b"", err.message)
        except Cancelled as err:
            return Result(1, b"", str(err))
        return Result(int(result.code), result.stdout, result.message)

    def start(self, name: str, config: str = '{"command":"cat"}', **kwargs: object) -> Result:
        return self.run("start", name, stdin=config.encode(), **kwargs)  # type: ignore[arg-type]

    def terminals(self, *, all_records: bool = True) -> List[Dict[str, object]]:
        from fakehc.rawclient import raw_call

        reply = raw_call(self.paths.socket, "terminal.list", {"all": all_records})
        found: List[Dict[str, object]] = reply["result"]["terminals"]
        return found

    def address(self, name: str) -> str:
        for record in sorted(self.terminals(), key=lambda r: parse_address(str(r["address"])) or 0, reverse=True):
            labels = record["labels"]
            assert isinstance(labels, dict)
            if labels.get("gc.session") == name:
                return str(record["address"])
        raise AssertionError(f"no terminal for {name}")


def make_city(tmp: Path, home: Path, *, city_path: str = "/cities/test", procs: Optional[ProcSource] = None) -> City:
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    launcher = write_launcher(str(bindir / "herdr-core"))
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "GC_EXEC_STATE_DIR": str(tmp / "R"),
        "GC_EXEC_CITY_PATH": city_path,
        "GC_HC_TEST": "1",
        "GC_HC_TEST_BIN": launcher,
    }
    paths = resolve_paths(env, machine=MACHINE, home=lambda: str(home))
    wrapped = CoreEnvProcs(procs or LinuxProcs())
    host = Host(procs=wrapped, pack_dir=str(PACK_ROOT), python=sys.executable, machine=MACHINE, home=lambda: str(home))
    return City(root=tmp, home=home, env=env, paths=paths, host=host, procs=wrapped)


def in_thread(fn: "object") -> threading.Thread:
    thread = threading.Thread(target=fn, daemon=True)  # type: ignore[arg-type]
    thread.start()
    return thread
