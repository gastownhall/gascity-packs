# Gate Python dependency failure

Baseline 004 self-marked requirements generation complete three times. The
controller rejected each attempt with `PyYAML is required to parse build
artifacts`. Direct worker checks passed because they used the experiment venv.

Gas City 1.4.2 `internal/convergence/condition.go` builds a restricted PATH from
the directories containing bd, gc, dolt and jq, plus system defaults. It does
not retain the experiment virtualenv directory or PYTHONPATH. Its gate selected
Homebrew Python, where PyYAML was absent. No version incompatibility or database
migration caused this failure.

[result.json](result.json) drives the actual SDK `convergence.RunCondition`:
original environment fails importing yaml, while a private tool directory with
a bd symlink and Python wrapper passes. The harness now installs those wrappers
inside each disposable runtime and checks yaml, jsonschema and pytest under the
restricted environment before launching Claude. Python's venv path must remain
unresolved to preserve its site-packages. No global Python installation changes.

[harness-sdk-verification.json](harness-sdk-verification.json) repeats the real
SDK check using the actual harness helper, passing both the fast preflight and
RunCondition. [condition-probe.go](condition-probe.go) is the real SDK probe source;
it was built in the matching local Gas City source tree with ICU include/link
flags and the recorded binary SHA-256. The probe process exits zero even for a
failed condition; inspect its `Outcome` and `ExitCode` fields.

Two regressions cover venv identity after PATH restriction and final report plus
cleanup on KeyboardInterrupt. Both failed before the change. An initial green
attempt exposed a macOS-specific test fixture path (`/bin/true`); replacing it
with executable discovery yielded [17 passed](harness-green.log). The first
green failure and red log are retained. Aborted earlier runs have explicitly
reconstructed reports and unknown collector error counts; future interrupted
runs retain the normal terminal report.

This validates the dependency fix, not end-to-end workflow success. Baseline
004's requirements also drifted from the original slugify task; that independent
quality failure is retained and has not been changed in the next baseline.

## Live workflow verification

Baseline 005 reached the actual requirements gate. The controller imported
PyYAML successfully and rejected a missing Markdown coverage table, then
started an ordinary repair attempt. See
[live gate result](../../build-baseline-005/run-001-baseline/live-gate-validation.json).
This verifies the environment fix beyond the SDK probe; it does not certify
artifact quality or a completed build.
