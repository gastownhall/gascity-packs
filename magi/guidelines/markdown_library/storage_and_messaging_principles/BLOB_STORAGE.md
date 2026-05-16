# Azure Blob Storage

### What It Is

Azure Blob Storage is object storage for the cloud. It stores unstructured data as blobs (binary large objects) organized in containers. It's designed for storing massive amounts of data that doesn't fit structured database models.

### Core Strengths

- **Massive Scale**: Virtually unlimited storage capacity
- **Cost-Effective**: Cheapest storage option per GB, especially for infrequent access
- **Durability**: 11+ nines durability with geo-redundancy options
- **Tiering**: Hot, Cool, Cold, Archive tiers for cost optimization
- **CDN Integration**: Serve static content globally with low latency
- **Immutable Storage**: WORM (Write Once Read Many) for compliance
- **Versioning**: Automatic version history for blobs
- **Lifecycle Management**: Automated tiering and deletion policies

### Core Weaknesses

- **No Querying**: Cannot query blob contents; must download entire blob
- **Latency**: Higher latency than databases; not for real-time access patterns
- **No Transactions**: No ACID transactions across multiple blobs
- **Limited Metadata**: Blob metadata is limited; requires external index for search
- **Archive Tier Latency**: Archive retrieval takes hours

### Ideal Use Cases

- File storage (images, videos, documents, backups)
- Static website hosting
- Data lake storage for analytics
- Backup and disaster recovery
- Log and telemetry archival
- Media streaming source files
- Machine learning training data
- Compliance archives (immutable storage)

### Avoid When

- Data requires frequent small updates (use database)
- Random access within files is needed
- Complex queries on data are required
- Low-latency access is critical (<10ms)
- Transactional consistency is needed

### Access Tiers

| Tier        | Access Latency | Storage Cost | Access Cost | Use Case                     |
|-------------|----------------|--------------|-------------|------------------------------|
| **Hot**     | Milliseconds   | Highest      | Lowest      | Frequently accessed data     |
| **Cool**    | Milliseconds   | Lower        | Higher      | Infrequent access (30+ days) |
| **Cold**    | Milliseconds   | Lower        | Higher      | Rare access (90+ days)       |
| **Archive** | Hours          | Lowest       | Highest     | Long-term archival           |

Set lifecycle policies to automatically transition blobs between tiers based on age.

### Naming Conventions

- **Storage Account**: Globally unique, 3-24 characters, lowercase alphanumeric
- **Container**: Lowercase, 3-63 characters, alphanumeric and hyphens
- **Blob Name**: Up to 1024 characters, case-sensitive, forward slashes create virtual hierarchy

```
https://{storage-account}.blob.core.windows.net/{container}/{blob-path}
https://myapp.blob.core.windows.net/images/users/123/profile.jpg
```

### Security Patterns

**Shared Access Signatures (SAS)**:
- Time-limited tokens for delegated access
- Scope to specific containers, blobs, or operations
- Always use HTTPS-only SAS tokens
- Prefer User Delegation SAS (Azure AD-backed) over Account SAS

**Azure AD Authentication**:
- Preferred for service-to-service communication
- Use Managed Identity for Azure services
- Assign minimal RBAC roles (Storage Blob Data Reader, Contributor)

**Private Endpoints**:
- Access blob storage over private IP within VNet
- Required for compliance and security-sensitive workloads

### Upload Patterns

| Size          | Method      | Notes                               |
|---------------|-------------|-------------------------------------|
| < 256 MB      | Put Blob    | Single request upload               |
| 256 MB - 5 TB | Block Blob  | Upload in blocks, commit block list |
| Large files   | AzCopy      | Parallel transfer, resume support   |
| Streaming     | Append Blob | Append-only, ideal for logs         |

### Integration Patterns

**Event Grid Integration**:
- Trigger Azure Functions on blob create/delete
- Enable event-driven processing pipelines

**CDN Integration**:
- Front blob storage with Azure CDN for global distribution
- Cache static assets at edge locations
- Custom domains with HTTPS

**Data Lake Storage Gen2**:
- Hierarchical namespace on blob storage
- Enables true directory operations
- Required for analytics workloads (Databricks, Synapse)

---
[Back to Overview](./OVERVIEW.md)
