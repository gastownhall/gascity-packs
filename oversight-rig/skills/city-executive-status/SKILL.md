---
name: city-executive-status
description: Maintain a concise, high-level portfolio brief from structured project-owner updates, with Obsidian-compatible Markdown output and optional deduplicated publishing. Use when setting up, sharing, operating, or troubleshooting an executive-status workflow for a multi-agent city or collection of projects.
---

# City Executive Status

Maintain one current portfolio brief without asking deterministic code to make
semantic judgments. Project owners describe outcomes and risks; bundled scripts
only request, validate, aggregate, write, and optionally publish those inputs.

## Preserve the boundary

- Let each project owner decide `health`, `current`, `next`, and `risk` from its
  real project context.
- Keep the scripts mechanical. Do not add keyword scoring, inferred health, or
  automatic rewriting of owner statements.
- Give every owner exactly one file named `<owner>.md`. Reject owner/filename
  mismatches and malformed inputs.
- Write the aggregate atomically. Preserve an existing brief when no valid
  inputs are available.
- Treat the vault as live production data. Preview paths and output before
  enabling scheduled writes.

## Install or share

Prefer importing the containing `oversight-rig` pack in a Gas City workspace.
The skill is inert until its configuration and example orders are copied into
that workspace. For a standalone installation, copy this entire
`city-executive-status/` directory into either a repository's `.claude/skills/`
directory or the recipient's Codex skills directory. Keep the scripts,
references, assets, tests, and `agents/openai.yaml` together.

Read [references/configuration.md](references/configuration.md) when installing,
changing paths, adding a publisher, or adapting the scheduler. Copy and edit the
bundled environment, input, and order examples rather than inventing new formats.

## Run the workflow

1. Configure paths and command templates from
   `assets/executive-status.env.example`.
2. Copy `assets/status-input-template.md` once per owner, naming each copy
   `<owner>.md` and setting its `owner` field to the same value.
3. Preview update requests:

   ```bash
   python3 scripts/request_status_updates.py \
     --agents-dir ./agents \
     --input-dir ./executive-status/inputs \
     --dry-run
   ```

4. Configure `EXECUTIVE_STATUS_DISPATCH_COMMAND`, then run the same command
   without `--dry-run`. The command template is parsed without a shell and must
   contain `{agent}` and `{message}`.
5. Preview the aggregate:

   ```bash
   python3 scripts/executive_status_sync.py --dry-run
   ```

6. Run with `--no-publish` to update only the Markdown brief. Configure
   `EXECUTIVE_STATUS_PUBLISH_COMMAND` only after the user explicitly authorizes
   the external destination. Publishing is content-hash deduplicated.
7. Stagger the request and aggregation schedules so owners have a composition
   window. Use the examples under `assets/orders/` as starting points.

## Interpret failures

- A malformed input is reported by filename and makes the sync exit nonzero;
  valid inputs are still visible with a coverage warning.
- Zero valid inputs makes the sync fail closed without replacing the existing
  brief.
- A failed dispatch or publish command propagates as an error. Do not mark its
  sentinel complete or hide it with a default value.
- Stale inputs remain visible as `Stale`; they are not silently dropped.

## Verify changes

Run all unit, integration, end-to-end, package-completeness, and scrub tests:

```bash
python3 -m unittest discover -s tests -v
```

Then validate the skill structure with the `skill-creator` validator.
