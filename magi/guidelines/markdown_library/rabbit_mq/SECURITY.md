# Security Configuration

### Authentication

RabbitMQ supports multiple authentication backends:

| Backend | Use case | Limitation |
|:--------|:---------|:-----------|
| Internal database | Development, small deployments | Not suitable for production at scale |
| LDAP | Corporate environments | Directory dependency |
| OAuth 2.0 | Modern microservices | Token infrastructure required |
| x509 certificates | High-security environments | Certificate management complexity |

Avoid internal database for production at scale; use LDAP or OAuth for centralized management.

### Authorization

Permissions control access to vhost resources:

| Permission | Actions |
|:-----------|:--------|
| `configure` | Create/delete exchanges and queues |
| `write` | Publish to exchanges |
| `read` | Consume from queues, bind queues to exchanges |

**Grant minimum required permissions.** Applications that only publish need only write permission. Applications that only consume need only read permission.

### TLS Configuration

Encrypt all connections in production:

- Enable TLS on AMQP listener (port 5671 by default).
- **Require TLS; disable plaintext listener (5672).**
- Use certificates from a trusted CA.
- Configure minimum TLS version (1.2 or 1.3).
- Verify client certificates for mutual TLS.

### User Management

Separate users by purpose:

- Administrative user for management operations.
- Application users per service with scoped permissions.
- Monitoring user with read-only management access.

**Never share credentials across applications. Never use the default `guest` user outside localhost.**

### Secrets Management

Store credentials in secrets management systems:

- HashiCorp Vault
- Cloud provider secrets (AWS Secrets Manager, Azure Key Vault)
- Kubernetes Secrets (encrypted at rest)

Never embed credentials in application code or configuration files committed to version control.

---
[Back to Overview](./OVERVIEW.md)
