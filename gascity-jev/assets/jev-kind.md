# Jev kind triage

> Scope: advisory command-line helpers kept for maintainer-city triage
> (`../REQUIREMENTS.md`, GC-JEV-BR-009). No overlay formula calls them. The
> build gates in `jev-build` are different: they act on their own inside
> bands, with audits and a circuit breaker.

In `auto` mode the helper delegates the bounded kind question to Jev when
configured. Without access, ordinary triage applies.
Use `off` to disable or `assist` to explicitly attempt assistance. The helper
also accepts the pack's PR snapshot
format for callers such as maintainer-city. It only reads title and body;
existing labels, reference answers, priority and other snapshot fields are
excluded from inference. It does not inspect code or diffs.

The rubric uses the [published Gas City policy](https://github.com/gastownhall/gascity/issues/125)
and its [primary-intent definitions](https://github.com/gastownhall/gastown/discussions/1399):
bug, feature, docs, chore. Mixed changes use primary intent; insufficient
context returns `unclear`. This is a title/body classifier, not a finding that
an issue really is reproducible or a PR really contains only documentation.

## Workflow integration

For `assist`, after checking the existing report-reuse path:

1. Read the helper's rubric in `assets/scripts/jev_kind.py`. If a custom triage
   rubric changes kind definitions, use ordinary LLM kind triage and record
   `rubric_mismatch`; label-name remapping alone is supported. This prevents a
   confident answer under the wrong policy from replacing the intended one.
2. Run the helper against `gc.github.snapshot_path`, writing to a **new**
   directory under `gc.github.triage_dir/jev-kind/` for each attempt:

   ```sh
   python3 <pack-root>/assets/scripts/jev_kind.py <snapshot-path> \
     --output-dir <triage-dir>/jev-kind/attempt-1 \
     --model <jev_kind_model> --threshold <jev_kind_threshold>
   ```

   If `jev_kind_labels_path` is nonempty, add `--labels <path>`. Keep the
   credential `TYPESAFE_API_KEY` in the worker environment, never in arguments
   or prompts. With no credential the helper records failure and exits 1.
3. Read `report.json`. Only `status=completed` and `decision.route=use_kind`
   supply a kind. Use `decision.choice` as the proposed logical kind and
   `decision.label` as its repository label. On `llm_kind`, failed status,
   malformed/missing output, or configuration error, explicitly record the
   fallback reason and perform ordinary LLM kind triage. Preserve failed
   attempt artifacts; never treat failure as successful Jev classification.
4. Explain the proposed kind and its source in the human-readable report
   body. Reference the assessment artifact in the local evidence record.
   Preserve the existing report front matter, verdict, priority, investigation,
   and public-comment/human-gate contracts. This helper grants no authority
   to apply GitHub labels. `gc.github.kind` still means `issue` or `pr`, not
   bug/feature/docs/chore.

Reused body-hash reports remain a no-op, including kind inference. To measure a
fresh title or different model/rubric, run the standalone helper with a new
attempt directory instead of changing the workflow's reuse policy.

## Maintainer-city adapter contract

Input: a JSON object containing a nonempty string `title` and string `body`.
The helper sends one Choice question, returns `gc.kind-assessment.v1`, and
records materialized state, exact request, raw response, question version,
input/request SHA-256 hashes, requested/resolved model, threshold, label map,
usage, failure information, and wall time. No automatic retries. Existing
output directories are rejected. `--validate-only` records the request without
inference and cannot produce a classification.

`use_kind` means the caller may use the proposed kind in its existing triage
policy. `llm_kind` means the caller must resolve that decision. Neither route
changes priority, complexity, adopt-pr eligibility, or approval policy.
This supports Julian's kind-only approach; it is not a port of his
maintainer-city implementation or evidence of identical model behavior.

Label names are explicit. Defaults use `kind/feature`; Gastown's newer
[PR Sheriff decoder](https://github.com/gastownhall/gastown/issues/4298) describes
`kind/enhancement`. For that repository, pass a JSON file such as:

```json
{"bug":"kind/bug","feature":"kind/enhancement","docs":"kind/docs","chore":"kind/chore"}
```

The default 0.85 confidence cutoff is uncalibrated. Tune it on pilot cases,
freeze it before held-out evaluation, and inspect both agreement and coverage.
High confidence is not proof of correctness.

See [the kind experiment protocol](../../specs/experiments/jev-evidence-routing/KIND-TRIAGE.md)
for historical backtesting, and [the paired results](../../specs/experiments/jev-evidence-routing/KIND-RESULTS.md)
for our measured kind agreement, fallback coverage, token use and latency.
