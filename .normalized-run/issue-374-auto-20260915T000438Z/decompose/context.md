# Decompose source context — issue-374-auto-20260915T000438Z

Immutable bindings for the `decomposition-base` child. Every path below is
byte-hashed in `work/checkpoints/design-review.json` and
`work/design-review/result.json`; do not re-derive them from live refs.

| Binding | Value |
| --- | --- |
| Canonical Issue | https://github.com/gastownhall/gascity-packs/issues/374 |
| Idempotency key | gastownhall/gascity-packs:issue:374 |
| Source revision | 2026-08-29T06:21:43Z (immutable) |
| Base branch | main |
| Base SHA | 05031f2c66e080865c379ff799c7369430560a8f (immutable; never the live tip) |
| Work Contract | /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/work-contract.json |
| Work Contract sha256 | 04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616 |
| Embedded contract sha256 | 4e11cce03a6c6a21651d92a0643bcc6f4122bd8581fc4f1f2d583e6dc1923ef5 |
| Contract revision | issue-374-auto-20260915T000438Z.r1 |
| Approved design (plan_path) | /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md |
| Approved design sha256 | c1faf90fe3c4352182d152fef5efbbb9c1bb7547ef0c29cd1ae9efa03e38d57c |
| Design-review result | /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/design-review/result.json |
| Design-review result sha256 | 2532d1a7bf67f7c7f05fc17146ed7d8136823d72ce2cdaf6fad60a9c1c6e9d39 |
| Review status / verdict | approved / done (global verdict approve) |
| Review attempt | 3 (converged; zero edits applied in the final round) |
| Implementation work dir | /data/projects/gascity-packs |

## Scope

`mol-refinery-patrol`: skip the `rebase` step when the target is already an
ancestor of a merge-heavy source branch, so a valid fast-forward candidate is
not linearized into artificial conflicts and rejected on every retry.

## Acceptance criteria — every task must trace to at least one

- AC-374-01
- AC-374-02
- AC-374-03
- AC-374-04
- AC-374-05
- AC-374-06
- AC-374-07

No AC may be left orphaned and no bead may exist without an AC trace.

## Decomposition constraints

- The approved design is **immutable input**. Decompose it; do not redesign,
  re-litigate settled amendments, or reopen the review's accepted residuals.
- The design's own residual [Minor] items and implementation-time obligations
  are recorded in `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/design-review/attempt-3/apply-summary.md`. They are
  **directed follow-ups**, not new gates — carry them as tasks where the design
  mandates a PR obligation, never as blockers.
- Preserve the design's literal pin strings verbatim (e.g. the leg-7 fence text
  and the `SKIP-REBASE:` echo convention). Rewording them breaks the harness
  pins the design relies on for its red controls.
- Every task states its verification: the design pairs static literal pins with
  behavioral legs, and a task that drops one half of that pair is incomplete.
