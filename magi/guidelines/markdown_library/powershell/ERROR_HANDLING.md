# Error Handling

### Philosophy

PowerShell distinguishes **terminating** and **non-terminating** errors. Terminating errors halt execution; non-terminating errors report problems and continue. **Explicit error handling strategy is mandatory** — implicit behavior varies by cmdlet and `-ErrorAction` preference.

### ErrorAction Preference

```powershell
$ErrorActionPreference = 'Stop'
```

Converts non-terminating errors to terminating, enabling consistent `try`/`catch` handling. Override per-command when continuation is intentional:

```powershell
Get-Service -Name 'NonExistent' -ErrorAction SilentlyContinue
```

### Try-Catch-Finally

```powershell
try {
    $connection = Connect-SqlServer -ServerInstance $Server -Database $Database
    $result = Invoke-SqlQuery -Connection $connection -Query $Query
    return $result
}
catch [System.Data.SqlClient.SqlException] {
    Write-Error "Database query failed: $($_.Exception.Message)"
    throw
}
catch {
    Write-Error "Unexpected error: $($_.Exception.Message)"
    throw
}
finally {
    if ($connection) {
        $connection.Dispose()
    }
}
```

### Typed Exception Handling

Catch specific exception types before general catches:

```powershell
catch [System.Net.WebException] {
    # Network-specific recovery
}
catch [System.UnauthorizedAccessException] {
    # Permission-specific messaging
}
catch [System.Exception] {
    # General fallback
}
```

### Throwing Errors

```powershell
if (-not (Test-Path $ConfigPath)) {
    throw [System.IO.FileNotFoundException]::new("Configuration file not found: $ConfigPath")
}
```

Use `Write-Error` for non-terminating errors that should be reported but not halt execution:

```powershell
foreach ($item in $Items) {
    if (-not (Test-Validity $item)) {
        Write-Error "Invalid item: $($item.Name)" -TargetObject $item
        continue
    }
    Process-Item $item
}
```

### Error Records

```powershell
catch {
    $errorRecord = $_
    Write-Warning "Exception Type: $($errorRecord.Exception.GetType().FullName)"
    Write-Warning "Message: $($errorRecord.Exception.Message)"
    Write-Warning "Target: $($errorRecord.TargetObject)"
    Write-Warning "Position: $($errorRecord.InvocationInfo.PositionMessage)"
}
```

### ShouldProcess for State Changes

```powershell
function Remove-OldLogFiles {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
    param([string]$Path, [int]$DaysOld = 30)

    $cutoff = (Get-Date).AddDays(-$DaysOld)
    $files = Get-ChildItem -Path $Path -Filter '*.log' | Where-Object LastWriteTime -lt $cutoff

    foreach ($file in $files) {
        if ($PSCmdlet.ShouldProcess($file.FullName, 'Delete log file')) {
            Remove-Item -Path $file.FullName -Force
        }
    }
}
```

Users preview with `-WhatIf` and control confirmation with `-Confirm`.

---
[Back to Overview](./OVERVIEW.md)
