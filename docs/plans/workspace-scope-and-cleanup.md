# Workspace Reuse and Cleanup Plan

## Goal

Reuse one worktree for each co-located implementation unit instead of creating a
new worktree for every drained step.

Workspace ownership is derived from the implementation graph:

- an implementation convoy with no epics owns one worktree;
- an implementation convoy with epics uses one worktree per epic;
- every runnable item in the same owner reuses that owner's worktree.

There is no public workspace-scope selector. Agent session context and workspace
ownership remain independent.

## Scope

This change is limited to workspace ownership, sequential reuse, and successful
cleanup.

Reuse the existing:

- formula and drain boundaries;
- host-local workspace command;
- common-Git state root;
- managed worktree path behavior;
- file locking;
- repository, worktree registration, detached-HEAD, and cleanliness checks.

Do not add a result ledger, service, lease, fence, TTL, garbage collector,
cross-host protocol, distributed transaction, telemetry, force deletion,
destructive repair, review/publish integration, or compatibility layer.

Commits and beads remain the durable implementation record. Workspace command
state is transient bookkeeping for a local worktree.

## Existing Boundary

This checkout contains every required boundary: pack formulas, workflow prompts,
the bead graph exposed through `gc bd`, and the host-local workspace command.

Relevant pack files:

- `gascity/formulas/implement.formula.toml`
- `gascity/formulas/do-work.formula.toml`
- `gascity/commands/workspace/run.sh`
- `gascity/commands/workspace/help.md`
- `gascity/commands/workspace/command.toml`
- `gascity/tests/test_workspace_script.py`
- the focused formula and workflow-asset tests

Separate drain may continue creating one full `do-work` child workflow per leaf
member. The workspace command's per-owner lock and state serialize preparation
and handoff locally; no renderer or dispatcher change is required.

## Automatic Workspace Ownership

The user does not select workspace scope and workflow prompts do not pass a
scope override.

`run.sh` derives the immutable owner directly from existing graph data:

1. resolve the claimed step's workflow root and source anchor as today;
2. read the source anchor's `parent_convoy_id`;
3. use that parent convoy as the workspace owner;
4. read the owner's own `parent_convoy_id` only to classify it:
   - empty parent: top-level convoy owner;
   - non-empty parent: nested convoy/epic owner;
5. fail closed on missing, malformed, or ambiguous graph identity.

No new metadata protocol or user-facing selector is introduced. `run.sh` does
not accept `--scope-kind`, `--scope-id`, an arbitrary state path, or an arbitrary
worktree path.

Every workspace action validates that the current graph-derived owner matches
existing transient state and that the claimed source anchor is the current item
when the action requires it.

## Workspace Identity and Transient State

Derive the state file, lock, and worktree name from:

```text
common Git repository identity + workspace owner kind + workspace owner ID
```

Including the kind prevents identical convoy and epic ID text from colliding.
Keep state beneath the existing common-Git state root and preserve the current
worktree-parent behavior.

The local state contains only what is needed to validate and hand off the
checkout:

```text
repository identity
workspace_owner_kind
workspace_owner_id
worktree_path
current_item = {
  source_anchor_id,
  input_oid,
  phase,
  output_oid
}
```

Valid phases are the existing preparation/entry/result phases or direct renamed
equivalents. A completed current item retains its output OID until the next item
enters or cleanup succeeds.

This state is not authoritative after acceptance and is not a historical result
store.

## Prepare and Reuse

Use the existing `prepare` action. Do not add a general lifecycle transition.

### First item for an owner

When no state or worktree exists for the derived owner:

1. resolve the supplied input ref to a commit;
2. create the detached worktree using the existing safe path behavior;
3. record that item as current;
4. return the authoritative worktree path and input OID.

### Replay of the current item

An exact replay succeeds only when the owner, source anchor, input OID, state,
path, worktree registration, and Git facts match. Conflicting replay fails
without mutation.

### Next item for the same owner

`prepare` is the owner lane: a different item waits while current owner state is
active and advances atomically only after the current item records a result.

`prepare` may replace completed item A with item B only when:

- A is in the completed/result phase with an output OID;
- the worktree is registered to the expected repository;
- the worktree is detached and clean, including no untracked files;
- `HEAD` equals A's recorded output OID;
- B resolves to the same workspace owner. Its launch input is advisory after the
  first item; the previous recorded output becomes B's authoritative input.

After those checks, retain the worktree path and record B as current. Never
replace an active or incomplete item. On any mismatch, retain the state and
worktree and fail closed.

This supports a linear commit chain within each owner. Different epic owners use
different worktrees and may be scheduled independently.

## Existing Actions and Results

`path`, `verify-entry`, `record-result`, and `result` continue to operate on the
claimed current item.

- `verify-entry` requires the expected clean detached input checkout.
- `record-result` records the current clean detached output commit.
- `result` returns the current item's exact source anchor, input OID, output OID,
  and worktree path for source-anchor close.
- Unknown or previous items cannot read the current item's transient result.

The existing bead and commit boundary persists each accepted item before the
owner lane advances. Historical lookup after that point is not a
workspace-command responsibility.

## Pack-Local Serialization

`prepare` holds the derived owner's state lock while validating or advancing the
workspace. If another item is active, it waits and retries. Once the current item
has recorded a clean result, the next item atomically becomes current and uses
the recorded output OID as its input. Different owners use different locks and
worktrees, so they may proceed independently.

This is local serialization only. A failed or interrupted active item retains
state and blocks later items for that owner rather than permitting unsafe reuse.

## Cleanup

Add `cleanup-if-complete` to the workspace command and invoke it from the
existing close-source-anchor prompt after that prompt closes and verifies its
exact source anchor.

The action queries existing beads, selects every direct source member whose
`parent_convoy_id` equals the derived owner, and requires all of them to be
`status=closed` with `gc.outcome=pass`. Earlier successful items return
`cleanup=retained`. The last successful item validates completed result state,
the clean detached output, and exact worktree registration, then removes the
worktree without force and deletes transient state. Malformed or ambiguous graph
data fails closed.
Removal uses `git worktree remove` without `--force` and deletes transient state
only after removal succeeds.

If validation or removal fails, retain the worktree and state and report the
path and reason. Session exit is not a cleanup trigger.

If both the derived state and derived worktree are already absent, repeated
cleanup succeeds as an already-completed no-op. If only one exists or facts are
ambiguous, fail closed.

## Pack Changes

Update only behavior directly affected by owner derivation, reuse, and cleanup:

- workspace command implementation, help, manifest description, and focused
  tests;
- close-source-anchor prompt wiring for `cleanup-if-complete`;
- `implementation-base` and `do-work` prepare/implement/close wording where it
  currently assumes one worktree per item;
- focused requirements and README text that documents this command behavior.

Do not change same-session/shared drain behavior, review/fix, publish/PR, remote
operations, or unrelated formulas.

## Tests

### Workspace command tests

Cover:

1. first item creates one owner worktree;
2. two sequential items with the same convoy owner reuse the same path;
3. two sequential items with the same epic owner reuse the same path;
4. different owner IDs and different owner kinds do not collide;
5. exact current-item replay succeeds and conflicting replay fails;
6. next input must equal the completed current `HEAD`;
7. active, dirty, untracked, attached, wrong-HEAD, wrong-owner, path-substituted,
   and registration-substituted reuse fails without mutation;
8. `result` works for the current completed item and rejects a previous or
   unknown item;
9. safe cleanup removes the registered worktree and transient state;
10. unsafe or failed cleanup retains both and never uses force;
11. repeated cleanup with both derived artifacts absent is harmless; an
    ambiguous partial absence fails closed.

### Formula and workflow tests

Prove:

- no public workspace-scope selector or new owner metadata protocol exists;
- workspace ownership is derived from existing `parent_convoy_id` graph fields;
- prompts use the existing workspace actions;
- source-anchor close reads the current item's exact result, closes and verifies
  that exact anchor, then invokes `cleanup-if-complete`;
- same-session/shared drain behavior is unchanged.

## Acceptance

The change is complete when:

1. a convoy without epics uses one worktree for its serialized implementation
   items;
2. a convoy with epics uses one worktree per epic;
3. items sharing an owner form a verified linear commit chain in one worktree;
4. different owners cannot collide;
5. accepted results remain durable in existing beads and commits, independent of
   transient workspace cleanup;
6. the command lock prevents overlapping owner handoffs while different owners
   remain independent;
7. the last successful direct member removes the owner worktree and transient
   state;
8. failed, dirty, interrupted, incomplete, or ambiguous workspaces are retained;
9. cleanup never uses force;
10. no unrelated lifecycle or architecture is introduced.
## Review Gate

Reject an implementation that:

- adds a user-selected workspace scope;
- creates a host-local historical result ledger;
- permits overlapping writers for one owner;
- lets prompts or agents own cleanup;
- cleans an unsuccessful or incomplete owner;
- force-removes or destructively repairs a worktree;
- changes same-session/shared drain behavior;
- introduces a new scheduler, service, lease, garbage collector, or cross-host
  protocol.
