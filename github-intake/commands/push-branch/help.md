Push the current git HEAD to a named GitHub branch using the workspace-owned
GitHub App installation.

Example:
  gc github-intake push-branch owner/repo \
    --installation-id 123456 \
    --branch fix-42

Arguments:
  <repository> owner/repo

Flags:
  --installation-id <id>    GitHub App installation id
  --branch <name>           branch name to create or update
  --ref <spec>              source ref to push (default: HEAD)
