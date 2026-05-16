# Changelog

All notable changes to the magi pack are recorded here.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). The pack follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `bd_close` in `scripts/magi_common.py` no longer passes a `--label` flag to `bd close`. The upstream `bd` CLI never accepted `--label` on the `close` subcommand; the prior code only worked against `bd create` because cobra prefix-matched `--label` → `--labels`. The fix applies outcome labels via `bd update --add-label <key>:<value>` BEFORE the close call, then issues a label-less `bd close`. This unblocks every doctor run that observed an orphaned bead and tried to close it, including the `reconcile_orphans` path that was previously emitting `WARNING bd_nonzero op=close ... stderr=Error: unknown flag: --label` and abandoning the close.
- `try_bd` in `scripts/magi_common.py` no longer logs `bd_nonzero` at WARNING when the underlying failure is a known bd-degraded operational state. A new helper `_is_bd_degraded_stderr(stderr)` substring-matches the raw stderr (and the JSON `error` envelope when bd emits one) for three markers: `"Dolt server unreachable"` (auto-start disabled or server died), `"failed to open database"` (Dolt store unreachable or corrupt), and `"no beads database found"` (bd binary present but never `bd init`-ed). When the matcher fires, the event is logged at INFO with op label `bd_degraded`; the body is suppressed because the bd message is already redundant once classification fires. All other non-zero `bd` exits keep the existing WARNING with full stderr.
- One pre-existing `mypy --strict` finding in `scripts/magi_install.py:139` (`Returning Any from function declared to return "str"`) — `_resolve_target_home` now wraps `args.home` in `str(...)` before passing to `os.path.expanduser`. `args.home` is typed `Any` by argparse and propagates that into the return type; the explicit `str` cast lets the function honor its declared return type without changing observable behavior.

### Added

- `_shakedown()` function and four probe helpers (`_probe_state_roundtrip`, `_probe_inflight_scan`, `_probe_bd_list_live`, `_probe_bd_show`) in `scripts/magi_doctor.py`. The shakedown phase runs after the registered checks complete and before `_aggregate`. It is a real-paths verification lap: it executes the live `read_state` → `write_state` → `read_state` roundtrip, scans the `inflight/` sentinel directory, calls `bd list --label pack:magi --status open --json` against the live bd database, and calls `bd show <first-bead-id> --json` against the first listed bead. Probe results are folded into the doctor's `results` list under the `shakedown` check name.
- Five explicit shakedown triggers (run if ANY fires) plus one interval trigger:
  1. `never-run` — `state.doctor.shakedown.last_run_at` is `None`.
  2. `script-modified` — `magi_doctor.py` mtime_ns or SHA-256 differs from the recorded values.
  3. `tunables-changed` — the SHA-256 fingerprint of `_DOCTOR_TUNABLE_ENV_KEYS` env values differs from the recorded value.
  4. `errors-in-run` — any prior check in the same doctor run produced a non-zero rc.
  5. `install-trigger-file` — `runtime_dir()/shakedown_trigger` is present (written by `magi install` on successful non-dry-run deploys; unlinked by `_shakedown` after observation, so the trigger is one-shot).
  6. `interval-elapsed` — more than `SHAKEDOWN_INTERVAL_SECONDS` (3600 s) since the last completed shakedown.
- Public helper `default_shakedown_entry()` and the `state.doctor.shakedown` sub-dict schema in `scripts/magi_common.py`. The sub-dict carries `last_run_at`, `last_run_rc`, `script_mtime_ns`, `script_sha256`, `tunable_fingerprint`, `triggers_fired`, and `last_findings`. `_default_state()` seeds the sub-dict so the schema is always present on a fresh install.
- Public helper `shakedown_tunable_fingerprint()` in `scripts/magi_common.py`. Loads pack env, iterates `sorted(_DOCTOR_TUNABLE_ENV_KEYS)`, redacts any secret-keyed value via `_is_secret_key` before hashing, and returns a SHA-256 hex digest. Mirrors the redaction-before-hash discipline of the existing `flag_fingerprint()`.
- `SHAKEDOWN_INTERVAL_SECONDS`, `SHAKEDOWN_TRIGGER_FILENAME`, and `_DOCTOR_TUNABLE_ENV_KEYS` module-level constants in `scripts/magi_common.py`. The tunable list pins the env vars whose change forces a shakedown: `GC_CITY_PATH`, `GC_CITY_ROOT`, `GC_PACK_STATE_DIR`, `MAGI_UTILITIES_SOURCE`, `LM_STUDIO_URL`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `INSTALL_REMOTE_MCP`.
- `_write_shakedown_trigger()` in `scripts/magi_install.py`. Atomic temp-then-`os.replace` write of the shakedown trigger sentinel under `runtime_dir()`. Invoked after the final `write_state` only when the install rc is 0 and `--dry-run` is not set.
- `## Shakedown` section appended to `guidelines/markdown_library/magi/doctor.md`. Documents the F1 test-lap analogy, all six triggers, the not-triggered condition, the `state.doctor.shakedown` schema, and the tunable-env-key list.
- Concurrent-doctor-safety via `fcntl.flock(LOCK_EX|LOCK_NB)` on `runtime_dir()/.shakedown.lock` inside `_shakedown`. A second doctor caught in the same window logs `shakedown: skipped reason=concurrent-run` and returns the prior shakedown entry untouched. The lock is released in a `finally` and the lock file fd is closed unconditionally.
- Defensive nested-type normalization for `state.doctor` and `state.doctor.shakedown` reads in `main()`. The prior value is coerced to `dict[str, object]` at each layer and defaulted to `default_shakedown_entry()` on the leaf when the on-disk shape is unexpected. The pattern mirrors the existing `exit_codes_raw if isinstance(exit_codes_raw, dict) else {}` defense elsewhere in the doctor.

### Changed

- `state.doctor` write shape in `main()` of `scripts/magi_doctor.py` — the previous `state["doctor"] = summary` clobber is replaced by a merge that preserves the new `shakedown` sub-key alongside the per-run `timestamp`, `results`, `summary_rc`, and `log` fields. Older state files without a `shakedown` key are normalized through `default_shakedown_entry()` on first read.
- Account-portability scrub: every literal maintainer username in the pack tree generalized to a placeholder. The pack now functions correctly under any user account on any host.
  - `enforcement/cleanup/merge-dotted-projects.sh` — glob generalized to `/*-.*`; sed substitution generalized to `s|-\.|--|g`. The dotted-key collapse pattern is transformed regardless of which user generated it.
  - `enforcement/lifecycle/history-per-project.sh` — doc-block example sanitized to use a generic `<u>` placeholder.
  - `mcp-servers/project-memory/index.js` — `GLOBAL_MEMORY_DIR` derives from the runtime project-key collapse rule applied to `$HOME/.claude` instead of a hard-coded literal user path. A small `projectKeyFromPath` helper mirrors the canonical collapse rule from `enforcement/shared/utils/project-key.sh`.
  - `plugins/marketplaces/local-lsp/.claude-plugin/marketplace.json` — the marketplace `owner.name` field is now the deployer placeholder `__USER_NAME__` so the install-time substitution loop fills it with the deploying user's name (matches the existing taxonomy in `INSTALL_PLACEHOLDERS`).
  - `plugins/README.md`, `plugins/lsp-architecture.mmd` — example marketplace JSON and Mermaid architecture diagram updated to show the `__USER_NAME__` placeholder in the owner field.
  - `mcp-servers/README.md`, `mcp-servers/mcp-architecture.mmd` — postgres role references generalized to `${LSP_USER}`; the global-memory-path example reworded to describe the project-key collapse rule rather than embedding a literal user path; the connection-string example uses `${LSP_USER}` for the role.
  - `claude/README.md` — the `LSP_USER=<username>` env-var example replaced with `LSP_USER=<your-user>`.
  - Pack-root CICD-guideline file `guidelines/markdown_library/cicd/NOTIFICATIONS_COMMUNICATION.md` — example notification handle sanitized to `@author`.
  - LaunchAgent plist source files renamed from `com.<username>.claude-cleanup-*.plist` to `com.__USER_NAME__.claude-cleanup-*.plist` under `enforcement/launchd/` (5 files). Each plist's internal `<key>Label</key>` already used the `__USER_NAME__` placeholder. The deployer's FROM-pattern in `scripts/magi_install.py` (`_PLIST_LABEL_REGEX` and `_rename_launchd_plists` glob) updated accordingly. The general install-time substitution loop already rewrites `__USER_NAME__` to the deploying user inside file contents; the special rename loop now matches the placeholder filename and renames in tandem.
  - Pack-root attribution (`LICENSE.md`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, per-runtime `claude/README.md`, `codex/README.md`) reworded to credit "magi pack maintainers" rather than embedding a personal name.

### Removed

- `claude/harness/` directory (entire 15M subtree). The contents were a byte-exact mirror of pack-root content (`CLAUDE.md`, `agents/`, `commands/`, `enforcement/`, `mcp-servers/`, `plugins/`, `scripts/`, `skills/`, `settings.json`, `.mcp.json`) plus five duplicated forms of the guideline library under `enforcement/guidelines/guideline_documents/` (`gsl`, `longer_markdown`, `markdown`, `markdown_library`, `xml`). The pack-root canonical drives the only supported deploy path; the legacy `claude/deploy_harness.sh` exec path is no longer reachable.
- `claude/deploy_harness.sh` script (the legacy claude deployer entry point). The direct-deploy path inside `scripts/magi_install.py` is the only supported claude install flow.
- `codex/harness/enforcement/guidelines/guideline_documents/` subtree (5.3M). Pure duplicate of pack-root canonical content. The codex-specific payload that the codex deployer actually references (`codex/harness/config/`, `codex/harness/hooks.json`, `codex/harness/rules/`, `codex/harness/enforcement/`) is preserved.
- `--legacy-claude-deployer` CLI flag on `gc magi install --target claude` (`scripts/magi_install.py`). The flag execed `claude/deploy_harness.sh` which no longer exists. `_deploy_target()` simplified to dispatch claude to the direct-deploy path unconditionally; non-claude targets continue to exec their per-target deployer.
- `magi/.env` working-tree file. The file held only empty-valued placeholder env vars (no real secrets). It is gitignored regardless; deleted to prevent any future accidental population from leaking on a re-export.

### Changed

- `_deploy_target()` in `scripts/magi_install.py` — the `deploy_mode` enum that lands in `state.json` `installs.<target>.deploy_mode` is `"direct"` for claude and `"vendored"` for codex/gemini/openai. The previous `"legacy"` value is retired.

## [0.2.0] — 2026-05-13

Self-contained pack release. The magi pack now ships the canonical Claude harness payload at pack root and deploys it directly via a stage-and-swap rsync + placeholder-substitution flow. Pack-source files reference only `${MAGI_PACK_DIR}` and pack-relative paths; the deployer substitutes the placeholder to the deploy home at install time. The 12th shakedown check (split into 12a pack-source and 12b doc-side) enforces this invariant. Minor version bump because the cleanup adds 49 markdown_library topic dirs alongside 7 other additive pack-root surfaces; CITY_GUIDELINES §21.1 maps additive surface to a minor bump.

### Added

- `AGENTS.md` at pack root — pack identity, primitives, agent routing, slash commands, build commands, `.utilities/` pattern, determinate-language gate, path discipline.
- `settings.json.template` and `.mcp.json.template` at pack root — placeholder templates deep-merged into existing deployed copies at install time.
- `agents/` — 28 subagent definitions promoted from the harness (api-designer, architecture-advisor, bash-script-enforcer, bashforge-script-generator, code-reviewer, csharp-forge, database-architect, deployment-guardian, dev-tracker, devops-engineer, documentation-writer, frontend-developer, gradle-forge, ignition-master, java-forge, maven-forge, neurotic-code-quality, performance-optimizer, plan-agent, python-forge, react-forge, react, rust-forge, security-auditor, test-engineer, tree-structure-documenter, utilities-agent, yew-forge).
- `claude-commands/` — 14 user-facing slash commands (bash-crew, check-project, consult, enforce-automation, enhance-guidelines, frontend-crew, full-stack-crew, gsl, rust-crew, scope, scope-reminder, scrub, scrub_mongodb, superwork).
- `mcp-servers/` — 4 custom MCP servers (guidelines-retriever, project-memory, system-info, remote-shell) plus the architecture diagram at `mcp-architecture.mmd`.
- `plugins/marketplaces/local-lsp/` — LSP marketplace shipping 8 language servers (bash-lsp, clangd-lsp, csharp-lsp, java-lsp, pyright-lsp, rust-analyzer-lsp, swift-lsp, typescript-lsp).
- `enforcement/` — full enforcement layer (rules + lifecycle + cleanup + launchd + shared + prohibited + guidelines pointer infrastructure).
- `skills/verify-frontend-ux/` alongside the existing `skills/verify-magi-installed/`.
- `guidelines/markdown_library/` — 49 cross-language topic dirs promoted from the harness (angular, angular_js, apache_wicket, api, application_dockerization, auth, automation_principles, azure_variable, bash, bicep, cicd, cosmosdb, csharp, datadog, docker, domain_infrastructure, email_authentication, frontend, gradle, ignition_v81, ignition_v83, java17, kafka, kubernetes, lxc, maven, netlify, nginx, powerquery, powershell, prohibited_behavior, python, rabbit_mq, react_node16, real_writing_style, redis, rust, session_recording, snowflake, sql, storage_and_messaging_principles, stripe, swift, typescript_react_node, utilities, vue_nuxt, wicket, woocommerce, wordpress, yew, zenfolio_integration) alongside the existing 8 magi-specific topics.
- Direct-deploy installer path for `--target claude` in `magi_install.py` — `_deploy_claude_from_pack_root()` performs stage-and-swap (snapshot → stage → substitute → set mode → validate → atomic rename → mode verify) from pack root instead of execing the vendored `claude/deploy_harness.sh`.
- 12th shakedown check — split into 12a (pack-source external-path grep with union regex covering `~`, `~<user>`, `${HOME}`, `${HOME:-...}`, `${HOME:?...}`, `$HOME`, `/Users/<u>`, `/Users/<anyname>` prefixes against `.claude`, `.codex`, `.gemini`, `.openai`, `.scripts`, `.lm-studio-magi` runtimes) and 12b (doc-side external-reference context allowlist requiring an install-destination context word in the same paragraph). Log destination is `${MAGI_PACK_DIR}/.scratch/magi-build/logs/shakedown-check12-<utc>.log`.
- Canonical placeholder enumeration table (15 placeholders) documented in `CONTRIBUTING.md` §"Adding a placeholder to the substitution set"; new `__LSP_PASS__`, `__LSP_USER__`, `__LSP_IP__`, `__LSP_REMOTE_HOME__`, `__BRAVE_API_KEY__`, `__GITHUB_PERSONAL_ACCESS_TOKEN__`, `__MY_GITEA_API_TOKEN__`, `__MY_GITEA_HOST__`, `__MY_GITEA_PORT__`, `__LM_STUDIO_HOST__`, `__LM_STUDIO_PORT__`, `__LM_STUDIO_URL__`, `__USER_HOME__`, `__USER_NAME__`, `__CLAUDE_HOME__` placeholders.
- `PACK_DIR_PLACEHOLDER`, `RUNTIME_STATE_PATHS`, `SUBSTITUTABLE_EXTENSIONS`, `SECRET_BEARING_FILES`, `CROSS_RUNTIME_EXEMPTIONS` constants in `scripts/magi_common.py` and `scripts/magi_install.py` — single source of truth consumed by Phase D rewrites, the deployer's sed loop, the 12th-check allowlist, and the secret-mode-set-before-rename rule.
- `--legacy-claude-deployer` flag on `gc magi install --target claude` — falls back to execing the vendored `claude/deploy_harness.sh`; the operator-visible signal is the `[magi-install] mode=legacy-deployer` stdout line and `state.json` `installs.claude.deploy_mode=legacy` value.

### Changed

- `magi_utilities_source()` default precedence — pack-internal `${MAGI_PACK_DIR}/.utilities/` is the primary probe; `MAGI_UTILITIES_SOURCE` env override is the fallback; legacy `${HOME}/.scripts/.utilities/` is the last-resort fallback retained for installs from the pre-cleanup era. Every resolution emits a `log_event("utilities", ...)` audit-trail line routed to the active verb's log file. `doctor/check-utilities.sh` cross-checks the most recent install log's `resolved source=` marker against its own resolution; disagreement is a warn (rc=2).
- `MAGI_UTILITIES_SOURCE` default value — pack-internal `${MAGI_PACK_DIR}/.utilities` replaces the empty-string default that previously forced installs to set the env var manually.
- `magi_install.py --target claude` flow — rsync + substitute + atomic-rename from pack root (was: exec the vendored `claude/deploy_harness.sh`). The new path runs as stage-and-swap: per-file pre-mutation snapshot (`<file>.pre-magi-<utc>.bak`) + staging dir (`<deploy-home>.staging-<utc>/`) + locked sed substitution + chmod 0600 on `SECRET_BEARING_FILES` IN STAGING + per-file validators (`jq -e .`, `plutil -lint`, `bash -n`) + atomic rename per file + post-rename mode verification. The mode bits are set in staging BEFORE the atomic rename, so the deployed file appears at its final path with its final content AND its final mode in one operation.
- `_TARGETS_WITH_UTILITIES` renamed to `_UTILITIES_AWARE_TARGETS` in `magi_install.py` — semantics unchanged (`{claude, codex}`), name clarifies that membership means "this target receives `.utilities/` at deploy time".
- `doctor/check-utilities.sh` — verifies pack-internal `.utilities/` first (was: `${HOME}/.scripts/.utilities/`). Falls through to env-var and legacy-fallback probes only when pack-internal is missing. Cross-checks the install log for the audit-trail marker.
- `guidelines/markdown_library/magi/utilities.md` — frontmatter declares six machine-readable constants (`default_source`, `env_var`, `setup_script`, `setup_flags`, `no_rsync`, `pack_internal`) consumed by `magi_common.load_policy("utilities")`. Body documents the pack-internal precedence model, the audit-trail contract, the doctor semantics, and the bootstrap-project invocation pattern.
- `CLAUDE.md` (pack-source) — rewrites every `~/.claude/...` runtime-path reference outside the `RUNTIME_STATE_PATHS` allowlist to `${MAGI_PACK_DIR}/...`. Guideline-source references rewrite from `xml/<lang>.xml` to `markdown_library/<lang>/OVERVIEW.md` (with topic-specific files when relevant). The "Where things live" table now names `markdown_library` as the authoritative format.
- `template-fragments/magi-usage.template.md` — every `~/.claude/...` reference rewrites to `${MAGI_PACK_DIR}/...`. Added one-line discovery references for the 28 agents, 14 slash commands, 4 MCP servers, enforcement layer, and `verify-frontend-ux` skill.

### Deprecated

- `--legacy-claude-deployer` flag — informational; primary path is direct-deploy from pack root. The flag exists as the R2 risk mitigation; removal in a future release follows after a deprecation window.
- Legacy `${HOME}/.scripts/.utilities/` fallback in `magi_utilities_source()` — retained for installs from the pre-cleanup era; pack-internal `.utilities/` is the canonical source going forward.

### Removed

- Duplicate guideline-format trees under `enforcement/guidelines/guideline_documents/`: `longer_markdown/`, `xml/`, `markdown/`, `gsl/`. The `markdown_library` format is canonical post-cleanup; the sibling formats served only as redundant copies.
- `.scripts-utilities/` from pack root — the harness's own scripts/utilities subset that was promoted alongside `.utilities/`. The user-authored `.utilities/` at pack root is preserved; `.scripts-utilities/` was a redundant subset that conflicted with the canonical pack-internal model.
- Empty intermediate `enforcement/guidelines/` directory after Phase C move.
- Per-rule "already-rewritten" guard from Phase D rewrite rule D2 — idempotency now lives in the atomic rewrite-and-revert model at §5.2.

### Fixed

- Pack-source files no longer contain external `~/.claude/...` or `/Users/<u>/...` absolute references in any promoted file. The 12th shakedown check (12a pack-source) enforces this invariant on every run.
- `state.json` `installs.<target>.utilities_linked` now reflects the actual deployed symlink state (was: sometimes wrote `true` when the post-deploy step was skipped via `--skip-utilities`).

### Security

- Placeholder substitution preserves mode 0600 on the deployed `.mcp.json`, `settings.json`, and `enforcement/env` via stage-and-swap ordering: `chmod 0600` runs against the staging file BEFORE the atomic rename, eliminating the secret-readable window present in the legacy `deploy_harness.sh` flow where rsync-then-chmod created a window during which the deployed file was briefly mode 0644 with secret content.
- Per-file backup chain captures every secret-bearing file before mutation via `<file>.pre-magi-<utc>.bak` snapshots adjacent to the original. The whole-tree backup at `<deploy-home>_backup-YYYYMMDD-HHMMSS` (legacy parity) runs in parallel. Both survive uninstall.
- New `__LSP_PASS__`, `__BRAVE_API_KEY__`, `__GITHUB_PERSONAL_ACCESS_TOKEN__`, `__MY_GITEA_API_TOKEN__` placeholders carry `Redaction=yes` in the canonical placeholder table and pass through `magi_common.redact()` in every log line. The redacted form is `<key>=***` in `state.json` `feature_flags` and in every log destination.
- Required-but-missing placeholders fail the install with a non-zero rc rather than silently substituting an empty string (per R5 mitigation). The deployer aborts with a clear error naming the unresolved placeholder before any pack-source file is staged.
- Atomic-rename ordering: `stage → substitute → chmod 0600 in staging → validate → atomic rename → post-rename mode verify`. No file is rsynced directly into the deploy home and then mutated in place. The deployed file appears at its final path with its final content and final mode in one rename operation.

### Operational

- Pack is fully self-contained: zero external path references in pack-source files. Vendored `claude/`, `codex/`, `project_analyzer/` byte-exact upstream payloads are exempt per CITY_GUIDELINES §13.1. `.utilities/` is the user-authored tree and is rsynced byte-exact.
- `${MAGI_PACK_DIR}` literal placeholder is the canonical pack-source reference; the constant is defined once as `PACK_DIR_PLACEHOLDER` in `scripts/magi_common.py` and consumed by the deployer's sed loop, the 12th-check positive control, Phase D rule rewrites, and CONTRIBUTING's external-reference invariant section.
- Re-install idempotency for the claude direct-deploy path: rsync runs with `--checksum` so byte-identical files are no-op; sed substitution against an already-substituted file produces zero changes; the atomic rename per STEP 5 is a no-op when content matches. Re-runs within the 300s `IDEMPOTENT_WINDOW_SECONDS` window reuse the prior bead id.
- Post-deploy invariant grep: after the atomic rename and mode verification, the deployer runs `grep -RIE '\$\{MAGI_PACK_DIR\}' <deploy-home> --exclude-dir=.utilities --exclude-dir=claude` and aborts non-zero on any match. The whole-tree backup restores the prior state.
- New documentation surface: `AGENTS.md` (pack identity), expanded `README.md` (23 sections covering verb surface, install operator surface, every pack-root surface), expanded `CONTRIBUTING.md` (eleven sections including four new procedural sections), refreshed `template-fragments/magi-usage.template.md` (40-line budget, surface enumeration).

### Known limits

- Linux launchd check returns 0 with an explicit note; magi does not install launchd jobs on Linux. The `enforcement/launchd/install.sh` script is macOS-only.
- `bd dolt push` only fires under `--bd-push` and is best-effort within `BD_PUSH_TIMEOUT_SECONDS=60`.
- `.utilities/` post-deploy step requires `magi_utilities_source()` to resolve to a path with an executable `setup_utilities.sh`; unresolved → warn-only, install bead still closes `outcome:0`, `state.json` records `utilities_linked=false`.
- The direct-deploy path's `npm install` step inside `mcp-servers/` is best-effort; failures log a warning and do not abort the install. Operators verify MCP server readiness via `gc magi doctor`.

## [0.1.0] — 2026-05-12

Initial release. Unifies five model-runtime deployers plus the `project_analyzer` tool behind one twelve-verb Gas City pack.

### Added

- 3 vendored runtimes under sibling directories (rsync-mirrored from the upstream distribution checkout with the documented exclusion list; never modified after vendoring):
  - `claude/` — claude_dist deployer plus harness tree
  - `codex/` — codex_dist deployer plus harness tree
  - `project_analyzer/` — bottom-up project analyzer plus three-model improvement pipeline
- 2 pack-built installers:
  - `gemini/deploy_gemini.sh` plus `gemini/harness/` — Gemini CLI enforcement bridge install
  - `openai/deploy_openai.sh` plus `openai/templates/` — LM Studio OpenAI-compatible configuration and shim
- 12 verbs:
  - `install`, `uninstall` — target-aware deploy and rollback
  - `analyze`, `improve` — project_analyzer wrappers
  - `status`, `doctor`, `ready`, `formulas` — read-only diagnostics
  - `molecule`, `bootstrap-project` — bd molecule and `.utilities/` wiring
  - `remember`, `recall` — magi-namespaced bd memories
- 7 doctor checks: `deploy-prereqs`, `python`, `lmstudio`, `ssh`, `launchd`, `beads`, `utilities`
- GSL guideline at `guidelines/gsl/magi.gsl` (single line, 4066 bytes, sections core / install / analyze / improve / doctor / bd / utilities / prohibited / required)
- markdown_library guidelines at `guidelines/markdown_library/magi/`: OVERVIEW, deploy, analyze, improve, doctor, beads, molecule, utilities — each with YAML frontmatter declaring machine-readable constants loaded by `magi_common.load_policy(topic)`
- Bootstrap formula at `formulas/mol-magi-bootstrap.formula.toml` — `doctor → install → bootstrap-project → status → analyze` chain with per-step `on_fail` semantics
- 3 bd hook registrations at `hooks/magi-bd-hooks.toml`:
  - `bead.closed` + `pack:magi:install` → `scripts/hook_post_install.py`
  - `bead.created` + `pack:magi:analyze` → `scripts/hook_pre_analyze.py`
  - `bead.failed` + `pack:magi` → `scripts/hook_on_failure.py`
- Template fragment at `template-fragments/magi-usage.template.md` — Go text/template `{{ define "magi-usage" }}` block; 4 use-cases + 4 anti-patterns + 6-step protocol
- Skill at `skills/verify-magi-installed/SKILL.md` — accepted-evidence and rejected-evidence rules for verifier agents
- bd integration: every verb participates in bd lifecycle (`create → claim → close`); orphan reconciliation via `inflight.json` sentinel; reconciliation runs at the start of every verb
- `.utilities/` portability via `setup_utilities.sh` — zero `.utilities/` content vendored; `MAGI_UTILITIES_SOURCE` resolves the user-owned tree

### Security

- `SECRET_KEY_PATTERNS` centralized in `scripts/magi_common.py`
- Redaction runs on every bd write (title, body, label values), every `state.json` write, and every log line
- Log files written with mode `0600`
- `state.json` written with mode `0600`
- `flag_fingerprint()` hashes secret-keyed values through `redact_secrets()` before SHA-256; raw secrets never enter the hash input
- `feature_flags` in `state.json` stores `key=<redacted>` for secret-keyed vars

### Operational

- All bd subprocess calls bounded: `BD_DEFAULT_TIMEOUT_SECONDS=10`, `BD_CLOSE_TIMEOUT_SECONDS=20`, `BD_PUSH_TIMEOUT_SECONDS=60`
- `bd_available_current()` PATH-keyed via `functools.lru_cache`; tests clear the cache via the `env_isolated` fixture
- Orphan reconciliation via `inflight.json` sentinel; `reconcile_orphans()` is process-locally memoized
- `IDEMPOTENT_WINDOW_SECONDS=300` idempotent re-run window
- `MAGI_LABEL_SCHEMA` validates every `bd_label()` call; schema violations raise `ValueError`
- Three-layer recursion guard on bd hooks: `MAGI_HOOK_REENTRANT=1` env, `role:hook-trigger` label filter, hook scripts default to reads only

### Known limits

- Linux `launchd` check returns 0 with an explicit note; magi does not install launchd jobs on Linux
- `bd dolt push` only fires under `--bd-push` and is best-effort within `BD_PUSH_TIMEOUT_SECONDS=60`
- `.utilities/` post-deploy step requires `MAGI_UTILITIES_SOURCE` to resolve; unresolved → warn-only, install bead still closes `outcome:0`

[0.2.0]: https://example.com/magi/releases/0.2.0
[0.1.0]: https://example.com/magi/releases/0.1.0
