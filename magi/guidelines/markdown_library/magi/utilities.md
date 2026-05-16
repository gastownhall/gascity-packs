---
default_source: ${MAGI_PACK_DIR}/.utilities
env_var: MAGI_UTILITIES_SOURCE
setup_script: setup_utilities.sh
setup_flags: ["-y"]
no_rsync: true
pack_internal: true
---

# Utilities — Pack-Internal `.utilities/` Integration

`magi_bootstrap_project.py`, `doctor/check-utilities.sh`, and the `_run_post_deploy_utilities()` step in `magi_install.py` load this file at startup via `magi_common.load_policy("utilities")`. The YAML frontmatter declares six machine-readable constants the orchestrators read; the body documents the resolution model, the audit-trail contract, and the doctor semantics.

## Frontmatter constants

| Key             | Value                              | Consumer                                                                                                                               |
|-----------------|------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| `default_source`| `${MAGI_PACK_DIR}/.utilities`      | `magi_common.magi_utilities_source()` primary probe.                                                                                   |
| `env_var`       | `MAGI_UTILITIES_SOURCE`            | `magi_common.magi_utilities_source()` fallback probe; named env override for installs that override the canonical source.              |
| `setup_script`  | `setup_utilities.sh`               | `magi_common.magi_utilities_source()` executability check (the function returns the source only when this file exists and is `+x`).   |
| `setup_flags`   | `["-y"]`                           | `_run_post_deploy_utilities()` argv build; suppresses interactive prompts.                                                             |
| `no_rsync`      | `true`                             | pack-build invariant: pack source does not rsync `.utilities/` content from any external source during pack build. The user-authored tree ships verbatim under `${MAGI_PACK_DIR}/.utilities/`. |
| `pack_internal` | `true`                             | declares canonical source is `${MAGI_PACK_DIR}/.utilities/`. The env-var fallback exists for backward compatibility with installs that override; the legacy `${HOME}/.scripts/.utilities/` path is the last-resort fallback. |

`magi_common.load_policy("utilities")` reads this frontmatter at runtime. Changing a key value propagates without code edits.

## Pack-internal precedence model

`magi_common.magi_utilities_source()` resolves the `.utilities/` source in this order:

1. **Pack-internal (primary)** — `${MAGI_PACK_DIR}/.utilities/`. Returned when the directory exists AND `setup_utilities.sh` inside it is a file AND `setup_utilities.sh` is executable. This is the canonical source post-cleanup.
2. **`MAGI_UTILITIES_SOURCE` env override (fallback)** — when the env var is set to a non-empty path AND that path holds an executable `setup_utilities.sh`. Documented for installs that override the canonical source.
3. **Legacy `${HOME}/.scripts/.utilities/` (last-resort fallback)** — only when neither of the above resolves. Retained for installs from the pre-cleanup era; not the recommended path.

The first match short-circuits; later probes do not run. The function returns the absolute path. When no probe resolves, the function returns `None` and the calling verb degrades:

- `gc magi install` skips the post-deploy `setup_utilities.sh` invocation and writes `installs.<target>.utilities_linked=false` to `state.json`. The bead still closes `outcome:0` because the install itself succeeded; the doctor warns.
- `gc magi bootstrap-project` exits non-zero with a clear error naming the precedence chain that was attempted.
- `gc magi doctor` `utilities` check exits 2 (warn) and prints the precedence chain.

## Audit-trail contract

Every resolution emits one `log_event("utilities", ...)` line to the active verb's log file. The log line carries the audit trail consulted by `doctor/check-utilities.sh`.

**Logged fields:**

- `chosen_path` — the absolute path `magi_utilities_source()` returned (or `none` when unresolved).
- `fallback_chain` — the ordered list of probes attempted: `["internal", "env-var", "legacy"]` truncated at the first match.
- `final_value` — synonym for `chosen_path`, present for grep clarity.

**Log destinations** (routed via `magi_common._get_log_path()` per the calling verb):

- `${GC_CITY_PATH}/.gc/runtime/packs/magi/logs/install-<target>-<utc>.log` when invoked from `gc magi install`.
- `${GC_CITY_PATH}/.gc/runtime/packs/magi/logs/doctor-<utc>.log` when invoked from `gc magi doctor`.
- `${GC_CITY_PATH}/.gc/runtime/packs/magi/logs/<verb>-<utc>.log` for every other verb that triggers utilities resolution.

The log lines flow through `magi_common.redact()`; secret-bearing values inside paths receive the same redaction treatment as other log content.

## Doctor check semantics

`${MAGI_PACK_DIR}/doctor/check-utilities.sh` is the operator-visible probe. The check resolves the source per the precedence model above and asserts:

| Condition                                                                            | rc | Operator message                                                                  |
|--------------------------------------------------------------------------------------|----|-----------------------------------------------------------------------------------|
| `${MAGI_PACK_DIR}/.utilities/` exists AND `setup_utilities.sh` is `+x`               | 0  | `utilities: ok (pack-internal)`                                                   |
| Pack-internal missing; env-var resolves to a dir with executable `setup_utilities.sh`| 2  | `utilities: warn (degraded — env-var fallback active; canonical source missing)` |
| Pack-internal missing; legacy `${HOME}/.scripts/.utilities/` resolves                | 2  | `utilities: warn (degraded — legacy fallback active)`                             |
| No probe resolves                                                                    | 2  | `utilities: warn (no source available; bootstrap-project is unavailable)`        |

**Cross-check:** the doctor tails the most recent `install-<target>-<utc>.log` under `${GC_CITY_PATH}/.gc/runtime/packs/magi/logs/` (or the deployed equivalent location) for the `resolved source=` marker. When the marker disagrees with the doctor's own resolution, the doctor exits 2 with a warn message naming both values. This is the audit-trail load-bearing check; without it the log line is decoration.

The check is wired into the doctor aggregator via `${MAGI_PACK_DIR}/doctor/utilities/doctor.toml`.

## Bootstrap-project verb invocation pattern

`gc magi bootstrap-project <project-path>` wraps `setup_utilities.sh -y <project-path>`. The verb:

1. Calls `reconcile_orphans()` before any work.
2. Resolves `magi_utilities_source()`; aborts non-zero when no probe resolves.
3. Creates a `pack:magi:bootstrap-project` bead with `target:project` label.
4. Invokes `subprocess.run([<source>/setup_utilities.sh, "-y", <project-path>], check=False)`.
5. Verifies the resulting `<project-path>/.utilities` symlink resolves to the source tree.
6. Closes the bead with the subprocess rc.

The verb is idempotent within `IDEMPOTENT_WINDOW_SECONDS=300` per `flag_fingerprint()` over `(project-path, source-path)`. Re-runs within the window reuse the prior bead id.

When invoked from `gc magi molecule bootstrap`, the same code path runs as a child step in the bootstrap formula; the parent molecule bead carries the `role:root` label and the child carries `role:child`.

## Pack-build invariant

`no_rsync: true` in the frontmatter declares that the pack-build step does not rsync `.utilities/` content from any external source. The user-authored tree ships verbatim under `${MAGI_PACK_DIR}/.utilities/`. The deployer rsyncs this tree byte-exact to the deploy home at install time (rsynced-only surface — no placeholder substitution). Substitutable-extension files inside `.utilities/` are NOT substituted; the user owns the content.

Earlier pre-cleanup designs vendored `.utilities/` via rsync at re-vendor time. That model coupled magi to an external source tree's stability and broke whenever a `.utilities/` script referenced a per-user path. The pack-internal model decouples magi from external sources: the pack OWNS the `.utilities/` content, the deployer copies it verbatim, and the env-var fallback exists only for installs that override the canonical source.
