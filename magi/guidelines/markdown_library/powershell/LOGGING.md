# Logging and Observability

### Write-* Cmdlet Streams

| Stream | Cmdlet | Purpose |
|:------:|:-------|:--------|
| 1 | `Write-Output` | Primary output; pipeline data |
| 2 | `Write-Error` | Errors |
| 3 | `Write-Warning` | Warnings |
| 4 | `Write-Verbose` | Detailed status; enabled with `-Verbose` |
| 5 | `Write-Debug` | Debug info; enabled with `-Debug` |
| 6 | `Write-Information` | Informational messages with tags |

### Verbose Output

```powershell
function Get-Configuration {
    [CmdletBinding()]
    param([string]$Path)
    Write-Verbose "Loading configuration from: $Path"
    $config = Get-Content $Path | ConvertFrom-Json
    Write-Verbose "Loaded $($config.Count) configuration entries"
    return $config
}
```

### Information Stream

```powershell
Write-Information -MessageData "Process started" -Tags 'Lifecycle', 'Start'
Write-Information -MessageData @{ Step = 'Validation'; Status = 'Complete' } -Tags 'Progress'

# Capture
Get-Something -InformationVariable info
$info | Where-Object Tags -contains 'Progress'
```

### Transcript Logging

```powershell
$transcriptPath = Join-Path $PSScriptRoot "logs\transcript_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
Start-Transcript -Path $transcriptPath -Append
# Script execution
Stop-Transcript
```

### Structured Logging

```powershell
function Write-StructuredLog {
    param(
        [ValidateSet('Debug', 'Info', 'Warning', 'Error')]
        [string]$Level = 'Info',
        [string]$Message,
        [hashtable]$Properties = @{}
    )
    $logEntry = [PSCustomObject]@{
        Timestamp   = [datetime]::UtcNow.ToString('o')
        Level       = $Level
        Message     = $Message
        MachineName = $env:COMPUTERNAME
        ProcessId   = $PID
        Properties  = $Properties
    }
    $logEntry | ConvertTo-Json -Compress | Out-File -FilePath $script:LogPath -Append
}
```

---
[Back to Overview](./OVERVIEW.md)
