# Project Configuration

### netlify.toml Structure

Store `netlify.toml` in the repository root unless operating a monorepo. Pin the Node.js version explicitly via `NODE_VERSION` in `netlify.toml`, `.nvmrc`, or `.node-version`. The `netlify.toml` declaration takes precedence.

```toml
[build]
  command = "npm run build"
  publish = "dist"
  functions = "netlify/functions"

[build.environment]
  NODE_VERSION = "22"
```

### Configuration Hierarchy

`netlify.toml` overrides UI settings for any key present in both. **Environment variables declared in `netlify.toml` are overridden by variables declared in the UI for the same key** — the UI is the secure location for secrets, while `netlify.toml` handles non-sensitive structural configuration.

| Lives In | Setting |
|:---------|:--------|
| **`netlify.toml`** | Build command, publish directory, functions directory, redirect rules, header rules, plugin declarations, context-specific build overrides, edge function declarations |
| **UI only** | API keys and authentication tokens, database connection strings, any secret value |

### Deploy Contexts

Deploy contexts allow per-environment configuration without branching logic in build scripts. Supported contexts: `production`, `deploy-preview`, `branch-deploy`, and named branches. Context-specific settings **merge** with base `[build]` settings — only overridden keys change; everything else inherits.

```toml
[context.production]
  command = "npm run build:prod"
  environment = { NEXT_PUBLIC_API_URL = "https://api.example.com" }

[context.deploy-preview]
  command = "npm run build:preview"
  environment = { NEXT_PUBLIC_API_URL = "https://staging-api.example.com" }

[context.branch-deploy]
  command = "npm run build:staging"

[context.staging]
  command = "npm run build:staging"
  environment = { NEXT_PUBLIC_API_URL = "https://staging-api.example.com" }
```

---
[Back to Overview](./OVERVIEW.md)
