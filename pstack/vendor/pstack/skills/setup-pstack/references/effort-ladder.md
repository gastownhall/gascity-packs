# Effort ladder

Do not handwrite a frozen table. Do not use Rust `Effort::VALID_VALUES` or `ReasoningEffort::from_str` as the live ladder. Those lists include reserved `max`. grok 1.0.13 CLI rejects `max` (same `use one of:` as 1.0.5).

Detect usable levels from the **live CLI runtime validator**. Compute three tiers, weakest → strongest.

`scripts/effort_ladder.py` is the same algorithm. Keep the role lists here and there identical.

## Detect the live enum

`/setup-pstack` detects. Spawn skills do not. `TaskToolInput` has no `reasoning_effort` field, so a later level cannot be applied on spawn without a setup overlay. Document that miss; do not fake a `task` probe.

Try, in this order, until you have a list:

1. Rejected invalid `--reasoning-effort` / `--effort`. Prefer the live message `unknown effort level …; use one of: …`. On grok 1.0.13 that line is `use one of: xhigh, high, medium, low` (probed this host). That is the usable set. Probe with `not-a-real-effort` (or another string that cannot be a level).
2. Only if that rejection never printed `use one of:`, parse `grok --help` for `--reasoning-effort` / `--effort`, canonical list **before** any `also` / per-model menu-id clause. Help text can name reserved values the CLI does not accept. Do not keep a help token the runtime `use one of:` list omitted.

Do **not** use `expected one of:` from `ReasoningEffort::from_str`. Do **not** use `Effort::VALID_VALUES`. Both include reserved `max`.

Drop `none`, `minimal`, and per-model menu ids such as `deep`. Do not invent `ultra`. Do not offer `max` unless this session's `use one of:` list named it.

The live `use one of:` list is strongest-first. Reverse it to weak → strong before stepping down (`xhigh, high, medium, low` becomes `low`, `medium`, `high`, `xhigh`). Do not use the TUI slash menu as the set (`EFFORT_LEVELS` / `SELECTABLE_REASONING_EFFORTS`).

If every probe fails, use the **ship-time snapshot** below and say so in the step 6 confirmation, not in the TUI.

## Three-tier map

Let the oriented Agent-usable levels be `L[0]` weakest … `L[n-1]` strongest.

- **Judgment** (highest): `L[n-1]`
- **Instruction-following** (highest − 1): `L[n-2]` if `n ≥ 2`, else `L[0]`
- **Mechanical** (highest − 2): `L[n-3]` if `n ≥ 3`, else the weakest (`L[0]`) when only one or two levels exist

Floor (Cola rejected shipped mechanical on `low` when a stronger rung exists): if `n ≥ 3` and highest − 2 would be `L[0]`, use `L[1]` (second-weakest) for mechanical instead. Never put shipped mechanical on the absolute floor unless only two levels exist.

### Role lists

**Mechanical.** `feature`, `refactoring`, `how-explorer`, `why-investigators`, `swarm-workers`

**Instruction-following.** `bug-fix`, `perf-issue`, `hillclimb`, `reflect-tooling`

**Judgment / explainer / verifier / panels.** `judgment-and-prose`, `hardest-tasks`, `how-explainer`, `why-synthesizer`, `reflect-judgment`, `independent-verifier`, `how-critics`, `arena-runners`, `arena-cross-judge-pool`, `architect-runners`, `interrogate-reviewers`

### Examples

Check these against `scripts/effort_ladder.py --check`.

| Detected usable set | Judgment | Instruction | Mechanical |
|---|---|---|---|
| grok 1.0.13 `use one of: xhigh, high, medium, low` | `xhigh` | `high` | `medium` |
| same plus `max` first (only if the live CLI listed it) | `max` | `xhigh` | `high` |
| `low` `medium` `high` only | `high` | `medium` | `medium` (not `low`) |
| `low` `high` only | `high` | `low` | `low` |

## Ship-time snapshot

Plugin agent frontmatter and [`defaults.toml`](defaults.toml) `[effort]` use the grok 1.0.13 usable set `low` `medium` `high` `xhigh` (unchanged from 1.0.5), so out of the box (no setup) the split is judgment `xhigh`, instruction `high`, mechanical `medium`.

That snapshot is what this plugin can bake. It is not `Effort::VALID_VALUES`. `/setup-pstack` re-detects from `use one of:` and writes `~/.grok/roles/pstack:<key>.toml` for the live split. `max` is offered only if that live list named it.

## Apply

Never send `reasoning_effort` on `task`. Write overlays as in [`resolve-effort.md`](resolve-effort.md).
