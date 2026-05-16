# Backup Strategy Decision Tree

| Data criticality | RTO | Strategy | Technologies |
|:----------------:|:---:|:---------|:-------------|
| Mission-critical | Minutes | Hot Standby with Continuous Replication | SQL Always On Availability Groups; Cosmos DB multi-region writes; Redis Enterprise Active-Active |
| Mission-critical | Hours | Warm Standby with Point-in-Time Recovery | Azure SQL Geo-Replication; Backup Vault hourly snapshots |
| Mission-critical | Days | Cold Backup with Daily Snapshots | Azure Backup Vault; Blob Storage with lifecycle policies |
| Important | — | Standard Backup with Geo-Redundancy | Daily backups, 30-day retention |
| Replaceable | — | Local Backup Only | Weekly backups, 7-day retention |

### Hot Standby Configuration

```csharp
public class HotStandbyConfiguration
{
    public void ConfigureAlwaysOn()
    {
        var primary = "sql-primary.database.windows.net";
        var secondary = "sql-secondary.database.windows.net";
        var connectionString = $@"
            Server={primary};
            Database=Production;
            MultiSubnetFailover=true;
            ApplicationIntent=ReadWrite;
            ConnectTimeout=30;
            TrustServerCertificate=false;
            Encrypt=true;
        ";
        // Automatic failover within seconds
    }
}
```

### Backup Orchestrator

Backups must be automated, monitored, verified, restore-tested. **An unverified backup is no backup.**

```csharp
public class BackupOrchestrator
{
    private readonly ILogger<BackupOrchestrator> _logger;
    private readonly Dictionary<string, IBackupStrategy> _strategies;

    public async Task ExecuteBackupAsync(BackupJob job)
    {
        var strategy = _strategies[job.DataType];
        try
        {
            // Pre-backup validation
            await strategy.ValidateSourceAsync(job.Source);

            // Create backup
            var backupId = Guid.NewGuid();
            var backupPath = GetBackupPath(job, backupId);
            await strategy.CreateBackupAsync(job.Source, backupPath);

            // Verify backup
            var isValid = await strategy.VerifyBackupAsync(backupPath);
            if (!isValid)
            {
                throw new BackupVerificationException();
            }

            // Register in catalog with checksum
            await RegisterBackupAsync(new BackupEntry
            {
                Id = backupId,
                JobId = job.Id,
                Path = backupPath,
                CreatedAt = DateTimeOffset.UtcNow,
                SizeBytes = await GetBackupSizeAsync(backupPath),
                Checksum = await CalculateChecksumAsync(backupPath)
            });

            // Apply retention policy
            await ApplyRetentionPolicyAsync(job.RetentionPolicy);

            // Replicate to secondary location if required
            if (job.RequiresGeoRedundancy)
            {
                await ReplicateToSecondaryAsync(backupPath);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Backup failed for job {JobId}", job.Id);
            await NotifyBackupFailureAsync(job, ex);
            throw;
        }
    }

    public async Task<RestoreResult> RestoreAsync(RestoreRequest request)
    {
        // Find appropriate backup
        var backup = await FindBackupAsync(request.PointInTime);

        // Validate backup integrity via checksum
        var checksum = await CalculateChecksumAsync(backup.Path);
        if (checksum != backup.Checksum)
        {
            throw new BackupCorruptedException(backup.Id);
        }

        // Perform restore
        var strategy = _strategies[backup.DataType];
        await strategy.RestoreAsync(backup.Path, request.Target);

        // Verify restore
        await strategy.VerifyRestoreAsync(request.Target);

        return new RestoreResult
        {
            BackupId = backup.Id,
            RestoredAt = DateTimeOffset.UtcNow,
            PointInTime = backup.CreatedAt
        };
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
