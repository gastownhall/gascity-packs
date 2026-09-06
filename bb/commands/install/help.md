Install the Gas City provider into BB

gc bb install [--yes]

Requires Node.js 22+, npm, and the BB CLI. Builds each installation in a fresh
version directory, then registers it with BB and checks the runtime status before
activating the host CLI. Pass --yes to skip BB's installation prompt.

Previous installed sources, local edits, configuration, and session journals are
preserved. An existing flat installation keeps working until the new version is
ready. Updates move BB's path registration without removing plugin settings,
secrets, or schedules; a failed activation restores the prior registration when
BB remains reachable. Failed builds remain available for inspection.

The default installation root is
${XDG_DATA_HOME:-~/.local/share}/gascity/bb/plugin; GC_BB_INSTALL_DIR overrides it.
Its current symlink selects the active directory under versions/. Installations
are serialized by .install-lock. After a killed installer, inspect BB's registered
source and the retained version before manually clearing that lock. No prior
versions or interrupted-installation evidence are removed automatically.
