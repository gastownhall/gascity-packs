# Gastown Pack

Gastown is the domain-specific coding workflow pack. It provides the city
coordinator roles, rig worker roles, patrol formulas, and the pack-local dog
pool used for stuck-agent shutdown warrants.

## Import

```toml
[imports.gastown]
source = "../packs/gastown"
```

Use the pack as the workspace pack for city-scoped agents and as a rig pack for
rig-scoped agents.

## Composition Ordering (when maintenance is present)

The Gas City maintenance pack still ships a legacy `mol-shutdown-dance`
(required `warrant_id` var, raw `{{target}}` placeholders, PARDON mail to the
requester). Formula names resolve last-wins across pack formula layers, so
whichever pack's formula layer loads last decides which recipe dogs run. The
dog agent resolves to gastown's wherever the dog names collide (legacy
includes composition: non-fallback wins over the maintenance fallback dog);
in import composition gastown's dog is a distinct `gastown.dog` agent and the
implicit maintenance dog remains a dormant, unused fallback pool. Until the
legacy maintenance copy is retired or renamed upstream, the formula the dog
reads back depends on composition style:

- **Schema-2 cities composing gastown via `[imports.gastown]`** (the style
  shown in Import above) are safe by default: the runtime expands the
  implicit maintenance system pack with the legacy includes pass, before any
  `[imports.X]` layers, so gastown's formula layer loads after maintenance's
  and wins. Do **not** add an explicit `[imports.maintenance]` alongside
  `[imports.gastown]`: an explicit import suppresses the implicit injection
  and moves maintenance into the import expansion, where binding names expand
  in sorted order (`"gastown"` < `"maintenance"`), so the legacy maintenance
  recipe would load last and win no matter where it is written in the file.
  If maintenance must be pinned explicitly anyway, only the import binding
  name's sort position relative to `gastown` controls layer order — too
  fragile to rely on; prefer the implicit injection.
- **Legacy schema-1 cities composing through `workspace.includes`** are
  exposed by default: the implicit maintenance injection lands after the
  user includes, so the legacy recipe wins. Compose maintenance explicitly
  (an explicit entry suppresses the implicit system injection of the same
  pack name) and list it before gastown in the same includes list, so
  gastown's formula layer loads after maintenance's.

Whichever style applies, verify which recipe wins after composing:

```bash
gc formula show mol-shutdown-dance
```

The effective recipe must read warrant metadata from the claimed bead via
`$GC_BEAD_ID` and must not declare a required `warrant_id` var. If it
demands `warrant_id`, the legacy maintenance copy won — remove the explicit
maintenance import (schema-2) or fix the include ordering (legacy includes)
before running dogs.

The same last-wins ordering governs template fragments: maintenance ships
diverging copies of the `propulsion-dog`, `architecture`, and `following-mol`
fragments used by the dog prompt, so the per-style guidance above also keeps
gastown's fragment text authoritative.

## Dog Pool

Gastown owns `mol-shutdown-dance` and the dog agent that runs stuck-agent
warrants, including the dog's `wake_mode` and `work_dir` settings. Where dog
names collide (legacy includes composition), gastown's non-fallback dog wins
over fallback dog providers; in import composition gastown's dog expands as
the distinct `gastown.dog` agent and the implicit maintenance dog remains a
dormant fallback pool that this pack's binding-prefixed producers never route
to.

Gastown deliberately does not ship retired dog formulas for JSONL export or
stale-session reaping. Compose the Gas City maintenance pack or an equivalent
exec-order provider when a city needs JSONL export, stale-session or stale-data
cleanup, and Dolt housekeeping.
