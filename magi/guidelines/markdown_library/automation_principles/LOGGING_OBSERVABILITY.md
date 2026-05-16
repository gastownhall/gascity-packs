# Logging and Observability

Logging is the primary mechanism for understanding automation behavior. Self-healing automation logs every significant action, decision, and outcome with sufficient context to diagnose problems without reproducing them.

### Log Levels

| Level | Purpose |
|:------|:--------|
| ERROR | Failures preventing successful completion. Always logged. Requires attention. |
| WARN | Conditions indicating problems but allowing continued operation. Degraded functionality, deprecated usage, near-limit resources. |
| INFO | Significant operational events. Start/stop, configuration loaded, major phase transitions, successful completions. |
| DEBUG | Detailed operational information. Individual operations, intermediate values, decision points. |
| TRACE | Extremely detailed information. Function entry/exit, loop iterations, raw data values. |

Production automation defaults to INFO with DEBUG/TRACE available via configuration.

### Log Message Structure

Every log message should include:
- **Timestamp** — ISO 8601 format with timezone, millisecond precision minimum
- **Level** — Severity classification
- **Component** — Source of the message (script name, function name)
- **Message** — Human-readable description of what occurred
- **Context** — Structured key-value data relevant to the event

### Structured Logging

Prefer structured logging formats (JSON) for machine processing:

```json
{"timestamp":"2025-01-15T10:30:00.123Z","level":"INFO","component":"deploy","message":"Container started","container_id":"abc123","image":"myapp:1.2.3","port":8080}
```

Human-readable formats are acceptable for interactive execution but should include sufficient structure for grep/awk processing.

### Sensitive Data Handling

**Never log:**
- Passwords, API keys, tokens, private keys
- Full credit card numbers, SSNs, or other PII
- Connection strings with embedded credentials
- Session identifiers that enable impersonation

Log that a credential was used without logging what the credential was.

### Correlation Identifiers

Multi-component automation needs correlation:

- Generate a unique execution ID at start
- Propagate the ID to all subprocesses and remote calls
- Include the ID in all log messages
- Pass the ID in headers for HTTP calls

### Progress Indication

Long-running operations need progress feedback:

- Estimated percentage complete
- Items processed vs total items
- Elapsed time and estimated remaining time
- Current phase of multi-phase operations

For interactive execution, progress can update in place. For non-interactive execution, periodic progress log messages prevent timeout kills and provide audit trails.

---
[Back to Overview](./OVERVIEW.md)
