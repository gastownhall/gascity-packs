from __future__ import annotations

import os
import pathlib
import shutil
import stat
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

TIERS = {
    "slack-mini": "gc-slack-mini-adapter",
    "slack-channel": "gc-slack-channel-adapter",
}

GO_STUB = """#!/usr/bin/env bash
echo "go $* cwd=$PWD" >> "$GO_STUB_LOG"
if [ "$1" = "version" ]; then
  echo "go version go${GO_STUB_VERSION:-99.0.0} stub/stub"
  exit 0
fi
if [ "$1" = "build" ]; then
  echo "buildenv GOCACHE=${GOCACHE:-unset} GOPATH=${GOPATH:-unset}" >> "$GO_STUB_LOG"
  if [ -n "${GO_STUB_BUILD_FAILS:-}" ]; then
    echo "go stub: simulated compile failure" >&2
    exit 1
  fi
  out=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "-o" ] && out="$a"
    prev="$a"
  done
  [ -n "$out" ] || { echo "go stub: no -o target" >&2; exit 2; }
  printf '%s\\n' '#!/usr/bin/env bash' \\
    'echo "STUB_ADAPTER_RAN pwd=$PWD ARGS=$* MARKER_VAR=${MARKER_VAR:-unset}"' > "$out"
  chmod +x "$out"
  exit 0
fi
echo "go stub: unexpected invocation: $*" >&2
exit 2
"""

BARE_SUPERVISOR_ENV = [
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "GOCACHE",
    "GOPATH",
    "GOMODCACHE",
]


@pytest.fixture(params=sorted(TIERS))
def tier(request):
    return request.param


@pytest.fixture()
def harness(tier, tmp_path: pathlib.Path):
    pack_dir = REPO_ROOT / tier
    run_sh = pack_dir / "adapter" / "run.sh"
    binary_name = TIERS[tier]

    adapter = tmp_path / "adapter"
    adapter.mkdir()
    assert run_sh.is_file(), f"{run_sh} is not checked in"
    shutil.copy(run_sh, adapter / "run.sh")
    (adapter / "run.sh").chmod(0o755)
    shutil.copy(pack_dir / "adapter" / "go.mod", adapter / "go.mod")

    stub_bin = tmp_path / "stubbin"
    stub_bin.mkdir()
    go = stub_bin / "go"
    go.write_text(GO_STUB)
    go.chmod(0o755)

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    go_log = tmp_path / "go-invocations.log"

    def run(extra_env: dict | None = None, drop_env: list[str] | None = None, args=()):
        env = dict(os.environ)
        env["PATH"] = f"{stub_bin}:{env['PATH']}"
        env["GO_STUB_LOG"] = str(go_log)
        env["HOME"] = str(fake_home)
        env.update(extra_env or {})
        for key in drop_env or []:
            env.pop(key, None)
        return subprocess.run(
            [str(adapter / "run.sh"), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def log_lines(prefix: str) -> list[str]:
        if not go_log.exists():
            return []
        return [l for l in go_log.read_text().splitlines() if l.startswith(prefix)]

    return pack_dir, adapter, binary_name, run, lambda: log_lines("go build"), lambda: log_lines("buildenv ")


def required_go_version(adapter: pathlib.Path) -> str:
    for line in (adapter / "go.mod").read_text().splitlines():
        if line.startswith("go "):
            return line.split(None, 1)[1].strip()
    raise AssertionError("no `go` directive in go.mod")


def test_missing_binary_is_rebuilt_and_execd(harness):
    _, adapter, binary_name, run, builds, _ = harness
    proc = run(args=("--flag", "value"))
    assert proc.returncode == 0, proc.stderr
    assert "STUB_ADAPTER_RAN" in proc.stdout
    assert "ARGS=--flag value" in proc.stdout
    assert "rebuilding from source" in proc.stderr
    assert "gc import install" in proc.stderr
    recorded = builds()
    assert len(recorded) == 1, recorded
    assert " . cwd=" in recorded[0], recorded[0]
    build_cwd = recorded[0].split(" cwd=", 1)[1]
    assert pathlib.Path(build_cwd).resolve() == adapter.resolve(), recorded[0]
    assert (adapter / binary_name).exists()
    assert not list(adapter.glob(f"{binary_name}.build.*"))


def test_existing_binary_skips_build(harness):
    _, adapter, binary_name, run, builds, _ = harness
    prebuilt = adapter / binary_name
    prebuilt.write_text("#!/usr/bin/env bash\necho PREBUILT_RAN\n")
    prebuilt.chmod(0o755)
    proc = run()
    assert proc.returncode == 0, proc.stderr
    assert "PREBUILT_RAN" in proc.stdout
    assert builds() == []


def test_self_heal_is_idempotent_across_restarts(harness):
    _, _, _, run, builds, _ = harness
    first = run()
    second = run()
    assert first.returncode == 0 and second.returncode == 0
    assert "STUB_ADAPTER_RAN" in second.stdout
    assert len(builds()) == 1


def test_inherited_environment_reaches_the_adapter(harness):
    _, _, _, run, _, _ = harness
    proc = run(extra_env={"MARKER_VAR": "from-service-env"})
    assert proc.returncode == 0, proc.stderr
    assert "MARKER_VAR=from-service-env" in proc.stdout


def test_self_heal_builds_when_home_is_unset(harness, tmp_path):
    _, adapter, binary_name, run, builds, build_environments = harness
    tmp = tmp_path / "tmpdir"
    tmp.mkdir()
    proc = run(extra_env={"TMPDIR": str(tmp)}, drop_env=BARE_SUPERVISOR_ENV)
    assert proc.returncode == 0, proc.stderr
    assert "STUB_ADAPTER_RAN" in proc.stdout
    assert len(builds()) == 1, builds()
    uid = os.getuid()
    gocache = tmp / f"{binary_name}-gocache-{uid}"
    gopath = tmp / f"{binary_name}-gopath-{uid}"
    assert build_environments() == [
        f"buildenv GOCACHE={gocache} GOPATH={gopath}"
    ], build_environments()
    for build_dir in (gocache, gopath):
        assert build_dir.is_dir() and not build_dir.is_symlink()
        assert stat.S_IMODE(build_dir.stat().st_mode) == 0o700
    assert (adapter / binary_name).exists()


@pytest.mark.parametrize("kind", ["gocache", "gopath"])
def test_home_less_build_refuses_a_symlinked_build_dir(harness, tmp_path, kind):
    _, adapter, binary_name, run, builds, _ = harness
    tmp = tmp_path / "tmpdir"
    tmp.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp / f"{binary_name}-{kind}-{os.getuid()}").symlink_to(elsewhere)
    proc = run(extra_env={"TMPDIR": str(tmp)}, drop_env=BARE_SUPERVISOR_ENV)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "refusing to build with it" in proc.stderr
    assert builds() == []
    assert not (adapter / binary_name).exists()


@pytest.mark.parametrize("cache_var", ["XDG_CACHE_HOME", "GOCACHE"])
def test_gopath_is_defaulted_whenever_home_is_unset(harness, tmp_path, cache_var):
    _, _, binary_name, run, _, build_environments = harness
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    drop = [v for v in BARE_SUPERVISOR_ENV if v != cache_var]
    tmp = tmp_path / "tmpdir"
    tmp.mkdir()
    proc = run(extra_env={cache_var: str(cache_dir), "TMPDIR": str(tmp)}, drop_env=drop)
    assert proc.returncode == 0, proc.stderr
    expected_gocache = str(cache_dir) if cache_var == "GOCACHE" else "unset"
    assert build_environments() == [
        f"buildenv GOCACHE={expected_gocache} GOPATH={tmp}/{binary_name}-gopath-{os.getuid()}"
    ], build_environments()


def test_shell_function_named_go_does_not_shadow_the_toolchain(harness):
    _, _, _, run, builds, _ = harness
    exported_function = {"BASH_FUNC_go%%": "() {  echo 'shadowed go was called' >&2; return 127\n}"}
    proc = run(extra_env=exported_function)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "shadowed go was called" not in proc.stderr
    assert "no Go toolchain found" not in proc.stderr
    assert len(builds()) == 1, builds()
    assert "STUB_ADAPTER_RAN" in proc.stdout


def test_toolchain_older_than_go_mod_is_rejected_when_pinned(harness):
    _, adapter, binary_name, run, builds, _ = harness
    proc = run(extra_env={"GO_STUB_VERSION": "1.0.0", "GOTOOLCHAIN": "local"})
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert f"need Go >= {required_go_version(adapter)}, found 1.0.0" in proc.stderr
    assert "GOTOOLCHAIN=local" in proc.stderr
    assert builds() == []
    assert not (adapter / binary_name).exists()


def test_toolchain_older_than_go_mod_still_builds_when_downloadable(harness):
    _, adapter, _, run, builds, _ = harness
    proc = run(extra_env={"GO_STUB_VERSION": "1.0.0"}, drop_env=["GOTOOLCHAIN"])
    assert proc.returncode == 0, proc.stderr
    assert f"go.mod needs >= {required_go_version(adapter)}" in proc.stderr
    assert "STUB_ADAPTER_RAN" in proc.stdout
    assert len(builds()) == 1, builds()


def test_go_build_failure_exits_1_and_publishes_nothing(harness):
    _, adapter, binary_name, run, _, _ = harness
    proc = run(extra_env={"GO_STUB_BUILD_FAILS": "1"})
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "go build failed" in proc.stderr
    assert "manual fix: cd " in proc.stderr
    assert "STUB_ADAPTER_RAN" not in proc.stdout
    assert not (adapter / binary_name).exists()
    assert not list(adapter.glob(f"{binary_name}.build.*"))


def test_stale_build_temp_is_ignored(harness):
    _, adapter, binary_name, run, builds, _ = harness
    stale = adapter / f"{binary_name}.build.99999"
    stale.write_text("#!/usr/bin/env bash\necho STALE_TEMP_RAN\n")
    stale.chmod(0o755)
    proc = run()
    assert proc.returncode == 0, proc.stderr
    assert "STALE_TEMP_RAN" not in proc.stdout
    assert "STUB_ADAPTER_RAN" in proc.stdout
    assert len(builds()) == 1


def test_pack_service_command_is_the_checked_in_run_sh(tier):
    try:
        import tomllib
    except ModuleNotFoundError:
        pytest.skip("tomllib unavailable")
    pack_dir = REPO_ROOT / tier
    with open(pack_dir / "pack.toml", "rb") as fh:
        pack = tomllib.load(fh)
    services = {s["name"]: s for s in pack.get("service", [])}
    assert tier in services, f"{tier} [[service]] block missing from pack.toml"
    command = services[tier]["process"]["command"]
    assert command == ["./adapter/run.sh"], command
    rel = pathlib.Path(command[0])
    target = pack_dir / rel
    assert target.exists() and os.access(target, os.X_OK)
    ignored = subprocess.run(
        ["git", "check-ignore", str(rel)], cwd=pack_dir, capture_output=True, text=True
    )
    assert ignored.returncode == 1, (
        f"{rel}: git check-ignore exited {ignored.returncode} "
        f"(0 means gitignored): {ignored.stderr}"
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(rel)],
        cwd=pack_dir,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, f"{rel} is not tracked by git: {tracked.stderr}"
