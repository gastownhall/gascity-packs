# gp-obim upstream twin

Fork draft: https://github.com/aphexcx/gascity-packs-prs/pull/47
Upstream base: 520e95cb22992a8a1017f7a60da267f203497c7e.
Final Go-tested/reviewed source: 62374eadd0f2f0bf1db84bdec274b209b1216bb3. Python ran at 76e76003; its code and test inputs are unchanged by the final Go-only concurrency fix.

The six fork implementation commits were cherry-picked onto that upstream base. The provenance transcript includes every original SHA. Conflict resolution added only the receipt startup block to upstream main, kept upstream's receipt-returning replay API, inserted the CHANGELOG bullet without importing fork history, and omitted fork-only delivery-session/own-thread bookkeeping. The durable store, tests and final canonicalized matching are the same as the reviewed fork source.

Upstream lacks the fork's emoji normalization prerequisites. The twin ports only the existing helper section, generated standard-name table, and its tests from d1348d0f, then applies the keyed matching fixes. The table accounts for most added lines. No dependency, manifest, inbound transport, or unrelated fork feature is imported.

Validation uses Go 1.26.5 darwin/arm64, GC_NO_INSTALL=1 and GC_TEMPLATE unset:

- upstream-go-tests.txt: 1,348 passing cases (719 top-level), no failed/skipped cases.
- upstream-go-race.txt: 126 passing cases (22 top-level), no race reports.
- upstream-python-tests.txt: 479 passed, 2 skipped, 2 existing os.fork multithreading warnings. The cached uv environment was used offline. The exact commands are in those transcripts.
- upstream-python-runner-notes.txt: upstream has no make test target and system Python lacks pytest; neither probe ran tests. No dependency install was needed.
- upstream-posted-text-assertions.diff: zero-context assertions against the upstream base.
- upstream-marker-after.txt: zero sibling matches and zero footer-contract docs matches. Existing turn_ref protocol substring matches are preserved.
- upstream-gate-prompt.txt and upstream-gate.txt: immutable upstream review. Fork native STANDARD and helper CLEAN records are in draft #47 at source 27e884fb.

Source validation does not include live Slack posts or rollout. The mayor owns Fable, merge, and rollout gates. Evidence-only commits do not alter the tested source.

The first transplant gate found concurrent replay metadata writes on storage failure. 62374ead fixes it by cloning metadata before replay mutation and annotating persistence failure on a private map. An integration test covers 16 concurrent retries for both confirmed and unavailable readbacks with unavailable storage; all retain exactly one Slack post. The same defensive copies and regression test are ported back to the fork, whose cache already deep-copies metadata. The first BLOCK record is preserved in upstream-gate-round1.txt.

Final validated upstream gate: VERDICT: CLEAN on 62374ead (upstream-gate.txt). Review was static; worker test transcripts above supply execution evidence.
