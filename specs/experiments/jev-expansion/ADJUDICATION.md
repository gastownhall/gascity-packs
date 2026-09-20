# Boundary cases observed during evaluation

Frozen expected labels remain unchanged. These notes explain the input/rubric
boundaries; they do not replace the registered scoring or erase mismatches.

- `failure-schema`: expected environment because the external installed bd
  fails before candidate code executes. Raw Jev calls it product with low
  confidence; both baseline and fresh fallback chose missing_evidence on the
  first repetition. The question mixes failure cause with the absence of the
  intended check. A default diagnosis replacement needs clearer scope than
  model agreement alone provides.
- `duplicates-version / candidate_1`: expected related because both concern
  export output paths. Both models chose unrelated for an old, fixed permission
  issue versus a new regression ignoring the output flag. The boundary between
  related and unrelated is debatable; both correctly avoid same_issue. Ranking
  must preserve all candidates, not drop ones on that distinction.
- `findings-uncertain / finding_0`: expected unclear for a vague “might be wrong”
  claim without intended behavior or observed output. Both models chose
  missing_evidence, which is also a plausible next action under this rubric.
  The frozen strict score records the mismatch. This is not evidence of a
  dangerous downgrade to residual risk or an established product defect.
- `duplicates-no-match / candidate_0`: raw Jev called an export-format feature
  request and a CSV quoting defect unrelated; the expected relation was related.
  Low confidence triggered a fresh Claude call, which restored the expected
  relation on the first repetition. Neither issue is a duplicate of the other.

Claims of quality preservation must include task-specific outcomes, source
retention and fallback behavior. Neither existing repository labels nor these
small authored fixtures are comprehensive production ground truth.

## Observed paired regression

In repetition 2, `failure-timeout` had expected `unclear`. Raw Jev also chose
`unclear`, but the required fresh Claude fallback changed it to
`missing_evidence`; the independent baseline returned `unclear`. No cause was
established by the timeout output. This is a baseline-correct/treatment-wrong
result under the frozen rule, even though the differing answer came from the
fallback model. Failure routing therefore cannot pass the default gate for
this cohort. Do not remove this case, relabel it, or attribute perfect quality
to the combined pipeline based on the raw Jev answer.

`findings-uncertain / finding_0` also became a paired regression in repetition 2:
the baseline returned the expected `unclear`, while the fresh treatment fallback
returned `missing_evidence`. The ambiguous wording remains relevant, but the
registered comparison still counts this against default promotion. Finding
classification/pair assistance stays opt-in for this version.
