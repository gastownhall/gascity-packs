---
name: verify-frontend-ux
description: ENFORCES functional, browser-driven USER EXPERIENCE testing of every frontend page in the active project. Triggers whenever frontend work is touched, a page/route/component is added or modified, a deploy is contemplated, or work is about to be declared "done". This skill is NOT satisfied by unit tests, integration tests, snapshot tests, API tests, curl, HTTPie, or any non-rendering check. It REJECTS those as evidence of completion. The only acceptable evidence is a real, rendered browser session interacting with each page, each element, each form field, each button, each navigation transition, and each error state — exactly the way a human user would.
---

# verify-frontend-ux

## THE ONE RULE

**Code tests and API tests DO NOT REFLECT ACTUAL USER EXPERIENCE.**

A passing test suite is not proof the UI works. A 200 response from an API is not proof the UI works. A successful build is not proof the UI works. A clean type-check is not proof the UI works.

**The ONLY proof the UI works is a real browser, rendering the real pages, with a real interaction loop completed end-to-end.**

If you have not driven a browser against the running app, the UI is unverified. Treat it as broken until proven otherwise.

## WHEN THIS SKILL FIRES

Activate this skill — without being asked — the moment ANY of the following are true:

- A frontend file changed (`.tsx`, `.ts`, `.jsx`, `.js`, `.vue`, `.svelte`, `.html`, `.css`, `.scss`, Yew/WASM Rust components, Razor pages, Blazor components, Angular templates, etc.).
- A new route, page, view, or component was added.
- An existing page's behavior, layout, copy, validation, or data flow changed.
- A backend change that the frontend consumes was made (API contract, response shape, auth flow).
- The user says "done", "ready", "ship it", "deploy", "looks good", "merge".
- A PR is being prepared, reviewed, or merged.
- The user asks "does it work?" or "is it working?".
- A bug fix is claimed.

If frontend code is in scope and this skill has not run, **the work is incomplete by definition.**

## WHAT THIS SKILL REJECTS AS EVIDENCE

The following are **NOT acceptable** as proof that the frontend works. If you offer any of these as completion evidence, you are wrong:

- "The tests pass." — Tests test code, not user experience.
- "TypeScript compiles cleanly." — Compilation is not rendering.
- "The build succeeded." — Builds produce artifacts, not verified UX.
- "I ran the linter." — Lint catches syntax, not broken UX.
- "I called the endpoint with curl/httpie/Postman/Insomnia and got 200." — APIs are not pages.
- "The component renders in isolation in Storybook." — Storybook is not the app.
- "The unit test for that hook passes." — Hooks in isolation are not the app.
- "The integration test passes." — Headless integration tests are not user experience.
- "I read the code and it looks correct." — Reading is not running.
- "The page loaded." — Loading is not interacting. A blank white page also "loads".
- "I checked the network tab and the request fired." — The request firing is not the UX completing.
- "Cypress / Playwright passed in CI." — A green CI run for selectors that bypass real interaction is not UX verification. (Playwright IS acceptable when used to drive real interactions per the workflow below.)

## WHAT THIS SKILL REQUIRES AS EVIDENCE

For every page, view, or route in scope, the following must be performed against a **live, running, rendered browser** (Chromium, Firefox, or WebKit — your choice, but a real one):

### 1. Existence verification

- The page actually loads at the expected URL.
- HTTP status is 200 (or the documented expected status).
- The page renders DOM — not a blank body, not an error page, not a framework's "404", not a hydration crash, not a CORS wall.
- The page title, header, or primary heading is present and correct.
- No console errors. No console warnings related to the page. No unhandled promise rejections.
- No 4xx/5xx requests in the network tab unrelated to expected behavior.

### 2. Functional interaction — every element

For **every interactive element** on the page, perform the user action and verify the result:

- **Every link**: click it. Verify it navigates to the right place. Verify the target page renders.
- **Every button**: click it. Verify the documented behavior. Verify side effects (toasts, modals, navigations, state changes) actually happen visually.
- **Every form field**: type into it. Verify the value is accepted. Verify validation triggers correctly on invalid input. Verify validation passes on valid input. Verify required fields actually block submission.
- **Every form**: submit it with valid data. Verify success state. Submit it with invalid data. Verify error states display correctly and are readable.
- **Every dropdown/select**: open it. Pick options. Verify the selection is reflected.
- **Every checkbox/radio/toggle**: flip it. Verify state changes are visible.
- **Every modal/dialog/drawer/popover**: trigger it. Interact inside it. Close it via X, via escape, via backdrop click, via cancel button — every documented close path.
- **Every tab/accordion/collapsible**: open and close each panel.
- **Every table**: verify sorting, filtering, pagination, row actions work.
- **Every navigation menu**: hover, expand, click — verify every entry routes correctly.
- **Every loading state**: verify skeletons/spinners actually appear during async work.
- **Every empty state**: verify it renders when data is absent.
- **Every error state**: trigger it (kill the network, send bad data) and verify the user sees a useful message — not a stack trace, not a blank page, not a stale UI.

### 3. Navigation flow

- Click through the full happy path of the feature, page-to-page.
- Use the browser back button. Verify state is preserved or restored correctly.
- Use the browser forward button. Same check.
- Hard-refresh on each page. Verify it survives a reload (no lost auth, no broken hydration).
- Open the page in a new tab via direct URL. Verify deep-linking works.

### 4. Real-world conditions

- **Auth states**: logged-out users see the right thing. Logged-in users see the right thing. Role-restricted pages reject the wrong roles visibly.
- **Responsive**: resize the viewport to mobile, tablet, desktop widths. Verify the layout does not collapse, overflow, or hide critical actions.
- **Slow network**: throttle to 3G in DevTools. Verify loading states appear and the UI does not appear frozen.
- **Empty data**: log in as a fresh user with zero data. Verify empty states are not broken.
- **Stale data**: leave the tab open, return later. Verify nothing is silently broken.

### 5. Console and network hygiene — per page

- Open DevTools. Reload the page. Read the console.
- Zero red errors. Zero unhandled promise rejections. Warnings get triaged.
- Network tab: every request you expected fires. No surprise 401s, 403s, 404s, 500s.

## HOW TO ACTUALLY DO THIS

Pick the highest-fidelity tool available **in this order**, top to bottom:

1. **Playwright driving a real browser**, with a script that performs the interactions above (clicks, types, assertions on visible text, screenshots saved to `<project>/.scratch/ux-verify/<timestamp>/`). This is the strongest automated evidence. Save screenshots on every page and on every failure.
2. **Puppeteer** with the same approach.
3. **A Chrome DevTools MCP / browser MCP** if available — drive interactions through it, capture screenshots, capture console, capture network.
4. **Manual hand-off to the user**: spin up the dev server, give the user the URL, give them the explicit click-list above, ask them to confirm each item. Do NOT declare done until they confirm. If you hand off, the user's confirmation IS the evidence — record it.

If none of these are available in the environment: **say so explicitly, do NOT claim the UI is verified, and ask the user how they want to proceed.** "I cannot drive a browser here" is an honest answer. "Tests pass so it's fine" is not.

## DELIVERABLE

When this skill runs, produce a short report. Format:

```
## Frontend UX Verification — <feature/branch>

App URL: <url>
Tool: <Playwright | Puppeteer | manual | ...>
Browser: <Chromium 130 | Firefox | ...>
Date: <YYYY-MM-DD>

Pages verified:
- /path/one — PASS — <one line on what was clicked/typed/asserted>
- /path/two — PASS — ...
- /path/three — FAIL — <what broke, console error, screenshot path>

Console: clean | <list of errors>
Network: clean | <list of bad responses>
Screenshots: <path to .scratch/ux-verify/<ts>/>

Verdict: SHIPPABLE | NOT SHIPPABLE — <one-line reason>
```

Anything other than `SHIPPABLE` means the work is **not done**.

## REINFORCEMENT — READ THIS EVERY TIME

- Tests test **code**. The UI is what users see. **They are not the same thing.**
- A green test suite has shipped broken UIs forever. It will ship broken UIs again.
- "I checked the API and it returns the right JSON" is not a frontend check. JSON is not a button.
- "The component is correct in isolation" is not a frontend check. Users do not use components in isolation.
- The browser is the **only** environment that reflects the user's reality. Everything else is a proxy and proxies lie.
- If you have not opened the page, clicked the things, and read the console, you have not verified the frontend. Period.

## DO NOT

- Do NOT substitute API curl checks for UI checks.
- Do NOT substitute unit tests for UI checks.
- Do NOT substitute "the build is green" for UI checks.
- Do NOT declare a frontend task complete on the basis of code review alone.
- Do NOT skip pages because "they probably still work" — verify each one touched, plus any page that consumes the changed code.
- Do NOT reduce the click-list because "this part wasn't changed" — regressions are precisely the things you didn't expect to break.
- Do NOT close the loop until the verdict is `SHIPPABLE`.
