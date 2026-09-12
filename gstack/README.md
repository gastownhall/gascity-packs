# Gstack Lite Gas City Pack

This is the canonical lightweight delivery pack for this city. It publishes
focused gstack skills and no delivery formula graph or pack-local worker fleet.

Ordinary delivery is deliberately direct:

1. create one durable bead in the code-owning rig;
2. give one implementation owner an exclusive write lease;
3. run repository-native checks;
4. expose one immutable candidate to required CI, external PR bots, and one
   independent different-family review for material changes;
5. consolidate and deduplicate exact-head findings, then allow at most one
   focused repair owner and require a consolidated exact-repaired-head re-review;
6. publish through the repository's protected path;
7. deploy, smoke-test, and account for wall time and rework.

A draft or non-mergeable PR may collect CI and bot feedback, but it grants no
merge authority. Bounded unavailable/timeout results are recorded in the
consolidated artifact before repair begins. Safety findings always block merge;
other blocking findings fail upward only after the consolidated re-review.
Rejected work stays reachable by exact commit, diff, and evidence until an
approved successor or durable remote reference preserves it. Rescue carries the
candidate forward by default; rebuilding from protected `main` requires a
recorded architecture, provenance, or security reason.

Explicit research and planning deliverables use a separate lightweight route:
the Sol/high Mayor creates and seeds a persistent, attachable
`gc.research-planner` conversation on the `sol-research` Sol/max provider, then
starts research immediately. After an exact structured `READY_FOR_ATTACH` safe
checkpoint, the Mayor queues autonomous continuation and returns the attach
command; attachment is optional steering, never a start gate. The session owns
the discussion until the plan, source artifacts, HTML/CSS report, reports-list
entry, and live-link verification are complete. Raw `gc sling ... --no-formula`
work is reserved for explicitly background research. The city and every current
rig cap the lane at one active session, and the audit forces newly added rigs
to receive the same singleton patch.

Use `gstack-lite` by default. Add `review`, `qa`, `cso`, planning, design,
migration, documentation, or release skills only when the changed surface
justifies that gate. The former `gstack-build` GraphV2 formulas and their
pack-local agents are retained under `../deprecated/gstack-graph/` for
historical audit only; Gas City does not discover or route them.

Import the pack at city scope:

```toml
[imports.gstack]
source = "https://github.com/gastownhall/gascity-packs.git//gstack"
```

Import the standalone shared roles on each rig:

```toml
[rigs.imports.gc]
source = "https://github.com/gastownhall/gascity-packs.git//gascity/roles"
```

Do not import `deprecated/complete-delivery` or route ordinary work through
`build-basic` or any archived gstack formula.

## Bounded delivery and health snapshots

Terminal product deliveries store a `gc.delivery.metrics` object conforming to
[`gc.delivery/v1`](./skills/gstack-lite/schemas/gc.delivery.v1.schema.json) on
their durable bead. Generate deterministic JSON directly from supported Gas
City outputs:

```sh
python3 gstack/skills/gstack-lite/scripts/delivery_snapshot.py delivery
python3 gstack/skills/gstack-lite/scripts/delivery_snapshot.py health
python3 gstack/skills/gstack-lite/scripts/delivery_snapshot.py snapshot
```

The delivery rollup includes only closed, explicitly instrumented `bug`,
`feature`, `task`, and `chore` beads. Ephemeral records, wisps, and control-plane
types are excluded; incomplete records remain in the denominator so telemetry
coverage is visible. The health result is separate and summarizes supported
`gc doctor --json` warnings. Advisory warnings are evidence to act on, not
universal launch blockers.
