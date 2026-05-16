# Extension Points

The 8.1 extension point system. Modules contribute new implementations of platform-defined abstractions.

### Extension Point Families

| Family | Type |
|:-------|:-----|
| Alarm notification | `AlarmNotificationProfile` + `ExtensionPoint<Settings extends PersistentRecord>` |
| Audit | `AuditProfile` + `AuditProfileType` |
| Tag history | `HistoryProvider` |
| Tag realtime | `RealtimeTagProvider` (custom tag namespaces) |
| User source | LDAP, AD, custom |
| OPC device | `DriverType` + `DeviceType` (replaced in 8.3 by `DeviceExtensionPoint`) |
| Schedule | Schedule provider |

### Extension Point Implementation Pattern (8.1)

| Step | Action |
|:-----|:-------|
| 1 | Define a `PersistentRecord` subclass with the type-specific settings fields plus a foreign key to the parent profile record |
| 2 | Implement the platform interface (e.g., `AlarmNotificationProfile`). Constructor receives `GatewayContext` and the settings record |
| 3 | Subclass platform-provided `ExtensionPointType` (e.g., `AlarmNotificationProfileType`). Override `getRecordClass()` and `createNewProfile()` |
| 4 | Add to `GatewayHook.getExtensionPoints()`: `return List.of(new MyExtensionPointType())` |

---
[Back to Overview](./OVERVIEW.md)
