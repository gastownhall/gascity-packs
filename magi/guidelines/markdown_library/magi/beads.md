---
label_keys: ["pack", "verb", "target", "outcome", "role"]
value_domains:
  pack: ["magi"]
  verb:
    - "install"
    - "uninstall"
    - "analyze"
    - "improve"
    - "status"
    - "doctor"
    - "molecule"
    - "bootstrap-project"
    - "remember"
    - "recall"
    - "ready"
    - "formulas"
  target: ["claude", "codex", "gemini", "openai", "project"]
  outcome: [0, 1, 2]
  role: ["root", "child", "hook-trigger", "uninstall-closure"]
timeouts:
  default: 10
  close: 20
  push: 60
hooks:
  - event: "bead.closed"
    label: "pack:magi:install"
    target: "scripts/hook_post_install.py"
  - event: "bead.created"
    label: "pack:magi:analyze"
    target: "scripts/hook_pre_analyze.py"
  - event: "bead.failed"
    label: "pack:magi"
    target: "scripts/hook_on_failure.py"
recursion_guard_env: "MAGI_HOOK_REENTRANT"
orphan_threshold_seconds: 3600
---

# Beads — Lifecycle and Label Rules

`magi_status.py` and the hook scripts load this file at startup. `magi_common.MAGI_LABEL_SCHEMA` mirrors the value domains above.

## Label taxonomy

Every magi bead carries five labels:

| Key | Domain |
|---|---|
| `pack` | `{magi}` |
| `verb` | one of the 12 verbs |
| `target` | `{claude, codex, gemini, openai, project}` |
| `outcome` | `{0, 1, 2}` |
| `role` | `{root, child, hook-trigger, uninstall-closure}` |

`bd_label()` validates against the schema at call time. Unknown keys or out-of-domain values raise `ValueError`. The raise is intentional: label typos are developer-side correctness defects and must surface in tests, not at runtime under a user.

## Bead lifecycle

`create → claim → close` per verb. Orchestrators wrap the subprocess in `try/finally` where the `finally` block calls `bd_close(outcome="interrupted")` when a `closed` boolean shows the success path did not run. This catches `BaseException` (KeyboardInterrupt, SystemExit, GeneratorExit), not just `Exception`. SIGKILL / `os._exit` / OOM fall through to `reconcile_orphans()` on next-verb invocation via the `inflight.json` sentinel.

`reconcile_orphans()` walks `runtime_dir() / "inflight"` at the start of every verb, closes each stale bead with `outcome:orphaned`, and clears the sentinel. It is process-locally memoized and bounded by `timeouts.default` per bd call.

## Timeouts

| Op | Seconds |
|---|---|
| create, update, label, dep, remember | 10 |
| close (success path) | 20 |
| `bd dolt push` (under `--bd-push`) | 60 |

On `subprocess.TimeoutExpired`, `try_bd()` logs `bd_timeout op=<name> seconds=<n>` and returns `None`. The verb proceeds without bd.

## Hook registrations

| Event | Label filter | Target |
|---|---|---|
| `bead.closed` | `pack:magi:install` + `outcome:0` + NOT `role:uninstall-closure` + NOT `role:hook-trigger` | `scripts/hook_post_install.py` |
| `bead.created` | `pack:magi:analyze` + NOT `role:hook-trigger` | `scripts/hook_pre_analyze.py` |
| `bead.failed` | `pack:magi` + NOT `role:hook-trigger` | `scripts/hook_on_failure.py` |

## Recursion guard

Hooks set `MAGI_HOOK_REENTRANT=1` in the subprocess env before invoking any magi verb. Every bd write helper (`bd_create`, `bd_update`, `bd_close`, `bd_remember`, `bd_label`, `bd_dep`) checks the env var at entry. When set, the helper logs `bd_skipped_reentrant op=<op>` and returns `None`. Reads (`bd_show`, `bd_list_pack`) do not check the flag.

Hook scripts default to reads only. State mutations target `state.json`, not the bd store. `hook_on_failure.py` appends to `failures: []` in state.json and never writes bd.

## Graceful degradation

`bd_available_current()` checks PATH for the `bd` binary. When absent, every write helper short-circuits to `None` and the verb continues. `state.json` records `bd_available=false`. The doctor's `beads` check warns; it does not fail.

## Molecule semantics

Parent bead per molecule; children via `bd_dep`. On first child failure with `on_fail="continue"`, the parent stays open and carries `outcome:partial`. With `on_fail="stop"`, the chain halts. Remaining un-ready children are never auto-cancelled; the operator decides via `gc magi status`.
