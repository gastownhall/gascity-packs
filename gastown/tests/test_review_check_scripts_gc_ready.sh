#!/usr/bin/env bash
# The review check scripts must read the molecule through gc on a split city.
#
# On a split-store city a molecule's steps live in the class binding.
# `gc bd list --all` reads only the work store and answers [], so a gate that
# listed members that way never saw its verdict. The scripts now read the check
# bead with `gc bd show` and the members with a `gc ready` union over every
# status. The stub below is a split city: the verdict steps are only visible to
# `gc ready`, the bead CLI is absent from PATH, and `gc bd list` answers [].
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CHECKS="$ROOT/gastown/assets/scripts/checks"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

write_gc_stub() {
    local bin="$1"
    mkdir -p "$bin"
    cat >"$bin/gc" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$GC_STUB_LOG"
if [ "${1:-}" = "bd" ]; then
    case "${2:-}" in
        show) printf '%s\n' '{"metadata":{"gc.attempt":"1","gc.root_bead_id":"root-1"}}' ;;
        list) printf '[]\n' ;;
        *) echo "unexpected gc bd $*" >&2; exit 1 ;;
    esac
    exit 0
fi
if [ "${1:-}" = "ready" ]; then
    status=""
    prev=""
    for arg in "$@"; do
        [ "$prev" = "--status" ] && status="$arg"
        prev="$arg"
    done
    case " $* " in *" gc.root_bead_id=root-1 "*) ;; *) echo "unexpected gc ready $*" >&2; exit 1 ;; esac
    if [ -n "${GC_STUB_FAIL_STATUS:-}" ] && [ "$status" = "$GC_STUB_FAIL_STATUS" ]; then
        echo "gc ready: store unavailable" >&2
        exit 1
    fi
    if [ "$status" = "closed" ]; then
        cat "$GC_STUB_MEMBERS"
    else
        printf '[]\n'
    fi
    exit 0
fi
echo "unexpected gc $*" >&2
exit 1
SH
    chmod +x "$bin/gc"
}

run_case() {
    local script="$1" step_ref="$2" key="$3" approved="$4"
    local tmp out rc
    tmp=$(mktemp -d)
    write_gc_stub "$tmp/bin"
    cat >"$tmp/members.json" <<JSON
[
  {"id": "s-old", "updated_at": "2026-01-01T00:00:00Z",
   "metadata": {"gc.step_ref": "$step_ref", "gc.root_bead_id": "root-1", "$key": "iterate"}},
  {"id": "s-new", "updated_at": "2026-01-01T00:00:01Z",
   "metadata": {"gc.step_ref": "$step_ref", "gc.root_bead_id": "root-1", "$key": "done"}}
]
JSON
    # A PATH holding only the stub and the base tools: no bd binary at all.
    local path="$tmp/bin:/usr/bin:/bin"

    rc=0
    out=$(env -i PATH="$path" HOME="$tmp" GC_BEAD_ID=check-1 GC_STUB_LOG="$tmp/log" \
        GC_STUB_MEMBERS="$tmp/members.json" bash "$CHECKS/$script" 2>&1) || rc=$?
    [ "$rc" -eq 0 ] || fail "$script: exit $rc, want 0 (newest verdict done): $out"
    case "$out" in *"$approved"*) ;; *) fail "$script: output $out, want $approved" ;; esac
    grep -q -- '--status open' "$tmp/log" || fail "$script: no open leg in the gc ready union"
    grep -q -- '--status in_progress' "$tmp/log" || fail "$script: no in_progress leg"
    grep -q -- '--status blocked' "$tmp/log" || fail "$script: no blocked leg"
    grep -q -- '--status closed' "$tmp/log" || fail "$script: no closed leg"
    if grep -q '^bd list' "$tmp/log"; then
        fail "$script: still lists members with gc bd list"
    fi

    # One failed leg must not read as an empty member set.
    : >"$tmp/log"
    rc=0
    out=$(env -i PATH="$path" HOME="$tmp" GC_BEAD_ID=check-1 GC_STUB_LOG="$tmp/log" \
        GC_STUB_MEMBERS="$tmp/members.json" GC_STUB_FAIL_STATUS=blocked \
        bash "$CHECKS/$script" 2>&1) || rc=$?
    [ "$rc" -eq 2 ] || fail "$script: exit $rc with a failed gc ready leg, want 2: $out"
    case "$out" in *"unable to determine"*) ;; *) fail "$script: output $out, want the outage message" ;; esac

    rm -rf "$tmp"
}

command -v jq >/dev/null 2>&1 || { echo "SKIP: jq not installed"; exit 0; }

run_case design-review-approved.sh \
    "mol-personal-work-v2.design-review-loop.run.1.apply-design-changes" \
    design_review.verdict "Design review approved"
run_case code-review-approved.sh \
    "mol-personal-work-v2.code-review-loop.run.1.apply-code-fixes" \
    code_review.verdict "Code review approved"
run_case adopt-pr-review-approved.sh \
    "mol-adopt-pr-v2.review-loop.run.1.apply-fixes" \
    review.verdict "Review approved"

echo "PASS: review check scripts read molecules through gc ready"
