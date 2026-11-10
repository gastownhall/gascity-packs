"""The pin and ``gc herdr-core install``: a stub release server (a directory),
stub binaries that are never executed, and a temp install root."""

from __future__ import annotations

import json
import os
import pwd
import stat
from pathlib import Path
from typing import Dict, Optional

import pytest
from releasekit import RELEASES, STUB, TARGET, archive, make_pin, pin_doc, publish, sha

from gc_runtime_herdr_core.herdrcore import install as installer
from gc_runtime_herdr_core.herdrcore.config import ConfigError, install_root, pin_policy, pinned_binary
from gc_runtime_herdr_core.herdrcore.install import (
    InstallError,
    directory_fetch,
    install,
    installed_versions,
    verify_installed,
)
from gc_runtime_herdr_core.herdrcore.pin import PinError, default_pin_path, host_target, load_pin, parse_pin
from gc_runtime_herdr_core.herdrcore.procs import Proc, ProcError, ProcSource
from gc_runtime_herdr_core.rpp.cancel import CancelToken


class Procs(ProcSource):
    """A process table whose processes run the executables given."""

    def __init__(self, exes: Optional[Dict[int, str]] = None, *, broken: bool = False) -> None:
        self.exes = exes or {}
        self.broken = broken

    def snapshot(self) -> Dict[int, Proc]:
        if self.broken:
            raise ProcError("no /proc")
        return {pid: Proc(pid=pid, ppid=1, uid=os.getuid(), start="1", comm="x", argv=("x",)) for pid in self.exes}

    def environ(self, pid: int) -> Optional[Dict[str, str]]:
        return {}

    def exe(self, pid: int) -> Optional[str]:
        return self.exes.get(pid)


def run_install(tmp_path: Path, version: str, data: bytes, *, procs: Optional[ProcSource] = None, pin_sha: Optional[str] = None, manifest_sha: Optional[str] = None, now: int = 1000) -> installer.InstallOutcome:
    releases = tmp_path / "releases"
    publish(releases, version, data, manifest_sha=manifest_sha)
    pin = make_pin(version, pin_sha or sha(data))
    return install(
        pin,
        root=str(tmp_path / "home" / ".local/share/gc-runtime-herdr-core/hc"),
        target=TARGET,
        fetch=directory_fetch(pin, str(releases)),
        procs=procs or Procs(),
        cancel=CancelToken(),
        now_ms=lambda: now,
    )


def root_of(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".local/share/gc-runtime-herdr-core/hc"


# --- the pin -----------------------------------------------------------------------


def test_the_shipped_pin_names_0_1_19_with_a_sha256_per_platform() -> None:
    pin = load_pin()
    assert str(pin.version) == "0.1.19" and str(pin.min_version) == "0.1.19"
    assert [str(v) for v in pin.tested] == ["0.1.19"]
    assert pin.releases == "https://releases.herdr.dev/core"
    assert sorted(pin.targets) == ["linux-aarch64", "linux-x86_64", "macos-aarch64", "macos-x86_64"]
    for name, target in pin.targets.items():
        assert target.asset == f"herdr-core-{name}.tar.gz"
        assert len(target.sha256) == 64
    assert pin.target("linux-x86_64").sha256 == "4adcfb423d52f24c5cc4a1e2cd2fcad1f62d28bb77876ac472c29082a3eaa424"
    assert pin_policy().min_version == pin.min_version


def test_an_unpinned_pack_is_an_error_never_a_fallback(tmp_path: Path) -> None:
    with pytest.raises(PinError, match="not pinned"):
        load_pin(str(tmp_path / "missing.json"))
    doc = pin_doc("0.1.19", "a" * 64)
    for key, value in [("sha", None), ("releases", "http://plain"), ("generation", 2), ("min_version", "0.2.0")]:
        broken = dict(doc)
        if key == "sha":
            broken["targets"] = {TARGET: {"asset": "x.tar.gz", "sha256": "ABC"}}
        else:
            broken[key] = value
        with pytest.raises(PinError):
            parse_pin(json.dumps(broken).encode())
    with pytest.raises(PinError):
        parse_pin(json.dumps({**doc, "targets": {}}).encode())
    with pytest.raises(PinError, match="not pinned for"):
        make_pin("0.1.19", "a" * 64).target("macos-aarch64")


def test_the_pin_lives_beside_the_package() -> None:
    assert Path(default_pin_path()).name == "hc-pin.json"
    assert Path(default_pin_path()).parent.name == "assets"


@pytest.mark.parametrize(
    "system, machine, want",
    [("Linux", "x86_64", "linux-x86_64"), ("Linux", "aarch64", "linux-aarch64"), ("Darwin", "arm64", "macos-aarch64"), ("Darwin", "x86_64", "macos-x86_64")],
)
def test_host_targets_use_the_release_manifests_names(system: str, machine: str, want: str) -> None:
    assert host_target(system, machine) == want


def test_a_host_without_a_build_is_refused() -> None:
    with pytest.raises(PinError):
        host_target("Windows", "x86_64")


# --- install root -------------------------------------------------------------------


def test_the_install_root_is_under_the_password_database_home_never_HOME(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/somewhere/else")
    monkeypatch.setenv("XDG_DATA_HOME", "/elsewhere/data")
    home = pwd.getpwuid(os.getuid()).pw_dir
    assert install_root() == os.path.join(home, ".local/share/gc-runtime-herdr-core/hc")
    assert pinned_binary() == os.path.join(home, ".local/share/gc-runtime-herdr-core/hc/0.1.19/herdr-core")


# --- install --------------------------------------------------------------------------


def test_install_places_the_verified_binary_read_only(tmp_path: Path) -> None:
    data = archive()
    outcome = run_install(tmp_path, "0.1.19", data)
    binary = root_of(tmp_path) / "0.1.19" / "herdr-core"
    assert outcome.installed and outcome.binary == str(binary)
    assert binary.read_bytes() == STUB
    assert stat.S_IMODE(binary.stat().st_mode) == 0o555
    assert stat.S_IMODE(binary.parent.stat().st_mode) == 0o555
    record = json.loads((binary.parent / "install.json").read_text())
    assert record["archive_sha256"] == sha(data) and record["binary_sha256"] == sha(STUB)
    assert verify_installed(make_pin("0.1.19", sha(data)), str(root_of(tmp_path)), TARGET) is None
    assert stat.S_IMODE(root_of(tmp_path).stat().st_mode) == 0o700
    # Installing again is a no-op that leaves the build alone.
    again = run_install(tmp_path, "0.1.19", data)
    assert not again.installed and binary.read_bytes() == STUB


def test_a_sha_mismatch_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    data = archive()
    with pytest.raises(InstallError, match="sha256 .* is not the pinned"):
        run_install(tmp_path, "0.1.19", data, pin_sha="b" * 64, manifest_sha="b" * 64)
    assert not (tmp_path / "home").exists()


def test_a_manifest_that_disagrees_with_the_pin_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InstallError, match="differs from the pin"):
        run_install(tmp_path, "0.1.19", archive(), manifest_sha="c" * 64)
    assert not (tmp_path / "home").exists()


@pytest.mark.parametrize(
    "data",
    [
        archive(name="other"),
        archive(link=True),
        archive(extra=[("./herdr-core", b"twice")]),
        b"not a tarball",
    ],
)
def test_an_archive_without_exactly_one_regular_binary_is_refused(tmp_path: Path, data: bytes) -> None:
    with pytest.raises(InstallError):
        run_install(tmp_path, "0.1.19", data)
    assert installed_versions(str(root_of(tmp_path))) == []


def test_only_the_binary_is_taken_from_the_archive(tmp_path: Path) -> None:
    run_install(tmp_path, "0.1.19", archive(extra=[("../escape", b"x"), ("README", b"y")]))
    assert sorted(os.listdir(root_of(tmp_path) / "0.1.19")) == ["herdr-core", "install.json"]
    assert not (tmp_path / "home" / ".local/share/gc-runtime-herdr-core/escape").exists()


def test_a_failed_rename_keeps_the_installed_version_and_leaves_no_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_install(tmp_path, "0.1.19", archive(b"old"))
    binary = root_of(tmp_path) / "0.1.19" / "herdr-core"
    os.chmod(binary.parent, 0o755)
    os.chmod(binary, 0o755)
    binary.write_bytes(b"tampered")  # verify_installed now fails: a reinstall replaces it
    os.chmod(binary.parent, 0o555)
    real_rename = os.rename

    def failing(src: str, dst: str) -> None:
        if ".new-" in src:
            raise OSError(28, "No space left on device")
        real_rename(src, dst)

    monkeypatch.setattr(os, "rename", failing)
    with pytest.raises(OSError):
        run_install(tmp_path, "0.1.19", archive(b"old"))
    monkeypatch.setattr(os, "rename", real_rename)
    assert binary.read_bytes() == b"tampered"  # the old directory is back in place
    assert [n for n in os.listdir(root_of(tmp_path)) if n.startswith(".") and n != ".install.lock"] == []


def test_the_previous_version_is_kept_for_rollback_and_older_ones_collected(tmp_path: Path) -> None:
    run_install(tmp_path, "0.1.17", archive(b"17"), now=1)
    run_install(tmp_path, "0.1.18", archive(b"18"), now=2)
    assert installed_versions(str(root_of(tmp_path))) == ["0.1.17", "0.1.18"]
    outcome = run_install(tmp_path, "0.1.19", archive(b"19"), now=3)
    assert installed_versions(str(root_of(tmp_path))) == ["0.1.18", "0.1.19"]
    assert outcome.removed == ("0.1.17",) and outcome.kept == ("0.1.18", "0.1.19")


def test_a_version_a_process_still_runs_is_never_collected(tmp_path: Path) -> None:
    run_install(tmp_path, "0.1.17", archive(b"17"), now=1)
    run_install(tmp_path, "0.1.18", archive(b"18"), now=2)
    running = str(root_of(tmp_path) / "0.1.17" / "herdr-core") + " (deleted)"
    outcome = run_install(tmp_path, "0.1.19", archive(b"19"), procs=Procs({4242: running}), now=3)
    assert outcome.removed == ()
    assert installed_versions(str(root_of(tmp_path))) == ["0.1.17", "0.1.18", "0.1.19"]


def test_nothing_is_collected_when_the_process_table_cannot_be_read(tmp_path: Path) -> None:
    run_install(tmp_path, "0.1.17", archive(b"17"), now=1)
    run_install(tmp_path, "0.1.18", archive(b"18"), now=2)
    outcome = run_install(tmp_path, "0.1.19", archive(b"19"), procs=Procs(broken=True), now=3)
    assert outcome.removed == () and "cannot tell" in outcome.gc_note
    assert installed_versions(str(root_of(tmp_path))) == ["0.1.17", "0.1.18", "0.1.19"]


def test_a_tampered_or_foreign_install_fails_verification(tmp_path: Path) -> None:
    data = archive()
    run_install(tmp_path, "0.1.19", data)
    root = str(root_of(tmp_path))
    pin = make_pin("0.1.19", sha(data))
    assert verify_installed(make_pin("0.1.19", "d" * 64), root, TARGET) is not None
    os.chmod(Path(root) / "0.1.19", 0o755)
    (Path(root) / "0.1.19" / "install.json").chmod(0o644)
    (Path(root) / "0.1.19" / "install.json").unlink()
    problem = verify_installed(pin, root, TARGET)
    assert problem is not None and "no install.json" in problem


def test_the_https_fetch_refuses_plain_http() -> None:
    with pytest.raises(InstallError, match="non-https"):
        installer.https_fetch("http://releases.herdr.dev/core/0.1.19/manifest.json", 10)


def test_a_test_release_directory_is_honoured_only_under_GC_HC_TEST(tmp_path: Path) -> None:
    pin = make_pin("0.1.19", "a" * 64)
    env = {installer.TEST_RELEASES_ENV: str(tmp_path)}
    publish(tmp_path, "0.1.19", b"x")
    assert installer.fetch_for(pin, env, test=True)(f"{RELEASES}/0.1.19/manifest.json", 1 << 16)
    with pytest.raises(InstallError):
        installer.fetch_for(pin, env, test=False)(f"{RELEASES}/0.1.19/manifest.json", 1 << 16)


def test_config_reports_an_unusable_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    from gc_runtime_herdr_core.herdrcore import config

    def broken(path: Optional[str] = None) -> object:
        raise PinError("hc is not pinned: cannot read hc-pin.json")

    monkeypatch.setattr(config, "load_pin", broken)
    with pytest.raises(ConfigError, match="not pinned"):
        config.pin_policy()
    with pytest.raises(ConfigError, match="not pinned"):
        config.pinned_binary(lambda: "/h")

