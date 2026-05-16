# Core Principles (Non-Negotiable)

1. **UNDERSTAND THE FULL SYSTEM** — Never treat functions in isolation. Trace all call paths, ownership flows, and lifetimes.
2. **NO OVER-ENGINEERING** — Code does exactly what's required. More abstractions = more failure points.
3. **THINK BEFORE CODING** — Trace the entire execution flow mentally before writing. Reflexive coding is forbidden.
4. **CONSIDER DOWNSTREAM EFFECTS** — Every change must account for all dependent code paths and trait implementations.
5. **USERS MUST NOT DISCOVER ERRORS** — If `user runs → reports error → you fix → repeat` emerges, you're doing it wrong. Type safety, Result types, and defensive coding prevent this.
6. **NEVER HANDLE IMPOSSIBLE SCENARIOS** — If a condition cannot occur given the type system, do not write handlers for it.
7. **LEVERAGE THE TYPE SYSTEM** — Make invalid states unrepresentable. Compile-time errors are better than runtime errors.

### Primary Rule: Compact First, Multi-line When Necessary
Use horizontal space efficiently before breaking to multiple lines. Only use multi-line formatting when:
- Line exceeds 220 characters
- Complex nested structures require it for clarity
- Multiple statements in a block

---
[Back to Overview](./OVERVIEW.md)
