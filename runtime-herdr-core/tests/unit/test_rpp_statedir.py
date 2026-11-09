"""The state root R and the city key (gascity docs/reference/exec-session-provider.md
"Environment Variables")."""

from __future__ import annotations

import hashlib
import os
import pwd
import stat
import sys
from pathlib import Path
from typing import Tuple

import pytest

from gc_runtime_herdr_core.rpp.statedir import (
    UNSCOPED_CITY_KEY,
    StateDirError,
    city_id,
    city_key,
    darwin_host_uuid,
    ensure_private_dir,
    format_host_uuid,
    host_name,
    machine_identity,
    state_root,
    user_home,
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


def test_city_id_keys_machine_and_city() -> None:
    expected = hashlib.sha256(b"4f2c9a\0/srv/city").hexdigest()
    assert city_id("4f2c9a", "/srv/city") == expected
    assert city_id("7d01ee", "/srv/city") != expected
    assert city_id("4f2c9a", "/srv/city2") != expected


# --- machine identity: what hc itself calls this machine ---------------------


def machine_files(tmp_path: Path, etc: object, dbus: object) -> Tuple[str, str]:
    """Two machine-id files; ``None`` leaves one missing."""
    paths = (tmp_path / "etc-machine-id", tmp_path / "dbus-machine-id")
    for path, content in zip(paths, (etc, dbus)):
        if isinstance(content, str):
            path.write_text(content)
    return str(paths[0]), str(paths[1])


def unreachable_host() -> str:
    raise AssertionError("the host name is only a fallback")


def test_identity_is_etc_machine_id(tmp_path: Path) -> None:
    files = machine_files(tmp_path, "0123456789abcdef0123456789abcdef\n", "ffff")
    assert machine_identity(darwin=False, files=files, host=unreachable_host) == "0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize("etc", [None, "", "  \n", "uninitialized\n"])
def test_identity_falls_back_to_the_dbus_machine_id(tmp_path: Path, etc: object) -> None:
    files = machine_files(tmp_path, etc, "fedcba98\n")
    assert machine_identity(darwin=False, files=files, host=unreachable_host) == "fedcba98"


def test_identity_falls_back_to_the_host_name_only_when_no_id_is_readable(tmp_path: Path) -> None:
    files = machine_files(tmp_path, None, "uninitialized")
    assert machine_identity(darwin=False, files=files, host=lambda: "box-1") == "box-1"


def test_a_renamed_host_keeps_its_identity(tmp_path: Path) -> None:
    # hc does not treat a host name change as a new machine; neither may the
    # city key, or every city re-keys at once (DHCP and Bonjour rename Macs).
    files = machine_files(tmp_path, "abc123\n", None)
    before = machine_identity(darwin=False, files=files, host=lambda: "laptop.local")
    after = machine_identity(darwin=False, files=files, host=lambda: "laptop-2.local")
    assert before == after == "abc123"


def test_macos_identity_is_the_host_uuid(tmp_path: Path) -> None:
    files = machine_files(tmp_path, "linux-id", None)
    uuid = "564D8E2A-1B2C-3D4E-5F60-718293A4B5C6"
    assert machine_identity(darwin=True, files=files, host_uuid=lambda: uuid, host=unreachable_host) == uuid
    assert machine_identity(darwin=True, files=files, host_uuid=lambda: None, host=lambda: "mac") == "mac"


def test_host_uuid_is_formatted_like_ioplatformuuid() -> None:
    assert format_host_uuid(bytes(range(16))) == "00010203-0405-0607-0809-0A0B0C0D0E0F"


@pytest.mark.skipif(sys.platform == "darwin", reason="exercises the non-macOS path")
def test_the_macos_source_reads_nothing_elsewhere() -> None:
    assert darwin_host_uuid() is None


def test_this_hosts_identity_is_stable() -> None:
    assert machine_identity() == machine_identity()
    if sys.platform.startswith("linux"):
        try:
            with open("/etc/machine-id", encoding="ascii") as fh:
                etc = fh.read().strip()
        except OSError:
            etc = ""
        if etc and etc != "uninitialized":
            assert machine_identity() == etc


def test_doctor_and_ops_key_the_same_city_alike() -> None:
    path = "/home/u/cities/alpha"
    from_op = city_key({"GC_EXEC_CITY_PATH": path})
    from_doctor = city_key({"GC_CITY_PATH": path}, var="GC_CITY_PATH")
    assert city_id("h", from_op) == city_id("h", from_doctor)


def test_host_name_is_uname_n() -> None:
    assert host_name() == os.uname().nodename


def test_user_home_comes_from_the_user_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/nonexistent-home")
    assert user_home() == pwd.getpwuid(os.getuid()).pw_dir


def test_state_root_defaults_under_the_user_home(home_dir: Path) -> None:
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
