# Native SQLite Beads backend

This pack selects the SQLite backend compiled into upstream `bd`. It has no
backend plugin process, server, or credentials. Every Gas City bead scope gets
its own SQLite file beneath that scope's `.beads/` directory.

Requires a `bd` release with `bd init --backend=sqlite` support.

```toml
[imports.bd-native-sqlite]
source = "../gascity-packs/bd-native-sqlite"

[beads]
provider = "bd"
backend = "sqlite"
# sqlite_path = "beads.db" # optional; pack default shown
```

Gas City initializes each scope with stock `bd`, then all `gc bd` and
controller operations use the backend recorded in `.beads/metadata.json`.
SQLite does not provide Dolt history, remotes, or `bd dolt push/pull`.
