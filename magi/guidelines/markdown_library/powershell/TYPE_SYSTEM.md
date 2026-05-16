# Type System and Output

### Type Declarations

```powershell
function Get-ProcessMemory {
    [OutputType([PSCustomObject])]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProcessName
    )
    [PSCustomObject]@{
        Name         = $ProcessName
        WorkingSetMB = [math]::Round((Get-Process -Name $ProcessName).WorkingSet64 / 1MB, 2)
        Timestamp    = [datetime]::UtcNow
    }
}
```

### OutputType Attribute

```powershell
[OutputType([System.ServiceProcess.ServiceController])]
[OutputType([PSCustomObject], ParameterSetName = 'Custom')]
```

Multiple `OutputType` attributes for functions returning different types based on parameter sets or conditions.

### Custom Object Creation

```powershell
[PSCustomObject]@{
    ComputerName       = $env:COMPUTERNAME
    OSVersion          = [Environment]::OSVersion.Version
    PowerShellVersion  = $PSVersionTable.PSVersion
    Uptime             = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
}
```

For repeated object creation, define a class:

```powershell
class ServerInventory {
    [string]$Name
    [string]$IPAddress
    [string]$OperatingSystem
    [datetime]$LastContact
    [bool]$IsOnline

    ServerInventory([string]$name, [string]$ip) {
        $this.Name = $name
        $this.IPAddress = $ip
        $this.LastContact = [datetime]::UtcNow
    }
}
```

### Type Accelerators

| Accelerator | Full Type |
|:------------|:----------|
| `[string]` | `System.String` |
| `[int]` | `System.Int32` |
| `[long]` | `System.Int64` |
| `[bool]` | `System.Boolean` |
| `[datetime]` | `System.DateTime` |
| `[array]` | `System.Array` |
| `[hashtable]` | `System.Collections.Hashtable` |
| `[psobject]` | `System.Management.Automation.PSObject` |
| `[regex]` | `System.Text.RegularExpressions.Regex` |
| `[xml]` | `System.Xml.XmlDocument` |
| `[ipaddress]` | `System.Net.IPAddress` |
| `[uri]` | `System.Uri` |
| `[version]` | `System.Version` |
| `[guid]` | `System.Guid` |
| `[securestring]` | `System.Security.SecureString` |
| `[pscredential]` | `System.Management.Automation.PSCredential` |

### Generic Collections

```powershell
$list  = [System.Collections.Generic.List[string]]::new()
$dict  = [System.Collections.Generic.Dictionary[string, int]]::new()
$queue = [System.Collections.Generic.Queue[PSCustomObject]]::new()
```

Generic lists outperform arrays for append-heavy operations. Arrays require reallocation on every addition; generic lists amortize allocation costs.

---
[Back to Overview](./OVERVIEW.md)
