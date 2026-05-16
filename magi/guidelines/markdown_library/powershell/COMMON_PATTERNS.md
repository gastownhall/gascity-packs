# Common Patterns and Idioms

### Splatting

```powershell
$params = @{
    ComputerName = 'Server01'
    Credential   = $credential
    ScriptBlock  = { Get-Service }
    ErrorAction  = 'Stop'
}
Invoke-Command @params
```

### Here-Strings

```powershell
$query = @"
SELECT *
FROM Users
WHERE Active = 1
ORDER BY LastName
"@

$json = @'
{
    "name": "value",
    "count": 42
}
'@
```

Double-quoted here-strings (`@"..."@`) expand variables; single-quoted (`@'...'@`) are literal.

### Calculated Properties

```powershell
Get-Process | Select-Object Name, @{
    Name       = 'MemoryMB'
    Expression = { [math]::Round($_.WorkingSet64 / 1MB, 2) }
}
```

### Progress Reporting

```powershell
$items = Get-ChildItem -Recurse
for ($i = 0; $i -lt $items.Count; $i++) {
    $percent = [math]::Round(($i / $items.Count) * 100)
    Write-Progress -Activity 'Processing files' -Status "$($items[$i].Name)" -PercentComplete $percent
    Process-Item $items[$i]
}
Write-Progress -Activity 'Processing files' -Completed
```

---
[Back to Overview](./OVERVIEW.md)
