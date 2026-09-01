# PStack poteto-mode router plan

A city operator slings one formula instead of guessing among twenty playbook names. The pack classifies the request into an existing formula. It does not run Cursor Task. It does not auto-sling. `pr-pstack-router` is the only GitHub PR. Dest-env archive stays a host item.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `skills/poteto-mode/playbooks/autopilot-stack.md`. The operator lands `pr-pstack-router`. Dest-env `--archive` is her host click, not a GitHub merge.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on her explicit go.
- [ ] On her go, persist the plan path on disk with this exact text. "docs/pstack-poteto-mode-router-plan.md. PR ids pr-pstack-router. Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. The operator lands. Done when pstack-poteto-mode writes pstack.route.v1 and pack tests pass."
- [ ] Read these from trunk at program start. Re-read them at every tick.
  - [ ] `git show origin/main:.github/workflows/ci.yml`
  - [ ] `git show origin/main:pstack/pack.toml`
  - [ ] `git show origin/main:gascity/tests/test_derived_pack_compatibility.py`
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
  - [ ] `pr-pstack-router` is first. Branch from `feat/pstack-pack-honesty`.
- [ ] Hold the file boundaries. `pr-pstack-router` touches only `pstack/**` plus `docs/pstack-poteto-mode-router-plan.md`.
- [ ] Hold the review gate. `pr-pstack-router` changes no interaction. It is not review-gated.

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
- [ ] Run the pytest command in that lane. Capture stdout.
- [ ] Save every screenshot to `/tmp/swarm-pr-pstack-router/worker-<n>/<slug>.png` and return the paths with the report.

## Encode the router table and formula (pr-pstack-router)

**Depends on.** None.

**Files.**

- [ ] Create `pstack/mappings/playbooks.toml`.
- [ ] Create `pstack/schemas/route.v1.yaml`.
- [ ] Create `pstack/formulas/pstack-poteto-mode.formula.toml`.
- [ ] Create `pstack/assets/workflows/pstack-methods/classify.md`.
- [ ] Edit `pstack/tests/test_pstack_pack.py`.
- [ ] Edit `pstack/ARCHITECTURE.md`.
- [ ] Edit `pstack/README.md`.

**Build.**

- [ ] Put the playbook map in `pstack/mappings/playbooks.toml` with keys `formula`, `class`, and `unsupported`. Mirror `CURSOR_PLAYBOOK_FORMULAS` and `CURSOR_PLAYBOOKS_UNSUPPORTED` from `pstack/tests/test_pstack_pack.py`.
- [ ] Add schema `pstack.route.v1` with required fields `status`, `playbook`, `formula`, `class`, and `reason`. Allowed status values are `routed` and `unsupported`.
- [ ] Add formula `pstack-poteto-mode` with steps `classify` then `write`. `classify` uses `pstack.coordinator`. `write` emits `pstack.route.v1` at `{{artifact_path}}`. Do not expand into the selected formula. Do not set `gc.graph_operator`.
- [ ] Load the TOML map from tests. Fail if the test dict and the TOML disagree.
- [ ] Document sling `pstack-poteto-mode` then sling the `formula` field. Name that this is not `/poteto-mode`.

**You see.**

- [ ] `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py` prints a passing `test_poteto_mode_router_table_matches_playbook_map`.
- [ ] A fixture route artifact with `status: unsupported` and `playbook: opening-a-pr` validates.
- [ ] A fixture with `formula: pstack-missing` fails validation.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `pstack/tests/test_pstack_pack.py::test_poteto_mode_router_table_matches_playbook_map`. Run `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py::test_poteto_mode_router_table_matches_playbook_map`.
- [ ] `pstack/tests/test_pstack_pack.py::test_route_schema_rejects_unknown_formula`. Run `uv run --with pytest --with pyyaml pytest -q pstack/tests/test_pstack_pack.py::test_route_schema_rejects_unknown_formula`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `grok-4.6` at the PR head, per the boot recipe.

- [ ] Lane 1. Load `pstack-poteto-mode` TOML. Save `load-formula.png`. Pass when `formula` equals `pstack-poteto-mode`.
- [ ] Lane 2. Parse `playbooks.toml`. Save `parse-map.png`. Pass when stem `feature` maps to `pstack-feature`.
- [ ] Lane 3. Parse `playbooks.toml` unsupported set. Save `unsupported.png`. Pass when `opening-a-pr` is listed.
- [ ] Lane 4. Validate a `routed` fixture for `bug-fix`. Save `route-bug-fix.png`. Pass when schema accepts it.
- [ ] Lane 5. Validate an `unsupported` fixture for `pause-safely`. Save `route-pause.png`. Pass when schema accepts it.
- [ ] Lane 6. Reject a fixture whose formula is not in the map. Save `reject-unknown.png`. Pass when validation fails.
- [ ] Lane 7. Confirm classify has no `gc.graph_operator`. Save `no-operator.png`. Pass when that key is absent.
- [ ] Lane 8. Run the full pack suite. Save `pack-suite.png`. Pass when pytest exit is 0.
- [ ] Lane 9. Run derived-pack compatibility. Save `derived.png`. Pass when pytest exit is 0.
- [ ] Lane 10. Confirm `pstack/intent/` is still absent. Save `no-intent.png`. Pass when the directory does not exist.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Wall time of `pytest -q pstack/tests/test_pstack_pack.py`.
- [ ] Probe. The same pytest command at `origin/main` if `pstack/tests` exists there, else at `feat/pstack-pack-honesty` before the PR, then at the PR head. Interleave three runs each.
- [ ] Baseline. Record the trunk or pre-PR median first.
- [ ] Rule. Head median must stay under 2x the baseline. Fail at 2x or more.

**Review gate.** None. `pr-pstack-router` is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends the PR to the Graphite stack and the operator lands it.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.
- [ ] On the host, after land, run `python pstack/scripts/apply_intent_change.py --source /home/tommyk/projects/gascity-packs/.work/openspec-changes/audit-pstack-gascity-pack-contracts --dest /home/tommyk/projects/dev-env --archive`.

## Appendix A. Prototype evidence

Auto-sling of the selected formula is unproven. This checkout has no Gas City consumer for `gc.graph_operator`. Classify-then-write is the chosen shape. No prototype branch. The existing map test at `pstack/tests/test_pstack_pack.py` already proves stem coverage.

## Appendix B. Alternatives rejected

A formula that expands into the selected playbook graph. Lost because expand of a whole factory is not a selector, and method clones are not those graphs.

A slash skill `/poteto-mode` inside the pack. Lost because Gas City entry is `gc sling`. The pack is not a Cursor plugin.

A dest-env-only router with no pack formula. Lost because the operator asked for a Gas City pack router.

Teaching `METHODOLOGY_FLOW_CONTRACTS` `graph.v2` to pstack in this PR. Lost because that is inference-gate work, not the router.

## Appendix C. Risks

`git show origin/main:skills/poteto-mode/playbooks/autopilot-stack.md` fails on this repository. Those files live in the pstack plugin, not gastownhall/gascity-packs. Watch the check-plan arm boxes and use the plugin path `~/.grok/installed-plugins/pstack-6ff43f58/skills/poteto-mode/playbooks/autopilot-stack.md` when trunk lacks them.

`pstack-poteto-mode` can over-promise if classify writes `routed` for a sequential shell. The route artifact `class` field must say `method-report` or `build-factory` so the operator sees the gap.

Dest-env write stays EACCES in this sandbox. Host `--archive` is the only apply.

## Appendix D. Links and reading list

`pstack/ARCHITECTURE.md`. `pstack/tests/test_pstack_pack.py`. `pstack/vendor/pstack/skills/poteto-mode/SKILL.md`. `pstack/scripts/apply_intent_change.py`. `docs/pstack-gascity-pack-apply-plan.md`. Use `skills/how/SKILL.md` and `skills/interrogate/SKILL.md` on `pr-pstack-router`. Trail `.audit/pstack-gascity-audit.tsv`.
