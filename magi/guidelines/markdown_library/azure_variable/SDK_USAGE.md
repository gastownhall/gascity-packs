# SDK Usage Patterns

### App Configuration SDK (C#)

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddAzureAppConfiguration(options =>
{
    options.Connect(new Uri(appConfigEndpoint), new DefaultAzureCredential())
        .Select(KeyFilter.Any, LabelFilter.Null)
        .Select(KeyFilter.Any, builder.Environment.EnvironmentName)
        .ConfigureKeyVault(kv => kv.SetCredential(new DefaultAzureCredential()))
        .ConfigureRefresh(refresh =>
        {
            refresh.Register("Sentinel", refreshAll: true)
                .SetCacheExpiration(TimeSpan.FromMinutes(5));
        })
        .UseFeatureFlags(ff =>
        {
            ff.CacheExpirationInterval = TimeSpan.FromMinutes(1);
        });
});
```

### App Configuration SDK (Python)

```python
from azure.appconfiguration.provider import AzureAppConfigurationProvider
from azure.identity import DefaultAzureCredential

config = AzureAppConfigurationProvider.load(
    endpoint=app_config_endpoint,
    credential=DefaultAzureCredential(),
    selects=[("*", None), ("*", environment)],
    keyvault_credential=DefaultAzureCredential(),
    refresh_on={"Sentinel": True},
    refresh_interval=300
)
```

### Key Vault SDK

Direct Key Vault access when App Configuration references are insufficient:

```csharp
var client = new SecretClient(new Uri(vaultUri), new DefaultAzureCredential());
KeyVaultSecret secret = await client.GetSecretAsync("secret-name");
string secretValue = secret.Value;
```

Use direct access for:
- Operations requiring secret metadata (expiration, enabled status)
- Certificate operations
- Key operations (encryption, signing)
- Scenarios where App Configuration is not used

### Error Handling

| Failure | Action | Method |
|:--------|:-------|:-------|
| Network timeout | Retry | Exponential backoff |
| 429 throttling | Respect | Honor `Retry-After` header; consider caching |
| 401/403 | Fail | Log and alert; do not retry (configuration issue) |
| Secret not found | Fail | Fail fast with clear error message |

Cache configuration aggressively. App Configuration and Key Vault have request quotas; excessive calls indicate architectural problems.

---
[Back to Overview](./OVERVIEW.md)
