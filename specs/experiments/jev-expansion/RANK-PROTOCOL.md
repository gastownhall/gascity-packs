# Ranking-only follow-up, registered before inference

The first experiment classified relationships and spent Claude fallbacks on
related-versus-unrelated distinctions that the ranking consumer does not need.
Raw Jev put a known matching issue first in 12/12 repeated positive cases.
That is descriptive analysis, not a replacement of the first experiment's
registered gate or a reason to delete its negative result.

This follow-up changes the application operation to candidate ordering. One
Noul question per candidate estimates whether it concerns the same underlying
issue. Code sorts scores stably, retains all candidates/source text, and renders
the investigation packet deterministically. No score creates a duplicate
verdict; the existing investigator still confirms the actual shared trigger or
requirement. Thus no classification fallback is needed merely to choose an
inspection order. Service/contract failure requires ordinary investigation.

Ten new authored cases, frozen before inference: two pilot and eight evaluation,
including six evaluation cases with an explicit matching candidate, two without
an established match, near-matches, different triggers and an embedded hostile
instruction. Evaluation runs twice with reversed arm order. No threshold tuning.

Both arms receive identical issue/candidate state and matching criteria.
Baseline uses subscription Opus 5 at max effort to order every candidate ID;
treatment invokes the production ranking CLI. Both use the same deterministic
source-preserving renderer. Timing includes preparation, inference, parsing,
validation and rendered handoff; it excludes GitHub acquisition and the later
full issue investigation/comment workflow. This is a complete ranking component,
not a full-triage speed measurement or the earlier generated-label report task.

Quality checks: exact candidate-ID permutation, no source loss or invented
verdict, expected matching candidate ranked first where one is established.
Unmatched/ambiguous cases do not have an invented correct top result. Default
promotion requires no baseline-correct/treatment-wrong top-1 result, passing
preservation checks, no failed/unknown attempts, and lower Claude tokens and
elapsed time. The first classification gate still controls kind, finding and
failure modes; this separate gate controls the revised ranking implementation.
