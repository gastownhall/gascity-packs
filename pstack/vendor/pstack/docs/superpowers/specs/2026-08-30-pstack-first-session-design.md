# pstack First session box (no plugin commands/)

Date: 2026-08-30
Status: approved (option A)

## Decision

Do not add plugin `commands/`. Skills already are `/name`. Add a short **First session** section on `README.md` and `README.zh-CN.md`, mirrored in `docs/guide/01-setup.md`.

## Must say

1. Install `grok plugin install tommy-ca/pstack --trust` (not bare `pstack`).
2. Enable from a host shell if EROFS on `config.toml`: `grok --sandbox off plugin enable pstack`.
3. Reload: Plugins tab `r`, or a new session. Spawn types are a session-start snapshot.
4. `inspect` "enabled" is trust. Load gate is `[plugins].enabled`.
5. Spawn `pstack:how-explorer`, not `how-explorer`.
6. Type `/poteto-mode`. It does not auto-enter. `/setup-pstack` is optional.
7. Do not run `marketplace add` from a sandboxed agent (same EROFS).

## Out of scope

Plugin `commands/`, hooks, MCP, LSP, `.rhai` workflows, Gate 4e overlay-stem leftovers, orch/benny deletion.
