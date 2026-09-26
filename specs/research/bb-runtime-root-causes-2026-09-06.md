# BB runtime failures and missing CI coverage

The first BB workflow checked builds, fixtures and released GC command loading.
It never started a supervisor or completed a model-backed BB conversation. Its
green result was insufficient evidence that the pack worked.

Commit `5ca4ac4` adds actual BB/GC startup, global/rig conversations, two turns,
tool output, independent prompt/transcript verification and a mandatory aggregate
check. [Its CI run](https://github.com/gastownhall/gascity-packs/actions/runs/34068400398)
failed: the two build/fixture jobs passed, both Claude inference jobs failed,
and both Codex jobs failed because `BB_CODEX_API_KEY` was absent. The key has
since been configured after an independent real Codex API inference check. Local tests with
explicit Codex credentials also failed; missing CI credentials are not the
only Codex blocker.

## Claude input loss: confirmed

A controlled experiment used separate, fresh, ready Claude Code 2.1.263 sessions
and the same 3,211-byte multiline prompt. GC 1.4.1's short-input transport,
`tmux send-keys -l`, produced a 145-byte user transcript: a 3,066-byte prefix was
lost. `tmux paste-buffer -p` preserved all 3,211 bytes exactly.

Both sessions returned the requested answer marker. Checking only the answer
would therefore have passed a broken delivery. The acceptance harness also
requires the complete forwarded prompt, including BB context, in a new GC user
message, independently verified against the durable receipt's hash.

A raw tty consumer received all bytes through both transports. This locates
the incompatibility in Claude's handling of unbracketed terminal input, rather
than missing GC startup, HTTP truncation or tmux byte loss. Claude's internal
implementation detail remains unknown.

Private evidence: `/private/tmp/gc-claude-ab-hl8ja55x/report.json` and associated
expected/observed inputs and pane captures. The directory includes private
configuration and must not be uploaded wholesale. All experiment sessions were
stopped after preserving evidence.

## Codex activity: confirmed omissions

GC 1.4.1's `ExtractCodexTailMeta` extracts usage and model data without activity.
Actual Codex CLI 0.153.4 logs contain identified `task_started`, `task_complete`
and `turn_aborted` events. Assistant text and token counts cannot substitute
for those lifecycle events.

There is a second omission: `SessionLogAdapter.LoadHistory` reads metadata
using the Claude extractor even for Codex. Fixing only the Codex extractor
does not fix the structured transcript consumed by BB.

## First input races startup: confirmed pack defect

The development Claude rig run accepted BB's submit while GC was still
processing its startup/core instructions. Its transcript contains that startup
message and a reply saying no task had arrived, but no BB request. The pack's
first-turn exception allowed submission against an empty/degraded fallback
transcript after checking only for a pending interaction.

GC's create API accepts an initial message, but the released API does not
expose the authoritative session working directory before creation. Sending
the request during creation would execute it before the pack's workspace
check. The correction retains empty creation and actual workspace verification,
then waits for reliable idle structured history before submitting the first
BB request. Pending interactions, cancellation and a bounded readiness timeout
must fail before recording or sending that request. An agent that never
publishes reliable startup history cannot be accepted through this path.

Independent review caught a second issue in that correction: GC streamed
upserts contain a suffix, not the complete history. The readiness path now
fetches and revalidates a full transcript before recording the baseline message
IDs. A suffix-only regression failed before this fix and passes afterward.

## Claude shared-workspace identity: confirmed GC defect

Reusing the test city exposed a separate failure on the second Claude session
in an existing workspace. The terminal completed startup, but structured
history remained unavailable. GC's startup hook discarded Claude's authoritative
`session_id` from hook stdin because it only allowed Codex. The narrow correction
accepts the Claude family too, preserving existing keys and rejecting unsupported
families, foreign beads and GC-ID collisions. The managed-hook regression
reproduced the missing key before the fix and passes afterward. Claude's
[SessionStart input contract](https://code.claude.com/docs/en/hooks#sessionstart-input)
supplies that identity; no newest-transcript guess is required.

## Codex resumed-session delivery

The retained Codex global session stopped after acknowledging a drain at
17:26:10. A subsequent BB submit woke it at 17:26:33 and was reported delivered
at 17:26:40, but its prompt remained in the resumed terminal's composer. The
existing transcript's idle state described the previous process. The request
and draft were preserved; the harness correctly failed complete delivery.

Four controlled rounds per transport, including the exact 500 ms debounce,
terminal wake sequence and an 80×24 alternate-screen viewport, preserved all
3,062 prompt bytes through standalone Codex with both literal input and bracketed
paste. There is no confirmed Codex truncation defect from those experiments.
The owning correction targets readiness of the resumed process before delivery.
Private A/B evidence is in `/private/tmp/gc-codex-ab-9v1fdpy6/report.json`.

The resumed-process correction waits for the current Codex viewport to show a
stable input composer, rejecting loading, busy and review/menu states. It uses
the same transport resolution as resume, so inferred ACP sessions do not enter
a terminal wait. Timeout or cancellation sends no input. A real Codex resume
experiment using the corrected runtime waited 2.27 seconds, then delivered all
3,071 bytes once and verified the answer; evidence is `report-resume.json` in
the same private directory. This targeted experiment does not establish BB
restart/recovery acceptance.

## BB startup acknowledgment and acceptance roles

On development build `1.4.1-bb-live.5`, Claude global completed both BB turns in
the retained city, including new sessions in its existing workspace. The rig
failed before acceptance: BB 0.42.1 allows 30 seconds for the `turn/start`
JSON-RPC response, while the provider awaited startup readiness for up to 150
seconds inside that request. The provider needs to acknowledge the request
promptly and report subsequent readiness/submission results through the SDK's
asynchronous turn events. Increasing the readiness timeout cannot fix that
protocol mismatch.

The Codex acceptance agents also inherited core's graph-worker prompt because
the harness supplied no explicit role. Session `gc-149` followed that prompt:
it ran `gc hook --claim --drain-ack --json`, received `action: drain` for no
assigned work, and stopped during its startup turn before BB supplied input.
That is correct behavior for the configured worker role. Conversation tests
must explicitly configure agents to await user messages and use tools for those
requests. They continue to import core, use real runtimes and verify complete
delivery; changing the test role does not certify conversational use of an
agent configured to drain itself.

Evidence remains under `/private/tmp/bb-live-9dbgrsx5`:
`claude-live5-global-dee00515/report.json` (pass),
`claude-live5-rig-653cea8f/report.json` (fail), and
`combined-live5-codex-pp0jab8r/{global,rig}/report.json` (fail).
The subsequent checks reuse the same city, BB server, ports, workspaces and
histories. GC is replaced only to load a changed binary; pack and role changes
use the running services.

After the asynchronous acknowledgment and conversational roles were installed,
Claude global and rig both passed the complete two-turn/tool checks under
`async-role-claude-ku5jdwqa/{global,rig}/report.json`. Codex rig also passed under
`verified-role-codex-qlo27dob/rig/report.json` (BB `thr_bmmfsj5r94`, GC `gc-213`),
including the reviewed-hook launch verifier. Codex global failed a transcript
stream-identity change despite receiving the request and producing the answer.

A subsequent controlled suspension of only `gc-213`, followed by new input in
its existing BB thread, failed the same identity guard. Its provider conversation
UUID changed; the controller cleared `session_key` before submission. Evidence
is in `codex-resume-evidence-ivo01e06/` and
`resumed-codex-rig-bber_f6k/rig/report.json`. The previous successful turns and
both provider transcripts remain intact. Resume is not certified, and the
uncertain operation has not been resent.

The pack's acknowledgment correction also needed a stop ownership guard:
canceling a waiting submission could let a newer turn start while the old stop
still updated its journal. A deterministic paused-journal regression reproduced
that corruption and now passes. All 37 provider tests and typechecking pass,
including actual wire acknowledgment, startup cancellation without remote
delivery, and preservation of uncertainty for an in-flight submit.

## Claude current approval menu and interruption

A separate conversational agent used Claude 2.1.263's `manual` permission mode
in the same retained city. The requested command only created a new nonce file
in that test workspace. Claude displayed a Bash approval modal, but GC returned
no pending interaction and BB showed none. The current screen uses “Do you want
to proceed?” and four numbered choices; GC expected older prompt/header text.

GC 1.4.0 and 1.4.1 both hardcode `deny` to key `3`. In the actual new menu,
`3` means approve and switch to auto mode, while `4` means No. No response was
sent. The runtime correction must parse the displayed choices, bind them to
the interaction identity, and select only the requested exact one-time Yes/No
action. A parser-only update would introduce an unsafe denial path.

BB's stop command then returned success and emitted an interrupted turn, but
the native approval modal remained open. GC's stop endpoint returned HTTP 200
after about 242 ms: its Ctrl-C did not dismiss the modal, and its idle detector
mistook the selected `❯ 1. Yes` row for an idle composer. The owning correction
must cancel a positively identified approval with Escape and require actual
idle settlement, preserving normal interruption for other states.

Private evidence is under `approvals-aiz094ar/`, including
`approval-report.json` and `stop-a65g_vwi/report.json`. The requested file remains
absent. The test provider requires an `options_schema_merge="by_key"` choice
override to render `--permission-mode manual`; overriding only the legacy
`permission_modes` map does not override GC's schema-managed CLI flag.

## Codex hook onboarding: confirmed startup gate

Codex CLI 0.153.4 requires separate trust for each non-managed hook definition;
trusting the workspace does not trust its hooks. In the retained test city,
both Codex workspaces were already trusted, but sessions `gc-47` and `gc-59`
stopped at “Hooks need review” for four GC-generated hooks: SessionStart prime,
PreCompact handoff, and UserPromptSubmit nudge/mail injection. After inspecting
the exact commands and their isolated city/config environment, the test operator
approved those four hooks in each existing session. Both resumed startup without
restarting GC. This authorized test onboarding is not permission to trust arbitrary
production hooks or enable a universal bypass.

GC's current tmux `Pending` parser recognizes Claude tool approval screens only;
this Codex startup gate therefore returns no pending interaction. GC does have
Codex startup-dialog handling elsewhere, but that path did not clear the gate
in these runs. Production needs
an actionable hook-review state directing the operator to inspect the affected
Codex session, with no automatic mapping of generic approval to hook trust.
The pack's bounded readiness wait prevents sending BB input into this gate, but
a timeout alone does not explain the required onboarding.

The CI harness now seeds native trust for the four exact reviewed hashes under
each fresh workspace's source-specific `[hooks.state]` keys. A launch verifier
rejects changed/extra hooks, unexpected workspaces, symlinked sources and the
wrong Codex configuration. Five guard tests pass, and comparison with actual
Codex trust records plus execution through the verifier succeeds. Other hook
sources retain their normal review requirements. No invocation-wide bypass
was introduced. The native key/hash behavior was checked against Codex
`rust-v0.153.4`; actual inference with this updated harness remains to be verified.
[Official Codex hook trust documentation](https://learn.chatgpt.com/docs/hooks).

Private evidence in `/private/tmp/bb-live-9dbgrsx5`: reviewed definitions and
native hashes in `codex-reviewed-hooks-gc47.json`, plus before/after pane captures
`codex-hooks-review-gc47-{before,after}.txt` and
`codex-hooks-review-gc59-{before,after}.txt`. Only the retained test root's
Codex configuration was updated; user configuration was untouched.

## Correction and validation

Corrections are being prepared in a separate GC worktree,
`/Users/csells/Code/gastownhall/gascity-bb-runtime-fixes`, branch
`fix/bb-live-runtime-compatibility`, based on released v1.4.1. The pack does not
pad prompts, inject terminal controls, weaken completion checks or silently
replace the user's installed supervisor.

Development GC builds carry a prerelease version and require the harness's
explicit `--gc-development-base` option. Their reports say
`verificationMode: development` and record the binary hash. They cannot serve
as acceptance evidence for the unchanged released binaries; the normal CI
matrix continues to use checksum-verified releases.

Full live validation of the corrections, broader lifecycle acceptance and
registry publication remain pending.

Development build `1.4.1-bb-live.2` passed `go vet ./...`. Its Claude global
and rig agents each completed both BB turns, preserved both complete forwarded
prompts, retained conversation context and produced the exact tool artifact. Evidence:
`/private/var/folders/6k/xzgngnms6jg4_z2l40y0_9vh0000gn/T/bb-development-v2-reports-p7eh_7op/claude/global/report.json`.
The adjacent `rig/report.json` records the other passing scope. The orchestration
process was then retired to retain and reuse the same GC city, so there is no
passing teardown/aggregate report. These results do not certify Codex, later
sessions in shared workspaces or released GC.

The test now requests and checks an exact final marker line, allowing preceding
explanatory prose. A prior completed tool turn had been rejected solely for
that prose. Eighteen guard tests retain completion, identity, tool and full
input checks; a marker embedded in prose or followed by more text still fails.

## Combined development validation and remaining Claude resume defect

The retained city loaded `1.4.1-bb-live.7` (`97ba30aa3`) while the same BB server,
store, ports, workspaces and prior transcripts remained in place. Both Codex
scopes passed three real BB turns: complete prompt delivery, tool artifact,
agent-only suspension, controller reconciliation, and a third tool-free memory
answer with unchanged GC/logical/provider/stream identities. Reports:
`live7-resume-fs7c2h4o/codex/{global,rig}/report.json`.

The manual Claude agent passed approve-once, denial without file creation, two
identical append commands requiring distinct BB interactions despite the same
GC request ID, and BB stop while awaiting approval. Stop removed the native
modal, preserved manual permission mode and left the unapproved file absent;
both BB and GC returned idle. Report:
`approvals-aiz094ar/approval-turns-r5xdhwcq/report.json`.

Claude global resume returned the correct native answer from the original
conversation, but GC lost its transcript key. The event store shows the valid
key through suspended/user-hold, canonical asleep and the initial resume, then
clears it during controller startup preparation. The exact transcript still
exists in the configured custom Claude directory. `staleResumeKeyProbe` uses
only default search paths, unlike worker history's configured observe paths;
its absence check wrongly treats this transcript as stale. The BB gate fails
instead of accepting an answer whose complete delivery can no longer be
verified. Evidence: `live7-resume-fs7c2h4o/claude/global/private/`, including
`diagnostic-bead.json`, `diagnostic-pane.txt` and before-suspend transcripts.

Independent pack review also reproduced a canceled observer's late rejection
and old startup timer terminating a successor turn. Failure callbacks now
carry their originating controller and ignore aborted or replaced owners.
Both regressions failed before the correction; 39 provider tests and
typechecking pass afterward.

## Claude underscore paths

A real isolated Claude 2.1.263 turn in `project_with_underscores` wrote its
transcript under a directory with hyphens in place of underscores. GC's reader
returned no exact-key transcript and its stale-key probe reported the existing
conversation as absent. The minimal correction adds the current spelling to
the legacy candidate list. It preserves exact-key matching and the existing
same-key alias policy; a newer transcript with another UUID cannot substitute.
Current and legacy layouts, absent keys and reverse alias refusal have
regressions. Corrected Go discovery also read the exact transcript produced by
the real CLI proof. Evidence: `claude-slug-proof-x03upvxy/report.json`.

## Longer conversations and workspace trust

Development `.8` (`f7e64f0b4`) passed Claude global and rig three-turn/tool/agent-
resume checks. Existing Codex conversations preserved their identities across
the GC binary replacement and completed another first turn. Their next tool
turns failed with `history_rewritten`. Independent snapshots show unchanged
message IDs, order, text and tool blocks, but older usage/model fields vanished.
GC enriched full structured history from a 64 KiB tail window; appending more
log data pushed the old metadata records outside that window. The owning fix
must derive stable per-message metadata from the complete parsed history,
including after a fresh adapter/server read. The pack reset guard stays strict.
Reports: `live8-final-dowk6nvn/{claude,codex}/{global,rig}/report.json`.

A new underscore workspace failed before receiving BB input because it had no
workspace trust entry. Claude 2.1.263 selected “No, exit” on its current trust
menu; GC's automatic startup-dialog handler blindly sent Enter, assuming the
trust option was selected. The session then exited and GC closed creation.
The test omitted the explicit trust provisioning used by the CI harness, which
exposed this separate GC compatibility bug. Both polling and streaming dialog
paths require an exact-menu correction under the existing auto-accept policy.
The role and underscore transcript lookup are independently verified. Evidence:
`live8-final-dowk6nvn/claude/underscore/report.json`, GC session `gc-493`.

The Codex correction uses token-count/context records already loaded by the
full parser, without an additional file scan; the bounded telemetry tail reader
retains its existing purpose. Both failed `.8` tool turns were independently
reviewed against complete prompt hashes, native logs, exact request-result
events, successful tools and artifact bytes. After the `.9` build loaded,
recovery initially rejected an active BB lease without changing the receipt.
The operator then released those two idle BB threads and ran reviewed recovery
once each. Both accepted receipts became completed with their original request
IDs; no prompt was resent. Evidence: `live9-released-recovery-km2q2sgn/report.json`.

Pack commit `d8d10fb` runs actual inference in CI with the newly configured Codex
key. Both build/CLI jobs pass. Both Claude jobs reach real conversations but
fail the final-answer marker assertion in both scopes. Safe diagnostics now
record only output size/hash and marker-presence booleans on that failure;
model output and private words remain excluded. The assertion stays strict.
Run: https://github.com/gastownhall/gascity-packs/actions/runs/34073849774.

## Final retained development conversations

GC `1.4.1-bb-live.9` (`55cfa4acc`) passes all five real BB conversation cases:
Claude global, rig and underscore workspace; Codex global and rig. Each case
passes three turns with full forwarded prompts of 3,108, 1,507 and 1,312 bytes,
an exact tool-created artifact, agent suspension/reconciliation and tool-free
memory recall after resume. All GC, logical, provider and stream identities
remain stable. An independent review recomputed all 15 prompt hashes from the
saved GC frames and verified their reliable idle state.

The four global/rig cases reuse threads from before the GC binary replacement;
their pre-replacement identities match the final frames. The existing BB server,
store, city, ports, workspaces and provider histories were retained. This proves
controlled supervisor replacement and continued conversations, not arbitrary
process loss during active work. Reports and binary/source hashes:
`/private/tmp/bb-live-9dbgrsx5/live9-final-jxzl2zm0/summary.json` and its five
case `report.json` files. The new Claude workspace passed without manually
seeding workspace trust. Existing Codex histories continued growing without
rewriting previously exposed metadata.

The two reviewed Codex recoveries changed only receipt state from accepted to
completed; request IDs, digests, baselines, targets and sessions stayed intact.
No prompt was resent. The prior Claude approve/deny/repetition/stop proofs were
run on `.7`; they are separate evidence, not fresh `.9` executions.

A further `.9` BB check selected the exact global agent with a different
existing scratch workspace. BB rejected the mismatch, emitted no input
acceptance, and left a creation-only receipt with no turn or GC submit result.
Evidence: `live9-lifecycle-1b4k6fph/mismatch-report.json`.

BB 0.42.1's public stop operation selects interruption for active threads and
release for idle/error threads. There is no separate public active-release
operation in the inspected CLI/server contract. Therefore an active approval
stop cannot be presented as a release proof. Existing idle release/restore and
pending-approval interruption have actual BB evidence; active bridge release
has provider-contract tests. Abrupt host/server loss, lost HTTP replies and
interruption during delivery still need live fault-injection evidence.

## Released-runtime CI after the corrections

[Pack CI run 34074336510](https://github.com/gastownhall/gascity-packs/actions/runs/34074336510)
at `2eb6424` fails all four live jobs and the required aggregate while both
build/fixture/CLI jobs pass. Codex global and rig on each released GC version
fail the bounded startup wait; no BB prompt was sent. All four Claude scopes
return the same 426-byte answer with SHA-256
`c6d2a670b7d411bea2d4e6b064840da6ebba19c060a72f1c350934d50e2cff8d`,
containing neither requested marker. This is not evidence of a formatting-only
failure or proof of a particular authentication/model error.

Claude 2.1.263's native error constructor writes API failures as assistant
records with `isApiErrorMessage` and error metadata. GC's current structured
reader omits that distinction, allowing such a record to appear as a completed
assistant message. That is a source-confirmed observability gap; the CI response
hash alone does not prove it caused these failures. CI uses repository Manifold
credentials/model aliases, while the successful local Claude runs use OAuth.
The harness now matches the failed answer's hash against its private native
records and publishes only finite error enums, the native error boolean and an
HTTP status where available. Seven guards protect the privacy boundary; the
original marker assertion remains strict. Raw output stays private.

[CI run 34074965026](https://github.com/gastownhall/gascity-packs/actions/runs/34074965026)
at `252ac34` confirms the cause: all four Claude cases match native API errors
classified as `authentication_failed`, HTTP 403, on the Manifold route. Both
build jobs pass; all four live jobs and the aggregate fail. This establishes
access rejection, not whether the token is expired or an access policy changed.
The workflow now supports a dedicated `BB_CLAUDE_API_KEY` for direct Anthropic
access and otherwise retains Manifold. Direct access unsets the Manifold token,
endpoint and model aliases; shell checks verify both routes and reject missing
Manifold model aliases. No direct Claude CI credential has been configured.
The available Anthropic vault notes are labeled for other projects, so none
was reused without approval.

The GC terminal-error correction is pushed as `59382ce25`. The matching pack
change uses one settlement path for success and typed provider failure, guarded
by complete prompt delivery, reliable idle, closed text/tools and no pending
interactions. A terminal provider error marks both BB and the durable receipt
failed, allowing an explicit later prompt. Recovery shares those guards and
cannot mistake an earlier planning message for success. Active retries stay
unsettled and a later successful answer can complete normally. Ordinary
transport failures preserve uncertainty. Forty-six provider tests, typecheck
and the actual BB 0.42.1 plugin build pass; the interrupt/release write race
is exercised for both success and failure. The five full `.9` conversation
runs precede this follow-up; error handling has the separate native producer,
API projection and pack-consumer evidence in the
[GC validation report](gc-runtime-fix-validation-2026-09-06.md).

## Final pack in the retained conversations

The final provider source (`b388fceaf975b9055dab85127a8270bcd457582046004e1adb0afb65d345a06e`)
was installed with prior installations preserved. All five existing threads had
completed receipts, empty BB queues and reliable GC idle state before their
idle bridge leases were released. Restored threads used the current source.
Neither GC nor BB was restarted; GC remains development `.9`.

Codex global and rig pass three fresh turns each, including complete forwarded
prompts, actual tool artifacts and tool-free memory after agent suspend/resume.
Both retain their original GC, logical, provider and stream identities across
BB release/restore and agent resume.

All three Claude cases fail their first turn. The identical 68-byte answer hash
`68df770c7fe4ffda5f92b07ff9d33479cea0fac7db53547d9285fc32959568cf`
matches native `isApiErrorMessage=true`, `error=rate_limit`, HTTP 429. Each full
3,108-byte forwarded prompt, request correlation, receipt digest and prior
identity is independently verified. No prompt was resent. Their receipts are
completed because the retained `.9` GC still projects native errors as assistant
answers; the new GC error-projection commit is not loaded in that server.
The strict marker gate correctly fails. Earlier five-case success does not
certify the final pack's Claude behavior. Safe reports are retained under
`/private/tmp/bb-live-9dbgrsx5/current-pack-fivecase-ki6iozqc`.
