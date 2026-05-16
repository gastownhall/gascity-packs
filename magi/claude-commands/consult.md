---
description: Consult LM Studio for scope/behavior review (user)
allowed-tools: Bash, Read, Write, WebFetch
---

# External Consultation via LM Studio

Consult the LM Studio instance at `${LM_STUDIO_HOST}:${LM_STUDIO_PORT}` to review Claude Code's adherence to scope, guidelines, and behavior patterns.

## 1. Gather consultation context

!PROJECT_KEY=$(echo "$PWD" | sed 's|^/||' | tr '/' '-' | tr '_' '-')
!PROJECT_DIR="$HOME/.claude/projects/-${PROJECT_KEY}"
!SCOPE_FILE="${PROJECT_DIR}/scope.md"
!echo "Project: $PWD"
!echo "Project Key: $PROJECT_KEY"
!if [ -f "$SCOPE_FILE" ]; then \
    echo "Scope file: $SCOPE_FILE"; \
else \
    echo "No scope file found (run /scope to create one)"; \
fi

## 2. Check LM Studio availability

First, verify LM Studio is reachable:

```bash
curl -s --connect-timeout 5 ${LM_STUDIO_URL%/v1/responses}/v1/models | head -c 200
```

If this fails, LM Studio is not available. Report the connection issue and abort.

## 3. Prepare consultation payload

Read the following files to build the consultation context:
1. The scope file (if it exists): `${MAGI_PACK_DIR}/projects/-{PROJECT_KEY}/scope.md`
2. Recent enforcement logs: `${MAGI_PACK_DIR}/projects/-{PROJECT_KEY}/*-enforcement.log`
3. The current conversation history (summarize the key actions taken)

## 4. Send consultation request

Use Bash with curl to POST to LM Studio (WebFetch is for GET requests):

**Endpoint:** `${LM_STUDIO_URL%/v1/responses}/v1/chat/completions`

**Request:**
```bash
curl -s -X POST "${LM_STUDIO_URL%/v1/responses}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistralai/magistral-small-2509",
    "messages": [
      {
        "role": "system",
        "content": "You are a code review consultant. Analyze whether the assistant has followed the project scope and guidelines. Identify any scope creep, violations, or areas of concern. Be specific and actionable."
      },
      {
        "role": "user",
        "content": "<scope>\n{SCOPE_CONTENT}\n</scope>\n\n<enforcement_log>\n{ENFORCEMENT_LOG}\n</enforcement_log>\n\n<conversation_summary>\n{SUMMARY_OF_ACTIONS}\n</conversation_summary>\n\nReview this session for:\n1. Scope adherence - is the work aligned with stated objectives?\n2. Guideline compliance - were the right guidelines read and followed?\n3. Agent usage - were appropriate agents used for tasks?\n4. Scope creep detection - identify any work outside the defined scope\n5. Recommendations - what adjustments are needed?"
      }
    ],
    "temperature": 0.3,
    "max_tokens": 4000,
    "stream": false
  }'
```

Replace `{SCOPE_CONTENT}`, `{ENFORCEMENT_LOG}`, and `{SUMMARY_OF_ACTIONS}` with actual content gathered in step 3.

## 5. Process and present consultation results

After receiving the LM Studio response:

1. Parse the JSON response to extract `.choices[0].message.content`
2. Present the consultation findings in a structured format
3. Highlight any scope violations or concerns
4. Provide actionable recommendations

## 6. Log the consultation

!PROJECT_KEY=$(echo "$PWD" | sed 's|^/||' | tr '/' '-' | tr '_' '-')
!PROJECT_DIR="$HOME/.claude/projects/-${PROJECT_KEY}"
!mkdir -p "$PROJECT_DIR"
!CONSULT_LOG="${PROJECT_DIR}/consultation.log"
!echo "[$(date)] Consultation requested" >> "$CONSULT_LOG"

## LM Studio Configuration Reference

Defaults read from environment (override per project):

| Setting | Value |
|---------|-------|
| Host | `${LM_STUDIO_HOST:-localhost}` |
| Port | `${LM_STUDIO_PORT:-1234}` |
| Base URL | `${LM_STUDIO_URL:-http://localhost:1234/v1}` |
| Review Model | `${LM_STUDIO_REVIEW_MODEL:-mistralai/magistral-small-2509}` |
| Context Model | `${LM_STUDIO_CONTEXT_MODEL:-ibm/granite-4-h-tiny}` |
| Chat Endpoint | `/chat/completions` |
| Timeout | 300 seconds |
| Temperature | 0.7 (default), 0.3 (for review) |
| Max Tokens | 4000 |

## Important Notes

- LM Studio runs on `${LM_STUDIO_HOST}:${LM_STUDIO_PORT}` (NOT localhost)
- The consultation is advisory - use judgment on recommendations
- If LM Studio is unavailable, report the connection issue
- Consultation results do not automatically modify behavior
- Alternative host available: `100.96.240.53:1234` (secondary IP)
