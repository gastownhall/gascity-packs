---
name: equip-persona
description: Equip a best-fit principal-engineer persona for a task, and inspect the persona registry and warm cache. Run `personas match "<task>"` to see which persona fits a task (and why), `personas equip "<task>"` to equip it and keep it warm for other agents, `personas show <id>` to read a persona's full playbook + verification bar, `personas lint` to check the registry is complete after an edit, and `personas cache` / `personas evict <id>` / `personas sweep` to inspect or age out the warm cache. Use when picking up a task and you want to work at principal-engineer level in that task's domain (backend, frontend, systems, security, data, platform, api-design, test, refactoring, docs), when debugging which persona an agent equipped, or when tuning the registry or warm-cache TTL.
---

# Equip Persona

## Overview

**blackrim-personas** is a dynamic persona system. A generalist agent is competent at
everything and excellent at nothing; a persona makes an agent excellent at one thing for
the duration of one task. The pack is a curated suite of principal-engineer personas —
each a specialist with a domain, a playbook, the conditions under which to equip it, the
skills/tools it brings, and a verification bar — that an agent equips dynamically based
on the task in front of it.

It composes with the rest of the toolchain rather than competing with it: **model-advisor**
picks the model *tier*, **provider-forge** picks the *provider/model*, and **personas**
picks the *role*. A dispatch is a tier, a provider/model, and a persona.

`bin/personas` is the read/equip/inspect CLI. `list`, `show`, `lint`, `match`, and `cache`
are pure reads; `equip`, `evict`, and `sweep` mutate the shared warm cache.

## When to Use

- You are **picking up a task** and want to work at principal-engineer level in its
  domain. Match it, equip the persona, and hold your work to that persona's bar.
- You need to **see why a persona was chosen** — `personas match` shows the score and the
  exact terms that fired.
- You are **debugging the equip-on-task-pickup hook** (it equips a persona at session
  start) and want to see the warm cache state.
- You are **tuning the registry** (adding a persona, adjusting match keywords) or the
  **warm-cache TTL policy**.

**When NOT to use:**

- For trivial or throwaway work — the role does not matter; skip it.
- To pick a model tier (that's `advisor advise`) or a provider/model (that's
  `forge targets`). Personas picks the role only.

## Process

### Step 1 — See the equip decision

```bash
personas match "implement a paginated REST endpoint backed by Postgres"
personas match "audit the upload handler for SSRF" --json
```

`match` scores every persona against the task (whole-word keyword + domain-vocabulary
match, plural/singular aware) and prints the best fit, its score, the terms that fired,
and the runners-up. It is read-only — it does not touch the warm cache. With no signal it
returns the registry's default (generalist) persona, flagged as a fallback.

### Step 2 — Equip the persona

```bash
personas equip "implement a paginated REST endpoint backed by Postgres"
personas equip --from-bead pers-0fs        # pull the task text from a work bead
```

`equip` matches, then **materializes** the persona into the shared warm cache (recording
a last-used timestamp). Its text output is the persona's playbook + verification bar — the
context you adopt for the task. If the persona is already warm, equip *reuses* it
(`was_warm=true`) and refreshes its idle TTL instead of paying the materialize cost again.

In a gas-town session you usually don't run this by hand: the `equip-on-task-pickup` hook
runs `personas equip --from-bead <current bead> --emit-context` at session start and
overlays the persona automatically.

### Step 3 — Read a persona's full definition

```bash
personas show principal-security-engineer
personas list                              # the whole roster
```

### Step 4 — Inspect / age out the warm cache

```bash
personas cache                             # materialized personas + TTL remaining
personas evict principal-backend-engineer  # dematerialize one persona now (e.g. after editing it)
personas sweep                             # evict expired personas now
personas sweep --all                       # clear the whole warm cache
```

The warm cache ages personas out on a **sliding 30-minute idle TTL** (refreshed on every
reuse) with a **2-hour absolute ceiling** (force-refresh so the persona picks up registry
edits). Both are configurable in `personas.toml` `[cache]`. Eviction is lazy — `equip` and
`cache` sweep expired entries as a side effect — so `sweep` is for housekeeping.

## Worked Example

A polecat claims a bead titled "Fix N+1 query in the orders service".

1. **Match.** `personas match "Fix N+1 query in the orders service"` →
   `principal-backend-engineer` (matched: `query`, `service`). The choice is explainable.
2. **Equip.** The session-start hook already ran `personas equip --from-bead <bead>
   --emit-context`, so the backend persona's playbook ("watch N+1 queries, unbounded
   result sets, missing indexes…") is overlaid on the agent.
3. **Hold the bar.** The agent meets the backend verification bar — inputs validated,
   change covered by a test — before handing off to the refinery.
4. **Reuse.** Ten minutes later another polecat picks up a sibling backend bead. The
   backend persona is still warm (`personas cache` shows it), so it is reused, not
   re-materialized.

## Why This Matters

- **Excellence on demand.** The agent becomes a domain specialist for the one task,
  then releases the role — no permanent, bloated mega-prompt.
- **Explainable routing.** Every equip decision shows the score and the matched terms,
  so a wrong match is debuggable and the keywords are tunable.
- **Amortized cost.** The warm cache means a busy fleet pays the materialize cost once
  per clustered work session, not once per task.

## Verification Gate

Before relying on an equipped persona:

- [ ] `personas match "<task>"` chose a persona whose domain actually fits — if it fell
      back to the default, the task description was too thin or a keyword is missing.
- [ ] You read the persona's **verification bar** (`personas show <id>`) and will hold
      your work to it before handing off.
- [ ] If you tuned the registry, `personas lint` is clean (exit 0), `python3 -m pytest`
      passes, and `personas list` shows the roster you expect.

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack contributes a
skill by placing `skills/<name>/SKILL.md` under the pack root, with YAML frontmatter
carrying at minimum `name` and `description`. This file lives at
`personas/skills/equip-persona/SKILL.md`, so it is picked up automatically — `pack.toml`
does not enumerate skills. Once the `personas` pack is imported into a city (vendored
under `packs/personas` and registered via a direct `source = "packs/personas"` import),
the skill surfaces in `gc skill list` binding-qualified as `personas.equip-persona`, and
the materializer projects it into the per-agent skills sink at `gc start`. Verify with
`gc skill list` (and `gc lint .` / `gc doctor`).
