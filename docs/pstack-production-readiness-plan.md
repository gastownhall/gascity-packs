# PStack production readiness plan

A city operator must import and sling before gastownhall `main` carries pstack. Arena and interrogate both said dogfood this checkout first. This plan is the task graph. Catalog honesty-docs commit on PR 385 first. Host dest-env and host sling next. `pr-pstack-restamp` is the only new GitHub unit.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `skills/poteto-mode/playbooks/autopilot-stack.md`. The operator lands `pr-pstack-restamp` on existing PR 385 after host dogfood receipts. Dest-env `--archive` is her host click.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on her explicit go.
- [ ] On her go, persist the plan path on disk with this exact text. "docs/pstack-production-readiness-plan.md. PR ids pr-pstack-restamp. Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. The operator lands 385 after restamp. Done when honesty-docs is committed on 385, a host city slings pstack-poteto-mode and pstack-build, dest-env is archived, and 0.1.0 is restamped on that SHA."
- [ ] Read these from trunk at program start. Re-read them at every tick.
  - [ ] `git show origin/main:.github/workflows/ci.yml`
  - [ ] `git show origin/main:registry.toml`
  - [ ] `git show origin/main:pstack/pack.toml`
  - [ ] `git show origin/main:skills/poteto-mode/playbooks/autopilot-stack.md`
  - [ ] `git show origin/main:skills/swarm/SKILL.md`
  - [ ] `git show origin/main:skills/poteto-mode/playbooks/opening-a-pr.md`
  - [ ] `git show origin/main:skills/how/SKILL.md`
- [ ] Arm the 30-minute audit tick with `scheduler_create` (`interval: "30m"`, `fire_immediately: true`) and `monitor` for event wakes. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from trunk and the persisted plan. Audit the operation against both and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then send the operator a status message, whether or not anything changed, with the queue table of PR, owner, state, and head SHA, the verdicts since the last tick, what merged, open operator gates, and blockers."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] From this parent session, spawn one owner per PR with `spawn_subagent` (`isolation: "worktree"`). Depth is 1. Owners do not spawn.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] Catalog honesty-docs commit on `feat/pstack-pack-honesty` first. Not a GitHub PR id.
  - [ ] Host dest-env apply and archive second. Not a GitHub PR. This TUI cannot write dest-env `openspec/`.
  - [ ] Host dogfood city import and sling third. Not a GitHub PR.
  - [ ] `pr-pstack-restamp` after both host receipts. Branch from `feat/pstack-pack-honesty`.
- [ ] Hold the file boundaries. `pr-pstack-restamp` touches only `registry.toml`.
- [ ] Hold the review gate. `pr-pstack-restamp` changes no interaction. It is not review-gated.

### PR mechanics, for every PR

- [ ] Open the PR ready, never draft, with `gh pr create` and `draft: false`, or with Graphite `gt` for a stack.
- [ ] Run the repo's lint and typecheck once before the PR-facing push. Push with hooks on.
- [ ] Run `/unslop` before each commit and `/no-comments` before review.
- [ ] Triage every Bugbot and security-reviewer comment per `../references/bugbot-triage.md`.
- [ ] Rebase onto current trunk before babysit and again before the merge-ready report.

### Verdict and merge, for every PR

- [ ] At the merge-ready head SHA, run the swarm per `skills/swarm/SKILL.md`. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. One audit lane that reads the diff and the receipts and distrusts the PR body.
- [ ] Clean only when every lane is `PASS`. Findings go back to the owner. A new head gets a fresh swarm and a fresh verdict.
- [ ] The root appends the PR to the Graphite stack. The operator lands it. No owner merges.

### Boot recipe, for every live lane

Each live lane runs in its own `isolation: "worktree"` child at the PR head. Drive the real surface (running app, CLI, tests, or Grok browser tools).

- [ ] `git fetch origin <head-branch> && git checkout <head SHA>`.
- [ ] Stay in the worktree. Do not start a city unless the lane names `gc`.
- [ ] Run the named command. Capture stdout.
- [ ] Save every screenshot to `/tmp/swarm-pr-pstack-restamp/worker-<n>/<slug>.png` and return the paths with the report.

## Restamp 0.1.0 after dogfood (pr-pstack-restamp)

**Depends on.** Honesty-docs commit on PR 385. Host dest-env archive receipt. Host sling receipt for `pstack-poteto-mode` and `pstack-build`.

**Files.**

- [ ] Edit `registry.toml`.

**Build.**

- [ ] Set `[[pack]] name = "pstack"` release `0.1.0` `commit` to the SHA that contains the dogfood receipts and the honesty-docs commit.
- [ ] Set `hash` to `python3 -c` `validate_registry.git_pack_content_hash` for `pstack` at that SHA.
- [ ] Run `python3 validate_registry.py`.

**You see.**

- [ ] `python3 validate_registry.py` prints `registry.toml: ok`.
- [ ] The pstack `commit` is an ancestor of `feat/pstack-pack-honesty` HEAD.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_validate_registry.py`. Run `PYTHONPATH=. uv run --with pytest --with pyyaml pytest -q tests/test_validate_registry.py`.
- [ ] `pstack/tests/test_pstack_pack.py`. Run `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.6` at the PR head, per the boot recipe.

- [ ] Lane 1. Show registry pstack commit. Save `pin-commit.png`. Pass when the SHA exists on the branch.
- [ ] Lane 2. Hash the pstack tree at that SHA. Save `pin-hash.png`. Pass when it matches `registry.toml`.
- [ ] Lane 3. Confirm `pstack/intent/` is absent. Save `no-intent.png`. Pass when the directory does not exist.
- [ ] Lane 4. Run schema inventory. Save `schemas.png`. Pass when the CLI prints `ok route.v1.yaml`.
- [ ] Lane 5. Load `pstack-poteto-mode`. Save `router.png`. Pass when classify has no `gc.graph_operator`.
- [ ] Lane 6. Parse `playbooks.toml`. Save `map.png`. Pass when `feature` maps to `pstack-feature` and `arena` is absent.
- [ ] Lane 7. Confirm catalog strings for swarm. Save `catalog-swarm.png`. Pass when the text does not claim Gas City expands `gc.graph_operator`.
- [ ] Lane 8. Run the pack suite. Save `pack-suite.png`. Pass when pytest exit is 0.
- [ ] Lane 9. Run derived-pack compatibility. Save `derived.png`. Pass when pytest exit is 0.
- [ ] Lane 10. Confirm dest-env archive receipt path exists. Save `dest-receipt.png`. Pass when the host log names `openspec archive` for this change only.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Wall time of `pytest -q pstack/tests/test_pstack_pack.py`.
- [ ] Probe. The same pytest command at `feat/pstack-pack-honesty` before the restamp, then at the restamp head. Interleave three runs each.
- [ ] Baseline. Record the pre-restamp median first.
- [ ] Rule. Head median must stay under 2x the baseline. Fail at 2x or more.

**Review gate.** None. `pr-pstack-restamp` is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends the commit onto PR 385. The operator lands 385.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

Dest-env copy from this sandbox is unproven. This TUI cannot write dest-env `openspec/`.

`apply_intent_change.py --validate-only --spec-root` against a readable OpenSpec tree printed that the change is valid.

This pack does not keep a dest-env checkout.

`gc import add` against gastownhall `main` is unproven. `pstack/` is absent on `origin/main`.

Host sling of `pstack-poteto-mode` and `pstack-build` is unproven. Pack tests do not sling.

Auto-sling remains unproven. No Gas City `graph_operator` consumer.

Honesty-docs README local clone is in the working tree until committed on 385.

## Appendix B. Alternatives rejected

Ship 0.1.0 on gastownhall `main` now. Lost because the README URL 404s and no city has slung.

Ship then dogfood. Lost because strangers would be the first live importers.

Restamp 0.1.0 again without a sling receipt. Lost because that is pin theater.

Add pydantic. Lost because Gas City `validate_schema_definition` is the producer-gate definition.

Copy `contract = "graph.v2"`. Lost because pack tests forbid it.

## Appendix C. Risks

`git show origin/main:pstack/pack.toml` fails until 385 lands. Use the feature branch for pstack files.

`git show origin/main:skills/poteto-mode/playbooks/autopilot-stack.md` fails on this repository. Use `~/.grok/installed-plugins/pstack-6ff43f58/skills/poteto-mode/playbooks/autopilot-stack.md`.

Nightly smokes on `main` are already red for sibling packs. A pstack smoke row will join a red canary.

This harness has no `pstack-models.toml`. Multi-provider verify cannot run here.

The pack copy of `check-plan.mjs` (Cursor pin `6fecddba`) still wants `/goal` and `grok-4.6-fast-xhigh`. Lint this plan with the plugin checker at `~/.grok/installed-plugins/pstack-6ff43f58/skills/poteto-mode/scripts/check-plan.mjs`.

## Appendix D. Links and reading list

`docs/pstack-poteto-mode-router-plan.md` is a finished-router note. `docs/pstack-gascity-pack-apply-plan.md` is dest-env host how-to. `pstack/ARCHITECTURE.md`. `pstack/TRACEABILITY.md`. `.work/openspec-changes/audit-pstack-gascity-pack-contracts/`. `pstack/scripts/apply_intent_change.py`. Trail `.audit/pstack-gascity-audit.tsv`. Use `skills/how/SKILL.md` and `skills/interrogate/SKILL.md` on `pr-pstack-restamp`.
