#!/usr/bin/env bash
# Surface durable polecat block contracts without attempting recovery.
#
# The blocked source/step rows are the recovery authority. This command only
# reads that authority, sends an at-least-once Mayor notification, and records
# an exact notification receipt. It never changes status, ownership, workflow,
# artifact, or routing state.

set -u -o pipefail

EXIT_USAGE=2
EXIT_INDETERMINATE=75

ACTION=${1:-}
if [[ -n "$ACTION" ]]; then
    shift
fi
if [[ "$ACTION" != "surface" || $# -ne 0 ]]; then
    echo "Usage: gc gastown polecat-blocks surface" >&2
    exit "$EXIT_USAGE"
fi

[[ -n "${GC_CITY_PATH:-}" && -n "${GC_RIG:-}" &&
   -n "${GC_RIG_ROOT:-}" ]] || {
    echo "polecat-blocks: GC_CITY_PATH, GC_RIG, and GC_RIG_ROOT are required" >&2
    exit "$EXIT_INDETERMINATE"
}
case "$GC_RIG" in
    ""|"."|".."|*[!A-Za-z0-9._-]*)
        echo "polecat-blocks: the runtime rig name is unsafe" >&2
        exit "$EXIT_INDETERMINATE"
        ;;
esac
RUNTIME_RIG=$GC_RIG
CITY_ROOT=$(CDPATH= cd -- "$GC_CITY_PATH" 2>/dev/null && pwd -P) || {
    echo "polecat-blocks: could not canonicalize the city root" >&2
    exit "$EXIT_INDETERMINATE"
}
RIG_ROOT=$(CDPATH= cd -- "$GC_RIG_ROOT" 2>/dev/null && pwd -P) || {
    echo "polecat-blocks: could not canonicalize the rig root" >&2
    exit "$EXIT_INDETERMINATE"
}

GC_CMD=${GC_BIN:-}
if [[ -z "$GC_CMD" ]]; then
    GC_CMD=$(command -v gc 2>/dev/null || true)
fi
if [[ -z "$GC_CMD" || ! -x "$GC_CMD" ]]; then
    echo "polecat-blocks: the invoking gc executable is unavailable" >&2
    exit "$EXIT_INDETERMINATE"
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "polecat-blocks: jq is required" >&2
    exit "$EXIT_INDETERMINATE"
fi

run_gc_bd() {
    local command=("$GC_CMD" "bd" "--rig" "$RUNTIME_RIG")
    GC_NO_API=1 \
    GC_CITY="$CITY_ROOT" \
    GC_CITY_PATH="$CITY_ROOT" \
    GC_RIG="$RUNTIME_RIG" \
    GC_RIG_ROOT="$RIG_ROOT" \
    GC_STORE_ROOT="$RIG_ROOT" \
    GC_STORE_SCOPE=rig \
        "${command[@]}" "$@"
}

run_gc_convoy() {
    local command=("$GC_CMD" "convoy")
    GC_NO_API=1 \
    GC_CITY="$CITY_ROOT" \
    GC_CITY_PATH="$CITY_ROOT" \
    GC_RIG="$RUNTIME_RIG" \
    GC_RIG_ROOT="$RIG_ROOT" \
    GC_STORE_ROOT="$RIG_ROOT" \
    GC_STORE_SCOPE=rig \
        "${command[@]}" "$@"
}

run_gc_mail() {
    local command=("$GC_CMD" "mail")
    GC_NO_API=1 \
    GC_CITY="$CITY_ROOT" \
    GC_CITY_PATH="$CITY_ROOT" \
    GC_RIG="$RUNTIME_RIG" \
    GC_RIG_ROOT="$RIG_ROOT" \
    GC_STORE_ROOT="$CITY_ROOT" \
    GC_STORE_SCOPE=city \
        "${command[@]}" "$@"
}

safe_atom() {
    local value=$1
    [[ -n "$value" && ${#value} -le 256 &&
       "$value" != *[!A-Za-z0-9._:-]* ]]
}

sha256_stream() {
    local output digest
    if command -v sha256sum >/dev/null 2>&1; then
        output=$(sha256sum) || return 1
        digest=${output%% *}
    elif command -v shasum >/dev/null 2>&1; then
        output=$(shasum -a 256) || return 1
        digest=${output%% *}
    elif command -v openssl >/dev/null 2>&1; then
        output=$(openssl dgst -sha256) || return 1
        digest=${output##* }
    else
        return 1
    fi
    digest=$(printf '%s' "$digest" | LC_ALL=C tr 'A-F' 'a-f') || return 1
    [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || return 1
    printf 'sha256:%s' "$digest"
}

bounded_text() {
    local value=$1 max_bytes=$2 fallback=$3
    printf '%s' "$value" | jq -Rrs \
        --argjson max "$max_bytes" --arg fallback "$fallback" '
        (explode |
          map(if . >= 32 and . <= 126 then . else 63 end) |
          implode |
          gsub(" +"; " ")) as $safe |
        (if ($safe | length) == 0 then $fallback else $safe end) |
        if length > $max
        then .[0:($max - 3)] + "..."
        else .
        end'
}

row_fingerprint() {
    local row_json=$1
    printf '%s' "$row_json" | jq -ceS '
        {
          id: .id,
          status: .status,
          assignee: (.assignee // ""),
          block: {
            source_reason: (.metadata.blocked_reason // null),
            step_reason: (.metadata["gc.blocked_reason"] // null),
            version: (
              if .metadata["gc.polecat_block_version"] == null
              then null
              else (.metadata["gc.polecat_block_version"] | tostring)
              end
            ),
            code: (.metadata["gc.polecat_block_code"] // null),
            source_step_ref: (
              .metadata["gc.polecat_block_step_ref"] // null
            ),
            source_step_id: (
              .metadata["gc.polecat_block_step_id"] // null
            ),
            source_root: (.metadata["gc.polecat_block_root"] // null),
            source_convoy: (
              .metadata["gc.polecat_block_convoy"] // null
            ),
            source_previous_route: (
              .metadata["gc.polecat_block_previous_route"] // null
            ),
            step_source: (
              .metadata["gc.polecat_block_source"] // null
            ),
            step_ref: (.metadata["gc.step_ref"] // null),
            step_root: (.metadata["gc.root_bead_id"] // null),
            route: (.metadata["gc.routed_to"] // null)
          }
        }' 2>/dev/null | sha256_stream
}

group_signature() {
    local group_json=$1 classification=$2 diagnostic=$3
    printf '%s' "$group_json" | jq -ceS \
        --arg classification "$classification" \
        --arg diagnostic "$diagnostic" '
        {
          schema: "gascity-polecat-block-alert-v1",
          classification: $classification,
          diagnostic: $diagnostic,
          rows: [
            .[] | {
              id: .id,
              status: .status,
              assignee: (.assignee // ""),
              block: {
                source_reason: (.metadata.blocked_reason // null),
                step_reason: (.metadata["gc.blocked_reason"] // null),
                version: (
                  if .metadata["gc.polecat_block_version"] == null
                  then null
                  else (.metadata["gc.polecat_block_version"] | tostring)
                  end
                ),
                code: (.metadata["gc.polecat_block_code"] // null),
                source_step_ref: (
                  .metadata["gc.polecat_block_step_ref"] // null
                ),
                source_step_id: (
                  .metadata["gc.polecat_block_step_id"] // null
                ),
                source_root: (
                  .metadata["gc.polecat_block_root"] // null
                ),
                source_convoy: (
                  .metadata["gc.polecat_block_convoy"] // null
                ),
                source_previous_route: (
                  .metadata["gc.polecat_block_previous_route"] // null
                ),
                step_source: (
                  .metadata["gc.polecat_block_source"] // null
                ),
                step_ref: (.metadata["gc.step_ref"] // null),
                step_root: (.metadata["gc.root_bead_id"] // null),
                route: (.metadata["gc.routed_to"] // null)
              }
            }
          ] | sort_by(.id)
        }' 2>/dev/null | sha256_stream
}

ROWS_JSON=$(run_gc_bd list --all \
    --metadata-field gc.polecat_block_version=1 \
    --json --limit=0 2>/dev/null) || {
    echo "polecat-blocks: could not scan durable v1 block markers" >&2
    exit "$EXIT_INDETERMINATE"
}
printf '%s' "$ROWS_JSON" | jq -e '
    type == "array" and
    all(.[];
      type == "object" and
      (.id | type) == "string" and (.id | length) > 0 and
      (.status | type) == "string" and (.status | length) > 0 and
      ((.assignee // "") | type) == "string" and
      ((.metadata // {}) | type) == "object" and
      (.metadata["gc.polecat_block_version"] != null) and
      ((.metadata["gc.polecat_block_version"] | tostring) == "1"))' \
    >/dev/null 2>&1 || {
    echo "polecat-blocks: the v1 block scan returned a malformed row set" >&2
    exit "$EXIT_INDETERMINATE"
}

SCANNED=$(printf '%s' "$ROWS_JSON" | jq -er 'length') || {
    echo "polecat-blocks: could not count v1 block rows" >&2
    exit "$EXIT_INDETERMINATE"
}
GROUPS_JSON=$(printf '%s' "$ROWS_JSON" | jq -ce '
    def m: (.metadata // {});
    [
      map(. + {
        "__block_source_key": (
          if ((m["gc.polecat_block_step_id"] | type) == "string" or
              (m["gc.polecat_block_step_ref"] | type) == "string" or
              (m["gc.polecat_block_root"] | type) == "string")
          then .id
          elif ((m["gc.polecat_block_source"] | type) == "string" and
                (m["gc.polecat_block_source"] | length) > 0)
          then m["gc.polecat_block_source"]
          else .id
          end
        )
      })
      | sort_by(."__block_source_key", .id)
      | group_by(."__block_source_key")[]
      | map(del(."__block_source_key"))
    ]') || {
    echo "polecat-blocks: could not group durable v1 block markers" >&2
    exit "$EXIT_INDETERMINATE"
}
if ! printf '%s' "$GROUPS_JSON" | jq -e --argjson scanned "$SCANNED" '
    type == "array" and
    all(.[]; type == "array" and length > 0) and
    ([.[][]] | length) == $scanned' >/dev/null 2>&1; then
    echo "polecat-blocks: grouped v1 block rows did not preserve the scan" >&2
    exit "$EXIT_INDETERMINATE"
fi
GROUP_TOTAL=$(printf '%s' "$GROUPS_JSON" | jq -er 'length') || {
    echo "polecat-blocks: could not count durable v1 block groups" >&2
    exit "$EXIT_INDETERMINATE"
}

VALID_COUNT=0
PARTIAL_COUNT=0
MALFORMED_COUNT=0
NOTIFIED_COUNT=0
DEDUPED_COUNT=0
FAILURE_COUNT=0

for ((GROUP_INDEX = 0; GROUP_INDEX < GROUP_TOTAL; GROUP_INDEX++)); do
    GROUP_JSON=$(printf '%s' "$GROUPS_JSON" |
        jq -cer --argjson index "$GROUP_INDEX" '.[$index]') || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }

    GROUP_COUNT=$(printf '%s' "$GROUP_JSON" | jq -er 'length') || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    CLASSIFICATION=malformed
    DIAGNOSTIC=pair_contract_mismatch
    PAIR_JSON=""

    PAIR_JSON=$(printf '%s' "$GROUP_JSON" | jq -cer '
        def m: (.metadata // {});
        [.[] |
          select(
            (m["gc.polecat_block_step_id"] | type) == "string" or
            (m["gc.polecat_block_step_ref"] | type) == "string" or
            (m["gc.polecat_block_root"] | type) == "string"
          )] as $sources |
        [.[] |
          select((m["gc.polecat_block_source"] | type) == "string")] as $steps |
        if ($sources | length) == 1 and ($steps | length) == 1 and
           length == 2
        then $sources[0] as $s | $steps[0] as $t |
          if $s.status == "blocked" and (($s.assignee // "") == "") and
             $s.metadata["gc.routed_to"] == "human" and
             ($s.metadata.blocked_reason | type) == "string" and
             ($s.metadata.blocked_reason | length) > 0 and
             ($s.metadata.blocked_reason | length) <= 2048 and
             ($s.metadata.blocked_reason | explode |
              all(.[]; . >= 32 and . != 127)) and
             ($s.metadata["gc.polecat_block_code"] | type) == "string" and
             ($s.metadata["gc.polecat_block_code"] |
              test("^[A-Za-z0-9._:-]{1,128}$")) and
             (($s.metadata["gc.polecat_block_version"] | tostring) == "1") and
             ($s.metadata["gc.polecat_block_step_ref"] | type) == "string" and
             ($s.metadata["gc.polecat_block_step_ref"] | length) > 0 and
             ($s.metadata["gc.polecat_block_step_id"] | type) == "string" and
             ($s.metadata["gc.polecat_block_step_id"] | length) > 0 and
             ($s.metadata["gc.polecat_block_root"] | type) == "string" and
             ($s.metadata["gc.polecat_block_root"] | length) > 0 and
             ($s.metadata["gc.polecat_block_convoy"] | type) == "string" and
             ($s.metadata["gc.polecat_block_convoy"] | length) > 0 and
             ($s.metadata["gc.polecat_block_previous_route"] | type) ==
               "string" and
             ($s.metadata["gc.polecat_block_previous_route"] | length) <=
               512 and
             (($s.metadata["gc.polecat_block_previous_route"] |
               contains("\n")) | not) and
             (($s.metadata["gc.polecat_block_previous_route"] |
               contains("\r")) | not) and
             (($s.metadata["gc.polecat_block_previous_route"] |
               contains("\t")) | not) and
             $t.id == $s.metadata["gc.polecat_block_step_id"] and
             $t.status == "blocked" and
             (($t.assignee // "") | type) == "string" and
             (($t.assignee // "") | length) > 0 and
             (($t.metadata // {}) | type) == "object" and
             $t.metadata["gc.step_ref"] ==
               $s.metadata["gc.polecat_block_step_ref"] and
             $t.metadata["gc.root_bead_id"] ==
               $s.metadata["gc.polecat_block_root"] and
             $t.metadata["gc.blocked_reason"] ==
               $s.metadata.blocked_reason and
             $t.metadata["gc.polecat_block_code"] ==
               $s.metadata["gc.polecat_block_code"] and
             (($t.metadata["gc.polecat_block_version"] | tostring) == "1") and
             $t.metadata["gc.polecat_block_source"] == $s.id and
             $t.metadata["gc.polecat_block_convoy"] ==
               $s.metadata["gc.polecat_block_convoy"] and
             (((($t.metadata // {}) |
                has("gc.outcome")) | not) or
              $t.metadata["gc.outcome"] == "")
          then {
            source: $s.id,
            step: $t.id,
            owner: $t.assignee,
            step_ref: $s.metadata["gc.polecat_block_step_ref"],
            root: $s.metadata["gc.polecat_block_root"],
            convoy: $s.metadata["gc.polecat_block_convoy"],
            code: $s.metadata["gc.polecat_block_code"],
            reason: $s.metadata.blocked_reason
          }
          else error("source/step block contract mismatch")
          end
        else error("expected exactly one source and one step")
        end' 2>/dev/null) || PAIR_JSON=""

    if [[ -n "$PAIR_JSON" ]]; then
        CLASSIFICATION=valid
        DIAGNOSTIC=valid
        ROOT_ID=$(printf '%s' "$PAIR_JSON" | jq -er '.root')
        CONVOY_ID=$(printf '%s' "$PAIR_JSON" | jq -er '.convoy')
        SOURCE_ID=$(printf '%s' "$PAIR_JSON" | jq -er '.source')
        if ! safe_atom "$ROOT_ID" || ! safe_atom "$CONVOY_ID" ||
           ! safe_atom "$SOURCE_ID"; then
            CLASSIFICATION=malformed
            DIAGNOSTIC=unsafe_pair_identity
        else
            ROOT_JSON=$(run_gc_bd show "$ROOT_ID" --json 2>/dev/null)
            ROOT_CODE=$?
            if [[ "$ROOT_CODE" -ne 0 ]]; then
                CLASSIFICATION=malformed
                DIAGNOSTIC=root_unreadable
            elif ! printf '%s' "$ROOT_JSON" | jq -e \
                --arg id "$ROOT_ID" --arg convoy "$CONVOY_ID" \
                --arg rig "$RUNTIME_RIG" '
                type == "array" and length == 1 and .[0].id == $id and
                .[0].status == "in_progress" and
                ((.[0].metadata // {}) | type) == "object" and
                .[0].metadata["gc.kind"] == "workflow" and
                .[0].metadata["gc.formula_contract"] == "graph.v2" and
                (((.[0].metadata | has("gc.formula_name")) | not) or
                 .[0].metadata["gc.formula_name"] == "mol-polecat-work") and
                .[0].metadata["gc.var.rig_name"] == $rig and
                .[0].metadata["gc.input_convoy_id"] == $convoy and
                (((.[0].metadata | has("gc.outcome")) | not) or
                 .[0].metadata["gc.outcome"] == "")' \
                >/dev/null 2>&1; then
                CLASSIFICATION=malformed
                DIAGNOSTIC=root_contract_mismatch
            else
                CONVOY_JSON=$(run_gc_convoy status "$CONVOY_ID" \
                    --json 2>/dev/null)
                CONVOY_CODE=$?
                if [[ "$CONVOY_CODE" -ne 0 ]]; then
                    CLASSIFICATION=malformed
                    DIAGNOSTIC=convoy_unreadable
                elif ! printf '%s' "$CONVOY_JSON" | jq -e \
                    --arg convoy "$CONVOY_ID" --arg source "$SOURCE_ID" '
                    type == "object" and .schema_version == "1" and
                    (.convoy | type) == "object" and
                    .convoy.id == $convoy and
                    (.children | type) == "array" and
                    (.children | length) == 1 and
                    (.children[0].id | type) == "string" and
                    .children[0].id == $source' >/dev/null 2>&1; then
                    CLASSIFICATION=malformed
                    DIAGNOSTIC=convoy_contract_mismatch
                fi
            fi
        fi
    elif [[ "$GROUP_COUNT" -eq 1 ]]; then
        CLASSIFICATION=partial
        DIAGNOSTIC=unpaired_v1_marker
    fi

    case "$CLASSIFICATION" in
        valid) VALID_COUNT=$((VALID_COUNT + 1)) ;;
        partial) PARTIAL_COUNT=$((PARTIAL_COUNT + 1)) ;;
        malformed) MALFORMED_COUNT=$((MALFORMED_COUNT + 1)) ;;
    esac

    ANCHOR_JSON=$(printf '%s' "$GROUP_JSON" | jq -cer '
        def m: (.metadata // {});
        sort_by(
          if ((m["gc.polecat_block_step_id"] | type) == "string" or
              (m["gc.polecat_block_step_ref"] | type) == "string" or
              (m["gc.polecat_block_root"] | type) == "string")
          then 0 else 1 end,
          .id
        ) | .[0]' 2>/dev/null) || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    ANCHOR_ID=$(printf '%s' "$ANCHOR_JSON" | jq -er '.id') || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    ANCHOR_STATUS=$(printf '%s' "$ANCHOR_JSON" | jq -er '.status') || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    ANCHOR_ASSIGNEE=$(printf '%s' "$ANCHOR_JSON" |
        jq -er '.assignee // ""') || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    if ! safe_atom "$ANCHOR_ID" || ! safe_atom "$ANCHOR_STATUS"; then
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    fi

    SIGNATURE=$(group_signature "$GROUP_JSON" \
        "$CLASSIFICATION" "$DIAGNOSTIC") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    if printf '%s' "$ANCHOR_JSON" | jq -e --arg signature "$SIGNATURE" '
        ((.metadata["gc.polecat_block_alert_version"] // null) | tostring) ==
          "1" and
        .metadata["gc.polecat_block_alert_signature"] == $signature' \
        >/dev/null 2>&1; then
        DEDUPED_COUNT=$((DEDUPED_COUNT + 1))
        printf 'POLECAT_BLOCK_KNOWN anchor=%s classification=%s signature=%s\n' \
            "$ANCHOR_ID" "$CLASSIFICATION" "$SIGNATURE"
        continue
    fi

    if [[ -n "$PAIR_JSON" ]]; then
        SOURCE_LABEL=$(printf '%s' "$PAIR_JSON" | jq -er '.source')
        STEP_LABEL=$(printf '%s' "$PAIR_JSON" | jq -er '.step')
        ROOT_LABEL=$(printf '%s' "$PAIR_JSON" | jq -er '.root')
        CONVOY_LABEL=$(printf '%s' "$PAIR_JSON" | jq -er '.convoy')
        CODE_LABEL=$(printf '%s' "$PAIR_JSON" | jq -er '.code')
        OWNER_LABEL=$(printf '%s' "$PAIR_JSON" | jq -er '.owner')
        REASON_LABEL=$(printf '%s' "$PAIR_JSON" | jq -er '.reason')
    else
        SOURCE_LABEL=$(printf '%s' "$GROUP_JSON" | jq -r '
            [.[] | .metadata["gc.polecat_block_source"] // empty] |
            map(select(type == "string" and length > 0)) | first // "unknown"'
            2>/dev/null || printf 'unknown')
        STEP_LABEL=$(printf '%s' "$GROUP_JSON" | jq -r '
            [.[].metadata["gc.polecat_block_step_id"]] |
            map(select(type == "string" and length > 0)) | first // "unknown"'
            2>/dev/null || printf 'unknown')
        ROOT_LABEL=$(printf '%s' "$GROUP_JSON" | jq -r '
            [.[].metadata["gc.polecat_block_root"],
             .[].metadata["gc.root_bead_id"]] |
            map(select(type == "string" and length > 0)) | first // "unknown"'
            2>/dev/null || printf 'unknown')
        CONVOY_LABEL=$(printf '%s' "$GROUP_JSON" | jq -r '
            [.[].metadata["gc.polecat_block_convoy"]] |
            map(select(type == "string" and length > 0)) | first // "unknown"'
            2>/dev/null || printf 'unknown')
        CODE_LABEL=MALFORMED
        OWNER_LABEL=$(printf '%s' "$ANCHOR_JSON" |
            jq -r '.assignee // "unknown"' 2>/dev/null || printf 'unknown')
        REASON_LABEL="Durable v1 marker rows do not form one exact block pair."
    fi
    [[ "$SOURCE_LABEL" != "unknown" ]] || SOURCE_LABEL=$ANCHOR_ID

    SOURCE_LABEL=$(bounded_text "$SOURCE_LABEL" 96 "unknown") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    STEP_LABEL=$(bounded_text "$STEP_LABEL" 96 "unknown") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    ROOT_LABEL=$(bounded_text "$ROOT_LABEL" 96 "unknown") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    CONVOY_LABEL=$(bounded_text "$CONVOY_LABEL" 96 "unknown") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    CODE_LABEL=$(bounded_text "$CODE_LABEL" 96 "MALFORMED") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    OWNER_LABEL=$(bounded_text "$OWNER_LABEL" 96 "unknown") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    REASON_LABEL=$(bounded_text "$REASON_LABEL" 512 \
        "Durable block reason is unavailable.") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    RIG_LABEL=$(bounded_text "$RUNTIME_RIG" 96 "unknown") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    ROW_IDS_RAW=$(printf '%s' "$GROUP_JSON" | jq -er '
        [.[0:8][].id] | join(",")' 2>/dev/null) || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    ROW_IDS_LABEL=$(bounded_text "$ROW_IDS_RAW" 512 "unknown") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }

    SUBJECT="POLECAT_BLOCK: $SOURCE_LABEL [$CODE_LABEL]"
    BODY=$(printf '%s\n' \
        "A durable polecat block requires attention." \
        "classification=$CLASSIFICATION diagnostic=$DIAGNOSTIC" \
        "rig=$RIG_LABEL source=$SOURCE_LABEL step=$STEP_LABEL" \
        "root=$ROOT_LABEL convoy=$CONVOY_LABEL owner=$OWNER_LABEL" \
        "code=$CODE_LABEL reason=$REASON_LABEL" \
        "signature=$SIGNATURE" \
        "row_count=$GROUP_COUNT row_ids=$ROW_IDS_LABEL" \
        "No status, ownership, workflow, artifact, or routing recovery was attempted.")

    if ! run_gc_mail send mayor/ -s "$SUBJECT" -m "$BODY" \
        >/dev/null 2>&1; then
        echo "polecat-blocks: Mayor notification failed for $ANCHOR_ID" >&2
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    fi

    CURRENT_JSON=$(run_gc_bd show "$ANCHOR_ID" --json 2>/dev/null) || {
        echo "polecat-blocks: alert sent but anchor became unreadable: $ANCHOR_ID" >&2
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    CURRENT_ROW=$(printf '%s' "$CURRENT_JSON" | jq -cer \
        --arg id "$ANCHOR_ID" --arg status "$ANCHOR_STATUS" \
        --arg assignee "$ANCHOR_ASSIGNEE" '
        if type == "array" and length == 1 and .[0].id == $id and
           .[0].status == $status and
           ((.[0].assignee // "") == $assignee) and
           ((.[0].metadata // {}) | type) == "object" and
           ((.[0].metadata["gc.polecat_block_version"] | tostring) == "1")
        then .[0]
        else error("alert anchor changed")
        end' 2>/dev/null) || {
        echo "polecat-blocks: alert sent but anchor authority changed: $ANCHOR_ID" >&2
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    EXPECTED_FINGERPRINT=$(row_fingerprint "$ANCHOR_JSON") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    CURRENT_FINGERPRINT=$(row_fingerprint "$CURRENT_ROW") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    if [[ "$CURRENT_FINGERPRINT" != "$EXPECTED_FINGERPRINT" ]]; then
        echo "polecat-blocks: alert sent but block generation changed: $ANCHOR_ID" >&2
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    fi

    if ! run_gc_bd update "$ANCHOR_ID" \
        --set-metadata gc.polecat_block_alert_version=1 \
        --set-metadata "gc.polecat_block_alert_signature=$SIGNATURE" \
        >/dev/null 2>&1; then
        echo "polecat-blocks: alert sent but receipt write failed: $ANCHOR_ID" >&2
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    fi
    VERIFY_JSON=$(run_gc_bd show "$ANCHOR_ID" --json 2>/dev/null) || {
        echo "polecat-blocks: alert receipt became unreadable: $ANCHOR_ID" >&2
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    if ! printf '%s' "$VERIFY_JSON" | jq -e \
        --arg id "$ANCHOR_ID" --arg status "$ANCHOR_STATUS" \
        --arg assignee "$ANCHOR_ASSIGNEE" --arg signature "$SIGNATURE" '
        type == "array" and length == 1 and .[0].id == $id and
        .[0].status == $status and
        ((.[0].assignee // "") == $assignee) and
        ((.[0].metadata["gc.polecat_block_version"] | tostring) == "1") and
        ((.[0].metadata["gc.polecat_block_alert_version"] | tostring) == "1") and
        .[0].metadata["gc.polecat_block_alert_signature"] == $signature' \
        >/dev/null 2>&1; then
        echo "polecat-blocks: alert receipt did not read back exactly: $ANCHOR_ID" >&2
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    fi
    VERIFIED_ROW=$(printf '%s' "$VERIFY_JSON" | jq -cer '.[0]' 2>/dev/null) || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    VERIFIED_FINGERPRINT=$(row_fingerprint "$VERIFIED_ROW") || {
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    }
    if [[ "$VERIFIED_FINGERPRINT" != "$EXPECTED_FINGERPRINT" ]]; then
        echo "polecat-blocks: receipt write changed protected authority: $ANCHOR_ID" >&2
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        continue
    fi

    NOTIFIED_COUNT=$((NOTIFIED_COUNT + 1))
    printf 'POLECAT_BLOCK_NOTIFIED anchor=%s classification=%s signature=%s\n' \
        "$ANCHOR_ID" "$CLASSIFICATION" "$SIGNATURE"
done

printf 'POLECAT_BLOCK_SURFACE rows=%s valid=%s partial=%s malformed=%s notified=%s deduped=%s failures=%s\n' \
    "$SCANNED" "$VALID_COUNT" "$PARTIAL_COUNT" "$MALFORMED_COUNT" \
    "$NOTIFIED_COUNT" "$DEDUPED_COUNT" "$FAILURE_COUNT"

[[ "$FAILURE_COUNT" -eq 0 ]] || exit "$EXIT_INDETERMINATE"
exit 0
