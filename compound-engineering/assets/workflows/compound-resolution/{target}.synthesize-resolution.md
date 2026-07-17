Synthesize the Compound Engineering final resolution.

Use the artifact inventory, review-resolution result, any deployment notes
preserved by the code-review report, and the ce-compound resolution template as
methodology guidance. Read the canonical final report path from workflow root
metadata `gc.build.final_report_path` and write the final build artifact there.
Do not replace it with an attempt-local path or a stock Compound Engineering
solution document.

If the methodology also calls for durable knowledge under `docs/solutions`,
record that repository-relative solution path as supporting evidence under the
canonical report's Artifacts section. A `docs/solutions` document never
replaces `gc.build.final_report_path`.

The canonical report is Markdown with YAML front matter, not JSON. Its first
line must be `---`, followed by a closing line containing exactly `---` before
the body. Use nested mappings with this shape:

```yaml
---
schema: gc.build.final-report.v1
workflow:
  id: <workflow-root-id>
  formula: <root-workflow-formula>
methodology:
  pack: compound-engineering
  name: ce-compound
producer:
  formula: compound-resolution
  stage: synthesize-resolution
  attempt: <current positive gc.attempt for this finalize stage>
status: approved
trace:
  upstream:
    - path: <canonical-build-artifact-path>
      hash: sha256:<artifact-digest>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

Trace the canonical absolute `gc.build.implementation_summary_path` and
`gc.build.review_report_path` exactly once each, using a freshly computed
`sha256:<digest>` of each exact file. An earlier artifact, a byte-identical copy
at another path, or a path without its current digest is stale and must block
finalization.

Use `status: approved` only when requirements, plan, decomposition,
implementation, review, and required publish-readiness evidence support a
successful build and no unresolved blocker remains. Use a schema-allowed
non-success status and retain failure evidence otherwise.

Every `trace.upstream` entry must contain a non-empty `path` and a
scheme-qualified `hash`. Preserve actual source IDs verbatim; never invent,
substitute, or renumber them. Every declared upstream ID must appear exactly
once in `trace.coverage`. If no source declares IDs, omit `ids` and use
`coverage: []`. Use only schema coverage statuses and include a non-empty
`rationale` for every status other than `covered`.

When coverage is non-empty, include one Markdown coverage table whose `ID` and `Status`
pairs exactly match `trace.coverage`:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Replace the illustrative data row with actual IDs. When coverage is empty,
omit the table or include only its header and separator; never emit a
placeholder data row.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Outcome`
- `## Artifacts`
- `## Remaining Risks`

Record `gc.build.final_report_path=<absolute canonical final report path>` on
the workflow root bead. Resolve the launcher rig root from workflow root
metadata `gc.work_dir`; if it names an attempt worktree, use the nearest
ancestor containing `.gc/scripts/checks/build-artifact-valid.sh`. From that
launcher rig root run:

Read the exact current bead ID from the startup claim output. In the same shell
invocation, substitute it literally for the placeholder below; variables from
earlier tool calls do not persist.

```bash
export CLAIMED_BEAD_ID='<exact-current-bead-id>'
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error in this exact canonical report before setting the
synthesis lane to `gc.outcome=pass`. Classify the final outcome as pass only
when required artifacts exist, validation succeeds, and unresolved blockers
are absent.

Do not invoke provider-native subagents. Synthesis happens in this Gas City lane.
