Configure the supervisor on this BB host

gc bb connect --id local --url http://127.0.0.1:8372

The default workspace policy is require-match: prompt submission requires matching BB and GC directories. Explicit --workspace-policy conversation permits mismatches with a visible notice and is only for conversation workflows through BB's provider picker. The dedicated Gas City launcher requires require-match. Configuration is host-local; configure each execution host.
