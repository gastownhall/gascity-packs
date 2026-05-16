# magi pack

The magi pack is a self-contained Gas City pack that deploys a hardened Claude Code harness — the MAGI runtime — into any city. It unifies four model-runtime install targets (`claude`, `codex`, `gemini`, `openai`/LM Studio) and the `project_analyzer` tool behind a single twelve-verb surface: `gc magi <verb>`. The pack ships, at pack root, the entire harness payload: the behavioral contract (`CLAUDE.md`), 28 subagents, 14 slash commands, 4 MCP servers, an 8-language-server LSP marketplace, a 52-topic guideline library, the enforcement layer (rules + lifecycle + cleanup + launchd + shared), 2 skills, the GSL, the bootstrap formula, and the bd hook registrations. Every pack-source path resolves under `${MAGI_PACK_DIR}`. The deployer substitutes that placeholder once, atomically, into the resolved deploy home.

## Status

| Fact                    | Value                                                              |
|-------------------------|--------------------------------------------------------------------|
| Pack name               | `magi`                                                             |
| Schema                  | `2`                                                                |
| Version                 | `0.2.0`                                                            |
| License                 | MIT — magi pack maintainers                                        |
| Install targets         | `claude`, `codex`, `gemini`, `openai` (alias `all`)                |
| Verbs                   | 12                                                                 |
| Agents                  | 28                                                                 |
| Slash commands          | 14                                                                 |
| MCP servers             | 4 (`guidelines-retriever`, `project-memory`, `system-info`, `remote-shell`) |
| LSP plugins             | 8                                                                  |
| markdown_library topics | 52 (51 cross-language plus `magi/`)                                |
| GSL                     | 1 (`guidelines/gsl/magi.gsl`)                                      |
| Skills                  | 2 (`verify-magi-installed`, `verify-frontend-ux`)                  |
| Doctor checks           | 7 file-system + 2 synthetic (`orphaned-beads`, `shakedown`)        |
| bd hook registrations   | 3                                                                  |

## Quick start

### 1. Place the pack on disk

The pack lives next to its consumer city, not inside it. Cities import packs by relative path from the city's `pack.toml`. Convention:

```
<workspace>/
├── <my-city>/                ← Gas City (city.toml, .gc/, rigs/)
└── packs/
    └── magi/                 ← this pack
        ├── pack.toml
        ├── scripts/
        ├── commands/
        └── ...
```

### 2. Import magi from `<my-city>/pack.toml`

```toml
[imports.magi]
source = "../packs/magi"

[agent_defaults]
append_fragments = ["magi-usage"]
```

The `source` is a path relative to the city's `pack.toml`. After saving, run `gc reload` to register the import. `gc magi --help` returns a 12-subcommand list when the import is registered.

### 3. Run an install

```bash
gc magi doctor                                       # 7 + 2 checks; rc=0 ok / 1 fail / 2 warn
gc magi install --target claude --dry-run --non-interactive   # plan only
gc magi install --target claude                      # real install
gc magi status --json                                # verify installs.claude.installed=true
```

`gc magi install --target claude` runs the stage-and-swap direct-deploy from pack root: snapshot every pre-existing file at the deploy home, stage every pack surface into `<deploy-home>.staging-<utc>/`, substitute `${MAGI_PACK_DIR}` plus 15 install placeholders across every `.sh .py .json .toml .md .plist .xml .gsl .conf .yaml .yml` file, set mode `0600` in staging for every entry in `SECRET_BEARING_FILES`, deep-merge any existing `settings.json` / `.mcp.json` at the deploy home, atomically rename staging into the deploy home, verify modes, run `npm install` per MCP server, and run `setup_utilities.sh -y` against the deploy home. `codex`, `gemini`, `openai` exec their per-target deployer (`codex/deploy_harness.sh`, `gemini/deploy_gemini.sh`, `openai/deploy_openai.sh`).

## The twelve verbs

Every verb's argparse parser is declared in `scripts/magi_<verb>.py` `_build_parser()`. The shell-side dispatchers under `commands/<verb>.sh` exec the Python orchestrator.

| Verb                | Script                          | Purpose                                                                       | Flags                                                                                                                                                       |
|---------------------|---------------------------------|-------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `install`           | `magi_install.py`               | Deploy a target runtime.                                                      | `--target` (req), `--home`, `--dry-run`, `--non-interactive`, `--skip-prereqs`, `--bd-push`, `--no-bd`, `--skip-utilities`                                  |
| `uninstall`         | `magi_uninstall.py`             | Close install beads; optionally purge the deploy home.                        | `--target` (req), `--yes`, `--dry-run`, `--really-purge`                                                                                                    |
| `analyze`           | `magi_analyze.py`               | Bottom-up `_DIRECTORY_OVERVIEW.md` per directory.                             | `project_path` (pos), `--model`, `--lm-url`, `--force`, `--context`, `--api-token`, `--no-bd`                                                               |
| `improve`           | `magi_improve.py`               | Three-model draft → verify → aggregate improvement pipeline.                  | `project_path` (pos), `--draft-model`, `--verify-model`, `--aggregate-model`, `--lm-url`, `--force`, `--context`, `--resume`, `--api-token`, `--no-bd`      |
| `status`            | `magi_status.py`                | Read state.json plus open `pack:magi` beads.                                  | `--json`, `--target {claude,codex,gemini,openai}`                                                                                                           |
| `doctor`            | `magi_doctor.py`                | Run every `doctor/<name>/check-*.sh`; aggregate worst child rc.               | `--json`, `--no-bd`                                                                                                                                         |
| `molecule`          | `magi_molecule.py`              | Pour / wisp / bootstrap the magi formula chain.                               | `bootstrap [project_path] [--no-bd]`, `pour <formula>`, `wisp <formula>`                                                                                    |
| `bootstrap-project` | `magi_bootstrap_project.py`     | Run `setup_utilities.sh -y` against a project root.                           | `project_path` (pos, optional; defaults to `$GC_CITY_PATH`), `--dry-run`, `--yes`, `--no-bd`                                                                |
| `remember`          | `magi_remember.py`              | Persist a `magi:<key>` bd memory entry.                                       | `remember <key> <value>`                                                                                                                                    |
| `recall`            | `magi_remember.py`              | Read a `magi:<key>` bd memory entry; also `list`.                             | `recall <key>`, `list`                                                                                                                                      |
| `ready`             | (`bd ready` wrapper)            | List ready `pack:magi` beads via bd.                                          | passthrough to `bd ready --label pack:magi`                                                                                                                 |
| `formulas`          | `magi_formulas.py`              | Enumerate, show, and cook formulas under `formulas/`.                         | `list`, `show <name>`, `cook <name>`                                                                                                                        |

`gc magi <verb> --help` prints the verb's flag table plus one example. Help text lives at `commands/<verb>/help.md`.

## The four install targets

`TARGET_REGISTRY` in `scripts/magi_common.py` is the single source of target metadata. Adding a target is one row plus a sibling directory. Every target's row carries `dir`, `script`, `env`, `default_home`.

### `claude`

The primary target. The direct-deploy path (`_deploy_claude_from_pack_root` in `magi_install.py`) runs stage-and-swap from pack root. Env passthrough: `INSTALL_GLOBAL_CLAUDE_MD`, `INSTALL_REMOTE_MCP`, `INSTALL_LAUNCHD`, `INSTALL_LM_STUDIO`, `INSTALL_LSP_BINARIES`, `LSP_IP`, `LSP_USER`, `LSP_PASS`, `LSP_REMOTE_HOME`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `LM_STUDIO_URL`, `BRAVE_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `MY_GITEA_API_TOKEN`, `MY_GITEA_HOST`, `MY_GITEA_PORT`. Default home: `~/.claude`. On success, `state.json` `installs.claude` carries `installed=true`, `target=<resolved-home>`, `last_run_rc=0`, `bead_id=<gas-...>`, `utilities_linked=true`, `deploy_mode=direct`, `flag_fingerprint=<sha256>`, `feature_flags={...}` (secret-keyed values redacted).

### `codex`

Execs `codex/deploy_harness.sh`. Env passthrough: `CODEX_HOME`, `INSTALL_CODEX_HOOKS`, `INSTALL_EXEC_POLICY`, `INSTALL_LM_STUDIO`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `LM_STUDIO_MODEL`, `LM_STUDIO_CONNECT_TIMEOUT`, `LM_STUDIO_MAX_TIME`, `CODEX_MAX_QUALITY_ATTEMPTS`, `CODEX_TURN_CONTENT_LIMIT`. Default home: `~/.codex`. Receives `.utilities/` at deploy time (member of `_UTILITIES_AWARE_TARGETS`). `state.json` `installs.codex` carries the same fields as `claude` except `deploy_mode` is absent.

### `gemini`

Execs `gemini/deploy_gemini.sh`. Env passthrough: `GEMINI_HOME`, `INSTALL_GEMINI_HOOKS`, `INSTALL_LM_STUDIO`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `LM_STUDIO_MODEL`, `GEMINI_TURN_CONTENT_LIMIT`. Default home: `~/.gemini`. Not utilities-aware. `state.json` `installs.gemini` carries `installed`, `target`, `last_run_*`, `bead_id`, `feature_flags`, `flag_fingerprint`.

### `openai`

LM Studio + OpenAI-compatible shim. Execs `openai/deploy_openai.sh`. Env passthrough: `OPENAI_TARGET_HOME`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `LM_STUDIO_MODEL`, `LM_STUDIO_CONTEXT`, `LM_STUDIO_AUTOLOAD_MODELS`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`. Default home: `~/.config/lm-studio-magi`. Not utilities-aware.

`--target all` iterates the registry in declaration order. `_UTILITIES_AWARE_TARGETS = {claude, codex}` is the canonical set that receives `.utilities/` at deploy time.

## Doctor checks

`magi_doctor.py` walks `doctor/*/doctor.toml` and runs the `check = "..."` script for each entry. The aggregator returns the worst child rc. Two synthetic checks (`orphaned-beads`, `shakedown`) run inline after the registered checks.

| Check            | Script                             | Verifies                                                                                                                                            | Exit code semantics                                                                                  |
|------------------|------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| `beads`          | `doctor/check-beads.sh`            | `bd` is on PATH.                                                                                                                                    | 0 found; 2 warn when missing (magi degrades gracefully)                                              |
| `deploy-prereqs` | `doctor/check-deploy-prereqs.sh`   | `jq`, `rsync`, `sed`, `awk`, `find`, `chmod` present; conditional `sshpass`+`ssh` when `INSTALL_REMOTE_MCP=1`.                                      | 0 ok; 1 fail when a hard requirement is missing                                                      |
| `launchd`        | `doctor/check-launchd.sh`          | `launchctl` exists on Darwin; on Linux returns 0 with an applicability note.                                                                        | 0 ok or n/a; 1 fail on Darwin when absent                                                            |
| `lmstudio`       | `doctor/check-lmstudio.sh`         | `${LM_STUDIO_URL}/v1/models` (default `http://localhost:1234`) returns HTTP 200.                                                                    | 0 ok; 2 warn when unreachable (required for `analyze`/`improve`, not for `install`)                  |
| `python`         | `doctor/check-python.sh`           | `python3` >= 3.10 on PATH.                                                                                                                          | 0 ok; 1 fail otherwise                                                                               |
| `ssh`            | `doctor/check-ssh.sh`              | `sshpass` and `ssh` present.                                                                                                                        | 0 ok; 1 fail when `INSTALL_REMOTE_MCP=1` and missing; 2 warn otherwise                               |
| `utilities`      | `doctor/check-utilities.sh`        | `magi_utilities_source()` resolves; `setup_utilities.sh` is executable; cross-checks the install log's `resolved source=` marker.                   | 0 ok; 2 warn when the source is missing or disagrees with the install log                            |
| `orphaned-beads` | `magi_doctor.py::_orphan_beads_check` | Calls `reconcile_orphans()`. Reports the count of stale `inflight/` sentinels closed in this run.                                                | 0 always (reporter only — orphan closure happens in every verb's `main()`)                           |
| `shakedown`      | `magi_doctor.py::_shakedown`       | Runs four live probes (state roundtrip, inflight scan, `bd list --label pack:magi`, `bd show <first-bead-id>`) when any of six triggers fires.       | 0 ok; non-zero matches the worst probe rc; the shakedown entry feeds `state.doctor.shakedown`        |

`--json` emits the per-check matrix as a JSON object keyed by check name. Operators consume this from CI.

## The shakedown lap

The shakedown is the pack's F1 test-lap. Pre-flight checks (`deploy-prereqs`, `lmstudio`, etc.) verify that the prerequisites are present in concept. The shakedown takes the car around the track at full speed before the race: it runs the magi code-paths end-to-end against live `state.json`, the live `inflight/` directory, and the live bd database. Pre-flight catches what is missing; the shakedown catches what is misconfigured.

### Triggers

`_shakedown(verb_log, prior_shakedown, results)` runs the lap when any of six triggers fires (declared in `scripts/magi_doctor.py`):

1. `never-run` — `state.doctor.shakedown.last_run_at` is `None`.
2. `script-modified` — `scripts/magi_doctor.py` mtime_ns or SHA-256 differs from the recorded values in `state.doctor.shakedown.script_mtime_ns` / `.script_sha256`.
3. `tunables-changed` — `shakedown_tunable_fingerprint()` differs from `state.doctor.shakedown.tunable_fingerprint`. The fingerprinted env keys are `GC_CITY_PATH`, `GC_CITY_ROOT`, `GC_PACK_STATE_DIR`, `MAGI_UTILITIES_SOURCE`, `LM_STUDIO_URL`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `INSTALL_REMOTE_MCP` (declared as `_DOCTOR_TUNABLE_ENV_KEYS` in `magi_common.py`).
4. `errors-in-run` — any prior check in the same doctor run produced a non-zero rc.
5. `install-trigger-file` — `runtime_dir()/shakedown_trigger` exists. `magi_install.py::_write_shakedown_trigger()` writes this sentinel after a successful non-dry-run install. The shakedown unlinks the file after observation, so the trigger is one-shot.
6. `interval-elapsed` — more than `SHAKEDOWN_INTERVAL_SECONDS` (3600 seconds) elapsed since `last_run_at`.

When no trigger fires, the shakedown logs `shakedown: skipped reason=no-triggers` and returns the prior entry untouched.

### Probes

When the lap runs, it executes four live probes:

| Probe                       | Function                       | What it verifies                                                                                          |
|-----------------------------|--------------------------------|-----------------------------------------------------------------------------------------------------------|
| `state-roundtrip`           | `_probe_state_roundtrip`       | `read_state` → `write_state` → `read_state` round-trip; the timestamp written under `state.doctor.shakedown.probe_at` survives the round-trip. |
| `inflight-scan`             | `_probe_inflight_scan`         | Walks `inflight/*.json`, counts sentinel files, records parse failures.                                  |
| `bd-list-live`              | `_probe_bd_list_live`          | Calls `bd list --label pack:magi --status open --json` and parses the response into a `bead_ids` list.   |
| `bd-show`                   | `_probe_bd_show`               | Calls `bd show <first-bead-id> --json` against the first listed bead.                                    |

Concurrent doctors are serialized by `fcntl.flock(LOCK_EX|LOCK_NB)` on `runtime_dir()/.shakedown.lock`. A second doctor in the same window logs `shakedown: skipped reason=concurrent-run` and returns the prior entry.

### State schema

`state.doctor.shakedown` (declared by `default_shakedown_entry()` in `magi_common.py`) carries:

| Key                    | Type        | Source                                                  |
|------------------------|-------------|---------------------------------------------------------|
| `last_run_at`          | ISO-8601 Z  | `now_utc_iso()` at lap entry                            |
| `last_run_rc`          | int         | `max(probe rcs)`                                        |
| `script_mtime_ns`      | int         | `os.stat(magi_doctor.py).st_mtime_ns`                   |
| `script_sha256`        | hex string  | SHA-256 of `magi_doctor.py`                             |
| `tunable_fingerprint`  | hex string  | `shakedown_tunable_fingerprint()`                       |
| `triggers_fired`       | list[str]   | Which of the six triggers fired this lap                |
| `last_findings`        | list[dict]  | The four probe result objects                           |

## Directory map

```
magi/
├── pack.toml                          pack manifest (name, schema, version)
├── CHANGELOG.md                       canonical feature inventory
├── CLAUDE.md                          behavioral contract (deploys with harness)
├── AGENTS.md                          pack-internal authoring contract
├── CONTRIBUTING.md                    eleven maintenance procedures
├── LICENSE.md                         MIT
├── README.md                          this file
├── settings.json.template             canonical settings template
├── .mcp.json.template                 canonical MCP template
├── .env                               pack-local env passthrough
├── .gitignore
├── scripts/                           12 verb orchestrators + 3 hooks + magi_common
├── commands/                          12 verb gc wrappers (<verb>.sh + <verb>/{command,help})
├── agents/                            28 subagent definitions
├── claude-commands/                   14 user-facing slash commands
├── mcp-servers/                       4 MCP server source trees + architecture diagram
├── enforcement/                       rules + lifecycle + cleanup + launchd + shared + prohibited + guidelines
├── guidelines/
│   ├── gsl/magi.gsl                   single-line GSL guideline
│   └── markdown_library/              52 topic dirs (51 cross-language + magi/)
├── plugins/marketplaces/local-lsp/    8 language-server plugins
├── skills/                            verify-magi-installed, verify-frontend-ux
├── doctor/                            7 check dirs + 7 check-*.sh scripts
├── formulas/                          mol-magi-bootstrap.formula.toml
├── hooks/                             magi-bd-hooks.toml
├── template-fragments/                magi-usage.template.md
├── project_analyzer/                  bottom-up analyzer + improve pipeline
├── .common/                           pack-local bash helpers
├── .utilities/                        user-authored portable utilities (rsynced byte-exact)
├── .scratch/                          build-side workspace (not deployed)
├── claude/                            vendored claude_dist upstream payload
├── codex/                             vendored codex_dist upstream payload
├── gemini/                            pack-built Gemini installer (no upstream)
└── openai/                            pack-built OpenAI/LM Studio installer
```

### `scripts/`

Foundation plus 12 verb orchestrators plus 3 bd hook targets. Every Python file imports from `magi_common` exclusively and uses the std-lib only.

- `magi_common.py` — shared constants, filesystem layout, state, redaction, bd helpers, fingerprinting, policy loading, orphan reconciliation.
- `magi_install.py` — install orchestrator with `_deploy_claude_from_pack_root` direct-deploy plus `_exec_vendored_deployer` fallback.
- `magi_uninstall.py` — close install beads, optionally purge via `--really-purge --yes`.
- `magi_analyze.py` — wraps `project_analyzer/analyze_project.sh`.
- `magi_improve.py` — wraps `project_analyzer/improve_project_analysis.sh` (three-model pipeline).
- `magi_status.py` — read-only; prints `state.json` plus open `pack:magi` beads.
- `magi_doctor.py` — registered check walker + synthetic `_orphan_beads_check` + `_shakedown` lap + four probes.
- `magi_molecule.py` — `bootstrap`, `pour`, `wisp` subcommands.
- `magi_bootstrap_project.py` — runs `setup_utilities.sh -y <project-path>`.
- `magi_remember.py` — `remember`, `recall`, `list` subcommands; magi-namespaced bd memory.
- `magi_formulas.py` — `list`, `show`, `cook` against `formulas/*.formula.toml`.
- `hook_on_failure.py` — `on:bead.failed --label pack:magi` target.
- `hook_post_install.py` — `on:bead.closed --label pack:magi:install` target.
- `hook_pre_analyze.py` — `on:bead.created --label pack:magi:analyze` target (LM Studio reachability probe).

`gc magi ready` is not a Python orchestrator; the `commands/ready.sh` dispatcher execs `bd ready --label pack:magi` directly.

### `commands/`

POSIX-sh dispatchers plus `command.toml` + `help.md` per verb. 12 entries:

```
commands/<verb>.sh              # execs scripts/magi_<verb>.py
commands/<verb>/command.toml    # description + run = "../<verb>.sh"
commands/<verb>/help.md         # usage block + flag table + example + bd note
```

The dispatchers guard `${GC_PACK_DIR}` and `${GC_CITY_PATH}` and forward argv verbatim.

### `agents/`

28 subagent definitions (one Markdown file per agent). Loaded by the deployed harness `Task` tool; routed by name. Citations inside agent prompts reference `${MAGI_PACK_DIR}/guidelines/markdown_library/<topic>/OVERVIEW.md` so deployment substitutes them to the deployed harness root.

Index: `api-designer`, `architecture-advisor`, `bash-script-enforcer`, `bashforge-script-generator`, `code-reviewer`, `csharp-forge`, `database-architect`, `deployment-guardian`, `dev-tracker`, `devops-engineer`, `documentation-writer`, `frontend-developer`, `gradle-forge`, `ignition-master`, `java-forge`, `maven-forge`, `neurotic-code-quality`, `performance-optimizer`, `plan-agent`, `python-forge`, `react-forge`, `react`, `rust-forge`, `security-auditor`, `test-engineer`, `tree-structure-documenter`, `utilities-agent`, `yew-forge`.

### `claude-commands/`

14 slash commands the operator invokes inside a Claude Code session as `/<command>`. Distinct from the shell-level `gc magi <verb>`; the two surfaces overlap intentionally for workflows that benefit from in-session invocation.

`/bash-crew`, `/check-project`, `/consult`, `/enforce-automation`, `/enhance-guidelines`, `/frontend-crew`, `/full-stack-crew`, `/gsl`, `/rust-crew`, `/scope`, `/scope-reminder`, `/scrub`, `/scrub_mongodb`, `/superwork`.

### `mcp-servers/`

Four MCP server source trees plus a Mermaid architecture diagram (`mcp-architecture.mmd`) and a directory README. The installer rsyncs each tree into the deploy home and runs `npm install --silent --no-fund --no-audit` per server directory containing a `package.json`.

| Server                 | Purpose                                                                                                                  |
|------------------------|--------------------------------------------------------------------------------------------------------------------------|
| `guidelines-retriever` | Serves markdown_library topic content via MCP; resolves by topic name + section anchor.                                  |
| `project-memory`       | Per-project memory store; survives session compaction.                                                                   |
| `system-info`          | Reports host OS, CPU, RAM, process inventory; used by doctor diagnostics.                                                |
| `remote-shell`         | sshpass-bridged remote shell for the LSP host; credentials sourced from `LSP_USER`/`LSP_PASS`/`LSP_IP`/`LSP_REMOTE_HOME`. |

### `enforcement/`

The harness enforcement layer. Seven subdirectories.

| Subdir          | Contents                                                                                                                                                                                                                       |
|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `rules/`        | `enforce-rules.sh` + `enforcement_rules.json` — pattern → severity → message rule set.                                                                                                                                         |
| `lifecycle/`    | 12 session lifecycle hooks: `clear-extensionless-tracking.sh`, `detect-compaction.sh`, `enforce-agent-routing.sh`, `enforce-file-extension.sh`, `enforce-ssh-sshpass.sh`, `enforcement-cache.sh`, `history-per-project.sh`, `inject-global-feedback.sh`, `session-start-cleanup.sh`, `session-tracker.sh`, `stop-verify-quality.sh`, `sweep-stale-artifacts.sh`. |
| `cleanup/`      | 6 periodic scripts run via launchd: `daily-age-sweep.sh`, `daily-bak-sweep.sh`, `hourly-cleanup.sh`, `hourly-history-partition.sh`, `merge-dotted-projects.sh`, `quarter-hourly-memory-sync.sh`.                              |
| `launchd/`      | 5 LaunchAgent plists (`com.__USER_NAME__.claude-cleanup-{daily-aging,daily-bak,history,hourly,memory}.plist`) plus `install.sh`. Installer registers them under `~/Library/LaunchAgents/` and renames `com.__USER_NAME__.` → `com.<user>.`. |
| `shared/utils/` | Sourced helpers (project-key collapse, log routing, color, path resolution).                                                                                                                                                   |
| `prohibited/`   | Tracking-file root referenced by `prohibited_behavior` markdown_library topic.                                                                                                                                                 |
| `guidelines/`   | `enforce-guidelines.sh`, `force-prohibited-read.sh`, `session-start-guidelines.sh` — hook scripts that gate session-start on reading the applicable guideline.                                                                |

Reinstall the launchd agents after a deploy: `bash ${MAGI_PACK_DIR}/enforcement/launchd/install.sh` (the placeholder resolves to the deployed harness root). Linux is not applicable; the `launchd` doctor check returns 0 with a note.

### `guidelines/markdown_library/`

52 topic directories. Each ships `OVERVIEW.md` plus topic-specific files. YAML frontmatter in `OVERVIEW.md` declares constants consumed by `magi_common.load_policy(topic)`.

Cross-language topics (51): `angular`, `angular_js`, `apache_wicket`, `api`, `application_dockerization`, `auth`, `automation_principles`, `azure_variable`, `bash`, `bicep`, `cicd`, `cosmosdb`, `csharp`, `datadog`, `docker`, `domain_infrastructure`, `email_authentication`, `frontend`, `gradle`, `ignition_v81`, `ignition_v83`, `java17`, `kafka`, `kubernetes`, `lxc`, `maven`, `netlify`, `nginx`, `powerquery`, `powershell`, `prohibited_behavior`, `python`, `rabbit_mq`, `react_node16`, `real_writing_style`, `redis`, `rust`, `session_recording`, `snowflake`, `sql`, `storage_and_messaging_principles`, `stripe`, `swift`, `typescript_react_node`, `utilities`, `vue_nuxt`, `wicket`, `woocommerce`, `wordpress`, `yew`, `zenfolio_integration`.

Magi-specific topic: `magi/` ships `OVERVIEW.md`, `analyze.md`, `beads.md`, `deploy.md`, `doctor.md`, `improve.md`, `molecule.md`, `utilities.md`.

| Orchestrator                | Topic file              | Drives                                                                                  |
|-----------------------------|-------------------------|-----------------------------------------------------------------------------------------|
| `magi_install.py`           | `magi/deploy.md`        | backup policy, idempotency window, purge gate                                           |
| `magi_uninstall.py`         | `magi/deploy.md` (§rollback) | retention rules, purge confirmation                                                 |
| `magi_analyze.py`           | `magi/analyze.md`       | ignore list, sha-256 idempotency, LM Studio prereq                                      |
| `magi_improve.py`           | `magi/improve.md`       | three-model pipeline, resume semantics                                                  |
| `magi_doctor.py`            | `magi/doctor.md`        | exit-code semantics, shakedown triggers and probes                                      |
| `magi_status.py`            | `magi/beads.md`         | label taxonomy, hook contracts, timeouts                                                |
| `magi_molecule.py`          | `magi/molecule.md`      | bootstrap-chain step list, on-failure semantics                                         |
| `magi_bootstrap_project.py` | `magi/utilities.md`     | `setup_utilities.sh` invocation, symlink verification                                   |

### `guidelines/gsl/magi.gsl`

Single-line GSL-format encoding of the magi guideline. Sections: `core / install / analyze / improve / doctor / bd / utilities / prohibited / required`. Header `MAGI/pack/schema2|`. The GSL is the only pack-shipped file exempt from the determinate-language gate by design (GSL uses the shortcode dictionary). Regenerate via the `/gsl` slash command; overwrite policy is `replace`.

### `plugins/marketplaces/local-lsp/`

LSP marketplace shipping 8 language-server plugins:

`bash-lsp`, `clangd-lsp`, `csharp-lsp`, `java-lsp`, `pyright-lsp`, `rust-analyzer-lsp`, `swift-lsp`, `typescript-lsp`.

Marketplace manifest at `plugins/marketplaces/local-lsp/.claude-plugin/marketplace.json`. The LSP host is reached via the `remote-shell` MCP server.

### `skills/`

Two skills.

| Skill                   | Purpose                                                                                                                                                |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| `verify-magi-installed` | Verifier-agent contract: which evidence is accepted vs. rejected when proving install state. Probes `state.json` and closed `pack:magi` beads only.   |
| `verify-frontend-ux`    | Browser-driven UX verification for frontend pack consumers; rejects unit / integration / snapshot / API / curl-based "tests" as proof of completion.  |

### `project_analyzer/`

Bottom-up project analyzer plus three-model improvement pipeline.

- `analyze_project.sh` — entry point invoked by `magi analyze`.
- `improve_project_analysis.sh` — entry point invoked by `magi improve`.
- `_analyzer.py`, `_improver.py` — Python implementations.
- `LM_STUDIO_API.md`, `README.md`, `CHANGELOG.md` — documentation.

### `template-fragments/`

`magi-usage.template.md` — Go text/template `{{ define "magi-usage" }}` block. The city imports it via `[agent_defaults] append_fragments = ["magi-usage"]`. The fragment surfaces the 4 use-cases + 4 anti-patterns + 6-step protocol to every city agent.

### `doctor/`

Per-check directories. Each contains `doctor.toml` with `description` and `run = "../check-<name>.sh"`. The 7 check scripts (`check-beads.sh`, `check-deploy-prereqs.sh`, `check-launchd.sh`, `check-lmstudio.sh`, `check-python.sh`, `check-ssh.sh`, `check-utilities.sh`) sit at `doctor/` root and exit `0` / `1` / `2`.

### `formulas/`

`mol-magi-bootstrap.formula.toml` — `doctor → install → bootstrap-project → status → analyze` chain. `doctor` and `install` carry `on_fail = "stop"`; remaining steps carry `on_fail = "continue"`. Variables: `target` (default `claude`), `project_path` (required).

### `hooks/`

`magi-bd-hooks.toml` — 3 bd hook registrations (see §"Hooks" below).

### `claude/`, `codex/`, `gemini/`, `openai/`

Per-runtime payload trees.

- `claude/` — per-runtime metadata directory. Carries `README.md` only; the direct-deploy installer reads its full payload from pack root (`agents/`, `commands/`, `claude-commands/`, `enforcement/`, `guidelines/`, `mcp-servers/`, `plugins/`, `scripts/`, `skills/`, `CLAUDE.md`, `settings.json.template`, `.mcp.json.template`).
- `codex/` — byte-exact vendored upstream `codex_dist`. `deploy_harness.sh` + `harness/` + `README.md`.
- `gemini/` — pack-built Gemini installer. `deploy_gemini.sh` + `harness/` + `README.md`. No upstream exists yet.
- `openai/` — pack-built OpenAI/LM Studio installer. `deploy_openai.sh` + `templates/` + `README.md`. Configures LM Studio + the OpenAI-compatible shim.

Vendored trees are never modified in-place. Re-promote via `CONTRIBUTING.md` §1.

### `.utilities/`

User-authored portable utilities tree. Rsynced byte-exact (no placeholder substitution). Consumed by post-install (`claude`/`codex` only) and by `gc magi bootstrap-project`. See `.utilities/UTILITIES_README.md` for content.

### `.common/`

Pack-local bash helpers sourced by `commands/<verb>.sh`: `bd_subprocess.sh`, `colors.sh`, `config.sh`, `logging.sh`, `utils.sh`.

### `.scratch/`

Build-side workspace. Holds shakedown logs and cleanup-plan scaffolding under `.scratch/magi-build/`. Not deployed.

### Pack-root metadata files

- `pack.toml` — `[pack] name = "magi"`, `schema = 2`, `version = "0.2.0"` per the manifest.
- `settings.json.template` — canonical pack-source template for the deployed `settings.json`. Deep-merged with any existing target file at install time.
- `.mcp.json.template` — canonical pack-source template for the deployed `.mcp.json`. Same deep-merge contract.
- `CLAUDE.md` — behavioral contract. Deploys with the harness; binding for any agent operating under the deployed runtime.
- `AGENTS.md` — pack-internal authoring contract. Strict mode: zero install-destination references, zero `~/.claude/...`, zero `/Users/<u>/...` absolute paths.
- `CHANGELOG.md` — Keep-a-Changelog 1.1.0 format. Source of truth for the feature inventory by release.
- `CONTRIBUTING.md` — eleven procedural sections (re-vendoring, re-promoting, adding verbs / targets / doctor checks / placeholders / markdown_library topics, regenerating GSL, re-running shakedown, external-reference invariant).
- `LICENSE.md` — MIT, magi pack maintainers.

## `magi_common.py` public API

Every verb script imports from `magi_common` exclusively (first-party). The public surface:

### Filesystem

| Symbol            | Signature                                          | Returns                                                                                       |
|-------------------|----------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `pack_root`       | `() -> Path`                                       | The magi pack root directory (parent of `scripts/`).                                          |
| `city_root`       | `() -> Path`                                       | Resolves `GC_CITY_PATH` or `GC_CITY_ROOT`. Raises `CLIError(exit_code=2)` when neither is set. |
| `runtime_dir`     | `() -> Path`                                       | `${GC_PACK_STATE_DIR}` when set; else `city_root() / ".gc" / "runtime" / "packs" / "magi"`.   |
| `state_path`      | `() -> Path`                                       | `runtime_dir() / "state.json"`.                                                               |
| `inflight_path`   | `() -> Path`                                       | `runtime_dir() / "inflight"`.                                                                 |
| `logs_dir`        | `() -> Path`                                       | `runtime_dir() / "logs"`.                                                                     |
| `log_path`        | `(verb: str, target: str | None = None) -> Path`   | `logs_dir() / "<verb>[-<target>]-<utc>.log"`.                                                 |
| `pack_env_path`   | `() -> Path`                                       | `pack_root() / ".env"`.                                                                       |
| `load_pack_env`   | `() -> dict[str, str]`                             | Loads pack-root `.env` into `os.environ` without overriding callers; runs once per process.   |

### Time

| Symbol         | Signature       | Returns                                                                |
|----------------|-----------------|------------------------------------------------------------------------|
| `now_utc_iso`  | `() -> str`     | Current UTC time as ISO-8601 with `Z` suffix at seconds precision.    |

### Secret redaction

| Symbol            | Signature                  | Behavior                                                                                                                            |
|-------------------|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| `redact_secrets`  | `(text: object) -> object` | Walks dicts / lists / tuples; per-key match against `SECRET_KEY_PATTERNS`. Strings pass through `_SECRET_INLINE_REGEX`. Other types unchanged. |

### Logging

| Symbol           | Signature                                                  | Behavior                                                                                       |
|------------------|------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| `attach_file_log`| `(verb: str, log_file: Path) -> None`                      | Attaches a FileHandler at mode `0644` (created), writes UTF-8, INFO-level format.              |
| `log_event`      | `(verb: str, message: str, level: int = logging.INFO)`     | Logs the message after `redact_secrets()` rewrites it. Stderr StreamHandler is always attached. |

### State

| Symbol         | Signature                                                                        | Behavior                                                                                       |
|----------------|----------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| `read_state`   | `() -> dict[str, object]`                                                        | Reads `state.json`; returns `_default_state()` when absent or invalid.                         |
| `write_state`  | `(state: dict[str, object]) -> None`                                             | Redacts via `_redact_structure`; writes via temp-then-`os.replace` at mode `0600` (umask-respecting). |
| `record_run`   | `(section: str, key: str, payload: dict[str, object]) -> None`                   | Read-modify-write helper that records `state[section][key] = payload`.                         |

### Fingerprinting

| Symbol                              | Signature                                       | Returns                                                                                                  |
|-------------------------------------|-------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| `flag_fingerprint`                  | `(argv: list[str], env_keys: list[str]) -> str` | SHA-256 hex digest over argv plus sorted env keys. Secret-keyed values pass through `<redacted>` first.  |
| `shakedown_tunable_fingerprint`     | `() -> str`                                     | SHA-256 hex digest over sorted `_DOCTOR_TUNABLE_ENV_KEYS` env values (redaction-before-hash).            |
| `default_shakedown_entry`           | `() -> dict[str, object]`                       | Default `state.doctor.shakedown` sub-dict (see §"Shakedown state schema").                               |

### Policy

| Symbol         | Signature                                | Behavior                                                                                                                                    |
|----------------|------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `load_policy`  | `(topic: str) -> dict[str, object]`      | Parses YAML frontmatter from `guidelines/markdown_library/magi/<topic>.md`. Std-lib parser; scalars + simple lists + one level of nesting. Cached. |

### `.utilities/`

| Symbol                  | Signature                            | Behavior                                                                                                                                                                                          |
|-------------------------|--------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `magi_utilities_source` | `(verb: str = "utilities") -> Path | None` | Resolves precedence: `MAGI_UTILITIES_SOURCE` env → `${MAGI_PACK_DIR}/.utilities/` (pack-internal) → `${HOME}/.scripts/.utilities/` (legacy). Each resolution emits an audit-trail `log_event` line. |

### bd integration

| Symbol                  | Signature                                                                                                                                  | Behavior                                                                                                                                                       |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `bd_available`          | `(path_signature: str = "") -> bool`                                                                                                       | `shutil.which("bd")`-backed. `path_signature` is the LRU-cache key.                                                                                            |
| `bd_available_current`  | `() -> bool`                                                                                                                                | Probes against the current `PATH`.                                                                                                                              |
| `try_bd`                | `(args: list[str], timeout: int = 10, verb: str = "bd") -> CompletedProcess[str] | None`                                                  | Subprocess wrapper bounded by `timeout`. Returns `None` when `bd` is missing or times out. Distinguishes Dolt-unreachable (INFO) from other non-zero (WARNING). |
| `bd_create`             | `(title: str, body: str, labels: dict[str, str], verb: str = "bd", timeout: int = 10) -> str | None`                                       | Creates a bead. Returns bead id on success, `None` on degraded paths. Hook-reentrant short-circuits.                                                            |
| `bd_update`             | `(bead_id: str, body: str | None = None, labels: dict[str, str] | None = None, claim: bool = False, verb: str = "bd", timeout: int = 10) -> bool` | Updates body / labels / claim. Returns `True` on rc=0.                                                                                                          |
| `bd_close`              | `(bead_id: str, outcome: str, labels: dict[str, str] | None = None, verb: str = "bd", timeout: int = 20) -> bool`                          | Applies outcome label via `bd update --add-label` BEFORE issuing `bd close`. (Upstream `bd close` does not accept `--label`.)                                  |
| `bd_remember`           | `(key: str, value: str, verb: str = "bd", timeout: int = 10) -> bool`                                                                      | `bd remember --key magi:<key> <value>`. Redacts the value.                                                                                                      |
| `bd_label`              | `(bead_id: str, key: str, value: str, verb: str = "bd", timeout: int = 10) -> bool`                                                        | `bd label <id> --add <key>:<value>`. Raises `ValueError` on `MAGI_LABEL_SCHEMA` violation.                                                                      |
| `bd_dep`                | `(parent_id: str, child_id: str, verb: str = "bd", timeout: int = 10) -> bool`                                                              | `bd dep add <parent> <child>`.                                                                                                                                  |
| `bd_show`               | `(bead_id: str, verb: str = "bd", timeout: int = 10) -> dict[str, object] | None`                                                          | `bd show <id> --json`. Returns parsed dict or `None`.                                                                                                           |
| `bd_list_pack`          | `(status: str | None = None, extra_labels: list[str] | None = None, verb: str = "bd", timeout: int = 10) -> list[dict[str, object]]`     | `bd list --label pack:magi [--label <extra>] --json`. Returns `[]` on degraded paths.                                                                           |

### Inflight + orphans

| Symbol                      | Signature                                                          | Behavior                                                                                                                  |
|-----------------------------|--------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| `write_inflight_sentinel`   | `(bead_id: str, verb: str, target: str | None = None) -> Path`     | Writes `inflight/<bead_id>.json` carrying `bead_id`, `verb`, `target`, `pid`, `started_at`.                              |
| `clear_inflight_sentinel`   | `(bead_id: str) -> None`                                           | Removes the sentinel. Idempotent on missing file.                                                                         |
| `reconcile_orphans`         | `(verb: str = "reconcile") -> int`                                 | Walks `inflight/*.json`; closes each stale bead with `outcome=orphaned`; clears the sentinel. Process-locally memoized. Returns count closed. |

### Module-level constants (operational)

`BD_DEFAULT_TIMEOUT_SECONDS=10`, `BD_CLOSE_TIMEOUT_SECONDS=20`, `BD_PUSH_TIMEOUT_SECONDS=60`, `IDEMPOTENT_WINDOW_SECONDS=300`, `ORPHAN_THRESHOLD_SECONDS=3600`, `SHAKEDOWN_INTERVAL_SECONDS=3600`, `SHAKEDOWN_TRIGGER_FILENAME="shakedown_trigger"`, `STATE_SCHEMA_VERSION=4`, `PACK_NAME="magi"`, `PACK_LABEL="pack:magi"`, `PACK_DIR_PLACEHOLDER="${MAGI_PACK_DIR}"`, `SUBSTITUTABLE_EXTENSIONS` (11 entries), `SECRET_BEARING_FILES = {.mcp.json, settings.json, enforcement/env}`, `RUNTIME_STATE_PATHS` (6 entries), `CROSS_RUNTIME_EXEMPTIONS` (6 entries), `_UTILITIES_AWARE_TARGETS = {claude, codex}`, `INSTALL_PLACEHOLDERS` (15 entries), `SECRET_KEY_PATTERNS` (21 patterns), `MAGI_LABEL_SCHEMA` (5 keys), `TARGET_REGISTRY` (4 targets), `_DOCTOR_TUNABLE_ENV_KEYS` (8 keys).

Private helpers (`_`-prefixed): `_strip_env_quotes`, `_expand_env_value`, `_parse_pack_env_line`, `_ensure_runtime_layout`, `_is_secret_key`, `_redact_structure`, `_verb_logger`, `_default_state`, `_default_install_entry`, `_parse_frontmatter_scalar`, `_parse_frontmatter_block`, `_candidate_utilities_dir`, `_is_hook_reentrant`, `_is_dolt_unreachable_stderr`, `_label_args`, `_validate_label`.

## bd integration contract

Every verb participates in the bd lifecycle:

```
parse argv → reconcile_orphans() → bd_create() → bd_update(--claim) →
write_inflight_sentinel() → subprocess work → bd_close(outcome={0,1,2}) →
clear_inflight_sentinel() → bd hook fires → state.json refresh
```

### Label taxonomy (`MAGI_LABEL_SCHEMA`)

`bd_label()` raises `ValueError` on schema violation. The five keys plus their domains:

| Key       | Domain                                                                                                                                       |
|-----------|----------------------------------------------------------------------------------------------------------------------------------------------|
| `pack`    | `{magi}`                                                                                                                                     |
| `verb`    | `{install, uninstall, analyze, improve, status, doctor, molecule, bootstrap-project, remember, recall, ready, formulas}`                     |
| `target`  | `{claude, codex, gemini, openai, project, all}`                                                                                              |
| `outcome` | `{0, 1, 2, interrupted, orphaned, partial}`                                                                                                  |
| `role`    | `{root, child, hook-trigger, uninstall-closure}`                                                                                             |

Every bd write helper redacts label values via `redact_secrets()` before issuing the subprocess.

### Idempotency

`IDEMPOTENT_WINDOW_SECONDS=300`. A re-run reuses the prior bead id when (1) the prior bead closed `outcome=0`, (2) `flag_fingerprint()` matches over the union of argv + every documented env-passthrough variable, and (3) elapsed time is under 300 seconds. `flag_fingerprint()` is SHA-256 over a redacted `key=value` newline-joined payload; secrets never enter the hash input in clear form.

### Graceful degradation

`bd_available_current()` resolves `PATH` per process. When `bd` is missing, every write helper short-circuits to `None` / `False`, `state.json` records `bd_available=false`, and the `beads` doctor check warns. No verb fails because `bd` is absent.

### Orphan reconciliation

Every verb's `main()` calls `reconcile_orphans()` as the first action after argument parsing. The function walks `inflight/*.json`, closes each stale bead with `outcome=orphaned`, and clears the sentinel. Process-locally memoized — subsequent calls in the same process are no-ops.

## Hooks

`hooks/magi-bd-hooks.toml` registers three bd hooks. Every hook script reads via `bd_show` only — zero bd writes. The recursion guard is structural: hook scripts never call bd write helpers, so re-firing is impossible by construction. The `MAGI_HOOK_REENTRANT=1` env plus the `role:hook-trigger` label filter exist as the second and third layers of defense.

| Hook script                | Registered on    | Label filter                                                                                  | Action                                                                                                          |
|----------------------------|------------------|-----------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| `hook_post_install.py`     | `bead.closed`    | `pack:magi:install` + `outcome:0`; NOT `role:uninstall-closure`; NOT `role:hook-trigger`     | Refresh `state.json` `installs.<target>` from the closed install bead.                                          |
| `hook_pre_analyze.py`      | `bead.created`   | `pack:magi:analyze`; NOT `role:hook-trigger`                                                  | Probe `${LM_STUDIO_URL:-http://localhost:1234}` via urllib; exits 0 on 2xx, 2 otherwise.                       |
| `hook_on_failure.py`       | `bead.failed`    | `pack:magi`; NOT `role:hook-trigger`                                                          | Append a failure record to `state.json` `failures: []`.                                                         |

## The `.utilities/` pattern

The pack ships `.utilities/` byte-exact under `${MAGI_PACK_DIR}/.utilities/`. The deployer rsyncs the tree into deploy homes whose target is in `_UTILITIES_AWARE_TARGETS = {claude, codex}` and runs `setup_utilities.sh -y <deploy-home>` as a post-deploy step.

`magi_utilities_source(verb)` resolves the source in this precedence:

1. `MAGI_UTILITIES_SOURCE` env override (when set and the resolved path passes the dir + executable-setup probes).
2. `${MAGI_PACK_DIR}/.utilities/` (pack-internal — primary).
3. `${HOME}/.scripts/.utilities/` (legacy fallback for installs from the pre-cleanup era).
4. `None` — no source resolves.

Every resolution emits a `log_event(verb, ...)` audit-trail line. `doctor/check-utilities.sh` cross-checks the most recent install log's `resolved source=` marker against its own resolution; disagreement warns (rc=2).

`gc magi bootstrap-project <project-path>` runs the same `setup_utilities.sh -y` against any project root so consumer rigs in a city bootstrap `.utilities/` on demand. Full contract: `guidelines/markdown_library/magi/utilities.md`.

## Install flow internals (claude direct-deploy)

`_deploy_claude_from_pack_root(deploy_home, args, verb_log)` in `magi_install.py` runs the stage-and-swap pipeline. Eight stages:

1. **Snapshot** — `_snapshot_pre_mutation()` writes `<file>.pre-magi-<utc>.bak` per existing file. `_whole_tree_backup()` writes `<deploy-home>_backup-<utc>/`.
2. **Stage** — `_stage_pack_source()` rsyncs every pack-root surface into `<deploy-home>.staging-<utc>/`.
3. **Substitute** — `_walk_substitute()` iterates every file whose extension is in `SUBSTITUTABLE_EXTENSIONS`; replaces `${MAGI_PACK_DIR}` plus every entry of `INSTALL_PLACEHOLDERS` (15 placeholders) using values resolved by `_build_placeholder_map()`. Required-but-missing placeholders abort the install with a non-zero rc.
4. **Set mode** — `_apply_secret_mode()` applies mode `0600` to every staging path matching `SECRET_BEARING_FILES = {.mcp.json, settings.json, enforcement/env}`. This runs BEFORE the atomic rename so the deployed inode is never readable at a wider mode.
5. **Deep-merge** — `_deep_merge_staged_files()` jq-equivalent merges any existing `settings.json` / `.mcp.json` at the deploy home into the staged version.
6. **Atomic swap** — `_atomic_swap()` renames `<deploy-home>.staging-<utc>/` over the deploy home.
7. **Verify modes** — `_verify_secret_modes()` re-stats every `SECRET_BEARING_FILES` entry and aborts on any deviation.
8. **Post-deploy** — `_npm_install_servers()` runs `npm install` per `mcp-servers/*/package.json`. `_rename_launchd_plists()` rewrites `com.__USER_NAME__.<service>.plist` to `com.<user>.<service>.plist`. `_post_deploy_invariant_grep()` runs `grep -RIE '\$\{MAGI_PACK_DIR\}' <deploy-home> --exclude-dir=.utilities --exclude-dir=claude` and aborts on any residual match. `_run_post_deploy_utilities()` runs `setup_utilities.sh -y` against the deploy home. `_write_shakedown_trigger()` writes the one-shot trigger sentinel (success path only, non-dry-run only).

### `INSTALL_PLACEHOLDERS`

Declared once in `magi_common.py`. 15 placeholders substituted at install time:

| Placeholder                        | Source                                 | Redacted in logs |
|------------------------------------|----------------------------------------|------------------|
| `${MAGI_PACK_DIR}`                 | computed (resolved deploy home)        | no               |
| `__USER_HOME__`                    | `HOME`                                 | no               |
| `__USER_NAME__`                    | `USER`                                 | no               |
| `__CLAUDE_HOME__`                  | computed                               | no               |
| `__LSP_PASS__`                     | `LSP_PASS`                             | **yes**          |
| `__LSP_USER__`                     | `LSP_USER`                             | no               |
| `__LSP_IP__`                       | `LSP_IP`                               | no               |
| `__LSP_REMOTE_HOME__`              | `LSP_REMOTE_HOME`                      | no               |
| `__BRAVE_API_KEY__`                | `BRAVE_API_KEY`                        | **yes**          |
| `__GITHUB_PERSONAL_ACCESS_TOKEN__` | `GITHUB_PERSONAL_ACCESS_TOKEN`         | **yes**          |
| `__MY_GITEA_API_TOKEN__`           | `MY_GITEA_API_TOKEN`                   | **yes**          |
| `__MY_GITEA_HOST__`                | `MY_GITEA_HOST`                        | no               |
| `__MY_GITEA_PORT__`                | `MY_GITEA_PORT`                        | no               |
| `__LM_STUDIO_HOST__`               | `LM_STUDIO_HOST` (default `127.0.0.1`) | no               |
| `__LM_STUDIO_PORT__`               | `LM_STUDIO_PORT` (default `1234`)      | no               |
| `__LM_STUDIO_URL__`                | `LM_STUDIO_URL`                        | no               |

Optional placeholders (Brave, GitHub, Gitea) substitute to empty strings when unset and disable the dependent MCP server entry.

## State and logs

Runtime root: `${GC_CITY_PATH}/.gc/runtime/packs/magi/`.

| Path                              | Purpose                                                                                  | Mode |
|-----------------------------------|------------------------------------------------------------------------------------------|------|
| `state.json`                      | per-verb state, `schema_version=4`                                                       | 0600 |
| `inflight/<bead_id>.json`         | per-bead sentinels; closed by `reconcile_orphans()` on next verb invocation              | 0600 |
| `logs/<verb>-<target>-<utc>.log`  | per-invocation log; ANSI-stripped, secret-redacted                                       | 0600 |
| `shakedown_trigger`               | one-shot sentinel written by `magi install`; consumed by next `magi doctor`              | 0644 |
| `.shakedown.lock`                 | `fcntl.flock`-held during a shakedown lap                                                | 0644 |

Sample `state.json` shape from `gc magi status --json`:

```json
{
  "schema_version": 4,
  "pack_version": "0.2.0",
  "bd_available": true,
  "installs": {
    "claude": {
      "installed": true,
      "target": "/Users/.../.claude",
      "last_run_timestamp": "2026-05-13T09:46:45Z",
      "last_run_rc": 0,
      "bead_id": "gas-abcd",
      "utilities_linked": true,
      "deploy_mode": "direct",
      "flag_fingerprint": "<sha256>",
      "feature_flags": {"LSP_PASS": "<redacted>", "LM_STUDIO_URL": "http://localhost:1234"}
    }
  },
  "doctor": {
    "shakedown": {
      "last_run_at": "2026-05-13T09:48:01Z",
      "last_run_rc": 0,
      "triggers_fired": ["install-trigger-file"],
      "last_findings": [{"probe": "state-roundtrip", "rc": 0}, ...]
    }
  }
}
```

## Determinate-language gate

Pack-source markdown, code comments, `.toml` `description` fields, every help.md, and every agent definition exclude the banned hedge tokens: `should`, `would`, `could`, `might`, `may`, `maybe`, `perhaps`. Emojis are banned (the GSL file is the single exception by design — it uses the GSL shortcode dictionary). The gate is binding for any contributor authoring pack-source content. Full ruleset: `guidelines/markdown_library/prohibited_behavior/OVERVIEW.md`. Enforcement is mechanical via `tests/test_determinate_language.py` plus the 12th shakedown check's pack-source pass.

## Rollback

```bash
gc magi uninstall --target claude --yes                       # close install beads; state-only
gc magi uninstall --target claude --really-purge --yes        # remove deploy home (irreversible without backup)
mv ${HOME}/.claude_backup-<utc> ${HOME}/.claude               # restore from whole-tree backup
find ${HOME}/.claude -name '*.pre-magi-*.bak' -print          # locate per-file backups
rm -rf "${GC_CITY_PATH}/.gc/runtime/packs/magi"               # clear pack runtime state
```

The `--really-purge` two-flag gate (`--really-purge` + `--yes`) is required for any filesystem mutation. `<deploy-home>_backup-<utc>/` survives uninstall.

## Troubleshooting

| Symptom                                                                                              | Cause                                                                | Resolution                                                                                                                                  |
|------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `gc magi status` shows `bd_available=false`                                                          | `bd` binary missing on PATH                                          | Install bd, or accept degraded status; the `beads` check warns but does not fail.                                                           |
| `gc magi analyze` exits non-zero before writing any file                                             | LM Studio unreachable at `${PROJECT_ANALYZER_LM_URL}`                | `lms server start`; verify `curl ${URL}/v1/models` returns 200.                                                                             |
| `gc magi install --target claude` fails with `sshpass: command not found` and `INSTALL_REMOTE_MCP=1` | sshpass missing                                                      | Install sshpass; the `ssh` check fails when `INSTALL_REMOTE_MCP=1`.                                                                         |
| `bd ready --label pack:magi` shows `in_progress` beads older than 1h                                 | A prior verb was SIGKILLed; orphan sentinel present                  | Run any magi verb; `reconcile_orphans()` closes the orphan with `outcome=orphaned`.                                                         |
| Install succeeded but `state.json` `installs.<target>.utilities_linked=false`                        | `magi_utilities_source()` returned `None`                            | Export `MAGI_UTILITIES_SOURCE=<abs path>` or restore `${MAGI_PACK_DIR}/.utilities/`.                                                        |
| `state.json` references a target home that no longer exists                                          | Manual `rm -rf <home>` without `gc magi uninstall`                   | `gc magi uninstall --target <name> --yes` syncs state.                                                                                      |
| `gc magi install --target claude` aborts with "residual ${MAGI_PACK_DIR} matches"                    | Substitution failed for at least one file                            | Inspect the failing file list; the whole-tree backup at `<deploy-home>_backup-<utc>/` restores prior state; fix the offending pack-source file and re-run.            |
| Post-install `.mcp.json` is world-readable                                                           | Mode-set ordering regressed                                          | Re-run the install; the deployer chmods 0600 in staging BEFORE the atomic rename, so the deployed inode is never readable at a wider mode. |

## Contributing

`CONTRIBUTING.md` covers the maintenance procedures: pack-root canonical layout, adding a verb, adding a target, adding a doctor check, regenerating the GSL, adding a placeholder, adding a markdown_library topic, re-running the 12th shakedown check, and the external-reference invariant. Every procedure is copy-paste runnable on a clean checkout. Read the document before opening a PR.

Pull-request gates: `bash ${MAGI_PACK_DIR}/.scratch/magi-build/shakedown.sh` returns `12/12 PASS`; `pytest tests/` is green; the CHANGELOG carries an entry under the active section.

## License

MIT. magi pack maintainers. See `LICENSE.md`.
