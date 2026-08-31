# Grok Build workflows

This page is how you use Grok's host-owned Rhai workflows **with** pstack. It is not a second `/poteto-mode`. Playbooks stay markdown. See ADR `0005-playbooks-are-not-rhai-workflows.md`.

## What a workflow is

A workflow is a Rhai script. The host runs `phase()`, `agent()`, `parallel()`, `pause()`, `complete()`. Discovery is not a plugin.json field. grok-build `PluginManifest` (`crates/codegen/xai-grok-agent/src/plugins/manifest.rs`) parses `skills`, `commands`, `agents`, `hooks`, `mcpServers`, `lspServers`. There is no `workflows` field. Unknown JSON is ignored.

`WorkflowRegistry::scan` (`crates/codegen/xai-grok-shell/src/session/workflow/registry.rs`) loads, first name wins:

1. `~/.grok/bundled/workflows/`
2. compiled builtins (`deep-research`)
3. `<git-root>/.grok/workflows/*.rhai` (project, if the folder is trusted)
4. `~/.grok/workflows/*.rhai` (user)

Filename must match `meta.name`. Built-in names cannot be overridden by project or user files.

This plugin repo has no `.grok/workflows/`. Enable pstack does not register Rhai.

## When to use `/poteto-mode` vs `/workflow`

Use `/poteto-mode` for playbook match, skill order, and `spawn_subagent` `pstack:<role>`.

Use `/workflow` when you already know a bounded pipeline: a named fan-out, a verify panel, a `complete({...})` result. Put that script in the **target** repository.

## How to run one

```text
/workflow review-changes {"target":"origin/main...HEAD"}
/workflow review-changes --agent-budget 256 --effort high {"target":"origin/main...HEAD"}
/workflow runs
```

`/workflows` is the catalog tab. `/workflow runs` is the live dashboard. Process restart does not resume a run.

Author with `/create-workflow`. Smoke-check with the `workflow` tool `validate_only: true`. Save under `.grok/workflows/<name>.rhai`.

## Spawn pstack roles from Rhai

`agent()` maps `agent_type` to `SubagentRequest.subagent_type` (`host_service.rs`). Default is `general-purpose`. After `grok plugin enable pstack`:

```rhai
let r = agent(prompt, #{
    label: "how",
    agent_type: "pstack:how-explorer",
    capability_mode: "read-only",
});
```

Use `pstack:feature` or `pstack:independent-verifier` the same way. Do not send `reasoning_effort` on `spawn_subagent` from a playbook. In Rhai, `effort` on `AgentOpts` is the workflow child's effort.

`isolation_worktree: true` gives a private tree and does **not** merge edits back.

## Benny copies

`automations/benny-grok/workflows/*.rhai` are optional. Copy them into a product repo's `.grok/workflows/` if you want `/workflow benny-triage`. Enable still loads `/benny-triage` as a skill. That slash path does not need the copy.

## What not to port

Do not clone `skills/poteto-mode/playbooks/` into Rhai. Do not add a `workflows` key to `plugin.json`. Do not add `.grok/workflows/` to this plugin repo.

Next: [Recipes and pitfalls](./10-recipes-and-pitfalls.md).
