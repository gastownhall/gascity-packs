# oversight-rig

A drop-in Gas City pack that **disaggregates project-level work scoping out of the mayor**. It adds one always-on, rig-scoped `project-lead` role per rig, so the mayor stops being the bottleneck for every project's day-to-day triage and dispatch.

## The problem it solves

In a single-mayor city, the mayor ends up in the minutiae of every project's work scoping — what to dispatch, what's blocked, what to escalate — across every rig at once. That doesn't scale.

## The model

```
mayor (city, unchanged) ──── plans cross-cutting work, handles escalations

  rig: foo                      rig: bar                  …
  project-lead-foo              project-lead-bar
  • bounded to foo's beads      • bounded to bar's beads
  • reads foo/.gc/              • reads bar/.gc/
    project-brief.md              project-brief.md
  • reconciles committed         • reconciles committed
    execution intent              execution intent
```

- **`project-lead`** (rig scope, always-on, one per rig)
  - Bounded to a single rig's beads. Reads its persona, current focus, and escalation triggers from `<rig>/.gc/project-brief.md` — each project owns its own scoping context, so it never piles onto the mayor.
  - Triages its rig every tick and **reconciles committed ready work in its own rig**. It observes existing eligible routes and controller progress but does not create a route from Beads readiness alone or treat a pool route as a concrete session identity.
  - Judges severity (info vs escalate) and writes structured rollup beads.
- **The mayor stays unchanged** and shrinks to what is genuinely cross-cutting: planning work that spans rigs, and reacting to escalations.

## Dispatch safety: READY != RUN

Project Lead dispatch is intentionally narrower than Beads readiness. A plain
ready backlog bead is not execution-authorized and must never be slung merely
because a worker pool exists. On each tick, Project Lead uses the pack's
read-only bounded selector:

```sh
python3 "$GC_PACK_DIR/assets/scripts/select-execution-candidates.py" --rig <rig> --json
```

Only its routed output may be monitored as committed execution intent. It
recognizes an existing valid `gc.routed_to` in the same rig, or a Formula/run
member whose existing root metadata resolves to a live workflow root in that
rig. It fails closed on query, JSON, schema, route, root, or bound uncertainty.
It does not invent or rewrite routes, infer arbitrary bead-tree intent, or add
a committed-root marker. Pool routes remain controller scheduling demand and
are never passed directly to session wake/nudge commands. Missing routing,
Formula control state, or persistent routed-but-open work is surfaced instead
of repaired by Project Lead.

## Deterministic escalation (no relay agent)

The project-lead writes a rollup bead labeled `severity:escalate`. A scheduled order (`escalate-rollups`) uses a mechanical condition trigger that checks for undelivered escalate-severity rollups and delivers them via extmsg — **no second agent decides "is this escalation-worthy."** The judgment is made once, by the agent with the right context, and the rollup bead is the audit trail. Human replies route straight back to the bound project-lead.

## What's in the pack

- `agents/project-lead/` — the role (agent config, prompt template, and a `project-brief.template.md` to copy per rig)
- `orders/` — `patrol-project-leads` (triage cadence) and `escalate-rollups` (deterministic delivery)
- `assets/scripts/` — the delivery script and a rig→channel resolver
- `skills/city-executive-status/` — an optional workflow for maintaining an Obsidian-compatible portfolio brief from project-owner updates

## Optional executive status brief

The `city-executive-status` skill packages the shareable workflow for requesting
structured project-owner updates, validating them, and writing one concise
portfolio brief. It can optionally publish a content-hash-deduplicated summary
through a deployment-specific adapter.

Importing this pack exposes the skill but does not activate its example
schedules or write to a vault. The only active pack orders remain
`patrol-project-leads` and `escalate-rollups`. To enable the workflow, follow the
skill's `SKILL.md`, copy its environment and order examples into the consuming
city, configure local paths, and verify dry-run output before scheduling writes.

## Requirements

- An extmsg/slack adapter in the city for outbound delivery and inbound replies — **compose this pack with your slack pack** (e.g. `slack-full`, `slack-channel`, or `slack-mini`). This pack ships only the oversight role and its escalation machinery, not a slack bridge.
- Optional: a workflow/formula pack (for example `gastown`) supplies the durable Formula/run metadata that Project Lead can safely reconcile. Project Lead does not initiate new convoy formulas.
- Optional: the executive-status skill needs Python 3.11 or newer. Obsidian and a publishing adapter are not required; without them it writes ordinary Markdown to a configured path.

## Install

1. Add the pack to your `city.toml` and stamp a `project-lead` per rig.
2. For each rig under oversight, author its brief:
   ```bash
   cp agents/project-lead/project-brief.template.md <rig-root>/.gc/project-brief.md
   # then edit the brief to fit the project
   ```
3. Bind each rig's `project-lead` session to that rig's channel via your slack pack so escalations deliver and replies route back.
4. `gc supervisor reload` — picks up the new agents and orders.
