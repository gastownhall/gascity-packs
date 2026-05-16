# Pipeline and Object Orientation

### Pipeline Processing

```powershell
function ConvertTo-HashedPassword {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [SecureString]$Password
    )
    begin {
        $hasher = [System.Security.Cryptography.SHA256]::Create()
    }
    process {
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
        try {
            $plainText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
            $bytes     = [System.Text.Encoding]::UTF8.GetBytes($plainText)
            $hash      = $hasher.ComputeHash($bytes)
            [Convert]::ToBase64String($hash)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }
    end {
        $hasher.Dispose()
    }
}
```

| Block | Purpose |
|:------|:--------|
| `begin` | Initialize resources used across all pipeline items. Runs once before first item |
| `process` | Handle each pipeline item. Runs once per input object |
| `end` | Finalize processing, clean up resources, emit aggregated results. Runs once after last item |

### Pipeline Input Binding

```powershell
[Parameter(ValueFromPipeline = $true)]
[string[]]$Name
```

Accepts: `Get-Content names.txt | MyFunction` or `MyFunction -Name 'value1', 'value2'`.

```powershell
[Parameter(ValueFromPipelineByPropertyName = $true)]
[Alias('FullName')]
[string]$Path
```

Accepts: `Get-ChildItem | MyFunction` (binds `FullName` property to `-Path`).

### Emitting Output

Emit objects directly; avoid `return` for single values:

```powershell
process {
    [PSCustomObject]@{
        Input     = $_
        Processed = Transform-Data $_
        Timestamp = [datetime]::UtcNow
    }
}
```

Use `Write-Output` explicitly when clarity requires it. Avoid it when the expression result naturally emits.

### Pipeline Operators

```powershell
Get-Service |
    Where-Object Status -eq 'Running' |
    Sort-Object DisplayName |
    Select-Object Name, DisplayName, StartType |
    Export-Csv -Path 'services.csv' -NoTypeInformation
```

### ForEach-Object vs foreach Statement

| Pattern | When |
|:--------|:-----|
| `ForEach-Object` | Pipeline-aware, streaming, lower memory for large collections |
| `foreach` statement | Faster for in-memory collections, no pipeline overhead |

```powershell
# Streaming
Get-Content largefile.txt | ForEach-Object { Process-Line $_ }

# In-memory
$items = Get-ChildItem
foreach ($item in $items) {
    Process-Item $item
}
```

---
[Back to Overview](./OVERVIEW.md)
