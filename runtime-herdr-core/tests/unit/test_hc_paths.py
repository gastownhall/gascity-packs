"""Deterministic hc discovery.

Every gc process of a city (supervisor, CLI, cron, ssh, sudo) must find the
same core, so nothing here may depend on the caller's XDG_*, HOME, TMPDIR,
HC_SOCKET or HC_SESSION, and an unset GC_EXEC_CITY_PATH is the fixed
`unscoped` bucket, never the cwd.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from gc_runtime_herdr_core.hc import paths as paths_module
from gc_runtime_herdr_core.hc.paths import (
    HOLDER_SOCKET_SUFFIX_LEN,
    SUN_PATH_MAX,
    HcPaths,
    ensure_dirs,
    resolve_paths,
    session_name,
)
from gc_runtime_herdr_core.rpp.statedir import StateDirError, city_id


CALLER_NOISE = {
    "XDG_RUNTIME_DIR": "/run/user/4242",
    "XDG_STATE_HOME": "/caller/state",
    "XDG_CONFIG_HOME": "/caller/config",
    "XDG_DATA_HOME": "/caller/data",
    "HOME": "/caller/home",
    "TMPDIR": "/caller/tmp",
    "HC_SOCKET": "/caller/hc.sock",
    "HC_SESSION": "default",
}


def resolve(env: Dict[str, str], home: Path, *, machine: str = "machine-a", tmp_root: str = "/tmp") -> HcPaths:
    return resolve_paths(env, machine=machine, home=lambda: str(home), uid=os.getuid(), tmp_root=tmp_root)


def test_layout_under_the_state_root(home_dir: Path, short_tmp: Path) -> None:
    root = short_tmp / "R"
    paths = resolve({"GC_EXEC_CITY_PATH": "/srv/city", "GC_EXEC_STATE_DIR": str(root)}, home_dir)
    cid = city_id("machine-a", "/srv/city")
    session = session_name(cid, str(root))
    assert re.fullmatch(r"gc-[0-9a-f]{10}", session)
    assert paths.city_key == "/srv/city"
    assert paths.city_id == cid
    assert paths.session == session
    assert paths.state_root == str(root)
    assert paths.state_dir == str(root / "herdr-core" / session)
    assert paths.socket == str(root / "herdr-core" / session / f"{session}.sock")
    assert paths.core_lock == str(root / "herdr-core" / session / "core.lock")
    assert paths.config_home == str(root / "hc-config")
    assert paths.config_file == str(root / "hc-config" / "herdr-core" / "config.toml")


def test_discovery_tuple_is_what_the_core_and_its_clients_share(home_dir: Path, short_tmp: Path) -> None:
    paths = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": str(short_tmp / "R")}, home_dir)
    assert paths.discovery_env() == {
        "HC_SESSION": paths.session,
        "HC_SOCKET": paths.socket,
        "XDG_STATE_HOME": paths.state_root,
        "XDG_CONFIG_HOME": paths.config_home,
    }


@pytest.mark.parametrize("with_state_dir", [True, False])
def test_discovery_ignores_the_callers_environment(home_dir: Path, short_tmp: Path, with_state_dir: bool) -> None:
    env = {"GC_EXEC_CITY_PATH": "/srv/city"}
    if with_state_dir:
        env["GC_EXEC_STATE_DIR"] = str(short_tmp / "R")
    noisy = dict(env, **CALLER_NOISE)
    assert resolve(noisy, home_dir) == resolve(env, home_dir)
    if not with_state_dir:
        assert resolve(env, home_dir).state_root == str(home_dir / ".local" / "state" / "gc-runtime-herdr-core")


def test_unset_city_path_is_unscoped_never_the_cwd(
    home_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    city = tmp_path / "city"
    city.mkdir()
    monkeypatch.chdir(city)
    paths = resolve({}, home_dir)
    assert paths.city_key == "unscoped"
    assert paths.city_id == city_id("machine-a", "unscoped")
    assert paths.session != resolve({"GC_EXEC_CITY_PATH": str(city)}, home_dir).session


def test_the_machine_is_in_the_key(home_dir: Path) -> None:
    # Two machines sharing an NFS home keep apart: their machine ids differ.
    env = {"GC_EXEC_CITY_PATH": "/srv/city"}
    a = resolve(env, home_dir, machine="machine-a")
    b = resolve(env, home_dir, machine="machine-b")
    assert a.session != b.session
    assert a.socket != b.socket
    assert a.state_dir != b.state_dir


def test_the_default_machine_is_what_hc_calls_this_machine(
    home_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths_module, "machine_identity", lambda: "machine-x")
    env = {"GC_EXEC_CITY_PATH": "/srv/city"}
    assert resolve_paths(env, home=lambda: str(home_dir), uid=os.getuid()) == resolve(env, home_dir, machine="machine-x")


def test_the_session_names_the_city_under_its_state_root() -> None:
    expected = "gc-" + hashlib.sha256(b"c0ffee\0/srv/R").hexdigest()[:10]
    assert session_name("c0ffee", "/srv/R") == expected


@pytest.mark.parametrize("long_roots", [False, True])
def test_two_state_roots_never_share_a_core(home_dir: Path, short_tmp: Path, long_roots: bool) -> None:
    # Conformance runs use the same city keys under scratch roots. One shared
    # socket would let one core steal the other's (hc's bind unlinks it) and
    # adopt its holders (every <socket>.holder.*.sock in that directory).
    pad = "r" * (120 if long_roots else 1)
    env = {"GC_EXEC_CITY_PATH": "/gc-rpp/city-a"}
    a = resolve(dict(env, GC_EXEC_STATE_DIR=str(short_tmp / f"a{pad}")), home_dir, tmp_root=str(short_tmp))
    b = resolve(dict(env, GC_EXEC_STATE_DIR=str(short_tmp / f"b{pad}")), home_dir, tmp_root=str(short_tmp))
    assert a.city_id == b.city_id
    assert a.session != b.session
    assert a.socket != b.socket
    assert a.state_dir != b.state_dir
    assert (os.path.dirname(a.socket) == os.path.dirname(b.socket)) is long_roots  # the shared /tmp fallback dir


def test_the_state_root_is_compared_normalized(home_dir: Path, short_tmp: Path) -> None:
    clean = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": str(short_tmp / "R")}, home_dir)
    messy = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": f"{short_tmp}//R/./"}, home_dir)
    assert messy == clean


def test_a_symlinked_spelling_of_the_root_names_the_same_core(home_dir: Path, short_tmp: Path) -> None:
    real = short_tmp / "real"
    real.mkdir()
    alias = short_tmp / "alias"
    alias.symlink_to(real)
    direct = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": str(real / "R")}, home_dir)
    aliased = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": str(alias / "R")}, home_dir)
    assert aliased == direct


def test_doctor_reads_gc_city_path_to_the_same_core(home_dir: Path) -> None:
    op = resolve({"GC_EXEC_CITY_PATH": "/srv/city"}, home_dir)
    doctor = resolve_paths(
        {"GC_CITY_PATH": "/srv/city"},
        machine="machine-a",
        home=lambda: str(home_dir),
        uid=os.getuid(),
        city_var="GC_CITY_PATH",
    )
    assert doctor == op


def test_a_long_state_root_moves_the_socket_to_a_private_tmp_dir(home_dir: Path, short_tmp: Path) -> None:
    root = short_tmp / ("r" * 120)
    paths = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": str(root)}, home_dir, tmp_root=str(short_tmp))
    assert paths.socket == str(short_tmp / f"gc-herdr-core-{os.getuid()}" / f"{paths.session}.sock")
    assert paths.state_dir == str(root / "herdr-core" / paths.session)


def test_the_socket_moves_when_only_hcs_holder_sockets_would_overflow(home_dir: Path, short_tmp: Path) -> None:
    # hc binds <session>.holder.<8hex>.sock beside the main socket, so the
    # main path fitting in sun_path is not enough.
    root = short_tmp / ("r" * (SUN_PATH_MAX - 50 - len(str(short_tmp)) - 1))
    paths = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": str(root)}, home_dir, tmp_root=str(short_tmp))
    session = paths.session
    main = f"{root}/herdr-core/{session}/{session}.sock"
    assert len(main.encode()) < SUN_PATH_MAX
    assert len(main.encode()) - len(".sock") + HOLDER_SOCKET_SUFFIX_LEN >= SUN_PATH_MAX
    assert paths.socket == str(short_tmp / f"gc-herdr-core-{os.getuid()}" / f"{session}.sock")


def test_ensure_dirs_makes_private_directories(home_dir: Path, short_tmp: Path) -> None:
    paths = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": str(short_tmp / "R")}, home_dir)
    ensure_dirs(paths)
    for directory in (
        paths.state_root,
        os.path.dirname(paths.state_dir),
        paths.state_dir,
        paths.config_home,
        os.path.dirname(paths.config_file),
        os.path.dirname(paths.socket),
    ):
        st = os.lstat(directory)
        assert stat.S_ISDIR(st.st_mode), directory
        assert stat.S_IMODE(st.st_mode) == 0o700, directory
    assert not os.path.exists(paths.config_file)  # it creates directories only


def test_ensure_dirs_refuses_a_symlinked_state_root(home_dir: Path, short_tmp: Path) -> None:
    real = short_tmp / "real"
    real.mkdir(mode=0o700)
    link = short_tmp / "R"
    link.symlink_to(real)
    paths = resolve({"GC_EXEC_CITY_PATH": "/c", "GC_EXEC_STATE_DIR": str(link)}, home_dir)
    with pytest.raises(StateDirError):
        ensure_dirs(paths)


@pytest.mark.parametrize("scoped", [True, False])
def test_nothing_is_written_under_the_city_path_or_the_cwd(
    home_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scoped: bool
) -> None:
    city = tmp_path / "city"
    (city / ".gc").mkdir(parents=True)
    (city / "city.toml").write_text("[workspace]\nname = 'c'\n")
    before = tree_snapshot(city)
    monkeypatch.chdir(city)
    env = {"GC_EXEC_CITY_PATH": str(city)} if scoped else {}
    paths = resolve(dict(env, **CALLER_NOISE), home_dir, tmp_root=str(tmp_path))
    ensure_dirs(paths)
    assert tree_snapshot(city) == before
    assert paths.state_root.startswith(str(home_dir) + os.sep)
    for path in (paths.state_root, paths.state_dir, paths.config_home, paths.socket):
        assert not path.startswith(str(city))


def tree_snapshot(root: Path) -> List[Tuple[str, int]]:
    """Every path under root with its mtime, to prove nothing wrote there."""
    out: List[Tuple[str, int]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in sorted(dirnames + filenames):
            full = os.path.join(dirpath, name)
            out.append((os.path.relpath(full, root), os.lstat(full).st_mtime_ns))
    out.append((".", os.lstat(root).st_mtime_ns))
    return sorted(out)
