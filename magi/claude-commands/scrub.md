---
description: Nuclear scrub - all project data + related sessions + history (user)
allowed-tools: Bash
---

# Nuclear Scrub (Archive Mode)

Archive all Claude Code traces for the current working directory to `${MAGI_PACK_DIR}/archived/`.

## 1. Create archive directory and identify project

!bash -c '
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-")
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR"
echo "Project: $PWD"
echo "Key: $PROJECT_KEY"
echo "Archive: $ARCHIVE_DIR"
'

## 2. Archive project data

!bash -c '
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR"
PROJECT_DIR="$HOME/.claude/projects/-${PROJECT_KEY}"
if [ -d "$PROJECT_DIR" ]; then
    mkdir -p "$ARCHIVE_DIR/projects/"
    mv "$PROJECT_DIR" "$ARCHIVE_DIR/projects/" 2>/dev/null && echo "✓ Archived projects/-$PROJECT_KEY" || echo "○ Failed to archive project dir"
else
    echo "○ No project dir found"
fi
'

## 3. Archive history.jsonl entries referencing this project

!bash -c '
PROJECT_PATH="$PWD"
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR"
HISTORY_FILE=${MAGI_PACK_DIR}/history.jsonl
if [ -f "$HISTORY_FILE" ]; then
    BEFORE=$(wc -l < "$HISTORY_FILE")
    jq -c "select(.cwd == \"$PROJECT_PATH\")" "$HISTORY_FILE" > "$ARCHIVE_DIR/history_extract.jsonl" 2>/dev/null || grep "\"cwd\":\"$PROJECT_PATH\"" "$HISTORY_FILE" > "$ARCHIVE_DIR/history_extract.jsonl"
    ARCHIVED=$(wc -l < "$ARCHIVE_DIR/history_extract.jsonl" 2>/dev/null || echo 0)
    TEMP_FILE=$(mktemp)
    jq -c "select(.cwd != \"$PROJECT_PATH\")" "$HISTORY_FILE" > "$TEMP_FILE" 2>/dev/null || grep -v "\"cwd\":\"$PROJECT_PATH\"" "$HISTORY_FILE" > "$TEMP_FILE"
    mv "$TEMP_FILE" "$HISTORY_FILE"
    echo "✓ Archived $ARCHIVED entries to history_extract.jsonl"
else
    echo "○ No history.jsonl found"
fi
'

## 4. Archive debug sessions related to this project

!bash -c '
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR/debug"
DEBUG_COUNT=0
for f in ${MAGI_PACK_DIR}/debug/*.txt; do
    if [ -f "$f" ] && grep -q "$PWD" "$f" 2>/dev/null; then
        mv "$f" "$ARCHIVE_DIR/debug/" 2>/dev/null && DEBUG_COUNT=$((DEBUG_COUNT + 1))
    fi
done
echo "✓ Archived $DEBUG_COUNT debug session files"
'

## 5. Archive file-history for this project

!bash -c '
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR"
if ls ${MAGI_PACK_DIR}/file-history/*"$PROJECT_KEY"* 1>/dev/null 2>&1; then
    mkdir -p "$ARCHIVE_DIR/file-history"
    mv ${MAGI_PACK_DIR}/file-history/*"$PROJECT_KEY"* "$ARCHIVE_DIR/file-history/" 2>/dev/null
    echo "✓ Archived file-history"
else
    echo "○ No file-history found"
fi
'

## 6. Archive todos for this project

!bash -c '
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR"
if ls ${MAGI_PACK_DIR}/todos/*"$PROJECT_KEY"* 1>/dev/null 2>&1; then
    mkdir -p "$ARCHIVE_DIR/todos"
    mv ${MAGI_PACK_DIR}/todos/*"$PROJECT_KEY"* "$ARCHIVE_DIR/todos/" 2>/dev/null
    echo "✓ Archived todos"
else
    echo "○ No todos found"
fi
'

## 7. Summary

!bash -c '
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-")
ARCHIVE_DIR=$(ls -dt ${MAGI_PACK_DIR}/archived/${PROJECT_KEY}-* 2>/dev/null | head -1)
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "SCRUB COMPLETE - Data archived to:"
echo "$ARCHIVE_DIR"
echo ""
ls -la "$ARCHIVE_DIR" 2>/dev/null || echo "Archive directory not found"
echo "════════════════════════════════════════════════════════════════════"
'

Run /clear to reset current conversation state.
