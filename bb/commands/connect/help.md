Configure the supervisor on this BB host

gc bb connect --id local --url http://localhost:7375

Use --workspace-policy conversation (default) for chat with explicit checkout mismatch notices, or require-match to block mismatched BB/GC working directories. The configuration is host-local; run on each execution host.
