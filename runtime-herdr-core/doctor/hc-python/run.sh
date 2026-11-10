#!/bin/sh
# The runtime runs under the python3 on gc's PATH; it needs 3.9 or later.
# Checked without loading the pack, which an older Python cannot import.
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found on PATH: the herdr-core runtime needs Python 3.9 or later"
  exit 2
fi
exec python3 -I -S -c '
import sys
version = ".".join(str(part) for part in sys.version_info[:3])
if sys.version_info < (3, 9):
    print("python3 is " + version + ": the herdr-core runtime needs 3.9 or later")
    sys.exit(2)
print("python3 " + version)
'
