# Jeffrey

Gas City adaptations of [Jeffrey Emanuel](https://github.com/Dicklesworthstone)
(@doodlestein)'s prompt library, packaged as Claude skill overlays.

This directory is not a pack itself; it groups related subpacks. Each subpack
contributes one skill that agents can invoke with `/<skill-name>` in Claude.

## Subpacks

- `all/` — rollup that imports every skill below
- `planning-workflow/` — multi-phase plan-before-code workflow
- `code-review/` — four-pass review (correctness, security, performance, maintainability)
- `idea-wizard/` — diverge / evaluate / converge brainstorming
- `ui-polish/` — iterative refinement loop for UI components
- `robot-mode/` — design an agent-friendly CLI (JSON, exit codes, structured errors)
- `readme-revise/` — evaluate and polish documentation
- `de-slopify/` — strip AI-telltale writing patterns

Import the full set:

```toml
[imports.jeffrey]
source = "../packs/jeffrey/all"
```

Or import one at a time; each subpack has its own README.
