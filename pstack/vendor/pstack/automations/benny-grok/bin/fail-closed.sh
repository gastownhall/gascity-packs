#!/bin/sh
INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cmd = (d.get('toolInput') or {}).get('command') or ''
print(cmd)
") || exit 0

case "$CMD" in
  *gh\ pr\ merge*|*gh\ merge*|*git\ push\ --force*|*git\ push\ -f*|*git\ merge*git\ push*|*git\ push*git\ merge*|*gt\ merge*)
    printf '%s\n' '{"decision":"deny","reason":"Benny is draft-only. Do not merge, force-push, or gt merge."}'
    exit 2
    ;;
esac

printf '%s\n' '{"decision":"allow"}'
