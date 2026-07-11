# Native PostgreSQL Beads backend

This pack selects the PostgreSQL backend compiled into upstream `bd`. Gas City
uses one PostgreSQL database connection and derives a separate schema for each
city or rig bead scope. There is no external Beads backend-plugin process.

Requires a `bd` release with `bd init --backend=postgres` support and an
existing PostgreSQL database reachable by the Gas City supervisor.

```toml
[imports.bd-native-postgres]
source = "../gascity-packs/bd-native-postgres"

[beads]
provider = "bd"
backend = "postgres"
postgres_url = "postgres://beads@127.0.0.1:5432/beads?sslmode=disable"
```

Keep the password out of `city.toml`. Provide it through the upstream variable
`BEADS_PG_PASSWORD`, the compatibility variable `BEADS_POSTGRES_PASSWORD`, a
scope-local `.beads/.env` file with mode `0600`, or the Beads credentials file.

The city scope defaults to schema `hq`; rig schemas use their Gas City prefix.
Set `[beads].postgres_schema` only when the city scope needs an explicit name.
PostgreSQL does not provide Dolt history, remotes, or `bd dolt push/pull`.
