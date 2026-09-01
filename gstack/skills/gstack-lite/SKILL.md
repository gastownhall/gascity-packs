---
name: gstack-lite
description: Deliver software pragmatically from a durable work item through implementation, repository-native checks, one independent review, protected publication, deployment, smoke verification, and concise accounting. Use by default for Gas City requests to build, fix, finish, test and deploy, ship, land, or take work end to end; use heavier gstack planning, QA, security, or migration skills only when the actual risk warrants them.
---

# Gstack Lite

Use one accountable owner and the smallest set of controls that can prove the
change is correct in production. This is a delivery policy, not a large formula.

## Invariants

- Never install or launch a retired delivery graph. Treat `gstack-build` and
  `build-basic` as retired ordinary delivery routes too. Do not mention retired
  workflow names to the user unless they ask about history or an active
  configuration violation is detected.
- Keep one durable `main`. Use one short-lived branch only when repository
  protection requires a pull request, then delete it after merge.
- Cap implementation at two genuinely independent writers and review at one
  reviewer. Rescue replaces a writer; it never adds a seat.
- Fail upward after one failed attempt and one targeted repair. Carry the failed
  diff and exact test evidence to the stronger lane.
- Never allow two sessions to write the same bead, branch, or worktree. Rescue
  replaces the implementation owner after a verified stop; it does not join it.
- Never call work complete before its requested terminal state. “Implemented,”
  “merged,” and “live in production” are different states.

## Route by risk

Use the configured city aliases:

- `gc.research-planner` with provider `sol-research`: explicit research,
  findings, comparison, planning, specification, roadmap, or architecture
  deliverables. Run it at Sol/max as a persistent, attachable planning room.
- `sol-fast`: normal features and fixes.
- `luna-economy`: small, atomic, well-specified or mechanical work.
- `claude-careful`: context-heavy refactors when a second implementation family
  is useful.
- `claude-review`: independent review of Codex-built material changes.
- `sol-rescue`: failed work, difficult debugging, auth, permissions, destructive
  operations, and migrations.

For Claude-built changes, review with Sol/high. Do not start the rescue lane or
an alternate builder concurrently with two existing writers.

## Route quality-first thinking without moving the user

Keep the persistent Mayor on Sol/high as the responsive conversation owner.
When research or planning is itself a requested deliverable or approval gate,
prefer a persistent, attachable Sol/max conversation:

```bash
gc session new <scope>/gc.research-planner --alias <scope>-<slug>-planning \
  --title "<planning title>" --no-attach
gc session submit <scope>-<slug>-planning \
  "interaction_mode=attachable autostart=true. <research and planning brief>. Begin immediately; after concrete kickoff progress, reply exactly READY_FOR_ATTACH at the first safe checkpoint."
# Verify READY_FOR_ATTACH as an exact assistant text block with:
gc session logs <scope>-<slug>-planning --tail 10 --json
gc session submit <scope>-<slug>-planning \
  "Continue autonomously to the report-complete terminal state; do not wait for attachment." \
  --intent follow_up
gc session attach <scope>-<slug>-planning
```

The Mayor creates and seeds it, waits until the structured log contains an
assistant text block exactly equal to `READY_FOR_ATTACH`, immediately queues
autonomous continuation, then gives the user the attach command. The initial turn
must make concrete progress; attachment never starts or resumes work. If readiness is not proven within 60 seconds,
diagnose the same session instead of creating another. Attached user messages
steer ongoing work. Suspend rather than close the session between conversations;
close it only after approved artifacts and the live report are complete. Use
`gc sling <scope>/gc.research-planner <bead-id> --no-formula` only for explicitly
background or report-only work.

Keep `gc.research-planner` bound to provider `sol-research` with
`max_active_sessions = 1` in every current rig. `audit_city.py` must fail when
a new rig lacks the singleton patch.

Pass the verbatim request, relevant context, settled constraints, expected
artifact, and evidence/citation requirements. The Mayor validates and presents
the result instead of independently recreating the analysis. Incidental planning
inside an implementation task does not trigger this lane. The lane does not
implement, review its own work, or become rescue capacity.

Every user-facing research engagement publishes an HTML/CSS bundle at
`/home/nvidia/gascity/reports/<rig>/<slug>/`, adds an active card to
`/home/nvidia/gascity/reports/index.html`, and returns the live
`https://gascity.tail96374b.ts.net/reports/<rig>/<slug>/` URL. The durable brief
must name the slug, title, source-plan directory, expected local bundle, and
evidence/citation requirements. The Mayor verifies both the library link and a
successful live HTTP response before reporting completion.

## Deliver in six stages

### 1. Anchor and measure

Create or identify one durable bead in the rig that owns the code. Record the
authorized start time, source base, intended outcome, acceptance criteria, and
canary. Separate active work, queue/provider wait, tests/CI, review/fix, deploy,
and manual intervention in the final accounting.

Record an exclusive lease on the bead before the first edit:

- `gc.delivery.owner_session`: exact session id;
- `gc.delivery.repo`: code-owning rig/repository;
- `gc.delivery.worktree`: exclusive worktree or branch;
- `gc.delivery.source_head`: immutable starting SHA;
- `gc.delivery.phase`: `implementation`, `review`, or `repair`.

Clear stale inbox work before claiming a new delivery. Verify the assignee and
lease again before every write after a handoff.

Inspect the repository and its instructions before asking questions answerable
from source. When the user authorizes autonomous completion, make reasonable
in-scope decisions without adding approval ceremonies.

### 2. Implement one complete slice

Give one owner a small deployable slice. Use a second writer only for work with
independent files and acceptance criteria. Preserve unrelated working-tree
changes. Run the narrowest useful check during implementation.

For a rescue task, require a focused reproduction or first relevant edit within
four minutes. If that does not happen, stop the lane and return its evidence to
the owner; do not pay for open-ended exploration.

### 3. Run deterministic gates

Run repository-native format, lint, type, test, build, and browser checks in the
order justified by the change. Run cheap failures before model review. Use the
full suite when it is cheap or the blast radius demands it; otherwise rely on
targeted local checks plus required CI and state that boundary explicitly.

Bind every reusable green result to the immutable candidate head and the check
definition (command or CI workflow revision). Inherit it only when both match;
do not rerun an unchanged broad baseline for each slice.

### 4. Review once, independently

For material code, run one direct `gstack.review` pass over the exact candidate
head with a different model family. Record one structured artifact with the
candidate SHA, verdict, severity, file/line, evidence, and required fix.
Documentation-only or harmless test-only changes may use deterministic checks
alone. Add `gstack.qa`, `gstack.cso`, design review, or migration review only
when the changed surface triggers that risk.

Apply actionable findings once and rerun affected checks. If the repaired diff
materially changes, perform one focused re-review. Escalate rather than loop.

Before assigning the one repair owner, revoke the previous lease:

```bash
gc runtime drain <exact-session>
gc runtime drain-check <exact-session>
```

If acknowledgement does not arrive promptly, close or kill the exact session
with `gc session close <session-id>` or `gc session kill <session-id>`, verify
it is stopped with `gc session list --state=all --json`, then replace the bead
lease. Never accept a late commit from a revoked owner.

### 5. Publish and deploy through repository controls

Use the repository's normal protected path. Confirm the PR head is current,
required CI is green, review findings are resolved, and the merge result is on
the protected base. Prefer repository-owned CI/CD credentials. Local cloud
authentication is not required when GitHub workload identity owns deployment;
request it only when no authoritative CI or public verification path exists.

Verify the exact merged revision when the platform exposes it, then run a public
smoke or feature canary. Do not substitute “workflow succeeded” for a requested
production behavior check.

When protected CI and post-merge deployment run the same tree and check
definition, preserve that immutable proof instead of launching a redundant
second broad suite. Still verify the merge SHA, deployment revision, and
behavior canary independently.

### 6. Close and account

Close the bead only after the requested terminal state is proven. Report:

- final commit, PR, merge SHA, deployment revision, and canary;
- every command and result that matters;
- total wall clock and stage breakdown;
- provider/model lane used for each intelligent pass;
- retries, rejected attempts, rework cause, and human intervention;
- residual risk or unavailable evidence.

Store comparable terminal accounting in the durable product bead's
`gc.delivery.metrics` metadata object. Its versioned contract,
[`schemas/gc.delivery.v1.schema.json`](schemas/gc.delivery.v1.schema.json),
covers stage timing, rework, human intervention, model lanes, immutable
revisions, and outcome.

Use `scripts/delivery_snapshot.py delivery` for a bounded product rollup with
telemetry coverage, and `scripts/delivery_snapshot.py health` for separate
supported `gc doctor --json` evidence. Only closed, instrumented,
non-ephemeral product beads count; only `blocking_failed > 0` blocks launch.

## City configuration audit

For changes to Gas City itself, run `scripts/audit_city.py --city <city-root>`
from this skill directory. Use `--fix-stale-skills` only to remove exact stale
`complete-delivery.complete-delivery` symlinks after the active import is gone.
The script enforces this city's strict Gstack Lite profile, so it also rejects
explicit legacy `build-basic` imports. A separate city may intentionally use
that legacy pack, but it is not compliant with this lightweight profile. The
script must pass before calling a Gstack Lite city configuration coherent.
