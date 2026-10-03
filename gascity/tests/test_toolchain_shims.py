"""Contract tests for gascity/assets/scripts/toolchain/{pnpm,node}.

Each test installs the wrappers into a throwaway shim directory the way the
README recipe does (`node` once, `npm` and `npx` as links to it), points
GC_TOOLCHAIN_DIR at a throwaway toolchain, and drives them with fake
programs: a fake pnpm that records every call and answers the wrapper's
read-only sync question the way pnpm's checkDepsStatus does (from a state
its own installs write over the lockfile, every manifest and the workspace
membership; `--lockfile-only` and the cleanup built-ins leave it out of
sync), fake node trees, and a fake nodejs.org served over file://. Nothing
touches the network or the machine's toolchain.

Round 3 ledger (bead gp-sgbj, 2026-09-11: the shape-A concurrency contract,
the mayor's decision after gate rounds 19 to 29 each found a hole around a
reader/writer model of running commands). The wrapper owns its own question
and the one frozen install per lockfile under the lane lock, and
mutate-vs-mutate serialization on that same lock; a project command runs
after the question holding nothing; nothing tracks running commands; a
running command is not fenced from a dependency mutation another caller
starts afterwards (the documented non-goal). Every row that pinned the
reader/writer model is listed here, not silently dropped:
- (r20) a rebuild started under a running check waits until the check ends:
  removed with the shape-A contract; the reverse is pinned as behaviour in
  test_a_mutate_does_not_wait_for_a_running_project_command.
- (r20) a reader token whose pid is dead holds nothing; a live token fails a
  mutate closed naming its pid: removed with the shape-A contract (there are
  no tokens).
- (r20) the wrapper's own frozen install waits for a live reader: removed
  with the shape-A contract.
- (r20/r21) tokens are dropped on exit and the readers directory is left
  empty: removed with the shape-A contract; no such directory is ever made
  (test_a_project_command_runs_holding_no_lock_and_no_token).
- (r26) a project command inside a running project command asks nothing and
  takes no token: removed with the shape-A contract; it asks pnpm under the
  lock like any other caller
  (test_a_command_started_by_a_running_command_is_any_other_caller).
- (r26) a mutate inside a running project command is refused, closed, naming
  the command, and two scripts each rebuilding are both refused with no wait
  on each other: removed with the shape-A contract; both run, serialized on
  the lock, under the commands that started them (the same test).
Kept from that test as rows of their own: a lane whose node_modules refuses
the lock fails closed and runs under LANE_DEPS=off (r17/r21); LANE_DEPS=off
on a nested command runs it as is; the command names of round 20.

Gate round 30 (on the shape-A commit) found three holes in the lock's own
mechanics and two misstatements, none in the contract; each is a row here:
the reclaim re-check could move a lock that changed hands between its read
and its rename (every change of hands now goes through the reclaim gate,
and the lock is re-read under it right before the move:
test_a_lock_that_changed_hands_between_the_read_and_the_check_is_never_moved);
a pid write that failed still returned the lock as taken
(test_a_pid_that_cannot_be_written_leaves_no_lock_and_fails_closed); a
trapped signal inside the reclaim released the lane lock but not the reclaim
gate (test_a_trapped_signal_releases_the_reclaim_lock_with_the_lane_lock); a
row's name said "never touches the lock" while the question is asked under
it (renamed and now measured during the question:
test_a_caller_whose_lane_is_in_sync_holds_the_lock_for_the_question_only_and_never_waits);
a failed frozen install exited 1 while the header promised pnpm's status
(test_failed_install_leaves_the_lane_out_of_sync_and_the_command_does_not_run).
Gate round 31 found the release path: the mark that says "no longer mine"
was cleared before the rmdir, so a trapped signal between the two left the
gate or the lock standing for good; both removals now run with the signals
held, removal before the mark
(test_a_signal_during_the_release_is_lost_and_nothing_is_left_standing);
and a pid file opened but not written would have held the directory
(removed before the rmdir; no row: no filesystem here fails a one-line
write after a successful open).
"""

from __future__ import annotations

import getpass
import hashlib
import os
import pathlib
import platform
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import threading
import time
import unittest

TOOLCHAIN = pathlib.Path(__file__).resolve().parents[1] / "assets" / "scripts" / "toolchain"
PNPM_SHIM = TOOLCHAIN / "pnpm"
NODE_SHIM = TOOLCHAIN / "node"

CHECK = "--config.verify-deps-before-run=error exec true"

FAKE_PNPM = r"""#!/bin/sh
# A stand-in for pnpm 11.20: records `<cwd>|<verify env>|<argv>` per call,
# honours -C/--dir/--prefix and --ignore-workspace (the working directory is
# the whole project: no lockfile above it is read), answers the read-only sync question from the
# state its installs write (lockfile + manifests + workspace membership),
# installs (optionally slowly, optionally failing), and lets the cleanup
# built-ins and --lockfile-only leave the tree out of sync.
printf '%s|%s|%s\n' "$(pwd -P)" "${pnpm_config_verify_deps_before_run-unset}" "$*" >> "$FAKE_PNPM_LOG"
printf 'PATH0=%s\n' "${PATH%%:*}" >> "$FAKE_PNPM_LOG"
start="$(pwd)"
want=""
ignore_workspace=0
for a in "$@"; do
    if [ -n "$want" ]; then cd "$start" && cd "$a" || exit 3; want=""; continue; fi
    case "$a" in
        --ignore-workspace) ignore_workspace=1 ;;
        -C|--dir|--prefix) want=1 ;;
        -C=*) cd "$start" && cd "${a#-C=}" || exit 3 ;;
        --dir=*) cd "$start" && cd "${a#--dir=}" || exit 3 ;;
        --prefix=*) cd "$start" && cd "${a#--prefix=}" || exit 3 ;;
        --) break ;;
    esac
done
lane() {
    d="$(pwd -P)"
    [ "$ignore_workspace" -eq 0 ] || { printf '%s\n' "$d"; return; }
    while [ ! -f "$d/pnpm-lock.yaml" ] && [ "$d" != / ]; do d="${d%/*}"; [ -n "$d" ] || d=/; done
    if [ -f "$d/pnpm-lock.yaml" ]; then printf '%s\n' "$d"; else pwd -P; fi
}
fp() {
    L="$(lane)"
    (cd "$L" && for f in pnpm-lock.yaml pnpm-workspace.yaml .npmrc package.json packages/*/package.json server/*/package.json; do
        [ -f "$f" ] && { printf '%s ' "$f"; shasum -a 256 < "$f"; }
    done) | shasum -a 256
}
case "$*" in
    "--config.verify-deps-before-run=error exec true"|"--ignore-workspace --config.verify-deps-before-run=error exec true")
        if [ "${FAKE_PNPM_PROBE_ERROR-}" = 1 ]; then echo "EACCES: permission denied, open '.pnpm-workspace-state-v1.json'" >&2; exit 2; fi
        L="$(lane)"
        [ -z "${FAKE_PNPM_LOCK_PROBE-}" ] || { cat "$L/node_modules/.gc-lane-deps.lock/pid" 2>/dev/null || echo none; } > "$FAKE_PNPM_LOCK_PROBE"
        # pnpm 11.20 reports a file error met inside its check under the verify code, on stdout
        if [ "${FAKE_PNPM_PROBE_WRAPPED_ERROR-}" = 1 ]; then echo "[ERR_PNPM_VERIFY_DEPS_BEFORE_RUN] EACCES: permission denied, open '$L/node_modules/.pnpm-workspace-state-v1.json.985617711'"; echo; echo 'Run "pnpm install"'; exit 1; fi
        if [ -f "$L/node_modules/.fake-state" ] && [ "$(cat "$L/node_modules/.fake-state")" = "$(fp)" ]; then exit 0; fi
        # pnpm 11.20 prints this on STDOUT
        echo " ERR_PNPM_VERIFY_DEPS_BEFORE_RUN  Your node_modules are out of sync (fake)"
        exit 1 ;;
esac
first=""
skip=""
after_flag=""
for a in "$@"; do
    if [ -n "$skip" ]; then skip=""; continue; fi
    if [ -n "$after_flag" ]; then
        after_flag=""
        case "$a" in true|false) continue ;; esac     # a boolean option's literal value
    fi
    case "$a" in
        --) break ;;
        -C|--dir|--prefix|-F|--filter|--loglevel|--reporter|--child-concurrency|--network-concurrency|with) skip=1 ;;
        -*) after_flag=1 ;;
        recursive|multi|m|pm) ;;
        *) first="$a"; break ;;
    esac
done
[ -n "$first" ] || for a in "$@"; do case "$a" in install|i|ci|add|update|it|install-test) first="$a"; break ;; esac; done   # `pnpm -- install`
case "$first" in
    install|i|ci|add|update|it|install-test)
        [ -z "${FAKE_PNPM_SLEEP-}" ] || sleep "$FAKE_PNPM_SLEEP"
        if [ "${FAKE_PNPM_FAIL_INSTALL-}" = 1 ]; then echo "fake pnpm: install failed" >&2; exit 7; fi
        L="$(lane)"
        mkdir -p "$L/node_modules" && : > "$L/node_modules/.fake-installed"
        [ -f "$L/pnpm-lock.yaml" ] || echo "lockfileVersion: '9.0'" > "$L/pnpm-lock.yaml"
        case "$*" in
            *--lockfile-only*) echo "# resolved $(date +%s%N)" >> "$L/pnpm-lock.yaml" ;;   # the lockfile moves, the tree does not
            *) fp > "$L/node_modules/.fake-state" ;;
        esac
        if [ -n "${FAKE_PNPM_HOOK-}" ]; then "$FAKE_PNPM_HOOK" run build || exit 9; fi
        [ -z "${FAKE_PNPM_TAKEOVER_PID-}" ] || echo "$FAKE_PNPM_TAKEOVER_PID" > "$L/node_modules/.gc-lane-deps.lock/pid"
        echo "fake pnpm: installed"
        exit 0 ;;
    clean|purge|prune|dedupe|rebuild|remove|rm|link|unlink|patch)
        [ -z "${FAKE_PNPM_SLEEP-}" ] || sleep "$FAKE_PNPM_SLEEP"
        L="$(lane)"
        rm -f "$L/node_modules/.fake-state"
        echo "fake pnpm: mutated"
        exit 0 ;;
esac
[ -z "${FAKE_PNPM_RUN_SLEEP-}" ] || sleep "$FAKE_PNPM_RUN_SLEEP"
if [ -n "${FAKE_PNPM_RUN_HOOK-}" ]; then $FAKE_PNPM_RUN_HOOK || exit 9; fi   # a script of the command re-entering the wrapper
echo "fake pnpm ran: $*"
"""


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exec(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class Fixture:
    """A shim dir with the wrappers, a toolchain dir, and a PATH with fakes."""

    def __init__(self, root: pathlib.Path, *, real_node: bool = False) -> None:
        self.root = root
        self.shims = root / "shims"
        self.toolchain = root / "toolchain"
        self.bin = root / "bin"  # the "machine" PATH: fake node/npm, plus system tools
        self.shims.mkdir()
        self.toolchain.mkdir()
        self.bin.mkdir()
        shutil.copy2(PNPM_SHIM, self.shims / "pnpm")
        shutil.copy2(NODE_SHIM, self.shims / "node")
        (self.shims / "npm").symlink_to("node")
        (self.shims / "npx").symlink_to("node")
        for name in ("node", "npm", "npx"):
            write_exec(self.bin / name, f'#!/bin/sh\necho "machine {name} $*"\n')
        if real_node:
            # the pnpm wrapper reads a manifest with node: give it the machine's real one
            machine_node = shutil.which("node") or "/usr/bin/false"
            write_exec(self.bin / "node", f'#!/bin/sh\nexec {machine_node} "$@"\n')
        # fake pinned pnpm at the place the shim installs it
        self.fake_pnpm = self.toolchain / "pnpm" / "v11.20.0" / "node_modules" / ".bin" / "pnpm"
        write_exec(self.fake_pnpm, FAKE_PNPM)
        self.log = root / "pnpm-calls.log"

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            "PATH": f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(self.root),
            "GC_TOOLCHAIN_DIR": str(self.toolchain),
            "FAKE_PNPM_LOG": str(self.log),
        }
        env.update(extra)
        return env

    def run(self, prog: str, *args: str, cwd: pathlib.Path | None = None, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.shims / prog), *args],
            cwd=str(cwd or self.root),
            env=self.env(**extra),
            capture_output=True,
            text=True,
        )

    def all_calls(self) -> list[str]:
        if not self.log.exists():
            return []
        return [line for line in self.log.read_text(encoding="utf-8").splitlines() if not line.startswith("PATH0=")]

    @staticmethod
    def is_check(call: str) -> bool:
        return call.split("|", 2)[2] in (CHECK, "--ignore-workspace " + CHECK)

    def calls(self) -> list[str]:
        """Every pnpm call except the wrapper's read-only sync questions."""
        return [c for c in self.all_calls() if not self.is_check(c)]

    def argv(self) -> list[str]:
        return [c.split("|", 2)[2] for c in self.calls()]

    def checks(self) -> list[str]:
        return [c for c in self.all_calls() if self.is_check(c)]

    def installs(self) -> list[str]:
        return [c for c in self.calls() if c.split("|", 2)[2] in ("install --frozen-lockfile", "--ignore-workspace install --frozen-lockfile")]

    def reset(self) -> None:
        self.log.unlink(missing_ok=True)

    def project(self, name: str = "proj", lock: str = "lockfileVersion: '9.0'\n") -> pathlib.Path:
        p = self.root / name
        p.mkdir(parents=True)
        (p / "package.json").write_text('{"name":"p","private":true}\n', encoding="utf-8")
        (p / "pnpm-lock.yaml").write_text(lock, encoding="utf-8")
        return p


def in_sync(proj: pathlib.Path) -> bool:
    return (proj / "node_modules" / ".fake-state").exists()


class PnpmShimVerdictTests(unittest.TestCase):
    """Round 10 of the codex gate: a probe failure that is not pnpm's verdict
    is not a reason to install; a package script overrides five built-ins."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(pathlib.Path(self.tmp.name), real_node=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_lane_is_the_workspace_root_even_with_per_package_lockfiles(self) -> None:
        ws = self.fx.root / "ws"
        ws.mkdir()
        (ws / "pnpm-workspace.yaml").write_text("packages:\n  - packages/*\nsharedWorkspaceLockfile: false\n", encoding="utf-8")
        (ws / "package.json").write_text('{"name":"ws","private":true}\n', encoding="utf-8")
        a = self.fx.project("ws/packages/a")
        b = self.fx.project("ws/packages/b")
        lock = ws / "node_modules" / ".gc-lane-deps.lock"
        holder = subprocess.Popen(["sleep", "30"])
        try:
            lock.mkdir(parents=True)
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            # both packages contend for the WORKSPACE lock, not their own lockfile directories
            ra = self.fx.run("pnpm", "install", cwd=a, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
            rb = self.fx.run("pnpm", "exec", "vitest", cwd=b, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
        finally:
            holder.kill()
            holder.wait()
        for r in (ra, rb):
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn(f"has held {lock.resolve()}", r.stderr)
        self.assertFalse((a / "node_modules" / ".gc-lane-deps.lock").exists())
        self.assertFalse((b / "node_modules" / ".gc-lane-deps.lock").exists())

    def test_help_and_version_requests_run_as_is(self) -> None:
        proj = self.fx.project()
        # the last value of the flag decides (round 28): `--no-help --help` asks
        for argv in (["run", "--help"], ["install", "--help"], ["-h", "exec", "vitest"], ["add", "x", "--help"], ["-v"], ["--version", "run", "build"], ["install", "--no-help", "--help"], ["install", "--help=false", "--help"], ["--no-help", "install", "-h"]):
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|{' '.join(argv)}"], argv)
            self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock").exists(), argv)
        # after `exec` pnpm reads no options (measured on 11.20: `pnpm exec -h` is
        # 'Command "-h" not found'), so `-h` there is the bin name: a project command
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "-h", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.fx.checks()), 1)     # asked (the fake's `add` above left the tree in sync)
        self.assertEqual(self.fx.argv(), ["exec -h"])

    def test_audit_fix_and_workspace_root_are_resolved_before_the_lock_and_the_override(self) -> None:
        ws = self.fx.root / "ws"
        ws.mkdir()
        (ws / "pnpm-workspace.yaml").write_text("packages:\n  - packages/*\n", encoding="utf-8")
        (ws / "package.json").write_text('{"name":"ws","private":true}\n', encoding="utf-8")
        (ws / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        member = ws / "packages" / "a"
        member.mkdir(parents=True)
        (member / "package.json").write_text('{"name":"a","scripts":{"clean":"rimraf dist"}}\n', encoding="utf-8")
        lock = ws / "node_modules" / ".gc-lane-deps.lock"
        holder = subprocess.Popen(["sleep", "30"])
        try:
            lock.mkdir(parents=True)
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            # `pnpm -w clean` from a member that defines clean: the ROOT has no such script,
            # so it is the built-in workspace cleanup, under the workspace lock
            r1 = self.fx.run("pnpm", "-w", "clean", cwd=member, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
            r2 = self.fx.run("pnpm", "audit", "--fix", cwd=ws, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
            r3 = self.fx.run("pnpm", "audit", cwd=ws, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
        finally:
            holder.kill()
            holder.wait()
        for r in (r1, r2):
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn(f"has held {lock.resolve()}", r.stderr)
        self.assertEqual(r3.returncode, 0, r3.stderr)  # a plain audit is informational
        self.assertEqual(self.fx.argv(), ["audit"])
        # without -w, the member's own clean script is a project command
        self.fx.reset()
        r = self.fx.run("pnpm", "clean", cwd=member)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.argv()[-1], "clean")
        self.assertGreaterEqual(len(self.fx.checks()), 1)

    def test_a_probe_error_that_is_not_a_verdict_runs_the_command_as_is(self) -> None:
        proj = self.fx.project()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_PROBE_ERROR="1", GC_TOOLCHAIN_LANE_DEPS_WAIT="3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("could not judge the lane", r.stderr)
        self.assertIn("EACCES", r.stderr)
        self.assertEqual(self.fx.argv(), ["exec vitest"])
        self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock").exists())  # asked under the lock, released, nothing installed
        self.assertFalse(in_sync(proj))

    def test_a_file_error_pnpm_reports_under_the_verify_code_is_no_verdict_either(self) -> None:
        """Round 18: pnpm wraps a file error met inside its check (the state
        refresh denied on a read-only lane) in ERR_PNPM_VERIFY_DEPS_BEFORE_RUN
        with the error as the reason; the wrapper warns and runs as is."""
        proj = self.fx.project()
        (proj / "node_modules").mkdir()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_PROBE_WRAPPED_ERROR="1", GC_TOOLCHAIN_LANE_DEPS_WAIT="3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("could not judge the lane", r.stderr)
        self.assertIn("a file error inside its check", r.stderr)
        self.assertIn("EACCES: permission denied", r.stderr)
        self.assertNotIn("installing lane dependencies", r.stderr)
        self.assertEqual(self.fx.argv(), ["exec vitest"])
        self.assertEqual(len(self.fx.checks()), 1)
        self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock").exists())
        self.assertFalse(in_sync(proj))
        # pnpm's own reasons (never a system error code) stay a verdict: the next command installs
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.argv(), ["install --frozen-lockfile", "exec vitest"])

    def test_a_package_script_named_like_a_built_in_is_a_project_command_unless_pm_forces_the_built_in(self) -> None:
        proj = self.fx.project()
        (proj / "package.json").write_text('{"name":"p","private":true,"scripts":{"clean":"rimraf dist","deploy":"echo","setup":"echo","rb":"echo"}}\n', encoding="utf-8")
        for argv in (["clean"], ["deploy"], ["setup", "--flag"], ["rb"]):
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            # a fresh lane: the script's dependencies are installed first, then the script runs
            self.assertEqual(self.fx.argv()[-1], " ".join(argv), argv)
            self.assertGreaterEqual(len(self.fx.checks()), 1, argv)
        self.assertTrue(in_sync(proj))
        # the manifest that decides is the one of the directory pnpm acts on, even when
        # that directory is named after the command: B has no `clean` script, so B's
        # built-in runs under B's lock, not A's script
        other = self.fx.project("other")
        self.fx.run("pnpm", "exec", "vitest", cwd=other)
        self.fx.reset()
        r = self.fx.run("pnpm", "clean", "--dir", "../other", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|clean --dir ../other"])
        self.assertFalse(in_sync(other))
        self.assertTrue(in_sync(proj))
        # `purge` and `rebuild` are not scripts here: still built-ins
        for argv in (["purge"], ["rebuild"], ["pm", "clean"]):
            self.fx.run("pnpm", "exec", "vitest", cwd=proj)
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|{' '.join(argv)}"], argv)
            self.assertFalse(in_sync(proj), argv)
        # an empty script is no script to pnpm (`"clean": ""` runs the built-in "Removing
        # node_modules", measured on 11.20; a blank `"purge": "   "` is one and runs as a
        # script): the built-in under the lock with no question asked; the blank one a
        # project command (round 28)
        (proj / "package.json").write_text('{"name":"p","private":true,"scripts":{"clean":"","purge":"   "}}\n', encoding="utf-8")
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.fx.reset()
        r = self.fx.run("pnpm", "clean", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|clean"])
        self.assertFalse(in_sync(proj))
        self.fx.reset()
        r = self.fx.run("pnpm", "purge", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertGreaterEqual(len(self.fx.checks()), 1)     # asked first: a project command
        self.assertEqual(self.fx.argv()[-1], "purge")


class PnpmShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(pathlib.Path(self.tmp.name), real_node=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pnpm_own_in_command_install_is_off_and_argv_reaches_pnpm(self) -> None:
        proj = self.fx.project()
        r = self.fx.run("pnpm", "exec", "vitest", "run", "--reporter=dot", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        last = self.fx.calls()[-1]
        self.assertEqual(last.split("|", 2)[1], "false")
        self.assertTrue(last.endswith("|exec vitest run --reporter=dot"), last)
        # the sync question is asked with the flag and without the environment value
        self.assertEqual([c.split("|", 2)[1] for c in self.fx.checks()], ["unset"])

    def test_info_commands_run_as_is_and_ask_nothing(self) -> None:
        proj = self.fx.project()
        for argv in (["store", "path"], ["--version"], [], ["config", "get", "x"], ["outdated"], ["-r", "list"], ["with", "current", "list"], ["dlx", "cowsay"]):
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.fx.argv(), [" ".join(argv)], argv)
            self.assertEqual(self.fx.checks(), [], argv)
        self.assertFalse((proj / "node_modules").exists())

    def test_first_project_command_asks_pnpm_installs_once_and_runs(self) -> None:
        proj = self.fx.project()
        r = self.fx.run("pnpm", "exec", "eslint", ".", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("installing lane dependencies once", r.stderr)
        self.assertEqual(self.fx.argv(), ["install --frozen-lockfile", "exec eslint ."])
        self.assertEqual(self.fx.calls()[0], f"{proj.resolve()}|false|install --frozen-lockfile")
        # asked before the lock and again under it, then never during the command
        self.assertEqual(len(self.fx.checks()), 1)     # asked once, under the lane lock (round 20)
        self.assertTrue(in_sync(proj))
        self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock").exists())

    def test_later_commands_ask_once_and_do_not_install(self) -> None:
        proj = self.fx.project()
        self.fx.run("pnpm", "test", cwd=proj)
        for argv in (["exec", "vitest"], ["run", "lint"], ["agreement:pdf", "a.md"], ["vitest", "run"], ["test", "--", "-C", "x"]):
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("installing", r.stderr)
            self.assertEqual(self.fx.argv(), [" ".join(argv)], argv)
            self.assertEqual(len(self.fx.checks()), 1, argv)

    def test_anything_that_makes_pnpm_say_out_of_sync_installs_exactly_once_more(self) -> None:
        proj = self.fx.project()
        (proj / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n\nimporters:\n\n  .:\n    dependencies: {}\n\n  packages/app:\n    dependencies: {}\n", encoding="utf-8")
        app = proj / "packages" / "app"
        app.mkdir(parents=True)
        (app / "package.json").write_text('{"name":"app"}\n', encoding="utf-8")
        self.fx.run("pnpm", "test", cwd=proj)
        self.assertEqual(len(self.fx.installs()), 1)
        edits = (
            (proj / "pnpm-lock.yaml", "lockfileVersion: '9.0'\nchanged: true\n"),
            (proj / "package.json", '{"name":"p","private":true,"dependencies":{"new":"1"}}\n'),
            (app / "package.json", '{"name":"app","dependencies":{"x":"1"}}\n'),
            (proj / "pnpm-workspace.yaml", "packages:\n  - packages/*\n"),
            (proj / ".npmrc", "node-linker=hoisted\n"),
            (proj / "packages" / "new" / "package.json", '{"name":"new"}\n'),  # a workspace member pnpm sees
        )
        for path, text in edits:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.fx.reset()
            r = self.fx.run("pnpm", "test", cwd=proj)
            self.assertEqual(r.returncode, 0, (path, r.stderr))
            self.assertEqual(self.fx.argv(), ["install --frozen-lockfile", "test"], path)
            self.fx.reset()
            self.fx.run("pnpm", "test", cwd=proj)
            self.assertEqual(self.fx.argv(), ["test"], path)
        (proj / "src.ts").write_text("export {}\n", encoding="utf-8")
        self.fx.reset()
        self.fx.run("pnpm", "test", cwd=proj)
        self.assertEqual(self.fx.argv(), ["test"])

    def test_command_from_a_subdirectory_installs_at_the_lockfile_root(self) -> None:
        proj = self.fx.project()
        sub = proj / "server" / "hocuspocus"
        sub.mkdir(parents=True)
        r = self.fx.run("pnpm", "exec", "tsc", cwd=sub)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.installs(), [f"{proj.resolve()}|false|install --frozen-lockfile"])
        self.assertEqual(self.fx.checks()[0].split("|", 1)[0], str(sub.resolve()))
        self.assertTrue(in_sync(proj))
        self.assertFalse((sub / "node_modules").exists())

    def test_no_lockfile_above_means_no_question_and_no_install(self) -> None:
        d = self.fx.root / "plain"
        d.mkdir()
        r = self.fx.run("pnpm", "exec", "node", "-e", "1", cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.all_calls(), [f"{d.resolve()}|false|exec node -e 1"])

    def test_concurrent_callers_wait_for_one_install_instead_of_racing_it(self) -> None:
        proj = self.fx.project()
        results: list[subprocess.CompletedProcess[str]] = []
        lock = threading.Lock()

        def call(name: str) -> None:
            r = self.fx.run("pnpm", "exec", name, cwd=proj, FAKE_PNPM_SLEEP="2")
            with lock:
                results.append(r)

        threads = [threading.Thread(target=call, args=(n,)) for n in ("vitest", "eslint", "tsc")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.fx.installs()), 1, self.fx.calls())
        ran = sorted(a for a in self.fx.argv() if a != "install --frozen-lockfile")
        self.assertEqual(ran, ["exec eslint", "exec tsc", "exec vitest"])
        waited = [r for r in results if "waiting for another caller's lane install" in r.stderr]
        self.assertEqual(len(waited), 2, [r.stderr for r in results])

    def test_failed_install_leaves_the_lane_out_of_sync_and_the_command_does_not_run(self) -> None:
        proj = self.fx.project()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_FAIL_INSTALL="1")
        self.assertEqual(r.returncode, 7, r.stderr)      # pnpm install's own status, as the header says (round 30)
        self.assertIn("lane install failed", r.stderr)
        self.assertIn("exit 7", r.stderr)
        self.assertIn("this command did not run", r.stderr)
        self.assertEqual(self.fx.argv(), ["install --frozen-lockfile"])
        self.assertFalse(in_sync(proj))
        self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock").exists())
        # the next caller asks pnpm again and installs, rather than trusting a half tree
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.fx.installs()), 2)

    def test_stale_lock_with_a_dead_owner_is_moved_aside_never_deleted(self) -> None:
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("moved aside a stale lane install lock", r.stderr)
        self.assertEqual(len(self.fx.installs()), 1)
        aside = [p for p in (proj / "node_modules").iterdir() if p.name.startswith(".gc-lane-deps.lock.stale-")]
        self.assertEqual(len(aside), 1, aside)
        self.assertEqual((aside[0] / "pid").read_text(encoding="utf-8").strip(), str(dead.pid))
        self.assertFalse(lock.exists())

    def test_ownerless_lock_older_than_two_minutes_is_moved_aside(self) -> None:
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        lock.mkdir(parents=True)
        old = time.time() - 180
        os.utime(lock, (old, old))
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stale lane install lock (owner pid none)", r.stderr)

    def test_live_lock_is_waited_for_then_fails_closed_naming_the_holder(self) -> None:
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        lock.mkdir(parents=True)
        holder = subprocess.Popen(["sleep", "30"])
        try:
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"another lane install (pid {holder.pid}) has held", r.stderr)
        self.assertIn("this command did not run", r.stderr)
        self.assertEqual(self.fx.calls(), [])
        self.assertTrue(lock.exists())

    def test_a_caller_whose_lane_is_in_sync_holds_the_lock_for_the_question_only_and_never_waits(self) -> None:
        """The question is asked under the lane lock (its pid file names this
        wrapper while pnpm answers, recorded by the fake), the lock is released
        before the command runs, and an in-sync lane with no holder costs no
        wait. (Until round 19 this row ran the in-sync caller past a LIVE
        holder; a mutate in flight reads as in sync to pnpm, so a live lock is
        waited for: test_a_project_command_waits_behind_a_live_lock_even_when_pnpm_says_in_sync.
        Renamed in round 30: it never said what it tested.)"""
        proj = self.fx.project()
        self.fx.run("pnpm", "test", cwd=proj)
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        probe = self.fx.root / "lock-owner-during-the-question"
        self.fx.reset()
        proc = subprocess.Popen(
            [str(self.fx.shims / "pnpm"), "exec", "vitest"], cwd=str(proj),
            env=self.fx.env(GC_TOOLCHAIN_LANE_DEPS_WAIT="5", FAKE_PNPM_LOCK_PROBE=str(probe)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(probe.read_text(encoding="utf-8").strip(), str(proc.pid))     # held by this wrapper while pnpm answered
        self.assertEqual(self.fx.argv(), ["exec vitest"])
        self.assertEqual(len(self.fx.checks()), 1)
        self.assertNotIn("waiting", err)
        self.assertFalse(lock.exists())
        self.assertFalse([p for p in (proj / "node_modules").iterdir() if p.name.startswith(".gc-lane-deps.lock")])

    def test_lane_deps_can_be_switched_off_by_environment_or_sidecar(self) -> None:
        proj = self.fx.project()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, GC_TOOLCHAIN_LANE_DEPS="off")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|exec vitest"])
        (self.fx.shims / "toolchain.env").write_text("LANE_DEPS=off\n", encoding="utf-8")
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|exec vitest"])
        # environment wins over the sidecar
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, GC_TOOLCHAIN_LANE_DEPS="on")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.fx.installs()), 1)

    def test_sidecar_values_are_read_as_text_never_evaluated(self) -> None:
        proj = self.fx.project()
        canary = self.fx.root / "canary"
        (self.fx.shims / "toolchain.env").write_text(
            f"LANE_DEPS_WAIT=$(touch {canary})\nLANE_DEPS=`touch {canary}`\n", encoding="utf-8"
        )
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(canary.exists())
        self.assertEqual(len(self.fx.installs()), 1)  # a non-"off" LANE_DEPS value keeps the lane path on

    def test_shim_directory_is_first_on_the_path_pnpm_runs_with(self) -> None:
        proj = self.fx.project()
        self.fx.run("pnpm", "--version", cwd=proj)
        path0 = [l for l in self.fx.log.read_text(encoding="utf-8").splitlines() if l.startswith("PATH0=")]
        self.assertEqual(path0, [f"PATH0={self.fx.shims.resolve()}"])

    def test_pnpm_install_is_keyed_by_version(self) -> None:
        proj = self.fx.project()
        other = self.fx.toolchain / "pnpm" / "v9.9.9" / "node_modules" / ".bin" / "pnpm"
        write_exec(other, '#!/bin/sh\necho "fake pnpm 9.9.9 $*"\n')
        r = self.fx.run("pnpm", "--version", cwd=proj, GC_TOOLCHAIN_PNPM_VERSION="9.9.9")
        self.assertEqual(r.stdout, "fake pnpm 9.9.9 --version\n", r.stderr)
        (self.fx.shims / "toolchain.env").write_text("PNPM_VERSION=9.9.9\n", encoding="utf-8")
        r = self.fx.run("pnpm", "--version", cwd=proj)
        self.assertEqual(r.stdout, "fake pnpm 9.9.9 --version\n", r.stderr)
        r = self.fx.run("pnpm", "--version", cwd=proj, GC_TOOLCHAIN_PNPM_VERSION="11.20.0")
        self.assertEqual(r.stdout, "fake pnpm ran: --version\n", r.stderr)


class PnpmShimMutationTests(unittest.TestCase):
    """Explicit dependency commands: where they run, what they hold, what
    pnpm says afterwards."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(pathlib.Path(self.tmp.name), real_node=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_explicit_dependency_commands_run_in_place_under_the_lock_and_pnpm_judges_the_result(self) -> None:
        proj = self.fx.project()
        pkg = proj / "packages" / "app"
        pkg.mkdir(parents=True)
        for argv, cwd in (
            (["install"], proj),
            (["add", "-D", "x"], pkg),          # a workspace package stays that package
            (["--filter", "app", "install"], proj),
            (["-C", "packages/app", "add", "y"], proj),
            (["add", "--dir", "packages/app", "z"], proj),
            (["--prefix=packages/app", "install"], proj),
            (["with", "current", "install"], proj),
        ):
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=cwd)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            # the explicit command itself, in the caller's directory, never a frozen install before it
            self.assertEqual(self.fx.all_calls(), [f"{cwd.resolve()}|false|{' '.join(argv)}"], argv)
            self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock").exists())
            self.assertFalse((pkg / "node_modules").exists(), argv)
        # a successful explicit install leaves pnpm saying in sync: the next check runs as is
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=pkg)
        self.assertEqual(self.fx.argv(), ["exec vitest"])
        # an install that certifies nothing (`--lockfile-only` after a manifest edit moves the
        # lockfile, not the tree) makes the next project command install
        (proj / "package.json").write_text('{"name":"p","private":true,"dependencies":{"new":"1"}}\n', encoding="utf-8")
        self.fx.reset()
        r = self.fx.run("pnpm", "install", "--lockfile-only", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=pkg)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.calls(), [f"{proj.resolve()}|false|install --frozen-lockfile", f"{pkg.resolve()}|false|exec vitest"])

    def test_every_built_in_that_can_change_node_modules_holds_the_lock_and_pnpm_notices_afterwards(self) -> None:
        proj = self.fx.project()
        for argv in (["clean"], ["purge"], ["pm", "clean"], ["with", "current", "clean"], ["recursive", "prune"], ["-r", "rebuild"], ["m", "dedupe"], ["remove", "x"], ["--reporter=silent", "purge"]):
            self.fx.run("pnpm", "exec", "vitest", cwd=proj)
            self.assertTrue(in_sync(proj))
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|{' '.join(argv)}"], argv)
            self.assertFalse(in_sync(proj), argv)
            self.fx.reset()
            self.fx.run("pnpm", "exec", "vitest", cwd=proj)
            self.assertEqual(self.fx.argv(), ["install --frozen-lockfile", "exec vitest"], argv)

    def test_failed_explicit_install_after_a_lockfile_switch_reinstalls_on_the_way_back(self) -> None:
        proj = self.fx.project()
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        lock_a = (proj / "pnpm-lock.yaml").read_text(encoding="utf-8")
        (proj / "pnpm-lock.yaml").write_text(lock_a + "b: true\n", encoding="utf-8")
        r = self.fx.run("pnpm", "install", cwd=proj, FAKE_PNPM_FAIL_INSTALL="1")
        self.assertEqual(r.returncode, 7)  # pnpm's own status, passed through
        self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock").exists())
        (proj / "pnpm-lock.yaml").write_text(lock_a, encoding="utf-8")
        # the tree still matches lockfile A here; pnpm decides, and it says in sync
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.argv(), ["exec vitest"])

    def test_explicit_install_waits_behind_a_live_lock_and_project_commands_wait_behind_an_explicit_install(self) -> None:
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        lock.mkdir(parents=True)
        holder = subprocess.Popen(["sleep", "30"])
        try:
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            r = self.fx.run("pnpm", "add", "x", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"another lane install (pid {holder.pid}) has held", r.stderr)
        self.assertEqual(self.fx.calls(), [])
        (lock / "pid").unlink()
        lock.rmdir()
        results: list[subprocess.CompletedProcess[str]] = []
        guard = threading.Lock()

        def call(argv: list[str], sleep: str) -> None:
            r = self.fx.run("pnpm", *argv, cwd=proj, FAKE_PNPM_SLEEP=sleep)
            with guard:
                results.append(r)

        t1 = threading.Thread(target=call, args=(["install"], "2"))
        t2 = threading.Thread(target=call, args=(["exec", "vitest"], "0"))
        t1.start()
        time.sleep(0.5)
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)
        for r in results:
            self.assertEqual(r.returncode, 0, r.stderr)
        # the explicit install finished first and left the lane in sync: no frozen install followed
        self.assertEqual(self.fx.argv(), ["install", "exec vitest"])

    def test_first_install_in_a_directory_without_a_lockfile_makes_that_directory_the_lane(self) -> None:
        d = self.fx.root / "fresh"
        d.mkdir()
        (d / "package.json").write_text('{"name":"f","private":true}\n', encoding="utf-8")
        r = self.fx.run("pnpm", "install", cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((d / "pnpm-lock.yaml").exists())
        self.assertFalse((d / "node_modules" / ".gc-lane-deps.lock").exists())
        self.fx.reset()
        r = self.fx.run("pnpm", "test", cwd=d)
        self.assertEqual(self.fx.argv(), ["test"])


class PnpmShimGateRoundTests(unittest.TestCase):
    """Rows for the codex gate rounds 1 to 8 that are not covered above."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(pathlib.Path(self.tmp.name), real_node=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_lifecycle_script_that_reenters_the_wrapper_during_the_install_does_not_deadlock(self) -> None:
        proj = self.fx.project()
        r = self.fx.run(
            "pnpm", "exec", "vitest", cwd=proj,
            FAKE_PNPM_HOOK=str(self.fx.shims / "pnpm"), GC_TOOLCHAIN_LANE_DEPS_WAIT="8",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("waiting for another caller", r.stderr)
        self.assertEqual(self.fx.argv(), ["install --frozen-lockfile", "run build", "exec vitest"])
        # the descendant asked pnpm nothing: the parent holds the lane
        self.assertEqual(len(self.fx.checks()), 1)     # asked once, under the lane lock (round 20)
        # the bypass is scoped to that lane: a sibling project still gets its own install
        other = self.fx.project("other")
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=other, GC_TOOLCHAIN_LANE_DEPS_INSTALLING=str(proj.resolve()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.argv(), ["install --frozen-lockfile", "exec vitest"])

    def test_two_waiters_seeing_one_dead_owner_clear_it_once_and_never_move_a_live_lock(self) -> None:
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        results: list[subprocess.CompletedProcess[str]] = []
        guard = threading.Lock()

        def call(name: str) -> None:
            r = self.fx.run(
                "pnpm", "exec", name, cwd=proj,
                FAKE_PNPM_SLEEP="3", GC_TOOLCHAIN_TEST_PAUSE_BEFORE_RECLAIM="1",
            )
            with guard:
                results.append(r)

        threads = [threading.Thread(target=call, args=(n,)) for n in ("vitest", "eslint")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.fx.installs()), 1, self.fx.calls())
        aside = [p for p in (proj / "node_modules").iterdir() if p.name.startswith(".gc-lane-deps.lock.stale-")]
        self.assertEqual(len(aside), 1, aside)
        self.assertEqual((aside[0] / "pid").read_text(encoding="utf-8").strip(), str(dead.pid))
        self.assertFalse(lock.exists())
        self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock.reclaim").exists())

    def test_reclaim_reread_finds_the_lock_live_again_and_moves_nothing(self) -> None:
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        holder = subprocess.Popen(["sleep", "30"])
        try:
            proc = subprocess.Popen(
                [str(self.fx.shims / "pnpm"), "exec", "vitest"], cwd=str(proj),
                env=self.fx.env(GC_TOOLCHAIN_TEST_PAUSE_IN_RECLAIM="2", GC_TOOLCHAIN_LANE_DEPS_WAIT="4"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            time.sleep(1)
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            out, err = proc.communicate(timeout=60)
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(proc.returncode, 1, err)
        self.assertNotIn("moved aside", err)
        self.assertIn(f"another lane install (pid {holder.pid}) has held", err)
        self.assertTrue(lock.exists())
        self.assertEqual((lock / "pid").read_text(encoding="utf-8").strip(), str(holder.pid))

    def test_stuck_reclaim_lock_fails_closed_when_old(self) -> None:
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        reclaim = proj / "node_modules" / ".gc-lane-deps.lock.reclaim"
        reclaim.mkdir()
        old = time.time() - 180
        os.utime(reclaim, (old, old))
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="3")
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale reclaim lock", r.stderr)
        self.assertEqual(self.fx.calls(), [])
        self.assertTrue(lock.exists())

    def test_a_lock_that_changed_hands_between_the_read_and_the_check_is_never_moved(self) -> None:
        """Round 30: the reclaim re-check read owner A, A was dead by the
        liveness check, and the directory by then was C's fresh live lock (A
        released and exited, C acquired): the rename moved C's lock and the
        reclaimer ran beside C. The lock is re-read under the reclaim lock
        right before the rename and moved only when it still names the owner
        that was judged; here it names C, so nothing moves and the caller
        waits for C and fails closed naming C."""
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        holder = subprocess.Popen(["sleep", "60"])
        try:
            proc = subprocess.Popen(
                [str(self.fx.shims / "pnpm"), "add", "x"], cwd=str(proj),
                env=self.fx.env(GC_TOOLCHAIN_TEST_PAUSE_AFTER_OWNER_READ="2", GC_TOOLCHAIN_LANE_DEPS_WAIT="1"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            time.sleep(3)       # inside the re-check: A read, not yet judged; the lock changes hands now
            (lock / "pid").unlink()
            lock.rmdir()
            lock.mkdir()
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            out, err = proc.communicate(timeout=60)
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(proc.returncode, 1, err)
        self.assertNotIn("moved aside", err)
        self.assertIn(f"another lane install (pid {holder.pid}) has held", err)
        self.assertTrue(lock.exists())
        self.assertEqual((lock / "pid").read_text(encoding="utf-8").strip(), str(holder.pid))
        self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock.reclaim").exists())
        self.assertEqual([p.name for p in (proj / "node_modules").iterdir() if p.name.startswith(".gc-lane-deps.lock.stale")], [])
        self.assertEqual(self.fx.calls(), [])

    @unittest.skipUnless(platform.system() == "Darwin", "an inherited deny-add_file ACL (chmod +a) is how the pid write fails while the lock mkdir succeeds")
    def test_a_pid_that_cannot_be_written_leaves_no_lock_and_fails_closed(self) -> None:
        """Round 30: the pid write's status was ignored, so a lock nobody owned
        stood while the mutation ran, cleanup refused it and a reclaimer moved
        it aside under the mutation. Now the directory just made goes and the
        command fails closed naming the file."""
        proj = self.fx.project()
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        nm = proj / "node_modules"
        ace = f"{getpass.getuser()} deny add_file,directory_inherit"
        subprocess.run(["chmod", "+a", ace, str(nm)], check=True)
        try:
            self.fx.reset()
            r = self.fx.run("pnpm", "add", "x", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("cannot write", r.stderr)
            self.assertIn(".gc-lane-deps.lock/pid", r.stderr)
            self.assertIn("this command did not run", r.stderr)
            self.assertNotIn("waiting", r.stderr)
            self.assertEqual(self.fx.all_calls(), [])
            self.assertFalse((nm / ".gc-lane-deps.lock").exists())       # the directory it made is gone
        finally:
            subprocess.run(["chmod", "-a", ace, str(nm)], check=False)

    def test_a_trapped_signal_releases_the_reclaim_lock_with_the_lane_lock(self) -> None:
        """Round 30: HUP/INT/TERM after the reclaim directory was made and
        before the rename ran a cleanup that released only the lane lock; the
        stale lock and the abandoned reclaim directory then blocked every
        caller. The trap releases this wrapper's reclaim lock too."""
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        reclaim = proj / "node_modules" / ".gc-lane-deps.lock.reclaim"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        proc = subprocess.Popen(
            [str(self.fx.shims / "pnpm"), "add", "x"], cwd=str(proj),
            env=self.fx.env(GC_TOOLCHAIN_TEST_PAUSE_IN_RECLAIM="3"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        time.sleep(1.5)     # inside the reclaim: its lock is held, nothing moved yet
        self.assertTrue(reclaim.exists())
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 143, err)
        self.assertFalse(reclaim.exists())          # released by the trap, after the pause ended
        self.assertTrue(lock.exists())              # the stale lock was not moved: the trap came first
        self.assertEqual(self.fx.calls(), [])
        # the next caller reclaims the stale lock and runs
        r = self.fx.run("pnpm", "add", "x", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("moved aside a stale lane install lock", r.stderr)
        self.assertEqual(self.fx.argv(), ["add x"])

    def test_a_signal_during_the_release_is_lost_and_nothing_is_left_standing(self) -> None:
        """Round 31: the mark that says "no longer mine" was cleared before
        the rmdir, so a trapped signal between the two made cleanup skip the
        removal and left the gate (or the lock) standing for every later
        caller. The release runs with HUP/INT/TERM held: a TERM sent inside
        it is lost, the command ends on its own status, nothing stands.
        Twice: inside the gate's release after a reclaim, and inside the
        lock's release after a mutate."""
        proj = self.fx.project()
        nm = proj / "node_modules"
        lock = nm / ".gc-lane-deps.lock"
        reclaim = nm / ".gc-lane-deps.lock.reclaim"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        # the reclaim's gate release is the first pause (~0 s in), the lock's the last
        proc = subprocess.Popen(
            [str(self.fx.shims / "pnpm"), "add", "x"], cwd=str(proj),
            env=self.fx.env(GC_TOOLCHAIN_TEST_PAUSE_IN_RELEASE="2"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        time.sleep(1)
        self.assertTrue(reclaim.exists())           # inside the gate's release, holding it
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)   # the signal was lost, the mutate ran to its end
        self.assertIn("moved aside a stale lane install lock", err)
        self.assertEqual(self.fx.argv(), ["add x"])
        self.assertFalse(reclaim.exists())
        self.assertFalse(lock.exists())
        self.fx.reset()
        proc = subprocess.Popen(
            [str(self.fx.shims / "pnpm"), "add", "y"], cwd=str(proj),
            env=self.fx.env(GC_TOOLCHAIN_TEST_PAUSE_IN_RELEASE="2", FAKE_PNPM_SLEEP="1"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        time.sleep(4)       # gate release (2 s) + pnpm (1 s): inside the lock's release now
        self.assertTrue(lock.exists())
        self.assertEqual((lock / "pid").read_text(encoding="utf-8").strip(), str(proc.pid))
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(self.fx.argv(), ["add y"])
        self.assertFalse(lock.exists())
        self.assertFalse(reclaim.exists())
        self.assertEqual([p.name for p in nm.iterdir() if p.name.startswith(".gc-lane-deps.lock.")], [p.name for p in nm.iterdir() if p.name.startswith(".gc-lane-deps.lock.stale-")])

    def test_ignore_workspace_makes_the_standalone_project_the_lane_for_probe_lock_and_install(self) -> None:
        """Round 15: a standalone fixture project inside a workspace, run with
        --ignore-workspace, is probed, locked and installed as itself; without
        the flag the same directory belongs to the workspace above it."""
        ws = self.fx.root / "ws"
        ws.mkdir()
        (ws / "pnpm-workspace.yaml").write_text("packages:\n  - packages/*\n", encoding="utf-8")
        (ws / "package.json").write_text('{"name":"ws","private":true}\n', encoding="utf-8")
        (ws / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        fixture = self.fx.project("ws/fixtures/standalone")
        r = self.fx.run("pnpm", "--ignore-workspace", "exec", "vitest", cwd=fixture)
        self.assertEqual(r.returncode, 0, r.stderr)
        # every question and the one install carry the flag and run in the fixture
        self.assertEqual(
            self.fx.checks(),
            [f"{fixture.resolve()}|unset|--ignore-workspace {CHECK}"],
        )
        self.assertEqual(self.fx.calls(), [
            f"{fixture.resolve()}|false|--ignore-workspace install --frozen-lockfile",
            f"{fixture.resolve()}|false|--ignore-workspace exec vitest",
        ])
        self.assertTrue(in_sync(fixture))
        self.assertFalse((ws / "node_modules").exists())  # the workspace was neither locked nor installed
        self.assertFalse((fixture / "node_modules" / ".gc-lane-deps.lock").exists())
        # the prepared project stays prepared: one question, no install
        self.fx.reset()
        r = self.fx.run("pnpm", "--ignore-workspace", "run", "test", cwd=fixture)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.fx.checks()), 1)
        self.assertEqual(self.fx.argv(), ["--ignore-workspace run test"])
        # without the flag the lane is the workspace root: the install lands there
        other = self.fx.project("ws/fixtures/other")
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=other)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.installs(), [f"{ws.resolve()}|false|install --frozen-lockfile"])
        self.assertFalse(in_sync(other))
        # a mutate with the flag holds the fixture's own lock, never the workspace's:
        # a live holder on the workspace lock does not stop it, one on the fixture does
        ws_lock = ws / "node_modules" / ".gc-lane-deps.lock"
        fx_lock = fixture / "node_modules" / ".gc-lane-deps.lock"
        holder = subprocess.Popen(["sleep", "30"])
        try:
            ws_lock.mkdir(parents=True)
            (ws_lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            self.fx.reset()
            r1 = self.fx.run("pnpm", "--ignore-workspace", "add", "left-pad", cwd=fixture, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
            fx_lock.mkdir(parents=True)
            (fx_lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            r2 = self.fx.run("pnpm", "--ignore-workspace", "add", "left-pad", cwd=fixture, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
            r3 = self.fx.run("pnpm", "--ignore-workspace", "exec", "vitest", cwd=fixture, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.assertEqual(r2.returncode, 1, r2.stderr)
        self.assertIn(f"has held {fx_lock.resolve()}", r2.stderr)
        self.assertEqual(r3.returncode, 1, r3.stderr)  # prepared, but a live lock is waited for first (round 19)
        self.assertIn(f"has held {fx_lock.resolve()}", r3.stderr)
        self.assertEqual(self.fx.argv(), ["--ignore-workspace add left-pad"])
        # every spelling pnpm 11.20 honours (measured: the flag, =true, a literal true after
        # it; =false, a literal false and --no-ignore-workspace undo it; the last one wins;
        # after `run` as well), and -w moves nothing under the flag (pnpm refuses it outside
        # a workspace)
        for n, argv in enumerate((
            ["--ignore-workspace=true", "exec", "vitest"],
            ["--ignore-workspace", "true", "exec", "vitest"],
            ["run", "--ignore-workspace", "test"],
            ["--ignore-workspace", "-w", "exec", "vitest"],
            ["-w", "--ignore-workspace", "exec", "vitest"],
            ["--ignore-workspace=false", "--ignore-workspace", "exec", "vitest"],
            ["--no-ignore-workspace", "--ignore-workspace", "exec", "vitest"],
        )):
            proj = self.fx.project(f"ws/fixtures/f{n}")
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.installs(), [f"{proj.resolve()}|false|--ignore-workspace install --frozen-lockfile"], argv)
            self.assertTrue(in_sync(proj), argv)
            self.assertEqual(self.fx.argv()[-1], " ".join(argv), argv)
        # the forms pnpm does not read (measured) select nothing here either
        for argv in (
            ["--ignore-workspace", "false", "exec", "vitest"],
            ["--ignore-workspace", "--no-ignore-workspace", "exec", "vitest"],
            ["--ignore-workspace", "--ignore-workspace=false", "exec", "vitest"],
            ["--config.ignore-workspace=true", "exec", "vitest"],
        ):
            proj = self.fx.project(f"ws/fixtures/g{len(argv)}{argv[1][:4]}")
            (ws / "node_modules" / ".fake-state").unlink(missing_ok=True)
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.installs(), [f"{ws.resolve()}|false|install --frozen-lockfile"], argv)
            self.assertFalse(in_sync(proj), argv)
        # a standalone directory with no lockfile of its own is no lane: the command runs as is
        bare = ws / "fixtures" / "bare"
        bare.mkdir()
        (bare / "package.json").write_text('{"name":"bare"}\n', encoding="utf-8")
        self.fx.reset()
        r = self.fx.run("pnpm", "--ignore-workspace", "exec", "vitest", cwd=bare)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.all_calls(), [f"{bare.resolve()}|false|--ignore-workspace exec vitest"])

    def test_option_values_are_read_by_pnpm_own_table_so_an_install_behind_them_is_a_mutate(self) -> None:
        """Round 16: `--child-concurrency 1 install`, `--recursive false
        install` and their kin are installs (pnpm's exploratory parse
        swallows the value, a boolean swallows a literal true/false), so
        they hold the lane lock and never run the frozen install first."""
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        holder = subprocess.Popen(["sleep", "60"])
        try:
            lock.mkdir(parents=True)
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            mutates = (
                ["--child-concurrency", "1", "install"],
                ["--recursive", "false", "install"],
                ["-r", "false", "install"],
                ["--frozen-lockfile", "false", "install"],
                ["--use-stderr", "false", "install"],
                ["--color", "auto", "install"],
                ["--link-workspace-packages", "deep", "install"],
                ["--network-concurrency", "4", "add", "x"],
                ["--loglevel", "warn", "install"],
                ["--reporter", "append-only", "install"],
                ["-s", "install"],                       # -s is --reporter=silent: no value
                ["-rw", "install"],                      # a run of one-letter shorthands
                ["--child-conc", "1", "install"],        # a unique prefix of an option name
                ["--no-frozen-lockfile", "install"],
                ["--no-frozen-lockfile", "true", "install"],
                ["--", "install"],                       # `--` ends the options; the command follows
                ["--filter", "--dir", str(proj), "install"],   # a string option never swallows an option-like token
                ["--store-dir", "--", "install"],        # nor a lone `--`
                ["--child-concurrency", "--", "install"],
                ["--dir", str(proj), "install"],
            )
            for argv in mutates:
                self.fx.reset()
                r = self.fx.run("pnpm", *argv, cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="1")
                self.assertEqual(r.returncode, 1, (argv, r.stderr))
                self.assertIn(f"has held {lock.resolve()}", r.stderr, argv)
                self.assertEqual(self.fx.all_calls(), [], argv)
            # the same values in front of a project command wait for the lock too (a live
            # lock is waited for before pnpm is even asked, round 19)
            for argv in (["--child-concurrency", "1", "exec", "vitest"], ["--recursive", "false", "run", "test"], ["-r", "false", "test"]):
                self.fx.reset()
                r = self.fx.run("pnpm", *argv, cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="1")
                self.assertEqual(r.returncode, 1, (argv, r.stderr))
                self.assertEqual(self.fx.all_calls(), [], argv)
            # `--recursive=maybe install`: nopt leaves `maybe` positional, so pnpm's command is
            # `maybe` (a script name), never install: no lock, pnpm's own error
            self.fx.reset()
            r = self.fx.run("pnpm", "--recursive=maybe", "install", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="1")
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertEqual(self.fx.argv(), [])   # project: asked pnpm, stale, waited for the lock
        finally:
            holder.kill()
            holder.wait()
        # without a holder the install runs where typed, arguments unchanged, once
        self.fx.reset()
        r = self.fx.run("pnpm", "--child-concurrency", "1", "install", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|--child-concurrency 1 install"])
        self.assertFalse(lock.exists())
        # `run`'s own options up to the script name: --resume-from and --workspace-concurrency
        # take a value there, so the script is the token after; help anywhere before it is info
        self.fx.reset()
        r = self.fx.run("pnpm", "run", "--resume-from", "pkg", "--workspace-concurrency", "2", "--dir", str(proj), "build", cwd=self.fx.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.checks()[0].split("|", 1)[0], str(proj.resolve()))
        # after `exec` pnpm reads no options: `exec -C x vitest` runs the bin `-C`, so the
        # target is the working directory, never x
        other = self.fx.project("other")
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "--dir", str(other), "vitest", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.checks()[0].split("|", 1)[0], str(proj.resolve()))
        self.assertFalse((other / "node_modules").exists())
        # an abbreviated global option and a shorthand prefix are read as pnpm reads them
        ws = self.fx.root / "ws"
        ws.mkdir()
        (ws / "pnpm-workspace.yaml").write_text("packages:\n  - packages/*\n", encoding="utf-8")
        (ws / "package.json").write_text('{"name":"ws","private":true}\n', encoding="utf-8")
        (ws / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        fixture = self.fx.project("ws/fixtures/standalone")
        self.fx.reset()
        r = self.fx.run("pnpm", "--ignore-w", "--verb", "exec", "vitest", cwd=fixture)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.installs(), [f"{fixture.resolve()}|false|--ignore-workspace install --frozen-lockfile"])
        self.assertEqual(self.fx.argv()[-1], "--ignore-w --verb exec vitest")

    def test_dir_wins_over_prefix_wherever_it_stands_and_a_refused_lock_fails_at_once(self) -> None:
        """Round 17: pnpm acts in --dir (-C) whatever its place beside --prefix
        (measured on 11.20), so that is the lane the wrapper prepares and locks;
        a lock mkdir that node_modules refuses is a permission failure, not a
        holder to wait ten minutes for."""
        a = self.fx.project("a")
        b = self.fx.project("b")
        for argv in (
            ["--dir", "a", "--prefix", "b", "exec", "vitest"], ["--prefix", "b", "--dir", "a", "exec", "vitest"],
            ["-C", "a", "--prefix", "b", "run", "test"], ["--prefix", "b", "-C=a", "test"],
            ["--prefix", "b", "--dir", "b", "--dir", "a", "exec", "vitest"],
            ["--config.dir=a", "--prefix", "b", "exec", "vitest"], ["--dir", "b", "--config.dir=a", "exec", "vitest"],
            ["--config.dir=b", "--dir", "a", "exec", "vitest"], ["--config.prefix=b", "--dir", "a", "exec", "vitest"],
        ):   # (`--config.dir=` is `--dir` for pnpm, last wins among them; `--config.prefix=` is not read: measured)
            (a / "node_modules" / ".fake-state").unlink(missing_ok=True)
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=self.fx.root)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.installs(), [f"{a.resolve()}|false|install --frozen-lockfile"], argv)
            self.assertEqual(self.fx.checks()[0].split("|", 1)[0], str(a.resolve()), argv)
            self.assertFalse((b / "node_modules").exists(), argv)
        # --prefix alone still selects; the last of two --prefix wins
        self.fx.reset()
        r = self.fx.run("pnpm", "--prefix", "a", "--prefix", "b", "exec", "vitest", cwd=self.fx.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.installs(), [f"{b.resolve()}|false|install --frozen-lockfile"])
        # a mutate holds the --dir project's lock, not the --prefix one's
        lock_a = a / "node_modules" / ".gc-lane-deps.lock"
        holder = subprocess.Popen(["sleep", "30"])
        try:
            lock_a.mkdir(parents=True)
            (lock_a / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            r = self.fx.run("pnpm", "--prefix", "b", "--dir", "a", "add", "x", cwd=self.fx.root, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
            r2 = self.fx.run("pnpm", "--ignore-workspace", "--config.dir=a", "install", cwd=self.fx.root, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn(f"has held {lock_a.resolve()}", r.stderr)
        self.assertEqual(r2.returncode, 1, r2.stderr)
        self.assertIn(f"has held {lock_a.resolve()}", r2.stderr)
        # node_modules that refuses the lock: the command fails at once, naming the refusal,
        # never waiting LANE_DEPS_WAIT for a holder that does not exist
        c = self.fx.project("c")
        (c / "node_modules").mkdir()
        (c / "node_modules").chmod(0o555)
        self.fx.reset()
        try:
            started = time.monotonic()
            r = self.fx.run("pnpm", "exec", "vitest", cwd=c)
            elapsed = time.monotonic() - started
        finally:
            (c / "node_modules").chmod(0o755)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("cannot create", r.stderr)
        self.assertIn("Permission denied", r.stderr)
        self.assertNotIn("waiting for another caller", r.stderr)
        self.assertLess(elapsed, 20)
        self.assertEqual(self.fx.argv(), [])

    def test_a_project_command_waits_behind_a_live_lock_even_when_pnpm_says_in_sync(self) -> None:
        """Round 19: a mutate in flight (a slow rebuild) leaves pnpm's answer
        yes while the tree is half built, so the live lock is waited for
        before the fast path; a disabled help flag is not a help request."""
        proj = self.fx.project()
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)   # prepared: pnpm says yes from here on
        self.assertTrue(in_sync(proj))
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        holder = subprocess.Popen(["sleep", "60"])
        try:
            lock.mkdir()
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            self.fx.reset()
            r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn(f"another lane install (pid {holder.pid}) has held", r.stderr)
            self.assertEqual(self.fx.all_calls(), [])     # not even asked: the holder comes first
            # a help flag whose last value is off (--no-help, --help=false, -h false, and
            # --help --no-help, round 28) is no help request: installs, under the lock
            for argv in (["--no-help", "install"], ["install", "--help=false"], ["-h", "false", "install"], ["--version=false", "add", "x"], ["install", "--help", "--no-help"], ["--help", "--no-help", "install"], ["-h", "install", "--help=false"]):
                self.fx.reset()
                r = self.fx.run("pnpm", *argv, cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="1")
                self.assertEqual(r.returncode, 1, (argv, r.stderr))
                self.assertIn("has held", r.stderr, argv)
                self.assertEqual(self.fx.all_calls(), [], argv)
        finally:
            holder.kill()
            holder.wait()
        # the holder gone (its lock now stale): the command asks pnpm once and runs
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("moved aside a stale lane install lock", r.stderr)
        self.assertEqual(self.fx.argv(), ["exec vitest"])
        # a concurrent mutate: the project command runs only after it released the lane
        self.fx.reset()
        results: dict[str, subprocess.CompletedProcess[str]] = {}

        def mutate() -> None:
            results["add"] = self.fx.run("pnpm", "add", "left-pad", cwd=proj, FAKE_PNPM_SLEEP="3")

        def check() -> None:
            time.sleep(1)
            results["exec"] = self.fx.run("pnpm", "exec", "vitest", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="20")

        threads = [threading.Thread(target=mutate), threading.Thread(target=check)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=60)
        self.assertEqual(results["add"].returncode, 0, results["add"].stderr)
        self.assertEqual(results["exec"].returncode, 0, results["exec"].stderr)
        self.assertIn("waiting for another caller's lane install", results["exec"].stderr)
        self.assertEqual(self.fx.argv(), ["add left-pad", "exec vitest"])

    def test_a_lock_taken_over_by_another_pid_is_not_released_by_the_first(self) -> None:
        proj = self.fx.project()
        holder = subprocess.Popen(["sleep", "30"])
        try:
            r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_TAKEOVER_PID=str(holder.pid))
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(r.returncode, 0, r.stderr)
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        self.assertTrue(lock.exists())
        self.assertEqual((lock / "pid").read_text(encoding="utf-8").strip(), str(holder.pid))

    def test_option_values_and_prefixes_never_stand_in_for_the_subcommand(self) -> None:
        proj = self.fx.project()
        for argv in (
            ["--filter", "app", "install"], ["-F", "app", "add", "x"], ["--filter=app", "install"],
            ["--loglevel", "warn", "--reporter", "silent", "install", "--frozen-lockfile"],
            ["-r", "--filter", "app", "outdated"], ["with", "current", "list"],
        ):
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.argv(), [" ".join(argv)], argv)
            self.assertEqual(self.fx.checks(), [], argv)
        for argv in (["--filter", "app", "run", "test"], ["--loglevel", "warn", "vitest", "run"], ["with", "current", "exec", "vitest"]):
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.argv()[-1], " ".join(argv), argv)
            self.assertGreaterEqual(len(self.fx.checks()), 1, argv)

    def test_directory_options_anywhere_in_pnpm_option_scope_select_the_lane(self) -> None:
        parent = self.fx.root / "parent"
        parent.mkdir()
        front = self.fx.project("parent/frontend")
        # a project command from a directory without a lockfile installs the target's lane
        for argv in (
            ["-C", "frontend", "test"], ["--dir", "frontend", "test"], ["--dir=frontend", "run", "lint"],
            [f"-C={front}", "exec", "vitest"], ["--prefix", "frontend", "test"], ["--prefix=frontend", "test"],
            ["run", "--dir", "frontend", "build"], ["-C", "frontend", "exec", "vitest"],
            ["run", "--dir=frontend", "--if-present", "lint"], ["run-script", "-C", "frontend", "test"],
            ["--child-concurrency", "1", "-C", "frontend", "test"], ["run", "--resume-from", "frontend", "-C", "frontend", "build"],
        ):   # (`exec -C frontend vitest` is not among them: after `exec` pnpm reads no options, measured; see round 16)
            (front / "node_modules" / ".fake-state").unlink(missing_ok=True)
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=parent)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.calls(), [f"{front.resolve()}|false|install --frozen-lockfile", f"{parent.resolve()}|false|{' '.join(argv)}"], argv)
            self.assertEqual(self.fx.checks()[0].split("|", 1)[0], str(front.resolve()), argv)
            self.assertFalse((parent / "node_modules").exists(), argv)
        # an explicit mutation targeting another project holds that project's lock and runs where typed
        lock = front / "node_modules" / ".gc-lane-deps.lock"
        holder = subprocess.Popen(["sleep", "30"])
        try:
            lock.mkdir()
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            self.fx.reset()
            r = self.fx.run("pnpm", "add", "--dir", "frontend", "x", cwd=parent, GC_TOOLCHAIN_LANE_DEPS_WAIT="2")
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"another lane install (pid {holder.pid}) has held {lock.resolve()}", r.stderr)
        self.assertEqual(self.fx.calls(), [])
        (lock / "pid").unlink()
        lock.rmdir()
        # the last -C wins, and a first install without a lockfile makes the target the lane
        fresh = parent / "fresh"
        fresh.mkdir()
        r = self.fx.run("pnpm", "-C", "frontend", "-C", "fresh", "install", cwd=parent)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((fresh / "pnpm-lock.yaml").exists())

    def test_arguments_after_the_script_or_bin_name_belong_to_it(self) -> None:
        proj = self.fx.project()
        elsewhere = self.fx.project("elsewhere")
        for argv in (["run", "build", "--dir", "../elsewhere"], ["exec", "vitest", "-C", "../elsewhere"], ["vitest", "run", "--dir=../elsewhere"], ["test", "--", "-C", "../elsewhere"], ["run", "build", "--prefix", "../elsewhere"]):
            self.fx.reset()
            r = self.fx.run("pnpm", *argv, cwd=proj)
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
            self.assertEqual(self.fx.argv()[-1], " ".join(argv), argv)
            self.assertEqual(self.fx.checks()[0].split("|", 1)[0], str(proj.resolve()), argv)
            self.assertFalse((elsewhere / "node_modules").exists(), argv)


class PnpmShimShapeATests(unittest.TestCase):
    """Round 3 (bead gp-sgbj): the concurrency contract, shape A. The wrapper
    owns its own question and the one frozen install per lockfile under the
    lane lock, and mutate-vs-mutate serialization on that same lock. A project
    command runs after the question holding nothing; nothing tracks running
    commands; a running command is not fenced from a dependency mutation
    another caller starts afterwards (the documented non-goal, pinned here as
    behaviour, pnpm:898 and pnpm:759 of round 29 included by name)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(pathlib.Path(self.tmp.name), real_node=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_project_command_runs_holding_no_lock_and_no_token(self) -> None:
        """(i) measured while the command runs: the lock is gone, no token
        directory exists, nothing of the wrapper's is in node_modules."""
        proj = self.fx.project()
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)     # prepared: pnpm says yes from here on
        nm = proj / "node_modules"
        self.fx.reset()
        result: dict[str, subprocess.CompletedProcess[str]] = {}

        def check() -> None:
            result["r"] = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_RUN_SLEEP="3")

        th = threading.Thread(target=check)
        th.start()
        time.sleep(1.5)
        self.assertFalse((nm / ".gc-lane-deps.lock").exists())
        self.assertEqual([p.name for p in nm.iterdir() if p.name.startswith(".gc-lane-deps")], [])
        th.join(timeout=60)
        self.assertEqual(result["r"].returncode, 0, result["r"].stderr)
        self.assertEqual(self.fx.argv(), ["exec vitest"])
        self.assertEqual(len(self.fx.checks()), 1)      # asked once, under the lock, before the command
        self.assertEqual([p.name for p in nm.iterdir() if p.name.startswith(".gc-lane-deps")], [])

    def test_two_mutating_calls_serialize_on_the_lane_lock(self) -> None:
        """(ii) the second waits for the first's lock; measured order and time."""
        proj = self.fx.project()
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        results: dict[str, subprocess.CompletedProcess[str]] = {}
        ends: dict[str, float] = {}

        def mutate(name: str, delay: float) -> None:
            time.sleep(delay)
            results[name] = self.fx.run("pnpm", "add", name, cwd=proj, FAKE_PNPM_SLEEP="2", GC_TOOLCHAIN_LANE_DEPS_WAIT="20")
            ends[name] = time.monotonic()

        started = time.monotonic()
        threads = [threading.Thread(target=mutate, args=("left-pad", 0.0)), threading.Thread(target=mutate, args=("right-pad", 0.5))]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=60)
        for name in ("left-pad", "right-pad"):
            self.assertEqual(results[name].returncode, 0, (name, results[name].stderr))
        self.assertNotIn("waiting", results["left-pad"].stderr)
        self.assertIn("waiting for another caller's lane install", results["right-pad"].stderr)
        self.assertEqual(self.fx.argv(), ["add left-pad", "add right-pad"])       # the measured order
        self.assertGreaterEqual(ends["right-pad"], ends["left-pad"])
        self.assertGreaterEqual(ends["right-pad"] - started, 3.5)                # two seconds each, never side by side
        self.assertFalse(lock.exists())

    def test_a_mutate_does_not_wait_for_a_running_project_command(self) -> None:
        """(iii) the non-goal pinned as behaviour: a rebuild started one second
        into a four-second check takes the lock at once and ends before the
        check does. Bare pnpm's own position; one lane, one agent."""
        proj = self.fx.project()
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.fx.reset()
        results: dict[str, subprocess.CompletedProcess[str]] = {}
        marks: dict[str, float] = {}

        def check() -> None:
            results["check"] = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_RUN_SLEEP="4")
            marks["check_end"] = time.monotonic()

        def rebuild() -> None:
            time.sleep(1)
            results["rebuild"] = self.fx.run("pnpm", "rebuild", cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="20")
            marks["rebuild_end"] = time.monotonic()

        threads = [threading.Thread(target=check), threading.Thread(target=rebuild)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=60)
        self.assertEqual(results["check"].returncode, 0, results["check"].stderr)
        self.assertEqual(results["rebuild"].returncode, 0, results["rebuild"].stderr)
        self.assertNotIn("waiting", results["rebuild"].stderr)
        self.assertLess(marks["rebuild_end"], marks["check_end"])       # ran under the check: unfenced by design
        self.assertEqual(self.fx.argv(), ["exec vitest", "rebuild"])
        self.assertFalse((proj / "node_modules" / ".gc-lane-deps.lock").exists())

    def test_a_command_started_by_a_running_command_is_any_other_caller(self) -> None:
        """Nothing marks a nested command: a project command a running command
        starts asks pnpm under the lock and runs; a mutate there takes the lock
        and runs under the command that started it (`pnpm rebuild` from a
        script, `node check.js & pnpm rebuild`, two scripts each rebuilding);
        LANE_DEPS=off on a nested command runs it as is."""
        proj = self.fx.project()
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        nm = proj / "node_modules"
        inner = self.fx.root / "check-inside.sh"
        write_exec(inner, f'#!/bin/sh\nunset FAKE_PNPM_RUN_HOOK\n"{self.fx.shims / "pnpm"}" exec eslint || exit 9\n')
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_RUN_HOOK=str(inner))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.argv(), ["exec vitest", "exec eslint"])
        self.assertEqual(len(self.fx.checks()), 2)      # each asked once, under the lock
        self.assertEqual([p.name for p in nm.iterdir() if p.name.startswith(".gc-lane-deps")], [])
        hook = self.fx.root / "rebuild-inside.sh"
        write_exec(hook, f'#!/bin/sh\nunset FAKE_PNPM_RUN_HOOK\nsleep 1 & bg=$!\n"{self.fx.shims / "pnpm"}" rebuild || {{ wait "$bg"; exit 9; }}\nwait "$bg"\n')
        self.fx.reset()
        started = time.monotonic()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_RUN_HOOK=str(hook), GC_TOOLCHAIN_LANE_DEPS_WAIT="30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(time.monotonic() - started, 10)
        self.assertNotIn("refused", r.stderr)
        self.assertNotIn("waiting", r.stderr)
        self.assertEqual(self.fx.argv(), ["exec vitest", "rebuild"])     # the rebuild ran, under its command
        self.assertFalse(in_sync(proj))                                   # (the fake's rebuild leaves the tree stale)
        self.assertFalse((nm / ".gc-lane-deps.lock").exists())
        # two scripts each rebuilding at once: both run, serialized on the lock, no wait on each other's command
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        pair: dict[str, subprocess.CompletedProcess[str]] = {}

        def script(name: str) -> None:
            pair[name] = self.fx.run("pnpm", "exec", name, cwd=proj, FAKE_PNPM_RUN_HOOK=str(hook), GC_TOOLCHAIN_LANE_DEPS_WAIT="30")

        self.fx.reset()
        started = time.monotonic()
        threads = [threading.Thread(target=script, args=(n,)) for n in ("vitest", "eslint")]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=60)
        self.assertLess(time.monotonic() - started, 15)
        for name in ("vitest", "eslint"):
            self.assertEqual(pair[name].returncode, 0, (name, pair[name].stderr))
            self.assertNotIn("refused", pair[name].stderr)
        self.assertEqual([a for a in self.fx.argv() if a == "rebuild"], ["rebuild", "rebuild"])
        self.assertEqual([p.name for p in nm.iterdir() if p.name.startswith(".gc-lane-deps")], [])
        # LANE_DEPS=off on the nested command runs it as is, no lock
        hook_off = self.fx.root / "rebuild-inside-off.sh"
        write_exec(hook_off, f'#!/bin/sh\nunset FAKE_PNPM_RUN_HOOK\nGC_TOOLCHAIN_LANE_DEPS=off "{self.fx.shims / "pnpm"}" rebuild || exit 9\n')
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        self.fx.reset()
        r = self.fx.run("pnpm", "exec", "vitest", cwd=proj, FAKE_PNPM_RUN_HOOK=str(hook_off))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.fx.argv(), ["exec vitest", "rebuild"])

    def test_a_lane_that_refuses_the_lock_fails_closed_and_lane_deps_off_runs_there(self) -> None:
        """Rounds 17 and 21, kept: with no lock the wrapper cannot serialize its
        question and install, so the command fails closed at once naming the
        refusal; LANE_DEPS=off is the way through when the lane is yours alone."""
        ro = self.fx.project("ro")
        self.fx.run("pnpm", "exec", "vitest", cwd=ro)
        (ro / "node_modules").chmod(0o555)
        try:
            self.fx.reset()
            started = time.monotonic()
            r = self.fx.run("pnpm", "exec", "vitest", cwd=ro)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertLess(time.monotonic() - started, 20)
            self.assertIn("cannot create", r.stderr)
            self.assertIn("cannot be coordinated from here", r.stderr)
            self.assertEqual(self.fx.all_calls(), [])
            r = self.fx.run("pnpm", "exec", "vitest", cwd=ro, GC_TOOLCHAIN_LANE_DEPS="off")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.fx.all_calls(), [f"{ro.resolve()}|false|exec vitest"])
        finally:
            (ro / "node_modules").chmod(0o755)

    def test_the_names_of_round_20_keep_their_kinds(self) -> None:
        """prefix/get/set/owners/peers/lane/change are informational; uni and
        runtime mutate (checked against the 115 names in the pinned pnpm.mjs)."""
        proj = self.fx.project()
        self.fx.run("pnpm", "exec", "vitest", cwd=proj)
        holder = subprocess.Popen(["sleep", "60"])
        lock = proj / "node_modules" / ".gc-lane-deps.lock"
        try:
            lock.mkdir()
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            for argv in (["prefix"], ["get", "registry"], ["set", "registry", "x"], ["owners", "ls", "x"], ["peers", "check"], ["lane"], ["change", "status"]):
                self.fx.reset()
                r = self.fx.run("pnpm", *argv, cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="1")
                self.assertEqual(r.returncode, 0, (argv, r.stderr))
                self.assertEqual(self.fx.all_calls(), [f"{proj.resolve()}|false|{' '.join(argv)}"], argv)
            for argv in (["uni", "x"], ["runtime", "set", "node", "22"], ["rt", "set", "node", "22"]):
                self.fx.reset()
                r = self.fx.run("pnpm", *argv, cwd=proj, GC_TOOLCHAIN_LANE_DEPS_WAIT="1")
                self.assertEqual(r.returncode, 1, (argv, r.stderr))
                self.assertIn("has held", r.stderr, argv)
        finally:
            holder.kill()
            holder.wait()


README = TOOLCHAIN.parents[2] / "README.md"
FRAGMENT = TOOLCHAIN.parents[2] / "template-fragments" / "gc-role-worker.template.md"
NON_GOAL = "A running command is not fenced from a dependency mutation another caller starts afterwards."
NON_GOAL_WHY = (
    "This is bare pnpm's own position, and under the lane model one lane belongs to one agent "
    "(memory dispatch-worktree-constraint), so the two callers are the same agent."
)


class ShapeAContractTextTests(unittest.TestCase):
    """(iv) the wrapper header, the README recipe and the role-worker fragment
    carry the non-goal sentence; the reader-token machinery and its words are
    gone from the wrapper and the README."""

    def test_header_readme_and_fragment_carry_the_non_goal(self) -> None:
        header = " ".join(
            line.lstrip("#").strip() for line in PNPM_SHIM.read_text(encoding="utf-8").splitlines() if line.startswith("#")
        )
        readme = " ".join(README.read_text(encoding="utf-8").split())
        fragment = " ".join(FRAGMENT.read_text(encoding="utf-8").split())
        for name, text in (("header", header), ("README", readme)):
            self.assertIn(NON_GOAL, text, name)
            self.assertIn(NON_GOAL_WHY, text, name)
            self.assertIn("syncInjectedDepsAfterScripts", text, name)     # pnpm:898 by name: a writer, unfenced by design
            self.assertIn("No child-pid tracking, no ancestor exemption.", text, name)
            self.assertIn("orphaned", text, name)                         # pnpm:759, the accepted dead-wrapper window
        self.assertIn(NON_GOAL[0].lower() + NON_GOAL[1:-1], fragment)    # the same words, mid-sentence in the lane paragraph
        lane_para = [p for p in fragment.split("## ") if p.startswith("Workspace")]
        self.assertEqual(len(lane_para), 1)
        self.assertIn("The lane is yours alone", lane_para[0])
        self.assertIn(NON_GOAL[0].lower() + NON_GOAL[1:-1], lane_para[0])

    def test_the_reader_token_machinery_is_gone(self) -> None:
        source = PNPM_SHIM.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        for gone in (
            ".gc-lane-deps.readers", "GC_TOOLCHAIN_LANE_DEPS_READING", "GC_TOOLCHAIN_LANE_DEPS_READER",
            "take_token", "drop_token", "wait_for_readers", "reader token", "refused: a mutate inside",
        ):
            self.assertNotIn(gone, source, gone)
            self.assertNotIn(gone, readme, gone)
        self.assertEqual(source.count("owner_is_dead()"), 1)     # one use left: the lock's owner
        self.assertIn("owner_is_dead \"$owner\"", source)


def fake_node_tree(root: pathlib.Path, version: str) -> pathlib.Path:
    """A minimal node install tree at root/v<version>: bin/{node,npm,npx}."""
    tree = root / f"v{version}"
    for name in ("node", "npm", "npx"):
        write_exec(tree / "bin" / name, f'#!/bin/sh\necho "fake {name} {version} $*"\n')
    return tree


def fake_dist(root: pathlib.Path, version: str, *, corrupt_sum: bool = False) -> str:
    """A nodejs.org-shaped dist directory served over file://; returns its URL."""
    os_name = platform.system().lower()
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}[platform.machine()]
    name = f"node-v{version}-{os_name}-{arch}"
    build = root / "build" / name
    for prog in ("node", "npm", "npx"):
        write_exec(build / "bin" / prog, f'#!/bin/sh\necho "downloaded {prog} {version} $*"\n')
    vdir = root / f"v{version}"
    vdir.mkdir(parents=True)
    tar_path = vdir / f"{name}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(build, arcname=name)
    digest = sha256(tar_path)
    if corrupt_sum:
        digest = "0" * 64
    (vdir / "SHASUMS256.txt").write_text(f"{digest}  {name}.tar.gz\n{'1' * 64}  other.tar.gz\n", encoding="utf-8")
    return f"file://{root}"


class NodeShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(pathlib.Path(self.tmp.name))
        self.node_root = self.fx.toolchain / "node"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_without_a_pin_the_wrapper_is_transparent(self) -> None:
        for prog in ("node", "npm", "npx"):
            r = self.fx.run(prog, "--version", "-e", "1")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, f"machine {prog} --version -e 1\n")
            self.assertEqual(r.stderr, "")

    def test_environment_pin_runs_the_installed_version(self) -> None:
        fake_node_tree(self.node_root, "9.9.9")
        r = self.fx.run("node", "-e", "1", GC_TOOLCHAIN_NODE_VERSION="9.9.9")
        self.assertEqual(r.stdout, "fake node 9.9.9 -e 1\n")
        self.assertEqual(r.stderr, "")
        r = self.fx.run("npm", "--version", GC_TOOLCHAIN_NODE_VERSION="v9.9.9")
        self.assertEqual(r.stdout, "fake npm 9.9.9 --version\n")
        r = self.fx.run("npx", "-y", "x", GC_TOOLCHAIN_NODE_VERSION="9.9.9")
        self.assertEqual(r.stdout, "fake npx 9.9.9 -y x\n")

    def test_nvmrc_above_the_working_directory_pins_and_a_major_picks_the_newest_installed(self) -> None:
        fake_node_tree(self.node_root, "9.9.9")
        fake_node_tree(self.node_root, "9.10.1")
        fake_node_tree(self.node_root, "10.0.0")
        repo = self.fx.root / "repo"
        deep = repo / "a" / "b"
        deep.mkdir(parents=True)
        (repo / ".nvmrc").write_text("9\n", encoding="utf-8")
        r = self.fx.run("node", "-v", cwd=deep)
        self.assertEqual(r.stdout, "fake node 9.10.1 -v\n", r.stderr)
        (repo / ".nvmrc").write_text("v9.9\n", encoding="utf-8")
        r = self.fx.run("node", "-v", cwd=deep)
        self.assertEqual(r.stdout, "fake node 9.9.9 -v\n", r.stderr)
        (repo / ".nvmrc").unlink()
        (repo / ".node-version").write_text("10.0.0", encoding="utf-8")
        r = self.fx.run("node", "-v", cwd=deep)
        self.assertEqual(r.stdout, "fake node 10.0.0 -v\n", r.stderr)

    def test_environment_wins_over_nvmrc_and_nvmrc_over_the_sidecar(self) -> None:
        fake_node_tree(self.node_root, "9.9.9")
        fake_node_tree(self.node_root, "10.0.0")
        fake_node_tree(self.node_root, "11.0.0")
        repo = self.fx.root / "repo"
        repo.mkdir()
        (self.fx.shims / "toolchain.env").write_text("NODE_VERSION=11.0.0\n", encoding="utf-8")
        r = self.fx.run("node", "-v", cwd=repo)
        self.assertEqual(r.stdout, "fake node 11.0.0 -v\n", r.stderr)
        (repo / ".nvmrc").write_text("10.0.0\n", encoding="utf-8")
        r = self.fx.run("node", "-v", cwd=repo)
        self.assertEqual(r.stdout, "fake node 10.0.0 -v\n", r.stderr)
        r = self.fx.run("node", "-v", cwd=repo, GC_TOOLCHAIN_NODE_VERSION="9.9.9")
        self.assertEqual(r.stdout, "fake node 9.9.9 -v\n", r.stderr)

    def test_unusable_nvmrc_spec_warns_and_falls_through(self) -> None:
        repo = self.fx.root / "repo"
        repo.mkdir()
        (repo / ".nvmrc").write_text("lts/*\n", encoding="utf-8")
        r = self.fx.run("node", "-v", cwd=repo)
        self.assertEqual(r.stdout, "machine node -v\n")
        self.assertIn("does not resolve", r.stderr)

    def test_missing_version_with_installs_off_warns_once_and_falls_through(self) -> None:
        r = self.fx.run("node", "-v", GC_TOOLCHAIN_NODE_VERSION="9.9.9", GC_TOOLCHAIN_NODE_INSTALL="off")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "machine node -v\n")
        self.assertIn("installs are off", r.stderr)
        self.assertIn("using the node on PATH", r.stderr)

    def test_unwritable_toolchain_warns_and_falls_through(self) -> None:
        self.node_root.mkdir()
        self.node_root.chmod(0o555)
        try:
            r = self.fx.run("node", "-v", GC_TOOLCHAIN_NODE_VERSION="9.9.9", GC_TOOLCHAIN_NODE_DIST="file:///nonexistent")
        finally:
            self.node_root.chmod(0o755)
        self.assertEqual(r.stdout, "machine node -v\n")
        self.assertIn("cannot write", r.stderr)
        self.assertEqual([p.name for p in self.node_root.iterdir()], [])

    def test_download_is_checksum_verified_installed_once_and_then_used_by_all_three_names(self) -> None:
        dist = fake_dist(self.fx.root / "dist", "1.2.3")
        r = self.fx.run("node", "-e", "1", GC_TOOLCHAIN_NODE_VERSION="1.2.3", GC_TOOLCHAIN_NODE_DIST=dist)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "downloaded node 1.2.3 -e 1\n")
        self.assertIn("installed node v1.2.3", r.stderr)
        self.assertTrue((self.node_root / "v1.2.3" / "bin" / "node").exists())
        self.assertEqual(sorted(p.name for p in self.node_root.iterdir()), ["v1.2.3"])  # no lock, no stage left
        for prog in ("node", "npm", "npx"):
            r = self.fx.run(prog, "--v", GC_TOOLCHAIN_NODE_VERSION="1.2.3", GC_TOOLCHAIN_NODE_DIST="file:///nonexistent")
            self.assertEqual(r.stdout, f"downloaded {prog} 1.2.3 --v\n", r.stderr)
            self.assertEqual(r.stderr, "")

    def test_an_interrupted_install_lock_is_moved_aside_and_the_install_proceeds(self) -> None:
        dist = fake_dist(self.fx.root / "dist", "1.2.3")
        lock = self.node_root / ".installing-v1.2.3"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        r = self.fx.run("node", "-v", GC_TOOLCHAIN_NODE_VERSION="1.2.3", GC_TOOLCHAIN_NODE_DIST=dist)
        self.assertEqual(r.stdout, "downloaded node 1.2.3 -v\n", r.stderr)
        self.assertIn("moved aside an interrupted node v1.2.3 install lock", r.stderr)
        self.assertFalse(lock.exists())
        aside = [p for p in self.node_root.iterdir() if p.name.startswith(".installing-v1.2.3.stale-")]
        self.assertEqual(len(aside), 1)
        # a live lock is waited for; the caller falls through after the wait when nothing appears
        lock.mkdir()
        holder = subprocess.Popen(["sleep", "30"])
        try:
            (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
            fake_node_tree(self.node_root, "9.9.9")  # unrelated version
            r = self.fx.run("node", "-v", GC_TOOLCHAIN_NODE_VERSION="1.2.3", GC_TOOLCHAIN_NODE_DIST="file:///nonexistent")
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(r.stdout, "downloaded node 1.2.3 -v\n")  # already installed above: no wait needed

    def test_two_waiters_seeing_one_dead_install_owner_clear_it_once_and_install_once(self) -> None:
        """Round 15: both callers read the dead owner before either reclaims;
        the reclaim lock lets one move it aside, the other re-reads a live
        lock and waits, and one tree is installed, never a nested one."""
        dist = fake_dist(self.fx.root / "dist", "1.2.3")
        lock = self.node_root / ".installing-v1.2.3"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        results: list[subprocess.CompletedProcess[str]] = []
        guard = threading.Lock()

        def call() -> None:
            r = self.fx.run(
                "node", "-v",
                GC_TOOLCHAIN_NODE_VERSION="1.2.3", GC_TOOLCHAIN_NODE_DIST=dist,
                GC_TOOLCHAIN_TEST_PAUSE_BEFORE_RECLAIM="1",
            )
            with guard:
                results.append(r)

        threads = [threading.Thread(target=call) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r.stdout, "downloaded node 1.2.3 -v\n", r.stderr)
        self.assertEqual(sum(r.stderr.count("moved aside") for r in results), 1, [r.stderr for r in results])
        self.assertEqual(sum(r.stderr.count("installed node v1.2.3") for r in results), 1, [r.stderr for r in results])
        aside = [p for p in self.node_root.iterdir() if p.name.startswith(".installing-v1.2.3.stale-")]
        self.assertEqual(len(aside), 1, aside)
        self.assertEqual((aside[0] / "pid").read_text(encoding="utf-8").strip(), str(dead.pid))
        # one install tree, no lock, no reclaim lock, no stage left behind
        self.assertEqual(sorted(p.name for p in self.node_root.iterdir()), [aside[0].name, "v1.2.3"])
        self.assertEqual(sorted(p.name for p in (self.node_root / "v1.2.3").iterdir()), ["bin"])

    def test_a_stuck_reclaim_lock_is_reported_and_the_wrapper_falls_through(self) -> None:
        dist = fake_dist(self.fx.root / "dist", "1.2.3")
        lock = self.node_root / ".installing-v1.2.3"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        reclaim = self.node_root / ".installing-v1.2.3.reclaim"
        reclaim.mkdir()
        old = time.time() - 180
        os.utime(reclaim, (old, old))
        r = self.fx.run("node", "-v", GC_TOOLCHAIN_NODE_VERSION="1.2.3", GC_TOOLCHAIN_NODE_DIST=dist)
        self.assertEqual(r.stdout, "machine node -v\n", r.stderr)
        self.assertIn("stale reclaim lock", r.stderr)
        self.assertIn("using the node on PATH", r.stderr)
        self.assertTrue(lock.exists())
        self.assertTrue(reclaim.exists())
        self.assertFalse((self.node_root / "v1.2.3").exists())

    def test_npm_and_npx_find_the_selected_node_first_on_path(self) -> None:
        """Round 25: npm and npx are `#!/usr/bin/env node` scripts; called by
        absolute path with no node on PATH they exited 127. The selected
        install's bin goes first on PATH before the program runs."""
        tree = fake_node_tree(self.node_root, "9.9.9")
        write_exec(tree / "bin" / "npm", '#!/bin/sh\nprintf "npm sees %s\\n" "$(command -v node)"\nexec node --version\n')
        env = self.fx.env(GC_TOOLCHAIN_NODE_VERSION="9.9.9")
        env["PATH"] = "/usr/bin:/bin"       # no node anywhere on the caller's PATH
        r = subprocess.run([str(self.fx.shims / "npm"), "--version"], cwd=str(self.fx.root), env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, f"npm sees {tree / 'bin' / 'node'}\nfake node 9.9.9 --version\n")
        self.assertEqual(r.stderr, "")

    def test_checksum_mismatch_installs_nothing_and_falls_through(self) -> None:
        dist = fake_dist(self.fx.root / "dist", "1.2.3", corrupt_sum=True)
        r = self.fx.run("node", "-v", GC_TOOLCHAIN_NODE_VERSION="1.2.3", GC_TOOLCHAIN_NODE_DIST=dist)
        self.assertEqual(r.stdout, "machine node -v\n")
        self.assertIn("checksum mismatch", r.stderr)
        self.assertFalse((self.node_root / "v1.2.3").exists())
        self.assertFalse((self.node_root / ".installing-v1.2.3").exists())

    def test_a_major_not_installed_resolves_from_the_dist_index(self) -> None:
        dist = fake_dist(self.fx.root / "dist", "1.2.3")
        (self.fx.root / "dist" / "index.json").write_text(
            '[{"version":"v2.0.0","lts":false},{"version":"v1.2.3","lts":"X"},{"version":"v1.1.9","lts":false}]',
            encoding="utf-8",
        )
        r = self.fx.run("node", "-v", GC_TOOLCHAIN_NODE_VERSION="1", GC_TOOLCHAIN_NODE_DIST=dist)
        self.assertEqual(r.stdout, "downloaded node 1.2.3 -v\n", r.stderr)

    def test_wrong_install_name_refuses(self) -> None:
        (self.fx.shims / "corepack").symlink_to("node")
        r = self.fx.run("corepack", "enable")
        self.assertEqual(r.returncode, 1)
        self.assertIn("install this file as node, npm or npx", r.stderr)

    def test_sidecar_is_read_as_text_never_evaluated(self) -> None:
        canary = self.fx.root / "canary"
        (self.fx.shims / "toolchain.env").write_text(f"NODE_VERSION=$(touch {canary})\n", encoding="utf-8")
        r = self.fx.run("node", "-v")
        self.assertEqual(r.stdout, "machine node -v\n")
        self.assertFalse(canary.exists())
        self.assertIn("is not X, X.Y or X.Y.Z", r.stderr)


if __name__ == "__main__":
    unittest.main()
