{{ define "read-with-outline" }}
## Reading Discipline: Outline First

Code is your most expensive input. A 2700-line file costs ~27,000 tokens
to `Read` in full (~10 tokens/line); the same file's outline is ~300 tokens
regardless of size. On a large file that is a ~100× saving — and on a
big-file-heavy exploration session it is roughly half your token budget.

**The rule:** for any source file **≥ 200 LoC**, run the outline FIRST,
before any full `Read`.

```bash
outline <file>
```

`outline` emits a compact Markdown skeleton — top-level declarations,
types, and functions — each anchored with an `L<start>–<end>` line span.
It is read-only and stateless; it never writes and never blocks you.

**The loop:**
1. **Outline first.** Run `outline <file>` and read the structural summary.
   For most questions ("does this file define X?", "where does Y live?",
   "what's the shape of this module?") the skeleton is the whole answer.
2. **Fetch bodies only when needed.** When you genuinely need an
   implementation, jump straight to it: take the function's `L<start>–<end>`
   from the outline and `Read` that span with `offset`/`limit`. You pay for
   the lines you read, not the file you opened.
3. **Escalate to a full read deliberately.** Reading the entire file is the
   escape hatch, not the default. Reach for it when the outline declares its
   limits — dense control flow, a body whose behaviour you can't infer from
   its signature, an edge case you must see.

**Why outline-first, not outline-only:** the trade-off is asymmetric.
Reading a full file when the outline would have sufficed wastes tokens but
produces correct work. Reading only the outline when you needed the body
produces *wrong* work — you answer from the skeleton and miss what's inside.
So: prefer the outline, but fetch the body the moment the outline stops
being enough. The outline is the default lens, not the only lens.

**Below 200 LoC**, `outline` stays silent — small files are cheap, just
`Read` them. The threshold is per-project overridable; some files opt out
with an `outline:skip` marker in their first few lines. When in doubt on a
large file, outline first.
{{ end }}
