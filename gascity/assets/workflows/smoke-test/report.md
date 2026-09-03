Deliver the verdict. You report — you do not fix, and you do not post to
GitHub.

**1. Bead notes.** Write a human-readable summary of verdict.json to the
workflow root bead's notes (`gc bd update <root bead id> --append-notes "<summary>"`):
overall pass/fail/blocked, a one-line-per-check table (result, dimension,
criterion, what the browser saw), state changes if any, and the run
directory path.

**2. Mail {{report_to}}:**

```bash
gc mail send {{report_to}} \
  -s "smoke-test <PASS|FAIL|BLOCKED>: {{app_url}}" \
  -m "<the same summary; include the run directory so screenshots can be pulled>"
```

Overall result is FAIL if any check failed, BLOCKED if nothing failed but
one or more checks were blocked, otherwise PASS. A `design-N` or `scope-1`
fail is a fail like any other — a declared divergence is a red line, never
a green tick.

**Frame section** — when verdict.json has a `frame` (both the bead notes
and the mail carry it, after the check table):

```
Frame: <artifact URL> #/<page> — mocked on <record>; live <url> @ <viewport>
FAIL design-3 <element> — declared divergence (PR body: "<quoted phrase>") — design-3-frame.png / design-3-live.png
FAIL design-5 <element> — missing — design-5-frame.png / design-5-live.png
FAIL scope-1 — unauthorised shrink at <bead|PR>: <elements> — authorised_by: none
authorised: design-9 <element> — operator-authorised divergence (tracker: "<quoted line>")
```

List EVERY design fail with its cause and its screenshot pair, then the
scope check, then the operator-authorised divergences; never summarise the
fails away into a count.

**3. Stop the remote browser session** (billing ends when it stops). If the
root bead's metadata has `smoke.mode=cloud`, stop `smoke.session` and
confirm it is gone; if it is still alive, stop it once more. A failure here
is non-fatal, but note it in the root bead.

**4. Close out.** Record `smoke.reported=1` on the workflow root bead and
close this step with `gc.outcome=pass` whatever the verdict was — the
verdict is the output, not a failure of this step.

**Exit criteria:** verdict in root bead notes, mail sent, remote session
stopped (or noted), `smoke.reported=1` on the root bead.
