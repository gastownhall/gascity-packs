# Jev full-build A/B on the documented operator path — September 23, 2026

The first complete `build-basic` runs in this series. Both workflow roots
closed with `gc.outcome=pass`, both reviews approved, and both produced an
implementation that passes the original tests (unchanged) and the four
independent hidden checks. The Jev arm ran two of its three integrations inside
a real Gas City workflow. The baseline arm's implementation drain recorded a
bookkeeping failure that its workflow did not block on (below).

This is one paired run (n=1 per arm). It shows the full workflow now works end
to end with and without Jev; it does not establish a speed or cost difference.

## Setup

- Harness: `scripts/jev_build_ab.py` at the operator path introduced in
  7f1cb03 — standalone city via `gc init --file`, `gc import add`, `gc rig add`
  on a fixture cloned from a local origin, task created with `gc bd create` and
  slung with `gc sling <bead> --on build-basic`; default patrol interval; private
  `GC_HOME` for the supervisor only.
- Gas City: `release/v1.5.0` at 26172ff4b, built locally (`dev`, embeds Beads
  v1.3.0). This branch carries the upstream fixes the earlier runs kept hitting:
  workspace-trust selection (c5fd5fb96, #5904), tmux-reaper (a6b72d832, #5392),
  workflow-root claim gating (449df7c4a, #5901) and force-reinit corroboration
  (8c2b970fe, #5330).
- Beads 1.3.0 (Homebrew), Dolt 2.3.5, Claude Code 2.1.281 on the Max
  subscription, `claude-sonnet-5` at low effort, Jev `jev-1.13.0`.
- Launch variables: `interaction_mode=headless`, `review_mode=agent`,
  `drain_policy=separate`, `max_iterations=2`, no push or PR. The Jev arm adds
  `jev_mode`, `jev_findings_mode` and `jev_failure_mode` = `auto`.
- Host: 18 logical CPUs, 1-minute load about 6–9 during the runs.

## Results ([full-build-003](full-build-003/))

| | Baseline (`gascity`) | Jev (`gascity-jev`) |
| --- | ---: | ---: |
| Status | completed | completed |
| Total elapsed (setup, build, verification, shutdown) | 1,126 s (18.8 min) | 1,284 s (21.4 min) |
| Setup | 15.3 s | 15.6 s |
| Workflow steps closed / closed as fail | 37/38 / 3 (see below) | 38/38 / 0 |
| Review and final report | approved | approved |
| Original tests unchanged; pytest and hidden checks pass | yes | yes |
| Claude API requests (Sonnet 5 plus Haiku auxiliary) | 295 | 321 |
| Claude tokens, total | 16,629,651 | 18,139,458 |
| — output | 83,809 | 96,293 |
| — uncached input | 62,457 | 61,852 |
| — cache read | 15,874,100 | 17,349,312 |
| — cache creation | 609,285 | 632,001 |
| Jev evidence assessment | — | completed: 3,495 in / 218 out tokens, 0.37 s |
| Jev findings categories/pairs | — | completed: 1 finding, Jev below threshold (`residual_risk` 0.29) → ordinary review classed it `required_fix` (747 in / 60 out) |
| Jev failure routing | — | not invoked (no fix failure occurred) |

**Baseline drain failure that still passed.** The baseline worker committed
a correct implementation (4fe0bd5 in worktree `fi-bl2`) but wrote no per-task
summary at the default path, so `do-work.close-source-anchor` closed with
`gc.failure_class=missing_evidence`, failing its `do-work` item and the
`build-basic.implement` drain. Review and finalize nevertheless ran, approved,
and closed the workflow root as `pass`; `workflow-finalize` was still open in
the final bead snapshot. The implement prompts are identical in both packs, so
this reads as a worker miss rather than a pack difference, but a failed
implementation drain should not end in a passing build. That contradicts the
pack README's promise that continuations refuse to finalize as a pass while
work is blocked, and needs its own investigation.

The evidence assessment judged every acceptance criterion `supported`
(confidence 0.90–0.98) and routed each to `reviewer_check`; the reviewer lanes
remained authoritative. Both arms' requirements restated the task, the ASCII
scope and the explicit "do not modify `tests/test_slugger.py`" constraint —
the task-fidelity loss seen in baselines 004 and 005 did not recur after the
requirements-prompt fix.

The Jev arm's test-evidence reviewer found a real defect the baseline did not
have: `implementation-summary.md` recorded a SHA-256 for `slugger.py` that does
not match the worktree file (an agent-written provenance hash). Synthesis
classified it as a required fix and the fix lane corrected it, so part of the
Jev arm's longer review stage is handling that finding, not Jev overhead. (An
earlier version of this note said the findings step had nothing to classify;
that misread the `gc.workflow-decisions.v1` report, whose answers live under
`decision.answers`.)

The Jev arm took 14% longer and used 9% more Claude tokens in this single
pair. With n=1, uncontrolled host load and nondeterministic agent paths, that
difference is not evidence that Jev slows builds; it is equally not evidence
of savings. Jev's own cost here was small (under 5,000 Jev tokens, under a
second). A comparative claim needs repeated, order-balanced pairs.

## Earlier attempts in this directory

- [full-build-001](full-build-001/): stock Gas City 1.4.2. Aborted after four
  minutes: every worker died at Claude's workspace-trust prompt (103 start
  attempts). Gas City 1.4.2 confirms the dialog with a bare Enter and current
  Claude Code pre-selects "No, exit" — upstream #5796, fixed on `main` and
  `release/v1.5.0` by #5904 (see also follow-up #6531). No model tokens used.
- [full-build-002](full-build-002/): Gas City 1.4.2 with #5904 backported.
  Aborted by choice during setup to target the 1.5 branch instead.
- [full-build-004](full-build-004/): a three-pair rerun of the unchanged packs
  on the 1.5 build, stopped at the user's request during the first baseline
  build because it would not advance the redesign. Inconclusive; no result.

## Observations for Gas City 1.5

- `gc stop` followed by `gc supervisor stop` leaves each Beads store's
  `bd db-proxy-child` (started with `--idle-timeout -1ns`) and its
  `dolt sql-server` running. The harness now stops them, scoped to the run's
  own city and rig paths, and sweeps a second time after 20 s.
- Ten seconds after the baseline city's cleanup, a new proxy started for that
  city's store; its launcher was not identified. Any `gc bd` call against a
  stopped 1.5 city starts a proxy that never exits — a monitoring query issued
  during this session did exactly that for the Jev rig store (stopped by hand).
- `gc bd` in 1.5 prints an "answering from the rig … store" notice ahead of
  `--json` output when both streams are merged.

## Reproduce

```sh
# Build gc from the 1.5 branch in a separate worktree, then:
TYPESAFE_API_KEY=… python scripts/jev_build_ab.py \
  --out specs/experiments/jev-operator-path/<new-dir> \
  --arms both --repetitions 1 --continue-on-failure \
  --gc-bin /path/to/gascity-release-v1.5.0/bin/gc
```

The harness refuses to start when the 1-minute load exceeds the CPU count
(`--max-load` overrides), and allows 75 minutes per workflow.
