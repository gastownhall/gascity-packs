# GC runtime fix validation — 2026-09-06

The first runtime correction commit is `aca49b990` on
`fix/bb-live-runtime-compatibility`. Its active pre-commit hook passed formatting,
changed-file lint, generated-artifact checks, vet and documentation tests.
Commit `97ba30aa3` adds the suspend/identity and current Claude approval
corrections. Its normal pre-commit hook also passed formatting, changed-file
lint, generators, vet and documentation tests. A pre-push run started before those edits completed was
contaminated by concurrent test edits; its results cannot certify that commit.

The required upstream baseline **failed overall**: `make test-fast-parallel LOCAL_TEST_JOBS=2`, run in `/Users/csells/Code/gastownhall/gascity-bb-runtime-fixes` with the documented `EXTRA_TEST_ENV=LOCAL_TEST_LOG_DIR=/var/tmp/gc-bb-baseline-ix7z24d1/jobs` plumbing, exited 2 after 1,025.605 seconds. Five of eight jobs passed; `unit-core` and command shards 1 and 5 failed, with 18 failing top-level tests. The changed package owners passed within that run: `internal/runtime/tmux` (13.720 seconds), `internal/sessionlog` (10.987 seconds), and `internal/worker` (20.048 seconds). The earlier focused session-log suite also passed (9.072 seconds). These package results do not make the baseline green and do not establish live BB acceptance.

Failures included short probe/timer deadlines under substantial host load, installed `herdr` rejecting `--no-focus`, and eight provider-ledger waivers that expired on 2026-08-26. A separate detached, unchanged v1.4.1 checkout at `/var/tmp/gc-bb-baseline-ix7z24d1/released` reproduced the expired-waiver failure. The two failing command tests, `TestStopManagedCityForcesCleanupAfterTimeout` and `TestInitRunDoltConfigGetTreatsSilentEmptyExitAsMissingKey`, passed when targeted on that clean release after the broad run finished. This proves the waiver failure predates these changes; it does not prove every timing failure was caused by host load. No unrelated test policy or timeout was changed to obtain a pass.

Retained local evidence is `/var/tmp/gc-bb-baseline-ix7z24d1/runner.log`, `result.txt`, `summary.json`, `jobs/`, `released-comparison.json`, `baseline-focus-cmd.log`, and `baseline-focus-ledger.log`. Raw logs and private runtime transcripts remain outside this repository. The Make isolation environment and normal shared Go cache were preserved; tests used disposable scaffolding.

## Existing Manifold credential investigation

At the start of this investigation, the repository exposed secret names `MANIFOLD_AUTH_TOKEN` and `OLLAMA_API_KEY`; `BB_CODEX_API_KEY` was absent. The repository variables describe Claude model mappings for Manifold and Ollama. Existing inference workflows configure Claude with `ANTHROPIC_BASE_URL=https://works.gascity.com/manifold-api` and the Manifold token; they do not configure a Codex Responses provider. Only variable and secret names were inspected through GitHub; secret values were not retrieved.

GC `origin/main` documents a real `/data/projects/maintainer-city/scripts/manifold-codex` wrapper in [the structured-transcript corpus guide](https://github.com/gastownhall/gascity/blob/main/internal/worker/workertest/testdata/corpus/README.md). That guide requires the credential broker and confirms Codex use exists on maintainer hosts, but the wrapper, its model mapping, Responses endpoint, and credential contract are absent from the searched tracked GC and pack sources. It does not establish that the existing Claude CI token authorizes that route.

Codex supports custom providers with `model_provider`, `model_providers.<id>.base_url`, and `env_key`; its documented protocol is `wire_api="responses"`. See [custom provider configuration](https://developers.openai.com/codex/config-advanced/) and [the configuration reference](https://developers.openai.com/codex/config-reference/). The installed CLI reports 0.153.4. Unauthenticated GET requests to the Manifold base, `/v1/models`, `/v1/responses`, and `/openapi.json` all returned HTTP 403. Those responses reveal neither supported routes nor model access. Therefore reuse of the existing Manifold token for Codex remains **unverified**, not known unsupported: a verified broker wrapper/configuration or endpoint contract plus actual Codex acceptance is still needed. No speculative Manifold endpoint was wired into CI. The Codex credential was subsequently supplied through the verified OpenAI route below.

## Verified Codex CI credential

The existing Dashlane note titled OpenAI Project API Key supplied one scoped
credential. Its authenticated OpenAI model-list request succeeded, followed by a
real Codex 0.153.4 `exec` request using `gpt-5.5` in a fresh private configuration
and workspace. The process exited 0 and returned the exact requested nonce.
The key was then piped into the repository secret `BB_CODEX_API_KEY`; a subsequent
secret-name listing verified it exists. No personal Codex OAuth credential was
uploaded and no secret value entered the repository or tool output. Private
proof: `/private/tmp/bb-live-9dbgrsx5/codex-api-proof-ro3uld13/report.json`.

## Final focused runtime checks

After the second correction commit, the complete tmux suite passed (16.081 s),
as did the complete session suite (6.444 s), worker suite (15.594 s), and focused
controller/suspend regressions (4.358 s). Earlier session-log checks passed
(9.072 s). This is targeted evidence; the required broad baseline remains red
as described above. The later pre-push attempt is not evidence for the final
source because concurrent edits contaminated its compile shards.

The follow-up copy-mode interruption regressions first failed, then the complete
tmux suite passed again (16.435 s). Recognized approval cancellation now exits
parked copy mode before Escape and preserves best-effort behavior if the
session disappears before key delivery. Independent review found no issue.

Configured-root resume/fork checks passed after the lint corrections (2.782 s).
Claude underscore discovery checks passed in sessionlog (0.460 s) and
worker/transcript (0.333 s); a scratch-only test overlay also resolved the exact
file generated by real Claude 2.1.263 (0.220 s). These changes had independent
read-only review. No default-path ambiguity policy or unrelated waiver was
changed to obtain a pass.

The final follow-up commit is `f7e64f0b4` (`fix(runtime): retain configured
transcripts during resume`). Its normal pre-commit hook passed lint (0 issues),
generated-artifact checks and `go vet ./...`. The initial attempts failed lint
and then missing local ICU include paths; both were corrected before commit.
The branch push deliberately bypasses only the pre-push invocation of
`make test-fast-parallel`, using a per-command hooks-path override: that broad
suite is already recorded red, including an expired-waiver failure reproduced
on unchanged v1.4.1. The normal repository hook setting is unchanged. Focused
checks above passed; the full GC baseline remains a release risk, not a pass.
