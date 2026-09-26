#!/bin/sh
# Fail the first loop attempt per workflow, pass the second.
OUT=/tmp/jl-Ke2A/out
key=$(basename "${GC_MOLECULE_DIR:-unknown}")
env | grep -E '^(GC_|BEADS_)' | sort > $OUT/check-env.$key.${GC_ITERATION:-x}.txt
n=$(cat $OUT/check-count.$key 2>/dev/null || echo 0); n=$((n+1)); echo $n > $OUT/check-count.$key
echo "$(date +%H:%M:%S) CHECK key=$key attempt=$n iter=$GC_ITERATION bead=$GC_BEAD_ID" >> $OUT/check.log
[ $n -ge 2 ] && exit 0
echo "first attempt fails on purpose" >&2
exit 1
