# Defense in Depth

Multiple, independent layers protect authentication and session integration from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Credential validation** — Use a vetted library (Argon2 / bcrypt / scrypt for passwords, OIDC libraries for tokens). Never roll-your-own.
2. **Rate limiting** — Login and token endpoints MUST be rate-limited per identity AND per source so brute force fails before passwords do.
3. **Multi-factor** — Sensitive accounts MUST require MFA; the second factor is the second independent layer.
4. **Session rotation** — Sessions/tokens MUST rotate on privilege escalation and MUST have an enforced absolute lifetime.
5. **Audit logging** — Every authentication event MUST be logged with user, IP, and outcome to a tamper-evident store.
6. **Anomaly detection** — Impossible-travel and brute-force patterns MUST be alerted on independently of rate limits.
7. **Revocation** — A revocation list (or short-lived tokens with a refresh cycle) MUST be honored everywhere a session is accepted.
8. **Shakedown** — §15 covers integration paths the unit and contract suites cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A correct password is one signal. And the most easily phished one.
- **Two is a tie** — Password + IP allowlist (or device cookie) is two signals, but both are replayable by an attacker who has compromised the device.
- **Three is a quorum** — Knowledge factor + possession factor + behavioral/anomaly signal form the canonical triple for authentication confidence. A login MUST score at least two of three to proceed; sensitive operations require all three.

Example: a successful password + valid TOTP + login from a never-seen-before country is two-of-three positive vs. one anomalous; treat as **step-up**, not pass.

---
[Back to Overview](./OVERVIEW.md)
