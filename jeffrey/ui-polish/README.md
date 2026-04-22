# Jeffrey UI Polish Pack

Iterative UI/UX refinement loop as a Claude skill.

## What It Provides

- Skill overlay at `overlay/.claude/skills/ui-polish/SKILL.md`
- Invocable as `/ui-polish` in Claude

The skill runs a repeated evaluate-identify-apply-review loop (at least ten
iterations or until diminishing returns) across spacing, typography, color,
alignment, micro-interactions, loading states, empty states, and error states.
Target quality bar is Stripe / Linear / Vercel dashboard polish.

## Import It

```toml
[imports.ui-polish]
source = "../packs/jeffrey/ui-polish"
```

## Attribution

Adapted from [Jeffrey Emanuel](https://github.com/Dicklesworthstone)
(@doodlestein)'s Stripe-Level UI prompt.
