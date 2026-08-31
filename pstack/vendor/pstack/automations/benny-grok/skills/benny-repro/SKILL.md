---
name: benny-repro
description: "Reproduce a trusted Benny marker through the real UI and open a draft PR only after proof. Use for /benny-repro or a report permalink."
disable-model-invocation: true
---

# Live grok repro

This skill is the live coordinator. It loads with `grok plugin enable pstack`. `automations/benny/skills/` is the **upstream reference** for marker names and atomic intent. Do not use it as the runbook.

## Input

The Slack permalink is the user argument (or `args.thread_url` on the optional workflow). Freeze source channel and root message id from that URL. Load `.grok/benny/configuration.yaml` if present. Stop if the config is missing.

## Run

Parent session only. `MAX_SUBAGENT_DEPTH` is 1.

1. Read the frozen thread. Proceed only for a trusted `[benny:bug]` or `[benny:performance]` from the configured triage identity. Stop for `[benny:other]`, a missing verdict, or an untrusted author.
2. Stop if a person already owns the fix. If an existing PR or commit may fix it, verify through the real UI twice. Do not author a competing diff.
3. Reproduce the discriminating symptom twice through the real UI. A unit test or injected state is not a repro. For code, `spawn_subagent` with `subagent_type` `pstack:feature`. For a second check, `pstack:independent-verifier`. Do not send `reasoning_effort`. Children get no Slack write tools.
4. Open a draft pull request only after before-and-after UI proof. Never merge or deploy. Plugin `hooks` stay off. Optional `automations/benny-grok/bin/fail-closed.sh` denies `gh pr merge` only if the operator installs that project hook.
5. Overnight waits use `/loop` → `scheduler_create`.

The parent is the only Slack poster. Never post a source-channel root message.
