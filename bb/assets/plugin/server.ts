import type { BbPluginApi } from "@get-bb/plugin-sdk";

export default function plugin(bb: BbPluginApi) {
  bb.providers.register({
    id: "gas-city", displayName: "Gas City", icon: "Building2",
    strings: {
      signInHint: "Run gc bb install and gc bb connect on the selected BB host.",
      expiredHint: "Run gc bb status on the selected BB host.",
      installUrl: "https://github.com/gastownhall/gascity-packs/tree/feat/bb-provider-gascity-1.4/bb",
    },
    maintenance: { health: true, usage: false, installation: false },
    capabilities: {
      permissionModes: ["full"], reasoningLevels: ["none"], fork: "none",
      supportsNativeUserQuestion: true, supportsManualCompaction: false,
      supportsThreadArchive: false, supportsThreadRename: false, supportsServiceTier: false,
    },
    composerActions: [], models: { scope: "workspace", fallback: [] },
    env: { passthrough: ["GC_BB_CONFIG", "GC_BB_AUTH_TOKEN", "XDG_CONFIG_HOME", "XDG_STATE_HOME"] },
    deriveProviderOptions(context) {
      return { projectId: context.projectId, bbThreadId: context.threadId };
    },
  });
}
