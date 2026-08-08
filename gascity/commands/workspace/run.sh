#!/usr/bin/env bash
set -euo pipefail

fail() { printf 'workspace: %s\n' "$*" >&2; exit 1; }
need_value() { [ "$#" -ge 2 ] || fail "missing value for $1"; [ -n "$2" ] || fail "empty value for $1"; case "$2" in -*) fail "malformed value for $1";; esac; }

[ "$#" -ge 1 ] || fail "missing action"
ACTION=$1; shift
case "$ACTION" in prepare|path|verify-entry|record-result|result|cleanup|cleanup-if-complete) ;; *) fail "unknown action: $ACTION";; esac
STEP_ID= INPUT_REF= WORKSPACE_PARENT=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --step-id) [ -z "$STEP_ID" ] || fail "duplicate --step-id"; need_value "$@"; STEP_ID=$2; shift 2;;
    --input-ref) [ "$ACTION" = prepare ] || fail "--input-ref is only valid for prepare"; [ -z "$INPUT_REF" ] || fail "duplicate --input-ref"; need_value "$@"; INPUT_REF=$2; shift 2;;
    --workspace-parent) [ "$ACTION" = prepare ] || fail "--workspace-parent is only valid for prepare"; [ -z "$WORKSPACE_PARENT" ] || fail "duplicate --workspace-parent"; need_value "$@"; WORKSPACE_PARENT=$2; shift 2;;
    *) fail "unknown argument: $1";;
  esac
done
[ -n "$STEP_ID" ] || fail "missing --step-id"
if [ "$ACTION" = prepare ]; then [ -n "$INPUT_REF" ] || fail "missing --input-ref"; fi
GC_WORK_DIR=${GC_WORK_DIR:-${GC_RIG_ROOT:-}}
[ -n "$GC_WORK_DIR" ] || fail "GC_WORK_DIR or GC_RIG_ROOT is required"

canonical_dir() { python3 - "$1" <<'PY'
import os,sys
p=sys.argv[1]
if not os.path.isdir(p): raise SystemExit(1)
print(os.path.realpath(p))
PY
}
RIG_ROOT=$(canonical_dir "$GC_WORK_DIR") || fail "GC_WORK_DIR is not an existing directory"
unset GIT_DIR GIT_WORK_TREE
if [ -d "$RIG_ROOT/.git" ] && [ "$(git --git-dir="$RIG_ROOT/.git" rev-parse --is-bare-repository 2>/dev/null || :)" = true ]; then
  REPO_KIND=control; COMMON_GIT_DIR=$(canonical_dir "$RIG_ROOT/.git") || fail "invalid bare .git control repository"
elif git -C "$RIG_ROOT" rev-parse --git-common-dir >/dev/null 2>&1 && [ "$(git -C "$RIG_ROOT" rev-parse --is-bare-repository 2>/dev/null || :)" = false ]; then
  REPO_KIND=ordinary; RAW_COMMON=$(git -C "$RIG_ROOT" rev-parse --path-format=absolute --git-common-dir) || fail "cannot resolve Git common directory"; COMMON_GIT_DIR=$(canonical_dir "$RAW_COMMON") || fail "invalid Git common directory"
elif [ "$(git --git-dir="$RIG_ROOT" rev-parse --is-bare-repository 2>/dev/null || :)" = true ]; then
  REPO_KIND=bare; COMMON_GIT_DIR=$RIG_ROOT
else fail "GC_WORK_DIR does not identify a supported Git repository"; fi
GIT=(git --git-dir="$COMMON_GIT_DIR")

show_bead() { gc bd show "$1" --json 2>/dev/null || fail "gc bd show failed for $1"; }
json_string_field() { python3 -c '
import json,sys
label,key=sys.argv[1:]
try: value=json.load(sys.stdin)
except Exception: raise SystemExit(f"malformed JSON for {label}")
if isinstance(value,list):
 if len(value)!=1: raise SystemExit(f"ambiguous JSON array for {label}")
 value=value[0]
if not isinstance(value,dict): raise SystemExit(f"malformed object for {label}")
result=value.get(key,"")
if result is None: result=""
if not isinstance(result,str): raise SystemExit(f"malformed {key} on {label}")
print(result)
' "$1" "$2"; }
metadata_value() { python3 -c '
import json,sys
label,key=sys.argv[1:]
try: value=json.load(sys.stdin)
except Exception: raise SystemExit(f"malformed JSON for {label}")
if isinstance(value,list):
 if len(value)!=1: raise SystemExit(f"ambiguous JSON array for {label}")
 value=value[0]
if not isinstance(value,dict): raise SystemExit(f"malformed object for {label}")
metadata=value.get("metadata")
if not isinstance(metadata,dict): raise SystemExit(f"malformed metadata for {label}")
result=metadata.get(key,"")
if result is None: result=""
if not isinstance(result,str): raise SystemExit(f"malformed {key} on {label}")
print(result)
' "$1" "$2"; }
STEP_JSON=$(show_bead "$STEP_ID")
ROOT_ID=$(metadata_value "$STEP_ID" gc.root_bead_id <<<"$STEP_JSON") || fail "invalid step metadata"
[ -n "$ROOT_ID" ] || fail "missing gc.root_bead_id on $STEP_ID"
ROOT_JSON=$(show_bead "$ROOT_ID")
CONVOY_ID=$(metadata_value "$ROOT_ID" gc.input_convoy_id <<<"$ROOT_JSON") || fail "invalid workflow root metadata"
[ -n "$CONVOY_ID" ] || fail "missing gc.input_convoy_id on $ROOT_ID"
ROOT_DRAIN=$(metadata_value "$ROOT_ID" gc.drain_member_id <<<"$ROOT_JSON") || fail "invalid workflow root metadata"
CONVOY_JSON=$(show_bead "$CONVOY_ID")
SYNTHETIC_KIND=$(metadata_value "$CONVOY_ID" gc.synthetic_kind <<<"$CONVOY_JSON") || fail "invalid input convoy metadata"
if [ "$SYNTHETIC_KIND" = drain-unit-convoy ]; then
  SOURCE_ANCHOR_ID=$(metadata_value "$CONVOY_ID" gc.drain_member_id <<<"$CONVOY_JSON") || fail "invalid input convoy metadata"
  [ -n "$SOURCE_ANCHOR_ID" ] || fail "missing gc.drain_member_id on drain-unit convoy $CONVOY_ID"
  [ "$SOURCE_ANCHOR_ID" != "$CONVOY_ID" ] || fail "drain-unit convoy cannot anchor itself"
else SOURCE_ANCHOR_ID=$CONVOY_ID; fi
if [ -n "$ROOT_DRAIN" ] && [ "$ROOT_DRAIN" != "$SOURCE_ANCHOR_ID" ]; then fail "workflow root drain member does not match source anchor"; fi
SOURCE_JSON=$(show_bead "$SOURCE_ANCHOR_ID")
OWNER_ID=$(json_string_field "$SOURCE_ANCHOR_ID" parent_convoy_id <<<"$SOURCE_JSON") || fail "invalid source anchor graph identity"
[ -n "$OWNER_ID" ] || fail "source anchor has no parent convoy"
OWNER_JSON=$(show_bead "$OWNER_ID")
OWNER_PARENT_ID=$(json_string_field "$OWNER_ID" parent_convoy_id <<<"$OWNER_JSON") || fail "invalid workspace owner graph identity"
if [ -n "$OWNER_PARENT_ID" ]; then OWNER_KIND=epic; else OWNER_KIND=convoy; fi

read -r OWNER_DIGEST NAME_DIGEST HOST_ID <<EOF
$(python3 - "$COMMON_GIT_DIR" "$OWNER_KIND" "$OWNER_ID" <<'PY'
import hashlib,socket,sys
common,kind,owner=sys.argv[1:]
value=common+"\0"+kind+"\0"+owner
digest=hashlib.sha256(value.encode()).hexdigest()
print(digest,digest[:20],socket.gethostname())
PY
)
EOF
SAFE_PREFIX=$(python3 - "$OWNER_ID" <<'PY'
import re,sys
s=re.sub(r"[^A-Za-z0-9._-]+","-",sys.argv[1]).strip(".-_")[:32]
print(s or "workspace")
PY
)
WORKTREE_NAME="$SAFE_PREFIX-$NAME_DIGEST"
STATE_DIR="$COMMON_GIT_DIR/gc-workspace-state/$OWNER_KIND"
STATE_FILE="$STATE_DIR/$OWNER_DIGEST.json"
LOCK_DIR="$STATE_FILE.lock"; LOCK_OWNED=0
cleanup_lock() { if [ "$LOCK_OWNED" = 1 ]; then python3 - "$LOCK_DIR" <<'PY' 2>/dev/null || :
import os,sys
try: os.unlink(os.path.join(sys.argv[1],"owner.json")); os.rmdir(sys.argv[1])
except FileNotFoundError: pass
PY
fi; }
trap cleanup_lock EXIT HUP INT TERM
acquire_lock() { python3 - "$STATE_DIR" "$LOCK_DIR" "$HOST_ID" <<'PY' || return 1
import json,os,sys
state_dir,lock_dir,host=sys.argv[1:]; os.makedirs(state_dir,mode=0o700,exist_ok=True)
try: os.mkdir(lock_dir,0o700)
except FileExistsError:
 print("workspace lock already exists",file=sys.stderr); raise SystemExit(1)
with open(os.path.join(lock_dir,"owner.json"),"x",encoding="utf-8") as f: json.dump({"pid":os.getpid(),"host_id":host},f,separators=(",",":"))
PY
LOCK_OWNED=1; }
release_lock() { cleanup_lock; LOCK_OWNED=0; }

owner_complete() {
  gc bd list --all --json --limit=0 2>/dev/null | python3 -c '
import json,sys
owner,current=sys.argv[1:]
try: values=json.load(sys.stdin)
except Exception: raise SystemExit(2)
if not isinstance(values,list): raise SystemExit(2)
members=[]
for value in values:
 if not isinstance(value,dict): raise SystemExit(2)
 parent=value.get("parent_convoy_id","")
 if parent is None: parent=""
 if not isinstance(parent,str): raise SystemExit(2)
 if parent==owner: members.append(value)
member_ids=[]
for value in members:
 ident=value.get("id")
 if not isinstance(ident,str) or not ident: raise SystemExit(2)
 member_ids.append(ident)
if not members or current not in member_ids or len(member_ids)!=len(set(member_ids)):
 raise SystemExit(2)
for value in members:
 metadata=value.get("metadata",{})
 if not isinstance(metadata,dict): raise SystemExit(2)
 if value.get("status")!="closed" or metadata.get("gc.outcome")!="pass": raise SystemExit(1)
' "$OWNER_ID" "$SOURCE_ANCHOR_ID"
}

emit_cleanup() { python3 - "$1" "$OWNER_KIND" "$OWNER_ID" <<'PY'
import json,sys
status,kind,owner=sys.argv[1:]
print(json.dumps({"cleanup":status,"workspace_owner_kind":kind,"workspace_owner_id":owner},separators=(",",":")))
PY
}

managed_worktree_absent() {
  [ ! -e "$RIG_ROOT/worktrees/$WORKTREE_NAME" ] && [ ! -L "$RIG_ROOT/worktrees/$WORKTREE_NAME" ] || return 1
  "${GIT[@]}" worktree list --porcelain -z | python3 -c '
import os,sys
name=sys.argv[1]
raw=sys.stdin.buffer.read()
if raw and not raw.endswith(b"\0"): raise SystemExit(2)
for field in raw.split(b"\0"):
 if not field: continue
 if field.startswith(b"worktree "):
  path=os.fsdecode(field[len(b"worktree "):])
  if os.path.basename(path)==name: raise SystemExit(1)
' "$WORKTREE_NAME"
}

state_field() { python3 - "$STATE_FILE" "$1" <<'PY'
import json,sys
path,field=sys.argv[1:]
expected={"version","workspace_owner_kind","workspace_owner_id","source_anchor_id","host_id","common_git_dir","worktree_path","input_oid","phase","output_oid"}
try:
 with open(path,encoding="utf-8") as f: state=json.load(f)
except Exception as e: raise SystemExit(f"invalid workspace state: {e}")
if not isinstance(state,dict) or set(state)!=expected: raise SystemExit("workspace state has invalid fields")
if state["version"]!=2 or any(not isinstance(state[k],str) for k in expected-{"version"}): raise SystemExit("workspace state has invalid values")
if state["phase"] not in ("preparing","entry","result"): raise SystemExit("workspace state has invalid phase")
print(state[field])
PY
}
write_state() { python3 - "$STATE_FILE" "$OWNER_KIND" "$OWNER_ID" "$SOURCE_ANCHOR_ID" "$HOST_ID" "$COMMON_GIT_DIR" "$WORKTREE_PATH" "$INPUT_OID" "$PHASE" "$OUTPUT_OID" <<'PY'
import json,os,sys,tempfile
path,kind,owner,anchor,host,common,worktree,input_oid,phase,output_oid=sys.argv[1:]
state={"version":2,"workspace_owner_kind":kind,"workspace_owner_id":owner,"source_anchor_id":anchor,"host_id":host,"common_git_dir":common,"worktree_path":worktree,"input_oid":input_oid,"phase":phase,"output_oid":output_oid}
fd,tmp=tempfile.mkstemp(prefix=".state-",dir=os.path.dirname(path),text=True)
try:
 with os.fdopen(fd,"w",encoding="utf-8") as f: json.dump(state,f,separators=(",",":")); f.write("\n"); f.flush(); os.fsync(f.fileno())
 os.replace(tmp,path)
finally:
 try: os.unlink(tmp)
 except FileNotFoundError: pass
PY
}
load_state() {
  [ -f "$STATE_FILE" ] || fail "workspace state not found"
  STATE_OWNER_KIND=$(state_field workspace_owner_kind) || fail "cannot read workspace state"; STATE_OWNER_ID=$(state_field workspace_owner_id) || fail "cannot read workspace state"; STATE_ANCHOR=$(state_field source_anchor_id) || fail "cannot read workspace state"; STATE_HOST=$(state_field host_id) || fail "cannot read workspace state"; STATE_COMMON=$(state_field common_git_dir) || fail "cannot read workspace state"
  WORKTREE_PATH=$(state_field worktree_path) || fail "cannot read workspace state"; INPUT_OID=$(state_field input_oid) || fail "cannot read workspace state"; PHASE=$(state_field phase) || fail "cannot read workspace state"; OUTPUT_OID=$(state_field output_oid) || fail "cannot read workspace state"
  [ "$STATE_OWNER_KIND" = "$OWNER_KIND" ] || fail "workspace state owner kind mismatch"; [ "$STATE_OWNER_ID" = "$OWNER_ID" ] || fail "workspace state owner mismatch"; [ "$STATE_HOST" = "$HOST_ID" ] || fail "workspace state belongs to another host"; [ "$STATE_COMMON" = "$COMMON_GIT_DIR" ] || fail "workspace state repository mismatch"
  case "$WORKTREE_PATH" in /*) ;; *) fail "recorded worktree path is not absolute";; esac
  EXPECTED_NAME=$(python3 - "$OWNER_ID" "$NAME_DIGEST" <<'PY'
import re,sys
s=re.sub(r"[^A-Za-z0-9._-]+","-",sys.argv[1]).strip(".-_")[:32]
print((s or "workspace")+"-"+sys.argv[2])
PY
)
  [ "$(basename "$WORKTREE_PATH")" = "$EXPECTED_NAME" ] || fail "recorded worktree path does not match workspace identity"
}
is_registered_path() { "${GIT[@]}" worktree list --porcelain | python3 -c 'import os,sys; target=os.path.realpath(sys.argv[1]); found=any(line.startswith("worktree ") and os.path.realpath(line[9:].rstrip("\n"))==target for line in sys.stdin); raise SystemExit(0 if found else 1)' "$WORKTREE_PATH"; }
validate_path_registration() {
  [ -d "$WORKTREE_PATH" ] || fail "recorded worktree path is missing"; [ ! -L "$WORKTREE_PATH" ] || fail "recorded worktree path is a symlink"
  CANON_WORKTREE=$(canonical_dir "$WORKTREE_PATH") || fail "cannot canonicalize recorded worktree"; [ "$CANON_WORKTREE" = "$WORKTREE_PATH" ] || fail "recorded worktree canonical path changed"; is_registered_path || fail "recorded worktree is not registered"
  ACTUAL_COMMON=$(git -C "$WORKTREE_PATH" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || fail "recorded path is not a Git worktree"; ACTUAL_COMMON=$(canonical_dir "$ACTUAL_COMMON") || fail "worktree common directory is invalid"; [ "$ACTUAL_COMMON" = "$COMMON_GIT_DIR" ] || fail "worktree belongs to another repository"
}
validate_detached_clean() {
  git -C "$WORKTREE_PATH" symbolic-ref -q HEAD >/dev/null 2>&1 && fail "worktree HEAD is attached"
  HEAD_OID=$(git -C "$WORKTREE_PATH" rev-parse --verify HEAD 2>/dev/null) || fail "worktree HEAD is invalid"; STATUS=$(git -C "$WORKTREE_PATH" status --porcelain=v1 --untracked-files=all) || fail "cannot inspect worktree status"; [ -z "$STATUS" ] || fail "worktree is dirty"
  WORKTREE_GIT_DIR=$(git -C "$WORKTREE_PATH" rev-parse --path-format=absolute --git-dir) || fail "cannot resolve worktree Git directory"
  python3 - "$WORKTREE_GIT_DIR" <<'PY' || fail "worktree has an in-progress Git operation"
import os,sys
markers=("MERGE_HEAD","CHERRY_PICK_HEAD","REVERT_HEAD","REBASE_HEAD","BISECT_LOG","sequencer","rebase-apply","rebase-merge")
raise SystemExit(1 if any(os.path.exists(os.path.join(sys.argv[1],marker)) for marker in markers) else 0)
PY
}
emit_json() { python3 - "$WORKTREE_PATH" "$INPUT_OID" "$OUTPUT_OID" "$PHASE" "$SOURCE_ANCHOR_ID" <<'PY'
import json,sys
path,input_oid,output_oid,phase,source_anchor_id=sys.argv[1:]
result={"worktree_path":path,"input_oid":input_oid,"phase":phase,"source_anchor_id":source_anchor_id}
if output_oid: result["output_oid"]=output_oid
print(json.dumps(result,separators=(",",":")))
PY
}

if [ "$ACTION" = prepare ]; then
  while :; do
    if acquire_lock; then
      if [ ! -f "$STATE_FILE" ]; then break; fi
      load_state
      if [ "$STATE_ANCHOR" = "$SOURCE_ANCHOR_ID" ] || [ "$PHASE" = result ]; then break; fi
      release_lock
    fi
    sleep 1
  done
else
  acquire_lock || fail "cannot acquire workspace lock"
fi
if { [ "$ACTION" = cleanup ] || [ "$ACTION" = cleanup-if-complete ]; } && [ ! -f "$STATE_FILE" ]; then
  managed_worktree_absent || fail "workspace state is absent but the managed worktree still exists or is ambiguous"
  if [ "$ACTION" = cleanup-if-complete ]; then emit_cleanup already-removed; fi
  exit 0
fi
if [ "$ACTION" = prepare ]; then
  REQUESTED_INPUT=$("${GIT[@]}" rev-parse --verify "$INPUT_REF^{commit}" 2>/dev/null) || fail "input ref does not resolve to a commit"
  if [ -f "$STATE_FILE" ]; then
    load_state
    if [ -n "$WORKSPACE_PARENT" ]; then REQUESTED_PARENT=$(canonical_dir "$WORKSPACE_PARENT") || fail "workspace parent must already exist on replay"; [ "$(dirname "$WORKTREE_PATH")" = "$REQUESTED_PARENT" ] || fail "workspace parent does not match recorded state"; fi
    validate_path_registration; validate_detached_clean
    if [ "$STATE_ANCHOR" = "$SOURCE_ANCHOR_ID" ]; then
      [ "$REQUESTED_INPUT" = "$INPUT_OID" ] || fail "input revision does not match recorded state"
      case "$PHASE" in entry) [ "$HEAD_OID" = "$INPUT_OID" ] || fail "entry HEAD does not match recorded input";; result) [ "$HEAD_OID" = "$OUTPUT_OID" ] || fail "result HEAD does not match recorded output";; preparing) [ "$HEAD_OID" = "$INPUT_OID" ] || fail "preparing HEAD does not match recorded input"; PHASE=entry; write_state;; esac
    else
      [ "$PHASE" = result ] || fail "cannot replace an incomplete workspace item"
      [ -n "$OUTPUT_OID" ] || fail "completed workspace item has no output"
      [ "$HEAD_OID" = "$OUTPUT_OID" ] || fail "completed item HEAD does not match recorded output"
      INPUT_OID=$OUTPUT_OID; PHASE=entry; OUTPUT_OID=; write_state
    fi
  else
    INPUT_OID=$REQUESTED_INPUT
    if [ -z "$WORKSPACE_PARENT" ]; then [ "$REPO_KIND" != bare ] || fail "true bare repository requires --workspace-parent"; WORKSPACE_PARENT="$RIG_ROOT/worktrees"; fi
    REQUESTED_PARENT=$(python3 - "$WORKSPACE_PARENT" <<'PY'
import os,sys
print(os.path.realpath(os.path.abspath(sys.argv[1])))
PY
)
    python3 - "$REQUESTED_PARENT" <<'PY' || fail "cannot create workspace parent"
import os,sys
os.makedirs(sys.argv[1],mode=0o755,exist_ok=True)
PY
    WORKSPACE_PARENT=$(canonical_dir "$REQUESTED_PARENT") || fail "invalid workspace parent"
    WORKTREE_PATH="$WORKSPACE_PARENT/$WORKTREE_NAME"; [ ! -e "$WORKTREE_PATH" ] && [ ! -L "$WORKTREE_PATH" ] || fail "workspace path already exists"; PHASE=preparing; OUTPUT_OID=; write_state
    if ! "${GIT[@]}" worktree add --detach "$WORKTREE_PATH" "$INPUT_OID" >/dev/null; then fail "git worktree add failed; retained preparing state at $WORKTREE_PATH"; fi
    validate_path_registration; validate_detached_clean; [ "$HEAD_OID" = "$INPUT_OID" ] || fail "created worktree HEAD does not match input"; PHASE=entry; write_state
  fi
else
  load_state
  [ "$STATE_ANCHOR" = "$SOURCE_ANCHOR_ID" ] || fail "action must use the current workspace item"
fi

case "$ACTION" in
  prepare) emit_json;;
  path) validate_path_registration; printf '%s\n' "$WORKTREE_PATH";;
  verify-entry) [ "$PHASE" = entry ] || fail "workspace is not in entry phase"; validate_path_registration; validate_detached_clean; [ "$HEAD_OID" = "$INPUT_OID" ] || fail "entry HEAD does not match recorded input"; emit_json;;
  record-result)
    case "$PHASE" in
      entry) validate_path_registration; validate_detached_clean; "${GIT[@]}" merge-base --is-ancestor "$INPUT_OID" "$HEAD_OID" || fail "result does not descend from input"; "${GIT[@]}" rev-list --parents "$INPUT_OID..$HEAD_OID" | python3 -c 'import sys; raise SystemExit(1 if any(len(line.split()) > 2 for line in sys.stdin) else 0)' || fail "result history is not linear"; OUTPUT_OID=$HEAD_OID; PHASE=result; write_state;;
      result) validate_path_registration; validate_detached_clean; [ "$HEAD_OID" = "$OUTPUT_OID" ] || fail "recorded result HEAD changed";;
      *) fail "workspace is not ready to record a result";;
    esac
    emit_json;;
  result) [ "$PHASE" = result ] && [ -n "$OUTPUT_OID" ] || fail "workspace result is not recorded"; validate_path_registration; validate_detached_clean; [ "$HEAD_OID" = "$OUTPUT_OID" ] || fail "recorded result HEAD changed"; emit_json;;
  cleanup|cleanup-if-complete)
    if [ "$ACTION" = cleanup-if-complete ]; then
      if owner_complete; then :; else COMPLETE_STATUS=$?; [ "$COMPLETE_STATUS" = 1 ] || fail "cannot validate workspace owner completion"; emit_cleanup retained; exit 0; fi
    fi
    [ "$PHASE" = result ] && [ -n "$OUTPUT_OID" ] || fail "workspace item is incomplete"
    validate_path_registration; validate_detached_clean; [ "$HEAD_OID" = "$OUTPUT_OID" ] || fail "cleanup HEAD differs from recorded output"
    "${GIT[@]}" worktree remove "$WORKTREE_PATH" || fail "worktree removal failed"
    [ ! -e "$WORKTREE_PATH" ] || fail "worktree path remains after removal"
    rm -f "$STATE_FILE" || fail "cannot remove workspace state"
    if [ "$ACTION" = cleanup-if-complete ]; then emit_cleanup removed; fi;;
esac
