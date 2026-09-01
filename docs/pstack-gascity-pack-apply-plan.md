# PStack dest-env apply plan

Superseded for production sequencing by `docs/pstack-production-readiness-plan.md`. This file remains the dest-env archive how-to. It does not list the live file set of PR 385.

This program lands pack honesty on gascity-packs. Dest-env OpenSpec archive is a later host-only step and is unproven. The pack does not ship OpenSpec change payloads. The program is for the pack importer and the dest-env spec owner. The rule is live Gherkin must match the pack. PR ids in order are pack-honesty then dest-env-archive.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `skills/poteto-mode/playbooks/autopilot-stack.md`. The operator lands both PRs. pack-honesty and dest-env-archive stop at merge-ready.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on her explicit go.
- [ ] On her go, persist the plan path on disk with this exact text. "docs/pstack-gascity-pack-apply-plan.md, pack-honesty then dest-env-archive, Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. The operator lands. Done when dest-env live swarm THEN is sequential frame fanout fanin."
- [ ] Read these from trunk at program start. Re-read them at every tick.
  - [ ] `git show origin/main:skills/poteto-mode/playbooks/autopilot-stack.md`
  - [ ] `git show origin/main:skills/swarm/SKILL.md`
  - [ ] `git show origin/main:pstack/tests/test_pstack_pack.py`
  - [ ] `git show origin/main:skills/poteto-mode/playbooks/opening-a-pr.md`
  - [ ] `git show origin/main:skills/show-me-your-work/SKILL.md`
- [ ] Arm the 30-minute audit tick with `scheduler_create` (`interval: "30m"`, `fire_immediately: true`) and `monitor` for event wakes. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from trunk and the persisted plan. Audit the operation against both and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then send the operator a status message, whether or not anything changed, with the queue table of PR, owner, state, and head SHA, the verdicts since the last tick, what merged, open operator gates, and blockers."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] From this parent session, spawn one owner per PR with `spawn_subagent` (`isolation: "worktree"`). Depth is 1. Owners do not spawn.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] pack-honesty is first. It branches from `main` in gascity-packs.
  - [ ] dest-env-archive after pack-honesty. It is host-only. It does not copy an OpenSpec payload from this pack. Host write stays unproven.
- [ ] Hold the file boundaries. pack-honesty touches only `pstack/**`, `gascity/tests/test_formula_assets.py`, `tests/test_gc_role_prompt_integration.py`, and `.gitignore`. dest-env-archive touches only `openspec/**` in dest-env.
- [ ] Hold the review gate. Neither PR changes an interaction.

### PR mechanics, for every PR

- [ ] Open the PR ready, never draft, with `gh pr create` and `draft: false`, or with Graphite `gt` for a stack.
- [ ] Run the repo's lint and typecheck once before the PR-facing push. Push with hooks on.
- [ ] Run `/unslop` before each commit and `/no-comments` before review.
- [ ] Triage every Bugbot and security-reviewer comment per `../references/bugbot-triage.md`.
- [ ] Rebase onto current trunk before babysit and again before the merge-ready report.

### Verdict and merge, for every PR

- [ ] At the merge-ready head SHA, run the swarm per `skills/swarm/SKILL.md`. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. One audit lane that reads the diff and the receipts and distrusts the PR body.
- [ ] Clean only when every lane is `PASS`. Findings go back to the owner. A new head gets a fresh swarm and a fresh verdict.
- [ ] The root appends the PR to the Graphite stack and the operator lands it. Nothing auto-merges.

### Boot recipe, for every live lane

Each live lane runs in its own `isolation: "worktree"` child at the PR head. Drive the real surface (running app, CLI, tests, or Grok browser tools).

- [ ] `git fetch origin <head-branch> && git checkout <head SHA>`.
- [ ] Use the worktree shell. Do not start a web UI.
- [ ] Run the named CLI or pytest command. Capture stdout.
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report.

## Land pack honesty (pack-honesty)

**Depends on.** None.

**Files.**

- [ ] Edit `pstack/formulas/pstack-planning.formula.toml`.
- [ ] Edit `pstack/formulas/pstack-decomposition.formula.toml`.
- [ ] Edit `pstack/tests/test_pstack_pack.py`.
- [ ] Edit `pstack/scripts/apply_intent_change.py` so copy and validate require an external `--source`.

**Build.**

- [ ] Keep selector overrides in the working tree. Commit them on a branch off gascity-packs `main`. Do not commit OpenSpec payloads under `pstack/`.

**You see.**

- [ ] `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py` prints a passing count.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `pstack/tests/test_pstack_pack.py` selector and pack-boundary cases. Run `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py gascity/tests/test_derived_pack_compatibility.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.6` at the PR head, per the boot recipe.

- [ ] Lane 1. Pack suite. Save `pack-suite.png`. Pass when pytest exits 0.
- [ ] Lane 2. Derived pack suite. Save `derived-pack.png`. Pass when pytest exits 0.
- [ ] Lane 3. No pack OpenSpec payload. Save `no-intent.png`. Pass when `pstack/intent/` is absent.
- [ ] Lane 4. Planning run target. Save `planning-target.png`. Pass when `pstack-planning` requirements target is `pstack.investigator`.
- [ ] Lane 5. Decomposition lever. Save `decomp-lever.png`. Pass when `decompose` needs `lever-decision`.
- [ ] Lane 6. Implementer heading. Save `heading.png`. Pass when the prompt contains `# PStack Implementation Worker`.
- [ ] Lane 7. Formula compiler. Save `compiler.png`. Pass when every formula has `formula_compiler`.
- [ ] Lane 8. No graph.v2. Save `no-contract.png`. Pass when no pstack formula sets `contract`.
- [ ] Lane 9. Dest-env still old. Save `dest-old.png`. Pass when dest-env swarm THEN still has `fans out through Gas City graph steps`.
- [ ] Lane 10. Apply refuses pack-local source. Save `refuse-pack-src.png`. Pass when `--source pstack` prints that payloads do not live inside the pack.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Pack test wall time.
- [ ] Probe. `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py` at trunk and at the head, interleaved.
- [ ] Baseline. Record the trunk seconds first.
- [ ] Rule. Head may not exceed trunk by more than 5 seconds.

**Review gate.** None. pack-honesty is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends the PR to the Graphite stack and the operator lands it.

## Archive dest-env specs (dest-env-archive)

**Depends on.** pack-honesty.

**Files.**

- [ ] Create `openspec/changes/audit-pstack-gascity-pack-contracts/` in dest-env on the host. Do not copy it from this pack.
- [ ] Edit `openspec/specs/pstack-gascity-pack/spec.md` by archive merge.
- [ ] Edit `openspec/specs/pstack-pack-fidelity/spec.md` by archive merge.
- [ ] Edit `openspec/specs/pstack-delivery-evidence/spec.md` by archive merge.

**Build.**

- [ ] From a host shell outside bubblewrap, run `python pstack/scripts/apply_intent_change.py --source <host-change-dir> --dest /home/tommyk/projects/dev-env --archive`. This sandbox cannot prove that command.

**You see.**

- [ ] dest-env live swarm THEN contains sequential `frame`, `fanout`, and `fanin`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `openspec validate audit-pstack-gascity-pack-contracts --type change --strict` before archive. Run it in dest-env after the copy and before `--archive`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.6` at the PR head, per the boot recipe.

- [ ] Lane 1. Copy change. Save `copy-change.png`. Pass when the dest-env change dir exists.
- [ ] Lane 2. Strict validate. Save `strict-validate.png`. Pass when stdout contains `is valid`.
- [ ] Lane 3. Archive. Save `archive.png`. Pass when archive path exists under `openspec/changes/archive/`.
- [ ] Lane 4. Swarm THEN. Save `swarm-then.png`. Pass when live spec has sequential `frame`.
- [ ] Lane 5. Old THEN gone. Save `old-then-gone.png`. Pass when live spec lacks `fans out through Gas City graph steps`.
- [ ] Lane 6. Optional packs. Save `optional-packs.png`. Pass when live spec names `compound-engineering`.
- [ ] Lane 7. Selector AND. Save `selector-and.png`. Pass when live spec names `pstack-planning` overrides.
- [ ] Lane 8. Requirement headings. Save `headings.png`. Pass when live `pstack-gascity-pack` still has ten requirement headings.
- [ ] Lane 9. Refresh untouched. Save `refresh-untouched.png`. Pass when `refresh-pstack-pack-source-and-formula-requirements` is still an active change.
- [ ] Lane 10. TRACEABILITY pointer. Save `trace-pointer.png`. Pass when pack TRACEABILITY still names `dev-env/openspec/specs/pstack-gascity-pack/spec.md`.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. `openspec archive` wall time.
- [ ] Probe. `time openspec archive audit-pstack-gascity-pack-contracts -y` after a dry validate.
- [ ] Baseline. Record the clone-archive seconds first.
- [ ] Rule. Host archive may not exceed the clone time by more than 10 seconds.

**Review gate.** None. dest-env-archive is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends the PR to the Graphite stack and the operator lands it.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

Dest-env write from this sandbox failed with Permission denied on `openspec/changes/audit-pstack-gascity-pack-contracts`. A writable clone at `.work/dev-env` archived an older payload. This pack does not ship the change payload. Host write stays unproven.

## Appendix B. Alternatives rejected

Copy `contract = "graph.v2"` from sibling packs. Rejected because pstack tests forbid it and dest-env doctor treats it as `formula-requirements`.

Archive `refresh-pstack-pack-source-and-formula-requirements` as written. Rejected because live specs were hand-synced and naive archive collides.

Add extra planning-base steps for principle and subtract. Rejected because the shared wrapper test requires planning step ids to match `planning-base`.

## Appendix C. Risks

pack-honesty. Working tree is already dirty on `main`. Owner must branch before commit.

dest-env-archive. Bubblewrap cannot write dest-env. The owner must run the apply script on a host shell.

## Appendix D. Links and reading list

`pstack/scripts/apply_intent_change.py`. `dev-env/docs/openspec-intent-driven.md`. How skill for pack layout. Interrogate skill is not required. Trail is `.audit/pstack-gascity-audit.tsv`. Dest-env archive remains host-only and unproven.
