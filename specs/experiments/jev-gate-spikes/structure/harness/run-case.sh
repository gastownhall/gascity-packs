#!/bin/sh
# usage: run-case.sh <label> <formula> [sling args...]
. /tmp/gcsp-7HiB/env.sh
label=$1; formula=$2; shift 2
cd $P/city
echo "START $(date +%H:%M:%S)"
out=$(gc sling rig/jover.scripter "$formula" --formula --json "$@" 2>&1); echo "$out" > $P/out/$label.sling.txt; echo "$out" | tail -3
R=$(printf "%s" "$out" | jq -rs "[.[] | .. | objects | (.workflow_id // .root_id // empty)] | last // empty" 2>/dev/null)
[ -z "$R" ] && { echo "NO WORKFLOW"; exit 1; }
cd $P/rig
i=0; while [ $i -lt 90 ]; do s=$(gc bd show $R --json 2>/dev/null | jq -r '(if type=="array" then .[0] else . end).status'); [ "$s" = closed ] && break; i=$((i+1)); sleep 2; done
echo "ROOT $R status=$s at $(date +%H:%M:%S)"
sleep 3
gc bd list --all --json 2>/dev/null > $P/out/$label.all.json
jq -r --arg r $R 'map(select(.id==$r or .metadata["gc.root_bead_id"]==$r)) | sort_by(.closed_at//"z", .metadata["spike.done_at"]//"z") | .[] | [.id, .status, (.metadata["gc.step_ref"]//"(root)"), (.metadata["gc.kind"]//"-"), (.metadata["gc.outcome"]//"-"), (.created_at|tostring), (.closed_at//"-"), (.metadata["spike.claimed_at"]//"-"), (.metadata["spike.done_at"]//"-")] | @tsv' $P/out/$label.all.json | tee $P/out/$label.beads.tsv
jq -r --arg r $R 'map(select(.id==$r))[0].metadata | with_entries(select(.key|startswith("spike.")))' $P/out/$label.all.json > $P/out/$label.root-meta.json
jq -r --arg r $R 'map(select(.metadata["gc.root_bead_id"]==$r and (.metadata["spike.role"]=="gate" or .metadata["spike.role"]=="synthesize"))) | .[] | {step:.metadata["gc.step_ref"], saw_root_plan:.metadata["spike.saw_root_plan"], saw_root_summary:.metadata["spike.saw_root_summary"], output_json:.metadata["gc.output_json"], lanes_at_claim:.metadata["spike.lanes_at_claim"]}' $P/out/$label.all.json | tee $P/out/$label.evidence.json
