# gascity-jev v2 overlay: structural evidence — September 26, 2026

No-LLM runs of the rebuilt `gascity-jev` overlay in disposable Gas City cities.
No Claude session and no live Jev call was made. The real `jev-build` and
`jev-build-compact` formulas ran end to end: every Claude role (`gc.*`) was
patched to [`scripts/jev_stub_worker.py`](../../../scripts/jev_stub_worker.py),
a one-shot script that does what its step's prompt asks with fixed,
schema-valid output, and the `gc.jev-gate` worker ran the real gate. Jev
answers came from a loopback stub inside
[`scripts/jev_structure_city.py`](../../../scripts/jev_structure_city.py).

- Host: Linux, 24 CPUs. `gc 1.5.0-dev-bb+8ab11cc90` (source
  `~/src/gascity-1.5-dev-bb`), bd 1.3.0, Dolt 2.3.5, system Python 3.14.
- Isolation: a `mkdtemp /tmp/jst-*` city with `GC_HOME`, `XDG_RUNTIME_DIR`,
  `DOLT_ROOT_PATH` and `GIT_CONFIG_GLOBAL` inside it, `launchctl`/`systemctl`
  shims that exit 1, a private supervisor port, `bd.dog` and the `claude` agents
  suspended, `mol-dog-stale-db` skipped. Teardown: `gc stop --force`,
  `gc supervisor stop --wait`, then two process sweeps scoped to the run's path
  25 s apart. Every run's `result.json` records `swept: []`: nothing survived.
- The fixture is the inference gate's slugify repo. Because PyPI is unreachable
  from this host, the gate's test command ran the fixture's three pytest-style
  tests with a stdlib stand-in runner (`jev_test_command`), not pytest.

## Results

All times UTC. "Lanes" are the review beads created in the first loop
iteration; `apply` is the fix lane.

| Run | Scenario | Gate item | Lanes | Root | Publish closed → root closed | Review report | Decisions / labeled / misses |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [001](structure-001/) | `some`: AC-1 at P 0.4, others 0.05 | `jev`; acceptance on AC-1 only; test evidence skipped; simplicity design-only | acceptance, simplicity, synthesize, apply | pass | 03:31:17 → 03:31:23 | valid | 6 / 1 / 0 |
| 001 | `none`: all 0.05, `simplicity.design.skip_when_screen_clean` | `jev`; every lane skipped; loop dropped | none | pass | 03:34:29 → 03:34:35 | valid | 7 / 0 / 0 |
| 001 | `audit`: `jev_audit_rate=1`, acceptance lane reports AC-2 violated | `jev`; every act decision audited, so every lane runs at full scope | all five | pass | 03:39:06 → 03:39:10 | valid | 6 / 6 / **1** |
| 001 | `tripped`: next build after the miss | `jev`; all four criteria in confirm; test evidence still skipped | acceptance, simplicity, synthesize, apply | pass | 03:43:33 → 03:43:41 | valid | 6 / 4 / 0 |
| 001 | `nokey`: city restarted without `TYPESAFE_API_KEY` | `fail-open:no_key`; every lane at full scope | all five | pass | 03:48:15 → 03:48:22 | valid | 6 / 6 / 0 |
| [002](structure-002/) | `jev-route` without a key in the operator shell | router failed open to `jev-build`; single lane | simplicity, apply (no synthesis) | pass | 03:57:48 → 03:57:56 | valid | 7 / 1 / 0 |
| [003](structure-003/) | `jev-route` with the stub: compact | `jev-build-compact`; single lane | simplicity, apply | pass | 04:02:19 → 04:02:25 | valid | 7 / 1 / 0 |

What each run shows:

- **Gated lanes, synthesis and loop.** Lane beads exist only for lanes the item
  says `run`; synthesis appears only with two or more lanes (runs 002/003 had
  one lane and no synthesis bead); with no lanes the review loop is absent and
  review-report → finalize → publish run directly. Every root closed `pass`
  only after the bond's publish.
- **Fail open.** Without a key the gate recorded `jev.review_error = no_key`,
  logged six `escalate` decisions with reason `jev unavailable: no_key`, and ran
  every lane. The intake router did the same in run 002 (`"error": "no_key"`,
  formula `jev-build`): `gc gc jev-route` runs in the operator's shell, so the
  key must be in that shell, not only in the sessions' `[workspace.env]`.
- **Audit, miss and circuit breaker.** In `audit`, all six act-band decisions
  were audited and labeled from the lane verdicts; the acceptance lane's
  `violated` on AC-2 was recorded as a miss and wrote
  `review.criterion.tripped = true` to `bands.json`
  ([audit.bands-after.json](structure-001/audit.bands-after.json)). In the next
  build (`tripped`) every criterion went to the acceptance lane while the
  test-evidence decision, a different type, kept acting.
- **Decision log.** Each build wrote `<artifact_root>/jev/decisions.jsonl`
  (copied as `*.decisions.jsonl`) and the shared `ledger.jsonl`; outcomes carry
  `label`, `audited`, `band` and `miss`.
- **Compact route.** Run 003's graph was prepare → one `do-work` drain → gate
  → bond, with no requirements, plan, plan-review, decompose or summarize step.
  The gate found the worktree through the input convoy and parsed C1–C4 from
  the task's "Expected behavior" list; the review report labeled the intake
  decision `compact` from the finished diff.
- `jev-build.workflow-finalize` was still open in the `audit` snapshot taken
  8 s after the root closed; it closes after the root by design (structure spike
  gotcha 4).

## The check-with-children loop inside a bond ([loop-spike](loop-spike/))

The one graph shape the structure spike had not tested: build-basic's review
loop is a check whose template has children. In a no-LLM city with script
workers, a bond holding that loop (check fails on iteration 1, passes on 2):

- all lanes: iteration 1 ran three lanes, synthesis and apply; the check failed;
  iteration 2 minted fresh children; the ralph control closed pass; then
  review-final → finalize → publish, root `pass`
  ([loop-all](loop-spike/evidence/loop-all.beads.tsv));
- only simplicity: the `{{simplicity}} == run` conditions held on both
  iterations (no other lane bead in either) ([loop-simp](loop-spike/evidence/loop-simp.beads.tsv));
- loop dropped by `condition = "{{loop}} == run"`: review-final → finalize →
  publish, root `pass` ([loop-dropped](loop-spike/evidence/loop-dropped.beads.tsv)).

Iteration children carry `gc.attempt` equal to `GC_ITERATION`, and the
iteration scope bead's `gc.root_bead_id` is the workflow root, which is what
`implementation-review-approved.sh` keys on, so the base check works unchanged
inside the bond.

## Problems found and fixed while building

| Problem | Evidence | Fix |
| --- | --- | --- |
| `gc import add <local path>` pins a git checkout to its committed `HEAD`; uncommitted pack edits were not loaded (`formula "jev-build" not found`) | first structure attempt | the structural harness writes a plain-path import; the A/B harness refuses a dirty pack tree |
| `gc bd close` from a one-shot script session is refused: the claim assigns the session id, the close acts as the session name | stub log, `cannot close …: assignee is "je-wisp-18p", actor is "…-pool"` | gate and stub close with `gc bd update --status closed` (the structure spike's method) |
| In an expansion (bond) template, `{{var}}` in metadata renders as `{value}`; the fanout was quarantined with `unknown formulas v2 target "{gc.implementation-worker}"` | review-fanout bead `gc.controller_error` | bond metadata and prompt text use single-brace `{var}`; conditions keep `{{var}} == value` |
| A workflow root (`gc.kind=workflow`) was handed to a role session by `gc hook --claim` | stub log | gate and stub release latches with `gc bd release-if-current`, as the base `claim` command does |
| Pack commands receive `gc`'s `--city`/`--rig` flags first | run 002 first attempt | `jev-route/run.sh` strips them, as `claim` does |
| `urllib` routes loopback calls through `HTTPS_PROXY` | unit test against the stub | the client bypasses proxies for loopback URLs only |
| Check gates run with `HOME` = city dir; this host's `~/.local/bin/bd` is a wrapper that execs `$HOME/...` | requirements check `gc.attempt_log` | the structural harness puts the real `bd` first on `PATH` (the A/B harness already does) |

None of these is claimed as a Gas City bug: each is either documented behavior
(bond vars, latches, pinned imports) or specific to how a script session or this
host is set up.

## Not shown here

- Anything about real Claude sessions or live Jev answers: stubs answered every
  question, so this proves the graph, the gate plumbing, the bands, the audit
  and breaker bookkeeping, and fail-open, not the quality or savings of the
  decisions.
- Review-loop iterations with real findings: the stub apply lane always
  returned `done`.
