# Parameter Design

### CmdletBinding and Parameter Blocks

```powershell
function Get-ServiceStatus {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory = $true, Position = 0, ValueFromPipeline = $true, ValueFromPipelineByPropertyName = $true)]
        [ValidateNotNullOrEmpty()]
        [Alias('ServiceName')]
        [string[]]$Name,

        [Parameter()]
        [ValidateSet('Running', 'Stopped', 'All')]
        [string]$Status = 'All',

        [Parameter()]
        [switch]$IncludeDisabled
    )
    # Function body
}
```

### CmdletBinding Attributes

| Attribute | Purpose |
|:----------|:--------|
| `SupportsShouldProcess` | Enables `-WhatIf` and `-Confirm` for state-changing operations |
| `ConfirmImpact` | Sets confirmation threshold: `Low`, `Medium`, `High`, `None` |
| `DefaultParameterSetName` | Specifies default when multiple parameter sets exist |
| `PositionalBinding` | Controls whether positional binding is enabled |
| `SupportsPaging` | Enables `-First`, `-Skip`, `-IncludeTotalCount` for paginated results |

### Parameter Attributes

- `Mandatory` — require the parameter; PowerShell prompts if omitted.
- `Position` — allow positional binding at specified index. Use sparingly; named parameters are clearer.
- `ValueFromPipeline` — accept entire pipeline objects as this parameter's value.
- `ValueFromPipelineByPropertyName` — match pipeline object property names to parameter names.
- `ValueFromRemainingArguments` — capture all unbound positional arguments.

### Validation Attributes

| Attribute | Purpose |
|:----------|:--------|
| `ValidateNotNull` | Reject `$null` values |
| `ValidateNotNullOrEmpty` | Reject `$null`, empty strings, empty collections |
| `ValidateSet` | Restrict to enumerated values |
| `ValidateRange` | Numeric range constraints |
| `ValidateLength` | String length constraints |
| `ValidatePattern` | Regex pattern match |
| `ValidateScript` | Custom validation logic |
| `ValidateCount` | Collection item count |
| `ValidateDrive` | Restrict to specific PowerShell drives |

Apply validation to catch errors at parameter binding, **before function logic executes**.

### Parameter Sets

```powershell
function Connect-Server {
    [CmdletBinding(DefaultParameterSetName = 'Credential')]
    param(
        [Parameter(Mandatory = $true, ParameterSetName = 'Credential')]
        [PSCredential]$Credential,

        [Parameter(Mandatory = $true, ParameterSetName = 'Certificate')]
        [X509Certificate2]$Certificate,

        [Parameter(Mandatory = $true, ParameterSetName = 'Token')]
        [SecureString]$AccessToken,

        [Parameter(Mandatory = $true)]
        [string]$Server
    )
}
```

Users specify one authentication method; PowerShell enforces mutual exclusivity.

### Common Parameter Patterns

**ComputerName** — remote targeting with localhost default:

```powershell
[Parameter(ValueFromPipelineByPropertyName = $true)]
[Alias('CN', 'Server', 'Host')]
[string[]]$ComputerName = $env:COMPUTERNAME
```

**Credential** — authentication with current user default:

```powershell
[Parameter()]
[PSCredential]
[System.Management.Automation.Credential()]
$Credential = [PSCredential]::Empty
```

**Path** — file system paths with validation:

```powershell
[Parameter(Mandatory = $true)]
[ValidateScript({ Test-Path $_ -PathType Leaf })]
[string]$Path
```

---
[Back to Overview](./OVERVIEW.md)
