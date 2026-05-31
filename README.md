# gascity-packs

A collection of opt-in [Gas City](https://github.com/gastownhall/gascity) packs.

## What's a pack?

Gas City is an orchestration-builder SDK for multi-agent coding workflows. A
*pack* is a unit of workspace configuration: agents, commands, services,
formulas, skills, hooks, template fragments, or any combination. Packs compose
through `pack.toml` imports, so a city can opt into any subset of the packs in
this repo without forking.

For the full model (cities, rigs, formulas, beads, runtime providers) see the
[Gas City README](https://github.com/gastownhall/gascity).

## Using a pack

Packs live next to the consuming workspace. A typical layout:

```text
your-city/
  pack.toml
packs/
  pr-review/          # pack from this repo
  discord/
  ...
```

Inside your workspace `pack.toml`:

```toml
[imports.pr-review]
source = "../packs/pr-review"
```

Each pack documents its own prerequisites, import snippet, and usage.

## Layout

Each top-level directory is either a pack or a group of related packs:

- A directory containing `pack.toml` is itself a pack; import it by path.
- A directory without `pack.toml` groups related subpacks and typically ships
  an `all/` rollup that imports the group as one.

Browse the tree for the current set; each pack has its own README.

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
