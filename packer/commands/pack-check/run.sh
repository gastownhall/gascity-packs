#!/usr/bin/env bash
set -euo pipefail

PACK="${1:-}"
AGENT="${2:-}"
FORMULA="${3:-}"
FOCUSED=""

if [[ -z "$PACK" ]]; then
  echo "usage: gc packer pack-check <pack> [agent|--focused] [formula]" >&2
  exit 2
fi

if [[ "$AGENT" == "--focused" ]]; then
  FOCUSED="1"
  AGENT=""
  FORMULA=""
fi

assert_file_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if [[ ! -f "$file" ]]; then
    echo "pack-check: missing $label: $file" >&2
    exit 1
  fi

  if ! grep -Eq -- "$pattern" "$file"; then
    echo "pack-check: $label did not match: $pattern" >&2
    exit 1
  fi
}

check_lazyjj_pack() {
  local prompt="$PACK/agents/tasksmith/prompt.template.md"
  local formula="$PACK/formulas/mol-polecat-lazyjj-work.toml"
  local readme="$PACK/README.md"
  local workspace_setup="jjw/assets/scripts/workspace-setup.sh"

  assert_file_contains "$prompt" "route normal pack work through.*mol-polecat-lazyjj-work" "tasksmith default formula guidance"
  assert_file_contains "$prompt" "tutorial formulas only when" "tasksmith tutorial formula boundary"
  assert_file_contains "$prompt" "LAZYJJ_WORK_TITLE" "tasksmith workspace title seed"
  assert_file_contains "$prompt" "--description-file" "tasksmith description-file seed"

  assert_file_contains "$formula" "--set-metadata lazyjj_workspace=" "workspace metadata recording"
  assert_file_contains "$formula" "--set-metadata lazyjj_workspace_dir=" "workspace directory metadata recording"
  assert_file_contains "$formula" "write_bead_change_description" "bead-derived change description"
  assert_file_contains "$formula" "jj describe --stdin" "workspace change seeding"

  assert_file_contains "$workspace_setup" "--bead\\|--title\\|--description\\|--description-file" "workspace setup metadata arguments"
  sh -n "$workspace_setup"

  assert_file_contains "$readme" "packer/commands/pack-check/run.sh gastown-lazyjj --focused" "LazyJJ focused check documentation"
  echo "pack-check: gastown-lazyjj focused checks ok"
}

if [[ -n "$FOCUSED" ]]; then
  if [[ "$PACK" != "gastown-lazyjj" && "$PACK" != */gastown-lazyjj ]]; then
    echo "pack-check: --focused is only defined for gastown-lazyjj" >&2
    exit 2
  fi
  check_lazyjj_pack
  echo "pack-check: ok"
  exit 0
fi

gc lint "$PACK"

if [[ -n "$AGENT" ]]; then
  gc prime "$AGENT" --strict >/dev/null
fi

if [[ -n "$FORMULA" ]]; then
  gc formula show "$FORMULA" >/dev/null
fi

if [[ "$PACK" == "gastown-lazyjj" || "$PACK" == */gastown-lazyjj ]]; then
  check_lazyjj_pack
fi

echo "pack-check: ok"
