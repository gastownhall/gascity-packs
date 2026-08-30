# Resolve `task.model`

Every pstack skill that spawns `task` uses this rule. Read it once, then apply it at the spawn site. Shipped defaults live in [`defaults.toml`](defaults.toml).

1. Read `~/.grok/pstack-models.toml` if it exists.
2. Look up the role key named at the spawn site (`feature`, `how-explorer`, `arena-runners`, …).
3. If that override file is **absent**, send `model: grok-4.6` (the Grok Build shipped default). If `task` rejects it, omit `model`. Do not send a slug from another product's panel.
4. If the override file exists and the key is missing, or the value is `inherit-parent` or `auto`, **omit** `task.model`. The child inherits the parent session model.
5. If the value is a real slug, send `model` only when that slug was confirmed this session: a live `task.model` rejection that names valid slugs, `grok inspect` if it actually lists models, or `grok models`. Never invent a slug. Never copy a slug from another product's panel or from training memory.
6. Array keys (`how-critics`, `arena-runners`, `arena-cross-judge-pool`, `architect-runners`, `interrogate-reviewers`): one `task` spawn per entry. An entry that is `inherit-parent` or `auto` omits `model` on that spawn. If the override file or key is absent, spawn **one** child and send `grok-4.6` (omit if rejected). Do not expand a missing panel into multiple guessed slugs.
7. Architect without an override file may still spawn **two** children (two sketches) with `grok-4.6` or omitted model. That is two prompts, not a four-model panel.
8. If `task` rejects a slug, omit `model` or retry only with a slug the error text named that is already in this session's detected set. Do not pick a "closest family equivalent."

Effort is a separate overlay. Never send `reasoning_effort` on `task`. Spawn `subagent_type` `pstack:<role-key>` and follow [`resolve-effort.md`](resolve-effort.md).

This plugin is the Grok Build port. `/setup-pstack` writes `~/.grok/pstack-models.toml` as an override. It does not ship other products' panel slugs.
