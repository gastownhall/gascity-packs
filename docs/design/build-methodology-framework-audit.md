# Build Methodology Framework Audit

This audit compares the vendored Superpowers, Compound Engineering, BMAD
Method, garrytan/gstack, and Cursor pstack workflows against the Gas City
build methodology implementation.

## Core Rule

Raw-framework subagents become Gas City fanouts. Vendored skills, prompts, and
persona files are methodology source material. Gas City owns work routing,
durability, retries, fanout/fanin, and observable state through formulas, beads,
convoys, drains, and expansion children.

## Current Coverage

| Framework | Best Raw Idea | Gas City Coverage | Remaining Gap |
| --- | --- | --- | --- |
| Superpowers | Design/spec approval before implementation, TDD task execution, spec-compliance review before code-quality review. | `superpowers-brainstorming` preserves design and written-spec approval loops. `superpowers-development` and `superpowers-development-item` run TDD per task. `superpowers-task-review` now converts per-task spec-compliance and code-quality reviewer handoffs into graph lanes. | Mode vocabulary still lives partly in toolkit-specific vars such as `brainstorming_approval_mode`; direct interactive defaults and adapter-safe autonomous defaults should converge on `interaction_mode`. |
| Compound Engineering | Wide persona review roster, cheap selector gates, structured review synthesis, and different human/agent review modes. | `compound-code-review` maps always-on, conditional, stack-specific, gap-analysis, synthesis, and apply-fix lanes into one review expansion. `compound-plan-review` provides a multi-lane plan review loop. | Planning parity is still thin: output format, resume behavior, and interactive/headless prompt behavior should become first-class planning vars/assets. Review authority should converge on `review_mode`. |
| BMAD Method | Disciplined PRD -> architecture -> epics/stories -> readiness -> story implementation lifecycle with step-file execution and adversarial review. | `bmad-build` maps the full lifecycle onto `build-base`. `bmad-story-development` converts quick-dev handoffs into implementation, self-check, acceptance-audit, and fix lanes. `bmad-code-review-flow` preserves adversarial review fanout. | BMAD activation/config/customization, language settings, frontmatter progress, and menu/checkpoint behavior are still mostly prompt guidance rather than explicit bootstrap/step formulas. |
| garrytan/gstack | A founder-friendly sprint: office-hours intake, CEO/design/eng/DX plan review, staff review, QA, CSO security, document-release, ship, and deploy readiness. | `gstack-build` maps Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect onto `build-base`, with explicit `gstack-plan-review`, `gstack-code-review`, `gstack-qa-review`, and `gstack-release-readiness` fanouts. | Browser/runtime-specific tools such as GStack Browser, taste memory, and cross-agent browser pairing remain reference behavior for now. The beginner pack should stay focused on one approachable factory path before adding those advanced surfaces. |
| Cursor pstack | 21 principles, method skills, and playbooks as a principle-gated factory. | `pstack-build` maps principle selection, subtraction, foundation, and lever decision onto `build-base`. Method formulas (`pstack-how`, `pstack-swarm`, `pstack-arena`, `pstack-interrogate`) stay sequential Gas City graphs. | Cursor `watch-pr` / `orch.ts` remain vendor corpus. Dest-env OpenSpec archive is host-only. |

## GC-METH-012 Disposition

`GC-METH-012` (external implementation compatibility) was deferred while no
concrete derived-pack implementations existed in the scanned evidence set. That
deferral is now resolved: all five derived packs carry pack-local compatibility
ledgers, and a dedicated test module proves the compatibility contract for
every pack.

| Evidence | Location |
| --- | --- |
| Compound Engineering ledger | `compound-engineering/REQUIREMENTS.md` |
| Superpowers ledger | `superpowers/REQUIREMENTS.md` |
| BMAD ledger | `bmad/REQUIREMENTS.md` |
| gstack ledger | `gstack/REQUIREMENTS.md` |
| pstack ledger | `pstack/REQUIREMENTS.md` |
| Compatibility tests | `gascity/tests/test_derived_pack_compatibility.py` |

The test module inspects all five packs for: `imports.gc.source = "../gascity"`
in `pack.toml`; a top-level formula that extends `build-base` with the base
anchors in order; `[metadata.gc.methodology]` restricted to the allowed
vocabulary; selector defaults for planning, decomposition, implementation,
implementation item, review, and review fix; separate and same-session drain
definitions (or a declared convoy-step strategy); local route targets backed by
providerless agents; the shared claim protocol in every agent prompt; no
provider-native subagent/task-tool dispatch in prompt assets; and pack-local
ledgers anchoring `GC-METH-012`.

All five packs pass, so the `GC-METH-012` rows in `gascity/REQUIREMENTS.md`
(Scenario Ledger and Deferred Follow-Up Requirements) record the requirement as
covered. Reproduce with:

```sh
python3 -m pytest gascity/tests/test_derived_pack_compatibility.py -q
```

If a future change breaks an individual pack, mark only that pack's ledger
entry blocked with a rationale and return `GC-METH-012` to deferred until the
pack passes again.

## Proposed Updates

1. **Standardize launch modes.**
   Add canonical `interaction_mode` and `review_mode` vars to concrete build
   methodology formulas and GitHub adapters while preserving existing legacy
   vars as compatibility aliases.

2. **Add a beginner-friendly methodology quickstart.**
   Add a README table with three copy-paste launch commands:
   `gstack-build` for founder-to-release sprint shape, `superpowers-build`
   for design/TDD discipline, `compound-build` for heavy review fanout, and
   `bmad-build` for product-to-story structure.

3. **Promote structured prompt files into small formulas.**
   BMAD step-file workflows and Compound planning/resume flows should become
   shallow expansion formulas where the graph boundary adds value: retry,
   resume, approval, artifact checks, or fanout. Keep simple one-shot prompt
   steps as assets.

4. **Show the factory graph in artifacts.**
   Have each concrete build write a short `factory-run.md` summary: selected
   methodology, interaction/review modes, major fanouts, artifact paths, and
   next human action. This makes Gas City approachable for first-time users
   without asking them to inspect beads manually.

5. **Keep adapter runs conservative.**
   GitHub PR review should stay report-only by default. GitHub issue-fix can
   use autonomous planning and review-fix loops, but any public posting or PR
   publication remains explicitly gated by adapter vars such as `post_mode` and
   `pr_mode`.

6. **Document the "why this is better than raw skills" story.**
   For each third-party README, keep one short paragraph explaining that users
   get the familiar framework process plus Gas City durability: persistent work
   beads, restartable formula steps, observable fanouts, and adapter-safe
   automation.

## Good First Demo Path

For a first introduction to automated software factories, start with
`gstack-build` because it mirrors a startup sprint in plain language:
office-hours, plan review, build, code review, QA, release readiness, finalize.
Then show `superpowers-build` for design/TDD discipline, `compound-build` on
the same task to demonstrate review fanout, and `bmad-build` to demonstrate
product-to-story decomposition.

The demo should avoid provider-native subagents entirely. Every visible
parallelism point should be a Gas City fanout with beads the user can inspect.
