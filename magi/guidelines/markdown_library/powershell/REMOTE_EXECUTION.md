# Remote Execution and Sessions

### Prerequisites

```powershell
# Windows
Enable-PSRemoting -Force

# Linux/macOS (SSH-based) — configure SSH subsystem in sshd_config
```

### Invoke-Command

```powershell
$results = Invoke-Command -ComputerName 'Server01', 'Server02' -ScriptBlock {
    Get-Service -Name 'W32Time'
} -Credential $credential
```

For SSH remoting (PowerShell 7+):

```powershell
Invoke-Command -HostName 'linux-server' -UserName 'admin' -ScriptBlock {
    Get-Process
}
```

### Persistent Sessions

```powershell
$session = New-PSSession -ComputerName 'Server01' -Credential $credential
Invoke-Command -Session $session -ScriptBlock { Get-Process }
Invoke-Command -Session $session -ScriptBlock { Get-Service }
Remove-PSSession -Session $session
```

### Session Configuration

```powershell
$sessionConfig = @{
    SessionType      = 'RestrictedRemoteServer'
    ModulesToImport  = 'ActiveDirectory'
    VisibleCmdlets   = 'Get-ADUser', 'Get-ADGroup'
    VisibleFunctions = 'TabExpansion2'
}
New-PSSessionConfigurationFile -Path '.\HelpDeskEndpoint.pssc' @sessionConfig
Register-PSSessionConfiguration -Name 'HelpDesk' -Path '.\HelpDeskEndpoint.pssc'
```

### Throttling and Error Handling

```powershell
$results = Invoke-Command -ComputerName $servers -ScriptBlock {
    Get-EventLog -LogName System -Newest 100
} -ThrottleLimit 10 -ErrorAction SilentlyContinue -ErrorVariable remoteErrors

foreach ($err in $remoteErrors) {
    Write-Warning "Failed on $($err.TargetObject): $($err.Exception.Message)"
}
```

---
[Back to Overview](./OVERVIEW.md)
