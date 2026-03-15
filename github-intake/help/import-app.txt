Import an existing GitHub App into the shared intake state.

Examples:
  gc github-intake import-app \
    --app-id 123456 \
    --client-id Iv1.example \
    --webhook-secret "$GITHUB_WEBHOOK_SECRET" \
    --private-key-file ./github-app.private-key.pem

Optional fields:
  --client-secret <secret>
  --slug <app-slug>
  --html-url <https://github.com/apps/...>

This is the manual fallback for environments where the hosted manifest flow is
not used.
