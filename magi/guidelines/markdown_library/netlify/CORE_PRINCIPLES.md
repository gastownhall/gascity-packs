# Core Principles

These guidelines define strict, reproducible, and production-grade patterns for all sites and applications deployed to Netlify, optimizing for:

- **Configuration as Code**: `netlify.toml` is the single source of truth for build, deploy, and routing behavior. UI-only configuration creates invisible drift that no team member can audit, reproduce, or version.
- **Atomic Deploys**: Every deploy is a complete, immutable snapshot. Partial deploys, manual file uploads to production, and runtime filesystem mutations are architectural failures.
- **Edge First**: Static assets serve from the CDN by default. Dynamic behavior runs at the edge when latency matters, in serverless functions when compute duration matters. Choose the right primitive for the constraint.
- **Platform Primitives**: Netlify provides Blobs, DB, Image CDN, caching APIs, and scheduled functions. Use them before bolting on third-party infrastructure. Each external dependency adds a failure mode, a credential to rotate, and a billing dimension to monitor.
- **Git-Driven Workflow**: The deploy pipeline starts at `git push`. Branch deploys, deploy previews, and production publishes all originate from the repository. Manual CLI deploys exist for emergencies, not standard workflow.

### The netlify.toml Contract

The configuration file defines what gets built, how it gets routed, and where it runs. If a behavior cannot be expressed in `netlify.toml` or a corresponding `_headers`/`_redirects` file, document why the UI override exists and who owns it. Configuration that lives only in the Netlify dashboard is invisible to code review, unreproducible in disaster recovery, and impossible to audit across environments.

### Deploy Previews Are Mandatory

Every pull request generates a deploy preview with a unique URL. This preview reflects the **exact** build output that will reach production upon merge. Reviewers must validate behavior in the preview, not just read diffs. Teams that skip deploy previews introduce a verification gap between authored code and shipped artifacts.

---
[Back to Overview](./OVERVIEW.md)
