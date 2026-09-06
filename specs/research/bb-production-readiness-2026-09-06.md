# BB pack production readiness — 2026-09-06

## Assessment and scope

Reviewed `feat/bb-provider-gascity-1.4` at `b8b255256d7fc218e3a6854d5b2069c515c5c17f`, including the complete `bb/` implementation, tests, installation command, and CI. The working tree was clean at assessment start. This report proposes work; no implementation or external publication was performed in this assessment.

The pack is staging quality. A bounded production release is feasible with pack changes: fix the confirmed lifecycle/discovery bugs, harden recovery and upgrades, and validate actual BB/GC conversations. A dedicated Gas City launcher can provide project-first selection with released BB extension APIs. Changing BB's native Model picker still requires BB core changes. The latter need not gate a separately advertised launcher or an existing-workspace-only release.

## Verified release baseline

- Latest stable Gas City in the 1.4 line: **1.4.1**, released 2026-08-15, commit `58ef17e3bd685fd5cf7f21286277b208d3324590`. The 1.4.0→1.4.1 diff changes the beads dependency and tests/CI/docs, not the adapter's production API/runtime contracts. [Release](https://github.com/gastownhall/gascity/releases/tag/v1.4.1), [changelog](https://github.com/gastownhall/gascity/blob/58ef17e3bd685fd5cf7f21286277b208d3324590/CHANGELOG.md).
- Latest BB desktop and npm `bb-app`: **0.42.1**, released 2026-09-05, commit `a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78`. Its source declares **SDK 0.4.47**, matching this pack's dependency. npm separately reports SDK 0.4.48 as latest; that is not evidence that the released desktop requires a dependency bump. [Release](https://github.com/get-bb/bb/releases/tag/desktop-v0.42.1), [release SDK manifest](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/packages/plugin-sdk/package.json#L1-L3), [npm SDK metadata](https://registry.npmjs.org/@get-bb%2fplugin-sdk/latest).

## Confirmed defects to fix first

### 1. Repeated approvals hang a later turn

`session.pending` permanently remembers approval IDs. GC tmux IDs derive from tool name and input, so repeating a command can reuse an ID. The bridge then suppresses the new question. An isolated reproduction using the existing fixture submitted two approval turns but produced one question and one completed boundary; the second turn remained busy.

Bound deduplication to the actual pending interaction, handle its resolution/clearing, and test repeated approvals within and across turns, denial, and resolution outside BB. [Bridge](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/assets/plugin/src/provider.ts#L272-L276), [GC ID hash](https://github.com/gastownhall/gascity/blob/58ef17e3bd685fd5cf7f21286277b208d3324590/internal/runtime/tmux/interaction.go#L149-L151).

Reproduction artifact: `/var/folders/6k/xzgngnms6jg4_z2l40y0_9vh0000gn/T/bb-gc-approval-repro-A9XYsF/repro.mjs`.

### 2. Steering falsely tells BB that an active turn is gone

The pack always responds to `turn/steer` with `NO_ACTIVE_TURN`. BB 0.42.1 interprets that error by clearing its active-turn state. Declaring `steerMode: queue` does not make BB queue for the provider: released documentation explicitly says the declaration is recorded but not acted upon. This is a source-confirmed contract mismatch; a full BB UI reproduction has not been run.

Implement the intended queue contract, or return an honest unsupported-operation response that preserves BB's live-turn state and visibly retains/rejects the input. Verify user follow-ups, stop, retries, and reconnect through the real runtime. [Pack](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/assets/plugin/src/provider.ts#L151-L153), [BB runtime](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/packages/agent-runtime/src/runtime.ts#L2141-L2146), [queue contract](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/docs/provider-plugin-api.md#L161-L165).

### 3. A stale binding breaks unrelated workspace discovery

`bindingFor` resolves every configured path with `realpath`. If any old worktree no longer exists, it throws before selecting a valid unrelated binding. An isolated check with one valid binding and one missing unrelated path reproduced `ENOENT`.

Skip missing paths with an actionable warning, preserve the binding configuration, and validate the relevant project/rig at execution. Add coverage for missing, ambiguous, and recreated paths. [Implementation](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/assets/plugin/src/config.ts#L62-L71).

Reproduction artifact: `/var/folders/6k/xzgngnms6jg4_z2l40y0_9vh0000gn/T/bb-binding-review-n6fpet95/check.mjs`.

## Production work beyond those defects

### Recovery and ownership

Keep the no-blind-resubmission rule. Add tested recovery for lost creation responses and crash-left locks, using stored request information/deterministic aliases and verified ownership. Current `recover` requires a session ID and turn receipt and takes the same directory lock that a crash can leave behind. It cannot reconcile those cases. [Journal](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/assets/plugin/src/journal.ts#L21-L29), [recovery command](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/assets/plugin/src/cli.ts#L76-L89).

Recovery currently accepts an idle transcript without reconciling the recorded async request. GC can continue async submission after HTTP acceptance, so test delayed delivery before considering an idle snapshot conclusive. Also test recovery versus a live writer and overlapping host processes: submit/completion do not acquire the start/recovery lock. These are source-based risks and missing guarantees, not separately reproduced end-to-end failures. [GC asynchronous submit](https://github.com/gastownhall/gascity/blob/58ef17e3bd685fd5cf7f21286277b208d3324590/internal/api/huma_handlers_sessions_command.go#L713-L734).

### Project and workspace UX using released BB capabilities

The native model-list request still carries only `cwd`; its project-first discovery gap remains. The native picker also substitutes a default/first model when a selection disappears. A complete native solution needs project/host/environment-aware requests and cache keys, stale-response handling, an explicit invalid selection state, and agent labels/grouping. [Request schema](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/packages/provider-bridge-protocol/src/requests.ts#L41-L43), [selection fallback](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/apps/app/src/hooks/thread-creation-options/model-catalog-selection.ts#L95-L110).

A pack-only launcher is feasible: contribute a navigation panel/homepage section, query the chosen host through typed host RPC, call `discover({projectId})`, and use `bb.sdk.threads.spawn` with explicit project, provider, model, execution-input provenance, and environment. This is a design inference from released API contracts, not an implemented or UI-tested flow. Composer defaults are seeds rather than enforced selections, so a custom launcher must validate its submission. [UI slots](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/packages/plugin-sdk/src/app-contract.ts#L1409-L1420), [host RPC](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/packages/plugin-sdk/src/host-contract.ts#L19-L32), [server SDK](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/packages/plugin-sdk/src/backend-contract.ts#L1685-L1694), [thread spawn inputs](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/packages/server-contract/src/api/threads.ts#L95-L109).

For coding, guide the user to a matching unmanaged environment and enforce matching BB/GC paths. Keep the documented conversation-only mismatch option explicit. A project binding does not synchronize separate checkouts. This can remain a same-host v1; remote filesystem adoption need not block it. [Current workspace contract](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/README.md#L121-L133).

### Installation, updates, and distribution

The installer overwrites the active path before npm installation/build succeeds. Since BB path installs register that directory in place, a failed upgrade can leave the next load using partial sources/dependencies. Stage and validate a versioned installation before activation, retain the previous working installation, and test failures without touching configuration/journals. Alternatively adopt BB's managed artifact/update path with its compatibility and rollback checks. [Installer](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/commands/install/run.sh#L9-L14), [BB path registration](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/apps/server/src/services/plugins/plugin-registration.ts#L403-L436), [managed update contract](https://github.com/get-bb/bb/blob/a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78/apps/server/src/services/skills/builtin-skills/bb-plugin-authoring/references/quickstart.md#L148-L174).

Declare tested compatibility accurately, make doctor report registration/binding/recovery failures rather than only supervisor reachability, and publish through the pack registry after the gates pass. Replace staging-branch installation links with the stable release path. Adding a BB marketplace entry is optional distribution work, not a transport requirement. [Doctor/status](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/assets/plugin/src/cli.ts#L62-L73), [existing release gate](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/bb/docs/staging.md#L79-L100).

### Real integration gate

Run BB 0.42.1 with isolated GC 1.4.1 cities and actual supported model runtimes. Exercise global and rig agents, first/second prompt, tools, repeated approve/deny, follow-up while busy, stop before/after acceptance, release without killing GC, completed resume after restart, disconnected hosts, stream replay, transcript reset, lost HTTP responses, recovery, and workspace mismatch. Test the actual launch UI and fresh install/update path. Keep the inference gate separate from deterministic fixture checks, but require a recorded successful run before promotion.

The current CI tests the SDK fixture and GC CLI, not a complete BB application. Extend the compatibility matrix to GC 1.4.1 and the actual BB release; retain 1.4.0 if still claiming it as the minimum. [Workflow](https://github.com/gastownhall/gascity-packs/blob/b8b255256d7fc218e3a6854d5b2069c515c5c17f/.github/workflows/bb-provider.yml).

## Evidence collected and limitations

- Existing branch CI completed successfully, covering 15 provider tests, TypeScript/build, and four GC 1.4.0 CLI checks. [Run](https://github.com/gastownhall/gascity-packs/actions/runs/34049732645).
- During this assessment, downloaded the official GC 1.4.1 Darwin ARM64 archive, verified SHA-256 `019e5ae701531d5c080fdf99d2dc1e3c046ae76d2735918c4d94ecd5ed8ac7a0`, and ran all four actual CLI checks successfully with Python 3.12. No installed binary or existing city was changed.
- Read the exact BB 0.42.1 release source and compared GC's peeled 1.4 tags. Reproduced repeated approval suppression and stale-path discovery failure in scratch fixtures.
- Earlier live discovery found five global agents on the user's GC 1.4.0 supervisor. This is discovery evidence only. The installed BB desktop was 0.41.0; BB 0.42.1 UI/inference was not executed in this assessment.
- Text-only input, no arbitrary existing-session attachment, no fork/rename/archive/compaction, no usage accounting, and tmux-only approval mapping can remain explicit v1 limits. Supporting every BB capability is not necessary for a reliable bounded release. Unsupported runtime choices should be identified before launch.

Recommended order: fix the three confirmed defects; harden ownership/recovery and upgrades; choose existing-workspace scope or build the dedicated launcher; run the real integration matrix; publish a versioned registry release. Native picker improvements and richer session features can follow independently.
