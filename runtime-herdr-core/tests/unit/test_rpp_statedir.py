"""The state root R and the city key (gascity docs/reference/exec-session-provider.md
"Environment Variables")."""

from __future__ import annotations

import hashlib
import os
import pwd
import stat
from pathlib import Path

import pytest

from gc_runtime_herdr_core.rpp.statedir import (
    UNSCOPED_CITY_KEY,
    StateDirError,
    city_id,
    city_key,
    ensure_private_dir,
    host_name,
    password_home,
    state_root,
)

LEAF = "gc-runtime-herdr-core"


def test_city_key_is_the_raw_city_path() -> None:
    assert city_key({"GC_EXEC_CITY_PATH": "/srv/cities/bright-lights/"}) == "/srv/cities/bright-lights/"
    assert city_key({"GC_EXEC_CITY_PATH": "relative/city"}) == "relative/city"


@pytest.mark.parametrize("env", [{}, {"GC_EXEC_CITY_PATH": ""}])
def test_unset_city_path_is_the_unscoped_bucket(env: dict[str, str]) -> None:
    assert UNSCOPED_CITY_KEY == "unscoped"
    assert city_key(env) == "unscoped"


def test_unset_city_path_never_reads_the_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    city = tmp_path / "city"
    city.mkdir()
    (city / "city.toml").write_text("[workspace]\n")
    monkeypatch.chdir(city)
    assert city_key({}) == "unscoped"
    assert city_id("h", city_key({})) == city_id("h", "unscoped")
    assert city_id("h", city_key({})) != city_id("h", str(city))


def test_city_id_keys_host_and_city() -> None:
    expected = hashlib.sha256(b"host-a\0/srv/city").hexdigest()
    assert city_id("host-a", "/srv/city") == expected
    assert city_id("host-b", "/srv/city") != expected
    assert city_id("host-a", "/srv/city2") != expected


def test_doctor_and_ops_key_the_same_city_alike() -> None:
    path = "/home/u/cities/alpha"
    from_op = city_key({"GC_EXEC_CITY_PATH": path})
    from_doctor = city_key({"GC_CITY_PATH": path}, var="GC_CITY_PATH")
    assert city_id("h", from_op) == city_id("h", from_doctor)


def test_host_name_is_uname_n() -> None:
    assert host_name() == os.uname().nodename


def test_password_home_comes_from_the_password_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/nonexistent-home")
    assert password_home() == pwd.getpwuid(os.getuid()).pw_dir


def test_state_root_defaults_under_the_password_home(home_dir: Path) -> None:
    env = {"HOME": "/elsewhere", "XDG_STATE_HOME": "/xdg/state", "XDG_RUNTIME_DIR": "/run/x"}
    root = state_root(env, leaf=LEAF, home=lambda: str(home_dir))
    assert root == str(home_dir / ".local" / "state" / LEAF)


def test_state_root_takes_gc_exec_state_dir(tmp_path: Path, home_dir: Path) -> None:
    root = state_root({"GC_EXEC_STATE_DIR": str(tmp_path / "R")}, leaf=LEAF, home=lambda: str(home_dir))
    assert root == str(tmp_path / "R")


def test_state_root_refuses_a_relative_state_dir(home_dir: Path) -> None:
    with pytest.raises(StateDirError):
        state_root({"GC_EXEC_STATE_DIR": "state"}, leaf=LEAF, home=lambda: str(home_dir))


def test_ensure_private_dir_creates_0700(tmp_path: Path) -> None:
    path = tmp_path / "a" / "R"
    ensure_private_dir(str(path))
    st = os.lstat(path)
    assert stat.S_ISDIR(st.st_mode)
    assert stat.S_IMODE(st.st_mode) == 0o700


def test_ensure_private_dir_repairs_loose_modes(tmp_path: Path) -> None:
    path = tmp_path / "R"
    path.mkdir(mode=0o755)
    os.chmod(path, 0o755)
    ensure_private_dir(str(path))
    assert stat.S_IMODE(os.lstat(path).st_mode) == 0o700


def test_ensure_private_dir_refuses_a_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    link = tmp_path / "R"
    link.symlink_to(real)
    with pytest.raises(StateDirError, match="symlink"):
        ensure_private_dir(str(link))


def test_ensure_private_dir_refuses_another_owners_directory(tmp_path: Path) -> None:
    path = tmp_path / "R"
    path.mkdir(mode=0o755)
    before = os.lstat(path).st_mode
    with pytest.raises(StateDirError, match="owned"):
        ensure_private_dir(str(path), uid=os.getuid() + 1)
    assert os.lstat(path).st_mode == before  # refused before any repair


def test_ensure_private_dir_refuses_a_file(tmp_path: Path) -> None:
    path = tmp_path / "R"
    path.write_text("")
    with pytest.raises(StateDirError):
        ensure_private_dir(str(path))
