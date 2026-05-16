---
exit_codes:
  ok: 0
  fail: 1
  warn: 2
severity_promotion:
  ssh: "conditional_on_INSTALL_REMOTE_MCP"
  lmstudio: "warn_only"
  launchd: "macos_only"
  beads: "warn_only"
  utilities: "warn_only"
orphan_threshold_seconds: 3600
---

# Doctor — Precondition Check Rules

`magi_doctor.py` loads this file at startup. The discovery model walks `doctor/*/doctor.toml`; each row registers a check and the orchestrator invokes the named `check-*.sh` script.

## Exit codes

| rc | meaning |
|---|---|
| 0 | every check returned 0 |
| 1 | at least one check returned 1 (fail) |
| 2 | at least one check returned 2 (warn); zero returned 1 |

The aggregate rc is the worst child rc. Order does not matter.

## Check severity promotion

| Check | Default | Promotion rule |
|---|---|---|
| `deploy-prereqs` | fail when `jq`, `rsync`, `sed`, `awk`, `find`, or `chmod` is missing | always fail |
| `python` | fail when `python3` is missing or `<3.10` | always fail |
| `lmstudio` | warn when `${LM_STUDIO_URL}/v1/models` returns non-200 | `warn_only` |
| `ssh` | depends on env | `conditional_on_INSTALL_REMOTE_MCP`: fail when `INSTALL_REMOTE_MCP=1`; warn otherwise |
| `launchd` | macOS requires `launchctl` | `macos_only`: Linux always returns 0 |
| `beads` | warn when `bd` is absent on PATH | `warn_only` |
| `utilities` | warn when `MAGI_UTILITIES_SOURCE` is unresolved or `setup_utilities.sh` is non-executable | `warn_only` |

## Orphaned-beads check

The aggregator includes a synthetic check that lists `bd list --label pack:magi --status in_progress`. Beads older than `orphan_threshold_seconds` (3600) cause rc=2. This is the soft alarm; the hard cleanup runs as `reconcile_orphans()` at the start of every verb.

## Discovery contract

Adding a new check is two files:

- `doctor/<name>/doctor.toml` declaring `name`, `description`, `check = "check-<name>.sh"`
- `doctor/check-<name>.sh` returning 0, 1, or 2

`magi_doctor.py` discovers it automatically. No edit to the orchestrator.

## Shakedown

A shakedown run exercises the actual live paths of `magi doctor` against real state, real inflight sentinels, and real `bd` commands — but only when conditions indicate the environment may have changed. The name refers to the F1 test-lap concept: the car has passed pre-flight checks; the shakedown is the driver's real-conditions verification lap before race day.

### Trigger conditions

A shakedown runs when ANY of the following is true:

1. **Never run** — `state.doctor.shakedown.last_run_at` is `None`.
2. **Script modified** — `magi_doctor.py` mtime or sha256 differs from the recorded values.
3. **Tunables changed** — the sha256 fingerprint of `_DOCTOR_TUNABLE_ENV_KEYS` env values differs.
4. **Errors in run** — any check in the current doctor run produced a non-zero rc.
5. **Install trigger** — `runtime_dir()/shakedown_trigger` file is present (written by `magi install` on successful deploy).
6. **Interval elapsed** — more than `SHAKEDOWN_INTERVAL_SECONDS` (3600 s) since last shakedown.

### Not triggered when

Pre-flight clean AND script unmodified AND tunables unchanged AND within interval AND no install trigger.

### State schema

`state.doctor.shakedown` carries:

| Field | Type | Description |
|---|---|---|
| `last_run_at` | `str \| None` | ISO-8601 UTC timestamp of last shakedown |
| `last_run_rc` | `int \| None` | Max probe rc of last shakedown |
| `script_mtime_ns` | `int \| None` | `magi_doctor.py` stat mtime_ns at last shakedown |
| `script_sha256` | `str \| None` | sha256 of `magi_doctor.py` at last shakedown |
| `tunable_fingerprint` | `str \| None` | sha256 over `_DOCTOR_TUNABLE_ENV_KEYS` values |
| `triggers_fired` | `list[str]` | Human-readable list of trigger names that fired |
| `last_findings` | `list[dict]` | Probe results from the last shakedown run |

### Tunable keys

Defined in `magi_common._DOCTOR_TUNABLE_ENV_KEYS`:
`GC_CITY_PATH`, `GC_CITY_ROOT`, `GC_PACK_STATE_DIR`, `MAGI_UTILITIES_SOURCE`, `LM_STUDIO_URL`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `INSTALL_REMOTE_MCP`.
