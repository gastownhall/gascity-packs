Verify the browser and the app before deriving any checklist.

Resolved app URL: {{app_url}}
Resolved run root override: {{run_root}} (empty means use the rig artifact root)
Resolved remote browser profile: {{cloud_profile_id}} (empty means the local browser)
Resolved report recipient: {{report_to}}

**1. Browser.** Use the browser tooling your city provides to agents (a
browser skill, a CDP-driven headless Chromium, a remote signed-in browser
session). The steps of this workflow name the capability they need, not a
tool: open a URL, run JavaScript in the page, set the viewport size, and
capture a screenshot of the viewport or of one element.

Prefer a **remote signed-in session** when `{{cloud_profile_id}}` is
non-empty and your tooling offers one: start it named `smoke-<root bead id>`
with that profile. On success record `smoke.mode=cloud` and
`smoke.session=smoke-<root bead id>` in the workflow root bead's metadata,
and put any live-view URL the session prints in the root bead notes so the
operator can watch.

If the profile id is empty or the remote start fails (missing auth, API
error), fall back to the **local headless browser**: record
`smoke.mode=local` and note that auth-gated checks will be blocked — you
have no credentials and must not attempt any.

**2. App reachability:**

```bash
curl -s -o /dev/null -m 15 -w "%{http_code}" "{{app_url}}"
```

Any HTTP status < 500 counts as reachable (a login redirect or a 404 on the
bare root is fine — the app is up). Connection failure, DNS failure, or a
5xx means the deploy itself is down.

**3. Run directory.** Read the current step bead with
`gc bd show <current-step-bead-id> --json` and take `gc.root_bead_id`; hard-fail
if it is missing. Resolve a run directory under the artifact root and record
it on the workflow root:

```bash
RUN_DIR="$({{pack_root}}/assets/scripts/artifacts.py path --override "{{run_root}}" \
  --relative "/smoke-runs/$(date -u +%Y%m%d-%H%M%S)-<root bead id>/" --mkdir-parents --directory)"
gc bd update <root bead id> --set-metadata smoke.run_dir="$RUN_DIR"
```

Later steps and the operator find everything under `smoke.run_dir`.

**If the browser cannot start or the app is unreachable:** do not continue.
Mail {{report_to}} with subject `smoke-test BLOCKED: {{app_url}}` and the
exact failing command output
(`gc mail send {{report_to}} -s "smoke-test BLOCKED: {{app_url}}" -m "<output>"`),
then close this step with `gc.outcome=fail` and
`gc.failure_class=<browser-unavailable|app-unreachable>`.

**Exit criteria:** browser session responding, app URL reachable,
`smoke.run_dir` recorded on the root bead.
