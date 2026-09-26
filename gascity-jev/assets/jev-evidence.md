# Jev evidence assistance

> Scope: advisory command-line helpers kept for maintainer-city triage
> (`../REQUIREMENTS.md`, GC-JEV-BR-009). No overlay formula calls them. The
> build gates in `jev-build` are different: they act on their own inside
> bands, with audits and a circuit breaker.

Used in `auto` mode, the helper asks Jev about a test-evidence bundle when a
credential is configured. Without access, record the
skipped assistance and perform ordinary review. `off` disables assistance;
`assist` explicitly attempts it and records failures. It does not replace the acceptance or simplicity lanes,
waive proof commands, or grant approval. It requires `TYPESAFE_API_KEY` in the
worker environment. Keep credentials out of prompts, bundles, and run logs.

For each implementation worktree, produce a `gc.evidence-bundle.v1` JSON file:

```json
{
  "schema": "gc.evidence-bundle.v1",
  "worktree": "/absolute/implementation/worktree",
  "head": "actual git rev-parse HEAD",
  "items": [{
    "id": "AC-1",
    "criterion": "Malformed input exits nonzero with a useful diagnostic",
    "claim": "The malformed-input test demonstrates the expected failure",
    "sources": [{
      "path": "tests/test_export.py",
      "sha256": "SHA-256 of the whole file",
      "start_line": 10,
      "end_line": 25
    }],
    "proofs": [{
      "path": "evidence/AC-1.txt",
      "sha256": "SHA-256 of the actual saved command output",
      "command": "python3 -m pytest tests/test_export.py -k malformed",
      "exit_code": 0,
      "head": "actual git rev-parse HEAD"
    }]
  }]
}
```

Gather the real acceptance criteria, implementation and relevant test source.
Run proof commands in the authorized implementation worktree and save their
actual stdout/stderr and exit status. Do not synthesize a success log or take a
worker's prose claim as an execution record. Files must be inside the worktree;
copy proof logs into a dedicated evidence directory if necessary. Hash source
files with SHA-256. Optional inclusive line ranges select relevant excerpts;
the hash still covers the entire source file. A bundle cannot span worktrees.

Hash/HEAD checks establish snapshot consistency, not the truth of a test claim
or a guarantee that a submitted log came from the stated command. The reviewer
still owns provenance and real test execution. A matching HEAD alone does not
prove that tests covered uncommitted edits. Capture source hashes when running
proof and recreate proof after any edits.

Run the helper with a new output directory for each attempt:

```sh
python3 <pack-root>/assets/scripts/jev_evidence.py bundle.json \
  --output-dir <artifact-root>/jev/attempt-1 --mode auto \
  --model jev-1.13.0 --threshold 0.85
```

`--validate-only` materializes and validates evidence without inference. Output
includes the original bundle, materialized state, exact request, raw response,
and `report.json`. Outputs are exclusive-created and never overwritten. A
failure returns nonzero and records an error report; it is not a passing review.
No automatic API retries hide extra latency or usage.

| Choice | Suggested next action |
| --- | --- |
| supported | Reviewer checks the supporting evidence; not automatic approval |
| missing_evidence | Run/gather the missing proof before changing code |
| contradicted | Investigate the implementation and proof before choosing a fix |
| unclear, or confidence below threshold | Ordinary LLM review |

The confidence threshold is an experimental policy, not an accuracy guarantee.
Independent question outputs do not enforce logical consistency across items.
Reviewers must resolve conflicts and preserve the existing review contract.
If Jev fails, record the attempt and explicitly use the ordinary review path.

Reference: TypeSafe's [citation cookbook](https://docs.typesafe.ai/cookbooks/citation_check)
and [known model limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13).
