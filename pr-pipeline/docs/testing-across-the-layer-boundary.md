# Testing across the layer boundary

A fix's test must fail on the unfixed **live build** and pass on the fixed live
build, with the fix as the only difference.

Everything in this document is in service of that one sentence. The common
failure in this stack is a patch that does exactly what it says, proves it with
a test that genuinely passes, and leaves the reporter's machine unchanged.

This is the review material behind `mol-pr-review` and `mol-pr-ship`. Read it
as the reasoning; the formulas are the checklist.

---

## The failure this exists to stop

Two worked examples, both real bugs, both public: `gastownhall/gascity` issues
**#5333** (`gc start` treats a supervisor reload timeout as fatal before the
readiness check) and **#5324** (`gc supervisor stop` can report success while
launchd remains able to restart the supervisor). Neither report, as written,
establishes that fixing it fixes the machine it was found on.

**#5333 has an executable that asserts the wrong thing.** The reproducer drives
`registerCityWithSupervisor` directly and replaces five seams:
`ensureSupervisorRunningHook`, `reloadSupervisorHook`, `supervisorAliveHook`,
`waitForSupervisorCityHook`, `cityControllerURLHook`. The report says plainly
why it had to. The real path "can regenerate or install platform supervisor
service files before liveness checks on macOS," so the test stubbed exactly the
boundary the bug lives on. What it proves is a claim about the stub graph: given
a `reloadSupervisorHook` that returns 1 and writes a particular string to
stderr, the caller now treats it as an async start. Whether the *real* macOS
reload returns 1, and writes that string, on a genuine timeout is a separate
claim, it is the load-bearing one, and nothing in the report establishes it. If
the real path returns 2, or a different message, the fix is correct in the test
and inert in the build.

**#5324 asserts the right thing and has no executable.** Its stated
postcondition is about the world, not the return value: `gc supervisor stop
--wait` "should leave the machine supervisor durably stopped, or fail if it
cannot prove that launchd will not restart it." That is the correct shape. Its
reproduction is a "best-effort reproduction shape" in prose, and its evidence
was withheld for a reason the reporter names: the logs "include machine-specific
paths and session identifiers."

Between them they name the two halves of the problem. A test can be runnable, or
it can be about the live system. Reports keep getting accepted that are only the
first.

---

## 1. Push the test to the outermost tier where the bug still reproduces

| Tier | What is real | What is fake |
|---|---|---|
| **T1** | the installed binary, the real platform service (launchd/systemd), a real store | nothing |
| **T2** | the real `gc` binary, real `bd`, real dolt, a throwaway city in a temp dir | the work, the repos |
| **T3** | in-process, real collaborators wired together | the environment |
| **T4** | in-process, seams replaced by hooks | the collaborators |

Both issues above sit at T4. That is the tier where a green result carries the
least information, and it is the tier the test hooks make easiest to reach.

**If a bug reproduces only at T4, you have not reproduced the bug. You have
reproduced a stub.** Move up until it stops reproducing. The last tier where it
still does is where the test belongs.

`test/acceptance/` and `test/qualification/` in `gastownhall/gascity` are the T2
tier and already exist; `test/acceptance/beads_cli_contract_test.go` is the
shape to copy. Reaching for a hook when a T2 harness exists is the specific move
to stop.

## 2. Every stub carries its fidelity claim, in the PR body

For each seam the reproducer replaces, the PR states the real behavior it stands
for and the evidence they match. "The real `reloadSupervisorHook` exits 1 and
writes `reconcile did not finish before timeout` to stderr on macOS timeout;
verified by `<command>`" is a reviewable sentence. Its absence is where the
fixes-the-reproducer-not-the-build failure lives, every time.

A reviewer who cannot find that sentence has found the finding.

## 3. Assert the postcondition, not the report

A test that checks the function returned success is testing the report. A test
that checks launchd no longer holds a restartable job is testing the world.
`success: true` is an exit line, not an outcome.

## 4. Kill the fix, and then kill the stub

Reverting the fix must turn the test red. That is necessary and it is weak: it
shows only that the stub graph is sensitive to the change. The second mutation
is the one that matters. Perturb each stub toward a plausible alternative real
behavior (a different exit code, a reworded message, an extra call) and see
whether the test still distinguishes fixed from unfixed. A test that survives
every such perturbation is not measuring the seam it claims to.

The same discipline applies to any guard you add: prove it can go red by
removing the exact thing it exists to catch, then restore. A guard that has
never been seen red is a guard nobody has tested.

## 5. For an environment-specific bug, ship a probe, not a city

Cities cannot be passed back and forth, which is usually where the conversation
stops. Something smaller can travel: a **diagnostic the reporter runs**,
emitting a scrubbed, machine-produced transcript with versions of `gc`,
`bd` and dolt, the platform service state, and the exact command output at the
failing step, with home paths, hostnames and session identifiers redacted at
the source.

That solves both halves of #5324 at once. The reporter wanted to give evidence
and could not do so safely; a probe that scrubs by construction yields a real
reading of a real environment and keeps their paths out of a public issue. The
bug report then contains an observation instead of a repro shape.

---

## The layer map

Four layers. Each row is what the layer owns, where its contract with the layer
above is written down, and what actually enforces it.

| Layer | Owns | Contract specified in | Enforced by |
|---|---|---|---|
| **dolt** | storage engine, SQL surface, version history | upstream | a pinned version in `deps.env` |
| **beads** (`bd`) | work records, claim/lease/fence, `--json` wire shapes, exit codes, `schema_version` | `engdocs/design/beads-dolt-contract-redesign.md` | nothing cross-repo |
| **gascity core** (`gc`) | cities, rigs, sessions, the supervisor, formulas, and the `bd` subprocess consumer (roughly 20 subcommands, parsed into a fixed struct, behavior keyed off exit codes and free-text error strings) | `engdocs/design/beads-gascity-contract-test-system.md` | Phase 0+1 only |
| **packs** | agents, commands, services, formulas, skills, hooks, template fragments, composed via `pack.toml` imports | `docs/reference/specs/pack-spec.md`, `engdocs/design/packv2/` | `gc lint` on 5 of 16 registry packs |

**The boundary is specified in four places and gated end to end in none.** Every
drift incident catalogued so far lives in the gap between a written contract and
an executed one.

`engdocs/design/beads-gascity-contract-test-system.md` (Proposed, 2026-06-24)
already diagnosed this for the `bd` to `gc` edge and catalogued **28 historical
drift incidents**, dominated by version-gated code that CI never exercises. Its
Phase 0+1 landed as `3f45f30aa` (gascity #3714). The cross-version matrix that
was the actual gate did not.

**Which layer owns your bug** decides where the fix goes and which repo's tests
must move:

- A wire shape, exit code or `--json` field changed under you: beads.
- `gc` mis-parsing a shape beads still emits correctly: gascity core.
- A workflow, prompt, formula or command behaving wrongly while `gc` behaves
  correctly: your pack.
- A pack needing something `gc` cannot express: a request for a new
  declaration in core, not a special case (see below).

## The interaction effect, and how not to make core bespoke

A pack expresses one user's particular system. Core must serve it without
learning about it. The test for whether a fix crossed that line:

> **Does the fix add a branch that names a pack, or a capability the pack
> declares and core validates generically?**

The first is bespoke and accrues forever. The second is what `gc lint` and the
packv2 conformance work are for: the pack *declares* its requirement, core
*checks* the declaration, and the check is the same code for every pack. A pack
that needs something core cannot express is a request for a new declaration, not
a new special case.

Prefer content-based discovery over hand-maintained lists on both sides. A check
that walks every `*.json` carrying an `oauth_config` key keeps working when a
pack adds a second manifest; a check that reads a list of paths silently skips
it.

## Where this stack currently fails its own advice

Re-derived on `gastownhall/gascity-packs` 2026-08-17, from the CI lint loop and
`registry.toml` (issue **#307** reports the same defect with a count of 10; the
list below is 11 because `profiler`, which CI does lint, is not a registry
pack): **11 of the 16 registry packs are never exercised against a running
`gc`**: `cass`, `contributing`, `discord`, `gastown`, `github`, `oversight-rig`,
`pr-pipeline`, `runtime-cloudflare`, `slack-channel`, `slack-full`,
`slack-mini`. The five CI does lint are `bmad`, `compound-engineering`,
`gascity`, `gstack` and `superpowers`. Several of the eleven have
their own pytest or Go suites, which test the pack's logic against the pack's
own fixtures. Nothing stands them up against a `gc` that has moved since the
pack was last touched, and `registry.toml` carries no support-tier or
last-validated-version field, so a user reading it cannot tell an exercised pack
from an unexercised one.

That is the same failure as #5333 at a different scale: a green suite that is
about the artifact's fixtures rather than the system it runs in.

A sharper instance, found in this repo's own suite on 2026-08-17: several pack
test suites were green in CI and red on every machine actually running Gas City.
A live agent seat exports `GC_API_BASE_URL`, `GC_TEMPLATE`, `BEADS_ACTOR` and
others into every child process, at a higher precedence than a fixture's own
`city.toml`. CI runners export none of them. The suites passed for a reason
unrelated to the code under test, which is the failure this whole document is
about, reproduced inside the tooling that is supposed to catch it. The fix is in
`discord/tests/`, `github/tests/` and `gascity/tests/`: strip the pack's own
environment prefixes in `setUp`, build subprocess environments from a filtered
copy rather than `os.environ`, and add an AST guard that fails when a module
starts reading a variable outside the stripped prefixes.

---

## What a reviewer asks

Five questions, in order. Any "no" is the review comment.

1. What tier is the test at, and does the bug reproduce at a higher one?
2. For each stub: what real behavior does it stand for, and what verified it?
3. Does the assertion name a state of the world, or a return value?
4. Reverting the fix turns it red, and does perturbing each stub break the
   discrimination?
5. If the bug is environment-specific, is there a probe the reporter can run?

---

## Refuting commands

Every number above is re-derivable. Resolve anchors at time of use rather than
trusting a pinned line number.

`$GASCITY` is a checkout of `gastownhall/gascity`, `$PACKS` a checkout of
`gastownhall/gascity-packs`.

```sh
# the five stubbed seams in #5333
gh issue view 5333 --repo gastownhall/gascity --json body \
  | grep -oE '[a-zA-Z]+Hook = ' | sort -u

# the 28 drift incidents and the design's status (still "Proposed")
sed -n '1,40p' "$GASCITY/engdocs/design/beads-gascity-contract-test-system.md"

# which packs CI actually lints against a running gc. The loop body is
# `"$GC_BIN" lint "$pack"`, so grepping for the literal `gc lint` finds nothing.
grep -n 'lint "\$pack"' -B4 "$PACKS/.github/workflows/ci.yml"

# registry packs never exercised against a running gc. Set the second list
# from the loop above; `profiler` appears there and is NOT a registry pack,
# which is how the count of 10 in #307 came out one short.
cd "$PACKS" && comm -23 \
  <(grep -A1 '^\[\[pack\]\]' registry.toml | grep 'name =' \
      | sed 's/.*= //' | tr -d '"' | sort) \
  <(printf '%s\n' gascity bmad compound-engineering gstack superpowers profiler \
      | sort)

# pack maintenance recency
cd "$PACKS" && for p in pr-pipeline slack-full slack-mini slack-channel oversight-rig; do
  printf '%-16s %s\n' "$p" "$(git log -1 --format='%ad %s' --date=short -- "$p")"
done
```
