"""Layer-4 **auto-scheduled eval** — rank gating cells and dispatch eval probes.

This is bead ``bh-0r9`` (v3): the deferred half of CC-TS Layer 4
(``docs/DESIGN.md`` §1.3 Layer 4, §5.4, §6.2, §7.3 "deferred").  v1 *records* the
uncertainty trigger and *surfaces* the highest-value eval per cell in
:func:`engine.inspect` (the ``widest_gating_cell`` pointer), but stops short of
acting on it.  This module closes that loop: it sweeps the configured
``(agent, shape)`` cells, asks the engine which cell is *gating a downgrade on
uncertainty*, ranks those cells by **posterior CI half-width × unlock-value**, and
emits eval-request beads for the top few — auto-dispatch proportional to width,
biggest-bang-for-the-probe first (DESIGN §5.4: "fires a deterministic eval-suite
run on that cell … proportional to posterior width").

The value of resolving a gating cell is the spend it would *unlock*: confirming a
downgrade from the baseline ``tier*`` to the gating candidate tier saves
``cost(tier*) − cost(candidate)`` per dispatch at the shape's representative
budget (DESIGN §2.3 / §5.4).  A wide CI on a cell that would unlock large savings
is the best place to spend an eval; a wide CI on a cell that barely saves anything
is not.  Hence ``score = ci_halfwidth × unlock_value`` and we take the top-k.

Design rules honoured (DESIGN §1.4, brief HARD RULES):

- **Stdlib-only**, ``from __future__ import annotations``, full type hints,
  per-function docstrings citing the design.
- **Reuse the gate.** The "is this cell gating on uncertainty?" decision is read
  straight from :func:`engine.inspect` (its ``widest_gating_cell``, which already
  applies the Layer-2 gate + the ``ci_hw > theta_eval`` filter + the Critical /
  ``force_baseline`` short-circuits).  We never re-implement the gate or the CI.
- **Pure planning, side-effect-gated emission.** :func:`schedule_evals` is a pure
  function of ``(cfg, store)`` — no I/O.  :func:`emit_eval_beads` only shells out
  when ``dry_run=False``; the default/test path returns command *strings* and
  touches nothing.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Optional

from modeladvisor import engine as _engine

# Label every scheduled eval-request bead carries, so the harvester / an operator
# can find them (``gc bd ready --label model-advisor-eval``) and the ingest path
# can later attribute the eval verdict back to the cell (DESIGN §4.3 / §7.3).
EVAL_LABEL = "model-advisor-eval"

# Bead type for an eval-request (a unit of work for whoever runs the eval suite).
EVAL_BEAD_TYPE = "task"


# --------------------------------------------------------------------------- #
# The scheduled request                                                         #
# --------------------------------------------------------------------------- #


@dataclass
class EvalRequest:
    """One ranked eval probe — the cell to resolve and why it is worth it.

    Mirrors the ``widest_gating_cell`` pointer :func:`engine.inspect` already
    surfaces (DESIGN §6.2), enriched with the economic ranking signal:

    - ``ci_halfwidth`` — the cell posterior's ``1 − alpha`` CI half-width (taken
      verbatim from the inspect output; see :func:`engine._ci_halfwidth`).  This
      is *what an eval shrinks*: a wide interval is why the gate can't yet admit
      the downgrade (DESIGN §5.4 / Layer 4).
    - ``unlock_value`` — the per-dispatch cost **savings** confirming this
      downgrade would unlock: ``cost(tier*) − cost(candidate)`` at the shape's
      representative token budget (DESIGN §2.3).  This is *what resolving the
      cell is worth*.
    - ``score`` — ``ci_halfwidth × unlock_value``; the ranking key (higher =
      resolve first).  Wide *and* valuable beats wide-but-cheap.
    """

    cell_key: str
    provider: str
    agent: str
    shape: str
    tier_id: str
    ci_halfwidth: float
    unlock_value: float
    score: float
    reason: str

    def to_dict(self) -> dict:
        """JSON-able view (the audit surface, mirroring the engine's ``reasons``)."""
        return {
            "cell_key": self.cell_key,
            "provider": self.provider,
            "agent": self.agent,
            "shape": self.shape,
            "tier_id": self.tier_id,
            "ci_halfwidth": round(self.ci_halfwidth, 6),
            "unlock_value": round(self.unlock_value, 8),
            "score": round(self.score, 8),
            "reason": self.reason,
        }


# --------------------------------------------------------------------------- #
# Scheduling (pure: a function of cfg + store)                                  #
# --------------------------------------------------------------------------- #


def _bead_title(req: EvalRequest) -> str:
    """The eval-request bead title, e.g. ``eval: <cell_key> (CI hw 0.14, unlocks $0.0113/dispatch)``."""
    return (
        f"eval: {req.cell_key} "
        f"(CI hw {req.ci_halfwidth:.2f}, unlocks ${req.unlock_value:.4f}/dispatch)"
    )


def schedule_evals(
    cfg: Any,
    store: Any,
    *,
    max_evals: int = 5,
    theta_eval: Optional[float] = None,
) -> list[EvalRequest]:
    """Rank the gating cells worth an eval and return the top ``max_evals``.

    Realises CC-TS Layer 4's auto-scheduling (DESIGN §1.3 Layer 4 / §5.4): for
    every configured ``(agent, shape)`` pair (``cfg.agent_shapes``), call
    :func:`engine.inspect` and read its ``widest_gating_cell`` — the cheaper tier
    the Layer-2 gate **rejected on uncertainty** (the engine has already applied
    the gate, the ``ci_hw > theta_eval`` filter, and the Critical / forced-
    baseline short-circuits, so we never re-derive any of that).  For each such
    cell we compute:

    - ``ci_halfwidth`` — the cell's ``1 − alpha`` CI half-width, taken straight
      from the inspect pointer (``engine._ci_halfwidth`` under the hood);
    - ``unlock_value`` — ``cost(tier*) − cost(candidate)`` at the shape's
      representative token budget (``cfg.budget_for`` → ``cfg.tier(...).cost``);
      the per-dispatch savings confirming this downgrade unlocks (DESIGN §2.3);
    - ``score = ci_halfwidth × unlock_value`` — wide *and* valuable ranks first.

    Cells whose half-width is at or below ``theta_eval`` are **not worth an eval**
    and are skipped.  ``theta_eval`` defaults to ``cfg.hp.theta_eval`` (the same
    threshold the engine's Layer-4 trigger uses); passing a *stricter* value lets
    a caller demand only the very widest cells.

    Pure function of ``(cfg, store)`` — no I/O, deterministic (DESIGN §1.4
    property 1).  The result is sorted by ``score`` descending, ties broken
    deterministically by ``cell_key`` so reruns are byte-stable.

    Parameters
    ----------
    cfg, store:
        The resolved advisor config and the materialised cell store (the engine
        state).  ``store`` is read-only here.
    max_evals:
        Cap on the number of returned requests (the eval budget for this run).
        ``<= 0`` returns an empty list (nothing scheduled).
    theta_eval:
        CI half-width floor below which a cell is not worth probing.  Defaults to
        ``cfg.hp.theta_eval``.

    Returns
    -------
    list[EvalRequest]
        Up to ``max_evals`` requests, highest ``score`` first.
    """
    if theta_eval is None:
        theta_eval = cfg.hp.theta_eval

    requests: list[EvalRequest] = []

    for agent, shapes in cfg.agent_shapes.items():
        for shape in shapes:
            try:
                info = _engine.inspect(agent, shape, cfg, store)
            except KeyError:
                # An (agent, shape) pair the config can't fully resolve (e.g. a
                # defaulted canonical shape absent from a custom taxonomy). One
                # bad pair must not abort the sweep — skip it (DESIGN §8
                # "the advisor must never block").
                continue
            widest = info.get("widest_gating_cell")
            if widest is None:
                # No cell is gating a downgrade on uncertainty for this pair
                # (admitted, Critical/forced, or all CIs already tight).
                continue

            ci_hw = float(widest["ci_halfwidth"])
            # The engine floors at hp.theta_eval; honour the caller's (possibly
            # stricter) threshold too. Skip cells not wide enough to be worth it.
            if ci_hw <= theta_eval:
                continue

            provider = info["cell"]["provider"]
            cand_tier = widest["tier_id"]
            base_tier = info["baseline_tier"]

            unlock_value = _unlock_value(cfg, shape, base_tier, cand_tier)
            score = ci_hw * unlock_value

            reason = (
                f"widest gating cell for {agent}/{shape}: {cand_tier} "
                f"(CI half-width {ci_hw:.2f} > theta_eval {theta_eval:.2f}); "
                f"confirming the downgrade from {base_tier} unlocks "
                f"${unlock_value:.4f}/dispatch — score {score:.4f} "
                f"(half-width x unlock-value)."
            )

            requests.append(
                EvalRequest(
                    cell_key=widest["cell_key"],
                    provider=provider,
                    agent=agent,
                    shape=shape,
                    tier_id=cand_tier,
                    ci_halfwidth=ci_hw,
                    unlock_value=unlock_value,
                    score=score,
                    reason=reason,
                )
            )

    # Highest value first; deterministic tie-break on the (unique) cell key so the
    # ordering — and thus the emitted bead set — is byte-stable across reruns.
    requests.sort(key=lambda r: (-r.score, r.cell_key))

    if max_evals <= 0:
        return []
    return requests[:max_evals]


def _unlock_value(cfg: Any, shape: str, base_tier: str, cand_tier: str) -> float:
    """Per-dispatch savings ``cost(tier*) − cost(candidate)`` at the shape budget.

    The value of *confirming* a gating downgrade (DESIGN §2.3 / §5.4): the cost
    differential between the known-good baseline ``tier*`` and the cheaper gating
    candidate, evaluated at the shape's representative token budget
    (``cfg.budget_for`` — §5.4).  Always ``>= 0`` since the candidate is cheaper
    than the baseline by construction (it is a *downgrade* the gate is weighing).
    """
    tok_in, tok_out = cfg.budget_for(shape)
    base_cost = cfg.tier(base_tier).cost(tok_in, tok_out)
    cand_cost = cfg.tier(cand_tier).cost(tok_in, tok_out)
    return base_cost - cand_cost


# --------------------------------------------------------------------------- #
# Emission (the side-effecting half — gated behind dry_run)                     #
# --------------------------------------------------------------------------- #


def build_create_command(req: EvalRequest, *, rig: Optional[str] = None) -> list[str]:
    """Build the ``gc bd create`` argv for one eval-request bead.

    The bead is a ``task`` carrying the :data:`EVAL_LABEL` so the operator /
    harvester can list scheduled evals (``gc bd ready --label model-advisor-eval``)
    and the ingest path can later attribute the eval verdict back to the cell
    (DESIGN §4.3).  ``--silent`` makes ``gc bd create`` print only the new bead id
    (for scripting / so :func:`emit_eval_beads` can capture it).  When ``rig`` is
    given, the bead is created in that rig's database (``--rig``) so it lands where
    the work will be dispatched (gc-work convention).

    Returned as an argv list (not a shell string) so :func:`emit_eval_beads` can
    run it without a shell; ``" ".join(...)`` yields the human/dry-run form.
    """
    argv: list[str] = [
        "gc",
        "bd",
        "create",
        _bead_title(req),
        "-t",
        EVAL_BEAD_TYPE,
        "-l",
        EVAL_LABEL,
    ]
    if rig:
        argv += ["--rig", rig]
    argv += ["--silent"]
    return argv


def emit_eval_beads(
    requests: list[EvalRequest],
    *,
    dry_run: bool = True,
    rig: Optional[str] = None,
) -> list[str]:
    """Turn ranked :class:`EvalRequest`s into eval-request beads.

    Realises the *dispatch* half of Layer 4 (DESIGN §5.4 / §7.3): each request
    becomes a ``gc bd create`` for an eval-request bead (a ``task`` labelled
    :data:`EVAL_LABEL`, titled ``eval: <cell_key> (CI hw X, unlocks $Y/dispatch)``).

    **Safe by default.** With ``dry_run=True`` (the default and the test path) this
    runs **nothing** — it returns the list of command *strings* that *would* be
    run, so the plan can be logged/inspected before it is armed.  Only with
    ``dry_run=False`` does it actually shell out (one ``gc bd create`` per request)
    and return the **created bead ids** (parsed from each ``--silent`` invocation's
    stdout).  A per-request failure does not abort the batch: its slot in the
    returned list is an ``"ERROR: <msg>"`` marker and the sweep continues.

    Parameters
    ----------
    requests:
        The ranked requests from :func:`schedule_evals`.
    dry_run:
        When True (default), return command strings and create nothing.
    rig:
        Optional rig to create the beads in (``gc bd create --rig <rig>``).

    Returns
    -------
    list[str]
        ``dry_run=True``  → the ``gc bd create …`` command strings (one per request).
        ``dry_run=False`` → the created bead ids (or ``"ERROR: …"`` markers).
    """
    out: list[str] = []
    for req in requests:
        argv = build_create_command(req, rig=rig)
        if dry_run:
            out.append(" ".join(argv))
            continue
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=True,
            )
            bead_id = proc.stdout.strip().splitlines()[-1].strip() if proc.stdout.strip() else ""
            out.append(bead_id or "ERROR: gc bd create returned no bead id")
        except subprocess.CalledProcessError as e:  # pragma: no cover - needs live gc
            msg = (e.stderr or e.stdout or str(e)).strip().splitlines()
            out.append(f"ERROR: gc bd create failed: {msg[-1] if msg else e}")
        except (OSError, ValueError) as e:  # pragma: no cover - needs live gc
            out.append(f"ERROR: {e}")
    return out
