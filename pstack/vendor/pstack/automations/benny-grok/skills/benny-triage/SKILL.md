---
name: benny-triage
description: "Triage one Slack issue report. One frozen-thread verdict with a Benny marker. Use for /benny-triage, Slack intake, or a report permalink."
disable-model-invocation: true
---

# Live grok triage

This skill is the live coordinator. It loads with `grok plugin enable pstack`. `automations/benny/skills/` is the **upstream reference** for marker names and atomic intent. Do not use it as the runbook.

## Input

The Slack permalink is the user argument (or `args.thread_url` on the optional workflow). Freeze source channel and root message id from that URL. Load `.grok/benny/configuration.yaml` if present. Stop with no posts and no tracker writes if the config is missing.

## Run

Parent session only. `MAX_SUBAGENT_DEPTH` is 1.

1. Read the frozen thread and attachments. For cause, `spawn_subagent` with `subagent_type` `pstack:how-explorer`. Do not send `reasoning_effort`. Children get no Slack write tools and no Slack tokens.
2. Classify. Search the configured tracker for duplicates. Create a ticket only for a clear net-new bug or performance issue.
3. The parent posts exactly one reply in the frozen thread. End with one marker: `[benny:bug]`, `[benny:performance]`, or `[benny:other]`. A bug or performance marker may include `tracker=<url>`. Never post a source-channel root message.
4. Overnight waits use `/loop`, which expands to `scheduler_create` (min 60s, new turn).
5. Merge deny is not a plugin hook. An optional script lives at `automations/benny-grok/bin/fail-closed.sh`. It does not freeze Slack coordinates.

Fail closed on a missing parent. One marker per run.
