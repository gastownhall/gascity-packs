# Contributing to magi

Procedure contracts for the maintenance operations magi accepts. Every command in this document is copy-paste runnable on a clean magi checkout. Eleven sections in order.

## 1. Re-vendoring an upstream runtime

The `claude/`, `codex/`, and `project_analyzer/` directories are rsync-mirrored from upstream distributions. The vendored content is never edited in place; changes flow upstream first, then re-vendor.

### Exact rsync invocation

```bash
rsync -av --delete \
  --exclude='.venv/' \
  --exclude='.work/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='logs/' \
  --exclude='.DS_Store' \
  --exclude='.git/' \
  --exclude='_DIRECTORY_OVERVIEW.md' \
  --exclude='_IMPROVEMENTS.md' \
  --exclude='_PROJECT_IMPROVEMENT_BACKLOG.md' \
  --exclude='_*OVERVIEW.md' \
  "${UPSTREAM_RUNTIME_DIR}/<runtime>/" \
  "${MAGI_PACK_DIR}/<runtime>/"
```

`<runtime>` is one of `claude_dist`, `codex_dist`, `project_analyzer`. Map to the magi directory name verbatim except `claude_dist → claude` and `codex_dist → codex`.

### Pre-flight

```bash
rsync -av --dry-run --delete \
  --exclude='.venv/' --exclude='.work/' --exclude='__pycache__/' \
  --exclude='*.pyc' --exclude='logs/' --exclude='.DS_Store' \
  --exclude='.git/' --exclude='_*OVERVIEW.md' \
  --exclude='_IMPROVEMENTS.md' --exclude='_PROJECT_IMPROVEMENT_BACKLOG.md' \
  "${UPSTREAM_RUNTIME_DIR}/<runtime>/" \
  "${MAGI_PACK_DIR}/<runtime>/"
```

Zero excluded files remain in the output. When any appear, extend the exclude list and re-run the dry-run.

### Post-flight

```bash
gc magi doctor
gc magi install --target <name> --dry-run --non-interactive
```

Bump `pack.toml` `version` (patch). Add a `CHANGELOG.md` entry under `### Changed` describing the upstream commit range absorbed.

## 2. Pack-root canonical layout

The magi pack ships its full deployed payload at pack root. The direct-deploy installer reads from pack root (`CLAUDE.md`, `agents/`, `claude-commands/`, `commands/`, `mcp-servers/`, `plugins/`, `enforcement/`, `skills/`, `guidelines/`, `scripts/`, `settings.json.template`, `.mcp.json.template`) for every supported target.

- Pack-root content is the single source of truth. There is no duplicate vendored copy under `claude/harness/` (removed); the pack stays small and the deployer stays simple.
- The `codex/harness/`, `gemini/harness/`, and `openai/templates/` directories contain only per-runtime artifacts that do not exist at pack root (e.g., codex hooks/rules, gemini policies, openai config templates).
- The `gc magi install --target claude` path is direct-deploy stage-and-swap — there is no legacy fallback flag.

## 3. Re-promoting harness content from upstream `claude_dist`

When upstream `claude_dist` releases a new version, run the 7-step procedure below.

### Step 1 — Confirm upstream commit range

```bash
cd "${UPSTREAM_CLAUDE_DIST_DIR}"
git log --oneline <prior-magi-promotion-sha>..HEAD
```

Record the commit range; the CHANGELOG `### Changed` entry names it explicitly.

### Step 2 — Sentinel-backup user-authored `.utilities/`

```bash
UTC="$(date -u +%FT%TZ)"
SENTINEL_DIR="${HOME}/Code/gas/.scratch/magi-build/_utilities_sentinel_${UTC}"
mkdir -p "${SENTINEL_DIR}"
rsync -av \
  "${MAGI_PACK_DIR}/.utilities/" \
  "${SENTINEL_DIR}/.utilities/"
```

The sentinel lives next to the pack root, never inside the pack tree. Phase A of the cleanup-plan invariants apply.

### Step 3 — Run cleanup phases A through D

```bash
bash "${MAGI_PACK_DIR}/.scratch/magi-build/phase-a-utilities-sentinel.sh"
bash "${MAGI_PACK_DIR}/.scratch/magi-build/phase-b-delete-duplicate-guidelines.sh"
bash "${MAGI_PACK_DIR}/.scratch/magi-build/phase-c-move-markdown-library.sh"
bash "${MAGI_PACK_DIR}/.scratch/magi-build/phase-d-rewrite-external-paths.sh"
```

Each phase is recoverable; Phase A creates the sentinel, Phase B deletes duplicate guideline trees, Phase C moves `markdown_library` up, Phase D rewrites external path references per `.scratch/magi-build/rewrite-rules.json`.

### Step 4 — Re-resolve any new placeholders

When the upstream snapshot introduces a new substitutable string, add it to the canonical placeholder table (Section 8 of this file) and re-run Phase D.

### Step 5 — Re-run rewrite rules

```bash
bash "${MAGI_PACK_DIR}/.scratch/magi-build/phase-d-rewrite-external-paths.sh" \
  --rules "${MAGI_PACK_DIR}/.scratch/magi-build/rewrite-rules.json"
```

Phase D forge reads `rewrite-rules.json` and iterates every rule. The 12th-check positive control consumes the same `placeholder` field.

### Step 6 — Bump CHANGELOG with the upstream version

Add a `### Changed` entry under the next minor or patch version section naming the upstream commit range from Step 1. Re-promote is patch-level when the upstream release is patch-level; minor when the release adds substantive surface.

### Step 7 — Re-run 12/12 shakedown

```bash
bash "${MAGI_PACK_DIR}/.scratch/magi-build/shakedown.sh"
```

Expected output: `12/12 PASS`. Failure modes are documented in Section 10 of this file.

## 4. Adding a verb

A new verb is a four-file change set:

| Path | Contents |
|---|---|
| `scripts/magi_<verb>.py` | Python orchestrator; std-lib only; imports `magi_common` exclusively |
| `commands/<verb>.sh` | POSIX `sh`; guards `${GC_PACK_DIR}` and `${GC_CITY_PATH}`; execs the python orchestrator |
| `commands/<verb>/command.toml` | `description = '<one-line>'` + `run = '../<verb>.sh'` |
| `commands/<verb>/help.md` | Usage block + flag table + at least 1 example + bd note |

Optional fifth and sixth files when the verb adds a precondition:

| Path | Contents |
|---|---|
| `doctor/<verb>/doctor.toml` | `name`, `description`, `check = "check-<verb>.sh"` |
| `doctor/check-<verb>.sh` | POSIX `sh`; exit 0 ok, 1 fail, 2 warn |

### Forbidden edits when adding a verb

- `scripts/magi_doctor.py`, `scripts/magi_common.py`, any sibling verb's files
- `guidelines/gsl/magi.gsl` rules content (regen only when guideline content actually changes)

### Verb implementation contract

- `argparse.ArgumentParser(allow_abbrev=False)`
- `magi_common.reconcile_orphans()` as the first action after parse
- `bd_create()` after reconciliation; `try/finally` wraps the subprocess
- `finally` block calls `bd_close(outcome="interrupted")` when a `closed` boolean shows the success path did not run; this catches `BaseException`
- `subprocess.run(..., check=False)`; rc propagates verbatim
- log to `magi_common.log_path(verb, target)`; mode `0600`
- state writes through `magi_common.write_state()` which redacts via `SECRET_KEY_PATTERNS`

## 5. Adding a target

`TARGET_REGISTRY` in `scripts/magi_common.py` is the single source of target metadata. Adding a target is one row plus a sibling directory:

```python
TARGET_REGISTRY["mytarget"] = {
    "dir": "mytarget",
    "script": "deploy_mytarget.sh",
    "env": ["MYTARGET_HOME", "INSTALL_FOO", "BAR_TOKEN"],
    "default_home": "<target-dir>",
}
```

Plus:

```
${MAGI_PACK_DIR}/mytarget/
  deploy_mytarget.sh
  harness/   (or templates/, per the target's idiom)
```

Update:

- `guidelines/markdown_library/magi/deploy.md` table of targets
- `commands/install/help.md` underlying env passthrough table
- `commands/uninstall/help.md` when uninstall semantics differ
- `CHANGELOG.md` under `### Added`

No edits to `magi_install.py` or `magi_uninstall.py` are required — both read from `TARGET_REGISTRY`.

When the new target uses the direct-deploy path (rather than execing a vendored deployer), add the target to `_UTILITIES_AWARE_TARGETS` when it receives `.utilities/` at deploy time.

## 6. Adding a doctor check

```bash
mkdir -p "${MAGI_PACK_DIR}/doctor/<name>"
```

Write `doctor/<name>/doctor.toml`:

```toml
name = "<name>"
description = "One-line description of what this check verifies"
check = "check-<name>.sh"
severity = "fail"   # or "warn"
```

Write `doctor/check-<name>.sh` (POSIX `sh`; `set -eu`; exit 0 ok, 1 fail, 2 warn). `magi_doctor.py` discovers it automatically via the `doctor/*/doctor.toml` glob walk; no edit to the orchestrator.

Update `guidelines/markdown_library/magi/doctor.md` `severity_promotion` table.

## 7. Regenerating the GSL guideline

```
/gsl <topic body>
```

Destination: `guidelines/gsl/magi.gsl`. Overwrite policy: replace.

Validate via the GSL spec: single physical line, exactly one trailing newline, `:white_check_mark:` exactly once, `:no_entry_sign:` >= 2, 500 <= chars <= 15000, starts with `MAGI/pack/schema2|`. No `\n`, `\r`, or `<br>` mid-line.

## 8. Adding a placeholder to the substitution set

The canonical placeholder table covers 15 placeholders consumed by `magi_install.py` at install time. Adding a new placeholder is a 5-step procedure.

### Step 1 — Append a row to `INSTALL_PLACEHOLDERS`

Edit `${MAGI_PACK_DIR}/scripts/magi_common.py`. Append the new placeholder to the `INSTALL_PLACEHOLDERS` constant (the canonical Python representation of the placeholder table):

```python
INSTALL_PLACEHOLDERS["__NEW_PLACEHOLDER__"] = {
    "substituted_to": "<one-line description>",
    "source": "env:NEW_PLACEHOLDER_ENV_VAR",
    "default": None,                    # or a literal string
    "required": True,                   # or False / "conditional"
    "redaction": False,                 # True when the value is a secret
}
```

### Step 2 — Add the env var to `TARGET_REGISTRY[<target>]["env"]`

Edit `${MAGI_PACK_DIR}/scripts/magi_common.py`. For each target that consumes the new placeholder, append the env-var name to that target's `env` list:

```python
TARGET_REGISTRY["claude"]["env"].append("NEW_PLACEHOLDER_ENV_VAR")
```

The deployer iterates this list to build the substitution environment at install time.

### Step 3 — Update placeholder documentation in this CONTRIBUTING file

Add the new row to the canonical placeholder table referenced from README §18. The columns are: Placeholder, Substituted to, Source, Default when missing, Required, Redaction.

### Step 4 — Update `settings.json.template` (when applicable)

Edit `${MAGI_PACK_DIR}/settings.json.template` to reference the new placeholder where the deployed `settings.json` value is needed. Numeric placeholders are quoted strings in the template so the template parses as valid JSON pre-substitution; the deployer strips the surrounding quotes after substitution where the deployed value requires a numeric type.

When the placeholder feeds `.mcp.json` instead, edit `${MAGI_PACK_DIR}/.mcp.json.template`.

### Step 5 — Re-run shakedown

```bash
bash "${MAGI_PACK_DIR}/.scratch/magi-build/shakedown.sh"
```

Expected output: `12/12 PASS`. When the new placeholder carries `Redaction=yes`, also re-run `pytest tests/test_placeholder_redaction.py`.

## 9. Adding a markdown_library topic

A new topic directory under `${MAGI_PACK_DIR}/guidelines/markdown_library/<topic>/` extends the guideline corpus. Adding a topic is a 5-step procedure.

### Step 1 — Create the topic directory and OVERVIEW.md

```bash
mkdir -p "${MAGI_PACK_DIR}/guidelines/markdown_library/<topic>"
```

Write `${MAGI_PACK_DIR}/guidelines/markdown_library/<topic>/OVERVIEW.md` with the topic's entry-point content. The file is the start point when scanning the topic.

### Step 2 — Declare YAML frontmatter constants

The OVERVIEW.md frontmatter declares machine-readable constants the orchestrators consume via `magi_common.load_policy("<topic>")`:

```yaml
---
default_source: "<canonical-source>"
env_var: "<TOPIC_OVERRIDE_ENV_VAR>"     # when applicable
allow_dynamic_extension: false           # or true
---
```

The exact key set is topic-specific. Existing topics (e.g. `utilities/`) document their key set in their OVERVIEW.md frontmatter.

### Step 3 — Document the loader script

The script that consumes the topic calls `magi_common.load_policy("<topic>")`. Document in the loader's docstring which keys it reads and which behaviors each key controls.

When the topic has multiple consumer scripts, list each consumer in the topic's `OVERVIEW.md` "Consumers" section.

### Step 4 — Update README §19

Edit `${MAGI_PACK_DIR}/README.md` §19 "Guidelines (49 + 8 topics)" to add the new topic to the cross-language topic list (or the magi-specific list when the topic ships under `magi/`).

### Step 5 — Re-run shakedown

```bash
bash "${MAGI_PACK_DIR}/.scratch/magi-build/shakedown.sh"
```

Expected output: `12/12 PASS`. Also bump `pack.toml` `version` by a minor increment per CITY_GUIDELINES §21.1 (adding a markdown_library topic is additive surface).

## 10. Re-running the 12th shakedown check on demand

The 12th shakedown check (split into 12a pack-source and 12b doc-side) enforces the external-path discipline invariant. Re-run on demand with:

```bash
bash "${MAGI_PACK_DIR}/.scratch/magi-build/shakedown.sh" --check 12
```

### Expected output

On pass: rc=0; log shows `Check 12a PASS (pack-source: 0 violations)` and `Check 12b PASS (doc-side: 0 violations)`. The shakedown report appends `12/12 PASS`.

### What to do on failure

1. Read the log at `${MAGI_PACK_DIR}/.scratch/magi-build/logs/shakedown-check12-<utc>.log`.
2. Identify the failing category (12a pack-source or 12b doc-side).
3. For 12a violations: a pack-source file regressed an external path reference. Locate the file from the log, revert the offending change, OR re-run Phase D rewrites against it via `phase-d-rewrite-external-paths.sh`.
4. For 12b violations: a doc file references `~/.claude/...` without an install-destination context word (`deploy`, `deployed`, `install destination`, `install target`, `runtime root`, `after install`) in the same paragraph. Add the context word, OR rewrite the reference to `${MAGI_PACK_DIR}/...`, OR (when the context is genuinely a deployed runtime state path) verify the path matches a `RUNTIME_STATE_PATHS` allowlist entry.
5. Re-run `bash "${MAGI_PACK_DIR}/.scratch/magi-build/shakedown.sh" --check 12` until it passes.

### Allowed install-destination context

The 12b allowlist requires one of `deploy`, `deployed`, `install destination`, `install target`, `runtime root`, `after install` in the same paragraph as the `~/.claude/...` reference. AGENTS.md is exempt from this allowlist (AGENTS.md is born self-contained; it has NO install-destination exemption per Section 11).

## 11. External-reference invariant

Every pack-source file resolves paths against `${MAGI_PACK_DIR}` (the Option A substitution model). The canonical placeholder string is the `PACK_DIR_PLACEHOLDER` constant in `${MAGI_PACK_DIR}/scripts/magi_common.py`. The full placeholder set lives in Section 8 of this file plus the canonical placeholder table referenced from README §18. The 12th shakedown check enforces this invariant.

Doc-side reference rule: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, every `commands/<verb>/help.md`, and every `markdown_library/<topic>/*.md` distinguish source references (pack-internal — uses `${MAGI_PACK_DIR}/...`) from install-destination references (deployed runtime — uses `~/.claude/...`). The install-destination form is allowed ONLY when the same paragraph contains one of: `deploy`, `deployed`, `install destination`, `install target`, `runtime root`, `after install`.

AGENTS.md is the strict-mode exception: every reference inside AGENTS.md resolves against pack-relative paths. No `~/.claude/...`. No `/Users/<u>/...` absolute paths. No `${HOME}/.claude/...`. No sibling-runtime forms `${HOME}/.codex/`, `${HOME}/.gemini/`, `${HOME}/.openai/`. AGENTS.md has NO install-destination context exemption.
