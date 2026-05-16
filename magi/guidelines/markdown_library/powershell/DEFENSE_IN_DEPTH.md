# Defense in Depth

Multiple, independent layers protect PowerShell scripts from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Strict mode** — `Set-StrictMode -Version Latest` and `$ErrorActionPreference='Stop'` MUST be at the top of every script. Default PowerShell behavior continues past errors; strict mode forbids it.
2. **PSScriptAnalyzer** — MUST pass with zero warnings. Lint catches naming, parameter, and pipeline issues that strict mode does not surface.
3. **SupportsShouldProcess** — Every destructive cmdlet/function MUST declare `CmdletBinding` with `SupportsShouldProcess` so `-WhatIf` shows planned actions before execution.
4. **Pester tests** — MUST cover every public function and parameter set. Untested PowerShell quietly degrades because of dynamic typing.
5. **Transcript logging** — `Start-Transcript` (or equivalent structured logging) MUST capture every run to a project-local log file. Console output is not a record.
6. **Retry and timeout** — Remote calls (`Invoke-Command`, `Invoke-RestMethod`) MUST retry with backoff and enforce explicit timeouts. PowerShell defaults are not safe for unattended runs.
7. **Shakedown** — The §21 `Invoke-Shakedown` MUST run after every change touching integration boundaries.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A single "Success" line in a transcript is one signal; verify the actual state changed.
- **Two is a tie** — `-WhatIf` showed correct intent but the transcript shows no error AND the post-state still looks unchanged: the run is suspect; do NOT proceed.
- **Three is a quorum** — Exit status + transcript content + post-condition `Get-*` check form the three witnesses. **Majority rule** — at least two MUST agree the change happened before declaring success.

Example: `Set-Service` returns success while the service silently fails to start. Combine `$?` + `Get-Service` status + event-log entry — three signals, not one.

---
[Back to Overview](./OVERVIEW.md)
