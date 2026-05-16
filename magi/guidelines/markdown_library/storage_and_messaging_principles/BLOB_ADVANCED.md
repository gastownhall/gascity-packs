# Blob Storage Advanced Patterns

### Resumable Uploads

```csharp
public class ResumableUploader
{
    private readonly BlockBlobClient _blobClient;
    private readonly int _blockSizeBytes = 4 * 1024 * 1024; // 4 MB blocks

    public async Task UploadAsync(Stream source, IProgress<long>? progress, CancellationToken ct)
    {
        var blockIds = new List<string>();
        var buffer = new byte[_blockSizeBytes];
        long totalUploaded = 0;
        int blockIndex = 0;

        while (true)
        {
            var bytesRead = await source.ReadAsync(buffer, 0, buffer.Length, ct);
            if (bytesRead == 0) break;

            var blockId = Convert.ToBase64String(Encoding.UTF8.GetBytes(blockIndex.ToString("D6")));
            blockIds.Add(blockId);

            using var blockContent = new MemoryStream(buffer, 0, bytesRead);
            await _blobClient.StageBlockAsync(blockId, blockContent, cancellationToken: ct);

            totalUploaded += bytesRead;
            progress?.Report(totalUploaded);
            blockIndex++;
        }

        // Commit all blocks
        await _blobClient.CommitBlockListAsync(blockIds, cancellationToken: ct);
    }
}
```

### Content Delivery with SAS

```csharp
public class ContentDeliveryService
{
    private readonly BlobContainerClient _containerClient;

    public Uri GenerateDownloadUrl(string blobName, TimeSpan validity)
    {
        var sasBuilder = new BlobSasBuilder
        {
            BlobContainerName = _containerClient.Name,
            BlobName = blobName,
            Resource = "b", // Blob
            ExpiresOn = DateTimeOffset.UtcNow.Add(validity)
        };

        sasBuilder.SetPermissions(BlobSasPermissions.Read);

        var sasUri = _containerClient
            .GetBlobClient(blobName)
            .GenerateSasUri(sasBuilder);

        return sasUri;
    }

    public Uri GenerateUploadUrl(string blobName, TimeSpan validity)
    {
        var sasBuilder = new BlobSasBuilder
        {
            BlobContainerName = _containerClient.Name,
            BlobName = blobName,
            Resource = "b",
            ExpiresOn = DateTimeOffset.UtcNow.Add(validity)
        };

        sasBuilder.SetPermissions(BlobSasPermissions.Write | BlobSasPermissions.Create);

        return _containerClient.GetBlobClient(blobName).GenerateSasUri(sasBuilder);
    }
}
```

### Lifecycle Management Policy

```json
{
  "rules": [
    {
      "name": "move-to-cool-after-30-days",
      "enabled": true,
      "type": "Lifecycle",
      "definition": {
        "filters": {
          "blobTypes": ["blockBlob"],
          "prefixMatch": ["logs/"]
        },
        "actions": {
          "baseBlob": {
            "tierToCool": {
              "daysAfterModificationGreaterThan": 30
            },
            "tierToArchive": {
              "daysAfterModificationGreaterThan": 180
            },
            "delete": {
              "daysAfterModificationGreaterThan": 365
            }
          }
        }
      }
    }
  ]
}
```

### Multi-Category Lifecycle Policy

```json
{
  "rules": [
    {
      "name": "archive-old-logs",
      "enabled": true,
      "type": "Lifecycle",
      "definition": {
        "filters": {
          "blobTypes": ["blockBlob"],
          "prefixMatch": ["logs/", "audit/"]
        },
        "actions": {
          "baseBlob": {
            "tierToCool": { "daysAfterModificationGreaterThan": 30 },
            "tierToArchive": { "daysAfterModificationGreaterThan": 90 },
            "delete": { "daysAfterModificationGreaterThan": 2555 }
          }
        }
      }
    },
    {
      "name": "delete-temp-files",
      "enabled": true,
      "type": "Lifecycle",
      "definition": {
        "filters": {
          "blobTypes": ["blockBlob"],
          "prefixMatch": ["temp/", "cache/"]
        },
        "actions": {
          "baseBlob": {
            "delete": { "daysAfterModificationGreaterThan": 7 }
          }
        }
      }
    }
  ]
}
```

### Data Retention Policy with Immutability

```csharp
public class DataRetentionService
{
    private readonly Dictionary<string, RetentionPolicy> _policies = new()
    {
        ["user-data"] = new RetentionPolicy { RetentionDays = 2555, Archive = true },
        ["logs"] = new RetentionPolicy { RetentionDays = 90, Archive = false },
        ["temp"] = new RetentionPolicy { RetentionDays = 1, Archive = false },
        ["audit"] = new RetentionPolicy { RetentionDays = 2555, Archive = true, Immutable = true }
    };

    public async Task ApplyRetentionPolicyAsync(string category, string blobName)
    {
        if (!_policies.TryGetValue(category, out var policy))
            throw new InvalidOperationException($"No retention policy for {category}");

        var blob = _container.GetBlobClient(blobName);
        var metadata = new Dictionary<string, string>
        {
            ["retention-days"] = policy.RetentionDays.ToString(),
            ["delete-after"] = DateTimeOffset.UtcNow.AddDays(policy.RetentionDays).ToString("O"),
            ["archive"] = policy.Archive.ToString(),
            ["category"] = category
        };
        await blob.SetMetadataAsync(metadata);

        if (policy.Immutable)
        {
            await EnableImmutabilityAsync(blob, policy.RetentionDays);
        }
    }

    private async Task EnableImmutabilityAsync(BlobClient blob, int retentionDays)
    {
        var immutabilityPolicy = new BlobImmutabilityPolicy
        {
            ExpiresOn = DateTimeOffset.UtcNow.AddDays(retentionDays),
            PolicyMode = BlobImmutabilityPolicyMode.Locked
        };
        await blob.SetImmutabilityPolicyAsync(immutabilityPolicy);
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
