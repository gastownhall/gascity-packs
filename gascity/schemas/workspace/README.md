# Workspace records

The base pack defines version 1 JSON records for source lifecycle state and a
read-only validator. These contracts bind run identity, source OIDs and evidence
for later workflow writers. Existing formulas still use their current lifecycle;
this package does not provision workspaces, write Beads metadata, advance a
chain, enforce locks or authorize publication.

## Validate

From the base pack directory:

```sh
python3 assets/scripts/workspace_records.py \
  --kind member-result --path /absolute/path/member-result.json
```

Success prints JSON with `ok`, `kind`, the ordered logical `identity` and the
canonical payload's `sha256`. Invalid records exit 1 with an error on stderr.
Invalid CLI arguments exit 2. `--stored /absolute/path/existing.json` additionally
requires an exact replay. The command reads files and makes no store or Git calls.
It uses `jsonschema`, already required by this repository's Python test CI.

[records.v1.json](records.v1.json) is a JSON Schema 2020-12 bundle whose `oneOf`
validates the nine record shapes. A caller can select an individual `$defs`
record by kind. The Python validator also enforces relationships that JSON
Schema cannot express: result OID equality, final commit binding, exact accepted
check/review subjects, claim binding equality and observed publication OID.
Use it when those checks are required.

## Identity and writers

Every record requires integer `version: 1`, `workflow_root_id`, positive integer
`generation` and `writer_step_id`. Unknown fields and versions fail validation.
The run record captures the initial generation, `1`; later source-plan
generations refer to its fixed base rather than recapturing it.

The identity prefix is `(workflow_root_id, generation)`. The suffixes below are
ordered and form the full logical identity. Payload fields outside the identity
still participate in replay comparison.

| Kind | Metadata payload key | Identity suffix | Designated writer |
| --- | --- | --- | --- |
| `run` | `gc.implementation_run` | `input_convoy_id`, `source_anchor_id`, `rig_root`, `common_git_dir` | Run capture |
| `source-plan` | `gc.source_plan` | `source_plan_owner_id` | Source-plan declaration |
| `workspace` | `gc.workspace` | `source_plan_owner_id`, `workspace_owner_id` | Workspace owner transition |
| `member-result` | `gc.workspace_result` | `source_plan_owner_id`, `workspace_owner_id`, `member_id` | Active member result |
| `owner-output` | `gc.workspace_output` | `source_plan_owner_id`, `workspace_owner_id` | Final member result |
| `canonical` | `gc.canonical` | `source_plan_owner_id` | Canonical binding |
| `review` | `gc.review` | `source_plan_owner_id`, `review_id` | Review report owner |
| `publish` | `gc.publish_intent` | `source_plan_owner_id`, `publish_id` | Publication owner |
| `blocker` | `gc.workspace_blocker` | `source_plan_owner_id`, `workspace_owner_id`, `blocker_id` | Workspace block/recovery owner |

`x-records` in the bundle supplies the identity field order, metadata key,
designated writer and lock scope. Writer names describe responsibilities; the
validator does not claim a step or prove that the caller holds that role.

Physical record IDs come from native Beads creation. Store adapters must maintain
explicit references containing `kind`, the full ordered `identity` array and
`bead_id`. `resolve_record_id(kind, record, references)` returns the single exact
match. Missing or ambiguous matches fail. Workspace lookup also requires that
the reference ID equals the payload's `workspace_bead_id`. Never derive a
physical ID by appending a suffix to a source anchor or owner name.

Dedicated lifecycle records require a proven nondispatch status, configuration
or dispatch filter and exclusion from runtime metadata writers. A milestone or
task type alone does not establish this. The selected backend and binary must
prove those properties before runtime use.

## Source and acceptance

Run records capture canonical absolute rig/common-Git paths and a full base OID.
Paths require absolute spelling and reject C0 controls and DEL; this validator
does not resolve symlinks or prove filesystem/Git topology. Source plans declare
ordered members and predecessor IDs, strategy and one terminal owner. The schema
enforces strategy counts and explicit arrays. Cycle, reachability, membership,
authorization and live accepted-input checks belong to the source-plan writer.

Workspace records keep the stable `workspace_owner_id`, native physical
`workspace_bead_id`, active member, current source OIDs and lifecycle phase.
`claim_binding` repeats root, generation, stable owner, exact `writer_step_id`
and `writer_attempt_id`; the validator requires equality with the payload.
Runtime writers must verify the current native claim under the selected lock.
An assignee value alone cannot authorize a lifecycle write.

`writer_attempt_id` identifies the lifecycle writer attempt.
`native_attempt_id` identifies native workspace provisioning. `native_provenance`
preserves the complete reported object, including extensions; its shape and
native identity/mode verification belong to the native verifier. It can be null
during preparation. Native provisioning base OIDs remain fixed for a shared
workspace attempt while member input/current/output OIDs advance.
`work_branch: null` represents a detached workspace. Runtime owner-reference,
detached-mode and nested-placement support require their native extensions;
representing these fields is not launch support.

Member results distinguish `changed` from `no_change`. A changed result requires
a different output and its final commit in `commit_oids`; no-change requires
equal input/output and no commits. Acceptance is a separate status. An
`accepted` result requires successful project-check entries and an independent
passed review, all bound to `output_oid`, with evidence paths and SHA-256 hashes.
The review identity must differ from the result writer step. These are evidence
bindings: the validator does not run checks, read artifacts, prove reviewer
independence, verify Git ancestry or establish actual project acceptance.

Integration owner outputs retain ordered input/output digests and an integration
artifact digest. Canonical records bind one owner-output digest, output OID and
summary digest. Review records bind canonical digest and reviewed OID; approval
requires clean before/after flags. Publish records bind intent, authorization and
review/canonical digests; an observed publication must equal its intended OID.
Blockers retain expected/actual source, Git state and the paused member/phase;
resolution adds a decision artifact and expected HEAD.

Cross-record consistency, artifact bytes, terminal selection, Git before/after
state, authorization and safe transitions remain writer responsibilities.

## Serialization and replay

Version 1 canonical bytes are UTF-8 JSON with sorted object keys, compact
separators, literal Unicode and no trailing newline. Array order is retained.
Non-finite numbers and duplicate JSON keys fail. SHA-256 covers those exact
bytes; this is a versioned pack encoding, not an RFC 8785 implementation.

`record_identity` validates a payload and returns its identity tuple.
`verify_replay` validates both payloads, rejects different identities and rejects
any changed canonical payload under the same identity. Equivalent object-key
ordering succeeds. It never repairs or overwrites a record.

This check applies to exact snapshot replay. Mutable workspace, blocker and
publish transitions require separate writer/claim/lock checks; `verify_replay`
is not a transition engine. Required lock scopes include the canonical common
Git directory plus root/generation, and owner for workspace transitions. Hold
the owner lock before the root lock when both are needed; common-Git registration
locking stays brief. Storage capability, bounded timeout and filesystem admission
must be verified by the record-access implementation.

Missing versions, unknown versions and conflicting payloads cannot be resumed
or silently adopted. Breaking changes need a new schema version and an explicit
migration decision. Legacy path/artifact metadata alone cannot create these
records.

## Source inventory and proof

[affected-surfaces.v1.json](affected-surfaces.v1.json) closes the current formula
and workflow inventory for Gas City, Compound Engineering, Superpowers, BMAD and
gstack. Content hashes detect changed behavior even when a formula dynamically
delegates through selectors or inheritance. Concrete owning-step bindings and
direct drains identify each separate/shared leaf's final source step; inherited
entrypoints remain visible. The artifact path check is recorded as an additional
source helper. Review delegation, fix-generation ownership and interactive
review's conditional source writes are explicit lifecycle responsibilities.

`legacy` classifies current lifecycle responsibilities, and `reference` identifies
planning/artifact-only surfaces. Every discovered asset must be listed; absent
or changed entries fail discovery. No existing formula is declared migrated.
Base, Compound and gstack shared-item commit-contract gaps are explicit. A future
migration must update classifications, hashes and owning steps together; runtime
mode selection and shadowed-pack admission are separate implementation work.

[scenario-coverage.v1.json](scenario-coverage.v1.json) maps all 23
[design scenarios](https://github.com/gastownhall/gascity-packs/issues/209) to an
implementation owner and observable oracle, and records current-source/RFC
differences. `contract-tested` covers this package's static source discovery.
All runtime scenarios remain `implementation-required`, including those with
partial JSON validation tests.

Fixtures in `tests/fixtures/workspace-records/` are independent synthetic payloads
for each kind, malformed fields/versions and conflicting replay. They do not
represent an executed workflow or a consistent multi-record store.

Run the focused contract tests from the repository root:

```sh
python3 -m unittest discover -s gascity/tests -p test_workspace_records.py -v
```
