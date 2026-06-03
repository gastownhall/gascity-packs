# Refinery / merge-queue integration — a plan is a bead payload

The write-side spine (`docs/WRITE-SIDE.md`) emits a symbolic-edit **PLAN** as a
content-addressed, *stateless* unit: `bin/op <op> <file>` prints a five-section
plan with a 64-hex **token**, and `bin/op <op>! <file> <token>` re-derives the
change, verifies the token (aborts if the file drifted), runs the compile
**gate**, and writes only on accept. Statelessness is the whole point — a plan
can be **emitted now and executed later by a different agent**.

This document realises the paper's "a plan is a bead payload" idea (WRITE-SIDE
§5) against gc's actual merge machinery: a PLAN is filed as a **bead** and
executed — **gated** — through gc's normal merge path (the refinery /
merge-queue). It covers the bead-metadata convention, the `bin/apply-plan-bead`
helper, an end-to-end demo on a throwaway repo, the example formula, and exactly
what is a pack-level convention vs. what would need gc-side wiring.

Nothing here modifies gc-core or the spine. The integration is three new
pack-owned artifacts plus one optional example formula:

| Artifact | Role |
| --- | --- |
| `astlens/bead.py` | parse the convention; source metadata (live or JSON); invoke `bin/op` |
| `astlens/apply_plan_bead_cli.py` | CLI orchestration + `git add` staging |
| `bin/apply-plan-bead` | thin venv wrapper (mirrors `bin/op`) |
| `formulas/mol-apply-plan-bead.toml` | example formula: claim → gated apply → hand to refinery |

---

## 1. Why this works: the spine property the integration leans on

A plan-bead carries no diff that the executor has to *trust*. It carries an
**intent** (`op`), a **target** (`file`, repo-relative), and a content-addressed
**token**. On execute, `bin/op` recomputes the change from the *current* file and
re-derives the token:

- token matches → the file is exactly the from-state the plan was built against →
  gate it, write iff accept;
- token mismatches (file drifted) → **stale plan, re-plan**, write nothing.

So a plan-bead filed by agent A in one worktree can be executed by agent B
(another polecat, or a refinery) against B's own checkout, and a divergence
between the two is caught **deterministically** rather than silently re-applied.
The compile gate remains the final, non-bypassable check before any byte reaches
the tree. That is precisely the property that lets a plan ride a gc bead and be
landed through the merge queue.

---

## 2. The bead-metadata convention

A **plan-bead** is an ordinary gc work bead that additionally carries four
metadata fields under the reserved `gc.` namespace (alongside gc's own
`gc.routed_to`, so they read as clearly framework-owned and never collide with
the refinery's existing `branch` / `target` / `merge_strategy` reads):

| Metadata key | Value | Required | Notes |
| --- | --- | --- | --- |
| `gc.symbolic_op` | op name, e.g. `strip-trailing-ws`, `rename-symbol` | yes | **bare** name — no trailing `!` (the helper applies the execute selector) |
| `gc.op_file` | path to transform, **relative to the repo root** | yes | repo-relative so a plan filed in one worktree resolves in the refinery's checkout |
| `gc.op_token` | the 64-hex plan token from `bin/op <op> <file>` | yes | content-addressed over (intent, from-state, to-state) |
| `gc.op_args` | JSON **object** string of op args, e.g. `{"old":"a","new":"b"}` | no | absent ⇒ `{}`; flattened to `--k v` for `bin/op` |

`gc.op_file` is stored **repo-relative on purpose.** The token still pins the
file *content*, so if a relative path resolves to a drifted file the spine's
stale-plan check refuses it — a relative path can never cause a wrong-but-silent
write.

### How a polecat files a plan-bead

The same `gc bd update --set-metadata` mechanics the refinery already uses for
`branch` / `target`:

```bash
# 1. Emit the plan and capture the token (read-only — writes nothing):
PLAN=$(bin/op strip-trailing-ws greet.py)
TOKEN=$(printf '%s\n' "$PLAN" | awk '/^- `[0-9a-f]{64}`$/{gsub(/[`-]/,"");gsub(/ /,"");print;exit}')

# 2. File the plan as bead metadata (carry the merge fields too):
gc bd update "$WORK" \
  --set-metadata gc.symbolic_op=strip-trailing-ws \
  --set-metadata gc.op_file=greet.py \
  --set-metadata gc.op_token="$TOKEN" \
  --set-metadata gc.op_args='{}' \
  --set-metadata branch="plan/$WORK" \
  --set-metadata target=main
```

The bead's human-facing description can hold the rendered five-section plan (the
diff + predicted verdict) as the reviewer artifact, exactly as WRITE-SIDE §5
tabulates. The four `gc.*` fields are the machine-executable payload.

---

## 3. The helper: `bin/apply-plan-bead`

The executor any agent runs to apply a plan-bead, gated:

```
bin/apply-plan-bead <bead-id> [--repo DIR] [--stage|--no-stage] [--dry-run] [--gc-bin GC]
bin/apply-plan-bead --metadata-json @file.json|-   [--repo DIR] [...]
```

It is a thin venv wrapper (same shape as `bin/op`) over
`astlens/apply_plan_bead_cli.py`. In order, it:

1. **Sources the bead metadata** — from the live store via
   `gc bd show <id> --json` (default), or from an explicit JSON payload via
   `--metadata-json` (`@path` reads a file, `-` reads stdin, or inline JSON).
   The JSON path accepts the full `gc bd show --json` envelope *or* a bare
   metadata object, so it can be driven from a captured payload with **no live
   city** — that is the path the demo and CI use.
2. **Parses the convention** into a `PlanBead` (clear error on any missing /
   malformed field; a stored trailing `!` on the op is rejected).
3. **Runs the gated execute** by shelling out to
   `bin/op <op>! <abs-file> <token> [--k v ...]`. It does *not* import the spine's
   `execute()` directly — going through `bin/op` keeps recompute → token-check →
   gate → write-iff-accept in the spine as the single execute code path. `op_file`
   is resolved against `--repo` (default cwd); `gc.op_args` is flattened to the
   spine's `--k v` / bare-`--flag` form (faithful to `astlens.cli._parse_args`,
   values passed as separate argv elements so spaces/metacharacters are safe).
4. **Reports the verdict.** On **accept**, the spine has already written the
   file; the helper echoes it and `git add`s it (unless `--no-stage`) so the
   change is **staged for gc's normal merge**. On **reject / stale token**,
   nothing was written and the helper exits non-zero. Staging is best-effort
   *reporting* — a staging hiccup (e.g. not a git repo) is noted, never converts
   a successful gated write into a failure.

### Exit codes (mirror `bin/op` so a formula step can branch)

| Code | Meaning |
| --- | --- |
| `0` | **ACCEPT** — gate passed, file written by the spine, change staged |
| `3` | **REJECT** — gate rejected *or* stale token (drift); nothing written |
| `2` | usage / unreadable bead / malformed plan payload |

### Safety properties

- **Never writes on its own.** Every byte to disk is `bin/op`'s, behind the gate.
- **Self-contained, exits cleanly.** No daemon, no lock, no partial state. A
  `gc`-absent host fails with an actionable message pointing at `--metadata-json`.
- **Idempotent re-run is a no-op-or-reject.** Re-applying an already-applied plan
  re-derives "nothing to change" → the spine reports stale → exit 3, write
  nothing. The merge path is the source of truth for "did this land".

---

## 4. End-to-end demo (throwaway repo, gate accepts; stale token refused)

Run on a fresh `git init` repo under `/private/tmp` (**not** the live city; the
demo files no real beads — it hands the plan metadata to `apply-plan-bead` via
`--metadata-json`, so the live store is never touched). `$REPO` is the temp repo.

### A) Emit the plan (read-only)

````console
$ bin/op strip-trailing-ws greet.py
# Plan: strip-trailing-ws
## Target
- op: `strip-trailing-ws`
- file: `$REPO/greet.py`
- repo root: `$REPO`
## Scope
- 1 file changed (relative to repo root):
  - `greet.py`
## Diff
```diff
--- a/greet.py
+++ b/greet.py
@@ -1,2 +1,2 @@
-def greet(name):   
-    return f"hi {name}"  
+def greet(name):
+    return f"hi {name}"
```
## Predicted verdict
- **ACCEPT** — all 1 touched file passed native syntax check
## Plan token
- `cfa6b17284f7c435b2e0b649b0e9f0b131ffca0168a727b2630595e21cf10352`
````

### B) File the plan-bead (what a polecat runs against the live store)

```console
$ gc bd update $WORK \
    --set-metadata gc.symbolic_op=strip-trailing-ws \
    --set-metadata gc.op_file=greet.py \
    --set-metadata gc.op_token=cfa6b172…1cf10352 \
    --set-metadata branch=plan/$WORK --set-metadata target=main \
    --assignee $RIG/refinery
```

### C) Executor runs the gated apply — ACCEPT

```console
$ bin/apply-plan-bead demo-1 --repo $REPO      # demo: --metadata-json @pb.json
plan-bead metadata payload: op=strip-trailing-ws file=greet.py
  token cfa6b17284f7c435b2e0b649b0e9f0b131ffca0168a727b2630595e21cf10352
ACCEPT — gate passed; file written by the spine
  wrote $REPO/greet.py
  staged $REPO/greet.py

$ git status --short
M  greet.py               # staged (index column 'M'), ready for the merge

$ git diff --cached --stat
 greet.py | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)
```

The trailing whitespace is gone, the change is **staged** for gc's normal merge.

### D) Rejected case — the file drifts, the same plan is now stale

```console
# someone edits greet.py after the plan was filed (adds a comment line)
$ bin/apply-plan-bead demo-1 --repo $REPO      # token no longer matches the file
plan-bead metadata payload: op=strip-trailing-ws file=greet.py
  token cfa6b17284f7c435b2e0b649b0e9f0b131ffca0168a727b2630595e21cf10352
REJECT — plan not applied (stale token or gate rejected); nothing written
  | REJECT — stale plan, re-plan (file changed since the plan was emitted)
exit: 3
# greet.py is byte-identical after the rejected apply (nothing written).
```

### What the demo proved

- A PLAN emitted by `bin/op` was filed as bead metadata and **executed later** by
  a separate `apply-plan-bead` invocation — the emit-now / execute-later split.
- On a matching token the **compile gate accepted**, the file was transformed,
  and the change was **`git add`-staged for the normal merge** (`M ` in the
  index) — not committed or merged by the helper.
- A **drifted file (stale token) was refused**, exit `3`, and the file was left
  **byte-for-byte unchanged** — no corruption, no partial write.
- A **malformed plan-bead** (missing `gc.op_file` / `gc.op_token`) exits `2` with
  an actionable message; `--dry-run` prints the exact `bin/op` command without
  executing. (Both exercised; see §6.)

The Go file in the broader demo (`main.go` with trailing whitespace) accepted
identically via `gofmt -e`, confirming the integration is language-agnostic —
it inherits the spine's full checker matrix for free.

---

## 5. Where it joins the merge queue, and the example formula

The integration deliberately **does not reimplement the merge.** A plan-bead
rides the *existing* path the refinery already runs (`mol-refinery-patrol`,
`gastown/agents/refinery`): polecats push a branch, set `branch` / `target`
metadata, assign the bead to the refinery; the refinery rebases, runs checks,
fast-forward-merges, closes the bead. The plan-bead adds one step *before* that
handoff — the gated apply — and is otherwise an ordinary work bead.

The canonical flow:

```
polecat:  bin/op <op> <file>            → emit PLAN (token)
polecat:  gc bd update --set-metadata gc.symbolic_op/op_file/op_token (+ branch/target)
executor: bin/apply-plan-bead <bead>    → GATED execute; on accept stage the change
executor: git commit + git push <branch>; assign bead to refinery
refinery: mol-refinery-patrol           → rebase, checks, ff-merge, close   (UNCHANGED)
```

`formulas/mol-apply-plan-bead.toml` encodes the **executor leg** as a four-step
graph.v2 formula so the flow is reproducible and auditable:

1. `claim-plan-bead` — claim the bead, read `gc.symbolic_op` / `op_file` /
   `op_token`; reject to pool if it is not a plan-bead.
2. `branch` — create `plan/$WORK` from a fresh `origin/<target>`, record
   `metadata.branch` / `metadata.target`.
3. `apply-gated` — run `bin/apply-plan-bead "$WORK"`; branch on the exit code
   (0 → commit; 3/2 → reject the bead back to the pool with a `rejection_reason`,
   delete the branch, stop). **A stale or rejected plan never reaches the
   refinery.**
4. `commit-and-handoff` — commit the staged change, push the branch, assign the
   bead to the refinery (`${GC_RIG:+$GC_RIG/}<prefix>refinery`, clear
   `gc.routed_to`), detach. The refinery lands it normally.

Choosing a **polecat** (not the refinery) as the executor is what keeps the
refinery's CARDINAL RULE intact ("merge processor, not a developer" — it never
runs application transforms). The plan-bead arrives at the refinery already
committed on a branch, indistinguishable from any other work bead; the
`gc.symbolic_op` / `gc.op_token` fields remain on the closed bead as the forensic
record of *which content-addressed plan* was landed.

---

## 6. Pack-level convention vs. gc-side wiring

**Everything functional is pack-level and works today** against an unmodified gc:

- The four-field metadata convention uses only `gc bd update --set-metadata` and
  `gc bd show --json`, which gc already provides. The refinery's existing
  `branch` / `target` / `merge_strategy` reads are untouched and coexist.
- `bin/apply-plan-bead` shells out to `gc bd show` and `bin/op` — no gc-core
  hook, no new gc API. It runs from any agent session (or a human shell, or CI
  via `--metadata-json`).
- The handoff to the refinery is an ordinary `gc bd update --assignee` — the
  same assignment the polecat formula already performs. **No refinery change is
  required**; a plan-bead landed by a polecat looks like any other work bead.

**Optional, to make the example formula discoverable** (one config step, no
gc-core change):

- `formulas/mol-apply-plan-bead.toml` must be on the city's formula search path
  for `gc bd mol wisp mol-apply-plan-bead` / `gc sling … --formula
  mol-apply-plan-bead` to resolve it. gastown's formulas live under
  `.gc/system/packs/gastown/formulas/`; this pack ships its formula under
  `packs/ast-lens/formulas/`. Wiring options, lowest-touch first:
  1. **Sling/cook by no path** — until the search path includes the pack dir,
     the executor leg can be driven directly: an agent just runs
     `bin/apply-plan-bead "$WORK"` (the formula is documentation of that flow,
     not a hard dependency). The convention works with zero formula wiring.
  2. **Add the pack `formulas/` dir to the city's formula search path** (city
     config), so the formula is poured like any gastown formula. This is config,
     not code.
  3. Copy the formula into the gastown `formulas/` dir if you want it available
     city-wide without a search-path change.

**What would need a genuine gc-core / formula change (explicitly out of scope
here, listed for completeness):**

- **An apply-capable refinery variant** that runs `apply-plan-bead` *inline*
  (skip the polecat executor leg) would need a new refinery formula branch that
  detects `gc.symbolic_op` on an assigned bead and runs the gated apply before
  the rebase. That edits `mol-refinery-patrol` (or adds a sibling), which the
  task forbids touching. The polecat-executor design above avoids it entirely
  and is the recommended path.
- **Auto-routing plan-beads to an executor pool** via `gc.routed_to` would be a
  city routing-config addition (point a `gc.routed_to=<rig>/<prefix>polecat` at
  the pool), not a code change — the metadata field already exists; only the
  routing rule is config.

In short: the **convention + helper + demo are fully working pack-level code on
stock gc**; the only thing beyond the pack is a one-line formula-search-path
config if you want `mol-apply-plan-bead` poured by name, and `apply-plan-bead`
already works without it.
