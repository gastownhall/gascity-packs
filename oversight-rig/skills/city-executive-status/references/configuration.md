# Configuration

## Data flow

```text
scheduled request
  -> one model-authored Markdown input per owner
  -> structural validation
  -> deterministic portfolio brief in the vault
  -> optional content-hash-deduplicated publisher
```

The input files are the semantic boundary. The requester supplies the exact
schema; the aggregator never infers health or rewrites project meaning.

## Environment variables

| Variable | Used by | Default | Purpose |
| --- | --- | --- | --- |
| `EXECUTIVE_STATUS_INPUT_DIR` | both | `executive-status/inputs` | Owner input directory |
| `EXECUTIVE_STATUS_AGENTS_DIR` | requester | unset | Discover `*-pl/agent.toml` owners |
| `EXECUTIVE_STATUS_DISPATCH_COMMAND` | requester | unset | Shell-free command template containing `{agent}` and `{message}`; `{subject}` is optional |
| `EXECUTIVE_STATUS_SUBJECT` | requester | `DIRECTIVE: EXECUTIVE_STATUS` | Dispatch subject |
| `EXECUTIVE_STATUS_DISPATCH_TIMEOUT` | requester | `30` | Per-owner command timeout in seconds |
| `EXECUTIVE_STATUS_OUTPUT` | sync | `executive-status/Executive Brief.md` | Aggregate Markdown path, normally inside the vault |
| `EXECUTIVE_STATUS_TITLE` | sync | `Executive Status Brief` | Brief and publish-summary title |
| `EXECUTIVE_STATUS_EXPECTED_OWNERS` | sync | unset | Comma-separated owners used for coverage reporting |
| `EXECUTIVE_STATUS_STALE_HOURS` | sync | `48` | Age at which an input is shown as stale |
| `EXECUTIVE_STATUS_PUBLISH_COMMAND` | sync | unset | Shell-free command template requiring `{body_file}`; `{title}` is optional |
| `EXECUTIVE_STATUS_PUBLISH_TIMEOUT` | sync | `90` | Publisher timeout in seconds |
| `EXECUTIVE_STATUS_MAX_PUBLISH_LENGTH` | sync | `3500` | Maximum summary length |
| `EXECUTIVE_STATUS_SENTINEL` | sync | beside output | Last successfully published summary hash |
| `EXECUTIVE_STATUS_LOG` | sync | beside output | Append-only audit log |

Command templates are split with `shlex` and executed directly. Shell syntax,
pipes, redirects, substitutions, and environment expansion are intentionally not
evaluated. Use a small adapter executable when an integration needs them.

## Installation

1. Copy `assets/executive-status.env.example` outside the skill and set local
   paths and command adapters.
2. Create the configured input directory.
3. Create one input from `assets/status-input-template.md` per expected owner.
4. Run both scripts in dry-run mode.
5. Run the sync with `--no-publish` and inspect the generated Markdown in the
   vault.
6. Configure publishing only with explicit authorization for that destination.
7. Install the two scheduler examples, replace their placeholder script paths
   with the copied or provider-materialized skill directory, and adjust their
   cadence. Leave enough time between request and aggregation for agents to
   write their inputs.

## Input contract

Each input must have both fences and exactly these fields:

```text
project, owner, updated, health, current, next, risk
```

`owner` must match the filename. `updated` must be an ISO-8601 timestamp with a
timezone. Health is one of `on-track`, `at-risk`, `blocked`, or `parked`.
Project and owner are limited to 80 characters; current, next, and risk are
limited to 240 characters each.

Inputs must be regular Markdown files no larger than 64 KiB. Symbolic links are
rejected so an input directory cannot redirect the reader elsewhere. Raw HTML
characters are escaped before owner content enters the brief or publish summary.

Use `blocked` only when the project cannot make useful progress. Use `at-risk`
when progress continues but an outcome is threatened. Use `parked` for deliberate
inactivity. Keep internal work IDs, paths, branches, queue counts, and incident
mechanics out of the brief.

## Adapters

For a Gas City installation, a dispatch adapter can invoke `gc mail send` with
the `{agent}`, `{subject}`, and `{message}` arguments. A publishing adapter can
invoke any approved channel command that accepts a Markdown file path. Keep
platform-specific identifiers and credentials in the deployment environment,
not in this skill.
