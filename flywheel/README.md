# Flywheel

Agent-enhancement stack inspired by [Agent Flywheel](https://agent-flywheel.com/).

This directory is not a pack itself; it groups related subpacks. Each subpack
adds one capability (messaging, search, memory, scanning) to agents in a city.

## Subpacks

- `all/` — rollup that imports the full stack
- `mcp-agent-mail/` — inter-agent messaging
- `cass/` — past-session search
- `cm/` — persistent memory / playbook
- `ubs/` — pre-commit bug scanning

Import the whole stack:

```toml
[imports.flywheel]
source = "../packs/flywheel/all"
```

Or cherry-pick individual subpacks; see each subpack's README for
prerequisites and configuration.
