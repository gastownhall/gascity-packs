---
name: lazyjj-taskcraft
description: Design LazyJJ-aligned tasks and bead shapes for new work.
category: development
allowed-tools: Bash
---

# LazyJJ Taskcraft

Use this skill when you need to author work that is already aligned to the
LazyJJ system. It is the task-bead skill for the pack.

## Covers

- task decomposition for LazyJJ-native work
- bead shapes that fit stack-based implementation
- examples of reviewable, claimable work items

## Workflow

1. Start with the stack and the workspace, not with a giant feature blob.
2. Split work into bead-sized pieces that can be claimed independently.
3. Include verification, dependencies, and a clear stack order.
4. Keep the task title short and the description precise.
5. Provide example beads when teaching the pattern to another agent.

## Suggested Bead Shape

```yaml
title: "Update LazyJJ tutorial skills"
type: task
priority: 2
description: |
  Split the LazyJJ pack guidance into tutorial-specific skills and update
  the pack docs so the learning path matches the runtime workflow.
acceptance_criteria:
  - Tutorial skills exist for the major LazyJJ learning paths.
  - Pack docs link to the correct skill for each topic.
  - Each skill has commands or references that match the tutorial content.
dependencies: []
files:
  - gastown-lazyjj/skills/
  - gastown-lazyjj/README.md
verification:
  - rg -n "spr" gastown-lazyjj returns no stale references
```

## Example Beads

```yaml
title: "Foundation skill for LazyJJ onboarding"
type: task
priority: 3
description: |
  Teach installation, quickstart, and the first stack so a new user can get
  from zero to a reviewable change quickly.
acceptance_criteria:
  - The skill explains install and quickstart steps.
  - The skill shows bookmark-based PR publishing.
  - The skill hands the user off to stack workflow guidance.
dependencies: []
files:
  - gastown-lazyjj/skills/lazyjj-foundations/SKILL.md
verification:
  - Manual review of the commands in the skill
```

```yaml
title: "LazyJJ tasksmith agent"
type: task
priority: 2
description: |
  Add an agent that authors LazyJJ-aligned task beads with example bead
  shapes and stack-aware dependencies.
acceptance_criteria:
  - The agent prompt describes task decomposition rules.
  - Example beads are included in the agent materials.
  - The agent references the tutorial skills instead of inventing workflow.
dependencies: []
files:
  - gastown-lazyjj/agents/tasksmith/
verification:
  - The agent config loads and the prompt references the pack skills
```
