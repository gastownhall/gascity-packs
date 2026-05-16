---
description: Analyze conversations to improve guidelines (user)
allowed-tools: Bash, Read, Write, Glob, Grep, WebFetch
---

# Guideline Auto-Enhancement System

Analyze conversation history and enforcement logs to identify patterns that indicate gaps in guidelines.

## 1. Initialize analysis context

!PROJECT_KEY=$(echo "$PWD" | sed 's|^/||' | tr '/' '-' | tr '_' '-')
!PROJECT_DIR="$HOME/.claude/projects/-${PROJECT_KEY}"
!GUIDELINES_DIR="$HOME/.claude/guidelines"
!echo "Project: $PWD"
!echo "Guidelines directory: $GUIDELINES_DIR"
!ls -la "$GUIDELINES_DIR"/*.md 2>/dev/null | wc -l | xargs echo "Total guideline files:"

## 2. Gather correction patterns from conversations

Scan all project .jsonl files to find user correction patterns. Look for messages containing:
- "no, " / "not like" / "wrong" / "that's incorrect"
- "should be" / "instead of" / "actually"
- "fix this" / "this is wrong" / "error"
- "I said" / "I meant" / "correction"
- Repeated clarifications on the same topic

Use this Bash command to extract user messages with correction indicators:
```bash
find ${MAGI_PACK_DIR}/projects -name "*.jsonl" -type f -exec cat {} \; 2>/dev/null | \
  jq -r 'select(.type == "user" and .message.role == "user") | .message.content' 2>/dev/null | \
  grep -iE "(no,|not like|wrong|should be|instead of|actually|fix this|I meant|correction|that's not)" | \
  head -50
```

## 3. Analyze enforcement logs for violation patterns

Check enforcement logs for repeated violations that indicate guideline clarity issues:
```bash
find ${MAGI_PACK_DIR}/projects -name "*-enforcement.log" -type f -exec cat {} \; 2>/dev/null | \
  grep -E "(BLOCKED|WARNING|VIOLATION)" | \
  sort | uniq -c | sort -rn | head -20
```

Also check the main enforcement log:
```bash
cat ${MAGI_PACK_DIR}/enforcement.log 2>/dev/null | grep -E "(BLOCKED|WARNING)" | tail -30
```

## 4. Identify guideline gaps

For each pattern found:
1. Determine which guideline file is relevant
2. Check if the guideline addresses this specific case
3. Identify if the language is ambiguous or incomplete

Categories of gaps:
- **Missing rules**: Behavior not covered by any guideline
- **Ambiguous language**: Rules that can be interpreted multiple ways
- **Contradictions**: Rules that conflict with each other
- **Incomplete coverage**: Edge cases not addressed
- **Outdated content**: Rules that no longer apply

## 5. Generate improvement suggestions

For each identified gap, prepare a suggestion with:
- **Guideline file**: Which file needs updating
- **Current text**: The existing rule (if any)
- **Problem**: Why the current text is insufficient
- **Suggested change**: Specific text to add or modify
- **Evidence**: The conversation/log entry that revealed the gap

## 6. Consult LM Studio for analysis (optional)

First, verify LM Studio is reachable at `${LM_STUDIO_HOST}:${LM_STUDIO_PORT}`:
```bash
curl -s --connect-timeout 5 ${LM_STUDIO_URL%/v1/responses}/v1/models | head -c 100
```

If available, send the collected data for deeper analysis using curl:

```bash
curl -s -X POST "${LM_STUDIO_URL%/v1/responses}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistralai/magistral-small-2509",
    "messages": [
      {
        "role": "system",
        "content": "You are a guidelines improvement specialist. Analyze patterns of user corrections and enforcement violations to identify gaps in the guidelines. Provide specific, actionable improvements."
      },
      {
        "role": "user",
        "content": "<correction_patterns>\n{PATTERNS}\n</correction_patterns>\n\n<enforcement_violations>\n{VIOLATIONS}\n</enforcement_violations>\n\n<current_guidelines>\n{EXCERPTS}\n</current_guidelines>\n\nAnalyze these patterns and suggest:\n1. Specific guideline text additions\n2. Clarifications for ambiguous rules\n3. New rules that should be added\n4. Priority ranking of improvements"
      }
    ],
    "temperature": 0.3,
    "max_tokens": 4000,
    "stream": false
  }'
```

Replace `{PATTERNS}`, `{VIOLATIONS}`, and `{EXCERPTS}` with actual content.

## 7. Present findings and recommendations

Structure the output as:

### Immediate Fixes (High Priority)
Rules causing repeated violations that need clarification

### New Rules Needed
Behaviors not covered by existing guidelines

### Clarifications Required
Ambiguous language that led to misinterpretation

### Evidence Summary
Conversation excerpts and log entries supporting each recommendation

## 8. Apply improvements (with user confirmation)

For each approved improvement:
1. Read the target guideline file
2. Locate the section to modify
3. Apply the specific change
4. Log the enhancement

Log enhancement to:
```bash
!ENHANCE_LOG="${PROJECT_DIR}/guideline-enhancements.log"
!echo "[$(date)] Enhancement analysis run for ${PROJECT_KEY}" >> "$ENHANCE_LOG"
```

## Important Notes

- Improvements are suggestions only - user must approve before applying
- Focus on patterns, not individual one-off corrections
- Prioritize rules that cause repeated violations
- Preserve existing rule intent while improving clarity
- Consider cross-guideline consistency when making changes
