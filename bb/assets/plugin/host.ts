import { experimental_defineHostEntry } from "@get-bb/plugin-sdk/host";
export { experimental_providerBridge } from "./src/bridge.js";
import { launcherHostContract } from "./src/launcher-contract.js";
import { createLauncherHostHandlers } from "./src/launcher-host.js";
export default experimental_defineHostEntry({ contract: launcherHostContract, handlers: createLauncherHostHandlers() });
