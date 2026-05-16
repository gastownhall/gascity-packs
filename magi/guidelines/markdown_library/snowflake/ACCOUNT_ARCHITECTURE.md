# Account and Organization Architecture

### Organization Structure

Snowflake Organizations group multiple accounts under centralized management. Use organizations when:

- Multiple business units require isolated environments.
- Regulatory requirements mandate data residency separation.
- Cost allocation requires account-level billing granularity.
- Cross-account data sharing is a primary integration pattern.

### Account Strategy

| Approach | Use case |
|:---------|:---------|
| Single Account | Small teams, proof-of-concept, workloads without strict environment isolation |
| Multi-Account (prod / staging / dev as separate) | Complete resource isolation, independent access control, separate billing and resource monitors, protection against dev mistakes affecting prod |

**Account Naming:** use consistent naming that encodes purpose and environment.

| Pattern | Example |
|:--------|:--------|
| `{company}_{business_unit}_{environment}_{region}` | `acme_analytics_prod_uswest2` |

Avoid generic names like `main` or `default` that provide no context.

### Region Selection

Deploy accounts in regions closest to:

1. Primary data sources (reduce ingestion latency).
2. Primary consumers (reduce query latency).
3. Compliance requirements (data residency mandates).

Cross-region data sharing incurs egress costs. **Plan region placement before loading data**; migrating accounts across regions requires data re-ingestion.

### Account Parameters

Configure account-level parameters to establish baseline behaviors:

```sql
ALTER ACCOUNT SET
    STATEMENT_TIMEOUT_IN_SECONDS = 3600,
    STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 600,
    TIMEZONE = 'UTC',
    TIMESTAMP_TYPE_MAPPING = 'TIMESTAMP_NTZ',
    DATE_OUTPUT_FORMAT = 'YYYY-MM-DD',
    TIMESTAMP_OUTPUT_FORMAT = 'YYYY-MM-DD HH24:MI:SS.FF3';
```

Standardize timestamp handling across the account. UTC as default timezone eliminates daylight-saving-time ambiguities and simplifies cross-timezone analytics.

---
[Back to Overview](./OVERVIEW.md)
