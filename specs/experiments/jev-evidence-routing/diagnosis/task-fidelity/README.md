# Original-task fidelity observation

Baseline 004 received the correct slugify task in source bead fi-ddp, linked by
input convoy fi-2fb. Requirements artifact REQ-001..003 instead describe creating
a valid requirements document. The original slugger.py stayed a stub and all
three unchanged tests failed after the diagnostic run was stopped.

The build-basic requirements stage mostly specifies artifact syntax and asks to
preserve the input target, but gives no explicit input-convoy retrieval procedure.
The role requires execution of the claimed bead and prohibits broad discovery.
The claim command returns that bead and identifiers; it does not append source
work-item content. Its convoy traversal is only observer bookkeeping when
GASWORKS_RUN_ID is set, not task content in the claim output. Reading the workflow
root alone reveals the formula description and a convoy link, not the task.

This source path explains a plausible input-retrieval gap, but a controlled
prompt/input comparison has not established causality. Baseline 005 keeps the
same task and pack; it only changes the gate Python provision. Do not attribute
any runtime-repair benefit to Jev.

A subsequent experiment could give both arms a deterministic snapshot of the
original input convoy, preserving bead IDs and hashes, then optionally ask Jev
whether every acceptance criterion is grounded in that source and every source
constraint is represented. That would be a distinct treatment from downstream
code-evidence review and needs its own frozen rubric and paired cohort. Merely
checking the generated requirements against themselves cannot detect this drift.

Evidence: ../../build-baseline-004/run-001-baseline/input-lineage-observation.json,
requirements-initial.md, independent-quality.json, and independent-pytest.log.
Source: gascity/commands/claim/run.sh, gascity/template-fragments/gc-role-worker.template.md,
gascity/assets/workflows/build-basic/requirements.md.

Baseline 005 produced slugify requirements after reading the implementation
stub and tests. Its first artifact still omitted the explicit unchanged-test
constraint and did not clearly state ASCII-only scope. This variation reinforces
that the input-retrieval hypothesis needs a controlled comparison; it is not a
proven deterministic failure. Initial artifacts and hashes for both runs are retained.
