# ast-lens write-side spine

The read-side (`bin/outline.py`) is a *lens for reading*: it auto-prepends an
AST outline to a `Read` so an agent navigates a file at the right altitude. The
write-side is the mirror image — a *lens for writing*. An agent issues a
transform **intent** on a file; the framework emits a content-addressed **plan**
(read-only); and a later **execute** commits that plan through a compile
**gate** that is *false-negative-only* by construction.

This document is the contract for the write-side spine, the gate's
false-negative-only guarantee, the plan/execute flow, the `bin/op` CLI, and how
a plan maps onto a gc bead payload.

Clean-room implementation of "The AST as LLM Lens" §5.5 (plan/execute pair),
§5.6 (compile gate, Alg. 2), and §3 (false-negative-only contract).

---

## 1. The shared write-side contract

The write-side is a Python package `astlens/` under the pack root. Four pieces
make up the contract; the spine owns the framework, and individual *ops* plug
into it.

### Ops — `astlens/ops/<name>.py`

Each op exposes **exactly** one function:

```python
def compute_change(file_path: str, args: dict) -> dict | None:
    ...
```

- Returns `{relpath: new_full_content}` for **every** file it changes, where
  `relpath` is relative to the repo root (the git root above `file_path`, else
  the file's own directory).
- Returns `None` when there is nothing to change, or it cannot do so safely
  (unreadable file, binary content, ambiguous edit).
- **Ops never write files.** They are pure functions from current state to
  proposed state. Writing is the exclusive job of `execute()`, and only after
  the gate accepts.

The spine ships one op, `astlens/ops/strip_trailing_ws.py` (the demo op, used
to prove the framework end-to-end across languages). The other ops
(`fix-imports`, `rename-symbol`, `extract-to-package`) are supplied by sibling
modules and registered defensively — an absent op module is skipped, never
fatal.

### Gate — `astlens/gate.py`

```python
def gate(changes: dict, repo_root: str) -> dict:
    # -> {"verdict": "accept" | "reject", "reason": str}
```

Materialises `changes` into a **temp copy** of the touched files, runs each
file's **native** syntax check, and accepts iff **all** pass. See §2.

### Plan / execute — `astlens/plan.py`

```python
make_plan(op, file_path, args)            -> dict
render_plan(plan)                          -> str   # five-section Markdown
execute(op, file_path, args, token)        -> dict  # {"verdict", "reason", ...}
```

See §3.

### Registry — `astlens/registry.py`

```python
resolve(name) -> compute_change            # lazy + cached; OpError if absent
available()   -> {name: bool}              # which op modules resolve right now
all_op_names() -> [str]                    # canonical order, present or not
```

Maps an op name to the backing module's `compute_change` with **guarded, lazy**
imports, so a missing op module never breaks the others. Resolving one op never
imports the rest.

---

## 2. The gate and its false-negative-only guarantee

The gate is the safety floor. Its job is **not** to prove a refactor is correct
— only to refuse to commit a change that would not even parse.

### The guarantee

From §3 (paper Def. "false-negative-only contract"):

> `gate(changes, root) == accept ⟹ the change does not corrupt valid programs.`

The contract is intentionally **asymmetric**:

- A **false negative** — the gate rejects a refactor that would in fact have
  worked — is an inconvenience the agent recovers from (it re-plans, perhaps
  with a smaller scope).
- A **false positive** — the gate accepts a refactor that silently breaks the
  program — is the failure mode we cannot tolerate, because it poisons the
  downstream task with a quietly-broken codebase.

Two design consequences follow, both enforced in `astlens/gate.py`:

1. **No checker ⟹ reject.** If no native checker is available for a file's
   language, the gate rejects. A language we cannot verify is, by the contract,
   a language we will not accept. (Concretely, `.ts`/`.tsx` reject when `tsc` is
   not on `PATH`; an unknown extension like `.rb` rejects; an extensionless
   file rejects; an empty change set rejects.) A checker that fails to launch,
   times out, or errors is likewise treated as "did not pass", never as a pass.

2. **The real tree is never touched.** The candidate is written under a fresh
   `tempfile.mkdtemp` scratch directory, checked there, and discarded after the
   verdict — so a reject leaves the disk untouched, and a checker that emits
   side artefacts (e.g. `py_compile`'s `.pyc`) lands in scratch. Even on
   *accept*, the gate writes nothing to the repo root; committing is `execute`'s
   job.

### Checker matrix

| Extension(s)                | Native check          | Status on a host with the tool |
| --------------------------- | --------------------- | ------------------------------ |
| `.py`                       | `python -m py_compile`| **VERIFIED** (uses the pack venv interpreter) |
| `.go`                       | `gofmt -e`            | **VERIFIED** if `gofmt` on PATH |
| `.js` `.jsx` `.mjs` `.cjs`  | `node --check`        | **VERIFIED** if `node` on PATH |
| `.ts` `.tsx`                | `tsc --noEmit`        | **VERIFIED** if `tsc` on PATH, else **REJECT** |
| _(any other extension)_     | —                     | **REJECT** (no checker) |

The `.py` check runs under the *same interpreter* that hosts the gate (the pack
venv), so the gate and the checker agree on the Python grammar version. Run
`bin/op --matrix` to print the live matrix for the current host (a missing `tsc`
flips `.ts`/`.tsx` to reject).

The native syntax check is the **floor**. The paper's opt-in LSP-diagnose step
for typed languages (a stronger, compile-aware gate) is out of scope for the
spine; its absence only ever makes the gate *stricter*, which the contract
permits.

---

## 3. The plan/execute flow

A compound op is exposed as a pair `⟨op, op!⟩` (§5.5). Planning is read-only;
the trailing `!` selects execute.

### `make_plan` → `render_plan`

`make_plan(op, file, args)` runs the op's `compute_change` against the
**current** file content, then runs the **real gate** against the proposed
change (in scratch — still no real writes) to predict the verdict.
`render_plan` produces the five-section Markdown the agent reads:

1. **Target** — op, file (absolute), repo root, args.
2. **Scope** — the relpaths that will change.
3. **Diff** — a `difflib` unified diff (old vs new) per file, fenced as
   ` ```diff `.
4. **Predicted verdict** — `ACCEPT`/`REJECT` from running the gate, with reason.
5. **Plan token** — the content-addressed hash (below) and the ready-to-run
   `bin/op <op>! <file> <token>` command line.

When the op declines, the plan is a clear "no change" plan: no token, no diff,
nothing executable.

### The plan token

```
token = sha256( op
                + for each changed relpath (sorted):
                      sha256(current bytes of that file)
                    + sha256(new content) )
```

The token is content-addressed over `(intent, every from-state, every
to-state)`. The sort makes it independent of dict iteration order. This is what
makes plans **stateless** — no server-side cookie, no session.

### `execute`

`execute(op, file, args, token)`:

1. Recomputes `compute_change` from the **current** file content and derives a
   fresh token.
2. **Token check, before anything else.** If the op now declines (nothing to
   change) or the fresh token ≠ the caller's token, it aborts:
   `{"verdict": "reject", "reason": "stale plan, re-plan ...", "written": []}`
   and **writes nothing**. The file changed since the plan was emitted — a real
   conflict, not a spurious one.
3. On a matching token, submits the change to the **gate**.
4. Writes the new contents to the **real files** iff the verdict is `accept`
   (returning `written` = the absolute paths). On reject, writes nothing.
5. Returns the verdict either way.

This ordering — recompute → token → gate → write — guarantees a drifted file
can never be committed against a stale plan, and a syntactically-broken change
can never reach disk.

### Why stateless (the trade-off)

A stateful plan with a server-side cookie would couple the agent to a session
and complicate multi-agent dispatch. The spine chooses statelessness on the
paper's principle: an LLM that has to re-plan because the file changed is
recovering from a *real* conflict, not a spurious one. The cost is a re-plan on
drift; the benefit is that **any** agent can emit a plan now and **any other**
agent can execute it later (see §5).

---

## 4. The `bin/op` CLI

`bin/op` is an executable wrapper that resolves the pack venv python (falling
back to system `python3`) and dispatches to `astlens.cli`.

```
bin/op <op>  <file> [--k v ...]          # print the PLAN (read-only)
bin/op <op>! <file> <token> [--k v ...]  # EXECUTE the plan (trailing ! = execute)
bin/op --list                            # list registered ops + availability
bin/op --matrix                          # print the gate's checker matrix
bin/op -h | --help                       # usage
```

- A trailing `!` on the op name selects execute (the `⟨op, op!⟩` pair).
- Generic `--k v` pairs become the op's `args` dict; a bare `--flag` with no
  following value means `flag=True`.
- **Exit codes:** plan mode exits `0` if the predicted verdict is accept, `3`
  if it is reject or there is nothing to do, `2` on usage/op-resolution errors.
  Execute mode exits `0` on accept, `3` on reject/stale, `2` on usage errors.
  This lets a script branch without parsing the Markdown.

### Worked example

```console
$ printf 'def f(x):   \n    return x  \n' > /tmp/smoke.py

$ bin/op strip-trailing-ws /tmp/smoke.py
# Plan: strip-trailing-ws
## Target
- op: `strip-trailing-ws`
- file: `/tmp/smoke.py`
- repo root: `/tmp`
## Scope
- 1 file changed (relative to repo root):
  - `smoke.py`
## Diff
```diff
--- a/smoke.py
+++ b/smoke.py
@@ -1,2 +1,2 @@
-def f(x):   
-    return x  
+def f(x):
+    return x
```
## Predicted verdict
- **ACCEPT** — all 1 touched file passed native syntax check
## Plan token
- `3f3ef543...b7853f3b1`
Execute with: `bin/op strip-trailing-ws! /tmp/smoke.py 3f3ef543...b7853f3b1`

$ bin/op strip-trailing-ws! /tmp/smoke.py 3f3ef543...b7853f3b1
ACCEPT — all 1 touched file passed native syntax check
  wrote /tmp/smoke.py
```

Re-running the same execute now reports `REJECT — stale plan, re-plan` (the file
is already clean), with exit code 3.

---

## 5. How a plan maps to a gc bead payload

The plan token mechanism is what lets the write-side ride gc's work-distribution
model. A plan is **stateless** and **content-addressed**, which gives an
emit-plan-now / execute-later workflow that any agent can pick up:

- **Emit-plan-now.** An agent (or a CI step) runs `bin/op <op> <file>` and
  captures the rendered plan. The plan is self-contained: it carries the
  intent, the scope, the human-readable diff, the predicted verdict, and the
  token. The entire payload of a bead can be just `(op, file, token)` plus the
  rendered Markdown for a reviewer — there is no session, no cookie, no
  server-side state to attach.

- **Execute-later, by any agent.** A different worker (the executor, or a
  human-approved follow-up) claims the bead and runs
  `bin/op <op>! <file> <token>`. Because the token is content-addressed over the
  file's from-state and to-state, the executor does **not** need to trust that
  the planning agent and the executing agent saw the same disk: if the file
  drifted in between, the token mismatches and the execute aborts with
  `stale plan, re-plan`, writing nothing. The bead is then re-planned rather
  than committed against stale state.

This is the same statelessness principle the read-side relies on: just as the
outline lens recomputes deterministically so the CLI, the hook, and the MCP
surface agree, the write-side recomputes deterministically so the planner and
the executor agree — or safely disagree. A plan is therefore a perfectly
shippable unit of work:

| Bead field         | From the plan                                  |
| ------------------ | ---------------------------------------------- |
| intent / title     | the op name (e.g. `rename-symbol`)             |
| target             | the file path (+ args)                         |
| commit token       | the 64-hex plan token                          |
| reviewer artefact  | the rendered five-section Markdown (the diff)  |
| predicted outcome  | the gate's `ACCEPT`/`REJECT` line              |

A reviewer agent (or human) approves the bead by reading the diff and the
predicted verdict; the executor commits it with a single content-addressed
call, and the compile gate is the final, non-bypassable check before anything
touches the tree.

---

## 6. Tests

`tests/test_write_spine.py` (run via the pack venv) covers the contract
end-to-end; fixtures live in `tests/write_fixtures/spine/`:

```console
$ .venv/bin/python -m pytest tests/test_write_spine.py -q
```

It asserts: the gate accepts clean changes (py/go/js); rejects syntax errors
(broken py/go/js); rejects when no checker is available (unknown ext,
extensionless, empty set, and `.ts` when `tsc` is absent); never writes the real
tree on accept or reject; the plan token detects drift (edit-after-plan aborts
"stale plan", writes nothing); execute writes iff the verdict is accept
(modified on accept, untouched on reject); the registry tolerates missing
sibling ops; and `bin/op` prints a plan and executes the demo op end-to-end.
