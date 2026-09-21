# Verified STOP respawn source (residual precision (a))

Measured 2026-09-21 against the live `maintainer-city` Gas City (the city that
runs this pack), replacing the design's repo-evidence-only assertion that
"re-selection relies on the rig's patrol respawn cadence (reconciler/pour)".

**Finding: the respawn source is the city-level `[session_sleep]` restart policy
applied by the session reconciler — not a poured wisp, not a cron/order cadence,
and not `orphan-sweep`.** Two mechanisms that look like plausible candidates are
provably inert for a guard STOP, one of them *because of* the zero-mutation
contract.

## Ruled out, each with the concrete check

**1. Not a poured wisp.** The guard's three STOP arms are echo + `gc runtime
drain-ack` + `exit 1` and nothing else: `:305-:306` (fetch), `:323-:324`
(skip-arm checkout), `:337-:338` (probe error). The only `gc bd mol wisp` pour
inside the `rebase` step is `:277`, within the missing-`$TARGET` halt
(`:249-:297`). Line-scoped grep over the guard block `:298-:341` finds no pour
site. This is the designed asymmetry: the halt pours precisely so one bead
cannot end the merge lane; the guard STOPs deliberately do not.

**2. Not a cron/order cadence.** `gc order list` in this city has exactly three
`formula`-type cooldown orders — `randy-patrol` (3h), `seth-patrol` (15m),
`wendy-patrol` (1h) — and none for the refinery. So the *mechanism* for a
cadence-driven patrol pour demonstrably exists and is in use, but it is not
wired for `mol-refinery-patrol`. `git grep` over the gastown pack confirms the
pack ships no order definition for this formula: every
`gc bd mol wisp mol-refinery-patrol` site is inside the formula itself or the
refinery prompt template.

**3. Not `orphan-sweep`.** The core `orphan-sweep` order (exec, 5m cooldown,
"Reset beads assigned to dead agents back to the work pool") lists
`--status=in_progress` beads and resets only those whose assignee fails
`is_known_agent`. That predicate's **first** test is
`agent_exists "$name"` — a direct match against a configured agent template —
and the patrol wisp is assigned to `$GC_AGENT` = `<rig>/refinery`, which is a
configured agent (`gastown/agents/refinery/agent.toml`). So the abandoned
`in_progress` patrol wisp is skipped, not reclaimed. The script's header states
the same scope in prose: beads "assigned to agents that don't exist in ANY rig"
are the targets. A dead *session* of a live *agent* is not in scope.

**4. Not `nudge-on-route`.** That core order ("Nudge the target session when a
bead is routed to it") is event-triggered on `bead.updated`. Every guard STOP
arm mutates no bead state by contract, so no `bead.updated` event is emitted and
no nudge fires. The zero-mutation property that makes the STOP safe is exactly
what makes this recovery path inert.

## The surviving source

```
[session_sleep]                       # maintainer-city config
interactive_resume = "5m"
interactive_fresh  = "5m"
noninteractive     = "5m"
```

```
# gastown/agents/refinery/agent.toml
wake_mode = "fresh"
idle_timeout = "2h"
max_active_sessions = 1
```

A patrol session is non-interactive, so the reconciler restarts it on the
`noninteractive = "5m"` sleep policy with a fresh session. The restarted session
runs `find-work`, which selects open beads assigned to this refinery carrying
`metadata.branch` — re-selecting the untouched work bead. This is precisely the
design's retry-by-repatrol semantic, and the formula's own `find-work` step
already names the mechanism in prose: "The session_sleep policy will restart
this session after the configured idle interval."

So the correct reading of residual precision (a) is: **the STOP is recovered by
the session-lifecycle restart, on a 5-minute policy in this city, and the bead
is re-selected by `find-work` — not by anything the STOP arm itself does, and
not by the bead-state-driven recovery orders.** The lane therefore does not
stall indefinitely in this configuration, while still never treadmilling: each
restart re-runs the decision from scratch against freshly fetched refs, and a
persistent failure surfaces as a repeated STOP log rather than a mutation loop.

## Limitation — state this in review

`maintainer-city` does **not** instantiate the gastown rig agents: `gc agent
list` contains no `refinery`, `witness`, `polecat` or `deacon`, and
`gc session list --state=all` has no refinery session. What is measured above is
therefore the governing configuration (city `[session_sleep]`, the refinery
agent contract, the full order inventory) plus the code paths that act on it,
traced end to end — **not** a direct observation of a live refinery
STOP→respawn cycle. Confirming the 5-minute restart empirically requires a rig
that actually runs the refinery. The three ruled-out paths (1-4 above) are
config- and code-level facts and do not depend on that.
