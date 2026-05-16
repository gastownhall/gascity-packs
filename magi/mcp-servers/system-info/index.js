#!/usr/bin/env node
const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { CallToolRequestSchema, ListToolsRequestSchema } = require("@modelcontextprotocol/sdk/types.js");
const { execSync } = require("child_process");
const os = require("os");
const fs = require("fs");
const path = require("path");
const server = new Server({ name: "system-info", version: "1.0.0" }, { capabilities: { tools: {} } });
function runCommand(cmd, timeoutMs) {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: timeoutMs || 10000, stdio: ["pipe", "pipe", "pipe"] }).trim();
  } catch (e) {
    return "Error: " + (e.message || "command failed");
  }
}
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "system_overview",
      description: "Get system overview: OS, hostname, uptime, CPU, memory, disk usage",
      inputSchema: { type: "object", properties: {}, required: [] }
    },
    {
      name: "process_list",
      description: "List running processes sorted by CPU or memory usage",
      inputSchema: {
        type: "object",
        properties: {
          sort_by: { type: "string", enum: ["cpu", "memory"], description: "Sort by cpu or memory usage" },
          limit: { type: "number", description: "Max processes to return (default 20)" }
        },
        required: []
      }
    },
    {
      name: "disk_usage",
      description: "Show disk usage for all mounted filesystems",
      inputSchema: { type: "object", properties: {}, required: [] }
    },
    {
      name: "network_info",
      description: "Show network interfaces and their addresses",
      inputSchema: { type: "object", properties: {}, required: [] }
    },
    {
      name: "check_port",
      description: "Check if a specific port is in use and what process is using it",
      inputSchema: {
        type: "object",
        properties: { port: { type: "number", description: "Port number to check" } },
        required: ["port"]
      }
    },
    {
      name: "environment_info",
      description: "Show environment variables (filtered, no secrets)",
      inputSchema: {
        type: "object",
        properties: { filter: { type: "string", description: "Filter env vars by prefix (e.g. PATH, NODE, PYTHON)" } },
        required: []
      }
    },
    {
      name: "installed_tools",
      description: "Check which development tools are installed and their versions",
      inputSchema: { type: "object", properties: {}, required: [] }
    }
  ]
}));
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  switch (name) {
    case "system_overview": {
      const cpus = os.cpus();
      const totalMem = os.totalmem();
      const freeMem = os.freemem();
      const usedMem = totalMem - freeMem;
      const info = {
        hostname: os.hostname(),
        platform: os.platform(),
        arch: os.arch(),
        os_release: os.release(),
        os_type: os.type(),
        uptime_hours: Math.round(os.uptime() / 3600 * 100) / 100,
        cpu_model: cpus[0] ? cpus[0].model : "unknown",
        cpu_cores: cpus.length,
        memory_total_gb: Math.round(totalMem / 1073741824 * 100) / 100,
        memory_used_gb: Math.round(usedMem / 1073741824 * 100) / 100,
        memory_free_gb: Math.round(freeMem / 1073741824 * 100) / 100,
        memory_usage_percent: Math.round(usedMem / totalMem * 10000) / 100,
        load_average: os.loadavg(),
        home_dir: os.homedir(),
        user: os.userInfo().username
      };
      return { content: [{ type: "text", text: JSON.stringify(info, null, 2) }] };
    }
    case "process_list": {
      const sortBy = (args && args.sort_by) || "cpu";
      const limit = (args && args.limit) || 20;
      const sortFlag = sortBy === "memory" ? "-m" : "-r";
      const platform = os.platform();
      let output;
      if (platform === "darwin") {
        output = runCommand(`ps aux ${sortFlag} | head -${limit + 1}`, 10000);
      } else {
        const sortCol = sortBy === "memory" ? "--sort=-rss" : "--sort=-pcpu";
        output = runCommand(`ps aux ${sortCol} | head -${limit + 1}`, 10000);
      }
      return { content: [{ type: "text", text: output }] };
    }
    case "disk_usage": {
      const output = runCommand("df -h", 10000);
      return { content: [{ type: "text", text: output }] };
    }
    case "network_info": {
      const platform = os.platform();
      let output;
      if (platform === "darwin") {
        output = runCommand("ifconfig 2>/dev/null | grep -E '(^[a-z]|inet )' | head -40", 10000);
      } else {
        output = runCommand("ip -4 addr show 2>/dev/null || ifconfig 2>/dev/null | grep -E '(^[a-z]|inet )' | head -40", 10000);
      }
      const interfaces = os.networkInterfaces();
      const parsed = {};
      for (const [iface, addrs] of Object.entries(interfaces)) {
        parsed[iface] = addrs.filter(a => !a.internal).map(a => ({ address: a.address, family: a.family, mac: a.mac }));
      }
      return { content: [{ type: "text", text: "Raw:\n" + output + "\n\nParsed:\n" + JSON.stringify(parsed, null, 2) }] };
    }
    case "check_port": {
      const port = args.port;
      const platform = os.platform();
      let output;
      if (platform === "darwin") {
        output = runCommand(`lsof -i :${port} 2>/dev/null || echo "Port ${port} is not in use"`, 10000);
      } else {
        output = runCommand(`ss -tlnp sport = :${port} 2>/dev/null || netstat -tlnp 2>/dev/null | grep :${port} || echo "Port ${port} is not in use"`, 10000);
      }
      return { content: [{ type: "text", text: output }] };
    }
    case "environment_info": {
      const filter = (args && args.filter) || "";
      const env = process.env;
      const secretPatterns = /password|secret|token|key|credential|auth/i;
      const filtered = {};
      for (const [k, v] of Object.entries(env)) {
        if (filter && !k.toLowerCase().startsWith(filter.toLowerCase())) { continue; }
        if (secretPatterns.test(k)) {
          filtered[k] = "***REDACTED***";
        } else {
          filtered[k] = v;
        }
      }
      return { content: [{ type: "text", text: JSON.stringify(filtered, null, 2) }] };
    }
    case "installed_tools": {
      const tools = [
        { name: "node", cmd: "node --version" },
        { name: "npm", cmd: "npm --version" },
        { name: "python3", cmd: "python3 --version" },
        { name: "pip3", cmd: "pip3 --version" },
        { name: "go", cmd: "go version" },
        { name: "rustc", cmd: "rustc --version" },
        { name: "cargo", cmd: "cargo --version" },
        { name: "dotnet", cmd: "dotnet --version" },
        { name: "java", cmd: "java -version 2>&1 | head -1" },
        { name: "git", cmd: "git --version" },
        { name: "docker", cmd: "docker --version" },
        { name: "kubectl", cmd: "kubectl version --client --short 2>/dev/null || kubectl version --client 2>/dev/null | head -1" },
        { name: "brew", cmd: "brew --version 2>/dev/null | head -1" },
        { name: "shellcheck", cmd: "shellcheck --version 2>/dev/null | head -2" },
        { name: "jq", cmd: "jq --version" },
        { name: "curl", cmd: "curl --version 2>/dev/null | head -1" },
        { name: "ssh", cmd: "ssh -V 2>&1" }
      ];
      const results = {};
      for (const tool of tools) {
        const ver = runCommand(tool.cmd, 5000);
        results[tool.name] = ver.startsWith("Error") ? "not installed" : ver;
      }
      return { content: [{ type: "text", text: JSON.stringify(results, null, 2) }] };
    }
    default:
      return { content: [{ type: "text", text: "Unknown tool: " + name }], isError: true };
  }
});
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("system-info MCP server running on stdio");
}
main().catch((e) => { console.error("Fatal:", e); process.exit(1); });
