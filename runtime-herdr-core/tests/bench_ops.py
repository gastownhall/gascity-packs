#!/usr/bin/env python3
"""Per-op CPU of the runtime's executable, against fake-hc on a scratch root.

    tests/bench_ops.py [--runs N] [--sessions N] [--ops a,b,...] [--python PY]
                       [--fakehc-python PY] [--compare ENTRY2] [--json]

Each op runs ``--runs`` times as a fresh process, the way gc runs it: a
direct exec of ``assets/bin/gc-runtime-herdr-core`` (its shebang picks the
interpreter), or ``PY -I -S <entry>`` with ``--python``. Stdin carries what
gc sends: the process names for ``observe`` and ``process-alive``, the value
for ``set-meta``, the text for ``nudge``; every other op gets an empty stdin.
CPU is the op process's user+sys time, the ``RUSAGE_CHILDREN`` delta around
each run; wall is the run's elapsed time. One unmeasured run of every op
comes first, so each entry's bytecode cache is written before it is timed.

``--compare ENTRY2`` interleaves runs of a second entry (for example the
runtime at an older commit, extracted with ``git archive <commit>
runtime-herdr-core | tar -x -C <dir>``) and reports before (ENTRY2), after
(this pack) and the change.

All state lives in a fresh 0700 scratch directory under ``/tmp``: a scratch
``GC_EXEC_STATE_DIR``, fake-hc as the hc binary (``GC_HC_TEST=1``), spawn
files under the scratch root. It never uses the default state root or a
real hc. ``--sessions`` sessions (running ``cat``) start through the pack's
own ``start``, so the core starts as it does under gc. Teardown always runs:
it stops the sessions, stops every fake-hc core under the scratch root with
the discovery environment its ``core.lock`` names, fails if fake-hc logged a
schema violation, and removes the scratch root. It kills no process.

fake-hc runs under ``--fakehc-python`` (default: this interpreter), which
needs ``jsonschema`` and ``referencing`` (and ``tomli`` below Python 3.11).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import resource
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import FrameType
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

PACK_ROOT = Path(__file__).resolve().parents[1]
ENTRY = PACK_ROOT / "assets" / "bin" / "gc-runtime-herdr-core"
sys.path.insert(0, str(PACK_ROOT / "tests"))

from fakehc.cli import write_launcher  # noqa: E402

OP_TIMEOUT_S = 120.0
NAME_PREFIX = "bench-"
PAIR_NAME = "bench-pair"
META_KEY = "bench.key"
AGENT_NAMES = b"cat\n"
SESSION_CONFIG = b'{"command":"cat"}'


class Case(NamedTuple):
    """One op as the bench runs it."""

    label: str
    op: str
    args: Tuple[str, ...]
    stdin: Optional[bytes]


def cases(session: str) -> List[Case]:
    """Every measured op but the start/stop pair, against ``session``."""
    return [
        Case("protocol", "protocol", (), None),
        Case("get-meta", "get-meta", (session, META_KEY), None),
        Case("set-meta", "set-meta", (session, META_KEY), b"value"),
        Case("remove-meta", "remove-meta", (session, "bench.other"), None),
        Case("is-running", "is-running", (session,), None),
        Case("observe", "observe", (session,), b""),
        Case("observe+names", "observe", (session,), AGENT_NAMES),
        Case("get-last-activity", "get-last-activity", (session,), None),
        Case("is-attached", "is-attached", (session,), None),
        Case("peek", "peek", (session, "20"), None),
        Case("list-running", "list-running", (), None),
        Case("inventory", "inventory", (), None),
        Case("process-alive", "process-alive", (session,), AGENT_NAMES),
        Case("nudge", "nudge", (session,), b"bench"),
    ]


PAIR_LABELS = ("start", "stop")
ALL_LABELS = tuple(c.label for c in cases("x")) + PAIR_LABELS


class Sample(NamedTuple):
    cpu_s: float
    wall_s: float


class BenchError(Exception):
    """An op failed or the scratch city could not be set up or torn down."""


def host_processes() -> Optional[int]:
    """The host's process count (Linux), or None."""
    try:
        return sum(1 for entry in os.listdir("/proc") if entry.isdigit())
    except OSError:
        return None


class Bench:
    """A scratch city, the entries under test, and their samples."""

    def __init__(self, python: Optional[str], fakehc_python: str) -> None:
        self.python = python
        self.scratch = Path(os.path.realpath(tempfile.mkdtemp(prefix="hcbench-", dir="/tmp")))
        os.chmod(self.scratch, 0o700)
        self.root = self.scratch / "state"
        bindir = self.scratch / "bin"
        bindir.mkdir()
        (self.scratch / "city").mkdir()
        self.launcher = write_launcher(str(bindir / "herdr-core"), python=fakehc_python)
        env = dict(os.environ)
        for key in ("GC_RPP_FAULT", "GC_EXEC_DEADLINE_MS", "GC_EXEC_CITY_NAME", "GC_HERDR_CORE_DEBUG"):
            env.pop(key, None)
        env.update(
            {
                "GC_EXEC_STATE_DIR": str(self.root),
                "GC_EXEC_CITY_PATH": str(self.scratch / "city"),
                "GC_HC_TEST": "1",
                "GC_HC_TEST_BIN": self.launcher,
                "GC_HC_TEST_SPAWN_ROOT": str(self.scratch / "spawn"),
            }
        )
        self.env = env
        self.sessions: List[str] = []

    def argv(self, entry: Path, op: str, args: Sequence[str]) -> List[str]:
        head = [str(entry)] if self.python is None else [self.python, "-I", "-S", str(entry)]
        return head + [op, *args]

    def run(self, entry: Path, op: str, args: Sequence[str], stdin: Optional[bytes]) -> Tuple[Sample, bytes]:
        """Run one op as a fresh process; fail unless it exits 0."""
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.monotonic()
        done = subprocess.run(
            self.argv(entry, op, args),
            env=self.env,
            input=stdin,
            stdin=subprocess.DEVNULL if stdin is None else None,
            capture_output=True,
            timeout=OP_TIMEOUT_S,
            check=False,
        )
        wall = time.monotonic() - started
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        if done.returncode != 0:
            stderr = done.stderr.decode("utf-8", "replace").strip()
            raise BenchError(f"{entry}: {op} {' '.join(args)} exited {done.returncode}: {stderr}")
        return Sample(cpu, wall), done.stdout

    def start_sessions(self, count: int) -> None:
        for index in range(1, count + 1):
            name = f"{NAME_PREFIX}{index}"
            self.sessions.append(name)  # stopped in teardown even if its start fails
            self.run(ENTRY, "start", (name,), SESSION_CONFIG)

    def python_version(self, entry: Path) -> str:
        _, out = self.run(entry, "x-version", (), None)
        python: str = json.loads(out)["python"]
        return python

    def teardown(self) -> List[str]:
        """Stop sessions and cores, check fake-hc's schema logs, remove the
        scratch root. Returns the problems found."""
        problems: List[str] = []
        for name in self.sessions + [PAIR_NAME]:
            try:
                self.run(ENTRY, "stop", (name,), None)
            except (BenchError, OSError, subprocess.TimeoutExpired) as err:
                problems.append(f"stop {name}: {err}")
        for lock in sorted(self.root.glob("herdr-core/*/core.lock")):
            state = lock.parent
            env = dict(os.environ)
            env.update({"HC_SESSION": state.name, "HC_SOCKET": lock.read_text().strip(), "XDG_STATE_HOME": str(self.root)})
            try:
                subprocess.run(
                    [self.launcher, "server", "stop"],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    timeout=OP_TIMEOUT_S,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as err:
                problems.append(f"server stop {state.name}: {err}")
            violations = state / "schema-violations.log"
            if violations.exists() and violations.stat().st_size:
                problems.append(f"fake-hc schema violations ({state.name}):\n{violations.read_text()}")
        shutil.rmtree(self.scratch, ignore_errors=True)
        return problems

    def sockets(self) -> List[str]:
        return [lock.read_text().strip() for lock in sorted(self.root.glob("herdr-core/*/core.lock"))]


def p90(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]


def summary(samples: Sequence[Sample]) -> Dict[str, float]:
    return {
        "runs": len(samples),
        "cpu_ms_median": round(statistics.median(s.cpu_s for s in samples) * 1000, 1),
        "cpu_ms_p90": round(p90([s.cpu_s for s in samples]) * 1000, 1),
        "wall_ms_median": round(statistics.median(s.wall_s for s in samples) * 1000, 1),
    }


def measure(bench: Bench, entries: Sequence[Path], labels: Sequence[str], runs: int) -> Dict[str, List[List[Sample]]]:
    """Samples per label, one list per entry; entries alternate run by run."""
    session = bench.sessions[0]
    found: Dict[str, List[List[Sample]]] = {}
    for case in cases(session):
        if case.label not in labels:
            continue
        per_entry: List[List[Sample]] = [[] for _ in entries]
        for entry in entries:
            bench.run(entry, case.op, case.args, case.stdin)  # warm the bytecode cache
        for index in range(runs):
            order = list(enumerate(entries)) if index % 2 == 0 else list(reversed(list(enumerate(entries))))
            for slot, entry in order:
                sample, _ = bench.run(entry, case.op, case.args, case.stdin)
                per_entry[slot].append(sample)
        found[case.label] = per_entry
    if any(label in labels for label in PAIR_LABELS):
        starts: List[List[Sample]] = [[] for _ in entries]
        stops: List[List[Sample]] = [[] for _ in entries]
        for index in range(runs + 1):
            order = list(enumerate(entries)) if index % 2 == 0 else list(reversed(list(enumerate(entries))))
            for slot, entry in order:
                started, _ = bench.run(entry, "start", (PAIR_NAME,), SESSION_CONFIG)
                stopped, _ = bench.run(entry, "stop", (PAIR_NAME,), None)
                if index:  # the first pair only warms the caches
                    starts[slot].append(started)
                    stops[slot].append(stopped)
        if "start" in labels:
            found["start"] = starts
        if "stop" in labels:
            found["stop"] = stops
    return found


def table(found: Dict[str, List[List[Sample]]], compare: bool) -> str:
    if not compare:
        lines = ["| op | runs | CPU median ms | CPU p90 ms | wall median ms |", "|---|---:|---:|---:|---:|"]
        for label, per_entry in found.items():
            s = summary(per_entry[0])
            lines.append(f"| {label} | {s['runs']} | {s['cpu_ms_median']} | {s['cpu_ms_p90']} | {s['wall_ms_median']} |")
        return "\n".join(lines)
    lines = [
        "| op | runs | CPU median ms before | after | change | CPU p90 ms before | after | wall median ms before | after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, per_entry in found.items():
        after, before = summary(per_entry[0]), summary(per_entry[1])
        change = (after["cpu_ms_median"] - before["cpu_ms_median"]) / before["cpu_ms_median"] * 100
        lines.append(
            f"| {label} | {after['runs']} | {before['cpu_ms_median']} | {after['cpu_ms_median']} | {change:+.0f}% "
            f"| {before['cpu_ms_p90']} | {after['cpu_ms_p90']} | {before['wall_ms_median']} | {after['wall_ms_median']} |"
        )
    return "\n".join(lines)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--runs", type=int, default=30, help="measured runs per op (default 30)")
    parser.add_argument("--sessions", type=int, default=3, help="sessions to start (default 3)")
    parser.add_argument("--ops", default="", help="comma-separated subset of: " + ",".join(ALL_LABELS))
    parser.add_argument("--python", default=None, help="run the entry as PY -I -S <entry> instead of executing it")
    parser.add_argument("--fakehc-python", default=sys.executable, help="interpreter fake-hc runs under")
    parser.add_argument("--compare", default=None, metavar="ENTRY2", help="a second entry to interleave (the before)")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args(argv)
    if args.runs < 1 or args.sessions < 1:
        parser.error("--runs and --sessions must be at least 1")
    return args


def _terminate(signum: int, frame: Optional[FrameType]) -> None:
    raise SystemExit(128 + signum)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    labels = [label for label in str(args.ops).split(",") if label] or list(ALL_LABELS)
    unknown = sorted(set(labels) - set(ALL_LABELS))
    if unknown:
        print(f"bench_ops: unknown ops: {', '.join(unknown)}", file=sys.stderr)
        return 2
    entries = [ENTRY]
    if args.compare is not None:
        other = Path(str(args.compare)).resolve()
        if not other.is_file():
            print(f"bench_ops: no entry at {other}", file=sys.stderr)
            return 2
        entries.append(other)
    signal.signal(signal.SIGTERM, _terminate)
    bench = Bench(args.python, str(args.fakehc_python))
    problems: List[str] = []
    try:
        procs_start = host_processes()
        python = bench.python_version(ENTRY)
        bench.start_sessions(int(args.sessions))
        sockets = bench.sockets()
        found = measure(bench, entries, labels, int(args.runs))
        procs_end = host_processes()
    except BenchError as err:
        problems.append(str(err))
    finally:
        problems.extend(bench.teardown())
    if problems:
        print("bench_ops: " + "\n".join(problems), file=sys.stderr)
        return 1
    if args.json:
        report = {
            "python": python,
            "host_processes": {"start": procs_start, "end": procs_end},
            "scratch": str(bench.scratch),
            "sockets": sockets,
            "entries": [str(e) for e in entries],
            "results": {label: [summary(samples) for samples in per_entry] for label, per_entry in found.items()},
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"Python {python}; host processes {procs_start} at start, {procs_end} at end")
        if args.compare is not None:
            print(f"before: {entries[1]}\nafter:  {entries[0]}")
        print(table(found, args.compare is not None))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
