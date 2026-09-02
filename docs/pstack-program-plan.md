# PStack program plan

A city operator needs pstack as a sequential Gas City factory today and N-model arena later without pack Task spawn. This program lands isolation and OpenSpec on PR 385, dogfoods a host city, restamps 0.1.0 after sling receipts, then stamps formulas only after Gas City consumes `gc.provider_panel`. The live graph is this file. Isolation and OpenSpec are on PR 385. Host sling and registry restamp remain.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `skills/poteto-mode/playbooks/autopilot-stack.md`. The operator lands `pr-pstack-land-honesty` then later `pr-pstack-panel-stamp`. Owners do not merge.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on her explicit go.
- [ ] On her go, persist the plan path on disk with this exact text. "docs/pstack-program-plan.md. PR ids pr-pstack-land-honesty then pr-pstack-panel-stamp. Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. The operator lands the stack. Done when PR 385 has isolation plus this plan, a host city slings pstack-poteto-mode and pstack-build, 0.1.0 is restamped after those receipts, and formulas still omit gc.provider_panel until the compiler consumer exists."
- [ ] Read these from trunk at program start. Re-read them at every tick.
  - [ ] `git show origin/main:.github/workflows/ci.yml`
  - [ ] `git show origin/main:registry.toml`
  - [ ] `git show origin/main:README.md`
  - [ ] `git show origin/main:gascity/pack.toml`
  - [ ] `git show origin/main:bmad/pack.toml`
  - [ ] `git show origin/main:gascity/REQUIREMENTS.md`
  - [ ] `git show origin/main:validate_registry.py`
- [ ] Arm the 30-minute audit tick with `scheduler_create` (`interval: "30m"`, `fire_immediately: true`) and `monitor` for event wakes. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read docs/pstack-program-plan.md. The execution playbook is the host plugin skills/poteto-mode/playbooks/autopilot-stack.md, not a path on this origin/main. Audit the operation against both and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then send the operator a status message, whether or not anything changed, with the queue table of PR, owner, state, and head SHA, the verdicts since the last tick, what merged, open operator gates, and blockers."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] From this parent session, spawn one owner per PR with `spawn_subagent` (`isolation: "worktree"`). Depth is 1. Owners do not spawn.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] `pr-pstack-land-honesty` first. Existing PR 385. Branch `feat/pstack-pack-honesty`.
  - [ ] Host sling of `pstack-poteto-mode` and `pstack-build` after `pr-pstack-land-honesty` is on 385. Not a GitHub PR.
  - [ ] Restamp `registry.toml` 0.1.0 on the same PR after sling receipts.
  - [ ] Gas City compiler consumer for `gc.provider_panel`. Outside this packs formula tree.
  - [ ] `pr-pstack-panel-stamp` after that consumer exists.
- [ ] Hold the file boundaries. `pr-pstack-land-honesty` must not touch `pstack/formulas`, `pstack/schemas`, or `registry.toml` until the restamp box. `pr-pstack-panel-stamp` touches formulas, schemas, and tests.
- [ ] Hold the review gate. `pr-pstack-land-honesty` changes no interaction. It is not review-gated. `pr-pstack-panel-stamp` changes sling behavior. It is review-gated.

### PR mechanics, for every PR

- [ ] Open the PR ready, never draft, with `gh pr create` and `draft: false`, or with Graphite `gt` for a stack.
- [ ] Run the repo's lint and typecheck once before the PR-facing push. Push with hooks on.
- [ ] Run `/unslop` before each commit and `/no-comments` before review.
- [ ] Triage every Bugbot and security-reviewer comment per `../references/bugbot-triage.md`.
- [ ] Rebase onto current trunk before babysit and again before the merge-ready report.

### Verdict and merge, for every PR

- [ ] At the merge-ready head SHA, run the swarm per `skills/swarm/SKILL.md`. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. One audit lane that reads the diff and the receipts and distrusts the PR body.
- [ ] Clean only when every lane is `PASS`. Findings go back to the owner. A new head gets a fresh swarm and a fresh verdict.
- [ ] Root appends the PR to the Graphite stack. The operator lands it. Owners do not merge.

### Boot recipe, for every live lane

Each live lane runs in its own `isolation: "worktree"` child at the PR head. Drive the real surface (running app, CLI, tests, or Grok browser tools).

- [ ] `git fetch origin <head-branch> && git checkout <head SHA>`.
- [ ] Use the repo CLI. `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py`. `python pstack/scripts/apply_intent_change.py --source openspec/changes/archive/2026-09-02-pstack-program-arm-list --validate-only`.
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report.

## Land isolation and OpenSpec (`pr-pstack-land-honesty`)

**Depends on.** None.

**Files.**

- [ ] Edit `pstack/DESIGN.md`.
- [ ] Edit `pstack/ARCHITECTURE.md`.
- [ ] Edit `pstack/REQUIREMENTS.md`.
- [ ] Edit `pstack/TRACEABILITY.md`.
- [ ] Edit `pstack/README.md`.
- [ ] Edit `pstack/scripts/apply_intent_change.py`.
- [ ] Edit `pstack/tests/test_pstack_pack.py`.
- [ ] Keep `openspec/specs/` as durable Gherkin.
- [ ] Create `docs/pstack-program-plan.md`.
- [ ] Point `docs/pstack-production-readiness-plan.md` at this file.
- [ ] Point `docs/pstack-provider-panel-plan.md` at this file.
- [ ] Point `docs/pstack-gascity-pack-apply-plan.md` at this file.
- [ ] Point `docs/pstack-poteto-mode-router-plan.md` at this file.
- [ ] Keep `openspec/` in the land commit.

**Build.**

- [x] Commit isolation, filled panel Purpose, `openspec/` including archived `pstack-gherkin-restamp`, and this plan onto PR 385 at `2f65f7b`. Do not stamp `gc.provider_panel`. Do not restamp `registry.toml` in this box.

**You see.**

- [ ] `rg gc.provider_panel pstack/formulas` prints nothing. `pytest -q pstack/tests/test_pstack_pack.py` prints `45 passed`. `openspec/specs/gascity-provider-panel/spec.md` has no TBD.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `pstack/tests/test_pstack_pack.py` locks spec files and isolation. Run `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.6` at the PR head, per the boot recipe.

- [ ] Lane 1. Read DESIGN Provider panel fanout. Save `design-panel.png`. Pass when the section names `[[provider_panels]]` and forbids stamping before a consumer.
- [ ] Lane 2. Grep formulas for `gc.provider_panel`. Save `no-stamp.png`. Pass when the grep is empty.
- [ ] Lane 3. Run pack tests. Save `pytest.png`. Pass when the log shows 45 passed.
- [ ] Lane 4. Read `openspec/specs/gascity-provider-panel/spec.md`. Save `panel-purpose.png`. Pass when Purpose is not TBD.
- [ ] Lane 5. Grep TRACEABILITY for another project checkout. Save `no-foreign-openspec.png`. Pass when the grep is empty.
- [ ] Lane 6. Confirm this plan has no gitignored payload path. Save `plan-clean.png`. Pass when no gitignored OpenSpec payload path appears.
- [ ] Lane 7. Confirm old plan files point here. Save `pointers.png`. Pass when each old H1 file names `docs/pstack-program-plan.md`.
- [ ] Lane 8. Read `openspec/specs/pstack-gascity-pack/spec.md` vendor rule. Save `gherkin-owner.png`. Pass when durable Gherkin is this repository `openspec/`.
- [ ] Lane 9. Confirm `pstack-arena.formula.toml` catalog is sequential. Save `arena-catalog.png`. Pass when the catalog line names sequential steps.
- [ ] Lane 10. Confirm `gascity/` has zero `graph_operator` hits. Save `no-consumer.png`. Pass when that grep is empty.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Wall time of `pstack/tests/test_pstack_pack.py`.
- [ ] Probe. `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py` at trunk then at the head, interleaved.
- [ ] Baseline. Record the trunk seconds first.
- [ ] Rule. Head fails if it is more than twice the trunk seconds.

**Review gate.** None. `pr-pstack-land-honesty` is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends the PR to the Graphite stack and the operator lands it.

## Stamp panel keys after the consumer (`pr-pstack-panel-stamp`)

**Depends on.** `pr-pstack-land-honesty`. Gas City compiler consumer for `gc.provider_panel`.

**Files.**

- [ ] Edit `pstack/formulas/pstack-arena.formula.toml`.
- [ ] Edit `pstack/formulas/pstack-interrogate.formula.toml`.
- [ ] Edit `pstack/schemas/arena-candidate.v1.yaml` or add per-child path bindings.
- [ ] Edit `pstack/tests/test_pstack_pack.py`.

**Build.**

- [ ] Stamp `gc.provider_panel` and `{child_id}` paths only after Gas City documents a compiler consumer. Delete the shared `.gc/pstack/arena-candidate.md` binding in the same wave.

**You see.**

- [ ] `gc sling ... --on pstack-arena` in a city with a three-member panel writes three candidate files under `.gc/pstack/arena/`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Replace graph_operator freeze tests for arena and interrogate with panel-stamp tests. Run `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.6` at the PR head, per the boot recipe.

- [ ] Lane 1. City with a three-member `pstack-arena` panel. Save `arena-n3.png`. Pass when three candidate files exist.
- [ ] Lane 2. City with no panel. Save `arena-fallback.png`. Pass when the sling stays one candidate bead.
- [ ] Lane 3. City with the session provider in members. Save `session-reject.png`. Pass when cook fails closed.
- [ ] Lane 4. Interrogate with two members. Save `interrogate-n2.png`. Pass when two review files exist and judgment has a path gate.
- [ ] Lane 5. Confirm no apply-findings child on interrogate. Save `no-apply.png`. Pass when the cooked graph has no apply node.
- [ ] Lane 6. Confirm pack TOML has no provider id strings. Save `no-provider-ids.png`. Pass when grep of formulas for `cursor-grok` is empty.
- [ ] Lane 7. Confirm isolated paths. Save `isolated.png`. Pass when two children do not share `arena-candidate.md`.
- [ ] Lane 8. Judge after candidates. Save `judge-order.png`. Pass when synthesis `needs` the child ids.
- [ ] Lane 9. Disposable city import lists `pstack-arena`. Save `formula-list.png`. Pass when `gc formula list` names it.
- [ ] Lane 10. Dual corpus. Save `skill-vs-asset.png`. Pass when formula `description_file` still wins over `pstack/skills/arena/SKILL.md`.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Cook time for `pstack-arena` with four panel members versus sequential fallback.
- [ ] Probe. `gc formula show pstack-arena` at trunk then at the head.
- [ ] Baseline. Record the sequential cook time first.
- [ ] Rule. Head fails if four-member cook is more than ten times sequential cook without an accepted cost note in DESIGN.md.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1 screenshots into `<media path>/pr-pstack-panel-stamp-review-arena-n3.png`.
- [ ] Record a 30 to 60 second video of the sling on the worktree child's real surface. Save it as `<media path>/pr-pstack-panel-stamp-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends the PR to the Graphite stack and the operator lands it.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

Explorer 01 proved production and panel plans still sequenced a foreign OpenSpec checkout while isolation already lived in the working tree. Isolation is now on PR 385 tip `2f65f7b`. Arena candidate 1 is one master plan. Candidate 2 is an index plus three files. Live sling of a panel remains unproven. `GC_TEST_BIN` unset.

## Appendix B. Alternatives rejected

Three stacked plans plus an index. Extra files for the same DAG. Lost.

A foreign OpenSpec archive node. This repository owns Gherkin. Lost.

A third GitHub PR for restamp. TRACEABILITY wants restamp on the same isolation head after sling receipts. Nested under 385.

## Appendix C. Risks

`origin/main` still lacks `pstack/`. Arm boxes read files that exist on trunk today. Watch pstack landing in `pr-pstack-land-honesty`.

Gas City compiler is outside this packs tree. `pr-pstack-panel-stamp` must not start on Gherkin alone.

Dual corpus. `pstack/skills/arena/SKILL.md` still documents Cursor Task. Watch that in stamp lane 10.

## Appendix D. Links and reading list

`pstack/DESIGN.md` Provider panel fanout. `openspec/specs/gascity-provider-panel/spec.md`. `openspec/specs/pstack-gascity-pack/spec.md`. `pstack/scripts/apply_intent_change.py`. Use `skills/how/SKILL.md` and `skills/interrogate/SKILL.md` on `pr-pstack-panel-stamp`.
