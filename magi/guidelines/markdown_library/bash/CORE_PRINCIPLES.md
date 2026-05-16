# Core Principles (Non-Negotiable)

1. **UNDERSTAND THE FULL SYSTEM** — Never treat functions in isolation. Trace all call paths and dependencies.
2. **NO OVER-ENGINEERING** — Code does exactly what's required. More complexity = more failure points.
3. **THINK BEFORE CODING** — Trace the entire execution flow mentally before writing. Reflexive coding is forbidden.
4. **CONSIDER DOWNSTREAM EFFECTS** — Every fix must account for all dependent code paths.
5. **USERS MUST NOT DISCOVER ERRORS** — If a pattern of `user runs → reports error → you fix → repeat` emerges, you are doing it wrong. Pre-flight checks, validation, and defensive coding prevent this.
6. **NEVER FIX IMPOSSIBLE SCENARIOS** — If a condition cannot occur given the code flow, do not write handlers for it.
7. **FAIL LOUDLY, SUCCEED QUIETLY** — Successful operations produce minimal (or verbosity-gated) output. Failures must always be loud, specific, and visible. A script that fails silently is worse than one that crashes.
8. **PRINCIPLE OF LEAST SURPRISE** — Scripts must behave predictably. Side effects must be documented, destructive actions must require confirmation or a flag, and default behavior must always be the safest option.
9. **SELF-SUFFICIENCY** — Every script runs to completion on a fresh system without manual intervention. If you have to run a manual command to make automation work, that command belongs IN the automation. No exceptions.
10. **DETERMINISTIC EXECUTION** — Given identical inputs and starting conditions, automation produces identical outcomes. Eliminate non-determinism from unordered globs, unsorted command output, race conditions, and locale-dependent sorting.
11. **FAILURE ISOLATION** — Individual component failures do not cascade. A failure in one phase must not corrupt state needed by other phases or leave the system in an unrecoverable condition.
12. **MINIMAL FOOTPRINT** — Automation installs only what is required and cleans up after itself. Do not install convenience packages, do not leave temporary artifacts, do not modify global system state beyond the script's purpose.

---
[Back to Overview](./OVERVIEW.md)
