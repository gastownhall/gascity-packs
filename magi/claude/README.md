# claude_dist

**Author:** magi pack maintainers

A self-contained, idempotent distribution of a hardened Claude Code harness. Drop the directory anywhere, run `deploy_harness.sh`, and the deployer materializes a complete `~/.claude/` configuration: the behavioral contract, hook-driven enforcement, twenty-one MCP servers (eight local, thirteen remote-over-SSH), twenty-eight curated subagents, slash-command skills, language-server plugins, and (on macOS) launchd cleanup agents. Every overwrite is backed up. Every placeholder is substituted at deploy time. Every secret stays in `.env` and is never copied verbatim into the deployed tree.

This README documents everything `claude_dist/` contains, what `deploy_harness.sh` does step-by-step, how to bootstrap from the magi pack-root `.env`, and how to roll back cleanly if you decide you hate it.

---

## What ships

The repository ships exactly three things at the top level:

```
claude_dist/
├── deploy_harness.sh  # the installer
└── harness/           # source-of-truth tree, copied to ~/.claude/
```

`harness/` is a snapshot of a working `~/.claude/` directory with literal user-specific values replaced by `__PLACEHOLDER__` tokens. The deployer copies the tree into your real `~/.claude/`, substitutes every placeholder against values from the magi pack-root `.env` (or interactive prompts), deep-merges any pre-existing `settings.json` and `.mcp.json` rather than clobbering them, locks the credentialed MCP config to mode `0600`, and (optionally) installs the launchd cleanup agents.

The deployer never installs Claude Code itself, never writes outside the chosen target, and never modifies files inside `claude_dist/` after clone.

---

## The harness/ tree

`harness/` mirrors the layout that lands in `~/.claude/`. Each subdirectory has a discrete job.

### harness/CLAUDE.md — the behavioral contract

A markdown file installed (optionally) at `~/.claude/CLAUDE.md`. Claude Code auto-loads this file at session start as global memory, so its content is binding for every conversation in every project. The contract codifies tone (terse, no filler, no emojis, deterministic language), scope discipline (no "while I'm here" cleanup, no flags or helpers the request did not name), reading discipline (read the applicable XML guideline before writing code in that language; read the entire target file before editing), hook compliance (hooks are policy, not obstacles — bypass attempts are violations), atomic-edit rules, shell-quoting rules, git/commit safety (no force-pushes, no `git add -A`, never commit `.env`), and a routing table mapping work domains to specialized subagents.

Skip `INSTALL_GLOBAL_CLAUDE_MD` and none of this lands. The rest of the harness still works without it; the contract is opt-in.

### harness/settings.json — Claude Code configuration

The deployed `~/.claude/settings.json`. Sets the model strategy (`CLAUDE_CODE_SUBAGENT_MODEL=opus`, `effortLevel=high`), output and timeout budgets (`CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000`, `BASH_DEFAULT_TIMEOUT_MS=300000`, `BASH_MAX_TIMEOUT_MS=600000`, `MCP_TOOL_TIMEOUT=120000`), permission defaults, the MCP-server enable list, the LSP plugin enable list, and the full hook chain. The hook chain is what gives the harness its teeth: at every lifecycle event Claude Code fires shell scripts under `enforcement/`, and the rules they enforce are documented below.

A handful of `__HARNESS_ENABLE_*__` placeholders in this file resolve to `1` or `0` at deploy time so downstream hooks introspect their own configuration without re-parsing `.env`. When `INSTALL_LM_STUDIO=0`, the deployer additionally strips `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, and `LM_STUDIO_URL` from the merged settings file rather than leaving stale placeholders behind.

### harness/.mcp.json — MCP server registry

The deployed `~/.claude/.mcp.json`. Defines twenty-one MCP servers across two tiers. The eight **local** servers run on the same machine as Claude Code: three custom Node.js servers shipped under `mcp-servers/` (`guidelines-retriever`, `project-memory`, `system-info`), four `npx`-bootstrapped reference servers (`filesystem-local`, `sequential-thinking`, `memory-local`, `everything-local`), and one `uvx`-bootstrapped tree-sitter server. The thirteen **remote** servers are stdio MCP processes living on a dedicated Linux host; the deployer rewrites their command lines to `sshpass -p "${LSP_PASS}" ssh ${LSP_USER}@${LSP_IP} '...'` so Claude Code launches them transparently over an SSH stdin/stdout pipe. Remote servers cover filesystem, memory, fetch, git, sqlite, sequential-thinking, everything, brave-search, github, puppeteer, postgres, gitea, and context7.

When `INSTALL_REMOTE_MCP=0`, the deployer prunes every `remote-*` entry from both `.mcp.json` and `settings.json.enabledMcpjsonServers`. There is no half-state. Either you provide an SSH host and the thirteen remote servers come online, or the deployed configuration does not mention them. After merge, `.mcp.json` is `chmod 600` because it contains your SSH password and any API tokens you supplied.

### harness/agents/

Twenty-eight subagent definitions, one markdown file per agent. Claude Code's `Task` tool routes work to these by name: `python-forge`, `csharp-forge`, `rust-forge`, `java-forge`, `maven-forge`, `gradle-forge`, `react-forge`, `react-typescript-forge`, `frontend-developer`, `yew-forge`, `bashforge-script-generator`, `bash-script-enforcer`, `code-reviewer`, `architecture-advisor`, `security-auditor`, `database-architect`, `performance-optimizer`, `api-designer`, `test-engineer`, `devops-engineer`, `documentation-writer`, `deployment-guardian`, `plan-agent`, `tree-structure-documenter`, `utilities-agent`, `dev-tracker`, `neurotic-code-quality`, and `ignition-master`. Each markdown file is the subagent's system prompt. The deployer copies the directory verbatim; no templating happens inside agent files.

### harness/commands/

Slash-command skill definitions. These extend the user-invocable command surface so that typing `/scope`, `/scope-reminder`, `/consult`, `/scrub`, `/scrub_mongodb`, `/superwork`, `/full-stack-crew`, `/frontend-crew`, `/rust-crew`, `/bash-crew`, `/check-project`, `/enforce-automation`, `/enhance-guidelines`, or `/gsl` runs the bundled skill instead of asking Claude to improvise. Each command is a single markdown file; behavior lives in the file content. Like agents, commands copy verbatim.

### harness/skills/

Ships skills that are not slash commands. The directory currently contains `verify-frontend-ux/`, the skill that gates frontend work behind real browser-driven UX verification — no curl, no unit tests, no snapshot tests count as evidence of "done". Claude Code auto-discovers skills from `~/.claude/skills/`.

### harness/enforcement/ — the policy layer

`enforcement/` is the tree of shell scripts referenced from the hook chain in `settings.json`, plus the data those scripts consult.

`enforcement/rules/enforce-rules.sh` reads `enforcement_rules.json` (a structured catalogue of forbidden patterns and the contexts in which they apply) and rejects tool calls that violate them. The catalogue covers the rules listed in `CLAUDE.md`'s "Hard rules" section: no `/dev/null`, no `/tmp` or any temp-named directory, no inline `python -c`/`node -e`/`bash -c`, no truncating piped output through `head`/`tail`, no reading from `__pycache__`/`node_modules`/`dist`/`build`, no unquoted shell variables, no `2>&1 | tee` patterns. The hook treats reword-to-bypass attempts as the same violation as the original.

`enforcement/guidelines/` holds two things. First, `guideline_documents/` — the language-and-domain guidelines themselves, in three parallel forms: authoritative XML under `xml/`, mirrored markdown under `markdown/`, and mirrored GSL (Generalized Syntax Language) under `gsl/`. The XML copies are what hooks parse; the markdown and GSL versions exist for human reading and tool interoperability. Coverage spans Python, Bash, PowerShell, C#, Rust, Java 17, Maven, Gradle, Swift, SQL, Snowflake, frontend, Angular (current and AngularJS), React (Node 16 and the modern TypeScript/Node stack), Vue/Nuxt, Yew, API design, Docker, Kubernetes, Bicep, LXC, Azure, CosmosDB, Kafka, RabbitMQ, Redis, storage/messaging principles, Datadog observability, PowerQuery, CI/CD, auth, email authentication, NGINX, Netlify, session recording, Stripe, WordPress, WooCommerce, Apache Wicket, Ignition v8.1 and v8.3, domain infrastructure, Zenfolio integration, and the `.utilities/` automation principles. The catalogue `prohibited_behavior.xml` encodes the absolute zero-tolerance rules. `WRITING_STYLE.md` lives at the root of `guideline_documents/` as the canonical voice spec for prose output.

Second, the scripts that consume those documents: `enforce-guidelines.sh` runs at every `PreToolUse` and verifies the active language guideline has been read this session, `force-prohibited-read.sh` runs at every `UserPromptSubmit` and refuses to let Claude proceed without ingesting `prohibited_behavior.xml` first, and `session-start-guidelines.sh` injects a guideline-availability banner into the session.

`enforcement/lifecycle/` holds the rest of the hook chain: `session-start-cleanup.sh`, `history-per-project.sh` (partitions `~/.claude/history.jsonl` into per-project buckets at session start), `enforcement-cache.sh`, `session-tracker.sh`, `inject-global-feedback.sh` (pulls the global feedback library into the current project's `memory/` directory), `sweep-stale-artifacts.sh`, `detect-compaction.sh`, `clear-extensionless-tracking.sh`, `enforce-ssh-sshpass.sh` (rejects raw `ssh user@host` calls that omit `sshpass` and credentialed env vars), `enforce-file-extension.sh`, `enforce-agent-routing.sh` (forces `Task` calls to use the right specialized subagent for the language they target), and `stop-verify-quality.sh` — the LM Studio quality reviewer that runs at the end of each turn when `INSTALL_LM_STUDIO=1`.

`enforcement/cleanup/` holds the periodic janitorial scripts: `quarter-hourly-memory-sync.sh` regenerates each project's `MEMORY.md` index from frontmatter every fifteen minutes, `hourly-cleanup.sh` and `hourly-history-partition.sh` drain `~/.claude/backups/` to `~/.claude/_OLD/` and partition stray history every hour, `daily-bak-sweep.sh` relocates dotted backup files at 02:30 local, `daily-age-sweep.sh` ages out `paste-cache`, `shell-snapshots`, `telemetry`, `plans`, `file-history`, `session-env`, and `tasks` directories at 03:00 local, and `merge-dotted-projects.sh` reconciles project-key collisions caused by the `'/'`/`'_'`/`'.'` collapse rule.

`enforcement/launchd/` holds the macOS LaunchAgent plists that drive the cleanup scripts on a schedule, plus `install.sh` that loads them into `~/Library/LaunchAgents/`. The plists are templated as `com.__USER_NAME__.claude-cleanup-*.plist` in the source tree; at deploy time the script renames each plist to `com.${USER}.claude-cleanup-*.plist` so the agent labels match the running user.

`enforcement/shared/utils/` holds reusable bash helpers sourced by every hook: `project-key.sh` (the canonical project-key collapse function — never reimplemented, always sourced), `colors.sh`, `logging.sh`, `paths.sh`, `filesystem.sh`, `input.sh`, `checks.sh`, `block-policy.sh`, `discipline-claude.sh`, `lm_studio.sh`, `transcript.sh`, `security.sh`, `banner.sh`, `main.sh`. Hooks source these for color rendering, project-key resolution, transcript parsing, LM Studio API calls, and policy block messaging.

`enforcement/prohibited/` carries additional prohibited-behavior tracking that the hook chain consults at `PreToolUse` time.

### harness/mcp-servers/

Source for the four custom local MCP servers. `guidelines-retriever/` exposes the XML guideline corpus to Claude as searchable MCP resources. `project-memory/` reads and writes the per-project memory index at `~/.claude/projects/<key>/memory/`. `system-info/` exposes structured system facts (OS, shell, paths, available tools). `remote-shell/` exposes the SSH-tunneled remote shell for the LSP host. Each is a Node.js project with its own `package.json`; the deployer runs `npm install --silent --no-fund --no-audit` inside each one after copying the tree.

### harness/plugins/

The LSP plugin tree. `marketplaces/local-lsp/plugins/` holds eight language-server plugins (`pyright-lsp`, `typescript-lsp`, `rust-analyzer-lsp`, `clangd-lsp`, `swift-lsp`, `bash-lsp`, `csharp-lsp`, `java-lsp`); `settings.json` enables all eight via `enabledPlugins` and registers the marketplace via `extraKnownMarketplaces.local-lsp.source.path`. The LSP servers themselves are not bundled — the plugins call binaries that have to be installed separately. `scripts/install-lsp-binaries.sh` is the bootstrapper for that, and `scripts/setup-mcp-lsp.sh` is the higher-level setup script the deployer optionally runs against an Ubuntu remote host.

### harness/scripts/

Standalone scripts that are not part of the hook chain: `install-lsp-binaries.sh`, `setup-mcp-lsp.sh`, and `utilities/` containing `launch_claude_debug.sh`, `test_enforcement.sh`, and `test_mcp_remote.sh` for verifying the harness end-to-end after a deploy.

---

## What deploy_harness.sh does, top to bottom

`deploy_harness.sh` is roughly six hundred lines of bash, `set -Eeuo pipefail` from the top. It supports four flags: `--target=DIR` overrides the deploy target (default `~/.claude`); `--dry-run` prints every action without executing any of them; `--non-interactive` forbids interactive prompts and either uses values from the magi pack-root `.env` or fails fast; `--skip-prereqs` bypasses the prerequisite probe.

Phase one is **environment loading and feature-flag resolution.** When the magi pack-root `.env` exists, the script sources it with `set -a` so every variable exports. Each `INSTALL_*` flag resolves through `resolve_flag`: a value set in the pack-root `.env` wins for direct deployer runs; `gc magi install` gives inherited environment values precedence before invoking the deployer. In non-interactive mode the documented default applies (`INSTALL_GLOBAL_CLAUDE_MD=1`, `INSTALL_REMOTE_MCP=0`, `INSTALL_LAUNCHD=1` on macOS only, `INSTALL_LM_STUDIO=0`, `INSTALL_LSP_BINARIES=0`); in interactive mode the user is prompted with the default in brackets. Each secret value resolves the same way through `resolve_value`, with sensitive values (passwords, API tokens) read silently.

Phase two is **prerequisite detection.** The script probes for `jq`, `rsync`, `node`, and `npx`. When `INSTALL_REMOTE_MCP=1` it additionally requires `sshpass` and `ssh`. Missing required tools trigger a yes/no offer to install them via the platform package manager (`brew` on macOS; `apt-get`, `dnf`, or `pacman` on Linux). On Linux, `INSTALL_LAUNCHD` forces to `0` because launchd is macOS-only.

Phase three is **substitution preparation.** The script computes `sed`-escaped forms of every value that lands in the tree (the deploy target path itself, `${HOME}`, `${USER}`, the LM Studio host/port/URL, the remote LSP IP/user/password/home, every API token, every external host). The placeholders these replace are: `__CLAUDE_HOME__`, `__USER_HOME__`, `__USER_NAME__`, `__HARNESS_ENABLE_REMOTE_MCP__`, `__HARNESS_ENABLE_LAUNCHD__`, `__HARNESS_ENABLE_GLOBAL_CLAUDE_MD__`, `__HARNESS_ENABLE_LM_STUDIO__`, `__LM_STUDIO_HOST__`, `__LM_STUDIO_PORT__`, `__LM_STUDIO_URL__`, `__LSP_IP__`, `__LSP_USER__`, `__LSP_PASS__`, `__LSP_REMOTE_HOME__`, `__BRAVE_API_KEY__`, `__GITHUB_PERSONAL_ACCESS_TOKEN__`, `__MY_GITEA_API_TOKEN__`, `__MY_GITEA_HOST__`, and `__MY_GITEA_PORT__`. Substitution restricts to file extensions where templating is safe: `.sh`, `.json`, `.plist`, `.md`, `.xml`, `.gsl`, `.py`, `.js`. Binary files and unknown extensions stay untouched.

Phase four is **backup.** Before anything is overwritten, the entire deploy target `cp -a`'s to a sibling directory named `<target>_backup-YYMMDD-HHMMSS`. Each individual file the deployer is about to merge or overwrite (`settings.json`, `.mcp.json`, and `CLAUDE.md` when applicable) also gets an independent snapshot at `<file>.pre-harness-YYYYMMDD-HHMMSS.bak` next to the original. Both forms of backup co-exist; you can roll back from either. When a backup path already exists (re-running the deployer twice in the same second), the folder backup is skipped with a warning rather than overwriting an existing snapshot.

Phase five is **tree copying.** Seven subtrees `rsync` from `harness/` into the deploy target, with `--exclude='.DS_Store'`: `agents/`, `commands/`, `skills/`, `enforcement/`, `mcp-servers/`, `plugins/`, and `scripts/`. `rsync -a` preserves permissions and modification times; existing files in the target tree overwrite in place. After all seven copies complete, the substitution sed program builds once and applies to every text file under the deploy target via `find ... -print0 | xargs -0 sed -i`. The deployer detects whether `sed -i` requires a backup-suffix argument (BSD `sed` on macOS) and falls back to `sed -i''` form when the first invocation fails — this is what makes the same script portable across macOS and Linux.

Phase six is **MCP node-dep installation.** For every `mcp-servers/*/package.json` in the deployed tree, the script `cd`s into that directory and runs `npm install --silent --no-fund --no-audit`. Failures emit a warning but do not abort the deploy.

Phase seven is **settings.json deep-merge.** The harness's templated `settings.json` copies to a staging file, sed-substitutes, then conditionally prunes: when `INSTALL_LM_STUDIO=0` the LM Studio environment keys strip out, when `INSTALL_REMOTE_MCP=0` the `remote-*` entries strip from `enabledMcpjsonServers`. The staged file then merges with whatever `settings.json` already exists in the deploy target via a recursive `jq` program (the `JQ_DEEP_MERGE` block in the script): nested objects merge key-by-key, arrays concatenate and de-duplicate stably, and on scalar conflicts the incoming value wins. The merged result writes atomically — `jq` writes to `<target>.merging`, then `mv -f` replaces the live file.

Phase eight is **.mcp.json deep-merge** — same procedure as `settings.json`, except that when `INSTALL_REMOTE_MCP=0` the entire `remote-*` server family filters out of `mcpServers` before merging, and the merged file `chmod 600`s afterwards because it now contains your SSH password and API tokens. When the chmod fails (some filesystems do not support it), the deployer warns rather than aborting.

Phase nine is **CLAUDE.md installation.** When `INSTALL_GLOBAL_CLAUDE_MD=1`, the harness's `CLAUDE.md` copies to `<target>/CLAUDE.md`. Any pre-existing `CLAUDE.md` was already snapshotted in phase four.

Phase ten is **launchd installation.** When `INSTALL_LAUNCHD=1` and the host is macOS, every `com.__USER_NAME__.claude-cleanup-*.plist` under `enforcement/launchd/` renames to `com.${USER}.claude-cleanup-*.plist`, and `enforcement/launchd/install.sh` executes to `launchctl unload`/`launchctl load` the agents into `~/Library/LaunchAgents/`. The five recurring jobs documented in `CLAUDE.md` (every-15-min memory sync; hourly backup drain and history partition; daily 02:30 bak relocation; daily 03:00 age-out sweep; the history-per-project hourly job) come online here.

Phase eleven is **optional LSP binary setup.** When `INSTALL_LSP_BINARIES=1`, the deployer executes `<target>/scripts/setup-mcp-lsp.sh`, which provisions the language-server binaries on the remote LSP host (or the local machine, depending on how that script is configured for your environment). This phase is opt-in because it takes several minutes and pulls down hundreds of megabytes of language-server payload.

Throughout, every action obeys `--dry-run`. In dry-run mode the script logs each action it would take but never modifies the filesystem. Run that first.

---

## Getting started: bootstrap from the pack-root .env

Edit `gascity-packs/magi/.env`. The file is intentionally minimal for secrets; blank secret values mean `deploy_harness.sh` prompts interactively for anything needed. Filling values in the file converts the deploy from a Q&A session into an unattended run. The file is consumed by every magi deployer; it is not installed verbatim into the deployed tree.

The first block is **feature flags.** Set each to `1` to install, `0` to skip, or leave blank to be prompted. Defaults applied in non-interactive mode are documented in the example file.

```dotenv
INSTALL_GLOBAL_CLAUDE_MD=1   # install the behavioral contract at ~/.claude/CLAUDE.md
INSTALL_REMOTE_MCP=0         # configure the 13 SSH-tunneled remote MCP servers
INSTALL_LAUNCHD=1            # install macOS launchd cleanup agents (ignored on Linux)
INSTALL_LM_STUDIO=0          # enable Stop-hook quality review against LM Studio
INSTALL_LSP_BINARIES=0       # run scripts/setup-mcp-lsp.sh after the deploy
```

`INSTALL_GLOBAL_CLAUDE_MD=1` is the recommended default — without the contract, none of the tone, scope, or hook-compliance rules are binding on Claude in fresh sessions. `INSTALL_REMOTE_MCP=0` is the recommended default for first-time installs because the remote tier requires SSH credentials to a real Linux host that you have already provisioned with the language-server and MCP binaries (see `harness/scripts/setup-mcp-lsp.sh`). `INSTALL_LAUNCHD=1` is recommended on macOS so the cleanup agents come online; on Linux this flag silently forces to `0`. `INSTALL_LM_STUDIO=0` is correct unless you actually run LM Studio locally — when enabled, every `Stop` event fires `enforcement/lifecycle/stop-verify-quality.sh`, which calls the LM Studio HTTP API to grade the turn. `INSTALL_LSP_BINARIES=0` is correct unless you have prepared the remote host and explicitly want to install the language-server payloads as part of this deploy.

The second block is the **remote LSP / MCP host.** The deployer reads these only when `INSTALL_REMOTE_MCP=1`.

```dotenv
LSP_IP=192.0.2.10            # IP or hostname of the SSH-accessible Linux box
LSP_USER=<your-user>         # remote username
LSP_PASS=<your-password>     # remote password (consumed by sshpass)
LSP_REMOTE_HOME=             # leave blank for /home/${LSP_USER}; override if non-standard
```

`LSP_PASS` is the most security-sensitive value in the entire deploy. It sed-substitutes into every `remote-*` entry in `.mcp.json`, so the deployed file contains your literal password in plaintext. That is exactly why the deployer immediately `chmod 600`s the merged `.mcp.json`. Treat the deployed `~/.claude/.mcp.json` as a credential file — back it up with the same care. Prefer an SSH key? Replace the `sshpass -p "${LSP_PASS}" ssh ...` invocations in `harness/.mcp.json` with `ssh -i /path/to/key ...` before running the deployer; the substitution model accommodates any command-line shape.

The third block is **LM Studio**, read only when `INSTALL_LM_STUDIO=1`. These point at any OpenAI-compatible local model server.

```dotenv
LM_STUDIO_HOST=localhost
LM_STUDIO_PORT=1234
LM_STUDIO_URL=http://localhost:1234/v1/responses
```

`LM_STUDIO_URL` is what `stop-verify-quality.sh` POSTs to. The default targets a stock LM Studio install with the OpenAI-compatible server enabled. Change the host or port and change the URL to match — the deployer does not derive it for you when both fields are explicitly set.

The fourth block is **API tokens**, read only when the corresponding remote MCP server is enabled. Leave any of them blank to disable just that specific remote server while letting the other twelve come online.

```dotenv
BRAVE_API_KEY=                       # remote-brave-search
GITHUB_PERSONAL_ACCESS_TOKEN=        # remote-github
MY_GITEA_API_TOKEN=                  # remote-gitea
MY_GITEA_HOST=                       # gitea hostname (no scheme)
MY_GITEA_PORT=3000                   # gitea port
```

Once `.env` is populated to your satisfaction, the canonical first run is:

```
cd claude_dist
./deploy_harness.sh --dry-run
```

Read the dry-run output. Confirm the deploy target, the resolved feature flags, the substitution count, and the list of files that would be backed up. When satisfied:

```
./deploy_harness.sh
```

For unattended re-runs (CI, multi-machine fleet, etc.) add `--non-interactive` and ensure every value the deploy actually needs is set in `.env`. The deployer is fully idempotent — re-running it deep-merges into the existing tree, snapshots a fresh backup, and never duplicates entries in arrays because `JQ_DEEP_MERGE` de-dupes stably.

---

## What lands where, after a deploy

Default `--target=~/.claude`:

```
~/.claude/
├── CLAUDE.md                                     # if INSTALL_GLOBAL_CLAUDE_MD=1
├── settings.json                                 # deep-merged
├── .mcp.json                                     # deep-merged, mode 0600
├── agents/                                       # 28 subagents
├── commands/                                     # 13 slash commands
├── skills/verify-frontend-ux/                    # browser-driven UX skill
├── enforcement/
│   ├── rules/{enforce-rules.sh, enforcement_rules.json}
│   ├── guidelines/{enforce-guidelines.sh, force-prohibited-read.sh,
│   │               session-start-guidelines.sh, guideline_documents/{xml,gsl,markdown}/}
│   ├── lifecycle/{detect-compaction.sh, enforce-agent-routing.sh, enforce-file-extension.sh,
│   │              enforce-ssh-sshpass.sh, enforcement-cache.sh, history-per-project.sh,
│   │              inject-global-feedback.sh, session-start-cleanup.sh, session-tracker.sh,
│   │              stop-verify-quality.sh, sweep-stale-artifacts.sh,
│   │              clear-extensionless-tracking.sh}
│   ├── cleanup/{quarter-hourly-memory-sync.sh, hourly-cleanup.sh, hourly-history-partition.sh,
│   │            daily-bak-sweep.sh, daily-age-sweep.sh, merge-dotted-projects.sh}
│   ├── launchd/{com.${USER}.claude-cleanup-*.plist, install.sh}    # macOS only
│   ├── prohibited/                                                 # tracking dir
│   └── shared/utils/                                               # sourced helpers
├── mcp-servers/{guidelines-retriever, project-memory, system-info, remote-shell}/
├── plugins/marketplaces/local-lsp/plugins/{pyright-lsp, typescript-lsp, rust-analyzer-lsp,
│                                            clangd-lsp, swift-lsp, bash-lsp,
│                                            csharp-lsp, java-lsp}/
└── scripts/{install-lsp-binaries.sh, setup-mcp-lsp.sh, utilities/}
```

Pre-existing per-project state under `~/.claude/projects/<key>/` is never touched. Pre-existing `CLAUDE.md`, `settings.json`, and `.mcp.json` are merged or backed up, never deleted.

---

## Idempotency, re-runs, and selective updates

Every phase of the deployer is safe to repeat. `rsync` is the file-copy primitive, so unchanged files are no-ops; changed files overwrite in place. The deep-merge is symmetric across re-runs because it concatenates arrays and de-dupes — running the deploy twice does not double-register hooks or MCP servers. Every run snapshots a fresh `<target>_backup-YYMMDD-HHMMSS` next to the deploy target and a fresh `*.pre-harness-*.bak` next to each merged file, accumulating a timeline of every deploy.

Selective updates work the same way: edit `harness/agents/foo.md`, run `deploy_harness.sh`, and only that one file rewrites in place under `~/.claude/agents/foo.md`. Add a new subagent, run the deployer, the new file appears in `~/.claude/agents/`. Remove a subagent from `harness/agents/`, however, and `rsync -a` (without `--delete`) leaves the old file in place — this is intentional, so hand-authored additions in `~/.claude/agents/` are not silently destroyed. To force deletion, remove the file manually under the deploy target, or fork the deployer to pass `--delete` inside `copy_tree`.

The launchd phase is also idempotent: `enforcement/launchd/install.sh` unloads any existing `com.${USER}.claude-cleanup-*` agents before reloading them, so re-running the deploy refreshes the schedule without leaving stale ghosts in `launchctl list`.

---

## Rolling back (if you decide you hate it)

Every deploy snapshots two parallel kinds of backup: a folder-level snapshot of the entire deploy target, and per-file snapshots of every file that was about to be merged or overwritten. Roll back from either.

The simplest rollback is **restore from the folder snapshot.** After a deploy you have something like `~/.claude_backup-260505-114512` next to the live `~/.claude/`. Both are full directory trees with permissions preserved, so restore by unloading the launchd agents, deleting the live tree, and renaming the backup back into place:

```
launchctl unload ~/Library/LaunchAgents/com.${USER}.claude-cleanup-*.plist
rm -rf ~/.claude
mv ~/.claude_backup-260505-114512 ~/.claude
```

The second form is **per-file rollback,** appropriate when you want to keep new agents/commands/skills the harness installed but revert a single configuration file. Each file's pre-harness backup sits next to it as `<file>.pre-harness-YYYYMMDD-HHMMSS.bak`. Restore by copying back:

```
cp ~/.claude/settings.json.pre-harness-20260505-114512.bak ~/.claude/settings.json
cp ~/.claude/.mcp.json.pre-harness-20260505-114512.bak ~/.claude/.mcp.json
cp ~/.claude/CLAUDE.md.pre-harness-20260505-114512.bak ~/.claude/CLAUDE.md
```

The third form is a **clean uninstall.** Walk away entirely:

```
launchctl unload ~/Library/LaunchAgents/com.${USER}.claude-cleanup-*.plist
rm -f  ~/Library/LaunchAgents/com.${USER}.claude-cleanup-*.plist
rm -rf ~/.claude
```

This destroys per-project memory under `~/.claude/projects/`, which the harness did not install but does drive. To preserve project memory across an uninstall, copy `~/.claude/projects/` aside before removing `~/.claude`, and copy it back afterwards.

A fourth form is the **dry-run reverse**: before destroying anything, run `./deploy_harness.sh --dry-run --target=/some/scratch/dir` to see exactly what a fresh deploy would put down, and use that as a reference for what to undo. The dry-run output names every file the script touches; the inverse of that list is your rollback plan.

---

## Troubleshooting

**The deployer aborts on the prereq check.** Install the missing tool, or re-run with `--skip-prereqs` when the tool is already available under a name the probe did not try. `jq`, `rsync`, and `node` are non-negotiable; `sshpass` and `ssh` are non-negotiable only when `INSTALL_REMOTE_MCP=1`.

**Hooks fire but block everything.** The hook chain fails closed by design — when `enforce-rules.sh` or `enforce-guidelines.sh` cannot satisfy a precondition, it blocks the tool call rather than letting it through. First-run failure modes are usually (a) the active language guideline has not been read, fixed by running the corresponding `Read` against `~/.claude/enforcement/guidelines/guideline_documents/xml/<lang>.xml`, or (b) `prohibited_behavior.xml` has not been ingested in this session, fixed automatically by `force-prohibited-read.sh` at the next `UserPromptSubmit`. Bypassing a hook by reshaping the command (substituting `/var/folders` for `/tmp`, splitting `2>&1` into separate redirects, wrapping in `bash -c`) is the same violation — the hook fires again. The fix is to honor the underlying rule.

**Remote MCP servers fail to connect.** Verify `LSP_IP`, `LSP_USER`, and `LSP_PASS` resolve correctly by running `sshpass -p "${LSP_PASS}" ssh -o ConnectTimeout=10 "${LSP_USER}@${LSP_IP}" 'echo ok'` directly. When the SSH itself works but the MCP server does not start, the language-server payload is missing at `${LSP_REMOTE_HOME}/.local/bin/`; run `harness/scripts/setup-mcp-lsp.sh` against that host. The `~/.claude/projects/<key>/enforcement.log` and `~/.claude/projects/<key>/security.log` files capture per-project hook output and are the right place to look first.

**Launchd agents do not appear to fire.** Check `launchctl list | grep com.${USER}.claude-cleanup` and inspect `~/.claude/_logs/cleanup/`. Re-running `bash ~/.claude/enforcement/launchd/install.sh` unloads and reloads every agent.

**npm install fails inside `mcp-servers/*/`.** Non-fatal — the deployer warns and continues. The affected MCP server does not start until the dependency issue resolves and `npm install` reruns inside its directory. Common causes are missing `node` versions (the harness assumes Node 18+) and offline package-registry access.

**The deploy completed but `~/.claude/` looks wrong.** Run `./deploy_harness.sh --dry-run` against the same `.env` and compare against the live tree. The dry-run output is the authoritative description of what a clean deploy produces.

---

## Author

magi pack maintainers. The harness reflects an opinionated set of choices about how Claude Code behaves under direction: terse output, hard rules with no soft-fail, reproducible cross-machine deploys, idempotent re-runs, full backup of every overwrite, and a deterministic rollback path. Pull it apart, modify what you do not like, and re-run the deployer — every part of `harness/` is plain text and every action `deploy_harness.sh` takes is grep-able in the script itself.
