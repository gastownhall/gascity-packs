Post an issue comment using the workspace-owned GitHub App installation.

Every posted body starts with the universal factory marker line
`<!-- gc-agent:v1 -->` (added automatically when missing), so analytics can
classify the comment as automation.

Example:
  gc github comment-issue owner/repo 42 \
    --installation-id 123456 \
    --github-app-identity mayor \
    --body "Started work on this issue"

Arguments:
  <repository>   owner/repo
  <issue-number> GitHub issue number

Flags:
  --installation-id <id>          GitHub App installation id, unless identity resolves one
  --github-app-identity <identity>     GitHub App identity for the comment author; see docs/github-app-identity.md
  --body <text>                   inline markdown body
  --body-file <path>              read markdown body from file
