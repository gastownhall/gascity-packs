# MCP Server Infrastructure

Model Context Protocol (MCP) server infrastructure for Claude Code. This system provides 21 MCP servers -- 8 local and 13 remote -- extending Claude Code with specialized tools for file operations, code intelligence, database access, web search, version control, and remote server management.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Architecture Diagram](#architecture-diagram)
- [Server Inventory](#server-inventory)
- [Configuration Files](#configuration-files)
- [Local Custom Servers](#local-custom-servers)
- [Remote Server Architecture](#remote-server-architecture)
- [Credential Management](#credential-management)
- [Installation](#installation)
- [How Claude Code Uses MCP Servers](#how-claude-code-uses-mcp-servers)

---

## Architecture Overview

```
                       Claude Code (macOS)
                              |
               +--------------+--------------+
               |                             |
        Local Servers (8)            Remote Servers (13)
               |                             |
    +----------+----------+          SSH via sshpass
    |          |          |                  |
  Custom    npx-based   Guidelines    Ubuntu 24.04 Server
  Node.js   packages    XML files    /home/$LSP_USER/.local/bin/
  servers                                    |
                                 +-----------+-----------+
                                 |           |           |
                              npx-based   pip-based   Go binary
                              wrappers    wrappers    (Gitea)
```

---

## Architecture Diagram

A full Mermaid diagram of the MCP architecture is available at [`mcp-architecture.mmd`](./mcp-architecture.mmd). It covers the complete flow from Claude Code startup through credential sourcing, SSH transport, and all 21 servers (8 local + 13 remote) with their underlying technologies.

To render the diagram, open the `.mmd` file in any Mermaid-compatible viewer (VS Code with the Mermaid extension, GitHub's built-in renderer, or [mermaid.live](https://mermaid.live)).

---

The local machine (macOS) runs 4 custom Node.js MCP servers and 4 npx-based community servers. The remote machine (Ubuntu 24.04) hosts 13 MCP servers accessed over SSH tunnels using `sshpass` for non-interactive authentication. All credentials and connection details live in a single file: `~/.claude/enforcement/env.remote`.

---

## Server Inventory

| # | Server Name | Type | Technology | Description |
|---|-------------|------|------------|-------------|
| 1 | `guidelines-retriever` | Local (custom) | Node.js | Retrieves coding guidelines from `~/.claude/guidelines/*.xml` files. Provides 5 tools and resource URIs. |
| 2 | `project-memory` | Local (custom) | Node.js | Manages project-specific memory/context with markdown files and frontmatter. Provides 8 tools and 3 resources. |
| 3 | `system-info` | Local (custom) | Node.js | Reports local system information: OS, CPU, memory, disk, network, ports, processes, installed tools. Provides 7 tools. |
| 4 | `remote-shell` | Local (custom) | Node.js | Executes commands on the remote host via SSH using `sshpass`. Provides 5 tools. |
| 5 | `filesystem-local` | Local (npx) | `@modelcontextprotocol/server-filesystem` | Local filesystem operations scoped to `$HOME`. |
| 6 | `sequential-thinking` | Local (npx) | `@modelcontextprotocol/server-sequential-thinking` | Structured sequential reasoning and problem decomposition. |
| 7 | `memory-local` | Local (npx) | `@modelcontextprotocol/server-memory` | Knowledge graph memory for entities, relations, and observations. |
| 8 | `everything-local` | Local (npx) | `@modelcontextprotocol/server-everything` | Reference/testing MCP server with example tools and resources. |
| 9 | `remote-filesystem` | Remote | `@modelcontextprotocol/server-filesystem` | Remote filesystem operations scoped to `/home/$LSP_USER`. |
| 10 | `remote-memory` | Remote | `@modelcontextprotocol/server-memory` | Knowledge graph memory on the remote server. |
| 11 | `remote-fetch` | Remote | `mcp-server-fetch` (pip) | HTTP fetch/web scraping from the remote server via `python3 -m mcp_server_fetch`. |
| 12 | `remote-git` | Remote | `mcp-server-git` (pip) | Git repository operations via `python3 -m mcp_server_git`. |
| 13 | `remote-sqlite` | Remote | `mcp-server-sqlite` (pip) | SQLite database operations via `python3 -m mcp_server_sqlite`. |
| 14 | `remote-sequential-thinking` | Remote | `@modelcontextprotocol/server-sequential-thinking` | Sequential reasoning on the remote server. |
| 15 | `remote-everything` | Remote | `@modelcontextprotocol/server-everything` | Reference MCP server on the remote host. |
| 16 | `remote-brave-search` | Remote | `@modelcontextprotocol/server-brave-search` | Web search via Brave Search API. Passes `BRAVE_API_KEY` as env var. |
| 17 | `remote-github` | Remote | `@modelcontextprotocol/server-github` | GitHub API operations. Passes `GITHUB_PERSONAL_ACCESS_TOKEN` as env var. |
| 18 | `remote-puppeteer` | Remote | `@modelcontextprotocol/server-puppeteer` | Headless browser automation via Puppeteer on the remote server. |
| 19 | `remote-postgres` | Remote | `@modelcontextprotocol/server-postgres` | PostgreSQL database operations against the `claude_mcp` database owned by user `${LSP_USER}`. |
| 20 | `remote-gitea` | Remote | Official Gitea MCP Go binary (v1.0.0) | Gitea API operations. Uses `GITEA_ACCESS_TOKEN` + `GITEA_HOST` env vars and CLI args `-t stdio --token ... --host ...`. |
| 21 | `remote-context7` | Remote | `@anthropic-ai/mcp-server-context7` | Context7 library documentation lookup. |

---

## Configuration Files

### `.mcp.json` -- Server Definitions

**Location:** `~/.claude/.mcp.json`

This file defines all 21 MCP server entries. Claude Code reads this file at startup to discover available servers.

Each entry follows one of three patterns:

**Pattern 1 -- Custom local Node.js server:**

```json
{
  "guidelines-retriever": {
    "command": "node",
    "args": ["~/.claude/mcp-servers/guidelines-retriever/index.js"]
  }
}
```

**Pattern 2 -- npx-based local server:**

```json
{
  "filesystem-local": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "~"]
  }
}
```

**Pattern 3 -- SSH-tunneled remote server:**

```json
{
  "remote-memory": {
    "command": "bash",
    "args": [
      "-c",
      "set -a; source ~/.claude/enforcement/env.remote 2>/dev/null; set +a; exec sshpass -p \"${LSP_PASS}\" ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=120 \"${LSP_USER}@${LSP_IP}\" \"/home/${LSP_USER}/.local/bin/mcp-memory\""
    ]
  }
}
```

### `settings.json` -- Enabled Servers

**Location:** `~/.claude/settings.json`

Lists all 21 server names in the `enabledMcpjsonServers` array and sets `enableAllProjectMcpServers: true`. Relevant fields:

```json
{
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": [
    "guidelines-retriever",
    "project-memory",
    "system-info",
    "remote-shell",
    "filesystem-local",
    "sequential-thinking",
    "memory-local",
    "everything-local",
    "remote-filesystem",
    "remote-memory",
    "remote-fetch",
    "remote-git",
    "remote-sqlite",
    "remote-sequential-thinking",
    "remote-everything",
    "remote-brave-search",
    "remote-github",
    "remote-puppeteer",
    "remote-postgres",
    "remote-gitea",
    "remote-context7"
  ]
}
```

---

## Local Custom Servers

All four custom servers are Node.js applications located at `~/.claude/mcp-servers/<name>/index.js`. Each depends on `@modelcontextprotocol/sdk` and communicates via stdio transport.

### guidelines-retriever

**Path:** `~/.claude/mcp-servers/guidelines-retriever/index.js`

Reads coding guideline XML files from `~/.claude/guidelines/`. Supports language-to-guideline mapping (e.g., `"python"` -> `python_guidelines.xml`, `"tsx"` -> `frontend_guidelines.xml`).

**Tools (5):**

| Tool | Description |
|------|-------------|
| `list_guidelines` | Lists all available guideline XML files with domain, language, version, and file size. |
| `get_guideline` | Returns full XML content of a specific guideline file by name (without `.xml` extension). |
| `search_guidelines` | Case-insensitive keyword search across all guideline files with context lines. |
| `get_rules` | Extracts `<rule>` elements, filterable by severity (`error`/`warning`/`info`), section, or guideline file. |
| `get_guideline_for_language` | Smart lookup by file extension or language name (e.g., `"py"`, `".py"`, `"python"` all resolve to `python_guidelines`). |

**Resources:** Each guideline file is exposed as a `guidelines://<name>` resource URI. A `guidelines://list` resource returns JSON metadata for all files.

### project-memory

**Path:** `~/.claude/mcp-servers/project-memory/index.js`

Manages persistent memory files stored as markdown with YAML frontmatter. Memories are organized per-project under `~/.claude/projects/<project-dir>/memory/` or globally under the project bucket for `~/.claude` (computed by the project-key collapse rule).

**Tools (8):**

| Tool | Description |
|------|-------------|
| `list_memories` | Lists all memories for a project or globally, optionally filtered by type. |
| `get_memory` | Reads a specific memory file by filename. |
| `save_memory` | Creates or updates a memory file with frontmatter (name, description, type, content). |
| `delete_memory` | Removes a memory file and updates the `MEMORY.md` index. |
| `search_memories` | Case-insensitive content search across all memories, optionally scoped to a project. |
| `list_projects` | Lists all projects that have memory directories. |
| `get_preferences` | Returns memories of type `user` or `feedback`. |
| `save_preference` | Quick-save a user preference or feedback entry. |

**Memory types:** `user`, `feedback`, `project`, `reference`

**Resources (3):** `memory://global`, `memory://projects`, `memory://project/{projectName}`

### system-info

**Path:** `~/.claude/mcp-servers/system-info/index.js`

Reports information about the local macOS machine. Handles both macOS (`darwin`) and Linux platforms for command differences.

**Tools (7):**

| Tool | Description |
|------|-------------|
| `system_overview` | OS, hostname, uptime, CPU model/cores, memory (total/used/free/percent), load average. |
| `process_list` | Running processes sorted by CPU or memory usage, with configurable limit. |
| `disk_usage` | Disk usage for all mounted filesystems (`df -h`). |
| `network_info` | Network interfaces and their addresses (both raw output and parsed JSON). |
| `check_port` | Checks if a port is in use and which process holds it (`lsof` on macOS, `ss`/`netstat` on Linux). |
| `environment_info` | Environment variables with secret values (`password`, `token`, `key`, `secret`, `credential`, `auth`) redacted as `***REDACTED***`. |
| `installed_tools` | Version checks for 16 development tools: node, npm, python3, pip3, go, rustc, cargo, dotnet, java, git, docker, kubectl, brew, shellcheck, jq, curl, ssh. |

### remote-shell

**Path:** `~/.claude/mcp-servers/remote-shell/index.js`

Executes commands on the remote Ubuntu server via SSH. This server gives Claude direct access to the remote host without Claude needing SSH credentials in its context.

**Tools (5):**

| Tool | Description |
|------|-------------|
| `remote_exec` | Execute an arbitrary shell command on the remote host. Configurable timeout (default 30000ms via `MCP_SSH_TIMEOUT`). |
| `remote_file_read` | Read a file from the remote host, optionally limited to N lines. |
| `remote_file_list` | List files in a remote directory with optional glob pattern. |
| `remote_service_status` | Check the status of a systemd service (e.g., `ssh`, `docker`, `nginx`). |
| `remote_system_info` | Get OS, uptime, memory, disk, CPU, and load information from the remote host. |

#### The `loadRemoteEnv()` Pattern

The `remote-shell` server uses a `loadRemoteEnv()` function at startup to extract credentials from `~/.claude/enforcement/env.remote` without exposing them in the MCP configuration:

```javascript
function loadRemoteEnv() {
  try {
    const out = execSync(
      'set -a; source "$HOME/.env.remote" 2>/dev/null; set +a; '
      + 'echo "LSP_IP=$LSP_IP"; echo "LSP_USER=$LSP_USER"; echo "LSP_PASS=$LSP_PASS"',
      { encoding: "utf-8", shell: "/bin/bash", timeout: 5000 }
    );
    const vars = {};
    for (const line of out.trim().split("\n")) {
      const eq = line.indexOf("=");
      if (eq > 0) vars[line.substring(0, eq)] = line.substring(eq + 1);
    }
    return vars;
  } catch (e) {
    console.error("Failed to load ~/.claude/enforcement/env.remote:", e.message);
    return {};
  }
}

const SHELL_VARS = loadRemoteEnv();
const LSP_IP = SHELL_VARS.LSP_IP || "";
const LSP_USER = SHELL_VARS.LSP_USER || "";
const LSP_PASS = SHELL_VARS.LSP_PASS || "";
```

This runs once at server startup, sources `~/.claude/enforcement/env.remote` in a child bash process, and captures the three required variables. The SSH command is then constructed using `sshpass`:

```javascript
function sshExec(command, timeoutMs) {
  const sshCmd = `sshpass -p ${JSON.stringify(LSP_PASS)} ssh -o ConnectTimeout=10 `
    + `-o StrictHostKeyChecking=no ${LSP_USER}@${LSP_IP} ${JSON.stringify(command)}`;
  const result = execSync(sshCmd, {
    encoding: "utf-8",
    timeout: timeoutMs || SSH_TIMEOUT,
    stdio: ["pipe", "pipe", "pipe"]
  });
  return { success: true, output: result.trim() };
}
```

---

## Remote Server Architecture

### SSH Command Pattern

Every remote MCP server in `.mcp.json` uses the same SSH invocation pattern:

```bash
set -a; source $HOME/.env.remote 2>/dev/null; set +a; \
exec sshpass -p "${LSP_PASS}" ssh \
  -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=no \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=120 \
  "${LSP_USER}@${LSP_IP}" \
  "/home/${LSP_USER}/.local/bin/<wrapper-name>"
```

**Key SSH options:**

| Option | Value | Purpose |
|--------|-------|---------|
| `ConnectTimeout` | 10 | Fail fast if the remote host is unreachable. |
| `StrictHostKeyChecking` | no | Accept host keys automatically (required for non-interactive use). |
| `ServerAliveInterval` | 30 | Send keepalive packets every 30 seconds. |
| `ServerAliveCountMax` | 120 | Allow up to 120 missed keepalives before disconnecting (1 hour). |

### Wrapper Script Pattern

Each remote MCP server is a small bash wrapper script located at `/home/${LSP_USER}/.local/bin/mcp-<name>`. The setup script creates these wrappers automatically.

**npx-based wrapper example (`mcp-memory`):**

```bash
#!/usr/bin/env bash
exec npx -y @modelcontextprotocol/server-memory
```

**npx-based wrapper with arguments (`mcp-filesystem`):**

```bash
#!/usr/bin/env bash
exec npx -y @modelcontextprotocol/server-filesystem "$@"
```

**pip-based wrapper example (`mcp-server-fetch`):**

```bash
#!/usr/bin/env bash
exec python3 -m mcp_server_fetch "$@"
```

**Go binary (Gitea):** The `mcp-gitea` binary is downloaded directly from `https://gitea.com/gitea/gitea-mcp/releases/download/v1.0.0/gitea-mcp_Linux_x86_64.tar.gz` and placed at `/home/${LSP_USER}/.local/bin/mcp-gitea`. No wrapper script is needed -- it runs as a native binary.

### Environment Variable Forwarding

Some remote servers require API keys or connection strings. These are forwarded as inline environment variables in the SSH command:

| Server | Forwarded Variables |
|--------|-------------------|
| `remote-brave-search` | `BRAVE_API_KEY=${BRAVE_API_KEY}` |
| `remote-github` | `GITHUB_PERSONAL_ACCESS_TOKEN=${GITHUB_PERSONAL_ACCESS_TOKEN}` |
| `remote-postgres` | `POSTGRES_CONNECTION_STRING=postgresql://${LSP_USER}:${LSP_PASS}@localhost:5432/claude_mcp` |
| `remote-gitea` | `GITEA_ACCESS_TOKEN=${MY_GITEA_API_TOKEN}` and `GITEA_HOST=http://${MY_GITEA_HOST}:${MY_GITEA_PORT}` |

### Complete Remote Binary List

All remote binaries and wrappers at `/home/${LSP_USER}/.local/bin/`:

| Binary/Wrapper | Type | Underlying Package |
|----------------|------|-------------------|
| `mcp-filesystem` | npx wrapper | `@modelcontextprotocol/server-filesystem` |
| `mcp-memory` | npx wrapper | `@modelcontextprotocol/server-memory` |
| `mcp-everything` | npx wrapper | `@modelcontextprotocol/server-everything` |
| `mcp-sequential-thinking` | npx wrapper | `@modelcontextprotocol/server-sequential-thinking` |
| `mcp-brave-search` | npx wrapper | `@modelcontextprotocol/server-brave-search` |
| `mcp-github` | npx wrapper | `@modelcontextprotocol/server-github` |
| `mcp-puppeteer` | npx wrapper | `@modelcontextprotocol/server-puppeteer` |
| `mcp-postgres` | npx wrapper | `@modelcontextprotocol/server-postgres` |
| `mcp-context7` | npx wrapper | `@anthropic-ai/mcp-server-context7` (fallback: `context7-mcp`) |
| `mcp-server-fetch` | pip wrapper | `mcp-server-fetch` (`python3 -m mcp_server_fetch`) |
| `mcp-server-git` | pip wrapper | `mcp-server-git` (`python3 -m mcp_server_git`) |
| `mcp-server-sqlite` | pip wrapper | `mcp-server-sqlite` (`python3 -m mcp_server_sqlite`) |
| `mcp-gitea` | Go binary | Gitea MCP v1.0.0 (Linux x86_64) |

---

## Credential Management

### `~/.claude/enforcement/env.remote` -- Single Source of Truth

All credentials, connection details, and API keys are defined in `~/.claude/enforcement/env.remote`. This file is sourced by both the setup script and every remote SSH command at runtime.

**Required variables:**

| Variable | Purpose |
|----------|---------|
| `LSP_IP` | Remote server IP address |
| `LSP_USER` | SSH username for the remote server |
| `LSP_PASS` | SSH password for the remote server (used by `sshpass`) |
| `LSP_SUDO_PASS` | Sudo password on the remote server (used during setup for apt installs) |
| `MY_GITEA_HOST` | Gitea server hostname |
| `MY_GITEA_PORT` | Gitea server port |
| `MY_GITEA_API_TOKEN` | Gitea API access token |
| `BRAVE_API_KEY` | Brave Search API key |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub personal access token |

**Changing the remote server IP:** Update `LSP_IP` in `~/.claude/enforcement/env.remote`. All 13 remote servers and the `remote-shell` custom server pick up the new value on next startup -- no other files need editing.

---

## Installation

### Prerequisites

**Local machine (macOS):**

- `sshpass` (install via `brew install hudochenkov/sshpass/sshpass`)
- `node` and `npm`
- `python3`
- `jq`
- `ssh`

**Remote machine (Ubuntu 24.04):**

The setup script installs all remote dependencies automatically:

- Node.js LTS (via NodeSource)
- `pip3` (via `python3-pip`)
- PostgreSQL with `postgresql-contrib`
- All MCP wrapper scripts and binaries

### Running the Setup Script

```bash
~/.claude/scripts/setup-mcp-lsp.sh
```

The script is idempotent and self-healing. It performs these operations:

1. Sources `~/.claude/enforcement/env.remote` for all credentials and connection details.
2. Installs PostgreSQL on the remote server, creates user `${LSP_USER}` and database `claude_mcp`.
3. Installs Node.js LTS on the remote server if not present.
4. Creates all npx-based wrapper scripts at `/home/${LSP_USER}/.local/bin/`.
5. Installs `pip3` on the remote server if not present.
6. Installs pip-based MCP packages (`mcp-server-fetch`, `mcp-server-git`, `mcp-server-sqlite`) and creates their wrappers.
7. Downloads and installs the Gitea MCP Go binary (v1.0.0).
8. Verifies all 13 remote binaries are present and executable.
9. Sets up LSP plugin marketplace files for local code intelligence.
10. Generates `~/.claude/.mcp.json` with all 21 server definitions.
11. Updates `~/.claude/settings.json` with the enabled server list.

The script uses a failure counter (`FAILURE_COUNT`) and reports all errors at completion rather than aborting on the first failure.

---

## How Claude Code Uses MCP Servers

### Discovery

Claude Code reads `~/.claude/.mcp.json` at startup. For each server entry, Claude Code:

1. Spawns the specified `command` with the given `args`.
2. Communicates with the server over stdio using the Model Context Protocol.
3. Calls `ListTools` (and `ListResources` where supported) to discover available capabilities.

### Invocation

During a conversation, Claude Code invokes MCP tools via `CallTool` requests. Each tool call specifies the tool name and arguments. The server executes the operation and returns results as text content.

### Server Roles

| Server | Role in Claude Code Workflow |
|--------|------------------------------|
| `guidelines-retriever` | Provides coding standards without reading raw XML files each time. Claude calls `get_guideline_for_language` before writing code. |
| `project-memory` | Persists project context, user preferences, and feedback across conversations. |
| `system-info` | Reports local machine state for debugging, environment checks, and tool availability verification. |
| `remote-shell` | Gives Claude SSH access to the remote server without credentials appearing in the conversation context. |
| `filesystem-local` / `remote-filesystem` | File read/write/search operations on local and remote machines. |
| `memory-local` / `remote-memory` | Knowledge graph storage for entities and relationships. |
| `remote-fetch` | HTTP requests and web content retrieval from the remote server. |
| `remote-git` | Git operations (clone, commit, diff, log) on remote repositories. |
| `remote-sqlite` / `remote-postgres` | Database queries and schema inspection. |
| `remote-brave-search` | Web search via Brave Search API. |
| `remote-github` | GitHub PR/issue/repo operations via the GitHub API. |
| `remote-gitea` | Gitea repository and issue management. |
| `remote-puppeteer` | Headless browser automation for web scraping and testing. |
| `remote-context7` | Library documentation lookup for up-to-date API references. |
| `sequential-thinking` / `remote-sequential-thinking` | Structured reasoning for complex problem decomposition. |

### Benefits

- **21 specialized capabilities** extend Claude Code beyond its built-in tools.
- **Remote execution** isolates heavy operations (Puppeteer, PostgreSQL, Git) from the local machine.
- **Centralized credential management** in `~/.claude/enforcement/env.remote` means changing the remote server IP updates all 13 remote connections.
- **Self-healing setup script** recovers from partial installations and is safe to re-run.
- **Credential isolation** keeps SSH passwords and API keys out of the conversation context via the `loadRemoteEnv()` pattern and `~/.claude/enforcement/env.remote` sourcing.

---

## Directory Structure

```
~/.claude/
  .mcp.json                          # All 21 MCP server definitions
  settings.json                      # Enabled servers list and Claude Code settings
  mcp-servers/
    guidelines-retriever/
      index.js                       # Custom Node.js MCP server
      package.json                   # Dependencies: @modelcontextprotocol/sdk ^1.27.1
      node_modules/
    project-memory/
      index.js                       # Custom Node.js MCP server
      package.json                   # Dependencies: @modelcontextprotocol/sdk ^1.27.1
      node_modules/
    system-info/
      index.js                       # Custom Node.js MCP server
      package.json                   # Dependencies: @modelcontextprotocol/sdk ^1.0.0
      node_modules/
    remote-shell/
      index.js                       # Custom Node.js MCP server
      package.json                   # Dependencies: @modelcontextprotocol/sdk ^1.0.0
      node_modules/
  scripts/
    setup-mcp-lsp.sh                 # Turnkey installation script
  guidelines/
    *.xml                            # Guideline files read by guidelines-retriever

~/.claude/enforcement/env.remote                      # Single source of truth for all credentials

/home/$LSP_USER/.local/bin/          # Remote server (Ubuntu 24.04)
  mcp-filesystem                     # npx wrapper
  mcp-memory                         # npx wrapper
  mcp-everything                     # npx wrapper
  mcp-sequential-thinking            # npx wrapper
  mcp-brave-search                   # npx wrapper
  mcp-github                         # npx wrapper
  mcp-puppeteer                      # npx wrapper
  mcp-postgres                       # npx wrapper
  mcp-context7                       # npx wrapper
  mcp-server-fetch                   # pip wrapper
  mcp-server-git                     # pip wrapper
  mcp-server-sqlite                  # pip wrapper
  mcp-gitea                          # Go binary (v1.0.0)
```
