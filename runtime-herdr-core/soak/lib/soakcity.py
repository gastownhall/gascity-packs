"""``soak city-init``: a scratch city on runtime herdr-core, and the small
TOML edits (``soak toml-set``, ``soak toml-del``) the runbook makes.

The TOML edits are line edits under an existing table header (or a new
table appended), so gc's own formatting and comments survive; the result is
parsed with ``tomllib`` afterwards where the interpreter has it (3.11+).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from soaklib import SoakPaths, append_jsonl, run, write_atomic

if sys.version_info >= (3, 11):  # the VM runs 3.12; the 3.9 floor skips the parse check
    import tomllib

    def _toml_loads(text: str) -> Optional[Dict[str, Any]]:
        return dict(tomllib.loads(text))

else:  # pragma: no cover - Python 3.9 and 3.10

    def _toml_loads(text: str) -> Optional[Dict[str, Any]]:
        return None


LOADS: Dict[str, Dict[str, int]] = {
    "bringup": {"burst_s": 180, "steady_s": 180, "nudge_s": 300},
    "soak": {"burst_s": 30, "steady_s": 60, "nudge_s": 120},
}
"""The load generator's periods (seconds) for ``--load``."""

NUDGE_MODES: Tuple[Tuple[str, int], ...] = (("wait-idle", 80), ("immediate", 10), ("queue", 10))

PHASE_RECONCILER = {
    "bringup": "legacy",
    "v2-switch": "v2",
    "drills": "v2",
    "soak-legacy": "legacy",
    "soak-v2": "v2",
    "soak-end": "v2",
}


class TomlEditError(Exception):
    pass


_HEADER = re.compile(r"^\s*\[\s*([^\[\]]+?)\s*\]\s*(#.*)?$")
_ARRAY_HEADER = re.compile(r"^\s*\[\[")


def _table_span(lines: Sequence[str], table: str) -> Optional[Tuple[int, int]]:
    """``(header index, end index)`` of ``[table]``: the body runs to the next header."""
    start: Optional[int] = None
    for i, line in enumerate(lines):
        m = _HEADER.match(line)
        is_header = m is not None or _ARRAY_HEADER.match(line) is not None
        if start is not None and is_header:
            return start, i
        if m is not None and m.group(1).replace(" ", "") == table:
            start = i
    return None if start is None else (start, len(lines))


def _key_line(lines: Sequence[str], span: Tuple[int, int], key: str) -> Optional[int]:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for i in range(span[0] + 1, span[1]):
        if pattern.match(lines[i]):
            return i
    return None


def toml_set(text: str, table: str, key: str, value: str) -> str:
    """Set ``key = value`` (``value`` a TOML literal) under ``[table]``,
    inserting the key or appending the table as needed."""
    lines = text.splitlines()
    span = _table_span(lines, table)
    entry = f"{key} = {value}"
    if span is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", f"[{table}]", entry]
    else:
        at = _key_line(lines, span, key)
        if at is not None:
            lines[at] = entry
        else:
            last = span[0]
            for i in range(span[0] + 1, span[1]):
                if lines[i].strip():
                    last = i
            lines.insert(last + 1, entry)
    return "\n".join(lines) + "\n"


def toml_del(text: str, table: str, key: str) -> str:
    lines = text.splitlines()
    span = _table_span(lines, table)
    at = None if span is None else _key_line(lines, span, key)
    if at is None:
        raise TomlEditError(f"no {key} under [{table}]")
    del lines[at]
    return "\n".join(lines) + "\n"


def toml_lookup(doc: Mapping[str, Any], table: str, key: str) -> Any:
    node: Any = doc
    for part in table.split(".") + [key]:
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"{table}.{key}")
        node = node[part]
    return node


def toml_check(text: str) -> Optional[Dict[str, Any]]:
    """The parsed document (None where tomllib is unavailable); TomlEditError if it does not parse."""
    try:
        return _toml_loads(text)
    except ValueError as err:
        raise TomlEditError(f"the edited file does not parse: {err}") from None


def edit_file(path: Path, table: str, key: str, value: Optional[str]) -> None:
    """Set (``value``) or delete (None) one key and check the file still parses."""
    text = path.read_text(encoding="utf-8")
    new = toml_del(text, table, key) if value is None else toml_set(text, table, key, value)
    doc = toml_check(new)
    if doc is not None:
        if value is None:
            try:
                toml_lookup(doc, table, key)
            except KeyError:
                pass
            else:
                raise TomlEditError(f"{table}.{key} is still set after the edit")
        else:
            got = toml_lookup(doc, table, key)
            want = toml_check(f"v = {value}\n")
            if want is not None and got != want["v"]:
                raise TomlEditError(f"{table}.{key} reads {got!r} after the edit, want {want['v']!r}")
    write_atomic(path, new, mode=0o644)


def toml_str(value: str) -> str:
    return json.dumps(value)


def city_keys(data: Path) -> List[Tuple[str, str, str]]:
    """``(table, key, TOML literal)`` the city's ``city.toml`` carries."""
    return [
        ("workspace", "provider", toml_str("soak")),
        ("session", "provider", toml_str("herdr-core")),
        ("daemon", "session_reconciler", toml_str("legacy")),
        ("daemon", "max_wakes_per_tick", "25"),
        ("beads", "proxied_idle_timeout", toml_str("0")),
        ("events.mirror", "path", toml_str(str(data / "gc-events" / "events.jsonl"))),
        ("events.mirror", "mode", toml_str("0600")),
        ("events.mirror", "max_size_bytes", "0"),
    ]


def render(template_dir: Path, name: str, values: Mapping[str, str]) -> str:
    """One ``city/<name>.in`` template with ``${...}`` placeholders filled."""
    return string.Template((template_dir / f"{name}.in").read_text(encoding="utf-8")).substitute(values)


@dataclass(frozen=True)
class CityFile:
    path: str
    template: str


CITY_FILES = (
    CityFile("agents/soak-steady/agent.toml", "steady.agent.toml"),
    CityFile("agents/soak-burst/agent.toml", "burst.agent.toml"),
    CityFile("assets/prompts/soak.template.md", "soak.template.md"),
    CityFile("formulas/soak-run.toml", "soak-run.toml"),
    CityFile("formulas/soak-pulse.toml", "soak-pulse.toml"),
)


def nudge_mode_table() -> List[List[Any]]:
    return [[mode, weight] for mode, weight in NUDGE_MODES]


def load_config(kind: str, seed: int) -> Dict[str, Any]:
    if kind not in LOADS:
        raise ValueError(f"--load must be one of {sorted(LOADS)}")
    return dict(LOADS[kind], load=kind, seed=seed, nudge_modes=nudge_mode_table())


def set_phase(data: Path, phase: str, reconciler: Optional[str] = None) -> Dict[str, Any]:
    rec: Dict[str, Any] = {"t": time.time(), "phase": phase, "reconciler": reconciler or PHASE_RECONCILER.get(phase, "")}
    write_atomic(data / "phase", phase + "\n")
    append_jsonl(data / "phases.jsonl", rec)
    return rec


def point_current(paths: SoakPaths, data: Path) -> None:
    tmp = paths.data_root / f".current.{os.getpid()}"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(str(data), str(tmp))
    os.replace(str(tmp), str(paths.current))


class InitFailed(Exception):
    pass


def city_init(
    paths: SoakPaths,
    name: str,
    steady: int,
    burst: int,
    mode: str,
    load: str,
    env: Mapping[str, str],
    say: Any = print,
    gc_bin: str = "gc",
) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise InitFailed(f"not a city name: {name!r}")
    if mode not in ("warn", "abort"):
        raise InitFailed("--mode must be warn or abort")
    city = paths.cities / name
    data = paths.data_root / name
    if city.exists():
        raise InitFailed(f"{city} exists: a soak city is always fresh")
    # 1. data directories, canary, soak.env, load.json, phase, current
    for sub in ("", "agents", "cmd", "gc-events", "drills", "captures"):
        (data / sub).mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(data / sub, 0o700)
    canary = "soakcanary" + secrets.token_hex(16)
    write_atomic(data / "canary", canary + "\n", mode=0o600)
    write_atomic(data / "soak.env", f"SOAK_CITY={city}\nSOAK_DATA={data}\nSOAK_MODE={mode}\n", mode=0o600)
    write_atomic(data / "load.json", json.dumps(load_config(load, secrets.randbits(32)), indent=2) + "\n")
    set_phase(data, "bringup")
    point_current(paths, data)
    say(f"data: {data}")
    # 2. gc init, born split
    paths.cities.mkdir(mode=0o700, parents=True, exist_ok=True)
    init_env = dict(env, GC_BEADS_PROXIED_IDLE_TIMEOUT="0")
    res = run(
        [gc_bin, "init", "--template", "empty", "--skip-provider-readiness", "--no-start", str(city)],
        env=init_env,
        timeout=600.0,
    )
    (data / "gc-init.log").write_text(res.out + res.err, encoding="utf-8")
    if not res.ok:
        raise InitFailed(f"gc init exited {res.code}: {res.tail(400)}")
    if "single-store" in (res.out + res.err) or "single store" in (res.out + res.err):
        raise InitFailed("gc init says the city starts single-store: the bd on PATH is wrong")
    city_toml = city / "city.toml"
    doc = toml_check(city_toml.read_text(encoding="utf-8"))
    if doc is not None:
        try:
            infra = toml_lookup(doc, "storage.bindings.infra", "provider")
        except KeyError:
            infra = None
        if infra != "sqlite-beads":
            raise InitFailed(f"city.toml has no [storage.bindings.infra] provider = \"sqlite-beads\" (found {infra!r})")
    say(f"city: {city} (born split)")
    # 3. city.toml keys
    for table, key, value in city_keys(data):
        edit_file(city_toml, table, key, value)
    # 4. pack.toml
    templates = paths.harness / "city"
    values = {
        "DATA": str(data),
        "CANARY": canary,
        "STEADY": str(steady),
        "BURST": str(burst),
        "PACK": str(paths.pack),
        "AGENT": str(paths.harness / "bin" / "soak-agent"),
    }
    pack_toml = city / "pack.toml"
    with open(pack_toml, "a", encoding="utf-8") as handle:
        handle.write("\n" + render(templates, "pack.append.toml", values))
    try:
        toml_check(pack_toml.read_text(encoding="utf-8"))
    except TomlEditError as err:
        raise InitFailed(f"pack.toml: {err}") from None
    # 5. the city's own pack files
    for item in CITY_FILES:
        target = city / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(templates, item.template, values), encoding="utf-8")
    # 6. validate, install the pinned hc, doctor before start
    for argv, timeout in (
        ([gc_bin, "config", "show", "--validate"], 120.0),
        ([gc_bin, "herdr-core", "install"], 600.0),
        ([gc_bin, "herdr-core", "status"], 120.0),
    ):
        res = run(argv, cwd=str(city), env=env, timeout=timeout)
        say(f"$ {' '.join(argv[1:])}  (exit {res.code})\n{res.out.rstrip()}")
        if not res.ok:
            raise InitFailed(f"{' '.join(argv[1:])} exited {res.code}: {res.tail(400)}")
    res = run([gc_bin, "doctor", "--json"], cwd=str(city), env=env, timeout=600.0)
    (data / "doctor-prestart.json").write_text(res.out, encoding="utf-8")
    say(f"doctor (before start) exit {res.code}: {data / 'doctor-prestart.json'}")
    return city
