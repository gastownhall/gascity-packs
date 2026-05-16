# Performance Optimization

### Collection Operations

```powershell
# Slow: Array reallocation every iteration
$results = @()
foreach ($item in $largeCollection) {
    $results += Process-Item $item
}

# Fast: Generic list with pre-allocated capacity
$results = [System.Collections.Generic.List[PSCustomObject]]::new($largeCollection.Count)
foreach ($item in $largeCollection) {
    $results.Add((Process-Item $item))
}
```

### String Operations

```powershell
$sb = [System.Text.StringBuilder]::new()
foreach ($line in $lines) {
    [void]$sb.AppendLine($line)
}
$result = $sb.ToString()
```

### Hashtable Lookups

```powershell
# Slow: O(n) search for each lookup
$users = Get-ADUser -Filter *
foreach ($id in $userIds) {
    $user = $users | Where-Object SamAccountName -eq $id
}

# Fast: O(1) hashtable lookup
$userHash = @{}
Get-ADUser -Filter * | ForEach-Object { $userHash[$_.SamAccountName] = $_ }
foreach ($id in $userIds) {
    $user = $userHash[$id]
}
```

### Pipeline vs Direct Invocation

```powershell
# Slower: Pipeline overhead per item
$files | ForEach-Object { $_.Name.ToUpper() }

# Faster: Direct method call
foreach ($file in $files) { $file.Name.ToUpper() }
```

### Parallel Processing

```powershell
$servers | ForEach-Object -Parallel {
    Test-Connection -ComputerName $_ -Count 1 -Quiet
} -ThrottleLimit 10
```

`-ThrottleLimit` controls concurrency. Default is 5. Too high risks resource exhaustion; too low underutilizes capacity.

### Runspace Pools

```powershell
$pool = [RunspaceFactory]::CreateRunspacePool(1, 10)
$pool.Open()

$jobs = foreach ($server in $servers) {
    $ps = [PowerShell]::Create().AddScript({ param($s) Test-Connection $s -Count 1 }).AddParameter('s', $server)
    $ps.RunspacePool = $pool
    @{ PowerShell = $ps; Handle = $ps.BeginInvoke() }
}

$results = foreach ($job in $jobs) {
    $job.PowerShell.EndInvoke($job.Handle)
    $job.PowerShell.Dispose()
}

$pool.Close()
$pool.Dispose()
```

---
[Back to Overview](./OVERVIEW.md)
