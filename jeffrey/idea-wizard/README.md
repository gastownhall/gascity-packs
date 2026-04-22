# Jeffrey Idea Wizard Pack

Structured brainstorming as a Claude skill.

## What It Provides

- Skill overlay at `overlay/.claude/skills/idea-wizard/SKILL.md`
- Invocable as `/idea-wizard` in Claude

The skill runs four phases:

1. **Diverge** — generate 30 one-liner ideas using analogies, inversions,
   cross-domain combinations, and constraint relaxation.
2. **Evaluate** — reject the weak ones with explicit reasons.
3. **Converge** — for survivors, detail the *what*, *why*, downsides, and
   a confidence score; rank by (impact × confidence) / effort.
4. **Implement** — start on the top-ranked idea.

## Import It

```toml
[imports.idea-wizard]
source = "../packs/jeffrey/idea-wizard"
```

## Attribution

Adapted from [Jeffrey Emanuel](https://github.com/Dicklesworthstone)
(@doodlestein)'s Idea Wizard.
