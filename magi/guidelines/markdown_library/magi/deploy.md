---
idempotency_window_seconds: 300
backup_pattern: "<target>_backup-YYYYMMDD-HHMMSS"
purge_requires_flags: ["--really-purge", "--yes"]
secret_redaction_required: true
utilities_post_deploy_hook: "setup_utilities.sh -y"
state_schema_version: 4
state_path_template: "${GC_CITY_PATH}/.gc/runtime/packs/magi/state.json"
log_path_template: "${GC_CITY_PATH}/.gc/runtime/packs/magi/logs/<verb>-<target>-<utc>.log"
log_mode: "0600"
---

# Deploy — Install and Uninstall Rules

`magi_install.py` and `magi_uninstall.py` load this file at startup and enforce the constants above.

## Target resolution

Targets resolve through `TARGET_REGISTRY` in `scripts/magi_common.py`. Each row names a sibling directory, a deployer script, the env-passthrough variable list, and a default install home. Adding a target is one registry row plus a sibling `<target>/` directory. No edits elsewhere.

| Target | Dir | Script | Default home |
|---|---|---|---|
| claude | `claude/` | `deploy_harness.sh` | `~/.claude` |
| codex | `codex/` | `deploy_harness.sh` | `~/.codex` |
| gemini | `gemini/` | `deploy_gemini.sh` | `~/.gemini` |
| openai | `openai/` | `deploy_openai.sh` | `~/.config/lm-studio-magi` |

`--target all` iterates every registered target in registry order.

## Env passthrough precedence

Order (highest first): explicit CLI flag > inherited env > pack-root `.env` file > markdown_library default. The orchestrator loads the pack-root `.env` without overriding inherited env, then forwards env via the subprocess environment.

## Backup policy

Every deployer creates `<target>_backup-YYYYMMDD-HHMMSS` next to the deployed home before overwriting. Backups are deployer-owned. `magi uninstall` does not touch them. Restore by renaming the backup back over the deployed home and running `gc magi status` to refresh state.

## Idempotency

Re-runs reuse the prior bead id when all three conditions hold:

1. Prior bead closed with `outcome:0`.
2. `flag_fingerprint()` matches over the union of argv flags AND every documented env-passthrough variable.
3. Elapsed < `idempotency_window_seconds` (300).

Within the window, the only state mutations are `last_run_timestamp` and `last_log`. Outside the window or on fingerprint mismatch, a new bead is created.

`flag_fingerprint()` computes SHA-256 over a sorted `key=redact_secrets(value)` payload. Secrets never enter the hash input in clear form. `feature_flags` in state.json stores `key=<redacted>` for secret-keyed vars.

## Dry-run requirement

The first install of a target on a city runs with `--dry-run` first. Magi enforces this only in documentation; the deployer accepts the flag verbatim. Skipping the dry-run is permitted on repeat installs of the same target.

## Uninstall (Rollback)

`magi_uninstall.py` flows:

1. `--target <name>` resolves the deployed home from state.json.
2. Closes any open `pack:magi:install` beads for the target with the extra label `role:uninstall-closure`. `hook_post_install.py` filters `NOT role:uninstall-closure` so the hook does not re-write state.json against a purged install.
3. Updates `state.json` `installs.<target>.installed=false`.
4. When `--really-purge --yes` is set: removes `<deployed-home>` and writes `last_uninstall_timestamp`.

Two-flag gate: `--really-purge` without `--yes` exits non-zero. `--yes` without `--really-purge` performs only state cleanup.

Deployer backup directories survive uninstall by design.

## Secret redaction

`SECRET_KEY_PATTERNS` lives in `scripts/magi_common.py` as a single readonly tuple. `redact_secrets()` runs as the last step of:

- every `bd_create`, `bd_update`, `bd_close`, `bd_remember`, `bd_label` (title, body, label values)
- every `write_state()` call (full state dict)
- every install log line

Log files are written with mode `0600`. `state.json` is written with mode `0600`. The pack-root `.env` is the single install-time configuration file for every deployer.

## Post-deploy `.utilities/` step

On claude and codex targets, after the deployer returns rc=0, magi resolves `${MAGI_UTILITIES_SOURCE}` from the pack-root `.env` or inherited environment and executes `${MAGI_UTILITIES_SOURCE}/setup_utilities.sh -y` against the deployed home. The script creates the `.utilities` symlink the vendored `enforcement_rules.json` references. When `MAGI_UTILITIES_SOURCE` is unresolved, the step warns and skips; the install bead still closes `outcome:0`. `--skip-utilities` suppresses this step.
