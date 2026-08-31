# Make it yours

poteto-mode is one person's style. The machinery underneath, playbooks, routing, model roles, works just as well wearing yours. This page covers generating a personal mode, capturing lessons from a session, authoring a focused skill, and testing a skill change before you trust it.

## Generate your own mode with `/automate-me`

```text
/automate-me
```

You don't describe your style, because [`/automate-me`](../../skills/automate-me/SKILL.md) reads it out of your history. It mines your recent transcripts in the active workspace for repeated preferences, in how you like replies, delegation, verification, code, prose, and process, then asks you which patterns are really you. It drafts a mode skill under this host's skill dir through Grok Build's `/create-skill`, runs the draft through [`/unslop`](../../skills/unslop/SKILL.md), and opens a PR from a worktree so you review it like any other change.

Run it again whenever your habits drift:

```text
/automate-me update my mode skill with everything since its last edit
```

Update mode mines only the history since the skill last changed. It keeps rules you haven't contradicted, revises the ones with new evidence, and adds sections only for genuinely new patterns.

## Capture a session's lessons with `/reflect`

Right after a task that taught you something, run:

```text
/reflect that took way too long. capture what we learned so the next run doesn't repeat it.
```

[`/reflect`](../../skills/reflect/SKILL.md) sends the transcript to three parallel reviewers, then a synthesizer sorts the proposals into `Accepted`, `Rejected`, and `Backlog` and waits for your approval before any skill changes. Approve a proposal only if it would change a future decision. One weird session is an anecdote, not a rule.

## Author a focused skill

When you already know the workflow you want to capture:

```text
/poteto-mode write a skill for verifying database migrations in this repo
```

Writing a skill matches the [Authoring or modifying a skill playbook](../../skills/poteto-mode/playbooks/authoring-a-skill.md), which routes through Grok Build's `/create-skill`, validates the frontmatter and links, and ships the result through the Opening a PR playbook. Agent-facing prose has a higher bar than human prose, because an unhelpful sentence becomes an instruction some future agent follows. Let the playbook hold that bar rather than writing a `SKILL.md` freehand.

One special case has its own generator. A skill that must drive your app and prove behavior is a verification skill, so use [`/create-verification-skill`](../../skills/create-verification-skill/SKILL.md) and [`/maintain-verification-skill`](../../skills/maintain-verification-skill/SKILL.md) instead. [Verify and ship](./06-verify-and-ship.md#create-a-project-verification-skill) covers both.

## Write docs to a standard with `/technical-writing`

Skills aren't the only prose you ship. For docs, RFCs, readmes, PR descriptions, and commit messages:

```text
/technical-writing review the readme changes
```

[`/technical-writing`](../../skills/technical-writing/SKILL.md) applies a layered standard with one goal, prose a tired engineer understands on the first read. It picks the document's mode first (tutorial, how-to, reference, or explanation), then works sentence by sentence: who does what, one thought per sentence, nothing readable two ways. Use it to review what you or an agent just wrote, or name it up front when you ask for a doc.

## Test a skill change blind

A skill edit affects every future session, so test it like the experiment it is:

```text
/poteto-mode run the eval playbook on this skill change. same task for both variants, candidates stay blind.
```

The [Eval playbook](../../skills/poteto-mode/playbooks/eval.md) is built around one failure mode, the observer effect. An agent that knows it's being evaluated behaves differently. So candidate agents get an organic-looking task in sanitized directories, never the words "eval" or "candidate", and never each other's existence. One judge scores all outputs under neutral labels, and chain-following gets graded from which files each candidate actually read, not from what it claims.

Read every output yourself before accepting the verdict. If you disagree with the judge, suspect the rubric before you suspect your judgment.

**Pitfall:** don't edit a skill mid-task because it's misbehaving. Fix it in its own PR and keep the task moving. A skill edit that ships tangled into feature work is invisible to review and impossible to evaluate.

## Keep Cursor pstack in sync

Playbooks and principles come from [official Cursor `pstack/`](https://github.com/cursor/plugins/tree/main/pstack). This tree recomposes those **atomic building blocks** on Grok Build natives in [`HARNESS.md`](../../HARNESS.md) (`spawn_subagent`, `get_command_or_subagent_output`, `scheduler_create`, `monitor`). The pin is [`UPSTREAM`](../../UPSTREAM). This repo stays a single plugin. The Grok catalog is [tommy-ca/grok-build-plugins](https://github.com/tommy-ca/grok-build-plugins), an index, not a `cursor/plugins` sibling tree. Porting the core to another host is [Port pstack](./12-porting.md).

When Cursor moves:

```bash
python3 scripts/sync-from-upstream.py --log
python3 scripts/sync-from-upstream.py --recipe
```

Then copy intent (`skills/`, `agents/`). Skip `make-bot-ui`. Do not overwrite `HARNESS.md`, `plugin.json`, README files, `tests/`, or `scripts/`. Run `python3 scripts/adapt-harness.py`. Hand-map depth-1 spawn (`pstack:<role>`) and persist-then-wake overnight (`/loop` → `scheduler_create`). Do not leave Cursor `Task`, same-run `/loop`, `~/.cursor/rules/*.mdc`, or `control-cli` as live Grok calls. Run `python3 scripts/verify-harness.py` and `python3 tests/test_verify_harness.py`. Update the `tree` line in [`UPSTREAM`](../../UPSTREAM).

Next: [Recipes and pitfalls](./10-recipes-and-pitfalls.md).
