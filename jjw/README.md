# jjw

Gas City pack for managing Jujutsu agent workspaces with
[`jjw`](https://github.com/aranw/jjw).

The pack provides:

- `assets/scripts/install-jjw.sh`: installs `jjw` with `go install` when it is
  not already on `PATH`.
- `assets/scripts/workspace-setup.sh`: pre-start helper for agent workspaces.
- `gc jjw install`: explicit install command.
- `gc jjw workspace-report`: prints a `jjw`-backed workspace report.
- `orders/workspace-report.toml`: direct exec smoke report order.
- `orders/jjw-workspace-report.toml`: formula-backed dog report order.
- `gc doctor`: `check-jjw` verifies the binary can be installed/resolved.

## Agent usage

Use from another imported pack:

```toml
pre_start = ["{{.ConfigDir}}/../jjw/assets/scripts/workspace-setup.sh {{.RigRoot}} {{.WorkDir}} {{.AgentBase}} --sync"]
```

The helper creates/uses a `.jjw.yaml` in the rig root. It writes that file only
when missing or when it already contains the Gas City marker.

The helper also accepts LazyJJ metadata flags such as `--bead`, `--title`, and
`--description-file`. When title metadata is present, it describes an
undescribed current workspace change so fresh and resumed workspaces start with
bead-derived context. The formula remains responsible for validating and
recording workspace metadata.

## Configuration

Set these through `city.toml` agent/rig env overrides when needed:

- `GC_JJW_VERSION`: version passed to `go install`; default `latest`.
- `GC_JJW_INSTALL_DIR`: install directory; default `$HOME/.local/bin`.
- `GC_JJW_WORKSPACE_DIR`: `jjw` workspace_dir override. Default is the target
  workspace parent, relative to the rig root.
- `GC_JJW_DEFAULT_BRANCH`: `jjw` default_branch; default `main`.
- `GC_JJW_BOOKMARK_PATTERN`: `jjw` bookmark_pattern; default `gc/{name}`.
- `GC_JJW_MANAGE_CONFIG`: `true` by default. Set `overwrite` to replace a
  hand-authored `.jjw.yaml`; set `false` to require an existing config.
