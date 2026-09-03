Turn the change context into 3–8 concrete browser checks — and, when an
approved design frame is in play, a DESIGN section derived from the FRAME
(not from the PR) plus one scope-shrinkage check.

Change context: {{change_context}}
Focus: {{focus}}
Design frame: {{design_frame}}

`RUN_DIR` is `smoke.run_dir` in the workflow root bead's metadata
(`gc bd show <root bead id> --json`).

**A. Non-design checks (3–8, capped):**

- If the context references a GitHub PR or issue, read it
  (`gh pr view <url> --json title,body,files` / `gh issue view <url>`) and
  derive checks from what actually changed.
- If the context is empty, write a general smoke: app loads, primary
  navigation works, the main list/dashboard surfaces render with data, no
  visible error states on the core pages.
- Cover three dimensions, at least one check each where the context allows:
  **intent** (does the shipped change do what was asked), **interface** (do
  the affected screens look and behave right), **functionality** (do the
  core flows still complete).

**B. Is a frame in play?** Decide this explicitly and write the answer as
the first line of checklist.md — `Frame: <artifact URL> #/<page> — mocked on
<record> (from design_frame | detected from <where>)` or `Frame: none`.

- `design_frame` non-empty → yes; it names the artifact URL, the page anchor
  and the record the frame is mocked on.
- `design_frame` empty → still yes if the change context, the PR body, the
  work bead (the bead id in the PR title / body / branch — `gc bd show <id>`)
  or the campaign tracker (the bead the work bead names as its campaign)
  references a design artifact URL, or a campaign tracker bead that names
  one. Take the URL from wherever it appears, the page from the work bead's
  "source of truth" line (else the artifact page whose route line matches
  the changed route), and the record from that route line. Say in
  checklist.md where you detected it.
- Neither → `Frame: none`; skip sections C and D.

**C. DESIGN section — only when a frame is in play.** The 3–8 cap above
does NOT apply here: one check per frame element, however many there are.

1. Open the frame with the artifact reader your session provides (in Claude
   Code, the Artifact tool's `read` action) — never `curl` the artifact URL:
   a plain fetch returns the hosting shell, not the design. The read saves
   the full HTML to a local file path it prints; keep that path (the drive
   step renders it). If no artifact reader is available, read the saved
   copy the campaign tracker names; if neither is readable, every design
   check is `blocked: frame unreadable` — still never curl.
2. Find the page and its frame container. A design artifact of this kind is
   a multi-page HTML mock: pages are hash-addressable (`#/<page>`), each
   page states the app route it is mocked on (a route line at the top of the
   frame) and wraps the mocked product page in one frame container (for
   example a `.frame` element that begins with that route line). Use the
   page's default mock state unless the work bead names a variant. Dynamic
   containers are filled by the artifact's inline JavaScript — enumerate
   from the RENDERED frame (render recipe in the drive step), never from
   empty containers in the markup. Enumerate only what sits INSIDE the frame
   container — the mocked page. Everything the artifact places OUTSIDE it —
   its own demo controls (view / phase / state switches), prose, diagnostic
   tiles, option cards, comparison tables, "what moved" notes — is
   rationale, not a frame element: a control outside the frame is never a
   check. Where such a demo control has a product equivalent inside the
   frame (an A/B/C option selector beside the frame vs the in-frame view
   switch that ships option A), the check targets the in-frame element,
   never the demo control.
3. Live target: the SAME record the frame is mocked on (the route line; a
   truncated id resolves through the app's own search — the frame usually
   names the entity). If that record is unreachable, a stand-in in the same
   state, and say so. Frame viewport = the artifact's content width (its
   page `max-width`; e.g. 1240px → drive at 1280 wide). Write both down.
4. Enumerate the frame's regions and elements top-to-bottom (identity
   block, facts line, score block, each metric tile, an action band and its
   buttons, each side-rail card, the main region's heading, filters, group
   headers, row anatomy, footer panels …) and write ONE check per element,
   id `design-1`, `design-2`, … in frame order, each with three
   sub-criteria:
   - **present** — the element exists on the live page;
   - **placed** — where the frame puts it: region order, column, rail vs
     main, above/below which neighbour;
   - **shape** — it carries the frame's data shape: the labels, the counts
     and bars, the controls (buttons, filters, tabs). Values are the
     record's own (the mock's figures are a fixture); shape is what is
     compared. A region that renders empty or as bare numbers where the
     frame shows rows / bars / filters does not match the shape — even when
     the cause is production data, that is a frame-vs-page difference to
     report.
   Name the CSS selector or landmark of each element in the frame so the
   drive step can crop it. An element whose shape needs data (rows, groups,
   bars) is still checked on the frame's own record: if that record renders
   it empty, the check FAILS on shape (`blocked` is never the answer for an
   empty frame region) — a same-state stand-in may ADD a note on the
   anatomy, never replace the frame's record.
5. Operator-authorised omissions: before writing the checks, read the
   campaign tracker's notes for operator decisions that refuse a frame
   element (e.g. "the assignee chips are NOT to be built"). List those
   elements too, tagged `operator-authorised divergence (tracker: "<quoted
   line>")` — they are the only omissions that will not fail.

**D. SCOPE-SHRINKAGE check — only when a frame is in play.** One check, id
`scope-1`. Read three scopes: the work bead's (`gc bd show <work bead>`),
the campaign tracker's scope line for this change (the bead the work bead
names as its campaign), and the frame's element list from C. Then read the
PR body's scope / divergence sections. The check FAILS when the bead or the
PR scopes LESS than the tracker or the frame without an operator decision
recorded ON THE TRACKER that authorises that omission. An authorisation is
a tracker line that records an OPERATOR decision (names the operator, a
mail id, or "operator approved/decided") and names the omitted element;
quote it verbatim in the check. A scope one-liner that merely does not
mention an element is NOT an authorisation —
silence never authorises, a PR body never does, a bead never does, and a
later tracker line revokes an earlier one. Write the check as: which
elements shrank, where (bead vs PR), and either the authorising quote or
`no operator decision on the tracker → FAIL`. Save the three scopes and the
PR's scope section verbatim to `$RUN_DIR/scope-1.md` as its evidence.

Write the checklist to `$RUN_DIR/checklist.md`: the `Frame:` line first,
then one check per line with an id (`intent-1`, `interface-1`,
`functionality-1`, …; `design-N`; `scope-1`), what to do, and what passing
looks like.

Close with `gc.outcome=pass`.

**Exit criteria:** `$RUN_DIR/checklist.md` written with 3–8 non-design
checks and — when a frame is in play — a `Frame:` line, one `design-N`
check per frame element (uncapped) and one `scope-1` check.
