{{ define "symbolic-edits" }}
## Editing Discipline: Structural Edits Go Through the Gate

Free-text editing of a structural change is two gambles at once: that you
found *every* site (each reference to a renamed symbol, each caller that
needs an import), and that the text you typed still parses. Miss either and
the build breaks — silently, until something downstream compiles a tree you
already poisoned.

This pack removes both gambles. The op CLI **computes** the change from the
AST, and a *false-negative-only* compile gate stands between that change and
the disk: it writes only what it can prove parses in every touched file, and
refuses everything else.

**The rule:** for a **structural** edit — renaming a symbol across files,
cleaning up an import block, or extracting a declaration into a new package —
use the gated op, not the `Edit` tool.

```bash
bin/op <op>  <file> [--k v ...]          # PLAN: read-only diff + predicted verdict + token
bin/op <op>! <file> <token> [--k v ...]  # EXECUTE: writes iff the gate accepts
```

**The loop:**
1. **Plan.** Run `bin/op <op> <file> …` (e.g. `rename-symbol --symbol Foo
   --new-name Bar`). It writes nothing; it emits a unified diff, the full set
   of files that change, a predicted `ACCEPT`/`REJECT`, and a content-hash
   token.
2. **Review.** Read the diff and the verdict. `ACCEPT` means the gate already
   parsed the proposed files in scratch. A `REJECT` or a token-less "no
   change" plan means re-plan with a narrower scope — do not force it.
3. **Execute.** Run `bin/op <op>! <file> <token> …` with the same args. It
   writes only on `ACCEPT`. A stale token (the file drifted since you planned)
   aborts with `REJECT — stale plan, re-plan` and writes nothing — a real
   conflict, recovered by re-planning, never a broken commit.

The ops: `rename-symbol` (Go, gopls, cross-file), `fix-imports` (Go + Python,
one file's imports), `extract-to-package` (Go, one exported decl → new
package). `bin/op --list` shows what resolves here.

**When NOT to reach for it:** the op CLI is *not* a general editor. Ordinary
edits — a function body, a literal, a comment, config, prose — and any change
outside those three ops still use `Edit`. The gate's worst case is a reject you
recover from; the cost it buys out is a silently-broken build.
{{ end }}
