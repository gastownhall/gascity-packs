# Node.js Runtime

Node.js 22 LTS (active, supported through April 2027). Node.js 24 LTS (current). Node.js 22.18+ natively strips TypeScript types, enabling direct `.ts` file execution without separate compilation for development.

### Pin the Node.js Version

Pin per project using `.node-version`, `.nvmrc`, or the `engines` field in `package.json`. All developers and CI use the same Node.js version. **Version drift between development, CI, and production causes "works on my machine" failures.**

```json
{
  "engines": { "node": ">=22.0.0" }
}
```

Use `nvm`, `fnm`, Volta, or `mise` for version management.

### ESM for All New Code

Set `"type": "module"` in `package.json`. Use `import`/`export` syntax. **CJS (`require`/`module.exports`) is legacy.** ESM provides static analysis, tree-shaking, top-level await, and consistent behavior between Node.js and browser environments. For packages that must support both ESM and CJS consumers, use the `exports` field with conditional exports.

### Graceful Shutdown

Handle process signals for graceful shutdown:

```typescript
process.on('SIGTERM', async () => {
  await server.close();
  await db.disconnect();
  process.exit(0);
});
process.on('SIGINT', /* same handler */);
```

Listen for `SIGTERM` and `SIGINT`. Close HTTP servers, database connections, message consumers, file handles. Flush logs. Exit with code 0. **Kubernetes, Docker, and systemd send `SIGTERM` before `SIGKILL`.** A server that does not handle `SIGTERM` drops in-flight requests and leaks connections.

### `process.exit()` Discipline

**Never use `process.exit()` in library code.** It terminates immediately without running cleanup handlers, closing connections, or flushing streams. Throw an error and let the top-level error handler decide whether to exit. `process.exit()` is acceptable only in CLI tool main functions and **after** graceful shutdown logic completes.

### Unhandled Promise Rejections

```typescript
process.on('unhandledRejection', (reason) => {
  logger.fatal({ reason }, 'unhandled rejection');
  process.exit(1);
});
```

Node.js 22+ throws on unhandled rejections by default (`--unhandled-rejections=throw`). **An unhandled rejection in production is a silent failure that corrupts state without crashing — worse than crashing.**

### Built-in APIs with `node:` Prefix

```typescript
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { test } from 'node:test';
```

The `node:` prefix distinguishes built-ins from npm packages and prevents accidental shadowing.

### Native TypeScript Type Stripping (Node 22.18+)

For development workflows: `node --experimental-strip-types app.ts` (stable in Node 22.18+, no flag needed). Executes TypeScript files directly by stripping types. **Use a proper `tsc` build for production artifacts, type checking, and declaration generation.** Node's type stripping does **not** type-check — it only removes type annotations for execution.

---
[Back to Overview](./OVERVIEW.md)
