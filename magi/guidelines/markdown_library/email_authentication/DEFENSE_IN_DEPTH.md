# Defense in Depth

Multiple, independent layers protect email authentication (SPF/DKIM/DMARC) and deliverability from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **SPF record** — MUST be published and limited to known senders; soft-fail MUST graduate to hard-fail equivalent (`~all` with DMARC `p=reject`) once verified.
2. **DKIM signing** — MUST sign every outbound message; rotated keys MUST be tested before retirement.
3. **DMARC policy** — MUST start at `p=none` for telemetry, then graduate to quarantine, then reject; aggregate (`rua`) and forensic (`ruf`) reports MUST be parsed.
4. **MTA-STS and TLS-RPT** — MUST be published; reports MUST be ingested.
5. **BIMI with VMC** — Raises the cost of impersonation and gives a positive trust signal in clients that support it.
6. **Inbox placement monitoring** — Seedlist deliverability tools (250ok / GlockApps / Postmark) MUST sample inbox vs spam placement over time.
7. **Bounce and complaint feedback** — Bounce and FBL feeds MUST be processed; ignored complaints destroy sender reputation faster than any of the above repairs it.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — SPF alone is forgeable through SPF-aligned forwarding; DKIM alone breaks on legitimate forwarding. Either signal alone is unsafe.
- **Two is a tie** — SPF + DKIM without DMARC has no enforcement policy. The two passes still leave the inbox decision to the receiver.
- **Three is a quorum** — SPF + DKIM + DMARC are the canonical rule-of-three for email auth and are the minimum production posture. A message MUST pass at least two of three with DMARC alignment to be considered authentic.

Example: a forwarded message breaks SPF but keeps DKIM aligned; DMARC then accepts it because two of three checks (DKIM + alignment) agree.

---
[Back to Overview](./OVERVIEW.md)
