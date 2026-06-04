"""provider-forge CLI — list / doctor / roster / targets over the catalog.

    forge list   [--all] [--json]            providers + models table (live by default)
    forge doctor [--json]                    per-live-provider CLI + auth readiness
    forge roster [--out FILE] [--provider P...]  generate model-advisor's [[tier]] roster
    forge targets [--json]                   run_target names the catalog declares (live)

Every surface reads ``catalog.toml`` (the source of truth). ``list``, ``doctor``,
``targets`` and ``roster``-to-stdout are read-only; only ``roster --out FILE``
writes, and only where you point it. ``doctor`` exits non-zero if any live
provider is broken (missing CLI or missing auth) so it is CI-usable.

Pure stdlib; invoked as ``python -m forge.cli`` by the bin/forge wrapper.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from typing import Any, Optional, Sequence

from forge.catalog import (
    Catalog,
    CatalogError,
    Model,
    Provider,
    load_catalog,
)

# doctor readiness states
READY = "ready"
MISSING_CLI = "missing-cli"
MISSING_AUTH = "missing-auth"


# --------------------------------------------------------------------------- #
# small table renderer (stdlib-only; no third-party tabulate)                   #
# --------------------------------------------------------------------------- #

def _render_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """A minimal fixed-width table: header row, rule, then rows. Left-aligned."""
    cols = len(headers)
    cells = [[("" if c is None else str(c)) for c in row] for row in rows]
    widths = [len(str(h)) for h in headers]
    for row in cells:
        for i in range(cols):
            widths[i] = max(widths[i], len(row[i]))

    def fmt(values: Sequence[str]) -> str:
        return "  ".join(str(v).ljust(widths[i]) for i, v in enumerate(values)).rstrip()

    out = [fmt([str(h) for h in headers]), "  ".join("-" * w for w in widths)]
    out.extend(fmt(row) for row in cells)
    return "\n".join(out)


def _money(x: float) -> str:
    """Render a $/MTok cost compactly (two decimals)."""
    return f"{x:.2f}"


# --------------------------------------------------------------------------- #
# list                                                                          #
# --------------------------------------------------------------------------- #

def _model_record(p: Provider, m: Model) -> dict[str, Any]:
    return {
        "provider": p.name,
        "status": p.status,
        "id": m.id,
        "model": m.model,
        "run_target": m.run_target,
        "in_cost": m.in_cost,
        "out_cost": m.out_cost,
        "context": m.context,
        "reasoning": m.default_reasoning or p.default_reasoning,
        "exclude_from_roster": m.exclude_from_roster,
        "note": m.note,
    }


def cmd_list(cat: Catalog, args: argparse.Namespace, out) -> int:
    include_scaffold = bool(args.all)
    providers = cat.providers if include_scaffold else cat.live()

    records: list[dict[str, Any]] = []
    for p in providers:
        for m in p.models:
            records.append(_model_record(p, m))

    if args.json:
        out.write(json.dumps(records, indent=2) + "\n")
        return 0

    if not records:
        scope = "any provider" if include_scaffold else "any LIVE provider"
        out.write(f"(no models declared under {scope})\n")
        return 0

    headers = ["PROVIDER", "MODEL", "STATUS", "RUN TARGET", "IN $/M", "OUT $/M", "REASONING"]
    rows = [
        [
            r["provider"],
            r["model"],
            r["status"],
            r["run_target"],
            _money(r["in_cost"]),
            _money(r["out_cost"]),
            r["reasoning"] or "-",
        ]
        for r in records
    ]
    out.write(_render_table(headers, rows) + "\n")

    # Note any live providers that declare no models, and (with --all) scaffolds.
    bare_live = [p.name for p in cat.live() if not p.models]
    if bare_live:
        out.write(f"\nlive providers with no models declared: {', '.join(bare_live)}\n")
    if include_scaffold:
        scaffolds = [p.name for p in cat.scaffold()]
        if scaffolds:
            out.write(
                f"scaffold providers (CLI not installed; no models yet): "
                f"{', '.join(scaffolds)}\n"
            )
    return 0


# --------------------------------------------------------------------------- #
# doctor                                                                        #
# --------------------------------------------------------------------------- #

def _which(cli: str) -> Optional[str]:
    """Resolve a CLI on PATH (indirection point for tests)."""
    return shutil.which(cli)


def diagnose_provider(p: Provider) -> dict[str, Any]:
    """Readiness of one live provider: CLI on PATH and auth file present.

    Order of failure reporting: a missing CLI dominates (you can't auth a CLI
    you don't have), then a missing auth file. A provider that declares no
    ``auth`` is considered authed-by-other-means (e.g. claude's native session).
    """
    cli_path = _which(p.cli)
    auth_path = p.auth_path()
    auth_ok = auth_path is None or auth_path.exists()

    if cli_path is None:
        status = MISSING_CLI
    elif not auth_ok:
        status = MISSING_AUTH
    else:
        status = READY

    return {
        "provider": p.name,
        "cli": p.cli,
        "cli_path": cli_path,
        "auth": str(auth_path) if auth_path is not None else None,
        "auth_ok": auth_ok,
        "status": status,
        "ready": status == READY,
    }


def cmd_doctor(cat: Catalog, args: argparse.Namespace, out) -> int:
    live = cat.live()
    results = [diagnose_provider(p) for p in live]
    broken = [r for r in results if not r["ready"]]

    if args.json:
        out.write(
            json.dumps(
                {"ok": not broken, "providers": results},
                indent=2,
            )
            + "\n"
        )
        return 1 if broken else 0

    if not results:
        out.write("(catalog declares no LIVE providers)\n")
        return 0

    headers = ["PROVIDER", "CLI", "STATUS", "CLI PATH", "AUTH"]
    rows = []
    for r in results:
        rows.append(
            [
                r["provider"],
                r["cli"],
                r["status"],
                r["cli_path"] or "(not on PATH)",
                _auth_cell(r),
            ]
        )
    out.write(_render_table(headers, rows) + "\n")

    if broken:
        names = ", ".join(r["provider"] for r in broken)
        out.write(f"\nNOT READY: {names}\n")
        return 1
    out.write(f"\nall {len(results)} live provider(s) ready\n")
    return 0


def _auth_cell(r: dict[str, Any]) -> str:
    if r["auth"] is None:
        return "(none required)"
    return r["auth"] if r["auth_ok"] else f"MISSING: {r['auth']}"


# --------------------------------------------------------------------------- #
# roster — generate model-advisor's [[tier]] roster from the catalog            #
# --------------------------------------------------------------------------- #

def render_roster_toml(cat: Catalog, providers: Optional[Sequence[str]] = None) -> str:
    """Emit a model-advisor-compatible ``[[tier]]`` roster as TOML text.

    Every LIVE provider's models except ``exclude_from_roster = true``,
    cost-ordered (rank 1 = cheapest by ``in_cost + out_cost``). Each tier emits
    exactly ``id, provider, model, run_target, rank, in_cost, out_cost``. A
    header comment records provenance and the cost caveat.
    """
    tiers = cat.roster_tiers(providers)

    live_names = [p.name for p in cat.live()]
    scope = (
        ", ".join(providers) if providers else ", ".join(live_names) or "(none)"
    )

    lines: list[str] = []
    lines.append("# advisor.toml roster — GENERATED by provider-forge from catalog.toml.")
    lines.append("#")
    lines.append("# Do not hand-edit the [[tier]] blocks below: regenerate with")
    lines.append("#   forge roster --out advisor.toml")
    lines.append("# so the model list is maintained in ONE place (the catalog). Paste these")
    lines.append("# tiers into model-advisor's advisor.toml (replacing its [[tier]] block);")
    lines.append("# the shapes / tolerance / agents / hyperparams sections are hand-owned.")
    lines.append("#")
    lines.append(f"# providers: {scope}")
    lines.append("# rank 1 = cheapest by (in_cost + out_cost); in_cost/out_cost are $/MTok.")
    lines.append("# COSTS ARE ESTIMATES (esp. Codex) — replace with your real rate sheet.")
    lines.append("# exclude_from_roster models are omitted; reasoning effort is advisory.")
    lines.append("")

    if not tiers:
        lines.append("# (no roster-eligible models — no LIVE providers declare models)")
        return "\n".join(lines) + "\n"

    for t in tiers:
        lines.append("[[tier]]")
        lines.append(f'id         = "{t["id"]}"')
        lines.append(f'provider   = "{t["provider"]}"')
        lines.append(f'model      = "{t["model"]}"')
        lines.append(f'run_target = "{t["run_target"]}"')
        lines.append(f'rank       = {t["rank"]}')
        lines.append(f"in_cost    = {_money(t['in_cost'])}")
        lines.append(f"out_cost   = {_money(t['out_cost'])}")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def cmd_roster(cat: Catalog, args: argparse.Namespace, out) -> int:
    providers = list(args.provider) if args.provider else None
    if providers:
        # Fail loudly on a typo'd / non-live provider rather than silently empty.
        live = {p.name for p in cat.live()}
        unknown = [p for p in providers if p not in live]
        if unknown:
            sys.stderr.write(
                "forge roster: not a LIVE provider: "
                + ", ".join(unknown)
                + f" (live: {', '.join(sorted(live)) or 'none'})\n"
            )
            return 2

    text = render_roster_toml(cat, providers)

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        n = len(cat.roster_tiers(providers))
        sys.stderr.write(f"forge roster: wrote {n} tier(s) to {args.out}\n")
        return 0

    out.write(text)
    return 0


# --------------------------------------------------------------------------- #
# targets — run_target names the catalog declares (the gc session configs)      #
# --------------------------------------------------------------------------- #

def cmd_targets(cat: Catalog, args: argparse.Namespace, out) -> int:
    records: list[dict[str, Any]] = []
    for p in cat.live():
        for m in p.models:
            records.append(
                {
                    "run_target": m.run_target,
                    "provider": p.name,
                    "model": m.model,
                    "id": m.id,
                    "exclude_from_roster": m.exclude_from_roster,
                }
            )

    if args.json:
        out.write(json.dumps(records, indent=2) + "\n")
        return 0

    if not records:
        out.write("(no run targets — no LIVE provider declares models)\n")
        return 0

    headers = ["RUN TARGET", "PROVIDER", "MODEL"]
    rows = [[r["run_target"], r["provider"], r["model"]] for r in records]
    out.write(_render_table(headers, rows) + "\n")
    out.write(
        f"\n{len(records)} run target(s) the catalog expects to exist as gc session configs\n"
    )
    return 0


# --------------------------------------------------------------------------- #
# argparse plumbing                                                             #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="forge",
        description="Catalog + enablement for multi-provider model run targets in gc.",
    )
    p.add_argument(
        "--catalog",
        default=None,
        help="path to catalog.toml (default: the pack's catalog.toml)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="list providers + models from the catalog")
    pl.add_argument("--all", action="store_true", help="include scaffold providers")
    pl.add_argument("--json", action="store_true", help="emit JSON")
    pl.set_defaults(func=cmd_list)

    pd = sub.add_parser("doctor", help="check live providers' CLI + auth readiness")
    pd.add_argument("--json", action="store_true", help="emit JSON")
    pd.set_defaults(func=cmd_doctor)

    pr = sub.add_parser("roster", help="generate model-advisor [[tier]] roster")
    pr.add_argument("--out", default=None, help="write to FILE instead of stdout")
    pr.add_argument(
        "--provider",
        action="append",
        metavar="P",
        help="restrict to this live provider (repeatable)",
    )
    pr.set_defaults(func=cmd_roster)

    pt = sub.add_parser("targets", help="list run_target names per live model")
    pt.add_argument("--json", action="store_true", help="emit JSON")
    pt.set_defaults(func=cmd_targets)

    return p


def main(argv: Optional[Sequence[str]] = None, out=None) -> int:
    out = out if out is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cat = load_catalog(args.catalog)
    except CatalogError as e:
        sys.stderr.write(f"forge: {e}\n")
        return 2
    return int(args.func(cat, args, out))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
