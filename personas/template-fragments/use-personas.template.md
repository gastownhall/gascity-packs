{{ define "use-personas" }}
## Equip a Persona Before You Build

A generalist agent is competent at everything and excellent at nothing. Before you
start meaningful work, equip the principal-engineer persona that fits the task — become
a principal backend engineer for a backend change, a principal security engineer for an
audit — do the work at that level, then release it when the task is done.

This composes with the rest of the toolchain: model-advisor picks the model *tier*,
provider-forge picks the *provider/model*, and personas picks the *role*.

**The rule:** on task pickup, equip the best-fit persona, then hold your work to that
persona's verification bar.

```bash
personas match "<task description>"   # see the equip decision (read-only)
personas equip "<task description>"    # equip it + keep it warm for the next agent
personas show <persona-id>             # the full playbook + verification bar
```

`personas` is pure-stdlib and read-only on `list`/`show`/`lint`/`match`/`cache`; `equip`
materializes the persona into a shared warm cache so the next agent that needs the same
role reuses it without paying the materialize cost. Equipped personas age out on a
sliding 30-minute idle TTL (2-hour absolute ceiling), both configurable.

**The loop:**
1. **Match.** `personas match "<task>"` returns the best-fit persona, the score, and the
   exact terms that fired — so the choice is explainable, not a black box.
2. **Equip.** Adopt that persona's playbook and mindset for the task. In a gas-town
   session the equip-on-task-pickup hook does this for you at session start.
3. **Hold the bar.** Each persona carries a verification bar — the standard it does not
   hand off work below. Meet it before you submit.

For trivial or throwaway work, skip it — the role does not matter. When the work is
consequential and squarely in one discipline, equip first.
{{ end }}
