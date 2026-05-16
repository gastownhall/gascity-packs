# Self-Hosted vs Cloud Deployment

The deployment model determines data sovereignty, compliance posture, operational burden, and total cost. **The choice is not purely technical — it is a regulatory and business decision.**

### Self-Hosted (OpenReplay)

Deploy on the organization's cloud infrastructure (AWS, GCP, Azure, DigitalOcean). Secure the Kubernetes cluster or Docker host with network policies, access controls, and encrypted storage.

Components requiring security hardening:

| Component | Purpose | Hardening |
|:----------|:--------|:----------|
| ClickHouse | Event storage | Non-default password, TLS, network restriction |
| PostgreSQL | Metadata | Non-default password, TLS, network restriction |
| Redis | Caching | Non-default password, AUTH, network restriction |
| Kafka / NATS | Message queuing | TLS between services, ACLs |

### Vendor Cloud (FullStory, LogRocket, Sentry, Datadog)

Execute a **Data Processing Agreement (DPA)** covering GDPR requirements before deployment. Verify:

- SOC 2 Type II certification
- Encryption standards (in-transit and at-rest)
- Data breach notification procedures
- Data deletion capabilities

The DPA must cover session replay data **explicitly**, not just generic "analytics data."

### Data Residency

For organizations with strict data residency requirements (EU data must stay in EU, healthcare data subject to HIPAA, financial data subject to regional regulations), prefer self-hosted solutions or vendor cloud solutions with **explicit data residency guarantees and DPAs**. Verify the vendor's sub-processor list, data center locations, and encryption-at-rest practices before transmitting session data.

### Per-User Deletion

GDPR Article 17 (right to erasure) requires the ability to delete a specific user's recordings on request. Verify the vendor provides per-user data deletion via API or dashboard. Self-hosted solutions must implement per-user deletion in the data pipeline, querying by user identifier and removing all associated session data from all storage layers (event store, blob storage, metadata database).

---
[Back to Overview](./OVERVIEW.md)
