# Release Compatibility Testing

## Status

Accepted.

## Context

The supported pack registry is the release boundary between Gas City and
gascity-packs. Source-tree tests prove this repository is internally
consistent, but they do not prove that the latest released `gc` binary can
consume the latest released pack pins from `registry.toml`.

Two release directions need the same guard:

- A new Gas City release must work with the latest active release of every
  first-class supported pack.
- A new pack release, or a newly supported pack, must work with the latest
  released Gas City binary.

Nightly runs cover drift between releases, such as a registry pin that becomes
unfetchable or a Gas City `latest` release that changes import behavior.

The registry smoke checks are necessary but not sufficient for inference-heavy
packs. The first-class supported packs also need behavior gates that run real
formulas with model-backed agents and verify both the artifacts and the agent
routes they use.

## Decision

Compatibility is registry-driven. The runner in
`scripts/pack_release_compat.py` reads `registry.toml`, selects the latest
non-withdrawn release for each pack, writes a temporary city with exact
`pack.toml` imports and `packs.lock` commits from that registry metadata, then
executes the consumer-facing `gc` checks:

- `gc pack release validate registry.toml`
- `gc import install`
- `gc import check`
- `gc config show`
- `gc formula list`
- `gc skill list`

The runner tests both shapes by default:

- `combined`: all latest active releases imported into one temporary city.
- `each`: every latest active release imported into its own temporary city.

This catches both single-pack loader regressions and cross-pack composition
conflicts.

The inference runner is intentionally narrower and deeper. The runner in
`scripts/gascity_pack_inference_gate.py` creates a disposable city and rig,
imports the selected pack at city scope, imports `gascity/roles` at rig scope
when the pack needs the shared run roles, and launches real formulas against
known fixtures.

The `review` gate launches the selected pack's real review formula against a
known-bad Python diff. It passes only when:

- The workflow root closes with `gc.outcome=pass`.
- The generated report validates against `gc.build.review.v1`.
- The report identifies the expected `subprocess.run(..., shell=True)` shell
  injection risk with a blocking review status.
- The workflow bead graph routed through the expected pack-specific review
  agents.

The build gate launches the selected pack's build formula with `--stdin --on
<pack-build-formula>` against a small Python fixture where `slugger.py` raises
`NotImplementedError` and `tests/test_slugger.py` defines the expected behavior.
For the `gascity` pack this remains the `build-basic` gate. It passes only when
the workflow closes with `gc.outcome=pass`, the generated build artifacts
validate against the shared Gas City build contracts, the implementation
worktree no longer contains the placeholder, `python -m pytest -q` passes in
that worktree, and the bead graph routed through the expected pack-specific
build agents.

The `gastown-orchestration` gate covers the Gastown pack, which is an
orchestration pack rather than a methodology build pack. It imports Gastown
using the same default-rig import shape used by real cities, requires mayor,
deacon, boot, and witness sessions to come up, verifies the Gastown formulas
are visible, and runs a bounded `mol-review-leg` assignment through the
Gastown polecat pool. The gate passes only when the assignment closes with a
structured report in the bead notes.

Together these test the pack's primary behavior: formula orchestration,
role-agent inference, code-writing drains, artifact writing, and pack-provided
validation.

## Automation

`.github/workflows/pack-release-compatibility.yml` installs a requested Gas City
module ref with `go install github.com/gastownhall/gascity/cmd/gc@<ref>` and
runs the compatibility runner.

The workflow runs on:

- Pull requests and pushes that touch `registry.toml`, top-level `pack.toml`
  manifests, or the compatibility runner/workflow.
- A nightly schedule.
- Manual dispatch with optional `gascity_ref`, `registry_ref`, `pack`, and
  `exercise` inputs.
- Repository dispatch events named `gascity-release-compatibility` or
  `pack-release-compatibility`.

The Gas City release pipeline should dispatch this repository before publishing
or promoting a release:

```json
{
  "event_type": "gascity-release-compatibility",
  "client_payload": {
    "gascity_ref": "v0.3.0",
    "exercise": "both"
  }
}
```

Pack release PRs should keep `registry.toml` updated with the release version,
commit, and content hash. The compatibility workflow then verifies the proposed
latest release against `gc@latest`.

`.github/workflows/gascity-pack-inference.yml` is the dispatchable
model-backed behavior gate for all first-class supported packs. It installs
`bd`, Dolt, Claude Code, and the requested Gas City ref, then runs the
selected pack gates through the same Ollama-backed Claude environment shape
used by Gas City's Tier C nightly:

- `ANTHROPIC_BASE_URL=https://ollama.com`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, and `OLLAMA_API_KEY` from
  `secrets.OLLAMA_API_KEY`
- model variables from the `GC_WORKER_INFERENCE_CLAUDE_OLLAMA_*` repository
  variables

The dispatchable inference workflow runs on push to `main` for supported pack
changes, manual dispatch, and repository dispatch events named
`gascity-pack-inference`, `gascity-release-inference`, or
`pack-release-inference`. Manual and repository dispatch can select one pack,
`methodology`, or `all-supported`; the default is `all-supported`.

`.github/workflows/supported-pack-nightly.yml` is the scheduled intra-release
regression run. It first runs the static pack flow contracts, then executes a
one-pack-at-a-time inference matrix against `gc@main` by default. Each pack has
a matrix-specific gate timeout below the job timeout so diagnostics still upload;
manual or release dispatch can override that timeout when deliberately needed:

- `gascity`: `review` plus `build-basic`
- `superpowers`: review plus build, including brainstorming/spec review,
  plan review, implementation drain, code-review loop, and finalization
- `compound-engineering`: review plus build, including selector-driven review
  fanout, plan review, implementation drain, compound resolution, and
  finalization
- `gstack`: review plus build, including office-hours planning, plan review,
  implementation drain, staff/QA/security review, QA fanout, release
  readiness, finalization, and optional publish surface
- `bmad`: review plus build, including PRD, architecture, epics/stories,
  implementation readiness, story development, and adversarial review fanout
- `gastown`: orchestration startup, rig-scoped agents, bounded polecat
  `mol-review-leg`, plus static build-orchestration contracts for polecat
  handoff, refinery merge/PR handling, witness recovery, deacon health checks,
  and idea-to-plan fanout

The static contracts are deliberately part of the live runner initialization:
nightly fails before spending inference budget if a high-value flow loses an
expected specialist lane, artifact schema, drain formula, approval check, or
pack-specific finalization/readiness step.

Gas City release automation should dispatch both workflows before promoting a
release that claims first-class pack compatibility:

```json
{
  "event_type": "gascity-pack-inference",
  "client_payload": {
    "gascity_ref": "v0.3.0",
    "pack": "all-supported",
    "gate": "all",
    "timeout": "75m"
  }
}
```

## Local Use

Run the same check locally with the `gc` on your `PATH`:

```sh
python3 scripts/pack_release_compat.py
```

Install and test an explicit Gas City release:

```sh
go install github.com/gastownhall/gascity/cmd/gc@latest
python3 scripts/pack_release_compat.py --gc-bin "$(go env GOPATH)/bin/gc"
```

Limit a run to one pack while authoring a new release:

```sh
python3 scripts/pack_release_compat.py --pack slack-full --exercise both
```

Run the supported-pack inference gate setup path locally without requiring
Ollama credentials:

```sh
python3 scripts/gascity_pack_inference_gate.py --setup-only --skip-inference-env-check --pack all-supported --gate all
```

Run the static flow-contract suite locally:

```sh
python3 -m pytest tests/test_gascity_pack_inference_gate.py gascity/tests/test_formula_assets.py -q
```

Run only a code-writing build gate when the Ollama-backed Claude environment
variables are present:

```sh
python3 scripts/gascity_pack_inference_gate.py --pack superpowers --gate build --gc-bin "$(command -v gc)"
```

Run the full inference gate set:

```sh
python3 scripts/gascity_pack_inference_gate.py --pack all-supported --gc-bin "$(command -v gc)"
```
