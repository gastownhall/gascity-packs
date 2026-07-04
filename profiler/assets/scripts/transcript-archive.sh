#!/bin/sh
# Archive transcripts for recently stopped sessions into the profiles area.
# Idempotent: skips sessions already archived. Lookback covers the eval
# cadence of event-triggered orders (controller patrol tick).
set -eu

CITY="${GC_CITY_PATH:?missing GC_CITY_PATH}"
LOOKBACK="${GC_TRANSCRIPT_ARCHIVE_LOOKBACK:-10m}"
DEST="$CITY/.gc/runtime/profiles/_transcripts"
mkdir -p "$DEST"

gc events --type session.stopped --since "$LOOKBACK" 2>/dev/null | while IFS= read -r line; do
  sid=$(printf '%s' "$line" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("subject",""))' 2>/dev/null) || continue
  [ -n "$sid" ] || continue
  out="$DEST/$sid.jsonl.gz"
  [ -e "$out" ] && continue
  python3 - "$sid" "$CITY" "$out" << 'PY'
import gzip, json, os, shutil, subprocess, sys
sid, city, out = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    beads = json.loads(subprocess.run(
        ["bd", "show", sid, "--json"], cwd=city,
        capture_output=True, text=True, timeout=60).stdout)
    b = beads[0] if isinstance(beads, list) else beads
    md = b.get("metadata") or {}
    wd, key = md.get("work_dir", ""), md.get("session_key", "")
    if not (wd and key):
        sys.exit(0)
    slug = os.path.abspath(wd).replace("/", "-").replace(".", "-")
    src = os.path.expanduser(f"~/.claude/projects/{slug}/{key}.jsonl")
    if not os.path.exists(src) and os.path.abspath(wd).startswith(("/tmp", "/var")):
        slug = ("-private" + os.path.abspath(wd).replace("/", "-")).replace(".", "-")
        src = os.path.expanduser(f"~/.claude/projects/{slug}/{key}.jsonl")
    if os.path.exists(src):
        with open(src, "rb") as f, gzip.open(out, "wb") as z:
            shutil.copyfileobj(f, z)
        print(f"archived {sid}")
except Exception as e:
    print(f"transcript-archive {sid}: {e}", file=sys.stderr)
PY
done
exit 0
