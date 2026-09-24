# Intake-router spike: protocol

Written and frozen 2026-09-24T16:21Z, before any Jev call. Changes after this point go in the
"Amendments" section at the bottom with a timestamp and reason; nothing above it is edited.

## Question

Given only the request text of a software task, can Jev pick how much workflow process the task
needs, well enough to route small well-specified work to a compact path without under-triaging
big or risky work?

## Data

- Source: public repo `gastownhall/gascity`, merged pull requests, via `gh`.
- Snapshot: PRs merged at or before the moment `collect.py` runs (recorded in `prs.json` as
  `snapshot_at`). Candidates are the 300 most recently merged PRs, sorted by `mergedAt` desc.
- Eligibility (applied in this order; excluded PRs are listed in `prs.json` with the reason):
  1. Base branch must be `main`. Backports and cherry-picks onto `release/*` or other branches
     are release-only work, not new requests.
  2. Author must not be a bot (`is_bot`, login ending in `[bot]`, or renovate/dependabot/
     github-actions).
  3. Title must not match dependency bumps or release/sync merges (case-insensitive):
     `^(chore|build|fix)\(deps\)`, `^bump `, `^(chore\()?release`, `^release`, `^merge .* into `,
     `^merge branch`.
- Sets:
  - Evaluation set: the 60 most recent eligible PRs.
  - Pilot set: the next 10 eligible PRs (ranks 61-70, all older than every evaluation PR). Used
    only for checking the API format and refining question wording.

## Request text (the only thing Jev sees)

- `PR title: <title>`, blank line, `PR description:` and the PR body.
- If the PR closes one or more issues (GitHub `closingIssuesReferences`), append for up to two of
  them: `Linked issue #<n>: <issue title>` and the issue body.
- HTML comments (`<!-- ... -->`) are removed. Nothing else is rewritten.
- Length cap 6000 characters. When a linked issue exists, the PR body is capped at 3000 characters
  first so the issue text survives; any cut is marked `[truncated]`. The whole string is then capped
  at 6000.
- Never included: diff, file list, stats, review data, ground truth, labels.

The state is sent as a JSON object `{"request": "<text>"}` so instructions can refer to `request`.

## Ground truth (computed by `collect.py` from what actually happened, before any Jev call)

Per PR: `lines = additions + deletions` (GitHub's numbers, tests and generated files included),
`files = changed_files`, full file list (paginated), review data (human reviews excluding the
author and bots, bot reviews, inline review comments, conversation comments).

Path classes (on any changed file path):

- `design_docs`: under `engdocs/`, `specs/`, or `plans/`, or any path containing `/design/` or
  starting with `design/`.
- `api_contract`: under `internal/api/`, or any path containing `openapi`.
- `schema`: under `schemas/`, `schemas_embed.go`, any file ending in `.schema.json`, or `.proto`.
- `migration`: under `internal/migrate/`, or any path segment containing `migration`.
- `security`: under `internal/{cliauth,clientauth,clientgrant,citywriteauth,credentialprovider,
  doltauth,gitcred,ssrf,webhookverify,promptsafe}/`, `SECURITY.md`, `.trivyignore*`, or any path
  containing `secret` or `credential`.

`risky` = any of the five classes. `deep_trigger` = any of `design_docs`, `api_contract`,
`schema`, `migration`.

Depth:

- `compact`: `files <= 3` and `lines <= 80` and not `risky`.
- `deep`: `files > 15` or `lines > 600` or `deep_trigger`.
- `standard`: everything else (including small changes that touch a `security` path).

Review rounds and comment counts are recorded and reported descriptively; they do not enter the
depth label.

## Jev call

- One call per PR: `POST https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`, all questions
  in the one call, the state above. No hidden retries: a transport or HTTP failure is recorded as a
  failed attempt; at most one more attempt is made and recorded separately. A PR with no successful
  attempt is reported as `no_answer` and routes up (never compact).
- Every request and response is saved under `calls/<set>/<pr>.request.json` and
  `.response.json`, with wall-clock latency.
- Question set v1 (starting point; the pilot may revise wording, then it is frozen):
  - `size` (score, ordered levels compact < standard < deep).
  - `needs_design` (choice: yes / no / cannot_tell).
  - `risky_surface` (choice: none / public_api_or_schema / persistence_or_migration /
    security_or_auth / cannot_tell).
  - `well_specified` (choice: clear_acceptance_criteria / partially_specified / underspecified /
    cannot_tell).
- Pilot: at most 3 pilot iterations over the 10 pilot PRs, each recorded under
  `calls/pilot-<n>/` with the question set used. The question set is then frozen into
  `questions.frozen.json` with its SHA-256, and the evaluation set is run exactly once with it.
  No wording, threshold, or rule changes after seeing any evaluation output.

## Routing rule under evaluation

Route `compact` only if all hold, otherwise route `up` (standard-or-deeper process):

- `size` says compact with confidence `>= t`: the most probable size level is `compact` and the
  answer's `confidence >= t`;
- `risky_surface.choice == none`;
- `needs_design.choice == no`.

`well_specified` is recorded but not part of the primary rule. Secondary (reported, clearly
labelled): the same rule additionally requiring `well_specified == clear_acceptance_criteria`, and
the same rule using `P(size = compact) >= t` in place of argmax+confidence.

## Metrics (evaluation set only; pilot reported separately)

For t in {0.6, 0.7, 0.8, 0.9}:

- coverage = routed compact / all answered PRs;
- under-triage = routed compact but ground truth standard or deep (count, rate over routed
  compact, and the list with reasons);
- over-triage = ground truth compact but routed up (count, rate over ground-truth compact);
- also precision/recall of the compact route.

Also: 3x3 confusion matrix of Jev's argmax size vs ground-truth depth; tokens (input/output) and
latency totals and per-call median.

Success bar for "viable" (stated in advance): at some t, under-triage of deep PRs is zero and
under-triage overall is at most 1 PR per 20 routed compact, while coverage recovers at least half
of the ground-truth compact PRs. n is small, so this is an indication, not a proof.

## Pre-registered secondary arm B (issue-only intake)

A PR description is written after the work and describes the implementation, which leaks size
information that a real intake request would not have. For evaluation PRs that close an issue,
make one more call with state = `Issue title` + issue body only (same frozen questions, same caps),
recorded under `calls/eval-issue-only/`. Reported separately with the same metrics on that subset.

## Amendments

- 2026-09-24T16:27Z, after the pilot and before any evaluation call:
  - API format: `score` criteria must be an ordered list (pilot-1 got HTTP 422 for an object);
    `choice` criteria are an object of option -> description. The score answer returns
    `probabilities` keyed by level index ("0" compact, "1" standard, "2" deep) plus `score`,
    `legend` and `confidence`; `confidence` is not equal to the top probability, so the primary
    rule uses argmax level + `confidence`, and the `P(compact) >= t` variant stays secondary as
    planned.
  - Pilot iterations: pilot-1 (v1, 422 format error, no answers), pilot-2 (v2 = v1 with list
    criteria), pilot-3 (v3). v2 routed 3 of 10 pilot PRs compact and all 3 were ground-truth
    standard (125-368 lines); size argmax matched ground truth on 2/10. v3 tightens the `compact`
    level description (few lines in one spot; a new helper or several regression cases is not
    compact), tells the model to judge by implied edits rather than tone and to pick the larger
    level when between two, and adds "deleted or pruned" data to `persistence_or_migration`. v3
    routed 0 pilot PRs compact (no under-triage; missed the one compact pilot PR) and matched
    size on 4/10. The pilot has only one compact PR, so it cannot measure coverage; v3 was chosen
    for fewer under-triage errors and better size agreement.
  - Frozen question set: `questions.frozen.json` (identical to `questions/v3.json`), SHA-256
    `1bd35172feed1416657730f156144180ac8d552fd9257a5784cdfbc2da4c8870`.
