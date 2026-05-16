# LSP Plugin Infrastructure for Claude Code

This document describes the Language Server Protocol (LSP) plugin system that provides Claude Code with real-time code intelligence -- completions, diagnostics, go-to-definition, and hover information -- for 7 programming languages via locally running LSP servers.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Architecture Diagram](#architecture-diagram)
- [Directory Structure](#directory-structure)
- [Supported Languages](#supported-languages)
- [Configuration Files](#configuration-files)
  - [marketplace.json](#marketplacejson)
  - [plugin.json](#pluginjson)
  - [.lsp.json](#lspjson)
  - [known\_marketplaces.json](#known_marketplacesjson)
  - [installed\_plugins.json](#installed_pluginsjson)
  - [settings.json](#settingsjson)
- [Installation](#installation)
  - [Full Setup (setup-mcp-lsp.sh)](#full-setup-setup-mcp-lspsh)
  - [Binary Installer (install-lsp-binaries.sh)](#binary-installer-install-lsp-binariessh)
- [How Claude Code Uses LSP Plugins](#how-claude-code-uses-lsp-plugins)
- [Comparison with Traditional IDEs](#comparison-with-traditional-ides)
- [Adding a New Language](#adding-a-new-language)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

---

## Architecture Diagram

A full Mermaid diagram of the LSP plugin architecture is available at [`lsp-architecture.mmd`](./lsp-architecture.mmd). It covers the complete flow from plugin discovery through marketplace resolution, cache loading, runtime activation, LSP protocol messages, and installation scripts.

To render the diagram, open the `.mmd` file in any Mermaid-compatible viewer (VS Code with the Mermaid extension, GitHub's built-in renderer, or [mermaid.live](https://mermaid.live)).

---

The LSP plugin system follows a **marketplace-based** architecture. A single local marketplace named `local-lsp` contains 7 language plugins. Each plugin declares which file extensions it handles and which LSP server binary to spawn. Claude Code discovers plugins through its settings, loads cached copies at startup, and spawns the appropriate language server on demand when a matching file is encountered.

```
                        +--------------------------+
                        |     Claude Code CLI      |
                        +------------+-------------+
                                     |
                        reads settings.json for
                        enabledPlugins + extraKnownMarketplaces
                                     |
                        +------------v-------------+
                        |  known_marketplaces.json  |
                        |  (discovers local-lsp)    |
                        +------------+-------------+
                                     |
                        +------------v-------------+
                        |  installed_plugins.json   |
                        |  (resolves cache paths)   |
                        +------------+-------------+
                                     |
              +------+------+------+------+------+------+------+
              |      |      |      |      |      |      |      |
           pyright  ts   rust   clangd swift  bash  csharp
              |      |      |      |      |      |      |
           reads .lsp.json from each cached plugin
              |      |      |      |      |      |      |
           spawns LSP binary via stdio on file match
```

---

## Directory Structure

```
~/.claude/plugins/
├── marketplaces/
│   └── local-lsp/                            # The LSP marketplace
│       ├── .claude-plugin/
│       │   └── marketplace.json              # Marketplace manifest
│       └── plugins/
│           ├── pyright-lsp/                  # Python
│           │   ├── .claude-plugin/
│           │   │   └── plugin.json           # Plugin manifest
│           │   └── .lsp.json                 # LSP server config
│           ├── typescript-lsp/               # TypeScript / JavaScript
│           │   ├── .claude-plugin/
│           │   │   └── plugin.json
│           │   └── .lsp.json
│           ├── rust-analyzer-lsp/            # Rust
│           │   ├── .claude-plugin/
│           │   │   └── plugin.json
│           │   └── .lsp.json
│           ├── clangd-lsp/                   # C / C++
│           │   ├── .claude-plugin/
│           │   │   └── plugin.json
│           │   └── .lsp.json
│           ├── swift-lsp/                    # Swift
│           │   ├── .claude-plugin/
│           │   │   └── plugin.json
│           │   └── .lsp.json
│           ├── bash-lsp/                     # Bash / Shell
│           │   ├── .claude-plugin/
│           │   │   └── plugin.json
│           │   └── .lsp.json
│           └── csharp-lsp/                   # C#
│               ├── .claude-plugin/
│               │   └── plugin.json
│               └── .lsp.json
├── cache/
│   └── local-lsp/                            # Cached copies (runtime)
│       ├── pyright-lsp/1.0.0/
│       │   ├── .claude-plugin/plugin.json
│       │   └── .lsp.json
│       ├── typescript-lsp/1.0.0/
│       ├── rust-analyzer-lsp/1.0.0/
│       ├── clangd-lsp/1.0.0/
│       ├── swift-lsp/1.0.0/
│       ├── bash-lsp/1.0.0/
│       └── csharp-lsp/1.0.0/
├── known_marketplaces.json                   # Registry of marketplace sources
├── installed_plugins.json                    # Registry of installed plugins
└── blocklist.json                            # Plugin blocklist
```

Each plugin exists in two locations:

1. **Marketplace source** (`marketplaces/local-lsp/plugins/<name>/`) -- the authoritative definition.
2. **Cache** (`cache/local-lsp/<name>/1.0.0/`) -- an identical copy that Claude Code reads at runtime.

The setup script writes both locations to keep them in sync.

---

## Supported Languages

| Plugin Name | Languages | Binary | Command | File Extensions | Language IDs | Install Method |
|---|---|---|---|---|---|---|
| `pyright-lsp` | Python | `pyright-langserver` | `pyright-langserver --stdio` | `.py`, `.pyi` | `python` | `npm install -g pyright` |
| `typescript-lsp` | TypeScript, JavaScript | `typescript-language-server` | `typescript-language-server --stdio` | `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.mts` | `typescript`, `typescriptreact`, `javascript`, `javascriptreact` | `npm install -g typescript-language-server typescript` |
| `rust-analyzer-lsp` | Rust | `rust-analyzer` | `rust-analyzer` | `.rs` | `rust` | `rustup component add rust-analyzer` |
| `clangd-lsp` | C, C++ | `clangd` | `clangd` | `.c`, `.h`, `.cpp`, `.cxx`, `.cc`, `.hpp`, `.hxx`, `.hh` | `c`, `cpp` | Xcode CLT (macOS) or `apt install clangd` (Linux) |
| `swift-lsp` | Swift | `sourcekit-lsp` | `sourcekit-lsp` | `.swift` | `swift` | Included with Xcode (macOS) |
| `bash-lsp` | Bash, Shell | `bash-language-server` | `bash-language-server start` | `.sh`, `.bash`, `.zsh` | `shellscript` | `npm install -g bash-language-server` |
| `csharp-lsp` | C# | `csharp-ls` | `$HOME/.dotnet/tools/csharp-ls` | `.cs`, `.csx` | `csharp` | `dotnet tool install --global csharp-ls` |

---

## Configuration Files

### marketplace.json

**Location:** `~/.claude/plugins/marketplaces/local-lsp/.claude-plugin/marketplace.json`

This file defines the marketplace and enumerates all plugins it contains.

```json
{
  "name": "local-lsp",
  "owner": {
    "name": "__USER_NAME__"
  },
  "metadata": {
    "description": "Local LSP plugins for Claude Code code intelligence",
    "version": "1.0.0",
    "pluginRoot": "./plugins"
  },
  "plugins": [
    {
      "name": "pyright-lsp",
      "source": "./plugins/pyright-lsp",
      "description": "Python code intelligence via Pyright language server",
      "version": "1.0.0"
    },
    {
      "name": "typescript-lsp",
      "source": "./plugins/typescript-lsp",
      "description": "TypeScript and JavaScript code intelligence via typescript-language-server",
      "version": "1.0.0"
    },
    {
      "name": "rust-analyzer-lsp",
      "source": "./plugins/rust-analyzer-lsp",
      "description": "Rust code intelligence via rust-analyzer",
      "version": "1.0.0"
    },
    {
      "name": "clangd-lsp",
      "source": "./plugins/clangd-lsp",
      "description": "C and C++ code intelligence via clangd",
      "version": "1.0.0"
    },
    {
      "name": "swift-lsp",
      "source": "./plugins/swift-lsp",
      "description": "Swift code intelligence via sourcekit-lsp",
      "version": "1.0.0"
    },
    {
      "name": "bash-lsp",
      "source": "./plugins/bash-lsp",
      "description": "Bash and shell script code intelligence via bash-language-server",
      "version": "1.0.0"
    },
    {
      "name": "csharp-lsp",
      "source": "./plugins/csharp-lsp",
      "description": "C# code intelligence via csharp-ls",
      "version": "1.0.0"
    }
  ]
}
```

### plugin.json

**Location:** `~/.claude/plugins/marketplaces/local-lsp/plugins/<name>/.claude-plugin/plugin.json`

Each plugin has its own manifest declaring name, description, and version. Example for `pyright-lsp`:

```json
{
  "name": "pyright-lsp",
  "description": "Python code intelligence via Pyright language server",
  "version": "1.0.0"
}
```

### .lsp.json

**Location:** `~/.claude/plugins/marketplaces/local-lsp/plugins/<name>/.lsp.json`

This is the core configuration file that tells Claude Code how to launch the language server and which file extensions map to which language ID. The format is:

```json
{
  "<key>": {
    "command": "<binary>",
    "args": ["<arg1>", "<arg2>"],
    "extensionToLanguage": {
      ".<ext>": "<languageId>"
    }
  }
}
```

**Fields:**

| Field | Required | Description |
|---|---|---|
| `command` | Yes | The LSP server binary to execute |
| `args` | No | Array of command-line arguments passed to the binary |
| `extensionToLanguage` | Yes | Maps file extensions to LSP language identifiers |

**Example -- pyright-lsp/.lsp.json:**

```json
{
  "python": {
    "command": "pyright-langserver",
    "args": ["--stdio"],
    "extensionToLanguage": {
      ".py": "python",
      ".pyi": "python"
    }
  }
}
```

**Example -- typescript-lsp/.lsp.json:**

```json
{
  "typescript": {
    "command": "typescript-language-server",
    "args": ["--stdio"],
    "extensionToLanguage": {
      ".ts": "typescript",
      ".tsx": "typescriptreact",
      ".js": "javascript",
      ".jsx": "javascriptreact",
      ".mjs": "javascript",
      ".mts": "typescript"
    }
  }
}
```

**Example -- clangd-lsp/.lsp.json (no args):**

```json
{
  "c_cpp": {
    "command": "clangd",
    "extensionToLanguage": {
      ".c": "c",
      ".h": "c",
      ".cpp": "cpp",
      ".cxx": "cpp",
      ".cc": "cpp",
      ".hpp": "cpp",
      ".hxx": "cpp",
      ".hh": "cpp"
    }
  }
}
```

**Example -- csharp-lsp/.lsp.json (absolute path binary):**

```json
{
  "csharp": {
    "command": "~/.dotnet/tools/csharp-ls",
    "extensionToLanguage": {
      ".cs": "csharp",
      ".csx": "csharp"
    }
  }
}
```

### known_marketplaces.json

**Location:** `~/.claude/plugins/known_marketplaces.json`

Tells Claude Code where to find each marketplace on the local filesystem.

```json
{
  "local-lsp": {
    "source": {
      "source": "directory",
      "path": "~/.claude/plugins/marketplaces/local-lsp"
    },
    "installLocation": "~/.claude/plugins/marketplaces/local-lsp",
    "lastUpdated": "2026-03-13T00:37:09.000Z"
  }
}
```

### installed_plugins.json

**Location:** `~/.claude/plugins/installed_plugins.json`

Tracks which plugins are installed, their versions, and cache paths. The format uses `version: 2` and keys plugins as `<name>@<marketplace>`.

```json
{
  "version": 2,
  "plugins": {
    "pyright-lsp@local-lsp": [
      {
        "scope": "user",
        "installPath": "~/.claude/plugins/cache/local-lsp/pyright-lsp/1.0.0",
        "version": "1.0.0",
        "installedAt": "2026-03-13T00:37:09.000Z",
        "lastUpdated": "2026-03-13T00:37:09.000Z"
      }
    ],
    "typescript-lsp@local-lsp": [{ "..." : "..." }],
    "rust-analyzer-lsp@local-lsp": [{ "..." : "..." }],
    "clangd-lsp@local-lsp": [{ "..." : "..." }],
    "swift-lsp@local-lsp": [{ "..." : "..." }],
    "bash-lsp@local-lsp": [{ "..." : "..." }],
    "csharp-lsp@local-lsp": [{ "..." : "..." }]
  }
}
```

### settings.json

**Location:** `~/.claude/settings.json`

Two keys in the Claude Code settings file enable the LSP plugins:

**`enabledPlugins`** -- Activates each plugin by its `<name>@<marketplace>` key:

```json
{
  "enabledPlugins": {
    "pyright-lsp@local-lsp": true,
    "typescript-lsp@local-lsp": true,
    "rust-analyzer-lsp@local-lsp": true,
    "clangd-lsp@local-lsp": true,
    "swift-lsp@local-lsp": true,
    "bash-lsp@local-lsp": true,
    "csharp-lsp@local-lsp": true
  }
}
```

**`extraKnownMarketplaces`** -- Points Claude Code to the local marketplace directory:

```json
{
  "extraKnownMarketplaces": {
    "local-lsp": {
      "source": {
        "source": "directory",
        "path": "~/.claude/plugins/marketplaces/local-lsp"
      }
    }
  }
}
```

---

## Installation

Two scripts handle the entire setup process. Both scripts are idempotent -- running them multiple times produces the same result.

### Full Setup (setup-mcp-lsp.sh)

**Location:** `~/.claude/scripts/setup-mcp-lsp.sh`

This is the primary orchestrator that configures the complete MCP and LSP infrastructure.

```bash
~/.claude/scripts/setup-mcp-lsp.sh
```

**What it does (in order):**

1. Sources environment variables from `~/.claude/enforcement/env.remote`
2. Validates required variables: `LSP_IP`, `LSP_USER`, `LSP_PASS`, `LSP_SUDO_PASS`, `MY_GITEA_HOST`, `MY_GITEA_PORT`, `MY_GITEA_API_TOKEN`, `BRAVE_API_KEY`
3. Generates SSH config for the remote server at `~/.ssh/config.d/lsp-server`
4. Verifies SSH connectivity to the remote host
5. Sets up PostgreSQL on the remote server (installs, creates user and database)
6. Installs MCP server binaries on the remote server (npx wrappers, pip packages, Gitea MCP)
7. **Delegates local LSP binary installation to `install-lsp-binaries.sh`**
8. **Creates the entire marketplace directory structure** (`marketplaces/local-lsp/plugins/...`)
9. **Writes all `plugin.json` and `.lsp.json` files** for each of the 7 plugins
10. **Writes `known_marketplaces.json`**
11. **Writes `installed_plugins.json`**
12. Sets up the `remote-shell` MCP server (Node.js)
13. **Writes `~/.claude/.mcp.json`** with all MCP server definitions
14. **Updates `~/.claude/settings.json`** with `enabledPlugins` and `extraKnownMarketplaces`
15. Runs final validation (remote binaries, PostgreSQL, local LSP binaries, JSON files, plugin cache)
16. Prints a summary with pass/fail counts

**Prerequisites:**

- `sshpass`, `ssh`, `node`, `npm`, `python3` installed locally
- `~/.claude/enforcement/env.remote` with the required environment variables
- Network access to the remote server

### Binary Installer (install-lsp-binaries.sh)

**Location:** `~/.claude/scripts/install-lsp-binaries.sh`

This script handles installing or verifying the 8 LSP-related binaries.

```bash
~/.claude/scripts/install-lsp-binaries.sh [-v|--verbose] [-h|--help]
```

**What it installs:**

| Category | Package | Binary | Action |
|---|---|---|---|
| npm global | `pyright` | `pyright-langserver` | Installs if missing |
| npm global | `typescript-language-server` | `typescript-language-server` | Installs if missing |
| npm global | `typescript` | `tsc` | Installs if missing |
| npm global | `bash-language-server` | `bash-language-server` | Installs if missing |
| dotnet tool | `csharp-ls` | `csharp-ls` | Installs if missing (skips if `dotnet` is not available) |
| status check | -- | `rust-analyzer` | Reports presence only (manual install required) |
| status check | -- | `clangd` | Reports presence only (manual install required) |
| status check | -- | `sourcekit-lsp` | Reports presence only (manual install required) |

**Total checks:** 8

The script logs output to `~/.claude/scripts/logs/` with timestamped filenames.

**Exit codes:**

- `0` -- All 8 checks passed
- `1` -- One or more checks failed
- `2` -- Unknown CLI option
- `3` -- Pre-flight failed (npm not installed)

---

## How Claude Code Uses LSP Plugins

The plugin discovery and activation flow proceeds as follows:

1. **Settings discovery** -- At startup, Claude Code reads `~/.claude/settings.json`. The `enabledPlugins` map identifies which plugins are active. The `extraKnownMarketplaces` map tells Claude Code where the `local-lsp` marketplace lives on disk.

2. **Marketplace resolution** -- Claude Code reads `~/.claude/plugins/known_marketplaces.json` to resolve the `local-lsp` marketplace path to `~/.claude/plugins/marketplaces/local-lsp`.

3. **Plugin loading** -- For each enabled plugin (e.g., `pyright-lsp@local-lsp`), Claude Code reads the cached copy from `~/.claude/plugins/cache/local-lsp/pyright-lsp/1.0.0/`. It loads:
   - `.claude-plugin/plugin.json` for metadata
   - `.lsp.json` for server configuration

4. **Extension mapping** -- The `extensionToLanguage` map in each `.lsp.json` tells Claude Code which file extensions trigger which language server. For example, opening a `.py` file maps to the `python` language ID and activates the `pyright-lsp` plugin.

5. **Server spawning** -- When a user opens or references a file with a matching extension, Claude Code:
   - Spawns the LSP server process using the `command` and `args` from `.lsp.json`
   - Communicates over **stdio** using the Language Server Protocol
   - Receives diagnostics (errors, warnings), completions, hover information, and go-to-definition targets

6. **Intelligence delivery** -- Claude Code uses the LSP responses to:
   - Catch errors and warnings before generating code
   - Provide accurate completions based on the actual codebase
   - Navigate symbol definitions and references
   - Display type information and documentation on hover

```
User references a .py file
        |
        v
Claude Code checks extensionToLanguage maps
        |
        v
".py" matches pyright-lsp plugin
        |
        v
Spawns: pyright-langserver --stdio
        |
        v
Communicates via Language Server Protocol
        |
        +---> textDocument/didOpen
        +---> textDocument/completion
        +---> textDocument/hover
        +---> textDocument/definition
        +---> textDocument/publishDiagnostics
        |
        v
Claude Code integrates intelligence into responses
```

---

## Comparison with Traditional IDEs

The same LSP binaries that power Claude Code's intelligence are the same binaries used by traditional IDEs and editors. The Language Server Protocol is an open standard -- all tools speak the same wire format.

| IDE / Editor | Python | TypeScript | Rust | C/C++ | Swift | Bash | C# |
|---|---|---|---|---|---|---|---|
| **Claude Code** | pyright-langserver | typescript-language-server | rust-analyzer | clangd | sourcekit-lsp | bash-language-server | csharp-ls |
| **VS Code** | Pylance (pyright) | typescript-language-server | rust-analyzer | clangd | sourcekit-lsp | bash-language-server | C# extension (OmniSharp / csharp-ls) |
| **Neovim (nvim-lspconfig)** | pyright | typescript-language-server | rust-analyzer | clangd | sourcekit-lsp | bash-language-server | csharp-ls |
| **JetBrains** | Built-in (or pyright) | Built-in | Built-in (or rust-analyzer) | Built-in (or clangd) | Built-in | Built-in | Built-in (Rider) |

The key difference is in the transport mechanism. IDEs typically use a socket or pipe connection to the language server. Claude Code uses **stdio** for all LSP connections -- the server reads from stdin and writes to stdout, with the LSP JSON-RPC protocol framing messages.

---

## Adding a New Language

To add a new language to the plugin system:

1. **Create the plugin directory** in both the marketplace and cache:

   ```bash
   mkdir -p ~/.claude/plugins/marketplaces/local-lsp/plugins/<name>/.claude-plugin
   mkdir -p ~/.claude/plugins/cache/local-lsp/<name>/1.0.0/.claude-plugin
   ```

2. **Write `plugin.json`** in both locations:

   ```json
   {
     "name": "<name>",
     "description": "<language> code intelligence via <server>",
     "version": "1.0.0"
   }
   ```

3. **Write `.lsp.json`** in both locations:

   ```json
   {
     "<key>": {
       "command": "<binary>",
       "args": ["--stdio"],
       "extensionToLanguage": {
         ".<ext>": "<languageId>"
       }
     }
   }
   ```

4. **Add the plugin entry to `marketplace.json`** in the `plugins` array:

   ```json
   {
     "name": "<name>",
     "source": "./plugins/<name>",
     "description": "<language> code intelligence via <server>",
     "version": "1.0.0"
   }
   ```

5. **Add the plugin to `installed_plugins.json`** under the `plugins` key:

   ```json
   "<name>@local-lsp": [{
     "scope": "user",
     "installPath": "~/.claude/plugins/cache/local-lsp/<name>/1.0.0",
     "version": "1.0.0",
     "installedAt": "<ISO timestamp>",
     "lastUpdated": "<ISO timestamp>"
   }]
   ```

6. **Enable the plugin in `settings.json`**:

   ```json
   "enabledPlugins": {
     "<name>@local-lsp": true
   }
   ```

7. **Install the LSP binary** on the local system and ensure it is in `PATH`.

8. **Restart Claude Code** to pick up the new plugin.

---

## Troubleshooting

### LSP server fails to start

**Symptom:** Claude Code does not provide code intelligence for a specific language.

**Cause 1:** The LSP binary is not installed or not in `PATH`.

**Solution:** Run the binary directly to verify it is accessible:

```bash
# For npm-installed binaries
which pyright-langserver
which typescript-language-server
which bash-language-server

# For rust-analyzer
which rust-analyzer

# For clangd
which clangd

# For sourcekit-lsp
which sourcekit-lsp

# For csharp-ls (uses full path)
ls -la ~/.dotnet/tools/csharp-ls
```

If missing, install the binary using the install method listed in the [Supported Languages](#supported-languages) table, or run:

```bash
~/.claude/scripts/install-lsp-binaries.sh -v
```

**Cause 2:** The cached plugin files are missing or corrupted.

**Solution:** Verify the cache directory contains both required files:

```bash
ls ~/.claude/plugins/cache/local-lsp/<plugin-name>/1.0.0/.claude-plugin/plugin.json
ls ~/.claude/plugins/cache/local-lsp/<plugin-name>/1.0.0/.lsp.json
```

If files are missing, re-run the setup script:

```bash
~/.claude/scripts/setup-mcp-lsp.sh
```

### Plugin is not recognized by Claude Code

**Symptom:** The plugin does not appear as active even though files exist on disk.

**Cause:** The plugin is not enabled in `settings.json` or is missing from `installed_plugins.json`.

**Solution:** Verify the following entries exist:

1. `~/.claude/settings.json` contains `"<name>@local-lsp": true` under `enabledPlugins`
2. `~/.claude/plugins/installed_plugins.json` contains a `"<name>@local-lsp"` entry under `plugins`
3. `~/.claude/plugins/known_marketplaces.json` contains the `local-lsp` marketplace entry

### JSON validation errors

**Symptom:** The setup script reports "Invalid JSON written to..." errors.

**Cause:** The JSON generation step produced malformed output.

**Solution:** Validate each JSON file independently:

```bash
python3 -c "import json; json.load(open('$HOME/.claude/plugins/known_marketplaces.json'))"
python3 -c "import json; json.load(open('$HOME/.claude/plugins/installed_plugins.json'))"
python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))"
```

If validation fails, re-run `~/.claude/scripts/setup-mcp-lsp.sh` to regenerate all files.

### csharp-ls is not found

**Symptom:** `install-lsp-binaries.sh` reports `[SKIP] csharp-ls (dotnet not available)`.

**Cause:** The .NET SDK is not installed.

**Solution:** Install the .NET SDK, then install the tool:

```bash
# macOS
brew install dotnet

# Then install csharp-ls
dotnet tool install --global csharp-ls
```

The `.lsp.json` for `csharp-lsp` uses the full path `$HOME/.dotnet/tools/csharp-ls` rather than relying on `PATH`, so the binary does not need to be globally accessible.

### rust-analyzer, clangd, or sourcekit-lsp missing

**Symptom:** `install-lsp-binaries.sh` reports `[WARN] <binary> not found (manual installation required)`.

**Cause:** These binaries are not installed via npm or dotnet. They require platform-specific installation.

**Solution:**

| Binary | macOS | Linux |
|---|---|---|
| `rust-analyzer` | `rustup component add rust-analyzer` | `rustup component add rust-analyzer` |
| `clangd` | Included in Xcode Command Line Tools (`xcode-select --install`) | `apt install clangd` or `apt install clang-tools` |
| `sourcekit-lsp` | Included with Xcode (`xcode-select --install`) | Build from source (Swift toolchain required) |

---

## Benefits

- **Real-time code intelligence** -- Claude Code gains the same diagnostic, completion, hover, and navigation capabilities as traditional IDEs.
- **Error prevention** -- Diagnostics from language servers catch type errors, undefined references, and syntax problems before Claude generates code.
- **Accurate context** -- Go-to-definition and hover information provide Claude with verified knowledge about the codebase, reducing hallucinated function signatures.
- **Extensible** -- Adding a new language requires creating a plugin directory with two JSON files and installing the LSP binary.
- **Idempotent setup** -- Running `setup-mcp-lsp.sh` multiple times produces the same result with no duplicates or side effects.
- **Graceful degradation** -- If a binary is missing, other plugins continue to function. Only the affected language loses code intelligence.
- **Standard protocol** -- All communication uses the Language Server Protocol, the same open standard used by VS Code, Neovim, and other editors.
