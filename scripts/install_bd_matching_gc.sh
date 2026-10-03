#!/usr/bin/env bash
# Install the bd that matches the beads module embedded in a gc binary.
#
# gc and bd share the beads store schema, so the inference gate refuses to run
# when they embed different beads module versions. Pinning bd separately from
# the gascity ref drifts every time gascity bumps beads, so derive it instead:
# read gc's build metadata, honour a go.mod replace, then install that release
# archive (tagged releases) or `go install` the exact module version
# (pseudo-versions and remote replacements), and verify the result.
#
# Usage: install_bd_matching_gc.sh <gc-bin> <install-bd-archive.sh>
#
# bd lands in $BD_INSTALL_BIN_DIR (default $RUNNER_TEMP/gc-matched-bd/bin).
# Under GitHub Actions that dir is added to GITHUB_PATH and GC_BEADS_BIN is
# exported, which the inference gate reads as its default --bd-bin.
set -euo pipefail

if (($# != 2)); then
  echo "usage: $0 <gc-bin> <install-bd-archive.sh>" >&2
  exit 2
fi
gc_bin="$1"
archive_installer="$2"
beads_module="github.com/steveyegge/beads"

# Print "<module> <version>" for module $2 in binary $1's build metadata,
# preferring the replacement on a following "=>" line. A local-path
# replacement has no version and prints just the path.
embedded_module() {
  go version -m "$1" | awk -v m="$2" '
    replaced_next && $1 == "=>" { mod = $2; ver = $3 }
    { replaced_next = 0 }
    ($1 == "dep" || $1 == "mod") && $2 == m { mod = $2; ver = $3; replaced_next = 1 }
    END { if (mod != "") print mod, ver }
  '
}

read -r module version < <(embedded_module "$gc_bin" "$beads_module") || true
if [[ -z "${module:-}" ]]; then
  echo "error: $gc_bin does not embed $beads_module; cannot choose a matching bd" >&2
  exit 1
fi
if [[ -z "${version:-}" ]]; then
  echo "error: $gc_bin replaces $beads_module with local path $module; no bd can be installed to match" >&2
  exit 1
fi

bin_dir="${BD_INSTALL_BIN_DIR:-${RUNNER_TEMP:-${TMPDIR:-/tmp}}/gc-matched-bd/bin}"
mkdir -p "$bin_dir"
bd_bin="$bin_dir/bd"
if [[ "$module" == "$beads_module" && "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]]; then
  echo "installing bd release $version to match $gc_bin"
  BD_INSTALL_BIN_DIR="$bin_dir" "$archive_installer" "$version"
else
  echo "installing bd from $module@$version to match $gc_bin"
  GOBIN="$bin_dir" go install "$module/cmd/bd@$version"
fi

read -r _ bd_version < <(embedded_module "$bd_bin" "$module") || true
gc_version="${version%+dirty}"
if [[ "${bd_version%+dirty}" != "$gc_version" ]]; then
  echo "error: installed $bd_bin embeds beads ${bd_version:-<none>}, but $gc_bin embeds $version" >&2
  exit 1
fi
if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "GC_BEADS_BIN=$bd_bin" >> "$GITHUB_ENV"
fi
if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "$bin_dir" >> "$GITHUB_PATH"
fi
echo "bd $bd_bin matches gc beads module $module@$version"
