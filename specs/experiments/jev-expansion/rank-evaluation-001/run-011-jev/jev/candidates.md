# Duplicate investigation order

No duplicate verdict is supplied. Investigate candidates before applying the existing triage policy.

## Source issue
Deleting a project leaves orphan tasks
Deleting a project must delete its tasks, but task rows remain with a missing project.

## Candidate 1: C1
Project deletion leaves task rows
Task rows survive deleting their parent project and refer to a missing parent.

## Candidate 2: C2
Cannot create a task
A foreign-key check rejects creation with a nonexistent project.

## Candidate 3: C3
Project icon
Allow a custom project icon.
