# Gas City 1.4.2: macOS orphan scanner selects the shared tmux server

Confirmed during `build-baseline-003` on 2026-09-19 PDT. This is separate from
the earlier Beads forced-init bug and Claude configuration errors.

**Correction, 2026-09-23.** This is not a new finding. It is a known upstream bug
already fixed on Gas City `main` by a6b72d832 "fix(proctable): never classify a
tmux server as an agent root (#5392)" (2026-09-03). That commit is not an
ancestor of the v1.4.2 release used here, so the bug was present in the tested
binary. The local patch below duplicates the upstream fix. The harness set
`patrol_interval = "1s"`, while the documented default is 30s
(`docs/reference/config.md`), which probably made the reaper act sooner. Also,
the "Beads forced-init bug" mentioned above is a latent, load-dependent issue,
not a demonstrated production bug; see the
[diagnosis correction](../README.md). Original text is kept.

## Observed failure

The controller logged `reaped process-table orphan pid=19620 session=jg7or0b-6hr`.
The retained process observations identify PID 19620 as the tmux server created
for the first operator. That session had been retired, while another operator
and the control dispatcher still used the same server. Both then became
`runtime-missing`; the controller launched replacements. The experiment was
aborted after confirmation, with 16 observed requests and 635,120 processed
tokens. It is not a completed build or an A/B speed sample.

## Cause

`ScanBySessionID` on Darwin parses `ps eww` output. Its inline environment parser
also recognizes `GC_SESSION_ID=...` in tmux's startup `-e` arguments. The server
retains that initial session identity after that session exits. The scanner
checks whether a process's *parent* is infrastructure, but fails to exclude the
current infrastructure process. With parent PID 1, the shared server becomes a
runtime root. Once the initial session bead is closed and no longer tracked,
the orphan reaper selects and terminates the server, destroying peer sessions.

## Fix and evidence

The local patch excludes tmux infrastructure in both `ScanBySessionID` and
`IsScanRoot`. It preserves actual worker roots beneath tmux and continues to
exclude ordinary worker descendants. No global binary was replaced.

- [Patch](gascity-v1.4.2-darwin-tmux-exclusion.patch).
- [Failing regression](regression-red.log): unpatched code returns the server.
- [Passing package tests](regression-green.log): 15 tests plus 3 subtests.
- [Real-process verification](live-probe-result.json): create two sessions in a
  uniquely named tmux server, retire the first, and compare old/new scanner
  binaries. Old code selects the shared server; patched code selects nothing.
  The peer survives. The probes do not signal scanned candidates; cleanup kills
  only their own disposable server.
- [Reproduction script](live_probe.py), [persisted reconciler trace](baseline-003-trace.json), and [build log](build.log).
- Initial full binary build lacked Homebrew ICU paths. The retry follows the
  repository Makefile with `CGO_CPPFLAGS=-I/opt/homebrew/opt/icu4c/include` and
  `CGO_LDFLAGS=-L/opt/homebrew/opt/icu4c/lib`; no dependency was installed or
  changed. See [retry log](build-icu.log).

Source baseline is Gas City v1.4.2. The local build uses the matching source
plus only this scanner patch. A successful scanner probe is not yet a successful
complete Gas City build. The next experiment must use a fresh city and record
the patched binary identity for both arms.

The local binary built successfully as `1.4.2-jev-tmux`; its SHA-256 and exact
compiler flags are in [build metadata](build-icu-result.json). Validation covers
the affected scanner package and real tmux boundary; the full upstream CI suite
has not been run. Baseline 004 uses this experimental binary.

Correction, 2026-09-23: new runs should not use this patched binary. The fix
is upstream in a6b72d832; use a build that includes it, and keep the default
patrol interval.
