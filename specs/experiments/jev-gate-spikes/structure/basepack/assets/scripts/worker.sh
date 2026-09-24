#!/bin/sh
# One-shot deterministic script worker (no LLM): claim at most one bead, act by spike.role, close pass.
OUT=/tmp/gcsp-7HiB/out
LOG=$OUT/worker.log
GC=${GC_BIN:-gc}
JQ=/opt/homebrew/bin/jq
now() { perl -MTime::HiRes=time -e 'printf "%.3f", time'; }
echo "$(now) START pid=$$ session=$GC_SESSION_NAME" >> $LOG
out=$($GC hook --claim --drain-ack --json 2>>$LOG)
action=$(printf '%s' "$out" | $JQ -r '.action // empty' 2>/dev/null)
[ "$action" = "work" ] || { echo "$(now) NOWORK action=$action raw=$(printf '%s' "$out" | tr -d '\n' | cut -c1-200)" >> $LOG; exit 0; }
id=$(printf '%s' "$out" | $JQ -r '.bead_id')
claimed=$(now)
show() { $GC bd show "$1" --json 2>>$LOG | $JQ -c 'if type=="array" then .[0] else . end'; }
bead=$(show "$id")
m() { printf '%s' "$bead" | $JQ -r --arg k "$1" '.metadata[$k] // empty'; }
role=$(m spike.role); step=$(m gc.step_ref); root=$(m gc.root_bead_id)
echo "$(now) CLAIM id=$id step=$step role=$role root=$root" >> $LOG
set_md() { $GC bd update "$1" "$@" >>$LOG 2>&1; }
case "$role" in
  implement)
    # Q3: write upstream facts onto the workflow root.
    plan=$(m spike.plan)
    $GC bd update "$root" --set-metadata "spike.impl_summary=implemented-by-$id" --set-metadata "spike.review_plan=$plan" >>$LOG 2>&1
    echo "$(now) ROOTWRITE root=$root rc=$? plan=$plan" >> $LOG
    ;;
  gate)
    # Q3: read the root (via gc.root_bead_id) and derive the gate decision from upstream metadata.
    rootj=$(show "$root")
    rplan=$(printf '%s' "$rootj" | $JQ -r '.metadata["spike.review_plan"] // empty')
    rsum=$(printf '%s' "$rootj" | $JQ -r '.metadata["spike.impl_summary"] // empty')
    [ -z "$rplan" ] && rplan='{"acceptance":"run","test_evidence":"run","simplicity":"run"}'
    items=$(printf '%s' "$rplan" | $JQ -c '{items:[.]}')
    $GC bd update "$id" --set-metadata "spike.saw_root_plan=$rplan" --set-metadata "spike.saw_root_summary=$rsum" --set-metadata "gc.output_json=$items" >>$LOG 2>&1
    echo "$(now) GATE items=$items saw_summary=$rsum rc=$?" >> $LOG
    ;;
  lane)
    s=$(m spike.sleep); sleep ${s:-1}
    ;;
  synthesize)
    # Evidence: status of every lane bead in this workflow at claim time.
    lanes=$($GC bd list --all --json 2>>$LOG | $JQ -c --arg r "$root" '[.[] | select(.metadata["gc.root_bead_id"]==$r and .metadata["spike.role"]=="lane") | {s:.metadata["gc.step_ref"],st:.status}]')
    $GC bd update "$id" --set-metadata "spike.lanes_at_claim=$lanes" >>$LOG 2>&1
    echo "$(now) SYNTH lanes_at_claim=$lanes" >> $LOG
    ;;
esac
done_at=$(now)
$GC bd update "$id" --set-metadata "spike.claimed_at=$claimed" --set-metadata "spike.done_at=$done_at" --set-metadata gc.outcome=pass --status closed >>$LOG 2>&1
echo "$(now) CLOSED id=$id step=$step rc=$?" >> $LOG
exit 0
