"""model-advisor CLI — the operator-facing surfaces.

Three subcommands, mirroring the read-side pack's ``bin/op``/``bin/outline``
ergonomics (see ``packs/ast-lens/bin/``) and the surfaces specified in
``docs/DESIGN.md`` §6 + the integration verdict in
``docs/INTEGRATION-FEASIBILITY.md`` (A):

  advise  <agent> <shape> [--json]
      Call ``engine.recommend(agent, shape, cfg, store)`` and print the
      recommended tier, a human rationale, and the cost differential vs every
      roster tier.  ``--json`` emits the structured ``reasons`` audit object.

  inspect <agent> <shape> [--json]
      Call ``engine.inspect(agent, shape, cfg, store)`` and show each tier's
      posterior (mean + credible interval on the quality DROP vs baseline),
      then name the widest *gating* cell as the next eval to run.

  apply   <agent> [--shape S] [--city PATH] [--rig NAME] [--dry-run]
      Compute the recommendation, then SET that agent's default model in gc
      config by writing/updating the ``model = "<model>"`` field for the agent
      (per the integration verdict: ``[[agent]]`` / ``[agent_defaults].model``,
      the field gc carries into ``GC_AGENT_MODEL``).  Backs the file up first,
      is idempotent, supports ``--dry-run``, prints a clear before/after, and
      refuses cleanly on a no-op (recommended tier == current) or when the
      agent/config cannot be resolved.

This module owns *only* the CLI.  The engine, store, and config are built by a
sibling bead under the shared contract::

    engine.recommend(agent, shape, cfg, store) -> {tier_id, model, rationale,
                                                   cost_delta, reasons, ...}
    engine.inspect(agent, shape, cfg, store)   -> {...}
    store.CellStore(...)        # the posterior cell store
    config.load_config(path)    # loads advisor.toml
    config.default_config()     # built-in defaults (no advisor.toml present)

The CLI imports and drives those.  It is deliberately tolerant of the engine
not being present yet (cold dev / test bootstrap): the heavy imports are lazy
and tests may inject a stub via :data:`ENGINE` / :data:`build_state`.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

PROG = "advisor"

# Cell key = provider::agent::shape::tier_id  (shared contract).
CELL_KEY = "{provider}::{agent}::{shape}::{tier_id}"


# --------------------------------------------------------------------------- #
# Engine / config / store wiring (lazy + injectable)
# --------------------------------------------------------------------------- #
#
# ``ENGINE`` and ``build_state`` are module-level hooks so tests can drive the
# CLI without the sibling engine present.  In production they resolve to the
# real ``modeladvisor.engine`` / ``modeladvisor.config`` / ``modeladvisor.store``.

ENGINE: Any = None  # set by _load_engine(); tests may monkeypatch.


def _load_engine() -> Any:
    """Import and return the real engine module, caching it in :data:`ENGINE`.

    Kept lazy so ``import modeladvisor.cli`` never hard-fails if the sibling
    engine bead has not landed yet (the CLI can still be imported, its argparse
    introspected, and ``apply``'s config editor unit-tested in isolation).
    """
    global ENGINE
    if ENGINE is not None:
        return ENGINE
    from modeladvisor import engine as _engine  # local import: see docstring

    ENGINE = _engine
    return ENGINE


@dataclass
class State:
    """Everything ``recommend``/``inspect`` need, resolved from disk/config."""

    cfg: Any
    store: Any
    provider: str


def build_state(
    *,
    advisor_toml: Optional[str] = None,
    telemetry_dir: Optional[str] = None,
    provider: Optional[str] = None,
) -> State:
    """Resolve config + cell store for a CLI invocation.

    Config (DESIGN §8 "config files the engine reads"): an explicit
    ``advisor.toml`` (``--config`` or ``$ADVISOR_TOML``) else the pack/city
    default config.

    Cell store (DESIGN §5.5 "the JSONL is the source of truth; the cache is
    rebuildable"): from the telemetry dir (``$ADVISOR_TELEMETRY_DIR`` or
    ``./.beads/telemetry``) we *rebuild* from ``invocations.jsonl`` when it is
    present (truth), else *load* the ``advisor-cells.json`` cache when present,
    else fall back to a conservative ``cold_start`` store (DESIGN §3.2 — the
    advisor must never block; worst case it recommends the baseline tier).

    Tests monkeypatch this wholesale to inject a fake ``State``; production uses
    the sibling ``config``/``store`` modules.
    """
    from modeladvisor import config as _config
    from modeladvisor import store as _store

    advisor_toml = advisor_toml or os.environ.get("ADVISOR_TOML")
    if advisor_toml and os.path.exists(advisor_toml):
        cfg = _config.load_config(advisor_toml)
    else:
        cfg = _config.default_config()

    telemetry_dir = (
        telemetry_dir
        or os.environ.get("ADVISOR_TELEMETRY_DIR")
        or os.path.join(os.getcwd(), ".beads", "telemetry")
    )
    jsonl = os.path.join(telemetry_dir, "invocations.jsonl")
    cache = os.path.join(telemetry_dir, "advisor-cells.json")
    if os.path.exists(jsonl):
        store = _store.CellStore.rebuild(cfg, jsonl)
    elif os.path.exists(cache):
        store = _store.CellStore.load(cfg, cache)
    else:
        store = _store.CellStore.cold_start(cfg)

    prov = (
        provider
        or getattr(cfg, "default_provider", None)
        or "claude"
    )
    return State(cfg=cfg, store=store, provider=prov)


# --------------------------------------------------------------------------- #
# Small output helpers
# --------------------------------------------------------------------------- #

def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` from a dict-or-object recommendation/inspect result.

    The engine returns plain dicts per the contract, but being lenient about
    attribute-style access keeps the CLI robust to a dataclass result too.
    """
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _fmt_money(x: Optional[float]) -> str:
    """Format a dollar cost differential with a sign, e.g. ``-$0.0114``."""
    if x is None:
        return "n/a"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    sign = "-" if v < 0 else "+"
    return f"{sign}${abs(v):.4f}"


def _fmt_ci(ci: Any) -> str:
    """Format a credible interval as ``[lo, hi]`` (+ ``*`` if it exceeds tol).

    Accepts either a 2-tuple/list ``(lo, hi)`` or the engine's richer dict
    ``{lo, hi, mean, q_tol, exceeds_tol}`` (DESIGN §6.2 — the credible interval
    on the quality *drop* vs baseline).  A trailing ``*`` flags an interval that
    breaches the tolerance (i.e. why a cheaper tier can't be admitted).
    """
    if not ci:
        return "[n/a]"
    if isinstance(ci, Mapping):
        lo = ci.get("lo")
        hi = ci.get("hi")
        if lo is None or hi is None:
            return str(ci)
        flag = "*" if ci.get("exceeds_tol") else ""
        return f"[{float(lo):.3f}, {float(hi):.3f}]{flag}"
    try:
        lo, hi = ci
        return f"[{float(lo):.3f}, {float(hi):.3f}]"
    except (TypeError, ValueError):
        return str(ci)


def _num(x: Any, fmt: str = "{:.3f}") -> str:
    try:
        return fmt.format(float(x))
    except (TypeError, ValueError):
        return "n/a" if x is None else str(x)


# --------------------------------------------------------------------------- #
# advise
# --------------------------------------------------------------------------- #

def cmd_advise(args: argparse.Namespace, out: io.TextIOBase) -> int:
    engine = _load_engine()
    state = _resolve_state(args)

    cfg = state.cfg
    # --thompson: run the genuine seeded Thompson-Sampling mode (DESIGN §7.3) for
    # this invocation by overriding the config's mode knob.
    if getattr(args, "thompson", False):
        cfg = cfg.with_hyperparams(mode="thompson")

    # --cascade-bead: resolve the bead's downstream DAG (gc bd dep tree --json) into
    # an effective blast radius and pass it as `cascade=` so the L3 cascade term
    # scales with the bead's true reach (DESIGN §1.3 L3 / §7.3).
    cascade = None
    cascade_bead = getattr(args, "cascade_bead", None)
    if cascade_bead:
        cascade = _resolve_cascade(cascade_bead, out)

    rec = engine.recommend(
        args.agent,
        args.shape,
        cfg,
        state.store,
        provider=state.provider,
        seed=getattr(args, "seed", None),
        cascade=cascade,
    )

    if args.json:
        # The audit surface: emit the structured ``reasons`` verbatim, with the
        # top-line decision fields alongside for a self-contained record.
        payload = {
            "agent": args.agent,
            "shape": args.shape,
            "provider": _get(rec, "provider", state.provider),
            "tier_id": _get(rec, "tier_id"),
            "model": _get(rec, "model"),
            "cost_delta": _get(rec, "cost_delta"),
            "reasons": _get(rec, "reasons", {}),
        }
        json.dump(payload, out, indent=2, default=str)
        out.write("\n")
        return 0

    tier = _get(rec, "tier_id", "?")
    model = _get(rec, "model")
    rationale = _get(rec, "rationale", "(no rationale provided)")

    out.write(f"advise {args.agent} {args.shape}\n")
    head = f"  recommend: {tier}"
    if model:
        head += f"  ({model})"
    out.write(head + "\n")
    out.write(f"  rationale: {rationale}\n")

    # Cost differential vs each roster tier (and vs baseline).  Prefer an
    # explicit per-candidate breakdown from ``reasons``; fall back to the
    # scalar ``cost_delta`` vs baseline.
    reasons = _get(rec, "reasons", {}) or {}
    cands = _get(reasons, "candidates", None)
    if cands:
        out.write("  cost differential vs each tier:\n")
        for c in cands:
            ctier = _get(c, "tier_id", "?")
            cdiff = _get(c, "cost_diff", _get(c, "cost_delta"))
            marker = " <- recommended" if ctier == tier else ""
            extra = []
            if _get(c, "q_lo") is not None:
                extra.append(f"q_lo={_num(_get(c, 'q_lo'))}")
            if _get(c, "exp_loss") is not None:
                extra.append(f"E[L]={_fmt_money(_get(c, 'exp_loss'))}")
            suffix = ("  " + " ".join(extra)) if extra else ""
            out.write(
                f"    {ctier:<12} {_fmt_money(cdiff)}{suffix}{marker}\n"
            )
    else:
        out.write(
            f"  cost differential vs baseline: {_fmt_money(_get(rec, 'cost_delta'))}\n"
        )

    if _get(reasons, "eval_flag"):
        out.write("  note: this cell wants an eval (posterior CI is wide)\n")
    return 0


# --------------------------------------------------------------------------- #
# inspect
# --------------------------------------------------------------------------- #

def cmd_inspect(args: argparse.Namespace, out: io.TextIOBase) -> int:
    engine = _load_engine()
    state = _resolve_state(args)

    info = engine.inspect(
        args.agent, args.shape, state.cfg, state.store, provider=state.provider
    )

    if args.json:
        json.dump(_as_jsonable(info), out, indent=2, default=str)
        out.write("\n")
        return 0

    out.write(f"inspect {args.agent} {args.shape}\n")
    baseline = _get(info, "baseline_tier")
    if baseline:
        out.write(f"  baseline tier*: {baseline}\n")

    tiers = _get(info, "tiers", []) or []
    if tiers:
        out.write(
            "  {:<12} {:>6} {:>6} {:>5} {:<22} {}\n".format(
                "tier", "mean", "q_lo", "n", "quality-drop 95% CI", "gate"
            )
        )
        for t in tiers:
            tid = _get(t, "tier_id", "?")
            mean = _num(_get(t, "mean"))
            q_lo = _num(_get(t, "q_lo"))
            n = _get(t, "n", 0)
            drop_ci = _fmt_ci(_get(t, "quality_drop_ci", _get(t, "drop_ci")))
            out.write(
                "  {:<12} {:>6} {:>6} {:>5} {:<22} {}\n".format(
                    tid, mean, q_lo, n, drop_ci, _gate_label(t, tid, baseline)
                )
            )

    widest = _get(info, "widest_gating_cell") or _get(info, "widest_cell")
    if widest:
        cell = _get(widest, "cell_key", _get(widest, "tier_id", "?"))
        hw = _get(widest, "ci_halfwidth",
                  _get(widest, "ci_half_width", _get(widest, "half_width")))
        out.write(
            f"  next eval (widest gating cell): {cell}"
            + (f" (CI half-width {_num(hw)})" if hw is not None else "")
            + "\n"
        )
        rationale = _get(widest, "rationale")
        if rationale:
            out.write(f"    {rationale}\n")
    else:
        out.write("  next eval: none — no cell is gating a downgrade\n")
    return 0


def _gate_label(tier: Any, tid: str, baseline: Optional[str]) -> str:
    """Render a tier's gate decision for the inspect table.

    The real engine marks the baseline with ``role == 'baseline'`` and each
    candidate downgrade with ``admitted`` (bool).  ``admit`` is accepted as a
    fallback alias so a simpler engine/stub still renders correctly.
    """
    role = _get(tier, "role")
    if role == "baseline" or tid == baseline:
        return "baseline"
    admit = _get(tier, "admitted", _get(tier, "admit"))
    if admit is True:
        return "admit"
    if admit is False:
        return "reject"
    return "-"


def _as_jsonable(info: Any) -> Any:
    """Best-effort coerce an inspect result to something ``json.dump`` accepts."""
    if isinstance(info, Mapping):
        return info
    # dataclass / object → its __dict__ if present
    d = getattr(info, "__dict__", None)
    return d if d is not None else info


# --------------------------------------------------------------------------- #
# apply  — the v1 "actually choose the model" action (per AGENT)
# --------------------------------------------------------------------------- #

def cmd_apply(args: argparse.Namespace, out: io.TextIOBase) -> int:
    engine = _load_engine()
    state = _resolve_state(args)

    shape = args.shape
    if not shape:
        shape = _default_shape_for(state.cfg, args.agent)
    if not shape:
        out.write(
            f"apply: cannot resolve a shape for agent '{args.agent}'. "
            "Pass --shape <lookup|implement|judge|review|patrol>.\n"
        )
        return 2

    rec = engine.recommend(
        args.agent, shape, state.cfg, state.store, provider=state.provider
    )
    new_model = _get(rec, "model")
    new_tier = _get(rec, "tier_id")
    if not new_model:
        out.write(
            "apply: the engine did not return a concrete model for "
            f"{args.agent}/{shape}; nothing to apply.\n"
        )
        return 2

    # The full cross-provider routing target for the chosen tier: provider +
    # model + run_target.  Applying a tier must set all three so a Codex tier
    # actually runs on Codex (not just rename the model).  Resolve them from the
    # roster (the engine returns a tier_id; the config owns the routing fields).
    new_provider = _get(rec, "provider", state.provider)
    new_run_target: Optional[str] = None
    dispatch: Optional[dict] = None
    if new_tier and getattr(state.cfg, "has_tier", None) and state.cfg.has_tier(new_tier):
        tier = state.cfg.tier(new_tier)
        new_provider = tier.provider or new_provider
        new_run_target = tier.run_target or None
        dispatch = dispatch_metadata(state.cfg, new_tier)

    # Resolve the gc config file + the scope (flat agent.toml / [[agent]] /
    # [agent_defaults]) that owns this agent's routing fields.
    try:
        target = resolve_agent_config(
            args.agent, city=args.city, rig=args.rig
        )
    except ConfigResolveError as e:
        if getattr(args, "json", False):
            json.dump({"agent": args.agent, "error": str(e)}, out, default=str)
            out.write("\n")
        else:
            out.write(f"apply: {e}\n")
        return 2

    current = read_model_field(target)
    cur_provider = read_field(target, "provider")
    cur_run_target = read_field(target, "run_target")

    # Refuse the no-op: the recommended model is already in effect.  (We key the
    # no-op on the model for back-compat with v1; provider/run_target are written
    # additively when the model itself changes.)
    is_noop = current is not None and current == new_model

    if getattr(args, "json", False):
        payload = {
            "agent": args.agent,
            "shape": shape,
            "config": target.path,
            "scope": target.describe(),
            "recommended_tier": new_tier,
            "provider": new_provider,
            "model": new_model,
            "run_target": new_run_target,
            "current": {
                "provider": cur_provider,
                "model": current,
                "run_target": cur_run_target,
            },
            "dispatch_metadata": dispatch,
            "dry_run": bool(args.dry_run),
            "noop": is_noop,
            "applied": False,
        }
        if is_noop:
            payload["reason"] = "recommended model equals the current model"
            json.dump(payload, out, indent=2, default=str)
            out.write("\n")
            return 3
        if not args.dry_run:
            backup = backup_file(target.path)
            set_tier_fields(
                target,
                provider=new_provider,
                model=new_model,
                run_target=new_run_target,
            )
            payload["applied"] = True
            payload["backup"] = backup
        json.dump(payload, out, indent=2, default=str)
        out.write("\n")
        return 0

    out.write(f"apply {args.agent} (shape={shape})\n")
    out.write(f"  config: {target.path}\n")
    out.write(f"  scope:  {target.describe()}\n")
    out.write(
        f"  recommended tier: {new_tier}  provider: {new_provider}  "
        f"model: {new_model}"
        + (f"  run_target: {new_run_target}" if new_run_target else "")
        + "\n"
    )
    out.write(f"  current model:    {current if current is not None else '(unset)'}\n")

    if is_noop:
        out.write(
            "  refused: recommended model equals the current model "
            f"('{new_model}') — no change to apply.\n"
        )
        return 3

    if args.dry_run:
        out.write(
            f"  DRY-RUN: would set provider = \"{new_provider}\", "
            f"model = \"{new_model}\""
            + (f", run_target = \"{new_run_target}\"" if new_run_target else "")
            + f" (model was {current if current is not None else 'unset'}); "
            "no file written.\n"
        )
        return 0

    backup = backup_file(target.path)
    set_tier_fields(
        target,
        provider=new_provider,
        model=new_model,
        run_target=new_run_target,
    )

    out.write(f"  backup: {backup}\n")
    out.write(
        f"  applied: model {current if current is not None else 'unset'} -> \"{new_model}\""
        f"  (provider=\"{new_provider}\""
        + (f", run_target=\"{new_run_target}\"" if new_run_target else "")
        + ")\n"
    )
    out.write(
        "  note: agent picks up the new provider/model/run_target on next "
        "session (gc routes the dispatch on the gc.provider/gc.model/"
        "gc.run_target triple).\n"
    )
    return 0


# --------------------------------------------------------------------------- #
# auto-apply  — sweep EVERY agent; set each to its conservative per-agent tier
# --------------------------------------------------------------------------- #

def cmd_auto_apply(args: argparse.Namespace, out: io.TextIOBase) -> int:
    """Drive :func:`modeladvisor.autoapply.auto_apply` over the whole roster.

    Default-safe: runs in **dry-run** unless ``--apply`` is given.  Emits a loud
    per-agent summary (and the full structured report under ``--json``).  The
    per-agent policy + apply gate live in :mod:`modeladvisor.autoapply`; this is
    only the operator surface.
    """
    from modeladvisor import autoapply as _autoapply

    engine = _load_engine()
    state = _resolve_state(args)

    # Default to dry-run; only --apply opts into writing.  (--dry-run is accepted
    # explicitly and is the default, so passing it is a harmless no-op.)
    dry_run = not getattr(args, "apply", False)

    scope = "town"
    rig = getattr(args, "rig", None)
    if rig:
        scope = f"rig:{rig}"

    report = _autoapply.auto_apply(
        state.cfg,
        state.store,
        scope=scope,
        dry_run=dry_run,
        provider=state.provider,
        city=getattr(args, "city", None),
        rig=rig,
        engine=engine,
    )

    if getattr(args, "json", False):
        json.dump(report.to_dict(), out, indent=2, default=str)
        out.write("\n")
        return _auto_apply_rc(report)

    mode = "DRY-RUN (no files written)" if dry_run else "APPLY"
    out.write(f"auto-apply [{report.scope}]  mode: {mode}\n")
    out.write(f"  provider: {report.provider}\n")
    for d in report.decisions:
        _write_auto_decision(out, d, dry_run)

    s = report.summary()
    out.write(
        "  ----------------------------------------------------------------\n"
    )
    out.write(
        "  SUMMARY: {agents} agents | "
        "{applied} applied | {dryrun} planned | {noop} no-op | "
        "{skipped} skipped | {blocked} blocked | {error} error\n".format(
            agents=s["agents"],
            applied=s[_autoapply.STATUS_APPLIED],
            dryrun=s[_autoapply.STATUS_DRYRUN],
            noop=s[_autoapply.STATUS_NOOP],
            skipped=s[_autoapply.STATUS_SKIPPED],
            blocked=s[_autoapply.STATUS_BLOCKED],
            error=s[_autoapply.STATUS_ERROR],
        )
    )
    if dry_run and s[_autoapply.STATUS_DRYRUN]:
        out.write(
            "  NOTE: this was a dry run — re-run with --apply to write the "
            f"{s[_autoapply.STATUS_DRYRUN]} planned change(s).\n"
        )
    return _auto_apply_rc(report)


def _write_auto_decision(out: io.TextIOBase, d: Any, dry_run: bool) -> None:
    """Render one per-agent decision line (+ detail) for the text report."""
    tag = {
        "applied": "APPLIED ",
        "dry-run": "WOULD   ",
        "noop": "noop    ",
        "skipped": "skipped ",
        "blocked": "BLOCKED ",
        "error": "ERROR   ",
    }.get(d.status, d.status)
    cur = d.current_model if d.current_model is not None else "(unset)"
    chosen = d.chosen_model or "?"
    out.write(f"  [{tag}] {d.agent}\n")
    out.write(
        f"      tier: {d.chosen_tier or '?'}"
        + (f" (binding shape: {d.binding_shape})" if d.binding_shape else "")
        + f"   current: {cur} -> chosen: {chosen}\n"
    )
    if d.per_shape:
        per = ", ".join(f"{k}={v}" for k, v in d.per_shape.items())
        out.write(f"      per-shape: {per}\n")
    if d.reason:
        out.write(f"      why: {d.reason}\n")
    if d.backup_path:
        out.write(f"      backup: {d.backup_path}\n")


def _auto_apply_rc(report: Any) -> int:
    """Exit code: 1 if any per-agent error occurred, else 0.

    A dry run with planned changes still returns 0 (it succeeded at planning);
    operators / orders gate on the JSON/summary, not a non-zero rc, so a healthy
    scheduled run is exit 0.
    """
    from modeladvisor import autoapply as _autoapply

    return 1 if report.count(_autoapply.STATUS_ERROR) else 0


def _default_shape_for(cfg: Any, agent: str) -> Optional[str]:
    """Resolve an agent's canonical default shape from config, if any.

    DESIGN §2.2 gives each agent a canonical shape set; the engine/config own
    the real mapping.  We probe a couple of plausible accessors and otherwise
    return ``None`` (caller then requires ``--shape``).
    """
    # The real config exposes ``canonical_shapes_for(agent) -> tuple[str, ...]``
    # (DESIGN §2.2); the first canonical shape is the agent's default.  Probe a
    # few plausible accessors so the CLI tolerates config-shape drift.
    for attr in ("default_shape_for", "default_shape", "canonical_shapes_for"):
        fn = getattr(cfg, attr, None)
        if callable(fn):
            try:
                s = fn(agent)
            except Exception:
                continue
            if isinstance(s, str) and s:
                return s
            if isinstance(s, (list, tuple)) and s:
                return s[0]
    shapes = getattr(cfg, "agent_shapes", None) or getattr(cfg, "canonical_shapes", None)
    if isinstance(shapes, Mapping):
        v = shapes.get(agent)
        if isinstance(v, str):
            return v
        if isinstance(v, (list, tuple)) and v:
            return v[0]
    return None


# --------------------------------------------------------------------------- #
# eval-schedule  — Layer-4 auto-eval: rank gating cells + emit eval beads
# --------------------------------------------------------------------------- #

def cmd_eval_schedule(args: argparse.Namespace, out: io.TextIOBase) -> int:
    """Rank the cells gating a downgrade on uncertainty and emit eval-request beads.

    Drives :func:`modeladvisor.evalsched.schedule_evals` (pure planning) then
    :func:`~modeladvisor.evalsched.emit_eval_beads` (gated emission). Dry-run by
    default; ``--apply`` actually creates the beads (DESIGN §1.3 Layer 4 / §5.4).
    """
    from modeladvisor import evalsched as _evalsched

    state = _resolve_state(args)
    max_evals = getattr(args, "max", None)
    if max_evals is None:
        max_evals = 5
    reqs = _evalsched.schedule_evals(state.cfg, state.store, max_evals=max_evals)

    apply = getattr(args, "apply", False)
    rig = getattr(args, "rig", None)
    emitted = _evalsched.emit_eval_beads(reqs, dry_run=not apply, rig=rig)

    if getattr(args, "json", False):
        json.dump(
            {
                "mode": "apply" if apply else "dry-run",
                "max_evals": max_evals,
                "requests": [r.to_dict() for r in reqs],
                "emitted": emitted,
            },
            out,
            indent=2,
            default=str,
        )
        out.write("\n")
        return 0

    mode = "APPLY (creating eval beads)" if apply else "DRY-RUN (no beads created)"
    out.write(f"eval-schedule  mode: {mode}\n")
    if not reqs:
        out.write("  no cell is gating a downgrade on uncertainty — nothing to schedule.\n")
        return 0
    out.write(f"  {len(reqs)} eval probe(s) ranked by CI half-width x unlock-value:\n")
    for r, e in zip(reqs, emitted):
        out.write(
            f"    {r.cell_key}  hw={r.ci_halfwidth:.3f} "
            f"unlock={_fmt_money(r.unlock_value)} score={r.score:.4f}\n"
        )
        label = "would run" if not apply else "created"
        out.write(f"      {label}: {e}\n")
    return 0


# --------------------------------------------------------------------------- #
# federate  — export/import per-cell observed aggregates (privacy-safe)
# --------------------------------------------------------------------------- #

def cmd_federate(args: argparse.Namespace, out: io.TextIOBase) -> int:
    """Export this rig's per-cell aggregates, or import + merge peers' (DESIGN §7.3).

    ``federate export [--out FILE]`` writes the privacy-safe observed aggregates
    (only ``a_obs``/``b_obs``/``n`` per cell — no raw telemetry). ``federate import
    PEER... [--trust X] [--max-peer-mass M]`` folds peer aggregates into a fresh
    store as trust-scaled prior mass and reports the cells moved.
    """
    from modeladvisor import federation as _federation

    state = _resolve_state(args)
    action = getattr(args, "action", None)

    if action == "export":
        doc = _federation.export_aggregates(state.store)
        text = json.dumps(doc, indent=2, sort_keys=True)
        out_path = getattr(args, "out", None)
        if out_path:
            os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            out.write(f"federate export: wrote {len(doc['cells'])} cell(s) -> {out_path}\n")
        else:
            out.write(text + "\n")
        return 0

    if action == "import":
        peers = list(getattr(args, "peers", []) or [])
        if not peers:
            out.write("federate import: no peer export paths given.\n")
            return 2
        # Config-supplied defaults; CLI flags override when present.
        trust = getattr(args, "trust", None)
        if trust is None:
            trust = getattr(state.cfg, "federation_trust", 0.3)
        mpm = getattr(args, "max_peer_mass", None)
        if mpm is None:
            mpm = getattr(state.cfg, "federation_max_peer_mass", None)
        try:
            merged = _federation.merge_peers(
                state.store, peers, trust=trust, max_peer_mass=mpm
            )
        except _federation.FederationError as e:
            out.write(f"federate import: {e}\n")
            return 2

        if getattr(args, "json", False):
            json.dump(
                {
                    "peers": peers,
                    "trust": trust,
                    "max_peer_mass": mpm,
                    "merged_observed_cells": len(merged.observed_cells()),
                },
                out,
                indent=2,
                default=str,
            )
            out.write("\n")
            return 0

        out.write(
            f"federate import: merged {len(peers)} peer(s) at trust={trust} "
            f"-> {len(merged.observed_cells())} observed cell(s).\n"
        )
        return 0

    out.write("federate: expected a subcommand 'export' or 'import'.\n")
    return 2


# --------------------------------------------------------------------------- #
# drift  — report Page-Hinkley change-points per cell from the telemetry stream
# --------------------------------------------------------------------------- #

def cmd_drift(args: argparse.Namespace, out: io.TextIOBase) -> int:
    """Report detected upstream-drift change-points per cell (DESIGN §7.3).

    Reads the ordered ``kind="quality"`` records from the telemetry
    ``invocations.jsonl``, groups them per cell, and runs
    :func:`modeladvisor.changepoint.detect_changepoints` on each cell's time-ordered
    ``q`` stream. Optional ``--agent``/``--shape``/``--provider`` filters narrow the
    sweep. This is the read-only operator view of the adaptive safety hatch that
    supersedes the static ``force_baseline`` (DESIGN §7.4).
    """
    from modeladvisor import changepoint as _changepoint
    from modeladvisor.store import parse_cell_key, read_jsonl

    state = _resolve_state(args)
    telemetry_dir = (
        getattr(args, "telemetry_dir", None)
        or os.environ.get("ADVISOR_TELEMETRY_DIR")
        or os.path.join(os.getcwd(), ".beads", "telemetry")
    )
    jsonl = os.path.join(telemetry_dir, "invocations.jsonl")

    want_agent = getattr(args, "agent", None)
    want_shape = getattr(args, "shape", None)
    want_provider = getattr(args, "provider", None) or state.provider

    # Group ordered q-streams per cell from the quality records.
    streams: dict[str, list[float]] = {}
    for rec in read_jsonl(jsonl):
        if rec.get("kind") != "quality":
            continue
        key = rec.get("cell_key")
        q = rec.get("q")
        if not key or q is None:
            continue
        try:
            prov, agent, shape, _tier = parse_cell_key(str(key))
        except ValueError:
            continue
        if want_agent and agent != want_agent:
            continue
        if want_shape and shape != want_shape:
            continue
        if want_provider and prov != want_provider:
            continue
        try:
            streams.setdefault(str(key), []).append(float(q))
        except (TypeError, ValueError):
            continue

    drifted: list[dict] = []
    for key in sorted(streams):
        obs = streams[key]
        cps = _changepoint.detect_changepoints(obs)
        if not cps:
            continue
        c_star = max(cps)
        pre = obs[:c_star] or obs[:1]
        post = obs[c_star:] or obs[-1:]
        drifted.append(
            {
                "cell_key": key,
                "n": len(obs),
                "changepoints": cps,
                "pre_mean": round(sum(pre) / len(pre), 4),
                "post_mean": round(sum(post) / len(post), 4),
            }
        )

    if getattr(args, "json", False):
        json.dump({"cells_scanned": len(streams), "drifted": drifted}, out, indent=2)
        out.write("\n")
        return 0

    out.write(f"drift: scanned {len(streams)} cell(s) with telemetry\n")
    if not drifted:
        out.write("  no change-points detected — all scanned cells look stationary.\n")
        return 0
    for d in drifted:
        out.write(
            f"  {d['cell_key']}  n={d['n']}  shifts@{d['changepoints']}  "
            f"mean {d['pre_mean']} -> {d['post_mean']}\n"
        )
    return 0


# --------------------------------------------------------------------------- #
# gc config editing  (the heart of `apply`)
# --------------------------------------------------------------------------- #
#
# gc accepts a ``model`` field in three shapes (INTEGRATION verdict (A)):
#
#   1. a *flat* per-agent ``agent.toml`` (gastown style: the file IS the agent;
#      ``model`` is a top-level key);
#   2. an ``[[agent]]`` array-of-tables entry inside a pack/city toml, matched
#      by ``name = "<agent>"``;
#   3. an ``[agent_defaults]`` table (the default model for all agents).
#
# We perform a *surgical, format-preserving text edit* — insert or replace a
# single ``model = "..."`` line in the correct scope — rather than round-trip
# the TOML (which would drop comments/formatting and needs a writer lib the
# venv doesn't ship).  This is the same approach gc's own ``doImportAdd`` takes.

_MODEL_LINE = re.compile(r'^(?P<indent>[ \t]*)model[ \t]*=.*$', re.MULTILINE)

# The cross-provider routing target gc honors per dispatch is the metadata triple
# gc.provider / gc.model / gc.run_target (the core ``mol-review-quorum`` formula
# proves gc routes on it).  Applying a tier must set all three in the agent's
# config scope so a Codex tier actually runs on Codex (not just the model name).
_TIER_FIELDS = ("provider", "model", "run_target")


def _field_line_re(field: str) -> "re.Pattern[str]":
    """A MULTILINE regex matching an existing ``<field> = ...`` line in scope."""
    return re.compile(
        r'^(?P<indent>[ \t]*)' + re.escape(field) + r'[ \t]*=.*$', re.MULTILINE
    )


class ConfigResolveError(Exception):
    """Raised when the agent's config file/scope can't be resolved."""


@dataclass
class ConfigTarget:
    """Where (file + scope) an agent's ``model`` field lives / should live."""

    path: str
    kind: str  # "flat" | "agent_block" | "agent_defaults"
    # For agent_block/agent_defaults we keep the [byte] span of the table body
    # so edits stay inside the right table.
    span: Optional[tuple] = None  # (start, end) char offsets into the file text
    agent: Optional[str] = None

    def describe(self) -> str:
        if self.kind == "flat":
            return f"flat agent.toml (top-level model for '{self.agent}')"
        if self.kind == "agent_block":
            return f"[[agent]] name = \"{self.agent}\""
        if self.kind == "agent_defaults":
            return "[agent_defaults]"
        return self.kind


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def resolve_agent_config(
    agent: str,
    *,
    city: Optional[str] = None,
    rig: Optional[str] = None,
) -> ConfigTarget:
    """Locate the gc config file + scope that owns ``agent``'s model field.

    The non-deprecated home for an agent's routing fields (``provider`` /
    ``model`` / ``run_target``) is the **per-agent flat
    ``agents/<agent>/agent.toml``** (gc warns that ``[workspace] provider`` is
    deprecated → "set provider per agent in ``agents/<name>/agent.toml``", and
    likewise resolves ``model`` per agent there). So resolution prefers — and,
    when absent, **creates** — that flat file rather than writing into
    ``city.toml``'s ``[workspace]`` / ``[[agent]]`` blocks.

    Resolution (first hit wins):

    1. ``$ADVISOR_AGENT_TOML`` — explicit file override (used by tests). If it
       contains an ``[[agent]]`` block named ``agent`` we target that; if it has
       an ``[agent_defaults]`` table we target that; otherwise it is treated as
       a flat per-agent ``agent.toml``. (Honored verbatim — the caller named the
       exact file, so we never redirect it to a created path.)
    2. An **existing** flat ``<city>/.gc/system/packs/<rig?>/agents/<agent>/
       agent.toml`` (the gastown layout). ``city`` defaults to ``$GC_CITY`` /
       cwd; ``rig`` narrows the pack search.
    3. If none exists, **create** a flat ``agents/<agent>/agent.toml`` at the
       canonical pack root (the ``--rig`` pack if given, else the first
       agent-bearing pack under ``.gc/system/packs``) and target it. This is the
       non-deprecated per-agent home, materialized to match gc's convention.
    4. Only if there is no ``.gc/system/packs`` at all do we fall back to a
       ``[[agent]] name = "<agent>"`` block / ``[agent_defaults]`` table inside
       ``<city>/city.toml``.

    Raises :class:`ConfigResolveError` if nothing resolves.
    """
    override = os.environ.get("ADVISOR_AGENT_TOML")
    if override:
        if not os.path.exists(override):
            raise ConfigResolveError(
                f"ADVISOR_AGENT_TOML points at a missing file: {override}"
            )
        return _classify_config_file(override, agent)

    city = city or os.environ.get("GC_CITY") or os.getcwd()

    # (2) EXISTING flat gastown agent.toml — search common pack roots.
    pack_roots = []
    sys_packs = os.path.join(city, ".gc", "system", "packs")
    if rig:
        pack_roots.append(os.path.join(sys_packs, rig))
    if os.path.isdir(sys_packs):
        for entry in sorted(os.listdir(sys_packs)):
            p = os.path.join(sys_packs, entry)
            if os.path.isdir(p) and p not in pack_roots:
                pack_roots.append(p)
    for root in pack_roots:
        cand = os.path.join(root, "agents", agent, "agent.toml")
        if os.path.exists(cand):
            return ConfigTarget(path=cand, kind="flat", agent=agent)

    # (3) No existing per-agent file: CREATE the canonical flat
    #     agents/<agent>/agent.toml (the non-deprecated home gc reads) rather
    #     than writing the routing fields into city.toml's [workspace]/[[agent]]
    #     (deprecated). Pick the creation pack root: the --rig pack if given,
    #     else the first pack that already carries an agents/ dir (a real
    #     agent-bearing pack like gastown — not bd/dolt/core), else the first
    #     pack root. Materialize an empty file (+ parent dirs) so the downstream
    #     read/backup/write path works unchanged (current model reads as unset).
    create_root = _pick_creation_pack_root(pack_roots, rig, sys_packs)
    if create_root is not None:
        new_path = os.path.join(create_root, "agents", agent, "agent.toml")
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        if not os.path.exists(new_path):
            with open(new_path, "w", encoding="utf-8") as fh:
                fh.write("")  # empty flat agent.toml; set_field inserts the keys
        return ConfigTarget(path=new_path, kind="flat", agent=agent)

    # (4) Last resort (no .gc/system/packs at all): city.toml [[agent]] /
    #     [agent_defaults]. Only reached on a city without a packs tree.
    city_toml = os.path.join(city, "city.toml")
    if os.path.exists(city_toml):
        try:
            return _classify_config_file(city_toml, agent, require_agent=True)
        except ConfigResolveError:
            pass

    raise ConfigResolveError(
        f"could not resolve a config file for agent '{agent}'. "
        f"Looked for a flat agent.toml under {sys_packs} and an [[agent]]/"
        f"[agent_defaults] block in {city_toml}. "
        "Set ADVISOR_AGENT_TOML or pass --city/--rig."
    )


def _pick_creation_pack_root(
    pack_roots: Sequence[str], rig: Optional[str], sys_packs: str
) -> Optional[str]:
    """Choose the pack root under which to create a new ``agents/<agent>/agent.toml``.

    Preference order:
      1. The ``--rig`` pack root, when ``rig`` was given and it exists on disk
         (the operator scoped the apply to that rig).
      2. The first pack root that already carries an ``agents/`` directory — i.e.
         a real agent-bearing pack (``gastown``), not an infra pack
         (``bd`` / ``dolt`` / ``core``) that holds no agents.
      3. The first pack root, if any.

    Returns ``None`` only when there are no pack roots at all (no
    ``.gc/system/packs`` tree), which routes the caller to the city.toml fallback.
    """
    if rig:
        rig_root = os.path.join(sys_packs, rig)
        if os.path.isdir(rig_root):
            return rig_root
    for root in pack_roots:
        if os.path.isdir(os.path.join(root, "agents")):
            return root
    return pack_roots[0] if pack_roots else None


def _classify_config_file(
    path: str, agent: str, require_agent: bool = False
) -> ConfigTarget:
    """Decide how ``agent``'s model is represented inside ``path``.

    Looks for an ``[[agent]]`` table whose ``name`` matches ``agent`` first,
    then an ``[agent_defaults]`` table, then falls back to treating the whole
    file as a flat agent.toml — but *only* when the file is not structurally a
    multi-agent config.  A file that carries ``[[agent]]`` blocks is a city /
    pack config: if no block matches and there is no ``[agent_defaults]`` table,
    treating the whole file as one agent's flat config would silently write the
    model into the wrong place, so we refuse instead.
    """
    text = _read(path)

    block = _find_agent_block(text, agent)
    if block is not None:
        return ConfigTarget(path=path, kind="agent_block", span=block, agent=agent)

    defaults = _find_table(text, "agent_defaults")
    if defaults is not None:
        return ConfigTarget(
            path=path, kind="agent_defaults", span=defaults, agent=agent
        )

    # No matching scope.  Is this a multi-agent (city/pack) config?
    has_agent_blocks = any(
        hdr.startswith("[[") and hdr.strip("[]").strip() == "agent"
        for hdr, _s, _e in _table_headers(text)
    )
    if require_agent or has_agent_blocks:
        raise ConfigResolveError(
            f"{path} has no [[agent]] name = \"{agent}\" block and no "
            "[agent_defaults] table to hold the model field"
        )
    return ConfigTarget(path=path, kind="flat", agent=agent)


def _table_headers(text: str):
    """Yield (header_name, header_start, body_start) for every top-level table.

    ``header_name`` is the raw bracket content (e.g. ``agent_defaults`` or
    ``[agent]`` for an array-of-tables — note double brackets keep their inner
    ``[agent]``).  We only need coarse boundaries to scope an edit, so a simple
    line scanner is sufficient and avoids a TOML round-trip.
    """
    for m in re.finditer(r'^[ \t]*(\[\[?[^\]\n]+\]\]?)[ \t]*$', text, re.MULTILINE):
        yield m.group(1), m.start(), m.end()


def _find_table(text: str, name: str) -> Optional[tuple]:
    """Return the (body_start, body_end) char span of the ``[name]`` table body."""
    headers = list(_table_headers(text))
    for i, (hdr, _hstart, hend) in enumerate(headers):
        inner = hdr.strip("[]").strip()
        if inner == name and not hdr.startswith("[["):
            body_start = hend
            body_end = headers[i + 1][1] if i + 1 < len(headers) else len(text)
            return (body_start, body_end)
    return None


def _find_agent_block(text: str, agent: str) -> Optional[tuple]:
    """Return the body span of the ``[[agent]]`` table whose ``name == agent``.

    Also matches a ``[agent.<name>]`` / ``[crew.<name>]`` / ``[workers.<name>]``
    style table (seen in ship.toml-style configs) keyed by the dotted name.
    """
    headers = list(_table_headers(text))
    for i, (hdr, _hstart, hend) in enumerate(headers):
        body_start = hend
        body_end = headers[i + 1][1] if i + 1 < len(headers) else len(text)
        body = text[body_start:body_end]
        inner = hdr.strip("[]").strip()
        is_array = hdr.startswith("[[")
        if is_array and inner == "agent":
            # match by `name = "<agent>"` inside the body
            nm = re.search(r'^[ \t]*name[ \t]*=[ \t]*["\']([^"\']+)["\']',
                           body, re.MULTILINE)
            if nm and nm.group(1) == agent:
                return (body_start, body_end)
        elif not is_array and "." in inner:
            # dotted table like [crew.Yatima] / [workers.builder] / [agent.foo]
            _prefix, _, dotted = inner.partition(".")
            if dotted == agent:
                return (body_start, body_end)
    return None


def read_model_field(target: ConfigTarget) -> Optional[str]:
    """Return the current ``model`` string for the target, or ``None`` if unset."""
    return read_field(target, "model")


def read_field(target: ConfigTarget, field: str) -> Optional[str]:
    """Return the current ``<field>`` string in the target's scope, or ``None``.

    Generalises :func:`read_model_field` to any scalar key (``provider`` /
    ``model`` / ``run_target``) so the apply path can report the current routing
    triple, not just the model.
    """
    text = _read(target.path)
    region = text
    if target.span is not None:
        region = text[target.span[0]:target.span[1]]
    esc = re.escape(field)
    m = re.search(
        r'^[ \t]*' + esc + r'[ \t]*=[ \t]*["\']([^"\']*)["\']', region, re.MULTILINE
    )
    if m:
        return m.group(1)
    # also accept an unquoted value just in case
    m = re.search(r'^[ \t]*' + esc + r'[ \t]*=[ \t]*([^\s#]+)', region, re.MULTILINE)
    if m:
        return m.group(1).strip().strip('"\'')
    return None


def set_model_field(target: ConfigTarget, model: str) -> None:
    """Write ``model = "<model>"`` into the target's scope, in place.

    Thin back-compat wrapper over :func:`set_field`.  If a ``model`` line already
    exists in scope it is replaced; otherwise a new line is inserted at the top
    of the scope body — but for an ``[[agent]]`` block just *after* the block's
    ``name = "..."`` line.  Formatting/comments elsewhere are preserved
    byte-for-byte.
    """
    set_field(target, "model", model)


def set_provider_field(target: ConfigTarget, provider: str) -> None:
    """Write ``provider = "<provider>"`` into the target's scope (see :func:`set_field`)."""
    set_field(target, "provider", provider)


def set_run_target_field(target: ConfigTarget, run_target: str) -> None:
    """Write ``run_target = "<run_target>"`` into the target's scope (see :func:`set_field`)."""
    set_field(target, "run_target", run_target)


def set_field(target: ConfigTarget, field: str, value: str) -> None:
    """Replace-or-insert ``<field> = "<value>"`` in the target's scope, in place.

    The byte-preserving editor generalised over the field name (``provider`` /
    ``model`` / ``run_target``).  An existing line for that field in scope is
    replaced; otherwise a new line is inserted at the top of the scope body —
    after the ``name = "..."`` line for an ``[[agent]]`` block so the block stays
    readable.  Everything else is preserved byte-for-byte.
    """
    text = _read(target.path)
    new_line = f'{field} = "{value}"'

    if target.span is None:
        # flat agent.toml: whole-file scope.
        updated = _replace_or_insert_top(text, field, new_line)
    else:
        start, end = target.span
        body = text[start:end]
        after_name = target.kind == "agent_block"
        new_body = _replace_or_insert_top(
            body, field, new_line, indent_from=body, after_name=after_name
        )
        updated = text[:start] + new_body + text[end:]

    _atomic_write(target.path, updated)


def set_tier_fields(
    target: ConfigTarget,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    run_target: Optional[str] = None,
) -> None:
    """Route an agent to a whole tier: set ``provider`` / ``model`` / ``run_target``.

    Applying a roster tier must set the full cross-provider routing target gc
    honors per dispatch (``gc.provider`` / ``gc.model`` / ``gc.run_target``), not
    just the model — otherwise a Codex tier would keep running on the agent's old
    provider.  This is **additive and byte-preserving**: each present field is
    replace-or-inserted via :func:`set_field`; ``None`` fields are left alone.

    ``model`` is always intended to be passed (back-compat: the model is still
    always written), with ``provider`` + ``run_target`` added alongside.  All
    three are applied in one pass so callers don't re-read the file per field.
    """
    # Order matters only for readability of a freshly-inserted block: write
    # provider, then model, then run_target so they land in a natural order
    # (each insert goes after `name`, so the last-written sits closest to it;
    # writing run_target last keeps model above it / provider at the bottom of
    # the inserted run — harmless either way, and replaces are position-stable).
    for field, val in (
        ("provider", provider),
        ("model", model),
        ("run_target", run_target),
    ):
        if val is not None and val != "":
            set_field(target, field, val)


def _replace_or_insert_top(
    body: str,
    field: str,
    new_line: str,
    indent_from: Optional[str] = None,
    after_name: bool = False,
) -> str:
    """Replace an existing ``<field> =`` line in ``body`` else insert it.

    ``indent_from`` (the scope body) is used to detect an existing indentation
    convention so an inserted line matches sibling keys.  When ``after_name`` is
    set and the body has a ``name = "..."`` line (an ``[[agent]]`` block), the
    new line is inserted right after it; otherwise it goes at the top of the
    body (after any leading blank lines).
    """
    m = _field_line_re(field).search(body)
    if m:
        indent = m.group("indent")
        return body[: m.start()] + f"{indent}{new_line}" + body[m.end():]

    indent = ""
    src = indent_from if indent_from is not None else body
    km = re.search(r'^(?P<indent>[ \t]+)\S', src, re.MULTILINE)
    if km:
        indent = km.group("indent")

    insert = f"{indent}{new_line}\n"

    if after_name:
        nm = re.search(r'^[ \t]*name[ \t]*=.*$', body, re.MULTILINE)
        if nm:
            # insert on the line after `name = "..."`
            pos = nm.end()
            # step past the newline that terminates the name line
            nl = body.find("\n", pos)
            pos = (nl + 1) if nl != -1 else len(body)
            return body[:pos] + insert + body[pos:]

    # Insert after a leading run of blank/whitespace lines so we sit at the top
    # of the actual content (and, for a scoped body, right under the header gap).
    lead = re.match(r'^([ \t]*\n)*', body)
    pos = lead.end() if lead else 0
    return body[:pos] + insert + body[pos:]


# --------------------------------------------------------------------------- #
# dispatch-side companion: the per-DISPATCH route triple
# --------------------------------------------------------------------------- #

def dispatch_metadata(cfg: Any, tier_id: str) -> dict:
    """Return the gc bead/agent routing metadata triple for a tier.

    The per-agent ``apply`` stamps the agent's *default* config; this is its
    dispatch-side companion: the ``{gc.provider, gc.model, gc.run_target}`` a
    caller can stamp on a single work bead to route just that dispatch to the
    tier's provider + model + run target (the triple the core
    ``mol-review-quorum`` formula proves gc honors per dispatch).
    """
    tier = cfg.tier(tier_id)
    return {
        "gc.provider": tier.provider,
        "gc.model": tier.model,
        "gc.run_target": tier.run_target,
    }


def backup_file(path: str) -> str:
    """Copy ``path`` to a timestamped ``.bak`` sibling and return its path."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{path}.advisor-bak-{ts}"
    shutil.copy2(path, backup)
    return backup


def _atomic_write(path: str, text: str) -> None:
    """Write ``text`` to ``path`` atomically (temp file + os.replace)."""
    tmp = f"{path}.advisor-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


# --------------------------------------------------------------------------- #
# state resolution shared by the subcommands
# --------------------------------------------------------------------------- #

def _resolve_state(args: argparse.Namespace) -> State:
    return build_state(
        advisor_toml=getattr(args, "config", None),
        telemetry_dir=getattr(args, "telemetry_dir", None),
        provider=getattr(args, "provider", None),
    )


def _resolve_cascade(bead_id: str, out: io.TextIOBase) -> Any:
    """Shell ``gc bd dep tree --json <bead>`` into a :class:`cascade.CascadeResult`.

    Best-effort + non-fatal: any failure (gc absent, non-JSON, unknown bead) prints
    a note and returns ``None`` so the advice still runs with the flat ``N_dep``
    (DESIGN §8 — the advisor must never block a dispatch).
    """
    import subprocess

    from modeladvisor import cascade as _cascade

    try:
        proc = subprocess.run(
            ["gc", "bd", "dep", "tree", "--json", bead_id],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:  # pragma: no cover - needs gc
        out.write(f"  note: --cascade-bead ignored (gc bd dep tree failed: {e})\n")
        return None
    if proc.returncode != 0 or not proc.stdout.strip():  # pragma: no cover - needs gc
        out.write("  note: --cascade-bead ignored (gc bd dep tree returned nothing)\n")
        return None
    try:
        tree = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):  # pragma: no cover - needs gc
        out.write("  note: --cascade-bead ignored (dep tree was not valid JSON)\n")
        return None
    graph = _cascade.build_graph_from_dep_json(tree)
    return _cascade.effective_cascade(graph, bead_id)


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROG,
        description="model-advisor — recommend / inspect / apply the "
        "cost-minimal model tier per agent·shape.",
    )
    p.add_argument(
        "--config",
        help="path to advisor.toml (else $ADVISOR_TOML or built-in defaults)",
    )
    p.add_argument(
        "--telemetry-dir",
        dest="telemetry_dir",
        help="telemetry dir holding invocations.jsonl / advisor-cells.json "
        "(else $ADVISOR_TELEMETRY_DIR or ./.beads/telemetry)",
    )
    p.add_argument(
        "--provider",
        help="provider token for the cell key (else config / 'claude')",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser(
        "advise",
        help="recommend a tier for <agent> <shape> (+ rationale, cost diff)",
    )
    a.add_argument("agent")
    a.add_argument("shape")
    a.add_argument("--json", action="store_true",
                   help="emit the structured `reasons` audit object")
    a.add_argument("--thompson", action="store_true",
                   help="use the genuine seeded Thompson-Sampling mode (DESIGN §7.3)")
    a.add_argument("--seed", type=int, default=None,
                   help="RNG seed for --thompson (reproducible draw)")
    a.add_argument("--cascade-bead", dest="cascade_bead", metavar="ID",
                   help="scale N_dep by this bead's downstream DAG "
                   "(gc bd dep tree --json)")
    a.set_defaults(func=cmd_advise)

    i = sub.add_parser(
        "inspect",
        help="per-tier posteriors + quality-drop CIs + widest gating cell",
    )
    i.add_argument("agent")
    i.add_argument("shape")
    i.add_argument("--json", action="store_true",
                   help="emit the per-tier table + widest-cell pointer as JSON")
    i.set_defaults(func=cmd_inspect)

    ap = sub.add_parser(
        "apply",
        help="set the agent's default model in gc config to the recommendation",
    )
    ap.add_argument("agent")
    ap.add_argument("--shape", help="shape to recommend on (else agent's "
                    "canonical default)")
    ap.add_argument("--city", help="city root (else $GC_CITY or cwd)")
    ap.add_argument("--rig", help="narrow the pack search to this rig")
    ap.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="print the planned change without writing")
    ap.add_argument("--json", action="store_true",
                    help="emit the structured apply result (incl. the per-DISPATCH "
                    "gc.provider/gc.model/gc.run_target metadata) as JSON")
    ap.set_defaults(func=cmd_apply)

    aa = sub.add_parser(
        "auto-apply",
        help="sweep EVERY agent; set each to its conservative per-agent tier "
        "(safest across its shapes), evidence-gated. Dry-run by default.",
    )
    scope_grp = aa.add_mutually_exclusive_group()
    scope_grp.add_argument(
        "--town", action="store_true",
        help="sweep all town/city agents (the default scope)",
    )
    scope_grp.add_argument(
        "--rig", metavar="NAME",
        help="narrow the config search + scope label to this rig",
    )
    aa.add_argument("--city", help="city root (else $GC_CITY or cwd)")
    aa.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="compute + report the plan without writing (this is the DEFAULT)",
    )
    aa.add_argument(
        "--apply", action="store_true", dest="apply",
        help="actually write config changes (otherwise dry-run-safe)",
    )
    aa.add_argument("--json", action="store_true",
                    help="emit the full structured per-agent report as JSON")
    aa.set_defaults(func=cmd_auto_apply)

    # ---- eval-schedule: Layer-4 auto-eval (DESIGN §5.4) ----
    es = sub.add_parser(
        "eval-schedule",
        help="rank gating cells by CI half-width x unlock-value and emit eval "
        "beads for the top N (dry-run by default)",
    )
    es.add_argument("--max", type=int, default=5,
                    help="cap on eval beads to schedule this run (default 5)")
    es.add_argument("--rig", metavar="NAME",
                    help="create the eval beads in this rig's database")
    es.add_argument("--city", help="city root (else $GC_CITY or cwd)")
    es.add_argument("--apply", action="store_true",
                    help="actually create the eval beads (otherwise dry-run-safe)")
    es.add_argument("--json", action="store_true",
                    help="emit the ranked plan + emitted commands/ids as JSON")
    es.set_defaults(func=cmd_eval_schedule)

    # ---- federate: export/import per-cell observed aggregates (DESIGN §7.3) ----
    fe = sub.add_parser(
        "federate",
        help="export this rig's per-cell aggregates, or import + merge peers'",
    )
    fe_sub = fe.add_subparsers(dest="action", required=True)
    fe_exp = fe_sub.add_parser(
        "export", help="write privacy-safe per-cell aggregates (a_obs/b_obs/n)",
    )
    fe_exp.add_argument("--out", help="write to this file (else stdout)")
    fe_exp.set_defaults(func=cmd_federate)
    fe_imp = fe_sub.add_parser(
        "import", help="fold peer aggregate exports into a merged store",
    )
    fe_imp.add_argument("peers", nargs="+", help="peer advisor-federation.json path(s)")
    fe_imp.add_argument("--trust", type=float, default=None,
                        help="trust weight on peer mass (else config / 0.3)")
    fe_imp.add_argument("--max-peer-mass", dest="max_peer_mass", type=float,
                        default=None, help="cap injected peer pseudocount mass per cell")
    fe_imp.add_argument("--json", action="store_true",
                        help="emit the merge summary as JSON")
    fe_imp.set_defaults(func=cmd_federate)

    # ---- drift: report Page-Hinkley change-points per cell (DESIGN §7.3) ----
    dr = sub.add_parser(
        "drift",
        help="report detected upstream-drift change-points per cell from telemetry",
    )
    dr.add_argument("--agent", help="filter to this agent")
    dr.add_argument("--shape", help="filter to this shape")
    dr.add_argument("--provider", help="filter to this provider (else config default)")
    dr.add_argument("--json", action="store_true",
                    help="emit the per-cell drift report as JSON")
    dr.set_defaults(func=cmd_drift)

    return p


def main(argv: Optional[Sequence[str]] = None,
         out: Optional[io.TextIOBase] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args, out)
    except BrokenPipeError:  # pragma: no cover - piped to head etc.
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
