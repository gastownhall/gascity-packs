# Isolated fix validation

**Correction, 2026-09-23.** The patch validated here works around a latent,
load-dependent Beads issue, not a demonstrated production bug. The five-second
preflight only interrupts migrations that run longer than five seconds; on this
host a plain `bd init` took 25–56 s under load averages of 20–74 on 18 CPUs.
Gas City `main` has a related mitigation not in v1.4.2 (8c2b970fe, #5330). Runs
that used this patched `bd` are not representative of the released runtime.
Original text is kept below.

The proposed Beads v1.3.0 patch changes `countExistingIssues` to use the existing
read-only store opener. This prevents a five-second issue-count probe from
starting migrations. It does not change schema versions or migrate a user city.
The global Homebrew `bd` binary remains unchanged.

`beads-v1.3.0-readonly-preflight.patch` applies to the v1.3.0 source archive.
The local build uses Go 1.27.1, `-tags=gms_pure_go`, and `-ldflags "-s -w"`
with version/build labels. The initial debug-symbol build was stopped at dsymutil
and the same cached source was linked without debug symbols. Both arms of any subsequent
paired benchmark must use the same runtime binary; results from distinct runtime
cohorts must not be pooled. Build provenance is recorded separately.

## Regression

`regression.py` starts its own loopback Dolt server, creates an empty database
and the metadata stub used by Gas City, and runs forced Beads initialization
without a migration-consent override. On successful init it creates one issue,
checks that a subsequent noninteractive reinitialization is refused, and verifies
that the issue remains. All paths and database state are local disposable fixtures.

From this directory, using a new output name each time:

```sh
BD_REGRESSION_BIN=/absolute/path/to/bd python3 -u regression.py \
  precreate-forced-pinned-managed-noconsent-unique-name
```

`regression-red.log` records the unpatched release failing fresh initialization.
The failure is timing-sensitive; the source-level explanation and additional
controls are in the parent diagnosis. A green probe is not a statistical claim
about every possible concurrent initialization race.

## Harness fixes

The full-build experiment now keeps real HOME, isolates Git and Dolt config,
uses a short temporary runtime path for macOS Unix sockets, and canonicalizes
paths before identifying leftover servers. Setup timeout is explicit and separate
from workflow timeout. Claude onboarding state is not rewritten. Runtime paths
are retained in each run's `runtime-path.json` for inspection.

## Token telemetry

A local loopback OTLP JSON receiver stores only a whitelist of Claude API-request
usage attributes. It excludes prompts and personal attributes and marks missing
counters unknown. Duplicate deliveries do not double-count requests.

The subscription CLI smoke test in `telemetry-smoke-001` reports exactly the same
four token counters in the receiver and CLI `modelUsage`: 2 uncached input,
4 output, 3,397 cache reads and 1,597 cache creation, totaling 5,000 processed
tokens. This verifies one main-model request only. Auxiliary-call coverage and
full-workflow delivery are not yet verified. Dollar estimates in raw CLI output
are provider list-price estimates, not subscription charges.

The proposed second probe without safe mode was rejected by automatic approval
review because it could load workspace-specific instructions or configuration.
It did not run. No auxiliary-coverage claim is made.

Protocol reference: [Claude monitoring documentation](https://code.claude.com/docs/en/monitoring-usage).

## Observed patched CLI result

The patched regression passed: forced fresh initialization exited 0, reached schema
v66, and left a clean working set. After one issue was created, forced
noninteractive reinitialization exited 12 and SQL confirmed the issue count
remained one. See [green log](regression-green.log), [commands](precreate-forced-pinned-managed-noconsent-green-001/commands.json) and
[build provenance](build-manifest.json). The global executable was not replaced.

## Gas City setup result

[Patched setup result](../../build-setup-patched-001/run-001-baseline/result.json):
city initialization, import install/check, configuration loading and the
build-basic formula lookup succeeded with Gas City 1.4.2 and the local patched
Beads binary. City and rig schema versions are both 66. Setup took 365.929 seconds
on this busy host; this is not an LLM execution-speed measurement.

Correction, 2026-09-23: the fact that setup needed a patched `bd` and more than
300 seconds reflects this host's load, not a requirement of the released
runtime.

City stop exceeded its 60-second process timeout. The subsequent supervisor-stop
command succeeded, and independent process inspection confirmed that experiment
supervisor 61906 and Dolt 60554 exited while pre-existing supervisor 23099
remained running. Including cleanup, the harness took 428.601 seconds. No model
work was dispatched; missing token telemetry stays unknown, not zero usage.
