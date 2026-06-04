# model-advisor v3 — shared build brief (deferred features, DESIGN §7.3)

You are one of 8 parallel builders implementing a single deferred feature from
`docs/DESIGN.md` §7.3 into the **model-advisor** gc pack at
`/Users/jayse/Code/packs/model-advisor`. Read this brief, then your feature spec
(in your task prompt). Read `docs/DESIGN.md` (the spec) and the modules you extend.

## What the pack does (one paragraph)

model-advisor routes each gc agent dispatch to the cost-minimal model **tier** that
preserves quality. It keeps a per-cell `Beta(a,b)` posterior over dispatch quality,
keyed `provider::agent::shape::tier_id`, learned from bead-closure telemetry. The
decision rule (`modeladvisor/engine.py::recommend`) is a 4-layer Conservative
Constrained Thompson Sampling policy: (L1) Beta posteriors, (L2) a conservative gate
admitting a cheaper tier iff its **Wilson lower bound** clears `baseline_mean − q_tol`,
(L3) asymmetric-loss selection with class multipliers (`Critical=∞` never downgrades)
scaled by a blast-radius `N_dep`, (L4) an uncertainty-triggered eval flag. It is
pure/deterministic/seedable; the store materialises posteriors from
`.beads/telemetry/invocations.jsonl`.

## HARD RULES (do not violate)

1. **Stdlib-only.** Import only the Python standard library — `math`, `statistics`
   (`NormalDist`, `mean`, `pstdev`), `random` (`betavariate`, seeded `Random`),
   `json`, `dataclasses`, `bisect`, `collections`, `typing`. **No** `scipy`, `numpy`,
   `pandas`, `pymc`, `scikit-learn` in the core. (One feature may add an *optional,
   import-guarded* heavy backend — yours will say so explicitly if it applies.)
2. **Match the house style.** `from __future__ import annotations`; full type hints;
   a module docstring and per-function docstrings that **cite the DESIGN section**;
   `@dataclass` for state; pure functions where possible (no hidden I/O/globals);
   deterministic and, where randomness is used, **seeded and reproducible**.
3. **Write ONLY your two new files** — `modeladvisor/<feature>.py` and
   `tests/test_<feature>.py`. **Do NOT edit** `engine.py`, `store.py`, `config.py`,
   `cli.py`, `ingest.py`, `autoapply.py`, `__init__.py`, `pack.toml`, or the README.
   Other builders are editing nothing there either; we avoid races by having each of
   you deliver a **hook-spec** (below) that the integrator applies to those shared
   files in one serialized pass.
4. **Your module must import and unit-test standalone against the code as it is now.**
   It must not depend on a config knob or shared-file change that doesn't exist yet.
   Achieve this by having your functions take their tunables as **parameters with
   sensible defaults** (e.g. `def conformal_lcb(cell, buffer, z, *, min_buffer=20)`).
   The integrator wires the real config knob to supply those params later.
5. **Run only your own test file**, with the pack venv, cache disabled:
   `./.venv/bin/python -m pytest tests/test_<feature>.py -p no:cacheprovider -q`.
   Do **not** run the whole suite (the other builders' half-landed work isn't wired
   yet). Aim for ≥ 8 focused tests covering the happy path, edge cases (empty/thin
   data), determinism, and the documented degenerate fallback.

## Architecture you extend (read the real source, this is the map)

- `modeladvisor/store.py` — `Cell` (`a`, `b`, `n`, `last_update`; `.mean/.variance/
  .stderr`; `.update(q,w,ts)` does the Beta `a+=w·q, b+=w·(1−q)` update). `CellStore`
  (`.get(key)`, `.pooled(provider,agent,shape,tier_id) -> Cell` capped pseudocount
  pooling, `.cells` dict, `.rebuild`/`.load`/`.save`, `.apply_quality(rec)` which today
  **drops non-binary q**). `cell_key()/parse_cell_key()`.
- `modeladvisor/engine.py` — `wilson_lcb(cell, z) -> float` (the swappable LCB),
  `recommend(agent, shape, cfg, store, *, provider, tol_class, baseline_tier, n_dep,
  tok_in, tok_out, seed) -> dict`, `inspect(...) -> dict`, `_ci_halfwidth`,
  `_expected_loss`. The `seed` param is already threaded for Thompson.
- `modeladvisor/config.py` — `AdvisorConfig` with `.hp` (hyperparameters:
  `z`, `alpha`, `pool_lambda`, `theta_eval`, `s_prior`, `w_close/w_review/w_eval`,
  `baseline_a/baseline_b/baseline_mean`, `cold_m_lo`), `.tier_ids` (cheapest→capable),
  `.tier(id)`, `.tol_class_for`, `.baseline_tier_id_for`, `.budget_for`,
  `.canonical_shapes_for`, `.agent_shapes`, `.default_provider`. **Read it** to see
  how `.hp` and classes are defined before you propose a new knob.
- `modeladvisor/ingest.py` — harvests bead-closure into `quality` telemetry records.
- `modeladvisor/cli.py` — `advisor` subcommands (`advise`, `inspect`, `apply`,
  `auto-apply`, …) using stdlib `argparse`. Look at one subcommand to copy the shape.

## Your deliverable: the structured report (return this as your final message)

Return a single fenced block the integrator can act on mechanically:

```
FEATURE: <bead-id> <name>
MODULE: modeladvisor/<feature>.py  (<N> lines)
TESTS:  tests/test_<feature>.py  (<M> tests, all passing — paste the pytest summary line)
PUBLIC API:
  - <exact signatures you expose, one per line>
INTEGRATION HOOKS (for the integrator to apply to shared files):
  - file: modeladvisor/<engine|store|config|cli>.py
    where: <function / anchor>
    add: |
      <the exact code to insert, copy-pasteable>
CONFIG KNOBS:
  - <name> (default <value>) — <meaning>; lives on <AdvisorConfig.hp | AdvisorConfig>
CLI:
  - advisor <subcommand> <args> — <what it prints/does>  (or "none")
SUMMARY: <2–3 sentences: what you built, the algorithm, any caveat/limitation.>
```

Keep the hook minimal and surgical — ideally a single dispatch line at the existing
call-site plus the knob. The integrator owns wiring, conflict resolution, the full
suite, and `gc lint`. Build the feature *correctly and faithfully to the paper*; a
small, exact, well-tested module beats a broad shaky one.
