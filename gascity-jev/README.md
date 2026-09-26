# Gas City Jev Overlay (`gascity-jev`, imported as `gc`)

An experimental overlay on [gascity](../gascity) whose Jev gates decide, from
deterministic receipts, whether Claude review sessions run at all. It imports
the base pack as `gc`, so every `gascity` formula, prompt, check, command and
skill is available unchanged, and it adds:

- **`jev-build`** — `build-basic` with its review stage replaced by a Jev review
  gate. The gate runs the tests itself, compares pre-existing test files by hash,
  asks Jev one "is there any input that violates this criterion?" question per
  acceptance criterion plus a smell screen over the diff, and then runs only the
  Claude review lanes Jev is not confident about.
- **`jev-build-compact`** — for small, well-specified tasks: one implementation
  drain, the same review gate, finalize and publish. No requirements, plan,
  plan review, decomposition or summary stages.
- **`gc gc jev-route <bead>`** — the intake router: asks Jev whether the task is
  compact and slings `jev-build-compact` or `jev-build`.
- **`gc.jev-gate`** — a deterministic script worker (no LLM) that runs the gate
  and the review-report step.

Why: a Jev answer takes about 0.4 s and a few thousand Jev tokens, while each
Claude session costs roughly ten requests of about 50K context tokens. A Jev
answer only saves money when it stops a session from running, so every gate here
decides whether a session runs. See the
[design](../specs/plans/0003-gascity-jev-redesign-design.md) and the
[gate spikes](../specs/experiments/jev-gate-spikes/README.md).

## Install

Use absolute paths to this checkout. Import the overlay at city scope and its
roles at rig scope, both as `gc` (the roles pack imports the base roles and adds
`gc.jev-gate`):

```toml
# pack.toml (city)
[imports.gc]
source = "/absolute/path/to/gascity-packs/gascity-jev"

# city.toml
[[rigs]]
name = "your-project"

[rigs.imports.gc]
source = "/absolute/path/to/gascity-packs/gascity-jev/roles"
```

`gc import add --name gc <path>` also works, but it pins a local git checkout to
its committed `HEAD`: uncommitted edits to the pack are not loaded. Write the
plain path as above while developing the pack.

Everything the base README requires still applies: the rig needs an `origin`
whose default branch resolves as `origin/HEAD`, and check gates need a `python3`
with PyYAML on Gas City's gate `PATH`
([base README](../gascity/README.md#python-for-check-gates)).

Jev needs `TYPESAFE_API_KEY` in the `gc.jev-gate` worker's environment, for
example in `[workspace.env]` as `TYPESAFE_API_KEY = "$TYPESAFE_API_KEY"` so the
value is expanded at session launch and never written to disk. Without it every
gate fails open to the ordinary path.

## Run

```sh
gc bd create "Add a --json flag to the export command"
# Let the intake router pick the compact or full build:
gc gc jev-route <bead-id> --var artifact_root=plans/json-flag/build
# Or always take the full gated build:
gc sling gc.run-operator <bead-id> --on jev-build --var artifact_root=plans/json-flag/build
```

Variables (all optional): `jev_mode` (`auto` or `off`), `jev_model`
(`jev-1.13.0`), `jev_state_dir`, `jev_test_command` (default: detect pytest,
`go test ./...`, `cargo test` or `npm test`), `jev_test_timeout`, and
`jev_audit_rate` (empty uses the adaptive schedule).

## What gets skipped

| Gate | Skips | When |
| --- | --- | --- |
| Receipts | test-evidence lane | the gate's own test run passes and no pre-existing test file changed |
| Review gate (Jev Noul per criterion) | acceptance lane, per criterion | P(violation) ≤ 0.15 |
| Smell screen (Jev Noul per rule × hunk) | smell checks in the simplicity lane | every answer ≤ 0.2; P ≥ 0.9 sends the smell straight to the fix lane |
| Lane count | synthesis session | fewer than two lanes run |
| Lane count | whole review loop | no lane runs |
| Intake router | requirements, plan, plan review, decompose, summary | compact at confidence ≥ 0.8, no risky surface, no design need |

The gate also writes the review context and the script step writes the
`gc.build.review.v1` report, so those two Claude sessions never run. Design
review in the simplicity lane always runs on day one.

Receipts come first: a failing test run, a changed pre-existing test, or no test
runner runs every lane. Any Jev failure (no key, HTTP error, invalid answer,
oversized input, gate crash) also runs every lane at full scope; the reason is
recorded on the gate bead.

## Bands, audits and the circuit breaker

- **Audits.** Per decision type, a random share of act-band decisions runs the
  skipped work anyway: 30% until 60 audited accepts, then 10% until 300, then
  5%. Lanes report per-criterion (`jev.criteria_verdicts`) and smell
  (`jev.smell_verdicts`) verdicts so each audit is labeled.
- **Circuit breaker.** An audited decision a lane contradicts is a miss; that
  decision type stops acting (other types keep acting) until a refit.
- **Decision log.** `<artifact_root>/jev/decisions.jsonl` per build, and
  `ledger.jsonl` in the state directory (`jev_state_dir`, default
  `<city>/.gc/jev-gate`) across builds.

```sh
python3 gascity-jev/assets/scripts/jev_decisions.py status --state-dir <city>/.gc/jev-gate
python3 gascity-jev/assets/scripts/jev_decisions.py aggregate <run>/**/decisions.jsonl --out summary.json
python3 gascity-jev/assets/scripts/jev_decisions.py refit --state-dir <city>/.gc/jev-gate
```

## Other Jev helpers

`jev_kind.py` (issue/PR kind), `jev_rank.py` and `github_duplicate_candidates.py`
(duplicate candidate ordering), `jev_tasks.py` and `jev_evidence.py` remain
available as advisory command-line tools for maintainer-city triage. No overlay
formula wires them in.

## Status

Experimental. The gated graph shape is proven in a disposable Gas City 1.5 city
with stub workers ([structure runs](../specs/experiments/jev-overlay-build/));
day-one bands come from small spikes and must be refit from audited outcomes. No
end-to-end speed or cost claim is made until a paired A/B has been run.
