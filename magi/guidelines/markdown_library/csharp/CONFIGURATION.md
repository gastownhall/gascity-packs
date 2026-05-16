# Configuration Management

### Configuration Sources

```csharp
var builder = WebApplication.CreateBuilder(args);
builder.Configuration
    .AddJsonFile("appsettings.json", optional: false, reloadOnChange: true)
    .AddJsonFile($"appsettings.{builder.Environment.EnvironmentName}.json", optional: true, reloadOnChange: true)
    .AddEnvironmentVariables()
    .AddCommandLine(args);
```

### Strongly-Typed Options

```csharp
public sealed class DatabaseOptions {
    public const string SectionName = "Database";
    public required string ConnectionString { get; init; }
    public int CommandTimeout { get; init; } = 30;
    public int MaxRetryCount { get; init; } = 3;
}

services.AddOptions<DatabaseOptions>()
    .BindConfiguration(DatabaseOptions.SectionName)
    .ValidateDataAnnotations()
    .ValidateOnStart();
```

### Secret Management

**Never store secrets in configuration files or source control:**

```csharp
if (builder.Environment.IsDevelopment()) {
    builder.Configuration.AddUserSecrets<Program>();
} else {
    builder.Configuration.AddAzureKeyVault(new Uri(keyVaultUri), new DefaultAzureCredential());
}
```

### Options Validation

```csharp
public sealed class DatabaseOptionsValidator : IValidateOptions<DatabaseOptions> {
    public ValidateOptionsResult Validate(string? name, DatabaseOptions options) {
        if (string.IsNullOrWhiteSpace(options.ConnectionString)) {
            return ValidateOptionsResult.Fail("ConnectionString is required");
        }
        if (options.CommandTimeout <= 0) {
            return ValidateOptionsResult.Fail("CommandTimeout must be positive");
        }
        return ValidateOptionsResult.Success;
    }
}

services.AddSingleton<IValidateOptions<DatabaseOptions>, DatabaseOptionsValidator>();
```

---
[Back to Overview](./OVERVIEW.md)
