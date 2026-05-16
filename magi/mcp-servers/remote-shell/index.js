#!/usr/bin/env node
const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { CallToolRequestSchema, ListToolsRequestSchema } = require("@modelcontextprotocol/sdk/types.js");
const { execSync } = require("child_process");
const SSH_TIMEOUT = parseInt(process.env.MCP_SSH_TIMEOUT || "30000", 10);
const ENV_FILE = process.env.CLAUDE_REMOTE_ENV || `${process.env.HOME}/.claude/enforcement/env.remote`;
function loadRemoteEnv() {
  try {
    const out = execSync('set -a; source "$CLAUDE_REMOTE_ENV" 2>/dev/null; set +a; echo "LSP_IP=$LSP_IP"; echo "LSP_USER=$LSP_USER"; echo "LSP_PASS=$LSP_PASS"', {
      encoding: "utf-8",
      shell: "/bin/bash",
      timeout: 5000,
      env: { ...process.env, CLAUDE_REMOTE_ENV: ENV_FILE }
    });
    const vars = {};
    for (const line of out.trim().split("\n")) {
      const eq = line.indexOf("=");
      if (eq > 0) vars[line.substring(0, eq)] = line.substring(eq + 1);
    }
    return vars;
  } catch (e) {
    console.error("Failed to load remote env:", e.message);
    return {};
  }
}
const SHELL_VARS = loadRemoteEnv();
const LSP_IP = SHELL_VARS.LSP_IP || "";
const LSP_USER = SHELL_VARS.LSP_USER || "";
const LSP_PASS = SHELL_VARS.LSP_PASS || "";
const server = new Server({ name: "remote-shell", version: "1.0.0" }, { capabilities: { tools: {} } });
function sshExec(command, timeoutMs) {
  try {
    const sshCmd = `sshpass -p ${JSON.stringify(LSP_PASS)} ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no ${LSP_USER}@${LSP_IP} ${JSON.stringify(command)}`;
    const result = execSync(sshCmd, {
      encoding: "utf-8",
      timeout: timeoutMs || SSH_TIMEOUT,
      stdio: ["pipe", "pipe", "pipe"]
    });
    return { success: true, output: result.trim() };
  } catch (e) {
    return { success: false, output: e.stdout ? e.stdout.trim() : "", error: e.stderr ? e.stderr.trim() : e.message };
  }
}
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "remote_exec",
      description: "Execute a shell command on the remote host via SSH",
      inputSchema: {
        type: "object",
        properties: {
          command: { type: "string", description: "Shell command to execute on the remote host" },
          timeout_ms: { type: "number", description: "Timeout in milliseconds (default 30000)" }
        },
        required: ["command"]
      }
    },
    {
      name: "remote_file_read",
      description: "Read a file from the remote host",
      inputSchema: {
        type: "object",
        properties: {
          path: { type: "string", description: "Absolute path to the file on the remote host" },
          lines: { type: "number", description: "Max lines to read (default: all)" }
        },
        required: ["path"]
      }
    },
    {
      name: "remote_file_list",
      description: "List files in a directory on the remote host",
      inputSchema: {
        type: "object",
        properties: {
          path: { type: "string", description: "Directory path on the remote host" },
          pattern: { type: "string", description: "Optional glob pattern filter" }
        },
        required: ["path"]
      }
    },
    {
      name: "remote_service_status",
      description: "Check the status of a systemd service on the remote host",
      inputSchema: {
        type: "object",
        properties: {
          service: { type: "string", description: "Service name (e.g. ssh, docker, nginx)" }
        },
        required: ["service"]
      }
    },
    {
      name: "remote_system_info",
      description: "Get system information from the remote host (OS, uptime, memory, disk)",
      inputSchema: { type: "object", properties: {}, required: [] }
    }
  ]
}));
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  switch (name) {
    case "remote_exec": {
      const timeout = (args && args.timeout_ms) || SSH_TIMEOUT;
      const result = sshExec(args.command, timeout);
      const text = result.success
        ? result.output
        : "STDERR:\n" + (result.error || "") + "\nSTDOUT:\n" + (result.output || "");
      return { content: [{ type: "text", text: text }], isError: !result.success };
    }
    case "remote_file_read": {
      const lineLimit = (args && args.lines) ? ` | head -${args.lines}` : "";
      const result = sshExec(`cat ${JSON.stringify(args.path)}${lineLimit}`);
      return { content: [{ type: "text", text: result.success ? result.output : "Error: " + result.error }], isError: !result.success };
    }
    case "remote_file_list": {
      const pattern = (args && args.pattern) ? `/${args.pattern}` : "";
      const result = sshExec(`ls -la ${JSON.stringify(args.path + pattern)} 2>/dev/null`);
      return { content: [{ type: "text", text: result.success ? result.output : "Error: " + result.error }], isError: !result.success };
    }
    case "remote_service_status": {
      const result = sshExec(`systemctl status ${args.service} 2>&1 | head -20`);
      return { content: [{ type: "text", text: result.success ? result.output : result.error || result.output }] };
    }
    case "remote_system_info": {
      const result = sshExec("echo '=== OS ===' && uname -a && echo '=== Uptime ===' && uptime && echo '=== Memory ===' && free -h && echo '=== Disk ===' && df -h / && echo '=== CPU ===' && nproc && echo '=== Load ===' && cat /proc/loadavg");
      return { content: [{ type: "text", text: result.success ? result.output : "Error: " + result.error }] };
    }
    default:
      return { content: [{ type: "text", text: "Unknown tool: " + name }], isError: true };
  }
});
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("remote-shell MCP server running on stdio");
}
main().catch((e) => { console.error("Fatal:", e); process.exit(1); });
