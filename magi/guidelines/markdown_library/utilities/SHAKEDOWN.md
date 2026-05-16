# Shakedown — Integration Validation

### Definition

A shakedown is the **first controlled execution of a `.utilities/` script against real inputs in an isolated scratch directory** after any change that touches the script's integration surface.

Shakedown validates that the utility operates correctly across the three layers (Foundation, Domain, Integration) when composed with **real sourced helpers, real cross-platform branches, and real logging targets**.

| Phase | Question |
|:------|:---------|
| Preflight | Static inspection — script parses, helpers exist, env vars present |
| **Shakedown** | **Does the integrated path actually execute correctly via a real round-trip?** |
| Testing | Behavioral correctness across the input space — comprehensive test suite |

**Shakedown is not a test suite** — it is a small set of representative cases with known-good outputs. **Shakedown is not preflight** — preflight is static inspection, shakedown is real execution.

### Mandatory Exposure

**Every utility script that mutates state** (writes files, mutates services, installs dependencies, modifies configuration) MUST expose shakedown through one of two mechanisms:

| Mechanism | Form |
|:----------|:-----|
| `--shakedown` mode | Built into the utility itself; runs the core path against known-good inputs in an isolated scratch directory, validates outputs, exits 0 on pass / 1 on fail |
| Companion `shakedown.sh` | Placed in the same directory as the utility; invokes the utility against known-good fixtures under a project-local scratch directory and validates outputs |

**Utility scripts that mutate state without either mechanism are prohibited.**

### Idempotency Inheritance

Shakedown inherits the utility's idempotency guarantee:

- A second shakedown invocation MUST produce identical pass results.
- A second invocation MUST NOT trip any self-healing correction.
- A second invocation MUST NOT write any additional side effects.
- Shakedown cleans the scratch directory at the start of each run so the validated baseline is reproducible.

### Mandatory Triggers

Shakedown is mandatory after any change to:

- The sourced helper chain (`.common/` functions used by the utility).
- Cross-platform branches (macOS vs Linux vs WSL code paths).
- The utility's contract with the directory layout (`.utilities/.common/`, `.utilities/.backend/`, etc.).
- Environment variable consumption from `project or pack .env` or project `.env` files.
- External command invocations (`brew`, `apt-get`, `docker`, `git`, `sshpass`, `rsync`).
- Any change to the utility's file mutations, service mutations, or package installations.
- Migration of a script between layers (Integration → Domain, Domain → Foundation).

### Non-Triggers

- Color code or log message rewording.
- Comment-only edits or `--help` text updates.
- Version bumps in version-detection strings that do not change detection logic.
- Read-only utilities that inspect state without mutating it.

### Validation Categories

Shakedown must exercise each of the **six integration surfaces specific to `.utilities/` scripts**:

1. **Data flow through sourced helpers** — fixtures pass through `.common/` functions (`say`, `log`, `die`, `have_cmd`) and emerge in the expected structural form.
2. **Cross-platform subsystem communication** — the OS-detection branch selected for shakedown matches the host (macOS vs Linux vs WSL); platform-specific external commands resolve and execute.
3. **Resource availability** — the scratch directory is created, locked if the utility uses lock files, and cleaned up on `EXIT` trap **without touching anything outside the scratch root**.
4. **Configuration propagation** — environment variables loaded from `project or pack .env` and project `.env` files reach the subshells and subprocesses the utility invokes.
5. **Error handling paths** — a deliberately failing fixture triggers `die()` with the expected context, `set -Eeuo pipefail` aborts the script at the expected point, and the `EXIT` trap cleans scratch state.
6. **Side effect correctness** — every file mutation lands under the scratch root (**never `~`, never `/tmp`, never the consuming project**), and a second invocation produces the same result (idempotency inheritance).

### Execution Principles

- **Known-good fixtures** stored alongside the utility (or in a shared `.utilities/_fixtures/` directory) with expected outputs committed.
- **Scratch directory under the utility's own directory** (e.g., `.utilities/.backend/.shakedown/`) — **never `/tmp`, never `$TMPDIR`, never `/var/folders`**.
- **Simplest end-to-end invocation first**, complexity added incrementally by passing additional representative fixtures.
- **Verbose logging** captured to `.shakedown/execution.log` via the utility's existing logging helpers.
- **Do not optimize during shakedown** — log performance anomalies to the issue list and move on.

### Portability Contract

Shakedown must honor the cross-project compatibility contract — the shakedown mode must succeed when the utility is invoked **from any consuming project**, not just the project the utility was developed in.

- Shakedown fixtures must not reference hardcoded project paths, hardcoded IPs, or credentials.
- All project-specific values are read from environment variables at shakedown time, **exactly as the utility reads them at runtime**.

### Self-Healing Integration

Shakedown validates that the utility's **self-healing behavior actually works** against real conditions. A self-healing utility that passes preflight and fails shakedown has self-healing that is aspirational, not functional. Every self-healing correction path (missing directory created, missing dependency installed, invalid permission adjusted) must be exercised at least once across the shakedown's representative fixtures.

### Reference `--shakedown` Mode

```bash
run_shakedown() {
    local scratch="${SCRIPT_DIR}/.shakedown"
    rm -rf "${scratch}"
    mkdir -p "${scratch}" || die "Cannot create shakedown scratch: ${scratch}"
    trap 'rm -rf "${scratch}"' EXIT
    local failures=0
    local fixture="${SCRIPT_DIR}/_fixtures/known-good.txt"
    [[ -f "${fixture}" ]] || die "Missing shakedown fixture: ${fixture}"

    # 1. Data flow through sourced helpers
    have_cmd jq || { warn "Shakedown: jq missing — category inconclusive"; ((failures++)); }

    # 2. Run the utility against the fixture, output to scratch
    if ! process_fixture "${fixture}" "${scratch}/out.txt"; then
        echo -e "${RED}✗${NC} Shakedown: process_fixture failed"
        ((failures++))
    fi

    # 3. Validate output matches expected baseline
    if ! diff -q "${SCRIPT_DIR}/_fixtures/known-good.out" "${scratch}/out.txt" >/dev/null; then
        echo -e "${RED}✗${NC} Shakedown: output diverged from baseline"
        ((failures++))
    fi

    # 4. Idempotency inheritance — second run must match first
    cp "${scratch}/out.txt" "${scratch}/out.first.txt"
    process_fixture "${fixture}" "${scratch}/out.txt"
    if ! diff -q "${scratch}/out.first.txt" "${scratch}/out.txt" >/dev/null; then
        echo -e "${RED}✗${NC} Shakedown: second run diverged — idempotency violated"
        ((failures++))
    fi

    # 5. Environment snapshot artifact
    {
        echo "bash=${BASH_VERSION}"
        echo "os=$(uname -s)"
        echo "utility=${SCRIPT_NAME:-${0##*/}}"
    } > "${scratch}/environment.snapshot"

    if (( failures == 0 )); then
        echo -e "${GREEN}✓${NC} Shakedown: PASS"
        return 0
    fi
    echo -e "${RED}✗${NC} Shakedown: FAIL-BLOCKING (${failures} categories failed)"
    return 1
}

# In argument parser:
#   --shakedown) run_shakedown; exit $?;;
```

### Reference Companion `shakedown.sh`

```bash
#!/usr/bin/env bash
# shakedown.sh — companion shakedown harness for ./the_utility.sh
set -Eeuo pipefail
umask 022
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../.common/colors.sh"
source "${SCRIPT_DIR}/../.common/utils.sh"
SCRATCH="${SCRIPT_DIR}/.shakedown"
rm -rf "${SCRATCH}"
mkdir -p "${SCRATCH}"
trap 'rm -rf "${SCRATCH}"' EXIT
"${SCRIPT_DIR}/the_utility.sh" --input "${SCRIPT_DIR}/_fixtures/known-good.txt" --output "${SCRATCH}/out.txt" \
    || { echo -e "${RED}✗${NC} shakedown: utility failed"; exit 1; }
diff -q "${SCRIPT_DIR}/_fixtures/known-good.out" "${SCRATCH}/out.txt" >/dev/null \
    || { echo -e "${RED}✗${NC} shakedown: output diverged"; exit 1; }
echo -e "${GREEN}✓${NC} shakedown: PASS"
```

### Result Classification

| Outcome | Exit code | Trigger |
|:--------|:---------:|:--------|
| `pass` | 0 | All six validation categories succeeded |
| `fail-blocking` | 1 | At least one category failed in a way that blocks trusting the utility — fix the utility, re-run shakedown from start |
| `fail-nonblocking` | 0 (with warning) | Non-critical anomaly observed (slower than last shakedown) — logged to issue list, proceed with caution |
| `inconclusive` | 2 | Environment limitation prevented validation (e.g., `jq` not installed) — remediate the environment and re-run |

### Required Artifacts

Every shakedown run produces four artifacts inside the utility's `.shakedown/` scratch directory:

- `execution.log` — full timestamped output of the shakedown run, written through the utility's logging helpers.
- `result.summary` — pass/fail classification per validation category.
- `issue.list` — every anomaly observed, classified blocking/non-blocking/deferred.
- `environment.snapshot` — bash version, OS, utility version, sourced helper versions, relevant env vars.

### Anti-Patterns

- Writing shakedown artifacts to `/tmp`, `/var/folders`, `$TMPDIR`, `~/.cache`, or any path outside the utility's own directory.
- Committing a `--shakedown` mode that calls **mocked** versions of external commands instead of the real ones.
- Skipping shakedown after "just a small sourced helper change".
- Expanding shakedown into a comprehensive test suite with dozens of cases — **shakedown is a small set of representative fixtures**.
- Running shakedown against a hardcoded project path instead of honoring the cross-project compatibility contract.
- Failing to clean the scratch directory at the start of each run — **shakedown must be reproducible**.
- Declaring shakedown PASS without producing all four required artifacts.

---
[Back to Overview](./OVERVIEW.md)
