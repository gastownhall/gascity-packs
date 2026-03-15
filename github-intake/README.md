# GitHub Intake Pack

Workspace-hosted GitHub slash-command intake for Gas City.

This pack keeps `gastown-hosted` generic. It runs the GitHub-facing service
inside the workspace and exports it through the normal published-service path:

- `github-webhook` is the public webhook endpoint GitHub calls
- `github-admin` is the tenant-visible setup and status surface
- both services share `.gc/services/github-intake/`

The current slice ships:

- GitHub App manifest/bootstrap hosted by the workspace service
- webhook signature validation
- durable receipt and request persistence
- `/gc review` and `/gc question` command parsing
- generic `gc sling` dispatch to repo-mapped formulas
- optional acknowledgment comments back to the PR using the imported app

The current slice does not yet post terminal review results. It queues or
rejects requests and records the outcome; downstream formulas still own the
actual review workflow and result publishing.

## Include It

```toml
[packs.github-intake]
source = "https://github.com/julianknutsen/packs.git"
ref = "main"
path = "github-intake"

[workspace]
includes = ["github-intake"]
```

## Publication

This pack expects helper-backed published services. After the workspace starts,
`gc service list` should show:

- `github-webhook` with public publication
- `github-admin` with tenant publication

Open the tenant-visible `github-admin` URL to register the GitHub App from the
hosted manifest helper.

## Repository Mapping

After app bootstrap, map repositories to slash-command targets:

```bash
gc github-intake map-repo owner/repo rig/polecat \
  --review-formula mol-github-review-pr-v0 \
  --question-formula mol-github-question-v0
```

That stores dispatch config locally under `.gc/services/github-intake/data/`.

## Manual App Import

If the manifest flow is not suitable, you can import an existing app:

```bash
gc github-intake import-app \
  --app-id 123456 \
  --client-id Iv1.example \
  --webhook-secret "$GITHUB_WEBHOOK_SECRET" \
  --private-key-file ./github-app.private-key.pem
```

## Inspect Status

```bash
gc github-intake status
gc github-intake status --json
```
