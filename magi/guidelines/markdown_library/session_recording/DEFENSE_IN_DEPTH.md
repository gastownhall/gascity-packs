# Defense in Depth

Multiple, independent layers protect session recording / capture infrastructure from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Redundant capture paths** — Each session MUST be captured by at least two independent agents/sinks; one agent crash MUST NOT lose the session.
2. **Durable write with fsync** — Recording streams MUST be written with fsync semantics on critical events; in-memory buffering alone loses data on crash.
3. **Storage replication** — Recordings at rest MUST be replicated cross-region or cross-account.
4. **Retention and lifecycle policy** — Retention MUST be policy-defined; manual cleanup is forbidden.
5. **Playback validation** — A scheduled job MUST sample-play recordings to confirm they are usable; an unplayable recording is no recording.
6. **Integrity checksums** — Each recording MUST have a checksum; periodic verification MUST detect bit rot.
7. **Audit log of access** — Every read/playback MUST be logged independently of the storage system's own logs.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A "recording saved" signal is one claim; until played back, it is unverified.
- **Two is a tie** — Two copies on the same volume share the volume's failure domain.
- **Three is a quorum** — Three copies — primary durable store + replicated copy + a periodically verified archive — form the rule of three. **Recovery MUST be possible from any two if the third is lost.**

**Example:** A bit-rotted primary + an unverified replica = two failed copies; only the periodically-verified archive is the recoverable third voter.

---
[Back to Overview](./OVERVIEW.md)
