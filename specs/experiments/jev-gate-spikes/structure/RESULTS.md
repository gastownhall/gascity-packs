# Structure spike: gated review tail on Gas City 1.5 — September 24, 2026

A no-LLM spike of the formula mechanics a Jev-gated build formula needs. Every
agent was a one-shot shell script (`prompt_mode = "none"`); no Claude session
started. `events.jsonl` recorded `session.woke` only for `rig/jover.scripter-{1,2,3}`
and `rig/core.control-dispatcher`, and `bd.dog` plus both `claude` agents
stayed suspended.

- gc `1.5.0-dev+26172ff4b` (`~/.local/bin/gc`), bd 1.3.0.
- Isolated city in `/tmp/gcsp-7HiB`: `GC_HOME`, `XDG_RUNTIME_DIR`,
  `DOLT_ROOT_PATH` and `GIT_CONFIG_GLOBAL` all pointed inside it, `launchctl`
  and `systemctl` were shimmed to `exit 1`, and the supervisor used a private
  loopback port.
- Teardown: `gc stop --force`, then `gc supervisor stop --wait`, then two
  sweeps 25 s apart. No process whose command line held the dir survived.

| Q | Question | Verdict |
| --- | --- | --- |
| Q1 | Gated review tail in an `on_complete` bond keeps dependency order, drops excluded lanes cleanly, and the root closes only after publish | **Yes** |
| Q2 | Overlay pack `extends` a base-pack formula, replaces `review` by id with the gate, and removes the inherited finalize/publish | **Yes**, using a whole-step replacement with a condition that is always false. Nothing deletes a step directly |
| Q3 | Gate script reads upstream facts from the workflow root through `gc.root_bead_id` | **Yes** |

## Layout

| Path | What it is |
| --- | --- |
| `basepack/` | Pack `jbase`: `sbuild-base` (build-base lookalike, `internal = true`), `sbuild` (build-basic lookalike: `extends` plus a `review` that `expand`s `sbuild-review`), the `scripter` agent, `worker.sh`, and check scripts |
| `overlaypack/` | Pack `jover` (imports `jbase`): the bond `jev-review-tail`, Q1 formula `q1-gated`, Q2 formula `jev-build`, the control `jev-build-nodrop`, `jev-build-needs`, the check variants, and negative probes `zprobe-*` |
| `city/` | The `city.toml`, `pack.toml` and `.gc/site.toml` that ran |
| `harness/` | `env.sh` and `run-case.sh` (sling, wait for root close, dump the bead timeline) |
| `evidence/` | Per-run `*.beads.tsv` timelines, `*.evidence.json` (gate/synthesize metadata), `*.root-meta.json`, `formula-show.txt` (compiled graphs and errors), `check.log`, `worker.log` |

Absolute paths inside the TOML and scripts (`/tmp/gcsp-7HiB/...`) are the ones
that ran. Adjust them before reusing the files.

`worker.sh` claims with `gc hook --claim --drain-ack --json`, acts on the
bead's `spike.role`, stamps `spike.claimed_at` and `spike.done_at` in epoch
seconds (ms precision), then closes with `gc.outcome=pass`. Lanes sleep
2/5/3 s (acceptance/test-evidence/simplicity), so synthesize has to wait for
the slowest lane that exists.

## Q1: gated review tail (yes)

Graph (`overlaypack/formulas/q1-gated.toml` and `jev-review-tail.toml`):

```
implement -> gate (on_complete: for_each output.items, bond jev-review-tail)
             gate-fanout (control) -> workflow-finalize
bond per item: acceptance?  test-evidence?  simplicity?   (condition "{{x}} == run")
               -> synthesize (needs all three) -> apply -> finalize -> publish
```

The gate script wrote `gc.output_json = {"items":[{"acceptance":…,"test_evidence":…,"simplicity":…}]}`.

Times are UTC (bd times are whole seconds). "claim" and "done" are the
worker's own stamps, mod 1000 s.

**All lanes run** (`evidence/q1-all.beads.tsv`):

| Bead | closed | claim → done |
| --- | --- | --- |
| gate | 21:04:39 | 877.46 → 878.31 |
| bond acceptance / simplicity / test-evidence | 21:04:46 / :54 / 21:05:06 | done 886.18 / 893.32 / 905.64 |
| synthesize | 21:05:22 | **claimed 920.93**, after the last lane at 905.64; `lanes_at_claim` = all 3 closed |
| apply → finalize → publish | 21:05:29 → :34 → :40 | strictly sequential |
| gate-fanout | 21:05:43 | |
| **root** | **21:05:47**, outcome pass | |
| workflow-finalize | 21:05:50 | |

**Only simplicity runs** (`q1-simplicity`): the bond created 5 beads. No
acceptance or test-evidence bead exists. Synthesize was claimed at 035.18,
after simplicity finished at 027.26, with `lanes_at_claim` = [simplicity:
closed]. Publish closed at 21:08:09, the fanout at 21:08:12, the root at
21:08:16 (pass).

**No lanes run** (`q1-none`): the bond created synthesize → apply → finalize →
publish only, and `lanes_at_claim` = `[]`. The excluded lanes' edges vanished
and nothing deadlocked. Publish closed at 21:09:50, the root at 21:09:56 (pass).

Why the root waits: at spawn, the dispatcher adds a `blocks` edge from the
`<step>-fanout` control to every sink of each bond instance
(`internal/dispatch/fanout.go`). The control closes only when those sinks
close. `workflow-finalize` needs the fanout control. A live `gc bd show rig-jq8`
(the q1-none gate-fanout) listed a `blocks` dependency on `rig-dn4`, the bond
publish bead.

The Q2 runs produced the same ordering (below), plus two extra checks:

- **A `check` loop inside the bond works.** `jev-review-tail-checked-q` puts a
  flaky exec check on bond finalize, with `max_attempts = 3`.
  `finalize.iteration.1` closed, the check failed on purpose, and
  `iteration.2` ran and passed. The ralph control closed pass, and only then
  did publish run (`evidence/q1-checked-q.beads.tsv`, `check.log`). This
  requires a binding-qualified `gc.run_target`; see gotcha 1.
- **Lanes do run in parallel.** In `q2-jev-build-all` the three lanes were
  claimed within 1 s of each other (294.7 / 295.3 / 295.7). In the first run
  (`q1-all`) the one-shot pool was still warming up and serialized them.

## Q2: overlay `extends` with the review stage replaced (yes, with a workaround)

The shape copies the real pack. `jbase/sbuild-base` is like `build-base`.
`jbase/sbuild` extends it and replaces `review` with an `expand` step, like
`build-basic`. `jover/jev-build` sits in a separate pack whose `pack.toml`
imports `jbase`; the city imports only `jover`.

The TOML that works (`overlaypack/formulas/jev-build.toml`):

```toml
formula = "jev-build"
version = 1
extends = ["sbuild"]

[requires]
formula_compiler = ">=2.0.0"

[vars]
[vars.keep_inherited_tail]
description = "Leave empty. A falsy value drops the inherited finalize/publish steps; the bond owns them."
default = ""

# Replace the inherited review stage (by id) with the gate producer.
[[steps]]
id = "review"
title = "Review gate"
needs = ["summarize-implementation"]
metadata = { "gc.run_target" = "scripter", "spike.role" = "gate" }

[steps.on_complete]
for_each = "output.items"
bond = "jev-review-tail"
vars = { acceptance = "{item.acceptance}", test_evidence = "{item.test_evidence}", simplicity = "{item.simplicity}" }

# "Delete" inherited finalize/publish: whole-step replace + a condition that is always false.
[[steps]]
id = "finalize"
title = "Finalize (dropped by jev-build)"
condition = "{{keep_inherited_tail}}"

[[steps]]
id = "publish"
title = "Publish (dropped by jev-build)"
condition = "{{keep_inherited_tail}}"
```

Compiled graph (`evidence/formula-show.txt`): prepare → implement →
summarize-implementation → review → review-fanout → workflow-finalize. The
inherited `expand = "sbuild-review"` is gone.

Runs:

- `q2-jev-build-all`: the gate closed at 21:11:18. The bond lanes closed at
  :38/:40/:41, synthesize at :52 (claimed 310.48, after the last lane at
  300.80), then apply, finalize at 21:12:12, publish at :18. The fanout closed
  at :18 and the root at 21:12:22 (pass).
- `q2-jev-build-testonly`: only the test-evidence lane was created. Synthesize
  ran after it, and the root closed after publish.
- **Control `q2-nodrop-control`** (review replaced, inherited tail kept): the
  inherited `finalize` closed at 21:14:51 and `publish` at 21:15:02. That is
  **before** any bond lane finished (first lane 21:15:04, bond publish
  21:15:53). This is why the inherited tail must be dropped.

What works and what does not:

| Attempt | Result |
| --- | --- |
| Replace an inherited step by id | Works. The replacement is whole-step (`mergeSteps`): no field merge, and the parent's position is kept. Inherited `expand`, `check`, `metadata` and `description_file` all vanish unless restated |
| Replaced step changes its `needs` | Works (`jev-build-needs`: `review` needs `implement`). The bypassed `summarize-implementation` becomes a dangling sink that `workflow-finalize` also waits on. The pack's own `build-from-*-base` chain uses the same idiom: children replace an entry step to prepend stages |
| Add `on_complete` to a replaced step | Works. `<id>-fanout` is injected |
| Delete an inherited step outright | **No syntax exists.** Workaround: replace it by id with `condition = "{{some_falsy_var}}"`. Conditions are filtered after `extends` and inline expansion, so the step and its edges are removed. The var can be undeclared (`{{never}}` compiled), but declaring it documents the intent |
| Replacement with only `id` + `condition` | Fails: `steps[5] (publish): title is required (unless using expand)` |
| Literal condition `condition = "false"` | Fails: `invalid step condition format: "false" (expected {{var}} or {{var}} == value)` |
| Drop only the middle step (`finalize`), keep `publish` | Compiles, but `publish` loses its only edge and becomes a root step that runs immediately (`zprobe-drop-middle`). Dependents are not rewired. Drop the whole downstream tail, or restate the dependents |
| Keep the inherited tail and gate it on the bond with `needs = ["review-fanout"]` | Fails: `needs references unknown step "review-fanout"`. The control is injected after validation |
| Keep the inherited tail with `waits_for = "children-of(review)"` | Compiles, but does not block (prior probe; spec §4 says `waits_for` modes have no runtime consumer) |
| Cross-pack `extends` through a nested import | Works. The overlay sees `jbase` formulas by name, and `sbuild`'s own `extends sbuild-base` resolves |

## Q3: the gate reads upstream facts from the root (yes)

The `implement` script ran `gc bd update <gc.root_bead_id> --set-metadata
spike.impl_summary=… --set-metadata spike.review_plan=<json>` on the
in-progress workflow root. The gate script read `gc.root_bead_id` from its own
bead, ran `gc bd show <root> --json`, and built its `gc.output_json` from
`spike.review_plan`. It echoed what it saw into its own metadata. In
`evidence/*.evidence.json`, every run shows `saw_root_summary =
"implemented-by-<implement bead id>"` and `saw_root_plan` equal to the plan
passed to the sling. Each Q1 case chose its lanes through that path (root
metadata → gate → items → bond conditions).

Bond beads also carry `gc.root_bead_id` (the same root) and `gc.step_id` (the
source step, e.g. `q1-gated.gate`), so lanes, synthesize and finalize can read
the same root facts. Exec check scripts get `GC_BEAD_ID`, `GC_MOLECULE_DIR`
(`…/.gc/molecules/<root>`) and `GC_ARTIFACT_DIR`, but not
`GC_ROOT_BEAD_ID` (`evidence/check.log` and the env dump).

## Recommended shape for the real gated build formula

```
jev-build  (overlay pack; extends = ["build-basic"])
  prepare -> requirements -> plan -> plan-review -> decompose
  -> implement | implement-same-session -> summarize-implementation      (inherited)
  review      REPLACED: deterministic Jev gate step
              needs = ["summarize-implementation"]
              reads root/upstream metadata, writes gc.output_json =
                {"items":[{"acceptance":"run|skip","test_evidence":"run|skip","simplicity":"run|skip", ...}]}
              on_complete = { for_each = "output.items", bond = "jev-review-tail", vars = {...} }
  finalize    REPLACED + condition = "{{keep_inherited_tail}}"   (dropped)
  publish     REPLACED + condition = "{{keep_inherited_tail}}"   (dropped)

jev-review-tail  (type = "expansion")
  {target}.acceptance-review     condition "{{acceptance}} == run"
  {target}.test-evidence-review  condition "{{test_evidence}} == run"
  {target}.simplicity-review     condition "{{simplicity}} == run"
  {target}.synthesize-review     needs all three lanes
  {target}.apply-review-findings needs synthesize
  {target}.finalize              needs apply   (+ [template.check] build-artifact-valid)
  {target}.publish               needs finalize
```

Rules for that shape:

- The gate must always emit **exactly one** item. `items: []` closes the
  fanout pass with no bond, which skips finalize and publish while the
  workflow still passes. "Skip all lanes" means one item with every field
  `skip`.
- The replaced `review` loses build-basic's `gc.build.artifact_schema`,
  `artifact_path_keys` and the review-report artifact. A bond step
  (synthesize, or a review-final step) has to produce `gc.build.review.v1`.
  Finalize and publish in the bond have to restate the inherited metadata and
  checks, because nothing is inherited into a bond.
- Use role-alias targets (`gc.run-operator` and similar) or other
  binding-qualified targets in the bond, never bare agent names (gotcha 1).
- Build-basic's review loop is a `[template.check]` whose template also has
  `[[template.children]]`, rerunning lanes until approved. This spike ran only a
  plain `check` inside a bond; the check-with-children loop inside a runtime
  bond was tested later and works, including gated children and a dropped loop
  ([loop spike](../../jev-overlay-build/README.md#the-check-with-children-loop-inside-a-bond-loop-spike)).

## Gotchas and errors hit

1. **A bare `gc.run_target` strands check retries.** With `gc.run_target =
   "scripter"`, first dispatch resolves to `rig/jover.scripter`. The check's
   `iteration.2` was minted with `gc.routed_to = "scripter"`, no worker ever
   claimed it, and the workflow hung. This happened on a top-level step
   (`q1-gated-checked-q.implement`) and inside a bond (`q1-gated-checked`).
   Cause: `qualifyBareTargetWithRigPrefix` only tries `rig/<target>`, and
   `rig/scripter` is not an agent. Fix: `gc.run_target = "jover.scripter"`
   (binding-qualified). The bond finalize iteration 2 then routed to
   `rig/jover.scripter` and passed. The two stuck runs were released by hand
   with `gc bd update <iteration.2> --set-metadata
   gc.routed_to=rig/jover.scripter`. Real gascity targets (`gc.<role>`) are
   already qualified, so this is a spike or author pitfall, not a confirmed
   product bug.
2. **An agent in a nested import takes the outer binding.** The city imports
   only `jover`, and `jover` imports `jbase`. The agent defined in `jbase` is
   `rig/jover.scripter`. `gc sling rig/jbase.scripter` fails with `agent
   "rig/jbase.scripter" not found … did you mean "rig/jover.scripter"?`.
3. Bond step refs are `<bond>.<source step_ref>.item.<n>.<template id>`, for
   example `jev-review-tail.jev-build.review.item.1.synthesize`. A check's
   `iteration.1` inside a bond has no bond prefix
   (`q1-gated-checked.gate.item.1.finalize.iteration.1`), but `iteration.2`
   does. Match bond beads on `gc.root_bead_id` plus `gc.step_id` or role
   metadata, not on a step_ref prefix.
4. The root closes before the `workflow-finalize` bead (root first, by
   design). In one run the finalize bead briefly showed `gc.outcome=skipped`
   before settling on `pass`, closed by "workflow cleanup … skip directive".
   Watch the root, not the finalize bead.
5. `gc session list --state all` shows no pool wisp sessions. Use
   `session.woke` subjects in `city/.gc/events.jsonl` to prove which agents
   ran.
6. Harmless noise in an isolated city: orders `jsonl-export` and `reaper`
   failed with `gc dolt: cannot resolve runtime port`. One
   `session.stranded` event is a race between a one-shot exit and its close;
   that bead closed pass.
7. `sling --json` prints one JSON line followed by a pretty-printed error or
   result document. Parse it with `jq -s` and take `workflow_id`.
8. macOS has no `timeout`. Unlike the earlier `probepack` probe, the
   `bd db-proxy-child` and `dolt sql-server` processes exited on
   `gc stop --force` this time, and both sweeps found nothing.

## Blockers

None for the structure. Before building the real overlay pack:

- Confirm that a check-with-children review loop (build-basic-review's shape)
  works inside a runtime bond, or accept one straight review pass per build.
- Move build-basic's review-artifact contract onto a bond step.
