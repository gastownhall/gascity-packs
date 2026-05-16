# PowerShell 7+ Features

### Null Coalescing

```powershell
$value = $config.Setting ?? 'DefaultValue'
$result ??= Get-DefaultResult
```

### Ternary Operator

```powershell
$status = $isOnline ? 'Online' : 'Offline'
```

### Pipeline Chain Operators

```powershell
Test-Connection Server01 && Write-Output 'Server is reachable'
Test-Connection Server01 || Write-Warning 'Server unreachable'
```

---
[Back to Overview](./OVERVIEW.md)
