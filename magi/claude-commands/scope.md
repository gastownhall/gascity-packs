---
description: Define project scope interactively (user)
allowed-tools: Read, Write, Bash, AskUserQuestion
---

# Project Scope Definition

You are now in scope definition mode for the current project.

## 1. Check for existing scope

!PROJECT_KEY=$(echo "$PWD" | sed 's|^/||' | tr '/' '-' | tr '_' '-')
!PROJECT_DIR="$HOME/.claude/projects/-${PROJECT_KEY}"
!SCOPE_FILE="${PROJECT_DIR}/scope.md"
!mkdir -p "$PROJECT_DIR"
!if [ -f "$SCOPE_FILE" ]; then \
    echo "════════════════════════════════════════════════════════════════════"; \
    echo "EXISTING SCOPE FOUND:"; \
    echo "════════════════════════════════════════════════════════════════════"; \
    cat "$SCOPE_FILE"; \
    echo ""; \
    echo "════════════════════════════════════════════════════════════════════"; \
else \
    echo "No existing scope found. Creating new scope definition."; \
fi

## 2. Interactive scope gathering

Use the AskUserQuestion tool to gather the following information from the user. Ask all questions in a single AskUserQuestion call with multiple questions:

1. **Project Overview**: What is this project? What problem does it solve?
2. **Key Objectives**: What are the main goals you want to accomplish?
3. **Tech Stack**: What technologies, frameworks, or languages are involved?
4. **Constraints**: Any limitations, requirements, or non-negotiables?

After gathering responses, create a comprehensive scope document.

## 3. Write scope file

After gathering all information, write the scope to the project's scope file at:
`${MAGI_PACK_DIR}/projects/-{PROJECT_KEY}/scope.md`

The scope file format:

```markdown
# Project Scope: {Project Name}
Generated: {timestamp}
Project Path: {PWD}

## Overview
{user's project overview}

## Objectives
{user's key objectives as bullet points}

## Technology Stack
{user's tech stack details}

## Constraints & Requirements
{user's constraints}

## Success Criteria
{derived from objectives - what does "done" look like}

---
*This scope file is enforced on conversation compaction/resume.*
*Run /scope-reminder to re-read this scope during a session.*
*Edit this file directly to update the scope.*
```

## 4. Confirm scope creation

After writing the scope file, confirm to the user that:
- The scope has been saved
- It will be enforced on conversation compaction
- They can run /scope-reminder to re-read it
- They can edit the file directly at the path shown
