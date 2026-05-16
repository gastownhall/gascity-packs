# Defense in Depth — Failure Prevention for Behavioral Contract Enforcement

Multiple, independent layers protect behavioral contract enforcement from a single failure. This is **NOT security defense in depth** — it is **failure-mode defense in depth**: every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

Every change in this domain MUST pass through the following independent failure-prevention layers. They are independent on purpose: a bug or outage in one MUST NOT mask the failure for another.

1. **Hooks as the first gate** — `PreToolUse` and `PostToolUse` hooks MUST block prohibited commands at the source. Self-restraint alone is not a defense.
2. **Guideline files read before acting** — The XML guideline for the language MUST be read before code generation; the file IS the policy.
3. **Agent routing for domain work** — Domain-specific agents (forge agents, review agents) MUST be used; the agent is a second opinion independent of the main thread.
4. **CI and review gates** — CI checks AND human review (or a code-review agent) MUST sign off before merge.
5. **Memory and feedback records** — Past corrections MUST persist in memory and be re-read on relevant tasks; the same mistake twice is a contract violation.
6. **Project-local audit logs** — Every action MUST be logged to a project-local file so violations are auditable after the fact.
7. **Self-checks after action** — After every change, the script/test/build MUST be re-run; "I think it works" is not a defense.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A hook block alone is one defense; a clever rephrasing slips past a single regex.
- **Two is a tie** — Hook + memory of past corrections is two defenses, but a fresh-context model violates before memory loads.
- **Three is a quorum** — Hook + guideline read + post-action audit form the triple. Even if any one fails, the other two MUST catch the violation. **Bypassing two of three is a deliberate contract breach, not an accident.**

**Example:** A bypassed hook (mutated command) is caught by the guideline read (rule cited verbatim) AND by the audit log (the run is recorded). All three MUST fail before the violation lands — and the audit alone surfaces it after the fact.

---
[Back to Overview](./OVERVIEW.md)
