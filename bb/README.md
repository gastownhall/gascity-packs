# BB provider for Gas City

Experimental **0.1.0**, staged on `feat/bb-provider-gascity-1.4`. This pack
connects unmodified [BB](https://github.com/get-bb/bb) to configured agents in
**Gas City 1.4.0** through BB's public provider bridge and GC's HTTP session API.
It is not yet a registry release.

In BB, select **Gas City** as the provider. The existing **Model** picker shows
agent choices such as `alpha · Global · gc.mayor [local]` and
`alpha · web · review.reviewer [local]`. Gas City retains the agent's model,
prompt, tools, permissions, and runtime configuration.

## What this first stage provides

| BB concept | Gas City mapping |
| --- | --- |
| Provider | One `gas-city` provider, configured independently on each BB execution host |
| Model choice | Exact configured agent identity: connection + city + qualified agent name |
| Project | Explicit BB project ID → connection + city + rig binding |
| Existing workspace | Longest matching configured checkout/worktree path |
| Thread | One new template-backed GC session, with a durable local ownership receipt |
| Prompt / streamed answer | GC asynchronous submit / structured transcript SSE |
| Interrupt | Stop the active GC turn |
| Release / host disconnect | Detach the BB bridge; retain the GC session |

Projectless discovery lists global agents from every running city on the
configured supervisors. A mapped project lists its city's globals plus that
rig's agents. Expanded configuration is the catalog source, so scale-zero
templates remain discoverable. Suspended cities, rigs, and agents are excluded.
Qualified identities distinguish identically named agents across cities, rigs,
and connections.

**Current BB limitation:** its `model/list` request has a working directory but
no selected project ID. The pack can filter an existing workspace whose path
has been bound. Selecting a project in a fresh New Thread dialog cannot yet
refresh the picker with that project's rigs. The CLI can show that exact list
today, and execution revalidates the selected target against the actual BB
project before creating the session. This branch does not promise the finished
project-first picker UX; see [staging](./docs/staging.md).

## Prerequisites and topology

- Gas City **1.4.0**, with a running supervisor and configured agents that can
  create sessions and produce a reliable structured transcript.
- BB with the public provider bridge used by `@get-bb/plugin-sdk` **0.4.47**.
  The plugin declares SDK compatibility `>=0.4.47 <0.5`.
- Node.js **22+**, npm, and the BB CLI.
- For the initial setup below, the BB server, BB execution host, Gas City, and
  pack checkout are on the same machine and run as the same operator. This
  also makes working-directory checks meaningful.

The adapter runs inside BB's host-side provider infrastructure. There is no
new HTTP service, ACP server, or background process started by importing this
pack. Separate BB hosts need their own GC configuration, filesystem paths,
and journals; a journal is not a portable cross-host session locator.

## Install this branch

Clone the staging branch, then import its local path from a Gas City city:

```sh
git clone --branch feat/bb-provider-gascity-1.4 \
  https://github.com/gastownhall/gascity-packs.git
cd /absolute/path/to/your-city
gc import add --name bb /absolute/path/to/gascity-packs/bb
gc bb install
gc bb connect --id local --url http://localhost:7375
gc bb status
gc bb agents
```

Use your supervisor's actual URL if it differs. `install` copies the adapter
out of the pack cache, installs locked npm dependencies, builds its helper
CLI, and invokes `bb plugin install path:<installed-directory>`. It forwards
`--yes` only when you explicitly pass it. Importing the pack alone performs
none of these installation steps.

Use the **Gas City** provider in BB and choose a qualified global agent.
Select **Full access**: this is the bridge's supported BB permission mode;
the agent's existing Gas City permission policy still applies. GC tmux
approval requests are shown as explicit BB questions offering **Approve once**
and **Deny**. Selecting Full access does not automatically answer them.

To update, pull this branch and run `gc bb install` again. Configuration and
session receipts live outside the installed adapter directory.

## Bind projects and existing workspaces

Use the stable BB project ID, not its display name. For example:

```sh
gc bb bind --project proj_example --id local --city alpha --rig web \
  --path /absolute/path/to/web-checkout \
  --path /absolute/path/to/existing-bb-worktree
gc bb agents --project proj_example --json
gc bb agents --cwd /absolute/path/to/existing-bb-worktree
```

Each path must exist. Multiple `--path` arguments cover existing worktrees;
newly allocated BB worktrees must be bound separately. Rebinding replaces
only that project's mapping on this host. Ambiguous workspace matches and
unmapped standard BB projects produce an error. BB's personal project
(`proj_personal`) remains projectless.

For a first rig-specific conversation without BB changes, use a BB unmanaged
environment pointing at a bound existing checkout. The picker can then obtain
its catalog from that workspace. `gc bb agents --project ... --json` also
returns the exact opaque IDs for BB clients that accept an explicit model ID;
this pack does not install a separate session launcher.

BB currently memoizes provider catalogs for up to ten minutes on the server,
with a separate browser cache. After changing mappings or GC configuration,
wait for that cache to expire or restart the BB server and reload the UI.
Reopening the browser alone does not clear the server cache. The CLI's
`agents` command always discovers afresh. BB's own default-model selection
behavior is unchanged; inspect the selected agent before starting a thread.

## Checkouts and configuration

Gas City owns the session checkout. The bridge does not silently move a rig
agent into BB's newly created worktree.

- `conversation` (default) allows different directories and posts a visible
  notice in the conversation. BB file and diff views do not automatically
  describe changes made in GC's different checkout.
- `require-match` blocks prompt submission unless the real BB and GC working
  directories match. Use a matching unmanaged BB environment for coding.

Set the policy while configuring a connection:

```sh
gc bb connect --id local --url http://localhost:7375 \
  --workspace-policy require-match
```

The host-local JSON file defaults to
`${XDG_CONFIG_HOME:-~/.config}/gascity/bb.json`:

```json
{
  "version": 1,
  "workspacePolicy": "conversation",
  "connections": [{ "id": "local", "url": "http://localhost:7375" }],
  "bindings": [{
    "projectId": "proj_example",
    "connection": "local",
    "city": "alpha",
    "rig": "web",
    "paths": ["/absolute/path/to/web-checkout"]
  }]
}
```

`GC_BB_CONFIG` overrides the config file. `GC_BB_INSTALL_DIR` overrides the
adapter install location (default `${XDG_DATA_HOME:-~/.local/share}/gascity/bb/plugin`).
Receipts live under `${XDG_STATE_HOME:-~/.local/state}/gascity/bb/sessions`.
Configuration and receipts are atomically written with private file modes.

Connections accept loopback HTTP or an authorized HTTPS proxy. An optional
`GC_BB_AUTH_TOKEN` environment variable supplies a bearer token to that proxy;
it is not stored in JSON or exposed in BB model IDs. One token applies to all
configured connections. URL credentials and redirects are rejected.
`X-GC-Request` is sent on writes for GC's request guard; it is not authentication.
Direct hardened deployments requiring GC-specific city grants are outside
this stage; access-denied responses are surfaced to the operator. Remote
proxies do not remove the same-filesystem requirement of this version.

## Conversation lifecycle and recovery

The bridge creates a template-backed GC session with a deterministic alias
derived from the BB thread ID. It waits for the correlated asynchronous
creation result and saves the actual GC session ID. It does not attach to a
pre-existing canonical agent conversation. GC singleton/capacity rules still
apply; choose an agent configuration that permits a new session.

Each text prompt is journaled before posting. A successful submit result means
queued/delivered, not finished. Completion requires new assistant output, a
reliable idle transcript, and no unfinished text, tools, or interactions.
Stream replay is deduplicated by structured message/block identity. The
bridge reports transcript rewrites, degraded history, and unknown interaction
types instead of presenting a successful turn.

A fresh session can temporarily have only GC's terminal fallback. For its
first prompt, the bridge checks for pending interactions, submits once, and
waits up to 150 seconds for normalized history containing that exact prompt.
Terminal fallback text and startup output are not rendered as its answer.
If structured history never becomes available, the turn fails visibly and
keeps its receipt for inspection. Existing conversations require a reliable
idle transcript before accepting another prompt.

Completed threads resume the same GC session on the original BB host. An
interrupted stream or uncertain HTTP response can leave remote work running.
The bridge then blocks resubmission/resume until the operator inspects it:

```sh
# Read the complete remote transcript in Gas City first.
gc bb recover --thread <BB-thread-ID> --confirm-reviewed
```

Recovery verifies an idle, non-degraded transcript with no pending tools or
interactions. It acknowledges output you reviewed; it does not import that
missing history into BB or resend the prompt. Preserve the journal when
reinstalling. Ambiguous session creation and crash-left lock directories need
manual inspection of the receipt and deterministic alias; this helper does
not guess a replacement session or break a lock automatically.

## Deliberate limits

- Agent choices are configured, expanded templates. GC 1.4's config endpoint
  does not enumerate every dormant named conversation. Generic rig templates
  without a resolved `dir` are skipped with a warning; import roles at rig
  scope so GC expands their identities.
- One active BB turn per session; text input only. Inline attachments, BB
  dynamic tools/skills injection, agent switching, fork, rename, archive,
  manual compaction, and model/reasoning/tier overrides are not implemented.
- Only the verified GC tmux approval interaction is translated. Other
  interactions require responding in GC and recovering the BB thread.
- GC tools and text appear in BB. Full fidelity usage, specialized tool UI,
  arbitrary named-session attachment, remote checkout adoption, and automatic
  mid-turn reconnect recovery are later stages.
- This is a branch for integration testing. The automated gates below do not
  establish live BB UI or model-backed runtime compatibility.

## Development and checks

```sh
cd bb/assets/plugin
npm ci --ignore-scripts
npm run typecheck
npm run build
npm test
cd ../../..
GC_TEST_BIN=/absolute/path/to/gc-1.4.0 \
  python3 -m unittest discover -s bb/tests -v
```

The TypeScript tests exercise a GC 1.4-shaped HTTP/SSE fixture and BB's
published bridge conformance runner: scoped discovery, exact identities,
async creation, prompt delivery, replay, tool deltas, resume, interrupt,
release, checkout mismatch, lost responses, and explicit approvals.
The Python checks use the **actual released GC binary** for pack lint,
resolved configuration, command discovery, and executable entrypoints.
The dedicated workflow pins GC 1.4.0 and verifies its download checksum.

The layout follows this repository's pack pattern: schema-2 `pack.toml`,
documented `commands/*/run.sh`, a `doctor` check, and adapter code under
`assets/`. No agent definitions or runtime configuration are changed by this
integration. See [staging and contract references](./docs/staging.md) for
the next BB PR and release gates.
