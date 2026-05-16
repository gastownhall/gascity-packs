# Shakedown — End-to-End Authentication Validation

### Definition

An email authentication shakedown is the **first controlled end-to-end delivery of a canary message from the real sender reputation chain to a controlled receiver that exposes the `Authentication-Results` header**, followed by programmatic verification that SPF, DKIM, and DMARC all evaluated as expected.

Shakedown is **not** DNS record syntax validation (that is preflight) and **not** ongoing aggregate-report monitoring (that is steady-state operations). Shakedown is the act of proving, with a real message through the real mail flow, that authentication works end-to-end before a new sender identity or changed configuration is trusted in production.

### Authentication-Results Is the Source of Truth

A DNS record that parses cleanly does not prove authentication works. An ESP dashboard that reports "DKIM configured" does not prove messages are signed in transit. The `Authentication-Results` header written by the receiving MTA is the only definitive record of how SPF, DKIM, and DMARC evaluated for a given message. Shakedown measures `Authentication-Results` — nothing else confirms the end-to-end outcome.

### Shake Down Outbound and Inbound

Outbound shakedown validates that mail you send authenticates correctly at receivers. Inbound shakedown validates that mail from known partners authenticates correctly at your receivers — and that your filters evaluate the results you expect. Both directions carry production risk. Both directions must be shaken down when the relevant configuration changes.

### Mandatory Triggers

- **Outbound shakedown** — before enabling any new sender identity in production: new sending IP, new ESP integration, new subdomain for a new mail stream, new DKIM selector, new SPF include, new From domain.
- **Inbound shakedown** — when adding a new partner sender, changing DMARC enforcement level (none → quarantine → reject), changing `arc=` evaluation, changing mail routing or a security gateway (Proofpoint, Mimecast, Microsoft Defender), or replacing the MX.
- **DNS propagation shakedown** — after publishing or modifying SPF, DKIM, DMARC, MTA-STS, TLS-RPT, or BIMI records.

### Non-Triggers

Shakedown is not required for routine content changes inside an already-validated mail stream — template copy updates, personalization token changes, marketing list changes that do not alter SPF, DKIM, DMARC, or sending infrastructure. Steady-state DMARC aggregate monitoring covers these.

### Outbound Validation Requirements

- Send the canary from the production (or production-equivalent) sending infrastructure. A test from a developer laptop or from the ESP's test console bypasses the very infrastructure the shakedown is meant to validate. The envelope sender, From header, DKIM signer, and TLS certificate must all be the ones that will carry production mail.
- Deliver the canary to a controlled mailbox that exposes the raw `Authentication-Results` header. Acceptable targets: a Gmail mailbox controlled by the team, a Microsoft 365 mailbox (writes `X-MS-Exchange-AuthAs` fields), a dedicated Postmark or dmarcian check-auth inbox, or a controlled postfix/dovecot inbox running header logging. Do not use services that summarize authentication without exposing the raw header.
- Verify each component explicitly:
  ```text
  spf=pass smtp.mailfrom=<envelope-sender-domain>;
  dkim=pass header.d=<from-domain> header.s=<selector>;
  dmarc=pass (p=reject sp=reject dis=none) header.from=<from-domain>
  ```
- Confirm DMARC alignment explicitly. SPF pass is not enough — the `smtp.mailfrom` domain must align (relaxed or strict per the DMARC `adkim`/`aspf` tags) with the `header.from` domain. DKIM pass is not enough — the `header.d` value must align with `header.from`. A shakedown that only checks "pass" and not "aligned" misses the most common DMARC failure mode.

### Inbound Validation Requirements

- Maintain an inbound shakedown partner list: every known legitimate sender whose mail must authenticate on inbound — SaaS vendors (Salesforce, Workday, ADP), payment processors, partner organizations, internal subsidiaries with distinct sending domains. For each partner, record the expected SPF result, expected DKIM signer, and expected DMARC outcome.
- During inbound shakedown, each partner sends a canary to a controlled receiver inbox. Capture the `Authentication-Results` written by the receiving mail flow (including any ARC chain added by intermediate relays) and compare against the recorded expectation.
- When ARC is in scope (mailing lists, forwarding, security gateways that rewrite), inbound shakedown must confirm the ARC chain is present, valid, and that receiving evaluation respects `arc=pass` when SPF and DKIM would otherwise fail due to legitimate intermediate modification.

### DNS Propagation Validation

- After publishing or modifying an SPF, DKIM, DMARC, MTA-STS TXT, TLS-RPT, or BIMI record, query the record via `dig +short` from at least five geographically distributed public resolvers (Google `8.8.8.8`, Cloudflare `1.1.1.1`, Quad9 `9.9.9.9`, Level3, OpenDNS). All responses must match the expected value.
- After DKIM key rotation, confirm both the old and new selectors resolve until the rotation overlap period completes. Sign a canary with the new selector and confirm `dkim=pass` at the receiver before retiring the old selector.

### Outbound Shakedown Sequence

| Step | Action |
|:----:|:-------|
| 1 | Preflight: confirm SPF record contains the expected include/IP for this sender; DKIM public key resolves at the selector; DMARC record is present on the From domain; ESP/MTA is configured to sign with the expected selector |
| 2 | Propagation check: `dig +short` the relevant records from at least five public resolvers; confirm all return expected values |
| 3 | Canary dispatch: from the real sending infrastructure, dispatch a single plain-text canary message to the controlled verification mailbox. Use a distinctive subject containing the shakedown run identifier and a UTC timestamp |
| 4 | Fetch the delivered message via IMAP or the receiver API. Locate the `Authentication-Results` header (and any `X-MS-Exchange-AuthAs` fields if Microsoft 365) |
| 5 | Parse `Authentication-Results` and extract spf, dkim, dmarc verdicts. Confirm `spf=pass` with aligned `smtp.mailfrom`, `dkim=pass` with aligned `header.d` and the expected selector, `dmarc=pass` |
| 6 | Optional: verify BIMI evaluation if deployed — confirm `bimi=pass` and that the logo renders in supported clients |
| 7 | Record the canary message headers, resolver query transcripts, and verdict summary. Tag artifacts with sender identity, date, and run identifier |
| 8 | Classify the result: pass, fail-blocking, fail-nonblocking, or inconclusive |

### Inbound Shakedown Sequence

| Step | Action |
|:----:|:-------|
| 1 | Confirm the partner is on the expected-sender list with recorded SPF, DKIM, DMARC expectations |
| 2 | Request that the partner send a canary from their production sender to a controlled recipient inbox on the receiving mail flow |
| 3 | Fetch the delivered (or quarantined) message and locate the `Authentication-Results` added by the receiving mail flow. If quarantined or rejected, inspect gateway logs for the verdict and disposition |
| 4 | Compare observed verdicts against recorded expectation. Confirm alignment and DMARC policy application match |
| 5 | If ARC is in play, verify the chain was added correctly by intermediate hops and final evaluation respects `arc=pass` |
| 6 | Record the message, receiver-side logs, and verdict comparison as artifacts. Classify the result |

### Required Artifacts

Every shakedown run produces:

- The canary message source (full headers and body).
- Resolver query transcripts for every relevant DNS record.
- The parsed `Authentication-Results` with per-component verdict.
- An environment snapshot (sending infrastructure version, DKIM selector in use, SPF record snapshot, DMARC policy value, receiver identity).
- An explicit classification: pass, fail-blocking, fail-nonblocking, or inconclusive.

Artifacts are retained with the sender identity record for future reference during incident response.

### Anti-Patterns (Forbidden)

- Sending the canary from a developer laptop instead of production infrastructure.
- Checking only ESP dashboard status instead of receiver `Authentication-Results`.
- Declaring success on `spf=pass` without confirming alignment.
- Skipping shakedown after "just a DKIM selector rotation".
- Skipping shakedown after DMARC enforcement escalation because "aggregate reports look fine".
- Running shakedown against a receiver that summarizes but does not expose raw `Authentication-Results`.
- Failing to capture artifacts.

---
[Back to Overview](./OVERVIEW.md)
