# Jeffrey De-Slopify Pack

Remove AI-telltale writing patterns from text, via a Claude skill.

## What It Provides

- Skill overlay at `overlay/.claude/skills/de-slopify/SKILL.md`
- Invocable as `/de-slopify` in Claude

The skill reads text line by line and strips the usual tells:

- Em dashes (replaced with semicolons, commas, or recast sentences)
- "It's not X, it's Y" constructions, "Here's why", "Let's dive in"
- Filler openers ("Certainly!", "Great question!", "Absolutely!")
- Hedging ("I think maybe", "It's worth noting that")
- Excessive bullets where prose works better
- Gratuitous emoji and self-referential AI meta-commentary
- Redundant transitions ("Furthermore", "Moreover") used as paragraph openers

This is intentionally a manual read-and-revise pass, not a regex substitution.

## Import It

```toml
[imports.de-slopify]
source = "../packs/jeffrey/de-slopify"
```

## Attribution

Adapted from [Jeffrey Emanuel](https://github.com/Dicklesworthstone)
(@doodlestein)'s De-Slopifier.
