# Removed APIs

Audit for and remove every reference during 8.1→8.3 migration:

| Area | Removed Items |
|:-----|:--------------|
| **Common API** | `SecurityUtils#decryptRSA`, `getKeyParameter`, `getPrivateKeyParameter`, `asymmetricSign`, `generateDESedKey` |
| **Gateway API** | `SystemMap`, `GatewayModuleHook#updateSystemMap`, `RedundancyManager.getPeerSystemMap`; `GatewayContext#getLaunchManager`; `LaunchDescriptor`, `LaunchFlavor`, `LaunchHandler`, `LaunchManager`; `SmtpManager` (and accessor on `GatewayContext`); `EmailProfilerManager` |
| **Redundancy** | `RuntimeStateProvider` (replaced by `SnapshotStateProvider`) |
| **OPC driver** | `com.inductiveautomation.xopc.driver.api.*` — entire package removed (`Driver`, `DriverType`, `DeviceType`) |
| **Perspective** | `EventBus` — entirely removed; migrate to `EventManager` (interface-compatible) |
| **Security internals** | `gateway.auth.adapter.AuthAdapter`, `gateway.config.AbstractTypedConfig`, `gateway.http.HttpRequest`, `gateway.mapper.attr.*` (`UserAttributeMapperConfig`, `AttributeMapper`, `AttributeMapperAdapter`, etc.), `gateway.security.level.policy.*` (`DerivedSecurityLevelPolicy` and adjacent), `gateway.user.UserAttribute`, `gateway.web.attr/response/session/state/strategy.*` — all moved from `gateway-api` to `gateway` and removed from public API |
| **EAM async** | `BackupService#requestGatewayBackup` → `requestGatewayBackupAsync`; `streamGatewayBackup`; `requestModules` → `requestModulesAsync`; `restoreBackup` → `restoreBackupAsync`; `InfoService#getControllers`; `InfoService#getRemoteServers`; `SendTagsService#importTags`; `UpgradeService#triggerUpgrade` → `triggerUpgradeAsync` |
| **Gson serializers** | `gateway.web.pages.status.serializers` and `config.serializers` moved to `gateway.web.serializers` |
| **Gateway Network naming** | `GatewayAreaNetworkManager` → `GatewayNetworkManager`; `GatewayAreaNetworkManagerImpl` → `GatewayNetworkManagerImpl` |
| **Routes** | `system/projectlist` split into `system/launchDesigner` and `system/launchVision` (the latter only available with Vision installed). Both now return JSON |

---
[Back to Overview](./OVERVIEW.md)
