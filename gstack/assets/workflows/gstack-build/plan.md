Draft the gstack implementation plan.

Use the requirements artifact, context bundle, and existing repo patterns to
produce a plan that is ready for the gstack plan-review fanout. Preserve the raw
gstack posture: founder-level scope challenge first, then design, engineering,
and developer-experience readiness.

The plan must include at least two implementation approaches, the recommended
approach, task boundaries, test commands, release risks, and what work is not in
scope. Keep it approachable for first-time factory users: concrete files and
commands beat abstract strategy.

Read the exact plan path from workflow root metadata `gc.build.plan_path`
(fallback `gc.var.plan_path`) and write the canonical artifact there. Do not
write an attempt-local substitute. The plan must be Markdown with YAML front
matter, not JSON. Its first line must be `---`, followed by a closing `---`
before the Markdown body.

Use nested YAML mappings with this top-level shape:

```yaml
---
schema: gc.build.plan.v1
workflow:
  id: <workflow-root-id>
  formula: <root-workflow-formula>
methodology:
  pack: gstack
  name: autoplan
producer:
  formula: gstack-build
  stage: plan
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: <requirements-artifact-path>
      hash: sha256:<requirements-artifact-digest>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

Every `trace.upstream` entry must contain a path and scheme-qualified hash.
Preserve actual source IDs verbatim; never invent, substitute, or renumber
them. Account for each declared ID exactly once in `trace.coverage`. When no
source declares IDs, omit `ids` and use `coverage: []`. Use only schema
coverage statuses and add `rationale` to every non-`covered` entry. Include one
Markdown table whose `ID` and `Status` pairs exactly match `trace.coverage`:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, and replace the
placeholder with an actual ID. When coverage is empty, do not add a data row;
omit the table or use only its header and separator.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Current System`
- `## Proposed Implementation`
- `## Non-Goals`
- `## Verification`

Put the alternative approaches, recommendation, concrete task boundaries, and
affected files under `## Proposed Implementation`. Put exact focused and final
proof commands under `## Verification`. Use `status: approved` only when the
plan is internally complete enough for the gstack review fanout; the fanout may
reopen required changes in place.

Record `gc.build.plan_path=<absolute path>` on the workflow root bead. Before
closing, read the launcher rig root from workflow root metadata `gc.work_dir`.
If necessary, walk to the nearest ancestor containing the canonical check.
Read the exact current bead ID from the startup claim output and substitute it
literally below; shell variables from earlier tool calls do not persist. Then
run:

```bash
GC_BEAD_ID=<exact-claimed-bead-id> <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error in this exact artifact before setting
`gc.outcome=pass`.

Close with `gc.outcome=pass` and the plan artifact path.

Do not invoke provider-native subagents. Gas City fanouts handle downstream
review.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
