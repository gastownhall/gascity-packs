"""Each op loads only its own code.

gc runs every op as a fresh process, so every module an op imports is paid
for on every call. These tests run the executable as gc does (``-I -S``, a
fresh interpreter) against the in-process fake-hc core and fail when an op
pulls in a module it does not need: the cold standard library modules, and
the runtime modules of other ops. ``start`` and ``stop`` are not run here
(from a subprocess, ``start`` refuses the in-process core as foreign); the
static checks in ``test_herdr_core_pack.py`` cover what every op imports.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, FrozenSet, List, NamedTuple, Optional

import pytest

from cityharness import City
from gc_runtime_herdr_core.herdrcore.context import Host
from gc_runtime_herdr_core.herdrcore.ops_table import OP_SPECS, build_ops

PACK_ROOT = Path(__file__).resolve().parents[2]
ENTRY = PACK_ROOT / "assets" / "bin" / "gc-runtime-herdr-core"
PACKAGE = "gc_runtime_herdr_core"

WRAPPER = """
import json, os, sys
entry = sys.argv[1]
sys.argv = sys.argv[1:]
with open(entry, encoding="utf-8") as source:
    code = compile(source.read(), entry, "exec")
status = 0
try:
    exec(code, {"__name__": "__main__", "__file__": entry})
except SystemExit as stop:
    status = stop.code
finally:
    with open(os.environ["HC_TEST_MODULES_OUT"], "w", encoding="utf-8") as out:
        json.dump(sorted(sys.modules), out)
sys.exit(status)
"""
"""Runs the entry as ``__main__`` and records every module it loaded."""

HEAVY_STDLIB: FrozenSet[str] = frozenset(
    {
        "subprocess",
        "tempfile",
        "shutil",
        "calendar",
        "traceback",
        "uuid",
        "platform",
        "tarfile",
        "ssl",
        "urllib.request",
        "http.client",
        "dataclasses",
        "annotationlib",
        "inspect",
        "ast",
        "dis",
        "tokenize",
    }
)
"""Standard library modules no hot op needs: process spawning, archives,
the network stack, modules that only cold paths use, and dataclasses with
what it and, on CPython 3.14, typing.NamedTuple import (records use
:mod:`gc_runtime_herdr_core.rpp.frozen`)."""

NEVER: FrozenSet[str] = frozenset(
    {
        "lifecycle",
        "core",
        "coreid",
        "corescan",
        "command",
        "server",
        "screen",
        "staging",
        "readiness",
        "install",
        "admin",
        "doctor",
        "commands",
        "envplan",
        "shim",
        "appvis",
        "launch",
        "unwelded",
        "provisioned",
    }
)
"""Runtime modules (``herdrcore.*``) the read and driving ops never load on
their happy path: start, stop, the core's own start, admin and doctor."""

OPTIONAL: FrozenSet[str] = frozenset({"inputs", "outcome", "attach", "activity"})
"""Runtime modules (``herdrcore.*``) loaded only by the ops that use them."""


class Case(NamedTuple):
    op: str
    args: List[str]
    stdin: bytes
    check: Callable[[str], bool]
    allowed: FrozenSet[str] = frozenset()


def _json_state(state: str, agent: Optional[str] = None) -> Callable[[str], bool]:
    def check(text: str) -> bool:
        answer = json.loads(text)
        return bool(answer["state"] == state and (agent is None or answer.get("agent") == agent))

    return check


def _inventory(text: str) -> bool:
    answer = json.loads(text)
    return bool(answer["complete"] is True and sorted(s["name"] for s in answer["sessions"]) == ["s1", "s2"])


def _rfc3339(text: str) -> bool:
    return text.endswith("Z\n") and text[4] == "-" and "T" in text


CASES: Dict[str, Case] = {
    "protocol": Case("protocol", [], b"", lambda t: json.loads(t)["version"] == 0),
    "get-meta": Case("get-meta", ["s1", "bench.key"], b"", lambda t: t == "preset"),
    "set-meta": Case("set-meta", ["s1", "other.key"], b"v", lambda t: t == ""),
    "remove-meta": Case("remove-meta", ["s1", "bench.key"], b"", lambda t: t == ""),
    "is-running": Case("is-running", ["s1"], b"", lambda t: t == "true\n"),
    "observe": Case("observe", ["s1"], b"", _json_state("running")),
    "observe+names": Case("observe", ["s1"], b"cat\n", _json_state("running", "alive")),
    "inventory": Case("inventory", [], b"", _inventory, frozenset({"attach", "activity"})),
    "list-running": Case("list-running", [], b"", lambda t: t == "s1\ns2\n"),
    "get-last-activity": Case("get-last-activity", ["s1"], b"", _rfc3339, frozenset({"activity"})),
    "is-attached": Case("is-attached", ["s1"], b"", lambda t: t == "false\n", frozenset({"attach"})),
    "peek": Case("peek", ["s1", "5"], b"", lambda t: t.endswith("\n")),
    "process-alive": Case("process-alive", ["s1"], b"cat\n", lambda t: t == "true\n"),
    "nudge": Case("nudge", ["s1"], b"hello", lambda t: t == "", frozenset({"inputs", "outcome", "activity"})),
}


def _loaded(city: City, tmp_path: Path, case: Case) -> List[str]:
    out = tmp_path / "modules.json"
    env = dict(city.env)
    env["HC_TEST_MODULES_OUT"] = str(out)
    done = subprocess.run(
        [sys.executable, "-I", "-S", "-c", WRAPPER, str(ENTRY), case.op, *case.args],
        env=env,
        input=case.stdin,
        capture_output=True,
        timeout=60,
        check=False,
    )
    stderr = done.stderr.decode("utf-8", "replace")
    assert done.returncode == 0, stderr
    text = done.stdout.decode("utf-8", "surrogateescape")
    assert case.check(text), f"{case.op} answered {text!r}; stderr {stderr!r}"
    modules: List[str] = json.loads(out.read_text(encoding="utf-8"))
    return modules


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="the scan ops read /proc on Linux; elsewhere they run ps, through subprocess",
)
@pytest.mark.parametrize("label", sorted(CASES))
def test_op_loads_only_its_own_code(city: City, tmp_path: Path, label: str) -> None:
    case = CASES[label]
    assert city.start("s1").code == 0
    assert city.start("s2").code == 0
    assert city.run("set-meta", "s1", "bench.key", stdin=b"preset").code == 0
    modules = _loaded(city, tmp_path, case)
    heavy = sorted(HEAVY_STDLIB.intersection(modules))
    assert heavy == [], f"{label} loads {heavy}"
    runtime = {m[len(PACKAGE) + len(".herdrcore.") :] for m in modules if m.startswith(f"{PACKAGE}.herdrcore.")}
    unwanted = sorted((runtime & NEVER) | ((runtime & OPTIONAL) - case.allowed))
    assert unwanted == [], f"{label} loads herdrcore modules {unwanted}"
    if label == "protocol":
        backend = [m for m in modules if m.startswith((f"{PACKAGE}.herdrcore", f"{PACKAGE}.hc"))]
        assert backend == [], f"protocol loads {backend}"


def test_every_op_in_the_table_resolves() -> None:
    # The table names each handler, and each no-city answer, by module and
    # function; a typo would otherwise fail only when gc runs that op.
    for op, spec in OP_SPECS.items():
        module = importlib.import_module(f"{PACKAGE}.herdrcore.{spec.module}")
        assert callable(getattr(module, spec.function)), op
        if spec.no_city:
            assert callable(getattr(module, spec.no_city)), op


def test_the_table_builds_every_op(city: City) -> None:
    host: Host = city.host
    table = build_ops(host)
    assert set(OP_SPECS) | {"protocol"} == set(table)
