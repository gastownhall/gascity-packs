Map a BB project to a Gas City rig

gc bb bind --project <BB-project-ID> --id local --city <city> --rig <rig> --path <absolute-checkout>

Repeat --path for existing worktrees. Paths must exist. This replaces that project's binding on this host; other projects are preserved.
