---
description: Re-read and align with project scope (user)
allowed-tools: Read, Bash
---

# Scope Reminder

Re-read the project scope file to realign with the original project objectives.

## 1. Locate and read scope file

!PROJECT_KEY=$(echo "$PWD" | sed 's|^/||' | tr '/' '-' | tr '_' '-')
!PROJECT_DIR="$HOME/.claude/projects/-${PROJECT_KEY}"
!SCOPE_FILE="${PROJECT_DIR}/scope.md"
!if [ -f "$SCOPE_FILE" ]; then \
    echo "════════════════════════════════════════════════════════════════════"; \
    echo "PROJECT SCOPE - REALIGNMENT"; \
    echo "════════════════════════════════════════════════════════════════════"; \
else \
    echo "No scope file found for this project."; \
    echo "Run /scope to create one."; \
    exit 0; \
fi

Read the scope file at the path shown above using the Read tool.

## 2. Acknowledge scope

After reading the scope file:

1. Summarize the key objectives from the scope
2. Confirm alignment with the stated goals
3. Identify any potential scope creep in recent work
4. Recommend next steps that align with the scope

Remember: The scope file is the source of truth for this project's objectives.
