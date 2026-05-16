# codex_dist

Author: magi pack maintainers

`codex_dist` is a self-contained distribution for installing a Codex enforcement
harness into a Codex home directory. The default target is
`${CODEX_HOME:-$HOME/.codex}`. The distribution copies hook scripts, rule files,
guideline documents, test fixtures, native execpolicy rules, and runtime
configuration into that target so Codex can enforce local operating rules during
future sessions.

The distribution directory is an installer source. After deployment, Codex reads
from the installed files under the target Codex home, not from this repository.
Changing files in an upstream distribution checkout does nothing
to an already installed harness until `deploy_harness.sh` is run again.

This is not a daemon, background service, package manager, or model provider. It
does not replace Codex. It gives Codex a configured hook bridge, a rule map, a
guideline corpus, and an optional LM Studio Stop-hook verifier.

## What This Installs

The installed harness affects Codex in three places.

First, it enables Codex hooks by ensuring the target `config.toml` contains:

```toml
[features]
codex_hooks = true
```

Second, it installs `hooks.json` entries that call the harness dispatcher for
Codex lifecycle events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`,
`PermissionRequest`, `PostToolUse`, and `Stop`.

Third, it installs native execpolicy rules into `rules/default.rules`. These
rules block specific command prefixes before they reach the normal approval
path. The bundled rule file forbids inline ephemeral runtimes such as
`python -c`, `python3 -c`, `node -e`, `ruby -e`, and `perl -e`; forbids ambient
`pip install` and `pip3 install`; and forbids `mktemp` so automation stays in
project-local scratch space.

The hook layer then enforces the richer JSON rules in
`enforcement/rules/enforcement_rules.json`. Those rules block risky commands,
forbid specific patch content, require guideline reads before edits in tracked
language domains, write local logs, and optionally run a final quality review
through LM Studio before Codex stops.

## Repository Layout

The top-level files are the operator interface.

`deploy_harness.sh` is the installer. It reads the magi pack-root `.env` when present, prompts for
missing values in interactive mode, writes runtime values into the target Codex
home, copies the harness tree, updates hook and rule configuration, creates
backups, and validates the installed JSON and Bash files.

The magi pack-root `.env` is the install-time configuration file for repeatable local installs. The installer uses those values only
while deploying. It then writes the runtime subset into
`~/.codex/enforcement/env` or the equivalent path under `--target`.

`README.md` is this document.

The `harness/` directory is the payload that gets installed.
`harness/hooks.json` is the Codex hook configuration template. It contains
`__CODEX_HOME__` placeholders that `deploy_harness.sh` substitutes with the
absolute deployment target before merging the entries into the target
`hooks.json`.

`harness/config/config.toml.snippet` is the minimal config used when the target
does not already have a `config.toml`. Existing config files are updated in
place, with backup, so `[features].codex_hooks` becomes `true`.

`harness/rules/codex-enforcement.rules` contains the native execpolicy block
that gets appended to `rules/default.rules` between
`# BEGIN CODEX_DIST ENFORCEMENT RULES` and
`# END CODEX_DIST ENFORCEMENT RULES`. Re-running the installer removes any old
marked block before appending the current one, so that section stays
idempotent.

`harness/enforcement/bin/codex-hook.sh` is the event dispatcher. Every installed
hook command calls this script with the event name as its first argument. The
script reads Codex hook JSON from stdin, resolves the session, current working
directory, tool name, command input, and transcript path, then runs the checks
that belong to that event.

`harness/enforcement/bin/common.sh` is shared runtime support. It resolves the
installed Codex home, state directory, log directory, rules file, guideline
paths, project-specific state paths, JSON extraction helpers, regex matching,
rule validation, guideline tracking, and language-to-guideline mapping.

`harness/enforcement/env.example` is the runtime environment template. The
installer writes a concrete `enforcement/env` file in the target from `.env`
values and interactive answers. Runtime hooks load this file without overriding
environment variables that are already set by the caller.

`harness/enforcement/rules/enforcement_rules.json` is the main policy document.
It currently contains 48 deny rules, 29 patch-content rules, 25 required
guideline enforcement mappings, 25 advisory guideline topics, and agent routing
metadata. The hook script reads this file at runtime and blocks if the JSON is
invalid.

`harness/enforcement/guidelines/guideline_documents/` is the bundled guideline
corpus. It contains XML, Markdown, and GSL versions of the guideline material,
plus `WRITING_STYLE.md`. The hook enforcement path uses the XML directory for
language-specific read gates and `WRITING_STYLE.md` for writing-style tracking.

`harness/enforcement/tests/run-fixtures.sh` is the installed smoke test suite.
It exercises representative blocks, guideline tracking, patch-content blocking,
Stop-hook skip behavior, and Stop-hook behavior when LM Studio is unreachable.

`harness/enforcement/tests/fixtures/stop-transcript.jsonl` is the transcript
fixture used by the Stop-hook test path.

## Complete File Inventory

The distribution contains no hidden application code beyond the files described
in this section. Operational behavior comes from `deploy_harness.sh`, the hook
templates, the installed shell scripts, the JSON rule map, the execpolicy rule
block, the runtime environment templates, and the fixture test. The remaining
files are guideline documents shipped as policy source material.

At the target directory root, `deploy_harness.sh` is the installer and `README.md` is the operator manual.
The install-time configuration lives at `gascity-packs/magi/.env` so all magi targets share one pack-local configuration surface.

Under `harness/`, `hooks.json` defines every Codex hook entry the installer
merges into the target. The file is not copied verbatim. The installer replaces
`__CODEX_HOME__` with the resolved target path so each hook command points at
the installed dispatcher.

Under `harness/config/`, `config.toml.snippet` is the minimal config created
only when the target has no `config.toml`. It exists to enable
`[features].codex_hooks = true` without inventing any other Codex settings.

Under `harness/rules/`, `codex-enforcement.rules` is the native execpolicy
payload. It complements hook enforcement by blocking command prefixes before
approval. It is inserted into the target `rules/default.rules` inside marked
begin and end comments.

Under `harness/enforcement/bin/`, `codex-hook.sh` is the installed event
dispatcher and `common.sh` is the installed shared library. `codex-hook.sh`
owns event-specific behavior. `common.sh` owns environment loading, project
state resolution, JSON helper functions, regex matching, guideline tracking,
rules-file validation, and path-to-language mapping.

Under `harness/enforcement/`, `env.example` is the runtime configuration
template. The installer does not require users to copy it manually because it
generates a concrete `enforcement/env` file during deployment.

Under `harness/enforcement/rules/`, `enforcement_rules.json` is policy data for
the hook layer. It is read on every hook invocation that needs policy. Invalid
JSON blocks hook execution because continuing with a broken rule file would make
enforcement unpredictable.

Under `harness/enforcement/tests/`, `run-fixtures.sh` is the smoke test runner.
Under `harness/enforcement/tests/fixtures/`, `stop-transcript.jsonl` is a small
Codex transcript used to test Stop-hook behavior without needing a live Codex
session.

Under `harness/enforcement/guidelines/guideline_documents/`,
`WRITING_STYLE.md` is the writing-style policy document. The `xml/`,
`markdown/`, and `gsl/` subdirectories contain guideline documents in different
representations. The installed hook uses XML paths for enforced guideline reads.
The Markdown and GSL files are still shipped intentionally because they preserve
the same policy corpus for human reading and downstream tooling.

The XML guideline files are the enforcement-facing documents. Their filenames
define the domains Codex can be told to read before editing or operating in that
area: Angular, AngularJS, Apache Wicket, API design, authentication, automation,
Azure variables, Bash, Bicep, CI/CD, Cosmos DB, C#, Datadog observability,
Docker, domain infrastructure, email authentication, frontend work, Gradle,
Ignition 8.1, Ignition 8.3, Java 17, Kafka, Kubernetes, LXC, Maven, Netlify,
Nginx, Power Query, PowerShell, prohibited behavior, Python, RabbitMQ,
React/Node 16, Redis, Rust, session recording, Snowflake, SQL,
storage-and-messaging, Stripe, Swift, TypeScript/React/Node, utilities,
Vue/Nuxt, Wicket, WooCommerce, WordPress, Yew, and Zenfolio integration.

The Markdown guideline files mirror that corpus for readable documentation and
include the Ignition module docs as Markdown-specific reference files. The GSL
guideline files provide the same policy material in GSL form for tools that
consume that representation. These files do not execute. They affect runtime
only when a hook rule maps a filename to a tracking key and requires Codex to
read that document before a patch.

## Install-Time Versus Runtime Configuration

There are two environment files with different jobs.

The repo-level `.env` is read by `deploy_harness.sh`. It answers installer
questions. It can choose the target Codex home, choose which features are
installed, and set the LM Studio values that get written into the installed
runtime environment.

The installed `enforcement/env` is read by the hook scripts during Codex
sessions. It controls whether the Stop quality verifier runs, how many Stop
attempts are allowed, how much transcript content is sent to the verifier, and
which LM Studio endpoint and model receive the review request.

Edit `gascity-packs/magi/.env` for local secrets or host-specific state. Do not add target-local `.env` files.

## Quick Start

From the magi pack root:

```bash
gc magi install --target codex
```

The interactive installer asks whether to install Codex hooks, native execpolicy
rules, and the LM Studio Stop verifier. It then asks for LM Studio host, port,
model, timeouts, Stop attempt limit, and transcript character limit. Blank
answers use defaults.

For a non-interactive install with all three feature groups enabled:

```bash
INSTALL_CODEX_HOOKS=1 \
INSTALL_EXEC_POLICY=1 \
INSTALL_LM_STUDIO=1 \
LM_STUDIO_HOST=localhost \
LM_STUDIO_PORT=1234 \
LM_STUDIO_MODEL=nvidia/nemotron-3-super \
./deploy_harness.sh --non-interactive
```

For a dry run:

```bash
./deploy_harness.sh --dry-run
```

For a test install that does not touch the real `~/.codex`:

```bash
./deploy_harness.sh --target=/tmp/codex-harness-test
```

After installing into the real Codex home, restart Codex. Hook configuration is
loaded by Codex itself, so an already running Codex process will not necessarily
pick up new hook settings.

## Configuring `.env`

Edit `gascity-packs/magi/.env`. The template contains:

```bash
CODEX_HOME=
INSTALL_CODEX_HOOKS=
INSTALL_EXEC_POLICY=
INSTALL_LM_STUDIO=

LM_STUDIO_HOST=localhost
LM_STUDIO_PORT=1234
LM_STUDIO_MODEL=nvidia/nemotron-3-super
LM_STUDIO_CONNECT_TIMEOUT=3
LM_STUDIO_MAX_TIME=75
CODEX_MAX_QUALITY_ATTEMPTS=3
CODEX_TURN_CONTENT_LIMIT=70000
```

`CODEX_HOME` selects the deployment target when `--target=DIR` is not supplied.
Blank means `${CODEX_HOME:-$HOME/.codex}` at installer startup. Use this when
you want a persistent default target in `.env`; use `--target` when you want a
one-off override.

`INSTALL_CODEX_HOOKS` controls whether `hooks.json` entries are installed.
`1` installs them. `0` skips them. Blank means the installer prompts unless
`--non-interactive` is used; in non-interactive mode the default is `1`.

`INSTALL_EXEC_POLICY` controls whether the native rules block is installed into
`rules/default.rules`. `1` installs it. `0` skips it. Blank follows the same
prompting and non-interactive default behavior as `INSTALL_CODEX_HOOKS`.

`INSTALL_LM_STUDIO` controls the Stop-hook quality verifier. `1` writes
`CODEX_SKIP_QUALITY_CHECK=0` into the installed runtime environment. `0` writes
`CODEX_SKIP_QUALITY_CHECK=1`. The hook entries can still be installed while the
quality verifier is skipped; in that state the Stop hook returns a continue
decision without contacting LM Studio.

`LM_STUDIO_HOST` and `LM_STUDIO_PORT` point to an OpenAI-compatible LM Studio
server. The hook posts to `http://HOST:PORT/v1/responses`.

`LM_STUDIO_MODEL` is the model string sent in the request payload.

`LM_STUDIO_CONNECT_TIMEOUT` is the curl connection timeout in seconds.

`LM_STUDIO_MAX_TIME` is the maximum total curl request time in seconds.

`CODEX_MAX_QUALITY_ATTEMPTS` prevents infinite Stop-hook recursion. The Stop
hook stores attempt state per Codex session and approves after the limit is
exceeded so a broken verifier cannot trap a session forever.

`CODEX_TURN_CONTENT_LIMIT` limits how many characters of extracted turn context
are sent to LM Studio. The hook extracts the current user request, assistant
messages, tool calls, tool results, command results, and affected file contents
before applying this limit.

## `deploy_harness.sh` Behavior

`deploy_harness.sh` is an idempotent installer. Its job is to make the target
Codex home contain the current harness payload while preserving recoverable
backups of files and directories it changes.

The script starts with strict Bash mode, resolves its own directory through
`BASH_SOURCE[0]`, sets `HARNESS_DIR` to `SCRIPT_DIR/harness`, sets `ENV_FILE` to
the magi pack-root `.env`, and creates a timestamp used in backup names. The default
deployment target is `${CODEX_HOME:-${HOME}/.codex}` unless `--target=DIR`
overrides it.

Supported arguments are:

`--target=DIR` installs into `DIR` instead of the default Codex home.

`--dry-run` prints the file operations it would perform and skips installed-file
validation because no installed files are written.

`--non-interactive` never prompts. Blank feature flags resolve to their defaults,
which are currently `1` for Codex hooks, execpolicy, and LM Studio. Blank runtime
values resolve to the built-in defaults shown in the pack-root `.env`.

`--skip-prereqs` skips the prerequisite command check. Use it only when the
environment is known-good and the check itself is inappropriate for the target.
The install still needs the underlying tools when their phases run.

`-h` and `--help` print the script header usage text and exit.

The installer rejects unknown arguments and exits with an error.

The deployment flow is fixed.

It loads `.env` if present. The script uses `set -a` while sourcing the file so
keys become environment variables for the rest of the installer run. This makes
`.env` a shell-sourced file, not a generic dotenv parser. Keep values as simple
shell assignments.

It resolves feature flags. Existing environment values win, including values
loaded from `.env`. If a flag is blank and the run is interactive, the script
prompts. If a flag is blank and the run is non-interactive, the default is used.

It resolves runtime values for LM Studio, request timeouts, Stop attempt limit,
and turn content limit. Existing environment values win. Otherwise it prompts or
uses defaults.

It checks prerequisites unless `--skip-prereqs` is set. The required commands
are `jq`, `rsync`, `sed`, `awk`, `find`, and `chmod`. Missing commands fail the
install before files are modified.

It backs up the whole deployment target if that target already exists. The
backup lives next to the target and uses the pattern
`${base}_backup-YYMMDD-HHMMSS`. For the default target, that means a path like
`~/.codex_backup-260505-153000`. If that exact backup path already exists, the
script warns and skips the folder backup instead of overwriting it.

It creates the target directory when needed.

It copies `harness/enforcement/` into `${DEPLOY_TARGET}/enforcement/` with
`rsync -a --exclude=.DS_Store`. This updates the installed hook scripts, rules,
guidelines, tests, fixtures, and runtime template. On real runs, it makes
installed `bin/*.sh` and `tests/run-fixtures.sh` executable.

It writes `${DEPLOY_TARGET}/enforcement/env`. Existing env files are backed up
first as `.pre-codex-harness-YYYYMMDD-HHMMSS.bak`. The generated runtime env is
mode `600` when `chmod` succeeds.

It ensures `${DEPLOY_TARGET}/config.toml` enables hooks. If the file does not
exist, the script writes `harness/config/config.toml.snippet`. If it exists, the
script backs it up and rewrites only the `[features]` handling needed to set
`codex_hooks = true`. Existing sections are preserved.

If Codex hooks are enabled, it installs hook entries. The script substitutes
`__CODEX_HOME__` in `harness/hooks.json` with the absolute deployment target,
backs up an existing target `hooks.json`, and deep-merges the incoming hook
configuration into the existing file. Object values merge recursively. Array
values are appended and de-duplicated with stable ordering. Incoming scalar
values win when a key exists in both objects.

If execpolicy is enabled, it installs the native rule block. The script backs up
`rules/default.rules`, removes any previous block between the Codex distribution
markers, appends the current `harness/rules/codex-enforcement.rules`, and writes
the end marker. This prevents duplicate blocks across repeated installs.

Finally, on non-dry-run installs, it validates the installed `hooks.json` and
`enforcement_rules.json` with `jq empty`, then checks Bash syntax for
`common.sh`, `codex-hook.sh`, and `run-fixtures.sh` with `bash -n`.

## Installed Hook Lifecycle

The installed `hooks.json` wires Codex events to
`enforcement/bin/codex-hook.sh`. Each hook command passes the event name as the
first argument and sends the Codex hook payload on stdin.

`SessionStart` runs for `startup`, `resume`, and `clear` matchers. It logs the
session start and emits additional context telling Codex that enforcement is
active and that guideline files live under the installed guideline directory.

`UserPromptSubmit` runs on user prompts. It clears extensionless-file warning
state for the current session. It periodically emits a prohibited-behavior
reminder. It also detects prompt text related to compaction or resume, clears
tracked guideline reads, and tells Codex to re-read relevant guidelines before
editing. This keeps guideline tracking from surviving context resets that would
make the model forget what it read.

`PreToolUse` is the main enforcement event. It records guideline reads issued
through Bash-like tools, evaluates deny rules against commands and patch file
paths, blocks extensionless file creation through `apply_patch`, requires
language guideline reads before edits for known file types, checks patch content
rules, warns about SSH/SCP commands that do not use `sshpass`, and logs the tool
attempt.

`PermissionRequest` delegates to the same checks as `PreToolUse`. This prevents
an escalation request from bypassing rules that would have blocked the tool use.

`PostToolUse` logs tool completion. It does not make policy decisions.

`Stop` performs optional quality verification. When enabled, it locates the
current Codex transcript, extracts the current turn, appends affected file
contents for files changed through `apply_patch`, sends the context to LM
Studio, and blocks or approves the stop based on the verifier response. A
response starting with `BLOCK`, `FAIL`, `FAILED`, or `REJECT` blocks. Other
responses approve. If the verifier is disabled by environment variable, the Stop
hook returns `continue: true` with output suppressed.

Unknown event names are blocked.

## Runtime State and Logs

The hook runtime defaults to `${CODEX_HOME:-$HOME/.codex}` unless environment
variables override it. The important installed paths are:

`~/.codex/enforcement/env` for runtime configuration.

`~/.codex/enforcement/rules/enforcement_rules.json` for hook policy.

`~/.codex/enforcement/guidelines/guideline_documents/xml` for enforced XML
guidelines.

`~/.codex/enforcement/state` for session and project state.

`~/.codex/enforcement/logs` for global log directory creation. Project-specific
logs are placed under `state/projects`.

For each Codex working directory, the hook creates a project key by stripping
the leading slash and replacing `/`, `_`, and `.` with `-`. It then writes state
under:

```text
~/.codex/enforcement/state/projects/-PROJECT-KEY/
```

Inside that project directory, `tracking/` stores guideline-read markers and
Stop quality attempt counters. `scratch/` is reserved for hook scratch space.
`enforcement.log` records lifecycle events and guideline tracking. `security.log`
records deny-rule and content-rule hits. `quality-verification.log` records Stop
verifier attempts and failures.

Runtime env loading is conservative. `common.sh` reads `enforcement/env`, skips
blank and comment lines, accepts only shell-safe variable names, and exports a
value only if that variable is not already set in the process environment.
Explicit environment variables supplied to a hook invocation therefore override
the installed env file.

## Rule Enforcement

The rule system has several layers.

Native execpolicy rules block command prefixes before normal unsandboxed
approval can be granted. These rules are intentionally narrow and live in
`rules/default.rules`.

JSON deny rules live in `enforcement_rules.json` under `deny`. They match either
tool command text or patch file paths. The current distribution includes deny
rules for ambient system Python and pip usage, inline runtime execution,
discrete Docker commands, discrete npm commands, discrete Azure resource
commands, direct Python quality-tool invocations, heredocs, `/tmp` and macOS
`/var/folders` scratch usage, junk directories, background `&` runs,
`/dev/null` suppression, truncation or inline tee patterns, protected
`pyproject.toml` edits, backend `requirements.txt` creation, and Rust build
script creation.

Patch-content rules live under `content_rules`. They inspect the patch body for
known forbidden content and either block or warn based on each rule action. The
current rules cover Python `Any`, `type: ignore`, relative imports, `src`
imports, Pydantic v1 syntax, unused-parameter underscore hiding, inline Python
comments, TODO comments, empty lines in Bash, trailing comma patterns, and a
large set of Rust risk patterns such as unsafe code, ABI/linker manipulation,
nightly features, panic patterns, debug macros, lint suppression, build output
overrides, and runtime blocking in async contexts.

Guideline enforcement rules live under `guideline_enforcements`. For known file
types, `codex-hook.sh` maps patch paths to a tracking key. If that key has not
been recorded for the current session, the hook blocks the patch and tells Codex
which guideline file to read. The current direct path mapping in `common.sh`
covers Python, Bash, C#, Rust, Java/Maven, frontend files, PowerShell, Swift,
SQL, Bicep, Vue/Nuxt, Power Query, WordPress/PHP, Dockerfiles, and YAML. The
rule file also contains path-specific enforcement entries for domains such as
Angular, API, auth, Kubernetes, Netlify, Nginx, WooCommerce, Yew, and writing
style.

Guideline reads are tracked when a Bash-like tool command references a guideline
file path under a `guidelines` or `guideline_documents` directory with an
`.xml`, `.md`, or `.gsl` extension. The hook resolves the filename through
`enforcement_rules.json` and records the corresponding tracking key. Tracking
expires after one hour in the hook implementation.

Advisory guideline topics and agent routing metadata are also stored in
`enforcement_rules.json`. The current hook script does not enforce all advisory
or routing metadata as hard blocks. The metadata documents intended routing and
topic associations for future or external enforcement layers.

## LM Studio Stop Quality Review

The Stop verifier is controlled by `CODEX_SKIP_QUALITY_CHECK`. A value of `1`
skips verification. A value of `0` enables verification.

When enabled, the Stop hook first increments a per-session attempt counter. If
the count exceeds `CODEX_MAX_QUALITY_ATTEMPTS`, it clears the counter and
approves the stop to avoid an infinite loop. Attempt state older than five
minutes is ignored.

The hook then finds a transcript. It prefers an explicit `transcript_path` or
`transcriptPath` from the hook payload. If no explicit file exists, it searches
`${CODEX_HOME}/sessions` for `rollout-*.jsonl` files matching the current
session id. If that fails, it uses the latest rollout file it can find.

The context sent to LM Studio is not the raw full transcript. The hook extracts
the current turn starting at the latest user message. It includes user requests,
assistant responses, assistant updates, tool calls, tool results, and command
results. It then appends contents for files affected by `apply_patch`, up to 20
files and 500 lines per file. The total extracted context is limited by
`CODEX_TURN_CONTENT_LIMIT`.

The request is sent to:

```text
http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1/responses
```

The request payload uses the configured `LM_STUDIO_MODEL`, temperature `0.1`,
`max_tokens` `1800`, and `stream: false`. The verifier prompt asks for exactly
one leading decision token: `PASS:` or `BLOCK:`.

If LM Studio returns a review, the hook blocks when the review begins with a
blocking token and approves otherwise. If the request fails, the first failure
blocks. After repeated verifier failures, the hook approves with a reason so a
dead local model server does not permanently trap Codex.

This verifier is a quality gate, not a security boundary. It is useful for
catching incomplete work, false claims, ignored errors, missing tests, and
unsafe command patterns at the end of a turn. Hard command and patch policy
still belongs in execpolicy and JSON rules.

## Verification

After installing into the real Codex home, run:

```bash
~/.codex/enforcement/tests/run-fixtures.sh
```

For a custom target, run the test from that target:

```bash
/path/to/target/enforcement/tests/run-fixtures.sh
```

The fixture script is written for the installed default home path:
`${HOME}/.codex/enforcement`. If you install into a custom target, inspect the
script before assuming it fully validates that target. The installer itself
still validates installed JSON and Bash syntax for any target.

The fixture suite currently checks:

`python -c` is blocked during `PreToolUse`.

A Bash command that reads `bash_guidelines.xml` records a guideline read.

A Bash command that reads `python_guidelines.xml` records a Python guideline
read.

An `apply_patch` operation that creates an extensionless file is blocked.

An `apply_patch` operation that introduces Python `Any` is blocked after the
Python guideline read has been tracked.

`Stop` returns `continue: true` when `CODEX_SKIP_QUALITY_CHECK=1`.

`Stop` blocks on the first attempt when LM Studio is unreachable.

For installer-only validation without touching the real Codex home, use:

```bash
./deploy_harness.sh --target=/tmp/codex-harness-test --non-interactive
```

Then inspect `/tmp/codex-harness-test/config.toml`,
`/tmp/codex-harness-test/hooks.json`,
`/tmp/codex-harness-test/rules/default.rules`, and
`/tmp/codex-harness-test/enforcement/env`.

## Reinstalling and Updating

Re-running `deploy_harness.sh` is the update path. The installer overwrites the
installed `enforcement/` tree with the current bundled payload, rewrites the
runtime env from current installer inputs, ensures hooks are enabled, merges
hook entries, and refreshes the marked execpolicy block.

Reinstalling is designed to be safe, but it is not a no-op. It creates backups
for the target directory and each existing file it modifies directly. It also
rewrites the runtime env file from current values, so local manual edits in the
installed `enforcement/env` should be copied back into `.env` before
reinstalling if they must persist.

Because `hooks.json` is deep-merged, existing unrelated hook configuration is
preserved. Because arrays are appended and de-duplicated, the Codex distribution
entries should not multiply across installs unless they differ structurally.

Because `rules/default.rules` uses explicit begin and end markers, the installer
can replace its own block without touching unrelated user rules outside that
block.

## Rollback

The installer gives you two rollback levels: targeted rollback and full target
restore.

If a user hates the installation and wants the fastest clean exit, stop Codex,
restore the most recent full target backup, and restart Codex:

```bash
mv ~/.codex ~/.codex_after-codex-dist
mv ~/.codex_backup-YYMMDD-HHMMSS ~/.codex
```

That restores the entire Codex home to the state captured before the installer
ran. Use the timestamped backup created by the install being rolled back. Keep
the moved-aside `~/.codex_after-codex-dist` directory until the restored Codex
home has been checked.

Use targeted rollback when you only want to remove the harness behavior while
keeping unrelated Codex configuration changes made after installation. This is
the least destructive path.

First, disable Codex hooks in `config.toml` or remove the hook feature line if it
was created only for this harness:

```toml
[features]
codex_hooks = false
```

Second, remove the Codex distribution hook entries from `hooks.json`. The entries
are the commands that call:

```text
~/.codex/enforcement/bin/codex-hook.sh
```

If the only hooks in the file are from this distribution, remove `hooks.json` or
restore its backup. If other hooks exist, remove only the events and command
objects added by this harness.

Third, remove the marked block from `rules/default.rules`. Delete everything
from:

```text
# BEGIN CODEX_DIST ENFORCEMENT RULES
```

through:

```text
# END CODEX_DIST ENFORCEMENT RULES
```

Fourth, remove the installed enforcement tree if you no longer want the files:

```bash
rm -rf ~/.codex/enforcement
```

Then restart Codex.

Use backup-based rollback when you want to restore the exact pre-install files.
The installer creates file backups with names like:

```text
config.toml.pre-codex-harness-YYYYMMDD-HHMMSS.bak
hooks.json.pre-codex-harness-YYYYMMDD-HHMMSS.bak
default.rules.pre-codex-harness-YYYYMMDD-HHMMSS.bak
env.pre-codex-harness-YYYYMMDD-HHMMSS.bak
```

Restore the backup you want over the active file. For example:

```bash
cp ~/.codex/config.toml.pre-codex-harness-YYYYMMDD-HHMMSS.bak ~/.codex/config.toml
cp ~/.codex/hooks.json.pre-codex-harness-YYYYMMDD-HHMMSS.bak ~/.codex/hooks.json
cp ~/.codex/rules/default.rules.pre-codex-harness-YYYYMMDD-HHMMSS.bak ~/.codex/rules/default.rules
cp ~/.codex/enforcement/env.pre-codex-harness-YYYYMMDD-HHMMSS.bak ~/.codex/enforcement/env
```

Use full target restore when the user wants the whole Codex home back to its
previous state. Before each real install, the script copies the whole existing
target next to itself with a name like:

```text
~/.codex_backup-YYMMDD-HHMMSS
```

To restore that snapshot, stop Codex, move the current target aside, and move
the backup into place:

```bash
mv ~/.codex ~/.codex_after-codex-dist
mv ~/.codex_backup-YYMMDD-HHMMSS ~/.codex
```

Restart Codex after any rollback. Codex needs to reload `config.toml` and
`hooks.json` before behavior changes are fully visible.

## Failure Modes

If installation fails during prerequisite checks, install the missing command or
rerun in an environment that already has it. The required commands are `jq`,
`rsync`, `sed`, `awk`, `find`, and `chmod`.

If installation fails during JSON validation, inspect the installed
`hooks.json` and `enforcement/rules/enforcement_rules.json`. The installer uses
`jq empty` on both files. Invalid JSON blocks completion because a malformed
hook config or rules file would make enforcement unreliable.

If installation fails during Bash syntax validation, inspect
`enforcement/bin/common.sh`, `enforcement/bin/codex-hook.sh`, and
`enforcement/tests/run-fixtures.sh` in the target. The installer runs `bash -n`
on those files.

If Codex does not appear to run hooks after install, verify that
`config.toml` has `[features].codex_hooks = true`, verify that `hooks.json`
contains commands pointing at the target `enforcement/bin/codex-hook.sh`, and
restart Codex.

If Stop verification blocks because LM Studio is unreachable, either start LM
Studio with an OpenAI-compatible `/v1/responses` endpoint at the configured host
and port, or disable the verifier by setting `CODEX_SKIP_QUALITY_CHECK=1` in
the installed `enforcement/env`. Reinstalling with `INSTALL_LM_STUDIO=0` also
writes the skip value.

If a patch is blocked for missing guideline reads, read the guideline file named
in the block message through a Bash command or another tracked read path, then
retry the patch. Guideline tracking is per session and expires.

If a command is blocked by a deny rule, change the workflow. The intended
pattern is to use project-local, reviewed scripts and project package managers
instead of one-off shell fragments, inline runtimes, ambient installs, or temp
directory shortcuts.

## Security and Operational Boundaries

This harness enforces local policy for Codex tool use. It is not a sandbox
replacement. It does not prevent a user from manually editing files outside
Codex. It does not secure LM Studio. It does not authenticate the local verifier
endpoint. It does not guarantee that every unsafe command pattern is blocked.

The hard guarantees are narrower and more useful: configured Codex hook events
run the dispatcher; the dispatcher validates the rule file before use; deny
rules and content rules can block matching operations; guideline reads can be
required before tracked edits; Stop verification can force Codex to continue
work when the local reviewer rejects the final response; and backups exist for
installer-touched targets and files.

Treat `enforcement_rules.json` as policy code. Validate it after edits. Treat
guidelines as source material for model behavior, not executable controls.
Treat LM Studio review as a final quality check, not the first line of defense.

## Expected Daily Use

Most users should install once, restart Codex, and leave the distribution
directory alone. Normal use happens through Codex. The harness will inject
session context, remind Codex about prohibited behavior when appropriate, block
known-bad command and patch patterns, require guideline reads before sensitive
edits, write logs under the installed state directory, and optionally review the
turn before Codex stops.

When the policy changes, update the distribution payload and rerun
`deploy_harness.sh`. When LM Studio settings change, update `.env` and rerun the
installer, or edit the installed `enforcement/env` directly for a local runtime
override. When behavior is unwanted, use targeted rollback or restore the target
backup.

The clean mental model is simple: this repository ships the harness; the target
Codex home runs the harness; backups let you leave.
