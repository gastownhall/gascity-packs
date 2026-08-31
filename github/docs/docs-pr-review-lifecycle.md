# GitHub Docs PR Review Lifecycle Contract

This contract defines when a GitHub Intake installation may advertise the
`Gas City / docs-impact` capability. It is deliberately independent of a
container scheduler, network topology, worker implementation, or City
deployment. A deployment that cannot satisfy every requirement below must
leave the capability disabled.

## Enablement

Enable docs PR review only after one installation has all four components
sharing durable run storage:

1. **Webhook intake** accepts opted-in `pull_request` deliveries, authenticates
   them, and creates or adopts a run before returning. It creates exactly one
   in-progress GitHub Check Run for that run.
2. **Reviewer dispatcher** gives a City reviewer the immutable assignment. It
   may use any queue or City entrypoint, but must preserve the assignment
   identity and lease recorded on the run.
3. **Candidate bridge** accepts only a candidate validated against that exact
   immutable assignment. The reviewer and bridge need no GitHub credentials.
4. **Reconciler** runs independently of webhook delivery and reviewer process
   lifetime. It scans every non-terminal run, re-dispatches expired leases,
   and completes eligible Check Runs.

The installation owns scheduling, process supervision, storage, and reviewer
selection. Those are deployment choices, not pack configuration. The webhook,
dispatcher, bridge, and reconciler may be one process or several, but they
must remain independently recoverable; a successful webhook response alone is
not enablement.

## Opt-in reviewer and scheduling

The pack ships the credential-free `docs-impact-reviewer` agent. A dispatcher
may select it only for an immutable `github-pr-docs-impact-assignment`; its
sole result is a validator-compatible documentation-impact decision. It cannot
publish GitHub results or create a proposal. The trusted candidate bridge and
projection boundary retain those responsibilities.

Use the runtime command as one-shot work under the installation's own event
and scheduling mechanism. For each accepted pull-request assignment, invoke:

```bash
python3 github/scripts/github_intake_docs_review_commands.py intake --once \
  --assignment-file <assignment.json> --projection action-file \
  --actions-file <actions.json>
```

Schedule an independent recurring invocation for recovery:

```bash
python3 github/scripts/github_intake_docs_review_commands.py reconcile --once \
  --projection action-file --actions-file <actions.json>
```

After the reviewer result has passed the candidate bridge, invoke:

```bash
python3 github/scripts/github_intake_docs_review_commands.py \
  candidate --once --candidate-file <candidate.json> --projection action-file \
  --actions-file <actions.json>
```

With `action-file` projection, the command records action intents; the
installation chooses how to consume them and how to provide the trusted
projection adapter.

## Immutable run identity

Each run is keyed by the repository ID, pull-request number, and head SHA.
The key is never reused for a later revision. Persist at least the key, Check
Run ID or external ID, creation time, deadline, dispatch attempt, lease expiry,
and terminal conclusion.

Duplicate webhook deliveries load that same record. They do not create another
Check Run or another independent review. A head change makes the old record
stale: before publishing a non-stale result, the reconciler confirms that the
current PR head still equals the stored SHA. A stale record completes only as
stale by updating its already-created Check Run on the old SHA; it never
publishes a candidate for the new revision.

## Dispatch and recovery

Intake records the run and its visible in-progress Check Run before dispatch.
Dispatch is at-least-once: a lease prevents unnecessary parallel work, but a
reconciler re-dispatches the same immutable assignment when that lease expires.
It does not create a new Check Run, source identity, or revision record.

Candidate delivery is also at-least-once. The bridge persists the first valid
candidate bound to the run identity. The reconciler validates it again before
terminal publication. A candidate with another identity is ignored. A valid
candidate produces one terminal conclusion: `success` for `no-impact` and
`docs-sufficient`; `action_required` for every other accepted verdict.

At the deadline, a non-terminal run completes `action_required` with an
operational reason. A candidate that arrives after that terminal transition is
recorded only if useful for audit, and cannot reopen or overwrite the Check
Run. This turns restart, duplicate delivery, and late work into convergence
rather than a permanently in-progress check.

## Adapter obligations

Adapters execute the actions emitted by
[`github_docs_pr_review_lifecycle.py`](../scripts/github_docs_pr_review_lifecycle.py):

- `ensure_check` creates or adopts the Check Run by a durable external ID.
- `dispatch` sends the already-persisted immutable assignment.
- `ensure_terminal_check` completes or adopts a non-stale terminal Check Run,
  after the current-head check.
- `ensure_stale_check` completes or adopts the already-created stale Check Run
  on its stored SHA. It must not require the current-head check.

Persist the transitioned run before performing an external action, and make
each action idempotent. The `ensure_*` actions are deliberately emitted again
for persisted runs: after a crash between persistence and an external write, a
later reconciliation adopts the existing GitHub Check Run by external ID or
performs the missing write. The pack does not prescribe a database, queue,
scheduler, or retry interval.

The credentials that create and update Check Runs are confined to the trusted
intake/reconciler boundary. This lifecycle contract governs only Check Run and
dispatch state. A separate authority-gated projection capability may create a
bot-owned follow-up branch and pull request; lifecycle itself does not
authorize GitHub issue, comment, pull-request, branch, or deployment mutations.

## Verification

Run the lifecycle model tests with:

```bash
python3 -m unittest github.tests.test_docs_pr_review_lifecycle -v
```

They prove the pack-level transitions for duplicate delivery, lease recovery,
late candidates, and once-only terminal completion. A deployment enabling the
feature must additionally exercise its concrete adapters against a test GitHub
Check Run and durable-store restart.
