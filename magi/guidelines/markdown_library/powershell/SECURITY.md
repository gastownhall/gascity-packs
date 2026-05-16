# Security Practices

### Credential Handling

```powershell
$credential = Get-Credential -Message 'Enter service account credentials'

# Store credential securely (Windows; tied to user + machine)
$credential | Export-Clixml -Path "$env:USERPROFILE\cred.xml"
$credential = Import-Clixml -Path "$env:USERPROFILE\cred.xml"
```

`Export-Clixml` credentials are tied to the user and machine that created them — not portable, which is the point.

**Forbidden:**

- Plain text passwords in scripts.
- Credentials in source control.
- Unencrypted credential files.

### SecureString Usage

```powershell
$securePassword = Read-Host -Prompt 'Enter password' -AsSecureString

# When plain text is unavoidable (API requirements)
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    # Use $plainPassword immediately
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
```

### SecretManagement Module

```powershell
Import-Module Microsoft.PowerShell.SecretManagement
$secret = Get-Secret -Name 'APIKey' -Vault 'Production'
```

Use the SecretManagement module for sensitive data. Vault-backed access removes credential storage from script-level concerns.

### Execution Policy

| Policy | Description |
|:-------|:------------|
| `Restricted` | No scripts execute; interactive only |
| `AllSigned` | All scripts must be signed by trusted publisher |
| `RemoteSigned` | Downloaded scripts require signature; local scripts run freely |
| `Unrestricted` | All scripts run with warning prompts for downloaded scripts |
| `Bypass` | No restrictions; no warnings |

Production servers: `AllSigned` or `RemoteSigned`. Development: `RemoteSigned`. **Never `Bypass` in production.**

### Code Signing

```powershell
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert
Set-AuthenticodeSignature -FilePath 'script.ps1' -Certificate $cert -TimestampServer 'http://timestamp.digicert.com'
```

Verify signatures before execution:

```powershell
$sig = Get-AuthenticodeSignature -FilePath 'script.ps1'
if ($sig.Status -ne 'Valid') {
    throw "Script signature invalid: $($sig.StatusMessage)"
}
```

### Input Validation

```powershell
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9_-]+$')]
    [string]$ServerName,

    [Parameter(Mandatory = $true)]
    [ValidateScript({ $_ -gt 0 -and $_ -le 65535 })]
    [int]$Port
)
```

**Never pass unvalidated input to `Invoke-Expression`, `Start-Process`, or any command that interprets strings as code.**

### Sensitive Data in Logs

```powershell
# Bad: Password visible in logs
Write-Verbose "Connecting with password: $password"

# Good: Mask sensitive values
Write-Verbose "Connecting with password: ********"
```

Use `[System.Management.Automation.PSCredential]` parameter type — PowerShell automatically masks credential display.

---
[Back to Overview](./OVERVIEW.md)
