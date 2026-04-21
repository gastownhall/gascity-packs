Post an issue comment using the workspace-owned GitHub App installation.

Example:
  gc github-intake comment-issue owner/repo 42 \
    --installation-id 123456 \
    --body "Started work on this issue"

Arguments:
  <repository>   owner/repo
  <issue-number> GitHub issue number

Flags:
  --installation-id <id>    GitHub App installation id
  --body <text>             inline markdown body
  --body-file <path>        read markdown body from file
