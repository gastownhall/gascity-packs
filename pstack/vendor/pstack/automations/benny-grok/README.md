# Benny on Grok Build

`automations/benny/skills/` is the **upstream reference**. This sibling tree is the live grok contract. It is part of the pstack plugin.

After `grok plugin install tommy-ca/pstack --trust` and `grok plugin enable pstack`, type `/benny-triage` or `/benny-repro`. No copy into `.grok/hooks` or `.grok/workflows` is required.

Grok has no Slack channel auto-start. Pass the Slack permalink as the skill argument. Optional inbound from a webhook: `grok -p '/benny-triage <permalink>'`. Overnight waits use `/loop` → `scheduler_create`. Fan-out uses `spawn_subagent` with `pstack:<role>`.

Enable from a host shell if the agent sandbox is EROFS. Spawn `pstack:how-explorer`, not `how-explorer`.

Plugin `plugin.json` has no `hooks` key. The merge-deny script under `bin/fail-closed.sh` is optional and local. It does not run for every pstack user.

## Optional workflow

`.rhai` files here are not a plugin component. Use `/benny-triage` after enable. `/workflow` is only if you already keep project workflows.
