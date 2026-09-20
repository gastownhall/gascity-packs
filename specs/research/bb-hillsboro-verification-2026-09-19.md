# Hillsboro BB provider qualification

Status: IN PROGRESS. This report records observed results, not a release
certification. Production data and previous installations are preserved; all
inference, fault injection, and installation tests use marked scratch roots.

## Artifacts

- BB 0.43.3 and plugin SDK 0.4.104.
- Current provider/harness snapshot:
  `/home/ubuntu/bb-gascity/releases/20260920-completion-11`.
  It includes visible provider-error events and corrections to recovery and
  process-identity assertions, in addition to the earlier test-state handling,
  automatic-memory isolation, and fixture discovery changes. Completion-9
  corrected process-exit and queue-shortcut harness handling. Completion-10
  changes only the lifecycle case module and its tests to handle the fixture
  service manager. Completion-11 changes only three test files: the shared
  conversation startup prompt, the browser case module, and its regression
  tests. Startup now explicitly says `Ready.` without tools or workspace
  inspection, and a failed BB turn ends approval waiting with diagnostic
  evidence. Its plugin is identical to completion-8/9/10. Completion-8's
  sole plugin change from completion-7
  corrected the CLI's catalog-refresh advice. Plugin source SHA256:
  `b17e84154ec378a97826c0eacc8f11ebd7f09a8d5b7b3e309e853564eb16039f`.
- GC base: released 1.4.2, commit
  `d4582166367aa687c1b62b296247ba0fb0a7e094`.
- GC candidate: `1.4.2-bb-runtime.4f41f8285070`, commit
  `4f41f8285070d3509dae94cd97509eb562f2f068`.
- GC binary SHA256:
  `ab81653e1542c5422e1ac1405e3eddef781fdce6eae283b18670b4f01cccfdad`.
- Claude CLI 2.1.270 on both model routes: native Manifold Claude, and
  Manifold Moonshot's `kimi-for-coding` through the Claude Anthropic adapter.
  This does not certify GC's native Kimi CLI adapter.

The candidate directory retains its build log, manifest, and complete source
patch against the release. The scrubbed [build manifest](bb-hillsboro-evidence-2026-09-19/gc-build-manifest.json)
and [source patch](bb-hillsboro-evidence-2026-09-19/gc-1.4.2-bb-runtime-4f41f8285070.patch)
are retained in this repository. The GC corrections cover workspace trust,
explicit API errors, intentional suspension identity, configured transcript
roots and fresh UUIDs, approval menu binding, interruption at an approval, and
underscore-containing workspace transcript paths. The latest two commits
recognize Claude's standalone tool-interruption message as idle while rejecting
that text when merely quoted inside another message.

## Automated checks

Completion-11 passes all 193 Python checks without skips on Hillsboro using
the raw released GC 1.4.2 binary. Completion-10 passed 192 checks; the new
regression proves an already-failed startup does not wait for an impossible
approval and retains its native pending interaction without answering it.
Its 36 Linux lifecycle guards include actual
zombie-child handling and service-manager ownership checks; independent review
found no confirmed defect in the manager-aware change. The unchanged browser
harness retains all 29 passing browser/desktop guards
(`completion9-browser-tests.log`). Its unchanged plugin retains completion-8's
61 passing provider tests (`completion8-plugin-tests.log`), TypeScript, and CLI
build checks. Earlier Python counts of 150, 161, and 175 and browser/desktop
counts of 23 are historical; completion-9's 184 Python checks are also a prior
snapshot result. All six affected GC package suites and each
commit's formatting, lint, code generation, and full vet hooks pass.

The broad GC baseline is not green. The identity work reproduced
`TestCustomTypesCheck_MissingTypes` on unchanged release source under the same
login-shell environment. A separate broad run also encountered unrelated
probe timeouts and installed-CLI incompatibilities; its detached-probe failure
passed alone. These do not count as a passing broad suite.

## Live observations

Evidence paths below are beneath `/home/ubuntu/bb-gascity/evidence` on Hillsboro.

| Route/run | Result |
| --- | --- |
| `completion11-kimi-full` | Fresh full matrix running with the clarified startup prompt. No overall pass yet. |
| `completion11-approval-interrupt` | Approval interruption passed in a new fixture; 39 cases unexecuted. This targeted proof does not replace the full matrix or rewrite snapshot-10. [Scrubbed summary](bb-hillsboro-evidence-2026-09-19/completion11-approval-interrupt-summary.json). |
| `completion10-kimi-full` | Finished: 39 passed, one failed, zero blocked, zero unexecuted. Approval interruption failed before the user task reached GC: Kimi requested a directory listing during startup instead of reporting ready. The provider correctly failed closed on that pending interaction. The task's tool did not execute. Snapshot-11 clarifies startup instructions and reports failed startup immediately; this failed ledger remains unchanged. [Scrubbed summary](bb-hillsboro-evidence-2026-09-19/completion10-summary.json). |
| `completion10-kimi-gc-lifecycle` | Three passed, 37 unexecuted: personal conversation, GC controller restart, and GC binary replacement. This focused subset is incomplete, not an aggregate pass. [Scrubbed summary](bb-hillsboro-evidence-2026-09-19/completion10-gc-lifecycle-summary.json). |
| `completion9-kimi-full` | Finished: 39 passed, one failed, zero blocked, zero unexecuted. Only GC binary replacement failed: the harness raced the fixture service manager's automatic controller restart. Manager-aware replacement handling is corrected in snapshot-10 and passed independent review, automated guards, and the focused and full snapshot-10 live runs. This failed summary remains unchanged. |
| `completion9-kimi-restarts-queue` | Four passed, 36 unexecuted in the retained snapshot-8 environment: personal conversation, BB host restart, BB server restart, and busy follow-up. This focused subset is incomplete, not an aggregate pass. |
| `completion8-kimi-full` | Finished: 37 passed, three failed, zero blocked, zero unexecuted. Host restart failed when the target process exited between observations; the server restart then failed from that incomplete transition. Busy follow-up failed before queue submission because the browser guard rejected BB's appended shortcut hint and assumed a Mac shortcut on Linux. Snapshot-9 corrects these two harness causes; this failed summary is retained unchanged. |
| `completion7-kimi-full` | Three chat cases passed: personal, mapped global, and mapped rig. Stopped early to pin the final CLI catalog-refresh advice correction; 37 cases remain unexecuted. The diagnostic-stop record and all state are preserved. |
| `completion7-kimi-recovery` | Two passed, 38 unexecuted: lost-create-response and uncertain-delivery bridge recovery. Uses the completion-7 plugin and current GC pins recorded below; this diagnostic subset remains incomplete. |
| `completion6-kimi-critical` | Three passed, one failed, 36 unexecuted. Lost-submit-response, streaming-disconnect, and interruption passed. Bridge-crash error text was visible, but the browser assertion incorrectly compared JSON-escaped text; that failed ledger remains preserved. Completion-7 corrected the guard and subsequently passed bridge recovery. Uses the same plugin and GC hashes as completion-7. |
| `native5-error-rendered-20260920` | Provider-error case passed; 39 cases unexecuted. An actual native invalid-token error is visible in the screenshot and BB UI, with `provider/error` marked `willRetry=false`, exactly one failed completion, a native typed error, one create and one submit, and no retry. Uses GC `d66ac779f2c4` and the same plugin source hash as completion-5/6/7. |
| `completion5-kimi-full` | Personal conversation passed; run stopped before further settled cases after an independently confirmed GC interruption-marker defect required a new pinned binary. Services, sessions, and evidence were preserved. |
| `completion4-kimi-full` | Retained ledger: 22 passed, 13 failed, five unexecuted. Passes include all three chat scopes, both launchers, release/restore, agent resume, six reasoning choices, immutable reasoning, provider switching, approve/repeat, fresh trust, configured mayor, workspace checks, and fresh installation. Denial, transport recovery, process lifecycle, upgrade/rollback, and busy-follow-up cases failed. The run stopped after confirming GC could remain in-turn after interruption; harness assertion defects were also found. This run remains incomplete. |
| `bb-native-v4-diagnostics-1a0522f99e` | Nine passed, two failed, 29 unexecuted. Approve/repeat, fresh trust, both workspace checks, fresh installation, approval interruption, startup error, and timeout passed. Denial and provider-error rendering failed. |
| `kimi4-denial-supplement-j2h3Dx` | Supplemental read-only browser verification of the original denial passed (`denial-browser-duration-verified.json`), followed by a passing same-conversation follow-up. The denied artifact remained absent; original turn/request identities were retained. The original failed ledger is unchanged. |
| `native-denial-supplement-s9mKrZAFjz` | Supplemental browser verification of the original denial and a same-conversation follow-up passed; the denied artifact remained absent. The original failed ledger is unchanged. |
| `final-kimi-d66ac779-core` | Personal conversation passed two turns, full prompt correlation, tool artifact and memory; BB release/restore passed. Native suspension failed an asleep-only harness assertion despite a stopped interval and restart with the same UUID. The corrected assertion later passed in completion-4. |
| `final-kimi-d66ac779-product` | Mapped-project/global, both launcher scopes, and provider switching passed. The rig first turn invoked automatic disk memory and failed the no-tools assertion. Scratch memory isolation was corrected; mapped rig conversation later passed in completion-4. This older run stopped before repeating the confirmed BB catalog-cache fixture failure. |
| `bb-native-final-core-eff3432a0b` | First native Claude turn passed. Upstream rejected the tool follow-up with a safeguard error; dependent lifecycle cases remained blocked. No retry of the refused request. |
| `native-provider-error-proof-0a9df1e3b0` | Verified native `provider_error` with `invalid_request`, BB terminal status `failed`, and preserved internal error text. This proves failed settlement, not a visible BB error row. |

The completed completion-6 critical and completion-7 recovery summaries use
plugin SHA256 `989e2f1f827ce62035e3d5bdd4455fb8282fd089bf6955e8543ddeb5b08ec09e`.
Both have the same current GC commit and binary hash recorded above. The
completion-8, completion-9, and completion-10 full-run summaries match those GC pins and plugin
SHA256 `b17e84154ec378a97826c0eacc8f11ebd7f09a8d5b7b3e309e853564eb16039f`
exactly. Earlier proofs retain their original plugin identity.

The startup failure's read-only diagnosis is retained privately as
`completion10-approval-startup-diagnosis-4ee32752/report.json`. Its native
transcript contains only the GC startup message, followed by the unrequested
directory-listing tool call; the BB task is absent. No approval or resend was
performed. Earlier scrubbed [snapshot-8](bb-hillsboro-evidence-2026-09-19/completion8-summary.json)
and [snapshot-9](bb-hillsboro-evidence-2026-09-19/completion9-summary.json)
summaries preserve the preceding failures.

The completion-4 runs used GC `d66ac779f2c4ded70745730c492023052b84b3c1`
(binary SHA256 `7b8f06282385b4d61f813cd0d9e343af8cf86136d69530d2b8333e6dec0a5df0`).
Their failures remain recorded rather than being converted to passes by later
fixes or supplements. In particular, failed turn settlement alone did not
render the provider error in BB. The current plugin explicitly emits
`provider.error` for that UI; the fresh native invalid-token diagnostic above
proves rendered failure without retry. That single-case proof leaves the
complete matrix incomplete.

The runners verify the loaded provider registration and complete installed
source, running BB version, running GC commit and binary hash, and pinned raw
and launch runtime artifacts. Diagnostic subsets leave omitted requirements
unexecuted; they cannot produce an overall pass.

GC's `/suspend` response is now checked against both stopped states,
`suspended` and `asleep`, with `running=false`. Every observation is saved;
the later recall still requires unchanged native identity and no tool use.
Scratch runtimes disable automatic disk memory so it cannot masquerade as
conversation recall. Native launch isolation uses a private, hash-verified
child wrapper that only sets that memory flag and executes the original
qualified CLI. Its actual official-launcher `--version` integration passed;
the original launcher configuration remains unchanged.

BB 0.43.3 retains picker catalogs for ten minutes, including across plugin and
server restarts. The test runner prepares separate untouched fixtures before
cases, then waits for ordinary public discovery when they are first needed.
It does not change the cache, application clock, or stored catalog rows.

## Scope boundaries

Deployment has not been activated. The completion-11 proposal at
`/tmp/bb-gascity-deployment-review-ppt6o__j` contains 14 proposed files and
121 artifact pins; its review checks are finishing. It uses the same pinned
provider and GC artifacts and the clarified conversation startup instructions.
Earlier proposals and all original state remain preserved; they are not
evidence of a completed installation.

Hillsboro qualification uses the two authorized available model routes.
Original stock-GC Claude/Codex CI gates, macOS desktop qualification, and public
registry publication remain separate requirements. A patched GC pass cannot
certify unchanged 1.4.0–1.4.2. Codex quota availability and the ZCode GLM5.3
upstream billing failure are not fixed by the provider pack; ZCode's requested
GLM5.3 default is retained.
