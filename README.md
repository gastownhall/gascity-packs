# gascity-packs

A collection of opt-in [Gas City](https://github.com/gastownhall/gascity) packs.

Gas City is an orchestration-builder SDK for multi-agent coding workflows. A
*pack* is a unit of workspace configuration: agents, commands, services,
formulas, skills, hooks, template fragments, or any combination. Packs compose
through `pack.toml` imports, so a city can opt into any subset of the packs in
this repo without forking.

For the full model (cities, rigs, formulas, beads, runtime providers) see the
[Gas City README](https://github.com/gastownhall/gascity).

## Sponsors

<p align="center">
  <a href="https://blacksmith.sh/">
    <img src="docs/images/blacksmith-powered.png" alt="Powered by Blacksmith" height="40">
  </a>
</p>

## Start here: first build in about ten minutes

If you just installed Gas City and want a working multi-agent build factory,
this is the shortest path. Each step is copy-pasteable; swap names to taste.

1. **Install Gas City and start a city** (skip steps you have already done):

   ```sh
   brew install gascity
   gc init ~/my-city
   cd ~/my-city
   gc start
   ```

2. **Add the repository you want agents to work on as a rig:**

   ```sh
   git clone https://github.com/you/your-project
   cd your-project
   gc rig add .
   ```

3. **Import the base pack.** From the city directory:

   ```sh
   gc import add --name gc https://github.com/gastownhall/gascity-packs.git//gascity
   ```

   This writes the import, fetches the latest release, and pins it in
   `packs.lock` — no clone needed. (`gc import upgrade gc` moves the pin
   later; contributors hacking on the packs themselves can point `source`
   at a local clone instead.)

4. **Import the rig roles** in your city's `city.toml`. Rig-scoped imports
   are declared on the rig entry:

   ```toml
   [[rigs]]
   name = "your-project"

   [rigs.imports.gc]
   source = "https://github.com/gastownhall/gascity-packs.git//gascity/roles"
   ```

   The city-level import provides the workflow formulas and the `gc.mayor`
   coordinator skill; the rig-level `roles` import provides the worker agents
   (`gc.implementation-worker`, `gc.requirements-planner`, and friends) that
   the formulas route work to. Run `gc import install` after editing to
   fetch anything newly referenced.

5. **Run your first build.** Create a bead describing the goal, then launch
   the starter factory against it:

   ```sh
   gc bd create "Add a --json flag to the export command"
   gc sling gc.run-operator <bead-id> --on build-basic \
     --var artifact_root=plans/json-flag/build
   ```

   `build-basic` walks requirements → plan → plan review → decomposition →
   parallel implementation → a three-lane review fanout → finalize. Artifacts
   (requirements, plan, review reports, and a `factory-run.md` summary) land
   under `artifact_root` in your rig.

6. **Pick a methodology when you want more opinion.** The four methodology
   packs below replace `build-basic`'s stages with vendored, battle-tested
   processes while keeping the same launch shape — import one at city scope
   and sling its build formula instead (for example `--on bmad-build`):

   ```sh
   gc import add https://github.com/gastownhall/gascity-packs.git//bmad
   ```

   Each pack's README has its own quick start.

## Which build pack should I use?

| Pack | Process it runs | Reach for it when |
| ---- | --------------- | ----------------- |
| [gascity](./gascity) (`build-basic`) | Requirements → plan → review → decompose → implement → three-lane review | You want the default starter factory with the fewest moving parts. |
| [bmad](./bmad) (`bmad-build`) | PRD → architecture → epics/stories → readiness gate → story-by-story implementation with self-check and acceptance audit → adversarial review | You want disciplined document-first delivery with explicit story decomposition and readiness checks. |
| [compound-engineering](./compound-engineering) (`compound-build`) | Brainstorm/plan → plan review → implement → the widest reviewer-persona fanout → resolution | Review depth matters most: correctness, security, performance, migrations, and API contracts each get their own reviewer lane. |
| [superpowers](./superpowers) (`superpowers-build`) | Brainstorm → written spec approval → per-task test-driven development → spec-compliance then code-quality review | You want hard approval gates before code and strict TDD per task. |
| [gstack](./gstack) (`gstack-build`) | Office-hours intake → multi-perspective plan review → build → staff review → QA → security → release readiness | You want founder/PM-flavored gates and explicit QA + release-readiness stages before shipping. |

All five expose the same launch variables (`interaction_mode`, `review_mode`,
`drain_policy`, `push`, `open_pr`, …), so switching methodology is a one-word
change to the formula name.

## Using a pack

The canonical path is the import CLI — it writes the import, fetches the
latest release, and pins the commit in `packs.lock`:

```sh
gc import add https://github.com/gastownhall/gascity-packs.git//bmad
```

Which is equivalent to this in `city.toml` (or any pack's `pack.toml`),
followed by `gc import install`:

```toml
[imports.bmad]
source = "https://github.com/gastownhall/gascity-packs.git//bmad"
```

Contributors working on the packs themselves can clone this repo and point
`source` at a local path instead:

```toml
[imports.bmad]
source = "../gascity-packs/bmad"
```

Each pack documents its own prerequisites, import snippet, and usage.

## Layout

Each top-level directory is either a pack or a group of related packs:

- A directory containing `pack.toml` is itself a pack; import it by path.
- A directory without `pack.toml` groups related subpacks and typically ships
  an `all/` rollup that imports the group as one.

Browse the tree for the current set; each pack has its own README.

### Agent context packs

- [cass](./cass) adds a shared `cass-search` prompt fragment and Claude skill
  overlay for searching past coding-agent sessions.

### Build methodology packs

Raw-framework subagents become Gas City fanouts. The vendored methodology text
is treated as source material for behavior, not runtime authority: if a raw
skill says to spawn a subagent, dispatch a task tool, or invoke a plugin
command, the pack should model that work as formula steps, expansion children,
drains, or fanout/fanin lanes.

Use two mode concepts when comparing methodology packs:

- `interaction_mode` describes human participation in planning and gates:
  interactive, autonomous, or headless.
- `review_mode` describes whether review is report-only, machine handoff, or
  an interactive top-level review that may apply safe fixes.

- [gascity](./gascity) provides the `build-base` workflow contract, the
  default `build-basic` implementation, and the `build-from-*` continuation
  entrypoints for resuming a build from existing artifacts.
- [compound-engineering](./compound-engineering) imports `gascity` as `gc`
  and implements `build-base` with vendored Compound Engineering skills,
  agent personas, and Gas City-native review/finalization expansions.
- [superpowers](./superpowers) imports `gascity` as `gc` and implements
  `build-base` with vendored Superpowers skills and Gas City-native
  development/review expansions.
- [bmad](./bmad) imports `gascity` as `gc` and implements `build-base` with
  vendored BMAD Method skills and Gas City-native story/review expansions.
- [gstack](./gstack) imports `gascity` as `gc` and implements `build-base`
  with vendored garrytan/gstack office-hours, autoplan, review, QA, security,
  documentation, and release-readiness skills mapped to Gas City fanouts.

See the [build methodology framework audit](./docs/design/build-methodology-framework-audit.md)
for the current parity assessment and proposed beginner-friendly updates.

### Slack packs (tiered)

The Slack provider ships as three tiers — pick the smallest one that covers
your use case:

| Tier | Pack | Use it when |
| ---- | ---- | ----------- |
| 1 | [slack-mini](./slack-mini) | The mayor only needs to post status into a single channel. No bindings, no state. |
| 2 | [slack-channel](./slack-channel) | A few named sessions share channels with distinct identities — no slash commands or cross-rig routing. |
| 3 | [slack-full](./slack-full) | Slash commands, interactive modals/buttons, peer fanout, launcher-mode spawning, or multi-rig channel routing. |

See the [tiering design memo](./docs/design/slack-pack-tiering.md) for the
rationale.

## Contributing

Issues and pull requests are welcome. When a pack's surface changes, update
its README in the same PR so the docs stay current with the code.

### Publishing registry releases

Registry releases are content-addressed. Use the Make targets so the release
commit and hash are stamped by `gc` instead of hand-authored:

```sh
GC=/path/to/gc make registry-publish \
  PACK=slack-mini \
  VERSION=0.1.1 \
  DESCRIPTION="Release summary."
```

`GC` defaults to `gc`, so local testing can point it at an uninstalled build.
`REGISTRY_COMMIT` defaults to `HEAD`, and only tracked files at that commit are
hashed; commit pack content before publishing. For new packs, also pass
`PACK_DESCRIPTION="..."`. To withdraw a bad consumed release without rewriting
it:

```sh
make registry-withdraw \
  PACK=slack-mini \
  VERSION=0.1.0 \
  REASON="Superseded by 0.1.1."
```

Before opening a PR, run:

```sh
make registry-format-validate
GC=/path/to/gc make registry-validate
```

### Release compatibility and inference gates

Supported pack releases are also gated by the registry-driven compatibility
smoke in `scripts/pack_release_compat.py` and the
`Pack Release Compatibility` workflow. First-class supported packs also have a
model-backed formula gate in `scripts/gascity_pack_inference_gate.py`, plus a
scheduled supported-pack nightly workflow. See
[Release Compatibility Testing](./docs/design/release-compatibility-testing.md)
for the release-time and nightly test contract.
