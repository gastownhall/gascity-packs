# Security Configuration

### Authentication

| Mechanism | Description | Configuration |
|:----------|:------------|:--------------|
| **SASL/SCRAM** | Username/password challenge-response | `security.protocol=SASL_SSL`, `sasl.mechanism=SCRAM-SHA-512` |
| **SASL/OAUTHBEARER** | Token-based; integrates with identity providers (preferred for modern stacks) | `security.protocol=SASL_SSL`, `sasl.mechanism=OAUTHBEARER` |
| **mTLS** | Mutual TLS with client certificates | `security.protocol=SSL`, `ssl.client.auth=required` |
| **SASL/GSSAPI** | Kerberos integration | Required for enterprise environments with existing Kerberos |

### Authorization (ACLs)

ACL structure:

- **Principal** — user or service identity.
- **Operation** — Read, Write, Describe, Delete, Alter, etc.
- **Resource** — Topic, consumer group, cluster, transactional ID.
- **Permission** — Allow or Deny.

**Best practices:**

- Deny by default; explicitly allow required access.
- Use prefixed ACLs for topic families: `PREFIXED topic:orders-`.
- Separate principals for producers and consumers.
- Regular ACL audits for least-privilege compliance.

**Producer ACL:**

```text
Principal: User:producer-app
Operation: WRITE
Resource:  TOPIC:orders.*
Permission: ALLOW
```

**Consumer ACL:**

```text
Principal: User:consumer-app
Operations: READ, DESCRIBE
Resources:  TOPIC:orders.*, GROUP:consumer-group-*
Permission: ALLOW
```

### Encryption

**In-transit:**

```properties
security.protocol=SASL_SSL
ssl.protocol=TLSv1.3
ssl.cipher.suites=TLS_AES_256_GCM_SHA384
```

**At-rest** options:

- Broker-level log segment encryption.
- Encrypted disk volumes at infrastructure layer.
- Client-side payload encryption (Kafka sees only ciphertext) — required for highly sensitive data.

### Network Segmentation

- Isolate Kafka brokers in private subnets.
- Expose only necessary ports (9092 plaintext, 9093 SSL).
- Use internal listeners for broker-to-broker communication.
- Configure advertised listeners for client connectivity requirements.

---
[Back to Overview](./OVERVIEW.md)
