# DNS Migration and Cutover

### Pre-Migration Checklist

Before migrating DNS to a new provider, complete the following without exception:

- Export the complete zone file from the current provider.
- Inventory every record and verify its purpose.
- Identify and remove orphaned records and stale verification TXT records.
- Lower TTLs on all records to 300 seconds at least 48 hours before migration.
- Confirm the new provider supports all record types in use (ALIAS, CAA, SRV are sometimes missing).
- Verify DNSSEC DS record update process at the registrar.

### Migration Execution

1. Recreate all records at the new DNS provider before changing nameservers.
2. Verify record accuracy using the new provider's API or dashboard.
3. Update nameservers at the registrar.
4. Monitor resolution with external tools (`dig @new-ns example.com`, online propagation checkers) to confirm the new nameservers are serving correct responses.
5. Keep the old zone intact at the previous provider for at least 72 hours as a rollback option — some resolvers with aggressive caching continue querying old nameservers beyond expected TTL.

### Cutover Risks

The most dangerous moment in a DNS migration is the nameserver change. If records at the new provider are incorrect or incomplete, users experience resolution failures.

For DNSSEC-enabled domains:

1. Disable DNSSEC before migration.
2. Complete the migration.
3. Re-enable DNSSEC at the new provider.
4. Update the DS record at the registrar.

This sequence avoids a broken chain of trust during the transition. If DNSSEC is enabled and the DS record at the registrar references keys at the old provider, validating resolvers will reject responses from the new provider until the DS record is updated.

---
[Back to Overview](./OVERVIEW.md)
