---
description: Nuclear scrub using MongoDB - no overwrites (user)
allowed-tools: Bash
---

# MongoDB-Based Nuclear Scrub

Archive all Claude Code traces for current directory to MongoDB with unique timestamps.

## 1. Source common functions and identify project

!bash -c '
set -Eeuo pipefail
source ${MAGI_PACK_DIR}/migration/common.sh 2>/dev/null || {
    echo "ERROR: Migration common.sh not found. Run history_mongodb_setup.sh first."
    exit 1
}
PROJECT_PATH="$PWD"
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-" | tr -cd "[:alnum:]_-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_COLLECTION="archive_${PROJECT_KEY}_${TIMESTAMP}"
echo "════════════════════════════════════════════════════════════════════"
echo "Project: $PROJECT_PATH"
echo "Key: $PROJECT_KEY"
echo "MongoDB Archive: $ARCHIVE_COLLECTION"
echo "════════════════════════════════════════════════════════════════════"
'

## 2. Archive history to MongoDB

!bash -c '
set -Eeuo pipefail
source ${MAGI_PACK_DIR}/migration/common.sh 2>/dev/null
PROJECT_PATH="$PWD"
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-" | tr -cd "[:alnum:]_-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_COLLECTION="archive_${PROJECT_KEY}_${TIMESTAMP}"
ARCHIVE_COUNT=$(mongosh claude_history --quiet --eval "
use claude_history;
var count = 0;
// Archive from global_history
db.global_history.find({ cwd: \"$PROJECT_PATH\" }).forEach(function(doc) {
    doc.archived_at = new Date();
    doc.original_collection = \"global_history\";
    db[\"$ARCHIVE_COLLECTION\"].insertOne(doc);
    count++;
});
// Archive from project-specific collection
var projectColl = \"${PROJECT_KEY//[^a-zA-Z0-9_]/_}\";
if (db.getCollectionNames().includes(projectColl)) {
    db[projectColl].find().forEach(function(doc) {
        doc.archived_at = new Date();
        doc.original_collection = projectColl;
        db[\"$ARCHIVE_COLLECTION\"].insertOne(doc);
        count++;
    });
    db[projectColl].drop();
}
// Remove from global_history
db.global_history.deleteMany({ cwd: \"$PROJECT_PATH\" });
print(count);
" 2>/dev/null || echo "0")
echo "✓ Archived $ARCHIVE_COUNT history entries to MongoDB"
'

## 3. Archive project directory

!bash -c '
set -Eeuo pipefail
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-" | tr -cd "[:alnum:]_-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR"
PROJECT_DIR="$HOME/.claude/projects/-${PROJECT_KEY}"
if [ -d "$PROJECT_DIR" ]; then
    mkdir -p "$ARCHIVE_DIR/projects/"
    cp -r "$PROJECT_DIR" "$ARCHIVE_DIR/projects/" 2>/dev/null
    rm -rf "$PROJECT_DIR"
    echo "✓ Archived project directory"
else
    echo "○ No project directory found"
fi
'

## 4. Archive debug sessions

!bash -c '
set -Eeuo pipefail
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-" | tr -cd "[:alnum:]_-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR/debug"
DEBUG_COUNT=0
for f in ${MAGI_PACK_DIR}/debug/*.txt; do
    if [ -f "$f" ] && grep -q "$PWD" "$f" 2>/dev/null; then
        mv "$f" "$ARCHIVE_DIR/debug/" 2>/dev/null && DEBUG_COUNT=$((DEBUG_COUNT + 1))
    fi
done
echo "✓ Archived $DEBUG_COUNT debug files"
'

## 5. Archive file-history

!bash -c '
set -Eeuo pipefail
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-" | tr -cd "[:alnum:]_-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
if ls ${MAGI_PACK_DIR}/file-history/*"$PROJECT_KEY"* 1>/dev/null 2>&1; then
    mkdir -p "$ARCHIVE_DIR/file-history"
    mv ${MAGI_PACK_DIR}/file-history/*"$PROJECT_KEY"* "$ARCHIVE_DIR/file-history/" 2>/dev/null
    echo "✓ Archived file-history"
else
    echo "○ No file-history found"
fi
'

## 6. Archive todos

!bash -c '
set -Eeuo pipefail
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-" | tr -cd "[:alnum:]_-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
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
set -Eeuo pipefail
PROJECT_KEY=$(echo "$PWD" | sed "s|^/||" | tr "/" "-" | tr "_" "-" | tr -cd "[:alnum:]_-")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_COLLECTION="archive_${PROJECT_KEY}_${TIMESTAMP}"
ARCHIVE_DIR="$HOME/.claude/archived/${PROJECT_KEY}-${TIMESTAMP}"
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "SCRUB COMPLETE"
echo ""
echo "MongoDB Archive: $ARCHIVE_COLLECTION"
echo "File Archive: $ARCHIVE_DIR"
echo ""
echo "To export MongoDB archive later:"
echo "  mongosh claude_history --eval \"db.$ARCHIVE_COLLECTION.find()\" > export.jsonl"
echo ""
echo "To view archive info:"
echo "  mongosh claude_history --eval \"db.$ARCHIVE_COLLECTION.stats()\""
echo "════════════════════════════════════════════════════════════════════"
'

Run /clear to reset conversation state.