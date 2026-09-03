Walk the app against `$RUN_DIR/checklist.md` in the browser.

Read `smoke.mode`, `smoke.session` and `smoke.run_dir` from the workflow
root bead's metadata (`gc bd show <root bead id> --json`). In `cloud` mode
every browser call addresses the remote session `smoke.session`; in `local`
mode, the local headless browser.

- Start at {{app_url}}. Screenshot every checkpoint into `$RUN_DIR` — one
  file per check (`<check-id>.png`), referenced by bare filename from the
  verdict.
- Record every URL you visit.

**Auth:** in cloud mode you are signed in AS the operator via their profile —
treat every click as if they made it. If a login screen still appears
(profile session expired), or in local mode (which has no app sign-ins), do
NOT attempt credentials — you have none, and never try to satisfy a second
factor or passkey. Record the check as `blocked: auth`, verify what is
verifiable unauthenticated (page loads, branding, redirect behaviour), and
say so in the verdict.

**Safety rails — this is production with real data:**
- Non-destructive by default. No sending email, no rejections, no votes or
  decisions, no state mutation — unless the feature under test *is* that
  action and the change is reversible. Anything you do change goes in
  `state_changes`.
- Stay in the app: only the {{app_url}} origin and its sign-in hop.
- Never capture credentials — no screenshots of account choosers, consent
  screens, cookies, tokens, or session values.

**Design checks — only when checklist.md has a `Frame:` line:**

- Render the frame for cropping in the LOCAL headless browser. It is
  separate from the remote session that drives the app; both run at once.
  With a CDP client (adapt the calls to your harness):
  1. `Emulation.setDeviceMetricsOverride` with the frame viewport from the
     checklist (e.g. width 1280, height 900, deviceScaleFactor 1, mobile
     false);
  2. open `file://<the saved artifact HTML path>#/<page>` and wait for the
     inline JavaScript to fill the dynamic containers;
  3. for each design check, evaluate the element's box in the page —
     `(function(){var e=document.querySelector(<selector>); if(!e) return null; var b=e.getBoundingClientRect(); return {x:b.x+scrollX,y:b.y+scrollY,width:b.width,height:b.height,scale:1}})()`
     — and pass it as `clip` to `Page.captureScreenshot` (`format: png`,
     `captureBeyondViewport: true`); write `$RUN_DIR/design-N-frame.png`.
     A `null` box means the selector is wrong: fix the selector, never skip
     the crop.
- Crop the LIVE page the same way in the session that drives the app: the
  same `Emulation.setDeviceMetricsOverride` width as the frame, then
  `Emulation.clearDeviceMetricsOverride` before the non-design checks —
  into `design-N-live.png`. When the element is ABSENT, crop the region
  where the frame places it (the neighbouring landmark that does exist, or
  the whole viewport) so the pair still shows the gap.
- Every design check gets the PAIR `design-N-frame.png` + `design-N-live.png`
  under `$RUN_DIR`, both named in that check's `evidence` and both written
  next to the check in checklist.md.
- Derive every result and cause fresh from THIS run's crops and the rules in
  THIS step. Never carry a previous run's checklist.md, verdict.json or
  causes forward — not for the same deployment, not from your own earlier
  session: an earlier run's causes were written under earlier rules, and a
  templated verdict is not a verification.
- Judge each of the three sub-criteria. A frame element ABSENT from the page
  is a FAIL — even if the PR body declares it out of scope. A check that
  fails carries a `cause`; decide it in this order, exactly one:
  1. `declared divergence (PR body: "<quoted phrase>")` — the PR body
     documents the omission or the degradation, either by naming the element
     or by declaring its region / the reframe it belongs to out of scope (a
     blanket "the page reframe was not built" / "the layout stays as it is"
     documents every element of that reframe — quote that sentence). This
     wins over the three below whenever the PR body speaks.
  2. `missing` — absent, and the PR body is silent about it and its region;
  3. `misplaced: <where it is> vs <where the frame puts it>` — present, wrong
     place, undocumented;
  4. `shape: <what differs, in your own words>` — present, wrong labels /
     counts / controls, undocumented. Describe THIS element's difference
     (e.g. `shape: empty activity list, no groups or rows (data: 0 items on
     this record)`); never reuse an example's wording.
  A region that is empty on the frame's own record is a `shape:` FAIL, not
  `blocked` — the frame-vs-page difference is the finding even when the
  cause is data. `cause` appears only on fails, plus the single passing
  form `operator-authorised divergence (tracker: "<quoted line>")` — a pass
  only when the tracker line records the operator's decision naming this
  element. A behaviour-only conflict (sorts, routes, gating, a state toggle
  such as disabled-at-ends, a fade vs hidden mechanism) on an element that
  IS present, placed and shaped is the builder's "shipped truth" territory:
  `pass`, the divergence in `notes`, no `cause`. Never fold a frame-element
  divergence into `notes` as an observation: it is a `fail` with a `cause`,
  so the operator sees the scope decision, not a green tick.
- `scope-1` follows the checklist's rule: FAIL unless every omission has an
  authorising tracker quote; put the quote (or `none`) in `authorised_by`
  and name `scope-1.md` as its evidence.

Write `$RUN_DIR/verdict.json`:

```json
{
  "app_url": "{{app_url}}",
  "verified_at": "<ISO-8601 UTC>",
  "visited": ["..."],
  "frame": {"url": "<artifact URL or none>", "section": "<#/page>", "mocked_on": "<record route>",
            "live_url": "<the page you drove>", "viewport": "1280x900"},
  "checks": [
    {"id": "intent-1", "dimension": "intent",
     "criterion": "<the check, in your words>",
     "result": "pass|fail|blocked",
     "notes": "<what you saw>", "evidence": ["intent-1.png"]},
    {"id": "design-3", "dimension": "design",
     "element": "<frame element, e.g. metric band — 4 tiles with bars + breakdowns>",
     "criterion": "present / placed <where the frame puts it> / shape <labels, counts, controls>",
     "result": "pass|fail|blocked",
     "cause": "declared divergence (PR body: \"<quoted phrase>\")",
     "notes": "<what the live page shows there instead>",
     "evidence": ["design-3-frame.png", "design-3-live.png"]},
    {"id": "scope-1", "dimension": "scope",
     "criterion": "bead and PR scope no less than tracker and frame, or an operator decision on the tracker",
     "result": "pass|fail",
     "cause": "unauthorised shrink at <bead|PR|bead + PR>: <elements>",
     "authorised_by": "<verbatim tracker line, or none>",
     "notes": "<the tracker lines you read>", "evidence": ["scope-1.md"]}
  ],
  "state_changes": [],
  "notes": "<anything the operator should know>"
}
```

Close with `gc.outcome=pass` (a failing verdict is this step's output, not a
failure of this step).

**Exit criteria:** every checklist item has a result in verdict.json with a
screenshot (a frame + live PAIR for every `design-N`), or a recorded reason
it was blocked.
