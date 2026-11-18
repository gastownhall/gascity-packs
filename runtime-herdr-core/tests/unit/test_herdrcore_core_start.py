"""When the pack starts a city's core, and when it must not.

A core is started by a session ``start``, by a read's kick for a city that
has started and is not at rest, by ``server-stop`` removing the records hc
keeps, and by ``restart-core`` and ``upgrade``. Never by a read of a city no
core has ever run for (``gc doctor`` before ``gc start``): with nothing of
it running, that city reads empty, which is the truth, since hc keeps every
record, live or finished, under the session's state directory and creates
it before any core or holder of the session runs. Never for an op that
names no city. fake-hc only.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

import pytest
from cityharness import City, make_city
from conftest import teardown_cores
from test_herdrcore_server import no_core_started, spawned, start_config, start_holder

from gc_runtime_herdr_core.herdrcore import core
from gc_runtime_herdr_core.herdrcore.context import OpContext
from gc_runtime_herdr_core.herdrcore.ops_table import build_ops

__all__ = ["spawned"]  # the fixture, imported for the tests below

OPS: Dict[str, Tuple[Tuple[str, ...], bytes]] = {
    "start": (("mc-a",), start_config("exec cat").encode()),
    "stop": (("mc-a",), b""),
    "kill-object": ((), b'{"session":"mc-a","box":"t1"}'),
    "observe": (("mc-a",), b"cat\n"),
    "inventory": ((), b""),
    "is-running": (("mc-a",), b""),
    "process-alive": (("mc-a",), b"cat\n"),
    "list-running": ((), b""),
    "is-attached": (("mc-a",), b""),
    "get-last-activity": (("mc-a",), b""),
    "peek": (("mc-a", "10"), b""),
    "get-meta": (("mc-a", "k"), b""),
    "set-meta": (("mc-a", "k"), b"v"),
    "remove-meta": (("mc-a", "k"), b""),
    "nudge": (("mc-a",), b"hello"),
    "send-keys": (("mc-a", "Enter"), b""),
    "interrupt": (("mc-a",), b""),
    "clear-scrollback": (("mc-a",), b""),
    "watch-startup": (("mc-a",), b""),
    "attach": (("mc-a",), b""),
    "copy-to": (("mc-a", "/etc/hostname"), b""),
    "server-stop": ((), b""),
    core.KICK_OP: ((), b""),
}
"""Every op but ``protocol``, with arguments and stdin it accepts."""


@pytest.fixture
def fresh(short_tmp: Path, home_dir: Path) -> Iterator[City]:
    """A city no core has ever run for: no hc state directory."""
    made = make_city(short_tmp, home_dir)
    try:
        yield made
    finally:
        teardown_cores(made.root / "R")
        if made.fake is not None:
            made.fake.close()


def no_trace_of_a_core(city: City) -> None:
    assert no_core_started(city, wait_s=2.0), "no op started a core"
    assert not os.path.exists(city.paths.state_dir), "nothing created the core's state"
    assert not os.path.exists(os.path.join(city.context().pack_state, core.KICK_FILE)), "no kick ran"


def test_every_op_is_covered(fresh: City) -> None:
    assert set(OPS) == set(build_ops(fresh.host)) - {"protocol"}


# --- a city no core has ever run for ------------------------------------------------------


def test_reads_of_a_never_started_city_answer_an_empty_city_and_start_no_core(fresh: City) -> None:
    inventory = fresh.run("inventory")
    assert (inventory.code, json.loads(inventory.stdout)) == (0, {"complete": True, "sessions": []}), inventory.stderr
    observed = fresh.run("observe", "mc-a", stdin=b"cat\n")
    assert (observed.code, json.loads(observed.stdout)) == (0, {"state": "absent"}), observed.stderr
    for op, stdin in (("is-running", b""), ("process-alive", b"cat\n"), ("is-attached", b"")):
        done = fresh.run(op, "mc-a", stdin=stdin)
        assert (done.code, done.text.strip()) == (0, "false"), (op, done.stderr)
    listed = fresh.run("list-running")
    assert (listed.code, listed.text) == (0, ""), listed.stderr
    assert fresh.run("peek", "mc-a").code == 66
    for op, args in (("get-meta", ("mc-a", "k")), ("get-last-activity", ("mc-a",))):
        done = fresh.run(op, *args)
        assert (done.code, done.text) == (0, ""), (op, done.stderr)
    no_trace_of_a_core(fresh)


def test_gc_doctors_reads_of_a_never_started_city_start_no_core(fresh: City) -> None:
    """``gc doctor`` before ``gc start``: liveness probes, then the
    orphan-sessions check's inventory."""
    for _ in range(3):
        assert fresh.run("is-running", "mc-a").text.strip() == "false"
    for _ in range(2):
        inventory = fresh.run("inventory")
        assert json.loads(inventory.stdout) == {"complete": True, "sessions": []}, inventory.stderr
    no_trace_of_a_core(fresh)


def test_the_first_start_of_a_never_started_city_starts_its_core(fresh: City) -> None:
    done = fresh.start("mc-a", start_config("exec cat"))
    assert done.code == 0, done.stderr
    assert fresh.run("is-running", "mc-a").text.strip() == "true"


def test_a_never_started_city_with_a_holder_running_cannot_tell_and_is_kicked(fresh: City, spawned: List[int]) -> None:
    """Something of the session runs, so its state is not known to be
    empty: reads answer unknown, and the core is kicked back to adopt it."""
    start_holder(fresh, [{"argv": ["sleep", "600"]}], spawned)
    assert json.loads(fresh.run("inventory").stdout) == {"complete": False, "sessions": []}
    assert json.loads(fresh.run("observe", "mc-a", stdin=b"cat\n").stdout) == {"state": "unknown"}
    assert not no_core_started(fresh, wait_s=20.0), "the core is kicked"


def test_a_city_whose_core_ran_is_still_kicked(fresh: City) -> None:
    """A core that ended without server-stop (a crash, a reboot) may have
    left records hc answers for: reads stay unknown and kick it back."""
    fresh.start_core()
    assert fresh.fake is not None
    fresh.fake.close()
    fresh.fake = None
    assert os.path.isdir(fresh.paths.state_dir)
    assert json.loads(fresh.run("inventory").stdout) == {"complete": False, "sessions": []}
    assert not no_core_started(fresh, wait_s=20.0), "the core is kicked"


def test_a_state_directory_that_cannot_be_examined_is_not_taken_for_never_started(fresh: City) -> None:
    if os.getuid() == 0:
        pytest.skip("root examines any directory")
    parent = Path(fresh.paths.state_dir).parent
    parent.mkdir(parents=True)
    ctx: OpContext = fresh.context()
    assert core.never_started(ctx)
    parent.chmod(0)
    try:
        assert not core.never_started(ctx), "an lstat that fails but for ENOENT cannot tell"
        assert not core.at_rest(ctx)
    finally:
        parent.chmod(stat.S_IRWXU)
