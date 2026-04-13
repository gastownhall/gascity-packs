Create a pull request using the workspace-owned GitHub App installation.

Example:
  gc github-intake create-pr owner/repo \
    --installation-id 123456 \
    --base main \
    --head fix-42 \
    --title "fix: correct widget behavior" \
    --body-file /tmp/pr.md

Arguments:
  <repository> owner/repo

Flags:
  --installation-id <id>    GitHub App installation id
  --base <branch>           base branch for the PR
  --head <branch>           head branch for the PR
  --title <text>            PR title
  --body <text>             inline PR body
  --body-file <path>        read PR body from file
