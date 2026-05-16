# Deploy Strategy

### Atomic Deploys Enforced

Every successful build produces a deploy — a complete, immutable snapshot of the publish directory, functions, and edge functions at that commit. Netlify serves the new deploy only **after** all assets are uploaded and verified. Visitors never see a partially deployed state.

This atomicity guarantee is foundational; do not undermine it with runtime file mutations or external asset loading from mutable sources.

### Deploy Previews

Deploy previews generate automatically for every pull request when continuous deployment is active.

| Aspect | Detail |
|:-------|:-------|
| URL format | `deploy-preview-{PR_NUMBER}--{site-name}.netlify.app` |
| Context | Uses `deploy-preview` context from `netlify.toml` |
| Blob stores | Share production stores by default — use deploy-scoped stores for write operations during preview testing |

### Branch Deploys

Enable branch deploys for long-lived branches (staging, QA, release candidates). URL format: `{branch-name}--{site-name}.netlify.app`. Configure which branches deploy in the UI or via API — deploying every branch wastes build minutes on feature branches that already have deploy previews.

### Rollbacks

Rolling back to a previous deploy is **instantaneous** — it changes which snapshot the CDN serves without rebuilding.

**Caveat:** Rollbacks only affect Netlify-served content. If the deploy included database migrations, external API configuration changes, or third-party webhook registrations, rolling back the deploy does not reverse those side effects. Design pipelines with rollback safety in mind: separate destructive external operations from the Netlify build/deploy lifecycle.

### Locked Deploys

Lock a deploy to prevent auto-publishing from overwriting it. Useful when production requires a specific known-good deploy while the team investigates an issue on a branch. Locked deploys prevent the auto-publish of new production builds but do not prevent new builds from running — they queue up and wait.

---
[Back to Overview](./OVERVIEW.md)
