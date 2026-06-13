---
name: plan
description: Develop compact requirements for a Gas City work item through an interactive, repo-aware interview.
---

# GC Plan

Use this skill to create or revise the requirements artifact for a planned unit
of work. This is a planning-only skill: inspect files as needed and write the
requirements document, but do not implement product/source changes.

## Workflow

1. Ask for an overview of what needs to be accomplished. Invite a wall of text.
2. Identify the target rig/root path, plan slug, and artifact root. Default to:
   `<rig-root>/.gc/plans/<plan-slug>/`.
3. After the overview, inspect the target codebase enough to avoid asking
   questions whose answers are discoverable from the repository.
4. Interview the user one question at a time:
   - Provide your recommended answer with each question.
   - Resolve dependent decisions before moving to downstream questions.
   - Stop when remaining uncertainty no longer materially affects requirements.
5. Write or overwrite `requirements.md`.
6. Ask the user to review. When the user explicitly approves, update
   `status: approved`. Otherwise leave `status: draft` or `status: questions`.

## Artifact

`requirements.md` must begin with YAML front matter:

```yaml
---
plan_slug: example-slug
phase: requirements
rig: backend
rig_root: /absolute/path/to/rig
artifact_root: /absolute/path/to/rig/.gc/plans
status: draft
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---
```

Use this body structure:

```markdown
# Requirements: <title>

## Problem Statement

## Solution

## User Stories

## Out Of Scope

## Other Notes
```

Each user story should include lightweight acceptance criteria, usually 2-5
bullets. Capture technical constraints discovered from the repo, but do not
make engineering design decisions here.
