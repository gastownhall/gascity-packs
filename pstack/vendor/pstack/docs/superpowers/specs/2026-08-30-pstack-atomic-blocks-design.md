# Official pstack atomic blocks and grok mapping

Date: 2026-08-30
Official pin: `6fecddba65801f9b9c08b8b328d998ee5b09d290` (`UPSTREAM`)
Port: tommy-ca/pstack

## Data flow

```
operator /poteto-mode <goal + check>
  -> match playbook (markdown under skills/poteto-mode/playbooks/)
  -> copy steps into todos (verbatim; skip: <reason>)
  -> situational skills (how, tdd, interrogate, …) as steps fire
  -> spawn_subagent subagent_type=pstack:<role>  (depth 1, parent fans out)
  -> join get_command_or_subagent_output
  -> optional pstack:independent-verifier
  -> opening-a-pr
```

Overnight: persist predicate, `/loop` → `scheduler_create` (min 60s, new turn). Watch: `monitor`.

## Schemas

**UPSTREAM pin.** One line `tree <40-hex>` = last official `pstack/` commit.

**Models overlay** `~/.grok/pstack-models.toml` (top-level keys, not `[models]`):

```toml
feature = "grok-4.6"          # or inherit-parent | auto
independent-verifier = "grok-4.6"

[effort]
feature = "medium"
```

**Role overlay** `~/.grok/roles/pstack:<key>.toml` (stem = spawn type):

```toml
description = "pstack role overlay"
reasoning_effort = "medium"
```

**spawn_subagent** (wire alias `task`): `subagent_type`, optional `model`, `background`, `isolation`. Never `reasoning_effort` or Cursor `readonly`.

## Building blocks vs this port

| Block | Official | Grok port |
|---|---|---|
| Router `/poteto-mode` | official YAML `mode: true` (Cursor sticky) | grok: `disable-model-invocation: true`, no `mode` field. Operator docs: type `/poteto-mode`; it does not auto-enter. |
| 22 playbooks + opening-a-pr | 23 files | same 23 files |
| 21 principles | `principle-*` | same 21 |
| Skill dirs (total) | 45 including `make-bot-ui` | 44; skip `make-bot-ui` |
| Remaining after router+principles+setup | 22 including `make-bot-ui` | 21 |
| Plugin agents | `poteto-agent`, `comment-sicko` | those two plus 20 role agents `pstack:<key>` |
| Setup | `~/.cursor/rules/*.mdc` | `pstack-models.toml` + `roles/pstack:<key>.toml` |
| Spawn | Cursor `Task` | `spawn_subagent` `pstack:<role>` |
| Overnight | same-run `/loop` | persist-then-wake `scheduler_create` |
| Benny | Cursor automations | source only, not grok hooks |
| Independent verify | Cloud Agent / Cursor | `pstack:independent-verifier` |

## Review of current implementation

**Keep.** Playbook filenames, principle set, situational skills except `make-bot-ui`. Skill order: pstack first.

**Remap (done).** Harness table in `HARNESS.md`. Overlay stems. Effort ladder grok 1.0.13 `xhigh|high|medium|low`.

**Skip (intentional).** `make-bot-ui`, Benny as grok hooks, Cursor babysit skill, `deslop`/`control-cli`/`control-ui` (use `/unslop`, `/no-comments`, drive the real app).

**Gaps (host limits, not missing files).** `MAX_SUBAGENT_DEPTH` 1 vs official nested `Task`. Overnight is not same-run. Official shipping.md still names `gt merge-when-ready`; HARNESS degrades to `gh` if `gt` is missing.
