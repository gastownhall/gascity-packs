import { createBridgeIo, experimental_defineProviderBridge } from "@get-bb/plugin-sdk/provider-bridge";
import { GasCityProvider } from "./provider.js";
const io = createBridgeIo<any>();
const provider = new GasCityProvider({ send: message => io.send(message) });
export const experimental_providerBridge = experimental_defineProviderBridge({
  handleLine: line => provider.handleLine(line),
  onClose: () => provider.close(),
});
