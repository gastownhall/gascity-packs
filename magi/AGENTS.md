# Magi Pack — AGENTS.md

`AGENTS.md` is the pack-internal authoring contract for the magi Gas City pack. It documents what the pack ships, how the primitives compose, and the invariants every contributor and verb-implementer respects. The file is born self-contained: every path reference inside resolves against pack-relative paths or the `${MAGI_PACK_DIR}` placeholder. Tilde-rooted runtime paths, `${HOME}`-rooted runtime paths, absolute `/Users/<name>` paths, and sibling-runtime forms for codex, gemini, and openai are excluded. This rule is stricter than the README/CHANGELOG/CONTRIBUTING rule: AGENTS.md has no install-destination context exemption.

## 1. Pack identity

| Field   | Value                                                                                                                                                |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| name    | `magi`                                                                                                                                               |
| schema  | `2`                                                                                                                                                  |
| version | `0.2.0`                                                                                                                                              |
| license | MIT (see `${MAGI_PACK_DIR}/LICENSE.md`)                                                                                                              |
| owner   | gas-city packs maintainers                                                                                                                           |
| source  | `pack.toml` `[pack]` block                                                                                                                           |

The pack ships, at pack root, the canonical Claude harness payload plus the magi orchestrator surface. Everything below is reachable from `${MAGI_PACK_DIR}` without external dependencies:

- 12 verbs implemented as Python orchestrators under `${MAGI_PACK_DIR}/scripts/` plus POSIX-sh dispatchers under `${MAGI_PACK_DIR}/commands/`
- 28 pack-internal subagent definitions under `${MAGI_PACK_DIR}/agents/`
- 14 user-facing slash commands under `${MAGI_PACK_DIR}/claude-commands/`
- 49 + 8 markdown_library topic directories under `${MAGI_PACK_DIR}/guidelines/markdown_library/` (49 cross-language topics plus 8 magi-specific topics under `magi/`)
- Enforcement layer under `${MAGI_PACK_DIR}/enforcement/` (rules, lifecycle, cleanup, launchd, shared, prohibited, guidelines)
- 4 MCP servers under `${MAGI_PACK_DIR}/mcp-servers/` (guidelines-retriever, project-memory, system-info, remote-shell)
- LSP marketplace at `${MAGI_PACK_DIR}/plugins/marketplaces/local-lsp/` shipping 8 language-server plugins
- 2 skills under `${MAGI_PACK_DIR}/skills/` (`verify-magi-installed`, `verify-frontend-ux`)
- `settings.json.template`, `.mcp.json.template`, behavioral contract at `${MAGI_PACK_DIR}/CLAUDE.md`
- Vendored upstream runtimes under `${MAGI_PACK_DIR}/claude/`, `${MAGI_PACK_DIR}/codex/`, `${MAGI_PACK_DIR}/project_analyzer/` (byte-exact, never modified after vendoring)

## 2. Primitives

The pack has five primitives plus six derived mechanisms. Removing any primitive breaks the pack contract. Every derived mechanism composes from the primitives.

**Five primitives:**

1. **Verbs** — every operator-visible operation is a `gc magi <verb>` invocation. Each verb has a Python orchestrator (`${MAGI_PACK_DIR}/scripts/magi_<verb>.py`), a POSIX-sh dispatcher (`${MAGI_PACK_DIR}/commands/<verb>.sh`), and a `commands/<verb>/command.toml` + `commands/<verb>/help.md` pair.
2. **bd beads** — every verb run participates in the bd lifecycle. The bead is the work record. Hooks fire on `bead.created`, `bead.closed`, `bead.failed`.
3. **Doctor checks** — `${MAGI_PACK_DIR}/doctor/<name>/doctor.toml` declares a check; `${MAGI_PACK_DIR}/doctor/check-<name>.sh` implements it. The orchestrator walks `doctor/*/doctor.toml` and aggregates rcs. Each check exits 0 ok, 1 fail, 2 warn.
4. **Formulas** — `${MAGI_PACK_DIR}/formulas/*.formula.toml` declares a bd molecule recipe with per-step `on_fail` semantics. `gc magi molecule pour <name>` and `gc magi formulas cook <name>` instantiate the formula.
5. **Hooks** — `${MAGI_PACK_DIR}/hooks/magi-bd-hooks.toml` declares bd hooks; `${MAGI_PACK_DIR}/scripts/hook_<name>.py` implements each hook. The recursion guard is `MAGI_HOOK_REENTRANT=1` env plus the `role:hook-trigger` label filter.

**Six derived mechanisms:**

6. **Install** — `magi_install.py` reads `TARGET_REGISTRY` in `magi_common.py` and dispatches per target. The `claude` target uses the stage-and-swap direct-deploy path from pack root; `codex`, `gemini`, `openai` exec their per-target deployer.
7. **Uninstall** — `magi_uninstall.py` reads state, closes open beads, and reverts state. The two-flag gate `--really-purge --yes` is required for filesystem purge.
8. **Analyze** — `magi_analyze.py` wraps `${MAGI_PACK_DIR}/project_analyzer/analyze_project.sh` and walks a project bottom-up, writing `_DIRECTORY_OVERVIEW.md` per directory.
9. **Improve** — `magi_improve.py` wraps `${MAGI_PACK_DIR}/project_analyzer/improve_project_analysis.sh` and runs the three-model pipeline (draft → verify → aggregate).
10. **Molecule** — `magi_molecule.py` reads a formula, creates a root bead plus per-step child beads, and dispatches each step in order.
11. **Bootstrap-project** — `magi_bootstrap_project.py` resolves `magi_utilities_source()` and invokes `setup_utilities.sh -y <project-path>` against an operator's project root.

## 3. Layering invariants

The pack distinguishes three layers; cross-layer references obey the rules below.

| Layer            | Files                                                                                                          | Invariant                                                                                                       |
|------------------|----------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| Pack-source      | Everything under `${MAGI_PACK_DIR}/` except vendored runtimes and `.utilities/`                                | Path references use `${MAGI_PACK_DIR}/...`. Zero external-runtime references.                                  |
| Vendored runtime | `${MAGI_PACK_DIR}/claude/`, `${MAGI_PACK_DIR}/codex/`, `${MAGI_PACK_DIR}/project_analyzer/`                    | Byte-exact upstream payload. Mutated only via `promote-harness.sh` re-vendoring. Exempt from 12th-check grep. |
| Deployed runtime | Whatever the install target uses (e.g. the deployed claude harness root)                                       | Pack-source does not name this path directly. The deployer substitutes `${MAGI_PACK_DIR}` to the deploy root.   |

Additional layering rules:

1. State lives in the city, not the pack. Runtime state writes to `${GC_CITY_PATH}/.gc/runtime/packs/magi/`. The pack source contains no runtime state.
2. `${MAGI_PACK_DIR}/.utilities/` is pack-internal but rsynced byte-exact by the deployer; substitutable extensions do not apply.
3. `${MAGI_PACK_DIR}/agents/`, `${MAGI_PACK_DIR}/claude-commands/`, `${MAGI_PACK_DIR}/mcp-servers/`, `${MAGI_PACK_DIR}/plugins/`, `${MAGI_PACK_DIR}/enforcement/`, `${MAGI_PACK_DIR}/skills/`, `${MAGI_PACK_DIR}/guidelines/` are substituted-and-rsynced.
4. The pack source uses `${MAGI_PACK_DIR}` as the canonical placeholder. The deployer's locked sed expression substitutes this placeholder once at install time.

## 4. Agent routing table

The 28 pack-internal subagents live at `${MAGI_PACK_DIR}/agents/<name>.md`. Each verb's Python orchestrator dispatches forge work to the agent class that owns the file type; the agent consults the markdown_library topic relevant to its language.

| Verb / dispatch context        | Forge agent                       | markdown_library topic consulted at runtime                                                                                |
|--------------------------------|-----------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| `*.py` file authoring          | `python-forge`                    | `${MAGI_PACK_DIR}/guidelines/markdown_library/python/OVERVIEW.md`                                                          |
| `*.sh` generation              | `bashforge-script-generator`      | `${MAGI_PACK_DIR}/guidelines/markdown_library/bash/OVERVIEW.md`                                                            |
| `*.sh` review                  | `bash-script-enforcer`            | `${MAGI_PACK_DIR}/guidelines/markdown_library/bash/OVERVIEW.md`                                                            |
| `*.rs` authoring               | `rust-forge`                      | `${MAGI_PACK_DIR}/guidelines/markdown_library/rust/OVERVIEW.md`                                                            |
| C# authoring                   | `csharp-forge`                    | `${MAGI_PACK_DIR}/guidelines/markdown_library/csharp/OVERVIEW.md`                                                          |
| Java authoring                 | `java-forge`                      | `${MAGI_PACK_DIR}/guidelines/markdown_library/java17/OVERVIEW.md`                                                          |
| Maven build authoring          | `maven-forge`                     | `${MAGI_PACK_DIR}/guidelines/markdown_library/maven/OVERVIEW.md`                                                           |
| Gradle build authoring         | `gradle-forge`                    | `${MAGI_PACK_DIR}/guidelines/markdown_library/gradle/OVERVIEW.md`                                                          |
| React / frontend authoring     | `react-forge`, `frontend-developer`, `react.md` | `${MAGI_PACK_DIR}/guidelines/markdown_library/frontend/OVERVIEW.md`, `typescript_react_node/`, `react_node16/` |
| Yew (Rust WASM) authoring      | `yew-forge`                       | `${MAGI_PACK_DIR}/guidelines/markdown_library/yew/OVERVIEW.md`                                                             |
| Ignition projects              | `ignition-master`                 | `${MAGI_PACK_DIR}/guidelines/markdown_library/ignition_v83/OVERVIEW.md` (or `ignition_v81/`)                               |
| Code review                    | `code-reviewer`                   | `${MAGI_PACK_DIR}/guidelines/markdown_library/prohibited_behavior/OVERVIEW.md`                                             |
| Architecture review            | `architecture-advisor`            | `${MAGI_PACK_DIR}/guidelines/markdown_library/automation_principles/OVERVIEW.md`                                           |
| Security review                | `security-auditor`                | `${MAGI_PACK_DIR}/guidelines/markdown_library/auth/OVERVIEW.md`                                                            |
| Database design                | `database-architect`              | `${MAGI_PACK_DIR}/guidelines/markdown_library/sql/OVERVIEW.md`                                                             |
| Performance tuning             | `performance-optimizer`           | `${MAGI_PACK_DIR}/guidelines/markdown_library/storage_and_messaging_principles/OVERVIEW.md`                                |
| API design                     | `api-designer`                    | `${MAGI_PACK_DIR}/guidelines/markdown_library/api/OVERVIEW.md`                                                             |
| Test authoring                 | `test-engineer`                   | `${MAGI_PACK_DIR}/guidelines/markdown_library/automation_principles/TESTING_VALIDATION.md`                                 |
| DevOps work                    | `devops-engineer`                 | `${MAGI_PACK_DIR}/guidelines/markdown_library/cicd/OVERVIEW.md`                                                            |
| Deployment gates               | `deployment-guardian`             | `${MAGI_PACK_DIR}/guidelines/markdown_library/automation_principles/DEPLOYMENT_PATTERNS.md`                                |
| Documentation authoring        | `documentation-writer`            | `${MAGI_PACK_DIR}/guidelines/markdown_library/real_writing_style/OVERVIEW.md`                                              |
| Tree-structure docs            | `tree-structure-documenter`       | `${MAGI_PACK_DIR}/guidelines/markdown_library/real_writing_style/OVERVIEW.md`                                              |
| Plan authoring                 | `plan-agent`                      | `${MAGI_PACK_DIR}/guidelines/markdown_library/automation_principles/OVERVIEW.md`                                           |
| Dev tracking                   | `dev-tracker`                     | `${MAGI_PACK_DIR}/guidelines/markdown_library/automation_principles/LOGGING_OBSERVABILITY.md`                              |
| Ignition launch                | `ignition-master`                 | `${MAGI_PACK_DIR}/guidelines/markdown_library/ignition_v83/OVERVIEW.md`                                                    |
| Neurotic quality sweep         | `neurotic-code-quality`           | `${MAGI_PACK_DIR}/guidelines/markdown_library/prohibited_behavior/OVERVIEW.md`                                             |
| `.utilities/` script authoring | `utilities-agent`                 | `${MAGI_PACK_DIR}/guidelines/markdown_library/utilities/OVERVIEW.md`                                                       |

Routing rule: when a verb authors or modifies a file, the orchestrator delegates to the agent class that owns the file's language. No verb writes outside its delegated agent's scope. The full agent index lives at `${MAGI_PACK_DIR}/agents/`; this table maps the dispatch contexts.

## 5. bd integration (in-line summary)

bd is the universal work-record substrate. Every verb participates in the lifecycle below; the `magi_common` helpers wrap every bd subprocess.

**Lifecycle:**

```
parse argv → reconcile_orphans() → bd_create() → bd_update(--claim) →
subprocess work → bd_close(outcome={0,1,2}) → bd hook fires →
post-deploy state refresh
```

`reconcile_orphans()` is the first action after argument parsing in every verb. It walks `${GC_CITY_PATH}/.gc/runtime/packs/magi/inflight/` for stale sentinels, closes each stale bead with `outcome:orphaned`, and clears the sentinel. Process-local memoization keeps the function called once per verb invocation.

**Label taxonomy:**

| Key       | Domain                                                                                                                                       |
|-----------|----------------------------------------------------------------------------------------------------------------------------------------------|
| `pack`    | `{magi}`                                                                                                                                     |
| `verb`    | `{install, uninstall, analyze, improve, status, doctor, molecule, bootstrap-project, remember, recall, ready, formulas}`                     |
| `target`  | `{claude, codex, gemini, openai, project}`                                                                                                   |
| `outcome` | `{0, 1, 2, orphaned, interrupted}`                                                                                                           |
| `role`    | `{root, child, hook-trigger, uninstall-closure}`                                                                                             |

**Timeout constants (declared in `magi_common.py`):**

| Constant                       | Value (seconds) | Applies to                                          |
|--------------------------------|-----------------|-----------------------------------------------------|
| `BD_DEFAULT_TIMEOUT_SECONDS`   | `10`            | `bd create`, `bd update`, `bd label`, `bd remember` |
| `BD_CLOSE_TIMEOUT_SECONDS`     | `20`            | `bd close` success path                             |
| `BD_PUSH_TIMEOUT_SECONDS`      | `60`            | `bd dolt push` (only under `--bd-push`)             |

**Hook recursion guard:** every hook script sets `MAGI_HOOK_REENTRANT=1` before invoking any magi subprocess. Every bd write helper in `magi_common` checks this flag and short-circuits. Hook write operations apply `role:hook-trigger` so the hook registration's `labels_not` filter excludes them from re-firing.

Graceful degradation: when `bd` is absent on PATH, every verb still succeeds. `bd_available_current()` short-circuits the write helpers; `state.json` records `bd_available=false`. The doctor's `beads` check warns but does not fail.

Full contract: `${MAGI_PACK_DIR}/guidelines/markdown_library/magi/beads.md`.

## 6. `.utilities/` pattern

`.utilities/` is per-user shared infrastructure. The pack ships it pack-internally at `${MAGI_PACK_DIR}/.utilities/`. `magi_common.magi_utilities_source()` resolves the source per the precedence below; the audit-trail log line records every resolution.

**Precedence:**

1. `${MAGI_PACK_DIR}/.utilities/` when `setup_utilities.sh` exists and is executable (pack-internal — primary).
2. `${MAGI_UTILITIES_SOURCE}` env override when set (fallback for installs that override the canonical source).
3. A legacy fallback path retained for installs from the pre-cleanup era; the full precedence chain (including the deprecated last-resort form) lives in `${MAGI_PACK_DIR}/guidelines/markdown_library/magi/utilities.md`.

**Doctor semantics** (implemented in `${MAGI_PACK_DIR}/doctor/check-utilities.sh`):

- rc=0 when pack-internal `.utilities/` exists and `setup_utilities.sh` is executable.
- rc=2 (warn) when pack-internal is missing and the env-var or legacy fallback resolves successfully (degraded source).
- rc=2 (warn) when none resolves; doctor prints a single-line note that `bootstrap-project` is unavailable.

**setup_utilities.sh-aware:** the pack invokes the script; it does not copy or modify it. Flag passing is `setup_utilities.sh -y <project-path>`. The post-deploy step of `gc magi install --target claude` runs the script against the deploy home; `gc magi bootstrap-project <project-path>` runs it against an operator's project root.

Full contract: `${MAGI_PACK_DIR}/guidelines/markdown_library/magi/utilities.md`.

## 7. Determinate-language gate

Pack-source documentation enforces determinate language. Every `.md` file, every `.toml` `description` field, every help.md, and every agent definition under `${MAGI_PACK_DIR}/` excludes the banned tokens below. The GSL file at `${MAGI_PACK_DIR}/guidelines/gsl/magi.gsl` is the single exception; that file uses the GSL shortcode dictionary by design.

**Banned tokens (case-insensitive whole-word match):**

- `should`
- `would`
- `could`
- `might`
- `may`
- `maybe`
- `perhaps`

**Banned content:**

- Emojis (Unicode emoji ranges). The GSL file is the single exempt surface.
- GSL shortcodes (`:white_check_mark:`, `:no_entry_sign:`, `:shield:`) in non-GSL files.
- Filler ("Great!", "Sure!", "Would you like me to...").
- Hedge phrases ("should be able to", "might help with", "some users find").

The gate is enforced by `${MAGI_PACK_DIR}/tests/test_determinate_language.py` (already shipped per CHANGELOG 0.1.0). The 12th shakedown check at `.scratch/magi-build/shakedown.sh` reads the same banned-token list when scanning pack-source.

## 8. Build commands

Every operator-visible operation maps to one `gc magi <verb>` invocation. The table below enumerates each verb with its one-line purpose; the README documents the per-verb flag surface and examples.

| Verb                  | Purpose                                                                                                       |
|-----------------------|---------------------------------------------------------------------------------------------------------------|
| `install`             | Deploys a target runtime (claude direct-deploy from pack root; codex/gemini/openai via per-target deployer).  |
| `uninstall`           | Reverts state and (with `--really-purge --yes`) purges the deployed home.                                     |
| `analyze`             | Runs `project_analyzer/analyze_project.sh` bottom-up against a project root.                                  |
| `improve`             | Runs the three-model improve pipeline against the analyze output.                                             |
| `status`              | Prints per-verb state from `state.json`; supports `--target` and `--json`.                                    |
| `doctor`              | Aggregates `doctor/<name>/doctor.toml` check rcs; worst child rc is the aggregate rc.                         |
| `molecule`            | Pours a bd molecule from a formula (`bd mol pour` / `bd mol wisp`).                                           |
| `bootstrap-project`   | Invokes `setup_utilities.sh -y <project-path>` against an operator's project root.                            |
| `remember`            | `bd remember --key magi:<key>` — magi-namespaced bd memory write.                                             |
| `recall`              | `bd recall magi:<key>` — magi-namespaced bd memory read.                                                      |
| `ready`               | `bd ready --label pack:magi` — lists actionable magi work.                                                    |
| `formulas`            | Lists/show/cook recipes under `${MAGI_PACK_DIR}/formulas/`.                                                   |

**Additional build entry points:**

- `bash ${MAGI_PACK_DIR}/.scratch/magi-build/shakedown.sh` — runs the 12-check suite. PASS gate is `12/12 PASS`. Log written to `${MAGI_PACK_DIR}/.scratch/magi-build/logs/shakedown-<utc>.log`.
- `bash ${MAGI_PACK_DIR}/.scratch/magi-build/shakedown.sh --check 12` — on-demand re-run of the 12th external-path-references check. Log written to `${MAGI_PACK_DIR}/.scratch/magi-build/logs/shakedown-check12-<utc>.log`.
- `gc magi install --target claude` — direct-deploy via stage-and-swap from pack root. The only deploy path for the claude target.

## 9. Path discipline

Pack-source files reference only:

1. Pack-relative paths (`commands/<verb>.sh`, `scripts/magi_common.py`).
2. The `${MAGI_PACK_DIR}` literal placeholder, substituted at install time by `magi_install.py`.
3. The `${GC_CITY_PATH}` literal placeholder when documenting deployed runtime state under the city.

Deployed runtime paths under the per-target homes (claude, codex, gemini, openai) appear ONLY as documented install destinations and ONLY in README, CHANGELOG, CONTRIBUTING, and the verbs' help.md files. Those four file classes carry the doc-side install-destination exemption documented in Phase I check 12b.

`AGENTS.md`, every agent definition under `${MAGI_PACK_DIR}/agents/`, every script under `${MAGI_PACK_DIR}/scripts/`, every command dispatcher under `${MAGI_PACK_DIR}/commands/`, every doctor check under `${MAGI_PACK_DIR}/doctor/`, every enforcement asset under `${MAGI_PACK_DIR}/enforcement/`, every MCP server source under `${MAGI_PACK_DIR}/mcp-servers/`, every plugin under `${MAGI_PACK_DIR}/plugins/`, every skill under `${MAGI_PACK_DIR}/skills/`, every markdown_library topic under `${MAGI_PACK_DIR}/guidelines/markdown_library/` (except `magi/deploy.md`, `magi/doctor.md`, `magi/beads.md` which describe deployed runtime state) carry NO install-destination exemption. The 12th shakedown check's pack-source pass (12a) enforces this mechanically.

The canonical placeholder string is the `PACK_DIR_PLACEHOLDER` constant in `${MAGI_PACK_DIR}/scripts/magi_common.py`. The full placeholder set lives in the cleanup plan's §0.1 canonical placeholder table; `CONTRIBUTING.md` §"Adding a placeholder to the substitution set" documents the procedure for extending it.
