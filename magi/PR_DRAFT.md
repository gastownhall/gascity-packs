## Summary

Adds `magi` as a top-level pack of `gascity-packs`, alongside `discord`, `slack-pack`, `pr-review`, et al. The pack ships at pack root the full hardened Claude Code harness payload (the MAGI runtime) — behavioral contract, twenty-eight subagents, fourteen slash commands, four MCP servers, an eight-language-server LSP marketplace, the enforcement layer (rules + lifecycle + cleanup + launchd + shared), two skills, fifty-two `markdown_library` topic dirs, and the three bd hook registrations — behind a single twelve-verb `gc magi <verb>` surface. Four install targets: `claude`, `codex`, `gemini`, `openai`/LM Studio.

This commit also carries three logical fix sets that landed in the same effort:

1. **`bd_close` `--label` regression** — `scripts/magi_common.py` `bd_close()` no longer passes `--label` to `bd close` (the upstream `bd` CLI never accepted `--label` on the close subcommand). Outcome labels are applied via `bd update --add-label key:value` BEFORE the close call, then a label-less `bd close` runs. This unblocks every doctor run that observed an orphaned bead.
2. **`try_bd` WARNING downgrade for known bd-degraded states** — new `_is_bd_degraded_stderr()` helper classifies three operational-degraded stderr markers (`Dolt server unreachable`, `failed to open database`, `no beads database found`) and routes them to INFO under op label `bd_degraded`. All other non-zero `bd` exits keep WARNING with full stderr.
3. **Shakedown verification phase** — `scripts/magi_doctor.py` grows `_shakedown()` plus four real-path probes (`state_roundtrip`, `inflight_scan`, `bd_list_live`, `bd_show`). Six explicit triggers (never-run, script-modified, tunables-changed, errors-in-run, install-trigger-file, interval-elapsed) gate execution. Concurrent-doctor safety via `fcntl.flock(LOCK_EX|LOCK_NB)`. Schema lives at `state.doctor.shakedown` with seven fields including the `tunable_fingerprint` over `_DOCTOR_TUNABLE_ENV_KEYS`.

Plus a comprehensive pre-publication scrub described under "Pre-publication scrub" below.

## What the pack provides

```
magi/
├── pack.toml              [pack] schema=2 version=0.2.0
├── CLAUDE.md              behavioral contract (deploys with the harness)
├── AGENTS.md              pack-internal authoring contract
├── README.md              full pack documentation (16 sections, 655 lines)
├── CHANGELOG.md           Keep-a-Changelog 1.1.0 format
├── CONTRIBUTING.md        maintenance procedures
├── LICENSE.md             MIT, magi pack maintainers
├── settings.json.template canonical deployer template for ~/.claude/settings.json
├── .mcp.json.template     canonical deployer template for ~/.claude/.mcp.json
├── scripts/               12 verb entry points + 3 bd hooks + magi_common.py foundation
├── commands/              gc wrappers (one .sh + one help dir per verb)
├── agents/                28 subagent definitions
├── claude-commands/       14 slash commands
├── mcp-servers/           4 MCP servers (guidelines-retriever, project-memory, system-info, remote-shell) + architecture diagram
├── plugins/marketplaces/local-lsp/   8-language LSP marketplace
├── enforcement/           rules + lifecycle + cleanup + launchd + shared + prohibited + guidelines
├── guidelines/markdown_library/      52 topic dirs (51 cross-language + magi/)
├── guidelines/gsl/        the GSL source of truth
├── skills/                verify-magi-installed, verify-frontend-ux
├── project_analyzer/      analyzer tool
├── template-fragments/    pack-source templates merged into deployed configs
├── doctor/                per-check directories (7 checks + 2 synthetic)
├── claude/                per-runtime metadata (README.md only — payload comes from pack root)
├── codex/                 per-runtime payload (deploy_harness.sh + harness/)
├── gemini/                per-runtime payload (deploy_gemini.sh + harness/)
├── openai/                per-runtime payload (deploy_openai.sh + templates/)
└── formulas/, hooks/      formulas + bd hook registrations
```

Twelve verbs after install:

```
gc magi install   --target {claude|codex|gemini|openai|all}
gc magi uninstall --target {claude|codex|gemini|openai|all}
gc magi analyze   --project <path>
gc magi improve   --project <path>
gc magi status
gc magi doctor
gc magi molecule  <name>
gc magi bootstrap-project --project <path>
gc magi remember  --key <k>  <value>
gc magi recall    --key <k>
gc magi ready
gc magi formulas
```

## How to try it out

Two paths.

### Path A — build + smoke-test the pack standalone

```bash
git clone -b MAGI-improvements https://github.com/<your-fork>/gascity-packs.git
cd gascity-packs/magi

# Static checks (zero-output is pass):
python3 -m mypy scripts/magi_common.py scripts/magi_doctor.py scripts/magi_install.py --strict --ignore-missing-imports

# Functional check against a city:
GC_CITY_PATH=/abs/path/to/any/city python3 scripts/magi_doctor.py
# Expected: INFO lines only, "magi doctor summary rc=0", shakedown + orphaned-beads rc=0.
```

### Path B — wire into a Gas City

```toml
# In <your-city>/city.toml — pin the pack:
[imports.magi]
source = "/abs/path/to/your/clone/of/gascity-packs/magi"
```

Then in your city:

```bash
gc magi install --target claude   # writes runtime_dir()/shakedown_trigger on success
gc magi doctor                    # next doctor consumes the trigger and runs a shakedown
# Expected: zero WARNINGs, rc=0, shakedown rc=0, orphaned-beads rc=0
```

## Account portability

The pack is portable across user accounts. No literal usernames embedded anywhere in the tree. Verified by:

```
git grep -nE "[Mm]arshall" | grep -vE "(marshalling|unmarshalling|Marshalling|Unmarshalling|hand-marshalled)"
```

returning empty. The maintainer-name attribution was migrated to either `magi pack maintainers` (LICENSE, README, CHANGELOG, CONTRIBUTING, per-runtime READMEs) or to install-time placeholders (`__USER_NAME__` for marketplace owner; `${LSP_USER}` for postgres role and connection strings; `<your-user>` for documentation examples).

## Pre-publication scrub

This commit also folds in:

- **Duplicate-tree removal.** The pack's prior `claude/harness/` directory (15M, full byte-mirror of pack-root canonical content) was deleted. The duplicate `enforcement/guidelines/guideline_documents/` subtree under `codex/harness/` (5.3M) was deleted. The remaining codex/harness/ content (`config/`, `hooks.json`, `rules/`, codex-specific `enforcement/`) is the codex deployer's actual payload and stays.
- **Legacy claude deployer removal.** The `claude/deploy_harness.sh` script and the `--legacy-claude-deployer` CLI flag were removed. The direct-deploy stage-and-swap path in `scripts/magi_install.py` is the only supported claude install flow.
- **Account-portability scrub.** Every literal maintainer username generalized to a placeholder:
  - `enforcement/cleanup/merge-dotted-projects.sh` — glob and sed substitution generalized to `/*-.*` and `s|-\.|--|g`.
  - `mcp-servers/project-memory/index.js` — `GLOBAL_MEMORY_DIR` derives from a runtime `projectKeyFromPath($HOME/.claude)` helper.
  - `plugins/marketplaces/local-lsp/.claude-plugin/marketplace.json` — owner is `__USER_NAME__` (deployer placeholder).
  - LaunchAgent plist source files renamed from `com.<username>.claude-cleanup-*.plist` to `com.__USER_NAME__.claude-cleanup-*.plist` (5 files); deployer FROM-pattern in `magi_install.py` updated.
  - `claude-commands/enhance-guidelines.md` + `claude-commands/consult.md` — hard-coded `192.168.85.26:1234` LM Studio host replaced with `${LM_STUDIO_HOST}:${LM_STUDIO_PORT}` and `${LM_STUDIO_URL%/v1/responses}/v1/...`.
  - `claude/README.md` example credential placeholder hardened to `<your-password>`.
  - mcp-servers documentation reworded to describe the project-key collapse rule rather than embedding a literal path.
  - `magi/.env` working-tree file deleted (held only empty-valued placeholders; was gitignored regardless).
- **gascity-packs `.gitignore`.** Adds `magi/.utilities/` so the 2GB local working tree (node_modules, vendored frontend, Claude worktrees) never enters the repo. Operators populate `.utilities/` via the `MAGI_UTILITIES_SOURCE` env var or the pack-internal fallback chain documented in `magi/guidelines/markdown_library/magi/utilities.md`.

Validation: `mypy --strict` clean on the three modified Python files; `gc magi doctor` end-to-end returns rc=0 with zero WARNINGs and zero ERRORs against a real city; secret scanner reports zero residual findings.

## Test plan

- [x] `python3 -m mypy scripts/magi_common.py scripts/magi_doctor.py scripts/magi_install.py --strict --ignore-missing-imports` → `Success: no issues found in 3 source files`
- [x] `python3 scripts/magi_doctor.py` against a live city → rc=0, zero WARNINGs, zero ERRORs, shakedown rc=0, orphaned-beads rc=0
- [x] Shakedown fires under each of the six triggers (never-run, script-modified, tunables-changed, errors-in-run, install-trigger-file, interval-elapsed) and skips cleanly when none fire
- [x] Concurrent doctor invocations: second instance logs `shakedown: skipped reason=concurrent-run` and exits cleanly
- [x] `bd_close` with composite labels (e.g. `outcome:orphaned`, `role:hook-trigger`) succeeds end-to-end against a live bd database — the bead is closed and carries every applied label
- [x] Full scrub scan: no real secrets, no hard-coded private IPs, no personal-name leakage, no oversized files, no junk artifacts
- [x] Pack directory tree contains zero `__pycache__/`, `.utilities/`, `.git/`, `.env`, `_logs/`, `.scratch/`, `node_modules/`, `.DS_Store` entries

## Companion upstream PR

The bd flock root-cause fix that pairs with this PR lives in the gascity Go core, branch `fix/events-flock-bounded-wait`. That patch bounds the `events.FileRecorder.Record` flock acquire loop to 250 ms total, eliminating the kernel-flock-on-dead-process pileup that triggered the original WARNING spam. Both PRs are independent and may merge in either order; together they deliver the clean operator experience documented above.
