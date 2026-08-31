### Orchestrate

**You own the program, never the code. Author briefs, drain the queue, keep the frontier green, decide.** For a whole project handed to one standing coordinator chat: multi-day, many stacked PRs, dozens to hundreds of subagents, the human checking in twice a day instead of every five minutes. One task driven to a predicate is Autonomous run. One ambitious run needing a bespoke workflow is figure-it-out. Route here when the work outlives any single agent. Work one agent could finish inside the session's budget is not a program; measured head-to-head, this playbook's ceremony turned a half-hour 12-unit job into 1 landed unit while a plain agent landed all 12. Below that line, route to Autonomous run.

Ceremony must scale with the program. Every gate below prices in coordinator minutes; on cheap near-identical units, collapse it as each section directs rather than paying list price.

Three rules carry the rest.

- Completions are queue events, not interrupts.
- Every spawn and every resume carries the standing orders verbatim.
- The brief is the product. A vague brief fails quietly, because a worker cannot ask you a question.

Open a todolist with the steps below copied in verbatim. A step you skip stays listed with `skip: <reason>`.

#### Roles and placement

- **Coordinator (this chat).** Local. Frames, authors briefs, drains the canonical host inbox, owns the human report, makes judgment calls. It never authors or edits code: conflicted merges, restacks, and code changes are always tasks. Mechanically landing a verified unit (fast-forward or clean cherry-pick of a worker's commit, then push) is bookkeeping the coordinator may do itself on repos where local git is cheap; queueing finished work behind an idle stacker is how a deadline harvests nothing. The loop is agentic end to end. Agents are spawned, resumed, and drained only through `spawn_subagent`. Durable state reads and writes use the host's canonical task and agent state. This playbook does not create a second scheduler, database, or session manager.
- **Track boards.** Partitions belong in canonical host state, not nested spawners. Grok Build `MAX_SUBAGENT_DEPTH` is 1, so this coordinator chat owns every `spawn_subagent` call. A child that calls it fails. When the program exceeds one drain, keep per-track units, briefs, and rollups in host state and still spawn workers and verifiers from here. Do not send Cursor `environment`. Isolation is `isolation`: `"none"` or `"worktree"`. Cap in-flight children at what one drain can process, roughly ten, as a rolling window; never as blocking batches, which cost the slowest child of every batch.
- **Worker / verifier.** Always `isolation: "worktree"` unless the task needs this machine: driving a local app or CLI; reading local transcripts; simulators; auth that exists only here. Worktree children cannot see unsynced local-only state, so their briefs inline what they need or point at repo paths. Prefer fewer, broader workers; one writer per worktree or branch (principle-separate-before-serializing-shared-state). Run a unit's verifier as `independent-verifier` on a different `model` from its worker.

Depth stays at this coordinator chat, then workers and verifiers. Tracks are host-state partitions, not nested agents. Hard-coded swarm trees were tried and parked as too rigid.

#### Durable state boundary

The coordinator MUST NOT create a playbook-local store or invoke an unshipped orchestration CLI. Keep transient prompt context in the current session. Publish durable units, claims, frontier, verification, gates, and decisions through the host's canonical task and agent state. For Gas City adapters, use Gas City formulas and Beads for routing, retries, persistence, and fanout/fanin. If the host lacks a field, record a gate or reported gap instead of adding a parallel store.

#### The brief

Your prompts to agents are your only product, and a sloppy brief compounds into slop across the whole tree. Every spawn carries all of it; a field you cannot fill is a unit you have not scoped yet.

```
GOAL         one sentence, the outcome, executable by a stranger with no chat access
SCOPE        paths this unit may write; paths it may not; its exclusive worktree or branch
CONTEXT      pointers to files and PRs; upstream reports pasted in full when this unit
             depends on them, because workers cannot see siblings
ACCEPTANCE   checkable criteria, one per line
VERIFY       exact commands or a project verify-* skill path, plus known gotchas
TIMEBOX      rough cap on runtime; on expiry, return partial findings and stop rather than run on
FORBIDDEN    no gt, no rebase, no force-push, no fixes outside scope, plus unit-specific bans
REPORT       status, branch, head SHA, PRs, verdict, what you actually ran, deviations,
             suggested follow-ups
STANDING     <standing-orders register pasted verbatim>
```

Size the brief to the unit. A one-command unit gets the template collapsed to a paragraph that still names goal, scope, the verify command, and the report shape; a 4KB scaffold around a two-line edit costs more to write and obey than the edit. Shared-cwd (`isolation: "none"`) children may reference the standing-orders source by name. Worktree children and every resume get the standing orders pasted verbatim, because they cannot see unsynced local-only state.

A track-board brief adds its track boundary and unit list, the spawn budget this coordinator will honor, the drain protocol, and the rollup format (per child: name, status, PR, head SHA, verdict, one line; plus track status and frontier delta).

A dependency is a context relay, not just ordering: undeclared upstream context makes the worker guess. Missing fields are a refuse-to-spawn condition. Audit one sampled worker brief per track per wave, concurrently with the wave it samples, never as a gate in front of it; a failing brief stops that track and fixes the track-board instructions, not just the worker, because brief quality decays late in a run. Never resume-chain a brief; respawn fresh with consolidated scope.

#### Steps

1. **Frame.** State the done predicate as something countable ("all 126 units merged, each ledger-verified `unit-test-verified` or better"). Quantify scope: units, rough effort, expected stacks, and the wall-clock budget. If one agent could finish inside that budget, stop here and run Autonomous run instead. Collapsing must not depend on another document being present: it means do the work directly in this session, plain workers where they help, verification inline, landing as you go, and none of the store, register, or pilot machinery below. Schedule landing against the budget: by roughly 70% of it, stop spawning and land what is verified, because finished-but-unlanded work counts as zero. Name the tracks per project. A contested decomposition or one-way door goes through the arena skill before the pilot. Present the framing once; reversible prep proceeds without waiting.
2. **Confirm the host runtime.** Open the trail via the show-me-your-work skill, write the standing orders before any spawn, and seed the frontier from existing canonical host PR/task state.
3. **Pilot.** Push one unit through the whole path: brief, worker, verification, stack entry, ledger row, merge. The pilot exists to falsify the brief template, the verify recipe, and the unit size while that costs one agent instead of fifty. Fix the contract from pilot evidence before any fan-out. Scale the pilot to the unit: on programs of near-identical cheap units, the first unit is the pilot, run as a normal unit with its verify command inline, and fan-out starts the moment it lands. The dedicated pilot pipeline (separate verifier agent, audit gate) is for expensive or novel unit shapes, not for clone-units where a serialized pilot has nothing to falsify.
4. **Scale.** Spawn a rolling window of workers up to the in-flight cap, refilling as children finish; blocking batches pay the slowest child of every batch. Keep per-track units, briefs, and rollups in canonical host state only past the one-drain threshold in Roles. Recompute ready work after each drain; relay upstream reports into downstream briefs; keep sibling communication upward only. The sampled brief audit runs alongside the wave it samples and stops the next refill on failure, not the current one.
5. **Drain.** Run the queue discipline below at every drain point.
6. **Land.** Landing is continuous, never a terminal phase: integration starts with the first verified unit and runs alongside the remaining waves. On heavy repos the stacker is a standing role from wave one, integrating as units verify; on repos where local git is cheap, the coordinator lands verified units itself per Roles. Keep the frontier green before upper-stack work; Stack safety governs. Advance the canonical host frontier only on merge or reported new head SHAs.
7. **Close.** Drain the final inbox, reconcile every spawned agent to a terminal row (done, abandoned, zombie-reconciled), confirm the predicate on the real artifact, confirm every landed PR has a verdict for its current head SHA, audit the trail per show-me-your-work including its cross-model review, and encode recurring corrections into the standing orders or brief template. Leave canonical host state intact as the postmortem.

#### Queue and drain

- On a completion notification, publish the pointer through the canonical host task/agent API and return to what you were doing. Never deep-review inline; a completion that needs review becomes a verifier unit. Never review a diff inside a drain.
- Drain in batches at four points: the end of a critical section, a track rollup, a frontier watcher wake (arm `monitor` plus `/loop` → `scheduler_create` as heartbeat), and before a human report. Begin each batch with the canonical host inbox. Arrivals during a drain wait for the next one.
- Critical sections you finish first: authoring a brief, a stack operation, a conflict decision, writing a gate, updating ledger or frontier.
- Each drain classifies every pointer (landed, needs-verify, failed, zombie, noise), writes resulting unit and ledger rows through canonical host state, then spawns the next wave in one message.
- Account for every spawned child at its track's rollup: arrived, respawned, or its scope explicitly absorbed. Silently redoing a missing child's work hides both the wasted spend and the coverage gap its result existed to close.
- A drain turn ends with the canonical host status counts, what changed, and gates open. Detail lives in host state; the full reply contract applies at checkpoints and close.

#### Stack safety

- The frontier is a computed host-state object, never narrative. Recompute it from `gt` after every merge and stack mutation because GitHub base refs drift mid-restack while gt tracking is authoritative: ordered PR list, branch names, head SHAs, a generation number, and the lowest unmerged PR. Resolve it where gt knows the stack, normally the stacker's clone; a checkout whose gt metadata never saw the submits reports no PRs and the command errors rather than guessing.
- Exactly one stacker per stack may run `gt`, serialized within its stack; record the holder in the standing orders. Restacks run in a worktree child or locally; this host has no Cursor cloud VMs.
- Workers never rebase and never run `gt`. Babysitters follow `playbooks/babysit.md`, one per stack, scoped to one immutable frontier generation; they report conflicts to the stacker rather than restacking.
- PR closes and retargets go through the stacker only; closing a base PR orphans every chain above it. Merges and stack surgery are units with briefs like any other.
- One retro watcher follows merged PRs for reverts, post-merge CI breaks, and orphaned follow-ups.

#### Verification

Scale verification to the unit. When VERIFY is a single cheap command, the worker runs it and reports the output, and the coordinator spot-checks receipts; a dedicated verifier agent (on a different model family than the worker) is for units whose verification is expensive, judgment-laden, or high-blast-radius. A verifier agent whose entire product would be rerunning one command is ceremony, not verification.

Write verification rows through canonical host state. Check the current PR and head SHA there. Each row is keyed by PR number plus head SHA and uses one of `live-ui-verified | unit-test-verified | type-check-only | verifier-blocked | verifier-failed`. CI green is an input to a verdict, not a verdict. Behavioral work needs better than `type-check-only`. `verifier-blocked` is not a pass; respawn when the environment heals. `verifier-failed` gets a fix unit, not a re-verify. A worker may self-report; a verifier overrides it on the same key. A new head SHA voids the row, so re-verify after restack. The ledger answers "was this verified", not memory and not the transcript.

A unit is not done until its output is externalized the moment it lands, never batched to the end of the run: a worker pushes its branch, a verifier writes the canonical ledger row, and receipts land in host state. Work that exists only on one VM when that VM dies was never done.

#### Liveness and failure

- Never resume an agent to check on it; a resume restarts an idle agent. Probe read-only: canonical ledger and unit state, `gh`, pushed branches, `get_command_or_subagent_output` with `timeout_ms` omitted or `0`. Transcript mtime is not liveness.
- A silent death gets a synthetic postmortem pointer in the canonical host inbox (unit, failure mode, last evidence, options). Replan on evidence as it arrives; never wait for full quiescence.
- Retry by mode: cap-hit or oom, respawn with smaller scope; network-drop, retry as-is; tool-error, retry on a different model; unknown, retry once. Two retries, then abandon the unit and replan around it.
- A zombie that returns hours late reconciles against the current frontier and ledger before anything is accepted; the world moved while it slept. Salvage unique findings through a fresh unit, never a blind merge.
- When continued spawning would produce garbage tree-wide (bad upstream output, broken acceptance, dead infra), write a stop line at the top of the standing orders, let in-flight work finish, fix the cause, clear it.
- Bound your own infra retries the same way you bound a child's. After a few consecutive tool aborts, stop retrying: write a terminal handoff to durable state (what is done, where it lives, the exact command to resume) and end the run. Hours of retry loops against a dead executor produce nothing a handoff would not.
- After a session restart: in-session `spawn_subagent` children are gone. Re-read the standing orders and canonical host unit state, recompute the frontier, reattach by PR and branch rather than `subagent_id`, respawn workers from stored briefs plus current state, drain, resume. No playbook-local lock or store needs repair.

#### Escalation

Reaches the human, batched into canonical host gates rather than per item: irreversible actions (force-push to shared branches, deploys, deletions, closing someone else's PR), genuine product or preference calls no experiment settles, a standing order that contradicts observed reality, a program-level dead end that survived a replan. Park each as a host gate before asking, and route work around it.

Never reaches the human: frontier nudges, restack mechanics, retries, CI flake triage, review-thread triage, format fixes, scope the brief already forbids (refuse and continue), and "should I keep going". When in doubt, act and log; deferring is the measured failure mode.

Mid-run discoveries fix only what blocks the frontier. Everything else parks in follow-ups; at this fan-out a small scope leak multiplies into PRs nobody asked for.

**Reply:** at checkpoints and close: the predicate and counts from canonical host unit and ledger state, tracks and what each landed, the frontier (PR list plus SHAs), verdicts summary, what was abandoned and why, gates awaiting the human (the only asks), the canonical state location, and the trail path. Numbers from host state, not narrative. Include PR links.
