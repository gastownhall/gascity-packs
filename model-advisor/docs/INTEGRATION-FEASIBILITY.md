# Model-Advisor — gc Integration Feasibility Verdict

**Bead:** bh-2hm (MAD pack effort)
**Scope:** READ-ONLY investigation of Gas City's (`gc`) integration surface for a model-tier advisor.
**Date:** 2026-06-03
**gc binary:** `/opt/homebrew/bin/gc`  •  **city root:** `/Users/jayse/Code`

This document answers three questions — (A) auto-apply, (B) telemetry, (C) quality
signal — then states the recommended **v1 MVP** (learn + recommend) and what **v2
auto-apply** requires from gc-core.

---

## TL;DR Verdicts

| | Question | Verdict |
|---|----------|---------|
| **A** | Can a model/tier be selected per agent or per dispatch? | **Per-AGENT: YES, today** (config field `model` → `GC_AGENT_MODEL` env). **Per-DISPATCH/per-task: NO** — needs a gc-core change (no `--model` on `gc sling`, no `gc.model` consumption at spawn). |
| **B** | What invocation/usage telemetry does gc emit for learning? | **Partial.** gc emits structured **lifecycle + bead** events to `.gc/events.jsonl`, but **no per-invocation record with model + token counts** is produced by gc-core in this city (the `worker.operation` events that `gc analyze reliability` expects are absent — the report returns 0). Token/model telemetry today lives only in the **gt/blackrim framework** (`.beads/telemetry/invocations.jsonl`), not gc. A small capture hook is needed for clean invocation records. |
| **C** | How to detect bead closed-OK vs reopened/escalated? | **YES, fully supported.** `gc bd show --json` + `bd history` + the `bead.closed` / Reopened events expose `status`, `closed_at`, `close_reason`, `metadata` (incl. `agent`, `session_id`), and `gc.outcome` / `gc.failure_class`. `bd reopen` emits a dedicated **Reopened** event. Task→agent→shape mapping is via bead `metadata.agent` + `metadata.session_id` + `gc.run_target` / `gc.formula_name`. |

---

## (A) AUTO-APPLY — model/tier selection per agent or per dispatch

### How gc spawns a session and sets its model

1. **Provider is per-agent.** `city.toml` has `provider = "claude"` but `gc config show`
   prints a deprecation warning making the mechanism explicit:

   > `workspace.provider is deprecated: Set provider per agent in agents/<name>/agent.toml.`

   Provider is resolved per `[[agent]]` block (e.g. the pooled `claude` worker agents and
   `gastown/witness` carry `provider = "claude"`).

2. **`model` is a first-class config field.** The gc binary validates it — string
   `agent_defaults.model redefined by %q` appears in the binary, alongside
   `agent_defaults.provider`, `agent_defaults.wake_mode`, `agent_defaults.default_sling_formula`.
   This means a `model = "..."` key is accepted at **`[agent_defaults]`** and per-**`[[agent]]`**
   scope and is part of the agent config schema (unknown keys error with `unknown field %q`).
   *No pack in this city currently sets it* (grep of all `packs/**/agent.toml` for
   `model|provider|tier` found zero `model=` assignments), so it is supported-but-unused.

3. **Model reaches the provider via an env var.** The binary contains **`GC_AGENT_MODEL=`**,
   positioned next to molecule/convoy dispatch strings (`convoy.molecule`, `gc.on_exhausted`).
   gc also sets `GC_PROVIDER`, `GC_TEMPLATE`, `GC_RIG_ROOT`, `GC_PROVIDER_SESSION_ID` at spawn.
   So the launcher: reads the agent's `model` field → exports `GC_AGENT_MODEL` → the provider
   adapter passes it to the underlying CLI (`claude-opus-4-7` / `claude-opus-4-8` model IDs are
   embedded in the binary; codex/opencode adapters build `--model … --effort …` argv, visible as
   `--model o4-mini gpt-5.5 … --effort opus-4-7`).

4. **Projected agent settings carry hooks, not a model.** The materialized per-agent settings
   are at `/.gc/agents/<agent>/.gc/settings.json` (NOT `.claude/settings.json` — that dir holds
   only skill symlinks). They contain `hooks` (SessionStart→`gc prime`, UserPromptSubmit→
   `gc nudge drain` / `gc mail check`, PreCompact→`gc handoff`) and flags like
   `skipDangerousModePermissionPrompt` — **no `model` key**. The claude provider has **no
   per-provider overlay** at `core/overlay/per-provider/` (only codex/copilot/cursor/gemini/
   kiro/omp/opencode/pi do). Model is therefore set via the agent **config field → env var**
   path, not via projected provider settings.

### Knobs a pack could use to set the model

| Knob | Granularity | Works today from a pack? |
|------|-------------|--------------------------|
| `model = "<id>"` in `[agent_defaults]` or `[[agent]]` (city/pack config) | **Per agent (template)** | **YES** — gc-core reads & validates it; injected as `GC_AGENT_MODEL`. A pack can ship/patch agent config. |
| `pre_start` hook on an agent (e.g. `gastown/polecat` uses one for worktree setup) | Per agent, at spawn | **Partially** — a `pre_start` script runs before the session; it could export env, but `GC_AGENT_MODEL` is set by gc's launcher *after* config resolution, so a hook would have to race/override the provider CLI invocation — brittle, not a clean seam. |
| `gc sling --var model=…` / formula vars | Intended per-dispatch | **NO for execution.** `mol-review-quorum` threads `lane_one_model` into **bead metadata** (`gc.model`, `gc.run_target`, `gc.reviewer_model`) and into the **prompt text**, but that metadata is *advisory* — it tells the agent which model to claim, it does **not** reconfigure the provider. There is no evidence gc reads `gc.model` off a bead to set `GC_AGENT_MODEL` at spawn. |
| `gc sling --model …` CLI flag | Per dispatch | **NO** — `gc sling` has no `--model`/`--effort`/`--provider` flag. Neither does `gc session new` / `gc session attach` / `gc session reset`. |

### Verdict (A)

- **Per-agent model selection is feasible from a pack TODAY**, with zero gc-core changes:
  set `model = "<provider-model-id>"` under `[agent_defaults]` or a specific `[[agent]]` block
  (or patch it via a pack overlay). gc resolves it and exports `GC_AGENT_MODEL` into the session.
  This is coarse: it pins a model for *all* dispatches that agent handles, changeable only by a
  config edit + `gc reload`/restart.

- **Per-task / per-dispatch model selection is NOT feasible today** — it requires gc-core support.
  The missing seam is: *at dispatch, read a model from the bead/wisp (`gc.model`) or a
  `gc sling --model` flag and have the session launcher honor it as `GC_AGENT_MODEL`.* The plumbing
  half-exists (`mol-review-quorum` already writes `gc.model`/`gc.run_target`/`gc.provider` onto
  step beads; `GC_AGENT_MODEL` already exists as the env lever) — what's absent is the launcher
  binding bead-`gc.model` → `GC_AGENT_MODEL`, and/or a `--model` flag on `gc sling`/`gc session new`.

> **gc-core ask for v2:** either (1) a `gc sling --model <id>` / `gc session new --model <id>` flag,
> or (2) launcher logic: "if the routed bead carries `gc.model`, set `GC_AGENT_MODEL` from it."
> Both are small, localized changes given the env var and metadata keys already exist.

---

## (B) TELEMETRY — invocation/usage data gc emits for learning

### What gc-core emits (`.gc/events.jsonl`, 26 MB in this city)

`gc events` / `gc analyze` read this append-only stream. Observed event types and counts:

```
17770 bead.updated     2869 order.fired      399 session.woke
 3215 bead.created     2865 order.completed   396 session.stopped
 3101 bead.closed         2 order.failed        7 mail.sent / read / archived
                          1 controller.started
```

- **`session.woke` / `session.stopped`** carry **no model and no tokens** — only
  `{subject: "gastown.boot", payload:{session_id, template, reason}}`. Example stopped reason:
  `"drain acknowledged"`.
- **`bead.created` / `bead.updated` / `bead.closed`** carry the **full bead object** in
  `payload.bead` (id, status, `close_reason`, `metadata`, `labels`, `closed_at`). This is the
  richest learning signal gc emits natively (see C).
- **No `worker.operation` events** in this city. `gc analyze reliability` is explicitly built on
  `worker.operation` events (which "supply the `(model, prompt_version, agent_name)` tuple per
  session") plus lifecycle events `session.crashed` / `session.idle_killed` / `session.draining` /
  `session.quarantined`. Running `gc analyze reliability` here returns an **all-zero TOTAL row**
  and the note *"session.quarantined is not emitted by current production paths."* None of those
  lifecycle/crash events are present in the stream either. So **the model/version/rig correlation
  surface that gc advertises is not populated in this deployment** — it would light up only if the
  controller were emitting `worker.operation`, which it currently isn't.

**Net:** gc-core does **not** emit a per-invocation record with `{model, input_tokens,
output_tokens, success}`. It emits *bead-lifecycle* and *session-lifecycle* events without token
or model fields.

### What the framework (gt/blackrim) emits — NOT gc

Token/model telemetry exists, but in the **framework layer**, written to per-rig
`.beads/telemetry/*.jsonl` (blackrim, poke-holes, gridwars, blackrim-vox, target/gascity):

- **`invocations.jsonl`** — the closest thing to what the advisor wants:
  ```json
  {"ts":"…","tool":"Agent","agent":"a6f97…","session":"62c4…","provider":"anthropic",
   "model":"claude-haiku-4-5","input_tokens":1,"output_tokens":1,"duration_ms":0,
   "mode":"subscription","source":"gt-cache-warm"}
  ```
  Caveat: for `source:"subagent_stop_estimated"` records, `model` is often `"unknown"` and
  tokens are `0` — these are *estimated* stops, not authoritative usage.
- **`dispatch-events.jsonl`** — `{event:"delegation_check", session_id, tool, action:"allow"}`
  (routing/guardrail events, no model/tokens).
- **`eval-runs.jsonl`** — `{run_id, suite, case_id, output, expected, scores[], provider, model}`
  (eval harness; carries authoritative `model` + pass/fail scores).

These are produced by gt hooks (`gt-cache-warm`, `subagent_stop_estimated`), **not** by `gc`.
The advisor cannot assume they exist in an arbitrary gc city.

### Verdict (B)

- **Available today to feed posteriors:**
  - **Model identity:** NOT from gc-core natively (no per-invocation model field). Available only
    if (a) the framework's `invocations.jsonl` is present, or (b) model is pinned per-agent via
    `agent.model` and inferred from `metadata.agent`, or (c) read from bead `gc.model`/
    `gc.reviewer_model` metadata when a model-routing formula like `mol-review-quorum` was used.
  - **Tokens:** NOT from gc-core. Only from framework `invocations.jsonl` (and often
    `0`/`unknown` for estimated records). **A clean capture hook is required for reliable tokens.**
  - **Outcome:** YES from gc-core — bead closure (`status`, `close_reason`, `gc.outcome`,
    `gc.failure_class`) and reopen/escalate transitions (see C). This is the strongest native
    signal.

- **A small capture hook IS needed** to produce clean per-invocation records. Recommendation: a
  **`Stop` / `SubagentStop` (or `PostToolUse`)** hook (the same mechanism gc already wires for
  `SessionStart`/`UserPromptSubmit`/`PreCompact` in `.gc/settings.json`) that appends a JSONL row:
  `{ts, session_id, agent (from GC_TEMPLATE), model (from GC_AGENT_MODEL or transcript),
  input_tokens, output_tokens, bead_id, outcome}`. This is a pack-owned hook — it does **not**
  require gc-core changes — and gives the advisor a self-consistent invocation log keyed to the
  same session_id that beads reference.

---

## (C) QUALITY SIGNAL — bd closure (success vs reopened/escalated)

### Detecting closed-OK vs reopened/escalated via `gc bd`

**Status enum (built-in):** `open`, `in_progress`, `blocked`, `deferred`, `closed`, `pinned`,
`hooked` (from `gc bd statuses`). Categories: active / wip / done / frozen. (`done`, `review`,
`ready`, `escalated`, `reopened`, `abandoned` seen in the binary/other rigs are **custom statuses
or label-states**, not built-ins — configurable via `bd config set status.custom`.)

**Successful closure** — observable on the bead and in the event stream:
- `gc bd show <id> --json` → `status:"closed"`, `closed_at:"…"`, `close_reason:"…"`, plus
  `metadata` and `labels`. Example: `close_reason:"order dispatch completed: tracking bead
  lifecycle finished"`.
- The **`bead.closed`** event carries the **entire bead object** in `payload.bead` (status,
  close_reason, metadata, labels, closed_at) — so closure quality is learnable from the stream
  alone, no extra `bd show` call needed.
- **Structured outcome metadata** (set by formulas/agents): `gc.outcome` (`pass`/`fail`),
  `gc.failure_class` (`none`/`transient`/`hard`), `gc.failure_reason`, `gc.final_disposition`.
  `mol-review-quorum` and `mol-do-work`-style flows close with `gc.outcome=pass` on success and
  `gc.outcome=fail` + `gc.failure_class` on retryable/hard failure. This is the **cleanest
  success bit** when present.

**Reopen / escalate / redo (the noisy negative signal):**
- **`bd reopen <id> [-r reason]`** — sets status back to `open`, clears `closed_at`, and **emits a
  dedicated Reopened event** (per its help: *"emits a Reopened event"*). This is the primary
  "the close didn't stick" signal.
- **`bd history <id>`** — full per-bead audit trail (e.g. 29 entries on a sample bead) showing every
  status transition with author + timestamp. Counting close→reopen cycles per bead is the direct
  "redo rate" metric.
- **Retry/attempt metadata** for dispatch-level redo: `gc.attempt`, `gc.max_attempts`,
  `gc.closed_by_attempt`, `gc.retry_from`, `gc.next_attempt`, `gc.last_failure_class`,
  `gc.partial_fragment` — these track formula-step retries and exhaustion
  (`gc.on_exhausted` = `soft_fail`/`hard_fail`).
- **Escalation** is expressed via **`bd set-state <id> <dim>=<val>`**, which writes a
  `<dimension>:<value>` label (e.g. `mode:degraded`, `health:failing`) **and** creates an event
  bead — so escalations are both queryable (by label) and in the event log. Some rigs use a
  custom `escalated` status for the same purpose.

### Mapping a dispatched task back to agent + shape

A bead resolves to who/what handled it via:
- **`metadata.agent`** — e.g. `"gastown.deacon"` (the agent template that worked it).
- **`metadata.session_id`** — e.g. `"bh-vt5"` (the session; joins to `session.*` events and to a
  capture-hook invocation row).
- **`labels`** — e.g. `agent:gastown.deacon`, `gc:nudge`, `source:session`, `order-run:<order>`,
  `exec`.
- **`created_by`** — e.g. `controller`, `order:mol-dog-doctor`, `gastown__mayor`.
- **Shape/formula provenance** (when dispatched via a formula/wisp): `gc.formula_name`,
  `gc.run_target`, `gc.provider`, `gc.model`, `gc.review_quorum_role`, `gc.kind`,
  `gc.continuation_group`. So a task → **(agent, provider, model, formula/shape)** tuple is
  reconstructable from bead metadata for formula-routed work; for plain `gc sling`/nudge work,
  agent+session are present but model is only known if pinned per-agent or captured by the hook.

### Verdict (C)

Bead closure is a **reliable, fully-supported quality channel today** via `gc bd show --json`,
`bd history`, and `bead.closed`/Reopened events. Success = `status:closed` with `gc.outcome=pass`
(or absent failure metadata); noisy-negative = a **Reopened** event / close→reopen cycle in
history, `gc.outcome=fail`, `gc.failure_class∈{transient,hard}`, retry-exhaustion metadata, or an
escalation state label. Task→agent→shape attribution comes from `metadata.{agent,session_id}` +
`gc.{run_target,formula_name,provider,model}` + labels.

---

## Recommended v1 MVP — learn + recommend (NO gc-core changes)

The advisor ships as a **pack** that observes and advises; it does not mutate dispatch.

1. **Capture invocation records (pack-owned hook).** Add a `Stop`/`SubagentStop` (or `PostToolUse`)
   hook via the agent's projected `.gc/settings.json` mechanism that appends an
   `invocations.jsonl` row: `{ts, session_id, agent=$GC_TEMPLATE, model=$GC_AGENT_MODEL (or parsed
   from transcript), provider=$GC_PROVIDER, input_tokens, output_tokens, duration_ms, bead_id}`.
   If the gt-framework `invocations.jsonl` is already present, ingest it instead/as well. This
   closes the (B) gap without gc-core support.

2. **Harvest the outcome signal from beads/events.** Tail `.gc/events.jsonl` for `bead.closed`
   (and watch for Reopened events) and/or periodically `gc bd list --json` + `bd history`. Derive
   per-bead success = `status:closed ∧ gc.outcome≠fail ∧ no later reopen`; failure/redo = Reopened
   event, `gc.outcome=fail`, `gc.failure_class`, or escalation label.

3. **Join on `session_id` + `bead_id`.** Build training rows of
   `(task-shape, agent, model, tokens, duration) → outcome` by joining the capture hook's
   invocation rows to bead closures via `metadata.session_id`/`bead_id`. Shape comes from
   `gc.formula_name`/`gc.run_target`/`issue_type`/labels.

4. **Maintain posteriors and emit a recommendation.** Per (shape × model/tier), keep a
   Beta-Bernoulli (or similar) posterior over success, with token/cost as a secondary axis.
   **Recommend** a tier per shape — surface it as a report, a `bd note`/comment on the routing
   bead, or `gc mail` to the mayor. **The pack recommends; a human/agent applies it by editing the
   agent's `model` config field.** (v1 *could* optionally auto-edit the per-agent `model` field +
   `gc reload`, but that is coarse, agent-global, and racy mid-session — keep it advisory in v1.)

**v1 deliverable:** a learning loop + recommendation surface that needs only pack-level hooks and
read-only `gc bd`/`gc events` access. No gc-core dependency.

## What v2 auto-apply requires (gc-core)

Per-task application of the advised tier needs **one** of these gc-core additions (smallest first):

1. **Bead-metadata binding (preferred, plumbing mostly exists):** at session spawn, if the routed
   bead/wisp carries `gc.model`, have the launcher set `GC_AGENT_MODEL` from it. `mol-review-quorum`
   already demonstrates writing `gc.model`/`gc.run_target`/`gc.provider` onto step beads; the env
   lever (`GC_AGENT_MODEL`) already exists. The advisor would then just stamp `gc.model` on the
   bead before/at `gc sling` and gc would honor it per-dispatch.
2. **A `--model` flag** on `gc sling` (and/or `gc session new`) that overrides `GC_AGENT_MODEL` for
   that one dispatch/session.

Either makes the advisor's recommendation **auto-applicable per task** rather than per-agent-config.
Tracking bead **bh-ylp** ("MAD (v2): auto-apply the recommended tier at dispatch") is the right home
for this and is correctly gated on the T2 verdict.

---

## Evidence Index (paths & probes — all read-only)

- City config: `/Users/jayse/Code/city.toml`; resolved: `gc config show` (deprecation warning:
  *set provider per agent in `agents/<name>/agent.toml`*).
- Agent defs: `/Users/jayse/Code/.gc/system/packs/gastown/agents/*/agent.toml`
  (`mayor`,`deacon`,`boot`,`polecat`,`refinery`,`witness`) — fields `scope/wake_mode/work_dir/
  idle_timeout/max_active_sessions/pre_start/nudge`; **no `model`** set. `witness` & pooled
  `claude` agents set `provider="claude"`.
- Projected per-agent settings: `/Users/jayse/Code/.gc/agents/<agent>/.gc/settings.json` (hooks +
  `skipDangerousModePermissionPrompt`; **no model**). `.claude/` holds only skill symlinks. No
  claude provider overlay under `/.gc/system/packs/core/overlay/per-provider/`.
- Binary strings (`strings $(command -v gc)`): `agent_defaults.model redefined by %q`,
  `GC_AGENT_MODEL=`, `GC_PROVIDER`, `GC_TEMPLATE`, `claude-opus-4-7`, `claude-opus-4-8`,
  `--model … --effort opus-4-7`, config keys `model/model_name/tier/tiers/durability_tier/
  title_model/reviewer_model/lane_one_model/lane_two_model/prompt_version`.
- Telemetry: gc stream `/Users/jayse/Code/.gc/events.jsonl` (types above; no tokens/model on
  sessions). `gc analyze reliability` → all-zero (no `worker.operation`/crash events). Framework
  telemetry: `/Users/jayse/Code/{blackrim,poke-holes,gridwars.run,blackrim-vox,target/gascity}/
  .beads/telemetry/{invocations,dispatch-events,eval-runs}.jsonl`.
- Bead/quality: `gc bd show <id> --json` (status, closed_at, close_reason, metadata{agent,
  session_id}, labels); `gc bd statuses`; `gc bd reopen` (emits Reopened event); `gc bd history`
  (full transition log); `gc bd set-state` (state labels + event beads). Outcome metadata keys:
  `gc.outcome/gc.failure_class/gc.failure_reason/gc.final_disposition/gc.attempt/gc.max_attempts/
  gc.closed_by_attempt/gc.retry_from/gc.run_target/gc.formula_name/gc.model/gc.provider/
  gc.reviewer_model`.
- Model-routing precedent: `/Users/jayse/Code/.gc/system/packs/core/formulas/mol-review-quorum.toml`
  (formula vars `lane_one_model`/`lane_one_provider`/`lane_one_target`; step metadata
  `gc.model`/`gc.run_target`/`gc.provider` + `gc.outcome` contract).
- Related beads: **bh-2hm** (this investigation), **bh-ylp** (v2 auto-apply at dispatch),
  **bh-9pf** (MAD parent), **bh-uzj** (PRs).
