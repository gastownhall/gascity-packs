# runtime-herdr-core soak runbook

Scratch-city bring-up, the switch to the v2 session reconciler, fault drills,
and the first watched 24-hour soak of runtime `herdr-core`.

Status: procedure and harness ready, not yet run. The harness this runbook
calls lives beside it (`soak/`, section 7) and is unit-tested on synthetic
logs and fake-hc only. Results go to `runtime-herdr-core/docs/soak-report.md`
(template in section 15).

Contents: 0 what a pass shows · 1 ground rules (1.1 decisions for Soak 1) · 2 pinned versions · 3 VM
layout · 4 provision the VM · 5 toolchain · 6 pack, live tier, harness ·
7 the harness · 8 the city · 9 phase 1 bring-up · 10 phase 2 v2 switch ·
11 phase 3 fault drills · 12 phase 4 the 24-hour soak · 13 abort predicates
and the abort procedure · 14 metrics · 15 report template · 16 teardown.

## 0. What a pass shows

1. **Bring-up** (legacy reconciler). A city whose `[session] provider` is
   `herdr-core` boots on the pinned herdr-core under a systemd user manager.
   `gc doctor` reports no error and every warning is disclosed. gc's
   conformance suite, run against a scratch state root while the city runs,
   reports v2-ready with no failed requirement and leaves no core behind. A
   formula run completes.
2. **Switch to v2.** With `session_reconciler` unset the controller boots v2
   by default, no running box reads as Ownerless or Unknown, and restarts
   converge.
3. **Fault drills.** Holder loss, a cgroup-wide holder kill, core loss, a
   planned core restart, an agent crash, a refused self-update, a pin upgrade,
   a stop against a wedged core and a reboot each keep the city's store
   running, restart what died within two patrols, reap what the dead agents
   left within one patrol, and leave no orphan behind.
4. **24-hour soak** (12 h legacy, then 12 h v2; 10 to 20 sessions under steady
   formula load). No first turn is lost or typed twice, no infrastructure
   process is killed, under 1% of nudges end unconfirmed, the pack's per-op
   spawn rate stays within budget, the core's RSS stays within ±20%, and the
   per-op spawn rate, op latency, controller CPU and death-to-restart latency
   are recorded.

The agents are scripted, deterministic programs (section 7.1). No model
credential is placed on the VM; a shorter soak with a real coding agent
follows later.

Order of work: build the harness (section 7) with its unit tests first,
then run sections 4 to 12 in order. A phase that fails stops the run: keep
its data, capture (`soak capture`), file the finding, and re-run that phase
once a fix has landed. Rough durations: provisioning and builds 45 minutes,
the live-tier pre-flight 15 minutes, bring-up 1.5 hours, the v2 switch 45
minutes, the drills 5 hours, the soak 25 hours.

## 1. Ground rules

- **Two machines.** The *operator host* only runs `ssh`, `rsync` and the
  harness's unit tests, which use synthetic data. It never runs a real
  herdr-core, never runs gc, bd or dolt against a city, and never runs a
  harness tool: every tool refuses unless `/etc/gc-soak-throwaway` holds the
  host's own `/etc/machine-id`, a file only the VM's provisioning writes.
- **The VM is disposable and dedicated.** Root may install packages, create
  users, start and kill processes. Never change sshd's configuration or the
  firewall. Never place a secret or a model credential on it. It reaches only
  the Ubuntu mirrors, GitHub, the Go module proxy, go.dev and
  releases.herdr.dev.
- **Kill by pid, after an ownership check, through a pidfd** (the live
  tier's rule): hc runtime of the city's state root, a process the harness
  recorded, or a process carrying the city's identity. Never `pkill`,
  `killall` or any pattern, on either machine.
- **No pushes.** Nothing in this runbook pushes to a repository or writes to
  GitHub. The VM only clones public commits.
- **The canary** used by the secrets check is a random string generated on
  the VM. It is not a credential.

### 1.1 Decisions for Soak 1

Decided 2026-11-17 by the task owner; the rest of this runbook follows them.

1. **The performance predicate is record-only.** AP5 (pack cost) is judged
   every run and its numbers are recorded (`perf` in each `check.jsonl`
   record: rate, limit, CPU, CPU limit, `n`, the reconciler); over its limit
   it is a `WARN` line naming the numbers (`AP5: record-only: ...`), never a
   hit, and its unreadable inputs do not count towards AP9. The harness's
   `soakcheck.RECORD_ONLY` holds the list. Every correctness predicate (AP1
   to AP4, AP6 to AP9) still aborts in `abort` mode. S5 is still reported
   against its target; a miss is a finding, not an abort.
2. **The default store only.** Every city is the default a new city gets at
   the pinned gc: bd's proxied Dolt server for work, SQLite for the
   infrastructure classes (section 8). No managed-Dolt city is created, and
   no drill switches a city to one. Dolt is installed only because bd's
   proxy runs `dolt sql-server`.
3. **Watching.** The orchestrating session is the watcher: it checks the VM
   about every 30 minutes (the last `check.log` line, `ABORTED`, the last
   digest) and tells the task owner on an abort or when the soak ends. On
   `ABORTED` nothing is restarted.
4. **The upgrade drill is a VM-local pin edit.** F8 writes the 0.1.20 pin
   (section 11; sha256 values from the 0.1.20 release manifest) over the VM's
   pack copy only, never a pin bump of the pack. F9, which runs next,
   restores the pinned 0.1.19 `hc-pin.json` from the pack commit and checks
   the copy against `runtime-herdr-core.SHA256SUMS`, and checks that the core
   runs 0.1.19 again after `gc start`. F8 saves the pack copy's pin to
   `~/packs/runtime-herdr-core.hc-pin.json` before it writes the 0.1.20 one;
   F9 restores from the `~/src/gascity-packs` clone when the VM has one, else
   from that copy (the `SHA256SUMS` check holds either way). If the drills stop
   between F8 and F9, restore the pin by hand the same way before anything
   else runs on the city.

Accepted defaults:

- `soak probe` sends `SIGKILL` to one always-on scripted agent every 30
  minutes for the death-to-restart samples (section 7.3).
- Anything outside the abort list (section 13) is a warning only.
- Disclosed tuning deviations: `max_wakes_per_tick = 25` and
  `proxied_idle_timeout = "0"` (section 8); both go in the report's
  deviations.
- The bd pack's `dog` maintenance pool runs the scripted agent and does
  nothing (a no-op), disclosed.
- Soak 1 runs on a fresh city, `hc-soak`.
- First-turn handbacks are recorded as not applicable: the pack has no
  `proc.launch` yet.
- The live-tier pre-flight (section 6) is recorded, not gating.
- Scripted agents only; no model credential is placed on the VM.

## 2. Pinned versions and sources

| What | Version | Source and check |
|---|---|---|
| Host | Ubuntu 24.04.4 LTS, kernel 6.8.0-138-generic, systemd 255.4-1ubuntu8.17, x86_64, cgroup v2, 4 vCPU, 7.7 GiB, 75 GB disk | the VM as provisioned |
| Python | 3.12.3 (Ubuntu `python3`) | the pack needs 3.9 or later; standard library only |
| Go | 1.27.4 | `https://go.dev/dl/go1.27.4.linux-amd64.tar.gz`, sha256 `7226736c2339719cda28fbf3a54d71aa63bcefe376e98cef00034268dab24840`; `GOTOOLCHAIN=local` so nothing else builds gc |
| gc (and `gc-osc7501`) | gascity `6cf1cccd640df81542d19b3a9270fdfc8c296a5b` | `CGO_ENABLED=0 go install github.com/gastownhall/gascity/cmd/gc@<sha> …/cmd/gc-osc7501@<sha>`; its `go.mod` asks for Go 1.27.4 and has no `replace`; it contains the vanished-session nudge fix, the infrastructure scope, the process scanner and its tmux fence the pack needs |
| bd | v1.3.4 | `https://github.com/gastownhall/beads/releases/download/v1.3.4/beads_1.3.4_linux_amd64.tar.gz`, sha256 `175c26904bde3ff9168d2282ff6b56f17b17f60c22fa5acb3dacc9fb3465303a` (gascity `deps.env` `BD_VERSION` and its `.github/scripts/install-bd-archive.sh`); gc's floor is 1.3.0, a split city needs 1.3.2 or later |
| dolt | 2.6.0 | `https://github.com/dolthub/dolt/releases/download/v2.6.0/dolt-linux-amd64.tar.gz`, sha256 `a8d4c2e2e94b85fd3592cb80748044f846ccfd03d25a536ed1f754baf7da6401` (`deps.env` `DOLT_VERSION`; the `dolt sql-server` bd's proxy runs) |
| herdr-core | 0.1.19 | installed by the pack's own `gc herdr-core install` from `releases.herdr.dev/core/0.1.19/`; `linux-x86_64` sha256 `4adcfb423d52f24c5cc4a1e2cd2fcad1f62d28bb77876ac472c29082a3eaa424` (pin and manifest must agree) |
| herdr-core, upgrade drill only | 0.1.20 | `releases.herdr.dev/core/0.1.20/manifest.json`; `linux-x86_64` sha256 `ac6b86890c451a37584620aaa438b71bc0d0bd430a2e7c1d7e095f052c414e74` (drill F8 only, a VM-local pin edit) |
| The pack | gascity-packs `a9ff70be08a43906af9623aa63270ea4eb52d3e6` | `runtime-herdr-core/` exported with `git archive` to a plain directory the city imports |
| Live tier and its kit | gascity-packs `21a0bfb3241964a142483ace0e0fdd19adae14b9` | the pinned pack plus `tests/live`; `assets/`, `commands/`, `doctor/` and `pack.toml` are byte-identical to the pinned pack (checked in section 6) |
| pytest | 8.4.2 | `~/venv`, live tier only |
| bpftrace | Ubuntu 24.04 archive build | records `bpftrace --version` in the report |
| The harness | the soak branch commit that carries `runtime-herdr-core/soak/` | recorded in the report (section 6) |

## 3. VM layout

| Path | What |
|---|---|
| user `soak` | non-root, lingering, its own systemd user manager; logs in with the operator host's soak key |
| `/etc/gc-soak-throwaway` | the VM's machine id; every harness tool refuses without it |
| `/usr/local/go` | Go 1.27.4 |
| `/usr/local/bin/{gc,gc-osc7501,bd,dolt}` | the pinned binaries |
| `~/.soakrc` | `PATH`, `GOTOOLCHAIN`, `CGO_ENABLED`, `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`; sourced first by `~/.bashrc` |
| `~/src/gascity-packs` | clone, detached at the live-tier commit (`tests/live`, the live kit) |
| `~/packs/runtime-herdr-core` | the pinned pack, a plain directory (`git archive`), with `runtime-herdr-core.COMMIT` and `runtime-herdr-core.SHA256SUMS` beside it |
| `~/soak` | the harness (`rsync` of `runtime-herdr-core/soak/`) |
| `~/venv` | pytest for the live tier |
| `~/cities/hc-bringup` | the city of phases 1 to 3 |
| `~/cities/hc-soak` | the city of phase 4 (fresh, same configuration, larger) |
| `~/soak-data/<city>/` | everything the harness writes for one city (below) |
| `~/soak-data/current` | symlink to the active city's data directory |
| `~/soak-data/optrace/optrace.log` | the per-op trace (root's bpftrace unit) |
| `~/.local/state/gc-runtime-herdr-core` | `R`, the pack's and hc's state root (the default; `GC_EXEC_STATE_DIR` is never set for a city) |
| `~/.local/share/gc-runtime-herdr-core/hc/<version>/herdr-core` | the pinned hc, read-only |

`~/soak-data/<city>/`:

| File | Writer | Content |
|---|---|---|
| `soak.env` | `soak city-init` | `SOAK_CITY`, `SOAK_DATA`, `SOAK_MODE` (`warn` or `abort`) for the harness units |
| `load.json` | `soak city-init` | the load generator's rates (section 7.2) |
| `phase`, `phases.jsonl` | `soak phase` | the current phase name; every phase change with its time and reconciler (the report's windows) |
| `PAUSE`, `DRILL`, `CONFORMANCE` | operator, `soak drill`, phase 1 | while present: the load generator pauses; a drill runs; the conformance run's scratch cores are expected |
| `canary` | `soak city-init` | the city's canary (0600) |
| `agents/<session id>.jsonl` | `soak-agent` | every incarnation's records (section 7.1) |
| `cmd/<session id>.cmd` | drills | one-shot commands for one agent |
| `gc-events/events.jsonl` | gc | the city's event log mirror (`[events.mirror]`) |
| `load.jsonl` | `soak load` | every sling and nudge with its result |
| `faults.jsonl` | drills, `soak probe`, `soak note` | every injected fault and planned operator action, with times and what it may end (`covers`, section 13) |
| `samples.jsonl` | `soak sample` | 60 s samples (section 7.4) |
| `check.jsonl`, `check.log` | `soak check` | predicate results: JSON, and one human line per run |
| `check-state.json` | `soak check` | what one run hands the next: infrastructure pids, blind counters, event and load offsets, workflow roots and when they closed; whether the soak aborted, and whether the abort's `gc stop` has exited 0 (`stopped`) |
| `probe-state.json`, `drill-agent-last` | `soak probe`, `soak drill` | the last session the probe or the agent-kill drill took (round robin) |
| `f1-store.json` | drill F1 | the store pids F1 placed, which F2 and F3 check |
| `digest.log` | `soak check` | the hourly digest |
| `drills/<name>-<time>.json` | `soak drill` | each drill's record and verdict |
| `captures/<time>.tar.gz` | `soak capture` | evidence bundles |
| `ABORTED` | `soak check` | created on the first abort hit (time, phase, hits); the abort adds the capture or its failure, then every `gc stop` it runs and what of the city remains after it |
| `gc-init.log`, `doctor-prestart.json`, `final-scan.json` | `soak city-init`, `soak-phase4 end` | gc init's output; doctor before the first start; the secrets grep and leftover scan after the final stop |

## 4. Provision the VM

On the operator host, with `SOAK_VM` set to the VM's address:

```bash
soakssh() { ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="$HOME/.ssh/known_hosts_herdr_soak" -i "$HOME/.ssh/herdr_soak_ed25519" "$@"; }
SOAK_RSYNC_SSH="ssh -o BatchMode=yes -o UserKnownHostsFile=$HOME/.ssh/known_hosts_herdr_soak -i $HOME/.ssh/herdr_soak_ed25519"
```

As root on the VM (packages from `main` and `universe`):

```bash
soakssh "root@$SOAK_VM" 'bash -s' <<'ROOT'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends \
  ca-certificates curl git jq python3-venv bpftrace sysstat lsof procps psmisc util-linux
cat /etc/machine-id > /etc/gc-soak-throwaway
cat > /etc/sysctl.d/90-gc-soak.conf <<'EOF'
fs.inotify.max_user_instances = 1024
fs.inotify.max_user_watches = 524288
EOF
sysctl --system >/dev/null
id soak >/dev/null 2>&1 || useradd --create-home --shell /bin/bash soak
install -d -m 0700 -o soak -g soak /home/soak/.ssh
install -m 0600 -o soak -g soak /root/.ssh/authorized_keys /home/soak/.ssh/authorized_keys
loginctl enable-linger soak
uid=$(id -u soak)
for _ in $(seq 1 60); do [ -S "/run/user/$uid/systemd/private" ] && break; sleep 1; done
test -S "/run/user/$uid/systemd/private"
test -S "/run/user/$uid/bus"
tmp=$(mktemp -d); cd "$tmp"
curl -fsSLo go.tgz https://go.dev/dl/go1.27.4.linux-amd64.tar.gz
echo "7226736c2339719cda28fbf3a54d71aa63bcefe376e98cef00034268dab24840  go.tgz" | sha256sum -c -
rm -rf /usr/local/go && tar -C /usr/local -xzf go.tgz
curl -fsSLo bd.tgz https://github.com/gastownhall/beads/releases/download/v1.3.4/beads_1.3.4_linux_amd64.tar.gz
echo "175c26904bde3ff9168d2282ff6b56f17b17f60c22fa5acb3dacc9fb3465303a  bd.tgz" | sha256sum -c -
mkdir bdx && tar -xzf bd.tgz -C bdx
install -m 0755 "$(find bdx -type f -name 'bd' -print -quit)" /usr/local/bin/
BD=/usr/local/bin/bd
curl -fsSLo dolt.tgz https://github.com/dolthub/dolt/releases/download/v2.6.0/dolt-linux-amd64.tar.gz
echo "a8d4c2e2e94b85fd3592cb80748044f846ccfd03d25a536ed1f754baf7da6401  dolt.tgz" | sha256sum -c -
tar -xzf dolt.tgz && install -m 0755 dolt-linux-amd64/bin/dolt /usr/local/bin/dolt
cd / && rm -rf "$tmp"
/usr/local/go/bin/go version; "$BD" version; dolt version; bpftrace --version
loginctl show-user soak -p Linger
ROOT
```

Expect `Linger=yes`, bd 1.3.4, dolt 2.6.0, go1.27.4. Nothing here touches sshd,
the firewall or systemd-oomd (not installed on this image).

## 5. Toolchain: gc, identities

As `soak`:

```bash
soakssh "soak@$SOAK_VM" 'bash -s' <<'SOAK'
set -euo pipefail
cat > ~/.soakrc <<'EOF'
export PATH=/usr/local/bin:/usr/local/go/bin:/usr/bin:/bin
export GOTOOLCHAIN=local CGO_ENABLED=0
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
EOF
grep -q soakrc ~/.bashrc || sed -i '1i . "$HOME/.soakrc"' ~/.bashrc
. ~/.soakrc
G=6cf1cccd640df81542d19b3a9270fdfc8c296a5b
go install "github.com/gastownhall/gascity/cmd/gc@$G" "github.com/gastownhall/gascity/cmd/gc-osc7501@$G"
go version -m ~/go/bin/gc | grep -E '^\s+mod\s+github.com/gastownhall/gascity\s'   # pseudo-version ending in 6cf1cccd640d
git config --global user.name soak && git config --global user.email soak@localhost
git config --global beads.role maintainer   # else gc doctor's beads-role check fails
[ -n "$(dolt config --global --get user.name || true)" ]  || dolt config --global --add user.name soak
[ -n "$(dolt config --global --get user.email || true)" ] || dolt config --global --add user.email soak@localhost
SOAK
soakssh "root@$SOAK_VM" 'install -m 0755 /home/soak/go/bin/gc /home/soak/go/bin/gc-osc7501 /usr/local/bin/ && gc version'
```

The `mod` line's pseudo-version must end in `6cf1cccd640d`; record it.

## 6. The pack, the live tier and the harness

As `soak`:

```bash
soakssh "soak@$SOAK_VM" 'bash -s' <<'SOAK'
set -euo pipefail
PACK=a9ff70be08a43906af9623aa63270ea4eb52d3e6
LIVE=21a0bfb3241964a142483ace0e0fdd19adae14b9
[ -d ~/src/gascity-packs ] || git clone --quiet https://github.com/gastownhall/gascity-packs.git ~/src/gascity-packs
cd ~/src/gascity-packs
git cat-file -e "$PACK^{commit}" 2>/dev/null && git cat-file -e "$LIVE^{commit}" 2>/dev/null \
  || git fetch --quiet origin '+refs/pull/*/head:refs/remotes/origin/pr/*'   # if the branches were merged and deleted
git checkout --quiet --detach "$LIVE"
test -z "$(git diff --stat "$PACK" "$LIVE" -- runtime-herdr-core/assets runtime-herdr-core/commands \
  runtime-herdr-core/doctor runtime-herdr-core/pack.toml)"
rm -rf ~/packs && mkdir -p ~/packs
git archive "$PACK" runtime-herdr-core | tar -x -C ~/packs
echo "$PACK" > ~/packs/runtime-herdr-core.COMMIT
(cd ~/packs/runtime-herdr-core && find . -type f -print0 | sort -z | xargs -0 sha256sum) > ~/packs/runtime-herdr-core.SHA256SUMS
python3 -m venv ~/venv && ~/venv/bin/pip install -q pytest==8.4.2
install -d -m 0700 ~/soak-data ~/cities
SOAK
```

On the operator host, from the gascity-packs worktree on the soak branch (`H`),
run the harness's unit tests (synthetic data only), then copy it over:

```bash
python3 -m pytest "$H/runtime-herdr-core/soak/tests" -q
test -z "$(git -C "$H" status --porcelain -- runtime-herdr-core/soak)"   # committed, not pushed
git -C "$H" rev-parse HEAD                                              # the harness commit, for the report
rsync -a --delete -e "$SOAK_RSYNC_SSH" "$H/runtime-herdr-core/soak/" "soak@$SOAK_VM:soak/"
soakssh "soak@$SOAK_VM" 'mkdir -p ~/.config/systemd/user && cp ~/soak/systemd/user/* ~/.config/systemd/user/ && systemctl --user daemon-reload'
soakssh "root@$SOAK_VM" 'bash -s' <<'ROOT'
set -euo pipefail
install -d -o soak -g soak -m 0755 /home/soak/soak-data/optrace
install -m 0644 /home/soak/soak/systemd/system/soak-optrace.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now soak-optrace.service
sleep 3; systemctl is-active soak-optrace.service; head -n 1 /home/soak/soak-data/optrace/optrace.log
ROOT
```

`optrace.log` must hold a `B` line (section 7.5); bpftrace prints `Attaching N probes...`
before it, which the harness ignores.

**Pre-flight checks** (as `soak`; all must hold):

```bash
systemctl --user is-system-running        # running or degraded
loginctl show-user "$USER" -p Linger      # Linger=yes
python3 --version                         # 3.12.3
BD=/usr/local/bin/bd; gc version; "$BD" version; dolt version
~/soak/bin/soak guard                     # exit 0 only on this VM
```

**Pre-flight: the live tier on this VM** (about 15 minutes, before any city
exists). It proves the pinned hc, the pack and this VM's user manager
together, both placements, with the live tier's own refusal and teardown
rules. It kills only hc runtime of its own scratch roots.

```bash
cd ~/src/gascity-packs/runtime-herdr-core
HC_LIVE=$(GC_HC_LIVE_THROWAWAY_HOST=$HOME python3 tests/live/fetch_hc.py ~/hclive)
for lane in systemd plain; do
  GC_HC_LIVE=1 GC_HC_LIVE_THROWAWAY_HOST=$HOME GC_HC_LIVE_LANE=$lane \
  GC_HC_LIVE_BIN="$HC_LIVE" GC_HC_LIVE_GC_BIN=/usr/local/bin/gc \
    ~/venv/bin/python -m pytest tests/live -v -rs -p no:cacheprovider 2>&1 | tee ~/soak-data/preflight-live-$lane.log
done
```

Every suite passes, or skips with the reason the live tier names (the
cgroup-wide kill of cases A and B, which the city drills F2 and F3 cover
with a real store). This gc is newer than the live tier's CI pin: a
conformance failure here is recorded and investigated before phase 1, not
waved through. For Soak 1 the pre-flight's result is recorded in the report,
not gating (section 1.1).

## 7. The harness

Standard library Python 3 (3.9 or later; the VM runs 3.12) and bash;
nothing to install. `bin/soak` is one entry with subcommands; every
subcommand calls `soaklib.guard()` first, and the bash phase scripts call
`soak guard` first. Every signal goes through `pidfd_open` +
`pidfd_send_signal` after an ownership check (`soaklib.signal_owned`: the
pidfd is opened, then the pid's start ticks and owner are checked, then the
signal goes through the pidfd), as the live tier's
`livekit.owned.Ownership.signal` does; where Python was built without them
it makes the same two syscalls through `ctypes`.

The harness carries its own small JSON-RPC client (`soakhc.HcRpc`, for
`server.status`) and `/proc` reader (`soaklib.ProcFS`) instead of importing
the live tier's kit or the pack's modules: the pack copy the city runs is a
pinned commit that has neither, and a self-contained harness is what its
unit tests check. The city's core tuple comes from the pack's own
`gc herdr-core status --env`. hc runtime is a process named `herdr-core`
(or one hc marks with `HC_RUNTIME=1`, which is also how fake-hc's cores are
told apart in the unit tests) whose argv names `serve` or `hold`.

```text
soak/
  RUNBOOK.md                      this file
  mypy.ini                        mypy --strict for lib/, the entries and tests/ (3.9 and 3.12)
  bin/soak-agent                  the scripted agent (7.1)
  bin/soak                        city-init, toml-set, toml-del, phase, note, wait, snapshot,
                                  hc-status, store, placement, load, probe, sample, check,
                                  capture, conf-teardown, orphans, drill, report, final-scan, guard
  bin/soak-phase1                 phase 1 end to end (section 9)
  bin/soak-phase2                 the switch to v2 (section 10, and the soak's switch at T0 + 12 h)
  bin/soak-phase4                 `start` and `end` of the 24-hour soak (section 12)
  bin/soak-optrace.bt             per-op exec/exit trace (7.5)
  lib/soaklib.py                  shared: guard, paths, /proc, JSON lines, commands, pidfd signals
  lib/soakanalysis.py             the analyses of 7.6 (pure)
  lib/soakagent.py                the scripted agent's logic
  lib/soakcity.py                 city-init and the TOML edits (section 8)
  lib/soakload.py                 load (7.2) and death probes (7.3)
  lib/soaksample.py               samples (7.4)
  lib/soakcheck.py                predicates, digest and the abort procedure (section 13)
  lib/soakcapture.py              evidence bundles; what of a stopped city remains
  lib/soakhc.py                   the core tuple, server.status, the conformance teardown
  lib/soakdrill.py                the fault drills (section 11)
  lib/soakreport.py               metrics and the Markdown report (section 14)
  lib/soakcli.py                  the subcommands
  city/                           templates rendered by `soak city-init` (section 8)
  systemd/user/                   soak-sample.service, soak-load.service, soak-check.{service,timer},
                                  soak-probe.{service,timer}
  systemd/system/soak-optrace.service
  tests/                          pytest unit tests: synthetic logs, a synthetic /proc, fake-hc
```

The unit tests run on any host (the operator host, CI) and never run gc, bd
or a real herdr-core; the harness's hc conversations are tested against
fake-hc only. From the pack directory:

```bash
python3 -m pytest soak/tests -q
(cd soak && python3 -m mypy --config-file mypy.ini && python3 -m mypy --config-file mypy.ini bin/soak-agent)
shellcheck soak/bin/soak-phase1 soak/bin/soak-phase2 soak/bin/soak-phase4
```

### 7.1 The scripted agent (`bin/soak-agent`)

`#!/usr/bin/python3 -I`, so its command name is `soak-agent`, which the
provider's `process_names` matches. gc starts it as the session command; the
pack's launcher execs it in its own scope under `gascity-agents.slice`.

- **Reads**: `GC_SESSION_ID`, `GC_SESSION_NAME`, `GC_ALIAS`, `GC_AGENT`,
  `GC_TEMPLATE`, `GC_INSTANCE_TOKEN`, `GC_RUNTIME_EPOCH`, `GC_CITY_PATH` (or
  `GC_CITY`), `GC_BIN` (else `gc`; every `gc` below is this binary),
  `SOAK_ROLE` (`steady` or `burst`), `SOAK_DATA`, `SOAK_POLL_S` (default 15),
  `SOAK_DRAIN_IDLE_S` (default 60). `SOAK_STEP_SCALE` (default 1) shortens
  the steps for the unit tests only; the city never sets it.
- **Log**: appends JSON lines to `$SOAK_DATA/agents/<GC_SESSION_ID>.jsonl`,
  one `write(2)` per line on an `O_APPEND` descriptor, each line under 4 KiB.
  Like every JSON line the harness writes, a longer record is cut to fit and
  marked `truncated`: long strings first, then the widest nested lists or
  objects, so keys and short values (a check run's `status`, finding ids)
  stay.
  Every record carries `ev`, `t` (wall seconds), `mono` (`CLOCK_MONOTONIC`
  seconds), `pid` and `inc` (`<boot id prefix>:<pid>:<start ticks>`, the
  incarnation key). The instance token is never logged; `boot` carries its
  sha256 prefix (`token16`).
- **Boot**: writes `boot` (session id, name, alias, agent, template,
  `token16`, epoch, `/proc/self/cgroup`, parent pid and command,
  `hc_scope` = whether `HC_SCOPE` is in its environment); starts two
  background children in sessions of their own (`start_new_session=True`,
  stdio to `/dev/null`): `sleep 86400` and a stand-in dev server,
  `python3 -I -m http.server 0 --bind 127.0.0.1`; writes `bg` with their pids
  and start ticks; prints `soak-agent <session name> pid <pid>` and then the
  ready prompt `soak> ` with no newline.
- **Input** (reader thread): reads stdin a line at a time. Each line becomes
  an `in` record: `n`, `text` (first 1000 characters), `beacon` (the line
  matches gc's beacon, `^\[[^]]+\] \S+ • \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$`),
  `marker` (contains `SOAK-FIRST-TURN`), `nonce` (from `SOAK-NUDGE <hex>`).
  The first line received starts the worker. EOF writes `eof` and exits 0.
- **Worker** (only after the first input; it prints `[claim]` before each
  action, so the ready prompt is the last line only while idle):
  1. Runs `gc hook --claim --json` (timeout 60 s), adding
     `--drain-ack` for a `burst` agent that has had no work for
     `SOAK_DRAIN_IDLE_S`. Parses the last JSON line of stdout and acts on
     its `action` whatever the exit code (gc exits 1 with a `drain` record
     when there is no work and nothing was acknowledged); the exit code is
     logged with it.
  2. `action` `work`: writes `claim` (bead, root), then the step: duration
     `10 + int(sha256(bead id).hexdigest()[:8], 16) % 21` seconds; one store
     write (`gc bd create "soak artifact <bead>" --json`, then
     `gc bd close <artifact id>`, written as `artifact` with exit codes
     and times); then
     `gc bd update <bead> --set-metadata gc.outcome=pass --status=closed`
     (one retry after 5 s), written as `close`; prints
     `done <bead>` and the prompt; claims again at once.
  3. `action` `drain` after `--drain-ack`, with `drain_acknowledged` or
     exit 0 (gc's tolerated refusal: the seat leaves either way): writes
     `drain_ack`, prints `drained`, stops claiming and waits to be stopped.
     A drain whose reason is neither `no_work` nor `claims_errored` (a
     pending drain) without `--drain-ack`: runs `gc runtime drain-ack`,
     writes it, waits to be stopped.
  4. Otherwise (no work): writes `idle` when the reason changes, prints the
     prompt, and waits `SOAK_POLL_S` or until the next input line.
  5. No parsable record (a timeout, a crash, a store fault with exit 2):
     writes `claim_error` (exit code, stderr tail), prints the prompt, waits
     `SOAK_POLL_S`.
- **Commands** (drills only): every second it looks for
  `$SOAK_DATA/cmd/<GC_SESSION_ID>.cmd`, takes it (rename, then unlink),
  runs it and writes `cmd` with the outcome: `bd-touch`
  (`gc bd list --limit 1 --json`),
  `bd-touch-after <pid> <start ticks> ...` (one or more pairs; polls every
  50 ms until all those processes are gone, at most 60 s, then `bd-touch`),
  `hc-ls` (`hc ls` from `PATH`, which starts with the pack's shim),
  `exit <code>`.
- **Heartbeat**: `hb` every 60 s.
- **Signals**: `SIGTERM`, `SIGHUP`, `SIGINT` write `signal` and exit
  `128 + signal`.

How gc's input reaches it: the pack types gc's start `nudge` once the
`soak> ` prompt shows (the first turn); hc types text, then submits with
Enter, so a multi-line turn arrives as several lines within a second. gc
composes every first turn as its beacon line, a blank line, then the
rendered prompt (`SOAK-FIRST-TURN <agent>`, section 8). So each beacon
line is one first turn typed: the first turn is the first input burst
(lines less than 1 s apart) of an incarnation that contains a beacon line,
and a second beacon line is a second first turn however soon it follows
(the pack re-sends a first turn the box refused as unavailable after
0.5 s, inside the same burst); the marker is a second check. This holds for
any agent the city runs on the scripted provider, including the bd pack's
maintenance pool (`dog`), whose own prompt follows the beacon.

### 7.2 Load (`soak load`, user service `soak-load`)

Reads `$SOAK_DATA/load.json`; skips its turn while `$SOAK_DATA/PAUSE` exists
or `gc status --json` does not show the city running. Every action runs with
`cwd=$SOAK_CITY`, a 120 s timeout, and writes one `load.jsonl` record (time,
action, argv, exit code, duration, parsed JSON or output tail).

| Action | Command | Bring-up and drills | Soak |
|---|---|---|---|
| fan-out workflow | `gc sling soak-burst soak-run --formula --var run=<seq> --json` (records `workflow_id`) | every 180 s | every 30 s |
| always-on workflow | `gc sling soak-steady soak-pulse --formula --var run=<seq> --json` | every 180 s | every 60 s |
| nudge | `gc session nudge <id> "SOAK-NUDGE <32 hex>" --delivery <mode> --json` to a running `soak-steady` session from `gc session list --json --template soak-steady`, chosen by a seeded generator | every 300 s | every 120 s |

Nudge modes are `wait-idle` 80%, `immediate` 10%, `queue` 10%. Targets are
always-on sessions only, so a nudge never races a pool session's drain.

### 7.3 Death probes (`soak probe`, timer `soak-probe`, soak only)

Every 30 minutes it takes the next running `soak-steady` session (round
robin by session id), finds its live incarnation from the agent log (pid and
start ticks match `/proc`, comm `soak-agent`, `GC_SESSION_ID` and
`GC_CITY_PATH` in its environment), writes a `probe-kill` fault record, and
sends it `SIGKILL`. The next `boot` of that session gives the
death-to-restart latency. 48 samples, 24 per reconciler.

### 7.4 Samples (`soak sample`, user service `soak-sample`)

Every 60 s, one `samples.jsonl` record:

- `t` and `mono_ns` (to place the trace's monotonic stamps);
- the phase;
- supervisor: `MainPID` of `gascity-supervisor.service`, its
  `utime+stime+cutime+cstime` ticks (gc's controller tree: the pack ops and
  bd calls it spawns and reaps are in `cutime`/`cstime`), RSS;
- core and holders: from `server.status` over the city's socket (`HcRpc`):
  pids, version, each one's RSS, CPU ticks and cgroup unit;
- programs: the processes whose parent is a holder of the city's core (the
  live boxes), by command name;
- store: every `db-proxy-child` process and its `dolt sql-server` child of
  this user: pid, start ticks, cgroup, RSS, and whether its environment
  carries `HC_SCOPE`;
- `usage_usec` of `user@<uid>.service` (all of this user's CPU);
- every five minutes, the bytes under `R` and under the city's hc state
  directory, the city's `.gc` directory and its `.beads` directory, and the
  events mirror's size; memory available; free disk.

### 7.5 The per-op trace (`bin/soak-optrace.bt`, root unit `soak-optrace`)

```text
#!/usr/bin/env bpftrace
/* soak-optrace.bt <entry>: one line per runtime-pack op process.
 *   B <mono_ns>                                         trace started
 *   E <mono_ns> <pid> <ppid> <parent comm> <argv...>    the op was exec'd
 *   X <mono_ns> <pid> <exit_code> <wall_ms> <cpu_us>    the op exited
 * exit_code is the kernel's: low 7 bits the killing signal, else status << 8. */
BEGIN { printf("B %llu\n", nsecs); }
tracepoint:syscalls:sys_enter_execve /str(args.filename) == str($1)/
{
  @start[pid] = nsecs;
  printf("E %llu %d %d %s ", nsecs, pid, curtask->real_parent->tgid, curtask->real_parent->comm);
  join(args.argv);
}
tracepoint:sched:sched_process_exit /@start[pid] && pid == tid/
{
  printf("X %llu %d %d %llu %llu\n", nsecs, pid, curtask->exit_code,
         (nsecs - @start[pid]) / 1000000, (curtask->utime + curtask->stime) / 1000);
  delete(@start[pid]);
}
END { clear(@start); }
```

```ini
# systemd/system/soak-optrace.service
[Unit]
Description=herdr-core soak: per-op exec/exit trace
[Service]
Environment=BPFTRACE_STRLEN=128
ExecStart=/usr/bin/bpftrace /home/soak/soak/bin/soak-optrace.bt /home/soak/packs/runtime-herdr-core/assets/bin/gc-runtime-herdr-core
StandardOutput=append:/home/soak/soak-data/optrace/optrace.log
StandardError=append:/home/soak/soak-data/optrace/optrace.err
UMask=0022
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
```

gc execs the pack's declared command by its absolute path, so the filter
sees every op gc and its CLIs run; pack commands and doctor checks reach the
entry through `commands/*/run.sh` and `doctor/*/run.sh` under another path
and are not counted. An op is *controller-spawned* when its `ppid` is the
supervisor's `MainPID` of that minute. If the installed bpftrace rejects
`args.filename`, use `args->filename` (and `args->argv`). After phase 1's
`gc start`, `E` lines naming `observe`, `inventory` or `start` must appear
within two minutes; if none do, the city execs another path: read it from
`ps -o args` of a running op and put it in the unit's `ExecStart`.

### 7.6 Analyses (`lib/soakanalysis.py`, unit-tested on synthetic logs)

- **Incarnations**: from `boot` records, keyed by `inc`; alive when `/proc/<pid>/stat`
  has the same start ticks and the boot id matches; otherwise its end is its
  last record.
- **First turns**: input bursts are `in` records less than 1.0 s apart. The
  first turn is the first burst with a beacon line; its latency and marker
  come from that burst. *Exact*: exactly one beacon line in the incarnation.
  *Lost*: no beacon line, and the incarnation has lived 180 s or more
  (alive, or ended 180 s or more after boot), unless a fault record ended it
  earlier. *Duplicated*: two or more beacon lines in one incarnation, in one
  burst or in several (a re-send 0.5 s after the first lands in the first's
  burst). *Short-lived*: ended within 180 s with no first turn and no fault
  record (reported, not a loss). A duplicated verdict comes with the second
  beacon line, a lost one 180 s after boot; AP4 judges it, and the report
  counts it (S1, S2), by that time.
- **Nudges**: a `load.jsonl` nonce whose CLI result was delivered or queued
  must appear in exactly one `in` record of that session's agent log within
  15 minutes of its send (the record's `t`, when the command returned, less
  its `dur_s`). *Lost*: none. *Duplicated*: more than one.
- **Message ops**: `op.changed` events in the mirror whose `op.kind` is
  `message`, last post-image per op id. *Unconfirmed*: a closed op with
  `maybe_delivered > 0`, or `attempt > 1`, or `outcome.reason` or
  `outcome.result.delivery.ack` containing `unconfirmed`.
- **Op trace**: pairs `E`/`X` by pid, maps `mono_ns` to wall time with the
  samples' pairs, and gives per-minute spawns (all, controller-spawned, by
  op = `argv[1]`), wall latency and CPU per op, and ops ended by a signal,
  classed by who ended them. *closed*: `watch-startup` ended by SIGKILL
  before its deadline less 1 s (gc ends every startup watch that way, one
  per start of an agent whose provider lists `process_names` or sets
  `accept_startup_dialogs`).
  *canceled*: SIGTERM before gc's timeout for the op less 1 s (a caller
  stopped waiting, or a session's `stop` ended an op its own gc command
  started). *overrun*: SIGTERM, or SIGKILL on `watch-startup`, at or past
  that point. *killed*: SIGKILL on
  any other op (it outlived gc's 2 s grace, or something else killed it).
  *other*: any other signal. gc's timeouts: 30 s; 120 s for start,
  provision and watch-startup (it runs under the start deadline); 4 s for
  observe and is-attached. A window has op figures only when the trace was
  read, the samples place its clock, and it started (a `B` line) at or
  before the window did; otherwise they are unknown, with the reason. A
  trace that is missing, unreadable, never started or started late is no
  evidence of zero ops. The trace's stamps carry no boot id and the trace
  spans F10's reboot, so a `B` line of an earlier boot counts as a start
  too: a trace that did not run in the samples' boot can still read as no
  ops.
- **Orphans**: a process of this user whose environment carries
  `GC_INSTANCE_TOKEN=T` and the city's `GC_CITY_PATH`, older than the
  window asked for, where no live box carries `T` (a box is a process whose
  parent is a holder of the city's core), and which is neither
  infrastructure nor under infrastructure (gc's infrastructure argv:
  argv[1] `db-proxy-child` or `__gc-managed-dolt-scope-watchdog`, `nudge
  poll`, and their descendants; the watchdog never runs in the default-store
  city, it is listed to match gc).
- **hc runtime**: processes with command name `herdr-core` (or marked
  `HC_RUNTIME=1`) whose argv names `serve` or `hold`; their
  `XDG_STATE_HOME` and `HC_SESSION` say whose they are.

### 7.7 The units

```ini
# soak-sample.service (soak-load.service is the same with `load`, Restart=on-failure)
[Unit]
Description=herdr-core soak: 60 s sampler
[Service]
EnvironmentFile=%h/soak-data/current/soak.env
ExecStart=%h/soak/bin/soak sample
Restart=always
RestartSec=10
[Install]
WantedBy=default.target

# soak-check.service
[Unit]
Description=herdr-core soak: predicates
[Service]
Type=oneshot
EnvironmentFile=%h/soak-data/current/soak.env
ExecStart=%h/soak/bin/soak check
# an abort captures and stops the city inside this one run (a failed gc stop is run again by every later run)
TimeoutStartSec=3600

# soak-check.timer (soak-probe.timer is the same with OnActiveSec=30min, OnUnitActiveSec=30min)
[Unit]
Description=herdr-core soak: predicates every 5 minutes
[Timer]
OnActiveSec=5min
OnUnitActiveSec=5min
AccuracySec=5s
[Install]
WantedBy=timers.target
```

## 8. The city

`soak city-init <name> --steady N --burst M --mode warn|abort --load bringup|soak`
does exactly this, as `soak`, and stops at the first failure:

1. `install -d -m 0700` the data directories; write `canary`
   (`"soakcanary" + secrets.token_hex(16)`), `soak.env`, `load.json` (the
   `--load` column of section 7.2), `phase` (`bringup`); point
   `~/soak-data/current` at it.
2. `GC_BEADS_PROXIED_IDLE_TIMEOUT=0 gc init --template empty --skip-provider-readiness --no-start ~/cities/<name>`
   (the variable sets the store's idle timeout wherever init creates the
   store; `city.toml` carries the same value below, so doctor sees no drift).
   gc writes `pack.toml` (with its `core` and `bd` imports) and `city.toml`
   born split: work on the bd-owned Dolt store, the five infrastructure
   classes on one SQLite store under `.gc/store`. Check that `city.toml` has
   `[storage.bindings.infra]` with `provider = "sqlite-beads"`; if gc printed
   that the city starts single-store, stop (wrong bd on `PATH`).
3. Set these keys in `city.toml` with `soak toml-set`, which inserts a key
   under an existing table header or appends the table, and checks the file
   with `tomllib` afterwards:

   ```toml
   [workspace]
   provider = "soak"

   [session]
   provider = "herdr-core"

   [daemon]
   session_reconciler = "legacy"   # removed in phase 2
   max_wakes_per_tick = 25         # a holder loss restarts every session in one tick

   [beads]
   proxied_idle_timeout = "0"      # the store never retires on idle, so any Dolt restart is a finding

   [events.mirror]
   path = "/home/soak/soak-data/<name>/gc-events/events.jsonl"
   mode = "0600"
   max_size_bytes = 0
   ```

4. Append to `pack.toml`:

   ```toml
   [imports.herdr-core]
   source = "/home/soak/packs/runtime-herdr-core"

   [providers.soak]
   display_name = "Soak scripted agent"
   command = "/home/soak/soak/bin/soak-agent"
   prompt_mode = "none"
   ready_prompt_prefix = "soak> "
   process_names = ["soak-agent"]

   [providers.soak.env]
   SOAK_DATA = "/home/soak/soak-data/<name>"   # every agent on the provider, the bd pack's `dog` too
   ```

5. Write the city's own pack files:

   `agents/soak-steady/agent.toml` (always-on pool; N is 3 for phases 1 to
   3 and 6 for the soak):

   ```toml
   provider = "soak"
   prompt_template = "assets/prompts/soak.template.md"
   work_dir = ".gc/agents/{{.AgentBase}}"
   min_active_sessions = N
   max_active_sessions = N

   [env]
   SOAK_ROLE = "steady"
   SOAK_DATA = "/home/soak/soak-data/<name>"
   SOAK_CANARY_TOKEN = "<canary>"
   ```

   `agents/soak-burst/agent.toml` (demand pool; M is 2, then 10): the same
   with `min_active_sessions = 0`, `max_active_sessions = M`,
   `SOAK_ROLE = "burst"` and `SOAK_DRAIN_IDLE_S = "60"`.

   `assets/prompts/soak.template.md`, one line:

   ```text
   SOAK-FIRST-TURN {{ .AgentName }}
   ```

   `formulas/soak-run.toml`:

   ```toml
   formula = "soak-run"
   description = "Soak load: a fan-out of deterministic scripted steps."

   [requires]
   formula_compiler = ">=2.0.0"

   [vars.run]
   description = "Load-generator run label."
   default = "manual"

   [[steps]]
   id = "prepare"
   title = "soak {{run}} prepare"

   [[steps]]
   id = "work-a"
   title = "soak {{run}} work-a"
   needs = ["prepare"]

   [[steps]]
   id = "work-b"
   title = "soak {{run}} work-b"
   needs = ["prepare"]

   [[steps]]
   id = "work-c"
   title = "soak {{run}} work-c"
   needs = ["prepare"]

   [[steps]]
   id = "collect"
   title = "soak {{run}} collect"
   needs = ["work-a", "work-b", "work-c"]
   ```

   `formulas/soak-pulse.toml`:

   ```toml
   formula = "soak-pulse"
   description = "Soak load: one deterministic step for an always-on session."

   [requires]
   formula_compiler = ">=2.0.0"

   [vars.run]
   description = "Load-generator run label."
   default = "manual"

   [[steps]]
   id = "pulse"
   title = "soak {{run}} pulse"
   ```

6. `cd ~/cities/<name> && gc config show --validate`, then
   `gc herdr-core install` (the pack's pinned installer: manifest and pin
   must agree, sha256 checked before anything is written, read-only install
   under `~/.local/share/gc-runtime-herdr-core/hc/0.1.19/`), then
   `gc herdr-core status` (pin, install verified, no core yet), then
   `gc doctor --json > ~/soak-data/<name>/doctor-prestart.json`.

What the city runs: `soak-steady` (N always-on sessions), `soak-burst` (0 to
M sessions on demand; each drains once idle for 60 s), the core pack's
formula `control-dispatcher` (one session, deterministic), and the bd pack's
maintenance pool `dog` (0 to 2 sessions, rarely; it inherits the scripted
provider). Every one of them runs under herdr-core. The store is the default
for a new city at this gc: bd owns a proxied Dolt server (`bd
db-proxy-child` and its `dolt sql-server`), started by the first bd read and
stopped by `gc stop`.

## 9. Phase 1: bring-up (legacy reconciler)

As `soak`, with the harness in warn mode. `~/soak/bin/soak-phase1` runs this
section's two blocks end to end and stops at the first failure
(`SOAK_BRINGUP_LOAD_S` overrides the 30 minutes of load); the commands are:

```bash
~/soak/bin/soak city-init hc-bringup --steady 3 --burst 2 --mode warn --load bringup
systemctl --user is-active gascity-supervisor.service || gc supervisor install
gc start ~/cities/hc-bringup
~/soak/bin/soak wait --steady 3 --first-turns --timeout 600
~/soak/bin/soak placement > ~/soak-data/hc-bringup/placement.json
cd ~/cities/hc-bringup
r1=$(gc sling soak-burst soak-run --formula --var run=bringup-1 --json | jq -r .workflow_id)
r2=$(gc sling soak-steady soak-pulse --formula --var run=bringup-2 --json | jq -r .workflow_id)
~/soak/bin/soak wait --workflows "$r1,$r2" --timeout 900          # each root closed (gc bd show <id> --json)
systemctl --user enable --now soak-sample.service soak-load.service soak-check.timer
sleep 1800                                                          # 30 minutes of bring-up load
```

Then the conformance run, against a scratch state root while the city runs:

```bash
snap=$(~/soak/bin/soak snapshot)                 # core pid, holders, every box's pid and start ticks
S=$(mktemp -d /tmp/hcconf.XXXXXX) && install -d -m 0700 "$S/state" && cd "$S"
touch ~/soak-data/hc-bringup/CONFORMANCE         # soak check skips the foreign-core predicate meanwhile
E=~/packs/runtime-herdr-core/assets/bin/gc-runtime-herdr-core
GC_EXEC_STATE_DIR="$S/state" gc runtime check "$E" > ~/soak-data/hc-bringup/runtime-check.txt 2>&1; echo "check=$?"
GC_EXEC_STATE_DIR="$S/state" gc runtime conformance --json "$E" \
  > ~/soak-data/hc-bringup/conformance.json 2> ~/soak-data/hc-bringup/conformance.err; echo "conformance=$?"
~/soak/bin/soak conf-teardown "$S/state"
cd ~ && rm -rf "$S" && rm -f ~/soak-data/hc-bringup/CONFORMANCE
~/soak/bin/soak snapshot --compare "$snap"
jq '{ok, v2_ready, failed: [.results[] | select((.status|ascii_downcase) == "fail") | .code]}' \
  ~/soak-data/hc-bringup/conformance.json
cd ~/cities/hc-bringup && gc doctor --json > ~/soak-data/hc-bringup/doctor.json; echo "doctor=$?"
```

`soak conf-teardown <root>`: for each `<root>/herdr-core/*/core.lock`, runs
`<pinned hc> server stop` with that core's tuple (`HC_SESSION` = the
directory name, `HC_SOCKET` = the lock's content, `XDG_STATE_HOME` = the
root, `XDG_CONFIG_HOME` = `<root>/hc-config`, the user's runtime directory
and bus); waits up to 15 s until no `herdr-core` process has that
`XDG_STATE_HOME`; then checks that every `core.lock` is free
(`flock --nonblock <lock> true` succeeds) and that the `hc-serve-*` and
`hc-hold-*` units those processes ran in are gone. A survivor is named,
killed by pid after the ownership check, and fails B4.

Pass criteria:

| ID | Criterion | Source |
|---|---|---|
| B1 | `gc doctor --json` reports `failed == 0`, before start and running; every `warning` result is listed in the report with a one-line reason | `doctor-prestart.json`, `doctor.json` |
| B2 | `gc runtime check` exits 0; `gc runtime conformance --json` exits 0 with `ok`, `v2_ready == true` and no failed requirement | `runtime-check.txt`, `conformance.json` |
| B3 | both workflows' roots are closed within 15 minutes of the sling | `soak wait`, `load.jsonl` |
| B4 | after the teardown: no `core.lock` of the scratch root is held, no hc process or unit of it remains, the root is gone; the city's core pid and every box are unchanged by the conformance run (`soak snapshot --compare` lists the boxes of every session outside the always-on pool (the demand pool, the formula dispatcher, the maintenance pool), which gc starts and retires with the load, apart as `demand_churn` and does not judge them) | `soak conf-teardown`, `soak snapshot --compare` |
| B5 | every scripted incarnation so far has exactly one first turn | `soak report --first-turns` |
| B6 | the core runs in an `hc-serve-*.service`, holders in `hc-hold-*.service`; each agent runs in a `run-*.scope` under `gascity-agents.slice` with no `HC_SCOPE`; the supervisor runs in `gascity-supervisor.service`; doctor's `hc-scope-hygiene` passes | `placement.json`, `doctor.json` |
| B7 | 30 minutes of bring-up load with no predicate hit | `check.log` |

First-use checks of this phase (each names what to do when it fails): the
events mirror grows (else fix `[events.mirror]` and restart the city);
`op.changed` events with `op.kind == "message"` appear after the first
nudge (else nudges run on the legacy queue: count them from
`worker.operation` events whose `operation` is `nudge` and say so in the
report); `gc sling --json` names a `workflow_id`; `gc hook --claim --json`
from an agent returns `action` and `bead_id` (see the agent logs); the op
trace shows the city's ops.

## 10. Phase 2: switch to the v2 reconciler

`~/soak/bin/soak-phase2 hc-bringup v2-switch --drill` runs this block
(`SOAK_V2_SETTLE_S` overrides the 30 minutes before the drill):

```bash
cd ~/cities/hc-bringup
~/soak/bin/soak phase v2-switch
gc doctor --check exec-runtime-identity --check ownerless-runtimes --check daemon-session-reconciler --json \
  > ~/soak-data/hc-bringup/v2-before.json
snap=$(~/soak/bin/soak snapshot)
~/soak/bin/soak toml-del city.toml daemon session_reconciler
~/soak/bin/soak note operator supervisor-restart "switch to the v2 reconciler"
systemctl --user restart gascity-supervisor.service       # the unit preserves sessions on SIGTERM
sleep 90
gc supervisor logs -n 50000 | grep -F "city 'hc-bringup': session reconciler: v2 (default: session_reconciler is unset)"
gc doctor --check exec-runtime-identity --check ownerless-runtimes --check daemon-session-reconciler --json \
  > ~/soak-data/hc-bringup/v2-after.json
~/soak/bin/soak snapshot --compare "$snap"                # which boxes v2 adopted, which it restarted
sleep 1800
~/soak/bin/soak drill agent-kill                          # one restart through v2
```

| ID | Criterion |
|---|---|
| V1 | the supervisor log names the city with `session reconciler: v2 (default: session_reconciler is unset)` (and the warning that the exec runtime's handshake chose v2, disclosed) |
| V2 | `exec-runtime-identity` and `ownerless-runtimes` name no Ownerless or Unknown box, before and after |
| V3 | restarts converge: within 10 minutes every configured session runs, each restarted at most once since the switch; none restarts in the following 20 minutes; no `session.quarantined` event |
| V4 | the agent-kill drill passes (section 11, F6) |
| V5 | every incarnation since the switch has exactly one first turn |

## 11. Phase 3: fault drills

On `hc-bringup` (v2, 3 always-on sessions, burst pool up to 2, load on,
harness in warn mode). Start with `~/soak/bin/soak phase drills`. Run the
drills in this order, at least 20 minutes
apart when a drill ends sessions (gc quarantines a session that starts more
than five times in an hour). `soak drill <name>` takes the drill lock
(`~/soak-data/<city>/DRILL`, which `soak check` honours), records the state
before, injects (writing a `faults.jsonl` record that names what the fault
may end before it signals), measures, waits 10 minutes (`--settle <s>`
changes it), scans for orphans, and writes `drills/<name>-<time>.json` with
each criterion's measured value and verdict. F10 is two steps:
`soak drill reboot` records the state before and keeps the drill lock across
the reboot; after root's `systemctl reboot`, `soak drill reboot-verify`
measures and releases the lock.

The raw commands each drill wraps, run from the city directory:

```bash
eval "$(gc herdr-core status --env | sed 's/^/CORE_/')"   # CORE_HC_SESSION, CORE_HC_SOCKET, CORE_XDG_STATE_HOME, CORE_XDG_CONFIG_HOME
HC=$HOME/.local/share/gc-runtime-herdr-core/hc/0.1.19/herdr-core
hcenv=(env -i HOME="$HOME" USER="$USER" LOGNAME="$USER" LANG=C.UTF-8 PATH="$(dirname "$HC"):/usr/local/bin:/usr/bin:/bin"
       XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"
       HC_SESSION="$CORE_HC_SESSION" HC_SOCKET="$CORE_HC_SOCKET"
       XDG_STATE_HOME="$CORE_XDG_STATE_HOME" XDG_CONFIG_HOME="$CORE_XDG_CONFIG_HOME")
~/soak/bin/soak hc-status        # server.status on CORE_HC_SOCKET: core pid, version, holder pids
~/soak/bin/soak store            # the store's proxy and Dolt: pid, start ticks, cgroup, HC_SCOPE, session
```

Before signalling a pid, `soak drill` checks: command name `herdr-core` with
argv `hold` or `serve` and `XDG_STATE_HOME=$CORE_XDG_STATE_HOME` (holder,
core); `soak-agent` with the city's `GC_CITY_PATH` (agent); argv[1]
`db-proxy-child` with the city's `GC_CITY_PATH` in its environment or the
city's `.beads` in its arguments (store proxy).

A fault that does not land ends the drill with verdict `error`, never a
pass: a refused signal (the check above fails, or the pid is gone or reused),
a holder `soak hc-status` lists that is not running, or a `systemctl kill`
that exits non-zero stops the drill where it happens. Each drill that
signals also judges that its fault took effect: every store proxy F1
signalled is gone (`F1-killed`), every holder F2 or F3 killed is gone
(`F2-killed`, `F3-killed`), and the core F4 killed is gone (`F4-killed`), so
the core that answers is a new one.

Criteria every drill also checks (C1 to C6):

| ID | Criterion |
|---|---|
| C1 | `gc beads health --json` passes after the drill; the store's proxy and Dolt pids are the ones before the drill (except F1, F9 and F10, which restart or stop the store by design) |
| C2 | every always-on session the drill ended runs again (a new incarnation's `boot`, or `running` in `gc session list --json`) within 2 × patrol (60 s) + 10 s of the injection. The core pack's formula dispatcher is a demand session (`max_active_sessions = 1`, no minimum; B4 counts it as demand churn): gc closes a dead one and starts a fresh session, under a new id, when work needs it, so the time until a dispatcher box runs again is recorded (`C2-dispatcher`), not judged |
| C3 | every background child of every ended incarnation is gone within 1 × patrol (30 s) + 10 s of the injection |
| C4 | 10 minutes after the injection, `soak orphans` finds no orphan |
| C5 | every always-on session the drill ended has a new incarnation with a `boot` record; every new incarnation has exactly one first turn; no surviving incarnation got a second; no live scripted agent of the city (command name `soak-agent`, the city's `GC_CITY_PATH`) has run 60 s or more without the `boot` record of its incarnation. C5 judges the incarnations born after the injection and before C5 starts, and every new one of an ended session; it waits up to 180 s + 10 s from its start for a missing incarnation or a first turn still pending (7.6). One still missing or pending then fails C5, as does a drill that ended no always-on session: it has nothing to judge |
| C6 | no `herdr-core` serve or hold process except the city's (same `XDG_STATE_HOME` and `HC_SESSION`); no start refused because the core "was started outside the pack" in the supervisor log since the injection (other failed starts are listed with their reasons) |

| Drill | Injection (raw) | Drill-specific pass criteria |
|---|---|---|
| F1 `place-store` | write `bd-touch-after <proxy pid> <start> <dolt pid> <start>` to one always-on agent's `cmd` file, then `kill -TERM <proxy pid>`; if the old Dolt still runs 30 s after its proxy ended, `kill -TERM` it too (recorded); the agent's bd read restarts the store from inside the agent's scope; repeat (at most 3 times) until the new store lands there | the new proxy and Dolt run in that agent's `run-*.scope` under `gascity-agents.slice`, carry no `HC_SCOPE`, and pass `gc beads health`; record their pids for F2 and F3; every proxy signalled is gone. If the controller restarts the store first every time, record that and run F2/F3 on the controller-placed store |
| F2 `holder-kill` (K1) | `kill -KILL <holder pid>` for each holder `soak hc-status` lists | every holder killed is gone; C1 to C6; the store pids recorded in F1 are unchanged (it ran inside a now-dead agent's scope); the controller pid is unchanged |
| F3 `holder-unit-kill` (K2) | `unit=$(awk -F/ '{print $NF}' /proc/<holder pid>/cgroup)`; check it matches `hc-hold-*.service` or `.scope`; `systemctl --user kill --kill-whom=all --signal=SIGKILL -- "$unit"` | as F2 (a cgroup-wide kill, as systemd-oomd would do; the agents and the store are outside the holder's cgroup) |
| F4 `core-kill` | `kill -KILL <core pid>` | the killed core is gone and a core answers again within 30 s; no box ends (every box pid and start ticks unchanged); a later start is not refused as foreign (F6 after it passes); C1, C4, C6 |
| F5 `core-restart` | `"${hcenv[@]}" "$HC" server restart` | every box unchanged; the core pid changed, its version did not; `gc herdr-core status` says `started: by the pack`; C1, C4, C6 |
| F6 `agent-kill` | `kill -KILL <agent pid>` (from its `boot` record) | C2 to C5 for that session |
| F7 `hc-update` | `"${hcenv[@]}" "$HC" update; echo $?` | exits non-zero (the binary and its directory are read-only); `gc herdr-core status` still says `installed: ... (matches the pin)`; the core's version and pid unchanged; every box unchanged |
| F8 `upgrade` | write the 0.1.20 pin (below) over `~/packs/runtime-herdr-core/assets/hc-pin.json`; `gc herdr-core upgrade` | prints `handed the city's core over from herdr-core 0.1.19 to 0.1.20; its sessions kept running`; every box unchanged; `gc herdr-core status` runs 0.1.20, `started: by the pack`; then F6 on one agent passes under 0.1.20 |
| F9 `stop-wedged` | `kill -STOP <core pid>`; `timeout 900 gc stop ~/cities/hc-bringup; echo $?`; `kill -CONT <core pid>`; `gc stop ~/cities/hc-bringup; echo $?`; restore the pin: `git -C ~/src/gascity-packs show "$(cat ~/packs/runtime-herdr-core.COMMIT)":runtime-herdr-core/assets/hc-pin.json > ~/packs/runtime-herdr-core/assets/hc-pin.json`, then `(cd ~/packs/runtime-herdr-core && sha256sum --quiet -c ../runtime-herdr-core.SHA256SUMS)`; `gc start ~/cities/hc-bringup` | the first stop exits non-zero and names the wedged runtime (gc at the pinned commit says the runtime `did not answer a listing ... (a wedged runtime server?)`; a server teardown failure counts too); the second prints `City stopped.` and exits 0, after which no box, holder or core of the city runs; after `gc start` the core runs 0.1.19 and every session is back (C2 and C5 measured from the start) |
| F10 `reboot` | as root: `systemctl reboot`; then as `soak`: `~/soak/bin/soak drill reboot-verify` | within 10 minutes of SSH answering: the supervisor, the city and every configured session run, each with a new incarnation and exactly one first turn; `gc beads health` passes; no orphan; doctor's `exec-runtime-identity` and `ownerless-runtimes` are clean; C6 |

The 0.1.20 pin for F8, written over the pack copy's `assets/hc-pin.json`
for this drill only (it is not a pin bump of the pack):

```json
{
  "version": "0.1.20",
  "generation": 1,
  "min_version": "0.1.19",
  "tested": ["0.1.19", "0.1.20"],
  "releases": "https://releases.herdr.dev/core",
  "binary": "herdr-core",
  "targets": {
    "linux-x86_64":  {"asset": "herdr-core-linux-x86_64.tar.gz",  "sha256": "ac6b86890c451a37584620aaa438b71bc0d0bd430a2e7c1d7e095f052c414e74"},
    "linux-aarch64": {"asset": "herdr-core-linux-aarch64.tar.gz", "sha256": "5f3037379d15cc76cfc72d2fd1a4262ea1c5b24df278bf7cfd8adcff7b914862"},
    "macos-aarch64": {"asset": "herdr-core-macos-aarch64.tar.gz", "sha256": "e58985d3fef6e909f33d3c5a4426e4898c81564a557d4636591cec9e3a06af26"},
    "macos-x86_64":  {"asset": "herdr-core-macos-x86_64.tar.gz",  "sha256": "36c0331c3ffea0ffaada195b89a3c7496f7f3fc5bf35e4605c19c84e5c205a56"}
  }
}
```

These sha256 values are the 0.1.20 release manifest's; `gc herdr-core
upgrade` checks the manifest against the pin and the archive against the
pin again before it writes anything.

After F10, stop the drill city before phase 4:

```bash
systemctl --user stop soak-load.service soak-check.timer soak-sample.service
gc stop ~/cities/hc-bringup
~/soak/bin/soak report --city hc-bringup --markdown > ~/soak-data/hc-bringup/report.md
```

## 12. Phase 4: the 24-hour soak

Setup (a fresh city, same configuration, soak scale, harness in abort
mode); `~/soak/bin/soak-phase4 start` runs it, `~/soak/bin/soak-phase2 hc-soak
soak-v2` is the switch at T0 + 12 h, and `~/soak/bin/soak-phase4 end` the
last row of the timeline:

```bash
~/soak/bin/soak city-init hc-soak --steady 6 --burst 10 --mode abort --load soak
gc start ~/cities/hc-soak
~/soak/bin/soak wait --steady 6 --first-turns --timeout 900
~/soak/bin/soak phase soak-legacy
systemctl --user enable --now soak-sample.service soak-load.service soak-check.timer soak-probe.timer
~/soak/bin/soak note operator soak-start "T0"
```

Timeline (T0 is the `soak-start` note):

| When | Action |
|---|---|
| T0 to T0 + 12 h | legacy reconciler. `soak check` every 5 minutes, digest hourly, probes every 30 minutes |
| T0 + 12 h | switch to v2 under load: `soak-phase2 hc-soak soak-v2` runs phase 2's commands on `hc-soak` (`soak phase soak-v2`, `toml-del`, the operator note, the supervisor restart, V1 to V3 checked, no agent-kill drill); it pauses `soak-probe.timer` from the snapshot before the restart to the snapshot after it, so a probe kill cannot read as a box v2 ended, and reads 50000 supervisor log lines for V1 because 500 cover well under the 90 s wait at soak log volume |
| T0 + 12 h to T0 + 24 h | v2 |
| T0 + 24 h | `soak phase soak-end`; stop `soak-load` and `soak-probe.timer`; wait 15 minutes; `soak check --final` (all predicates, the secrets grep and the orphan scan once more); `gc doctor --json > doctor-final.json`; `soak report --city hc-soak --markdown > report.md`; `soak note operator city-stop`; `gc stop ~/cities/hc-soak`; then `soak final-scan` (the secrets grep of `R` once more and the check that no box, holder or core of the city runs) |

During the soak nothing else runs against the city: no manual nudges, no
config edits but the scheduled switch, and no doctor runs but the one
`soak check` makes every 6 hours (its errors are warnings in the digest).

**Watching.** The orchestrating session (section 1.1) reads, about every
30 minutes, the last line of `check.log`, whether `ABORTED` exists, and the
last digest, and tells the task owner on an abort or at the end:

```bash
soakssh "soak@$SOAK_VM" 'tail -n 1 ~/soak-data/current/check.log; cat ~/soak-data/current/ABORTED 2>/dev/null; true'
soakssh "soak@$SOAK_VM" 'tail -n 40 ~/soak-data/current/digest.log'
```

On `ABORTED`, the task owner is told at once and nothing is restarted.

Soak pass criteria (both halves unless stated):

| ID | Criterion | Target |
|---|---|---|
| S1 | lost first turns, each in the half its verdict came in (7.6), whatever phase its incarnation booted in; a verdict in `soak-end`, the settle that still runs v2, is the v2 half's | 0 |
| S2 | duplicated first turns, each in the half its verdict came in: a steady session booted before `soak-legacy` and typed its first turn again after the switch is the v2 half's, as is one typed again in `soak-end` | 0 |
| S3 | Dolt or proxy restarts, and any other infrastructure process killed | 0 |
| S4 | unconfirmed message ops / closed message ops | < 1% |
| S5 | controller-spawned pack ops per second per session, phase mean; `unknown` unless the op trace ran from the half's start (7.6), so a missing, unreadable or late trace does not read as no ops (one with only an earlier boot's lines still can, 7.6) | ≤ 0.30 legacy, ≤ 0.05 v2 |
| S6 | core RSS: every hourly median within ±20% of hour 2's median | yes |
| S7 | no abort predicate hit (AP5 is record-only, section 1.1); `unknown` when the half had no check run or one without a status; the v2 half's takes in the check runs of `soak-end`, `check --final` among them, so a hit there is a `no` and a run without a status there is `unknown` | yes |
| S8 | recorded: per-op spawn rate, p50/p95/p99 op latency and CPU per op, controller-tree CPU, death-to-restart latency (n, p50, p95, max), for each reconciler | recorded |

Also reported with target 0, as warnings, not abort predicates: nudges lost
or typed twice, orphans at the hourly scans, short-lived incarnations,
unexplained core restarts or holder losses, ops killed, ended by another
signal or overrun (a `watch-startup` closed by gc and a canceled op are
expected), spawn files older than 5 minutes, workflows open after 30 minutes.

## 13. Abort predicates and the abort procedure

`soak check` evaluates every predicate every 5 minutes. In `abort` mode
(phase 4) any hit aborts at once; in `warn` mode it is logged. AP5 is
record-only for Soak 1 (section 1.1): it never hits, warns with its numbers
when over its limit, and its unreadable inputs do not count towards AP9. Each run
appends one record to `check.jsonl` and one line to `check.log`
(`<time> <phase> OK|WARN|HIT <ids> <reason>`). Budgets use `n`, the mean
number of live boxes in the window (at least 1).

| ID | Predicate | Source | Hit when |
|---|---|---|---|
| AP1 | store outage or integrity error | `gc beads health --json` (60 s timeout) | 3 consecutive failures 30 s apart; or one failure naming the catalog, the branch head, corruption, a checksum or integrity |
| AP2 | an infrastructure process killed | the supervisor's `MainPID`, every store proxy and Dolt pid and start ticks, from the previous run | one of them is gone and no `faults.jsonl` record covers it (the planned supervisor restart, the drills) |
| AP3 | controller crash loop | `NRestarts` and `MainPID` changes of `gascity-supervisor.service`, `controller.started` events | more than 3 controller starts in 15 minutes not covered by a fault record |
| AP4 | a lost or duplicated first turn | 7.6 first turns | any whose verdict came in the phase or since the previous run, whatever phase its incarnation booted in (a session that survives the switch and is typed its first turn again after it is the new phase's); `--final`: any, of every incarnation |
| AP5 (record-only) | pack cost over twice the budget | op trace, samples | over the last 15 minutes, controller-spawned ops per second above 2 × 0.30 × n (legacy) or 2 × 0.05 × n (v2), or controller-spawned op CPU above 2 × 0.015 × n cores |
| AP6 | state size | samples | the city's hc state directory above 2 GiB, or `R` above 4 GiB, each judged on its own; unknown while the last size sample lacks either, even when the other hits |
| AP7 | an unexpected core or holder | 7.6 hc runtime | a `herdr-core` serve or hold process whose `XDG_STATE_HOME` or `HC_SESSION` is not the city's, or two cores of the city (skipped while `CONFORMANCE` exists) |
| AP8 | a secret on disk (hourly) | the canary | the canary in any regular file under `R`, under `~/.local/share/gc-runtime-herdr-core` or under `/tmp/gc-herdr-core-<uid>` |
| AP9 | the harness cannot see | every predicate's inputs | a predicate cannot be evaluated (stale samples, a trace silent for 10 minutes while boxes run, a silent events mirror, a failed probe, an agent log missing, a state size missing) on 3 consecutive runs |

**Fault records and what they cover.** Every `faults.jsonl` record carries
`covers`, the infrastructure it may end: `supervisor`, `controller`,
`store`, `core`, `holder`, or `all`. AP2, AP3 and the core and holder
warnings excuse a change only when a record covering it falls between the
previous run and this one. `soak note operator supervisor-restart` covers
the supervisor, the controller and the store; `city-stop`, `city-start` and
`reboot` notes cover everything; each drill names its own. While `DRILL`
exists AP2 and AP5 are not judged, and AP7's foreign-core part is skipped
while `CONFORMANCE` exists. A predicate whose inputs cannot be read counts
towards AP9 and shows as `WARN` until then. AP4 cannot be evaluated while
`agents/` is missing, or while a live scripted agent of the city (command
name `soak-agent`, the city's `GC_CITY_PATH`) that has run for 60 s or more
has no `boot` record of its incarnation in the agent logs: the agent writes
that record before it reads any input. The other sessions' first turns are
still judged.

Warnings (logged and in the digest, never an abort): orphans older than 10
minutes; any tmux server of this user; outside phase 1 to 3, fewer than 10
or more than 20 live boxes for 15 minutes; no workflow root closed in 20
minutes while load runs; nudges lost or duplicated; an unexplained core
restart or holder loss; an op ended by a signal gc does not send by design
(killed, other or overrun; closed and canceled are expected, see the op
trace below), naming the ops; a spawn file older than 5
minutes in `/run/user/<uid>/gc-herdr-core/`; memory available under 1 GiB;
free disk under 10 GiB.

**The abort procedure** (`soak check`, on the first hit in `abort` mode):

1. Write `ABORTED` (time, phase, hits). Stop `soak-load` and
   `soak-probe.timer`.
2. Capture first (`soak capture`), into `captures/<time>.tar.gz`:
   `gc trace status`; `gc trace reasons --since 30m`;
   `gc trace show --since 30m --type cycle_result --json`;
   `gc trace show --since 30m --json`; `.gc/runtime/session-reconciler-trace/`;
   `gc supervisor logs -n 2000`; `gc status --json`;
   `gc session list --json --state all`; `gc doctor --json`;
   `gc herdr-core status`; `server.status` over the city socket; every
   `*.log` under the city's hc state directory (the core's and the
   holders'); `ps -eo pid,ppid,lstart,args`; `systemd-cgls --user-unit
   gascity-supervisor.service` and `systemctl --user list-units 'hc-*' --all`;
   the agents' logs; the events mirror; `load.jsonl`, `faults.jsonl`,
   `samples.jsonl`, `check.jsonl`, the op trace. `ABORTED` names the bundle;
   a capture that fails is written there as `capture: FAILED <error>`, and
   the city is stopped all the same.
3. `gc stop` the city (its server teardown ends the city's core); then check
   that no box, holder or core of the city and no process carrying the
   city's `GC_SESSION_ID`s remain, and write both results into `ABORTED`.
   Step 3 runs even when step 1 or 2 fails. `check-state.json` records
   `stopped` once `gc stop` exits 0; until then every later `soak check` run
   runs `gc stop` again, before it collects anything, so a run that then
   fails has still tried, and adds its result to `ABORTED`.
4. The watcher pages the person, who files a work item with the capture.
   The soak restarts from the failed phase only after a fix has landed.

## 14. Metrics

Every number in the report comes from one of these, for each phase window
(and each half of the soak):

| Metric | Definition | Source |
|---|---|---|
| incarnations | `boot` records of scripted agents | agent logs |
| first turns | exact, lost, duplicated, short-lived; latency boot → first turn p50/p95. A lost or duplicated first turn counts in the window its verdict came in, whatever window its incarnation booted in; the others, and the latency, count by boot | 7.6 |
| nudges (load) | sent; CLI delivered, queued, refused; received once, lost, duplicated; latency CLI → received p50/p95 | `load.jsonl`, agent logs |
| message ops | closed total; succeeded by `delivery.ack` (`delivered`, `delivered_unobserved`, other); failed by reason; skipped; canceled; unconfirmed and its ratio | events mirror, `op.changed` |
| store | proxy and Dolt pid changes with their cause; health failures | samples, `faults.jsonl`, `check.jsonl` |
| sessions | starts, restarts by cause (probe, drill, unexplained), quarantines, controller starts, core restarts, holder losses | agent logs, events mirror, samples |
| workflows | slung, closed, open after 30 minutes; sling → root closed p50/p95/max | `load.jsonl`; the root's `bead.closed` event in the events mirror (its time is the close time; every pending root is settled from the one incremental events read of each check) |
| orphans | count at each hourly scan | `soak orphans` |
| pack ops | per second: all, controller-spawned, per session, by op; wall latency p50/p95/p99 and CPU per op; ops ended by a signal, by class (watch-startup closed by gc, canceled, killed, other, overrun) | op trace |
| CPU | controller tree (supervisor incl. reaped children), controller-spawned op CPU, all of this user's CPU (`user@<uid>.service`) | samples, op trace |
| core RSS | hour 2 median (reference), hourly medians, largest deviation; holder RSS | samples |
| sizes | `R`, the city's hc state directory, `.gc`, `.beads`, events mirror | samples |
| death-to-restart | probe kill → the boot that answered it (the killed session's next `boot`, or, when gc replaces the session instead of restarting it, as the legacy reconciler does, the first `boot` of a new session of the same always-on template within 10 minutes of the kill): n, p50, p95, max; under the patrol only, nothing pokes the controller | `faults.jsonl`, agent logs |

Budgets behind S5 and AP5: at most 2 pack spawns per second per 40 sessions
on v2 (0.05 per session); on legacy about 10 to 15 ops per session per 30 s
before gc remembered a runtime's missing `exec` op and read typed input
outcomes, about 40% fewer since (0.30 per session); about 0.6 core per 40
sessions for the legacy patrol's ops (0.015 per session). One op costs
about 15 ms of CPU on a quiet host and 45 ms on a loaded one. These are
estimates made before any soak; the soak's job is to replace them with
measurements.

## 15. Report template

The template below is already at `runtime-herdr-core/docs/soak-report.md`;
fill it there from `soak report --markdown`, the drill records and the
check log.

```markdown
# runtime-herdr-core soak report

## Verdict

| Phase | Result | Notes |
|---|---|---|
| Pre-flight (live tier on the VM) | | |
| Bring-up (legacy) | | |
| Switch to v2 | | |
| Fault drills | | |
| 24-hour soak | | |

## What ran

- Host: Ubuntu 24.04.4 LTS, kernel <...>, systemd <...>, 4 vCPU, 8 GB, disposable.
- gc: gascity <commit> (pseudo-version <...>), Go 1.27.4, CGO_ENABLED=0. bd v1.3.4. dolt 2.6.0.
- herdr-core 0.1.19 (0.1.20 during the upgrade drill). Pack: gascity-packs <commit>.
  Harness: <commit>. Python 3.12.3. bpftrace <version>.
- City: <steady> always-on and up to <burst> on-demand scripted sessions, the formula
  dispatcher, the store's maintenance pool; `[session] provider = "herdr-core"`;
  store: bd-owned proxied Dolt for work, SQLite for infrastructure; nudge delivery: <lane | queue>.
- Agents: scripted only; no model credential on the host.

## Bring-up

| ID | Criterion | Measured | Result |
|---|---|---|---|
| B1 | doctor: no error | | |
| B2 | conformance: v2-ready, nothing failed | | |
| B3 | formula runs complete | | |
| B4 | no core left by the conformance run; city untouched | | |
| B5 | one first turn per incarnation | | |
| B6 | placement | | |
| B7 | 30 minutes without a predicate hit | | |

Disclosed doctor warnings:

| Check | Message | Why it is acceptable here |
|---|---|---|

## Switch to v2

| ID | Criterion | Measured | Result |
|---|---|---|---|
| V1 | boot log shows the v2 default | | |
| V2 | no Ownerless or Unknown box | | |
| V3 | restarts converge | | |
| V4 | a restart through v2 | | |
| V5 | one first turn per incarnation | | |

## Fault drills

| Drill | Injected at | Sessions back (s) | Children reaped (s) | Store pids kept | Orphans at 10 min | First turns | Specific criteria | Result |
|---|---|---|---|---|---|---|---|---|
| F1 place-store | | | | | | | | |
| F2 holder-kill | | | | | | | | |
| F3 holder-unit-kill | | | | | | | | |
| F4 core-kill | | | | | | | | |
| F5 core-restart | | | | | | | | |
| F6 agent-kill | | | | | | | | |
| F7 hc-update | | | | | | | | |
| F8 upgrade | | | | | | | | |
| F9 stop-wedged | | | | | | | | |
| F10 reboot | | | | | | | | |

## 24-hour soak

| ID | Criterion | Target | Legacy half | v2 half | Result |
|---|---|---|---|---|---|
| S1 | lost first turns | 0 | | | |
| S2 | duplicated first turns | 0 | | | |
| S3 | infrastructure processes killed, Dolt restarts | 0 | | | |
| S4 | unconfirmed message ops | < 1% | | | |
| S5 | controller-spawned pack ops / s / session | ≤ 0.30 / ≤ 0.05 | | | |
| S6 | core RSS within ±20% | yes | | | |
| S7 | no abort | yes | | | |

Warnings (target 0): nudges lost or duplicated <...>; orphans <...>; short-lived incarnations <...>;
unexplained core restarts / holder losses <...>; ops killed, ended by another signal or overrun <...>; stale spawn files <...>;
workflows open after 30 min <...>.

## Measurements

| | Legacy | v2 |
|---|---|---|
| pack ops / s (all; controller-spawned; per session) | | |
| top ops by rate (/s) | | |
| op latency p50 / p95 / p99 (ms), by op | | |
| op CPU (ms), by op | | |
| controller-tree CPU (cores), mean / p95 | | |
| death-to-restart (s): n, p50, p95, max | | |
| core RSS (MiB): reference, max deviation | | |
| sizes at the end: R, hc state, .gc, .beads, events | | |

## Deviations and findings

<what differed from the runbook, and why; findings filed, with links>

## Artifacts

<where the data directories, captures and drill records are archived>
```

## 16. Teardown

After the report is written and the data copied to the operator host
(`rsync -a -e "$SOAK_RSYNC_SSH" "soak@$SOAK_VM:soak-data/" <archive dir>/`):

```bash
systemctl --user disable --now soak-sample.service soak-load.service soak-check.timer soak-probe.timer
gc stop ~/cities/hc-soak 2>/dev/null; gc stop ~/cities/hc-bringup 2>/dev/null
gc supervisor uninstall
```

and as root `systemctl disable --now soak-optrace.service`. The VM itself
is left as it is until it is destroyed.
