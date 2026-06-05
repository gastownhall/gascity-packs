"""cockpit CLI — make a gas city Cockpit-ready and publish the discovery handshake.

    cockpit ready    [--base-url URL] [--city NAME] [--json]
        assert the live /v0 API is reachable + version-compatible + has the
        endpoints the Cockpit depends on.
    cockpit discover [--base-url URL] [--write] [--out FILE] [--json]
        probe the API and (with --write/--out) publish the discovery descriptor.
    cockpit contract [--json]
        print the /v0 API contract the extension pins.
    cockpit adapter  [--city NAME] [--callback-url URL] [--json]
        print the extmsg adapter registration spec the host submits at runtime.

``ready`` and ``contract`` are pure reads; ``discover`` only writes with
``--write``/``--out``. ``adapter`` PRINTS the registration spec — it does NOT
register (extmsg registration is a runtime, ephemeral API call; see
``docs/DESIGN.md`` fork #2 + cockpit-1ll.12).

Exit codes: 0 ok; 1 reachable but not Cockpit-compatible (version/paths); 2 API
unreachable or a contract error. Pure stdlib; invoked as ``python -m cockpit.cli``
by the ``bin/cockpit`` wrapper.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional, Sequence

from cockpit import contract as K
from cockpit import discovery as D


def _load_contract_or_die(path: Optional[str]) -> dict[str, Any]:
    try:
        return K.load_contract(path)
    except K.ContractError as e:
        sys.stderr.write(f"cockpit: {e}\n")
        raise SystemExit(2)


# --------------------------------------------------------------------------- #
# ready                                                                          #
# --------------------------------------------------------------------------- #

def cmd_ready(args: argparse.Namespace, out) -> int:
    contract = _load_contract_or_die(args.contract)
    req_ver = K.required_api_version(contract)
    req_paths = K.required_paths(contract)
    probe = D.probe_api(args.base_url, timeout=args.timeout)
    verdict = D.assess_readiness(probe, req_ver, req_paths)

    city_readiness = None
    if args.city and probe.get("reachable"):
        city_readiness = D.fetch_city_readiness(args.base_url, args.city, args.timeout)

    if args.json:
        out.write(
            json.dumps(
                {"probe": probe, "verdict": verdict, "city_readiness": city_readiness},
                indent=2,
            )
            + "\n"
        )
        return 0 if verdict["ready"] else (2 if not probe["reachable"] else 1)

    out.write(f"API:        {probe['base_url']}\n")
    if not probe["reachable"]:
        out.write("status:     UNREACHABLE\n")
        for e in probe["errors"]:
            out.write(f"  - {e}\n")
        out.write(
            "\nThe supervisor /v0 API is not answering. Is the city running "
            f"(gc start)? The API is served by the supervisor on {D.DEFAULT_BASE_URL} "
            "by default.\n"
        )
        return 2

    out.write(f"title:      {probe.get('api_title')}\n")
    out.write(
        f"version:    {probe.get('api_version')} "
        f"({'ok' if verdict['version_ok'] else 'MISMATCH; need ' + req_ver})\n"
    )
    if probe.get("build_id"):
        out.write(f"build:      {probe.get('health_status')} ({probe.get('build_id')})\n")
    if verdict["missing_paths"]:
        out.write(f"endpoints:  MISSING {len(verdict['missing_paths'])} required path(s):\n")
        for p in verdict["missing_paths"]:
            out.write(f"  - {p}\n")
    else:
        out.write(f"endpoints:  all {len(req_paths)} required path(s) present\n")
    if city_readiness is not None:
        out.write(f"city {args.city}: {json.dumps(city_readiness)}\n")

    out.write("\n" + ("COCKPIT-READY\n" if verdict["ready"] else "NOT cockpit-ready (see above)\n"))
    return 0 if verdict["ready"] else 1


# --------------------------------------------------------------------------- #
# discover                                                                       #
# --------------------------------------------------------------------------- #

def cmd_discover(args: argparse.Namespace, out) -> int:
    probe = D.probe_api(args.base_url, timeout=args.timeout)
    if not probe["reachable"]:
        sys.stderr.write(
            f"cockpit discover: /v0 API unreachable at {probe['base_url']} "
            f"({'; '.join(probe['errors']) or 'no response'}).\n"
        )
        return 2
    cities = sorted({str(c) for c in (args.city or [])})
    descriptor = D.build_descriptor(probe, cities=cities)

    written = None
    if args.write or args.out:
        written = D.write_descriptor(descriptor, args.out)

    if args.json:
        out.write(json.dumps({"descriptor": descriptor, "written_to": written}, indent=2) + "\n")
        return 0

    out.write(json.dumps(descriptor, indent=2) + "\n")
    if written:
        out.write(f"\npublished -> {written}\n")
    else:
        out.write(f"\n(not written; pass --write to publish to {D.descriptor_path()})\n")
    return 0


# --------------------------------------------------------------------------- #
# contract                                                                       #
# --------------------------------------------------------------------------- #

def cmd_contract(args: argparse.Namespace, out) -> int:
    contract = _load_contract_or_die(args.contract)
    if args.json:
        out.write(json.dumps(contract, indent=2) + "\n")
        return 0
    disc = contract.get("discovery", {})
    out.write(f"schema:           {contract.get('schema')}\n")
    out.write(f"required version: {K.required_api_version(contract)}\n")
    out.write(f"openapi:          {contract.get('api', {}).get('openapi')}\n")
    out.write(f"descriptor:       $GC_HOME/{disc.get('descriptor_path')}\n")
    out.write(f"default base url: {disc.get('default_base_url')}\n")
    out.write(f"auth model:       {disc.get('auth_model')}\n")
    req = K.required_paths(contract)
    out.write(f"\nrequired endpoints ({len(req)}):\n")
    for p in req:
        out.write(f"  - {p}\n")
    return 0


# --------------------------------------------------------------------------- #
# adapter                                                                        #
# --------------------------------------------------------------------------- #

def cmd_adapter(args: argparse.Namespace, out) -> int:
    contract = _load_contract_or_die(args.contract)
    spec = K.adapter_registration_spec(
        contract,
        account_id=args.account_id,
        name=args.name,
        callback_url=args.callback_url,
    )
    endpoint = K.register_path(contract).replace("{cityName}", args.city or "{cityName}")

    if args.json:
        out.write(json.dumps({"endpoint": endpoint, "method": "POST", "body": spec}, indent=2) + "\n")
        return 0

    out.write("# extmsg adapter registration spec (RUNTIME — see docs/DESIGN.md fork #2,\n")
    out.write("# cockpit-1ll.12). extmsg registration is an in-memory API call requiring a\n")
    out.write("# reachable callback_url; a static pack install does NOT durably register it.\n\n")
    out.write(f"POST {endpoint}\n\n")
    out.write(json.dumps(spec, indent=2) + "\n\n")
    out.write("# example:\n")
    out.write(f"curl -fsS -X POST {D.DEFAULT_BASE_URL}{endpoint} \\\n")
    out.write("  -H 'Content-Type: application/json' -H 'X-GC-Request: true' \\\n")
    out.write(f"  -d '{json.dumps(spec)}'\n")
    if not args.callback_url:
        out.write("\n# NOTE: no callback_url set — outbound delivery to the Cockpit needs one.\n")
    return 0


# --------------------------------------------------------------------------- #
# argparse plumbing                                                             #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cockpit",
        description="Make a gas city Cockpit-ready and publish the /v0 discovery handshake.",
    )
    p.add_argument(
        "--contract",
        default=None,
        help="path to the /v0 contract toml (default: the pack's contract/v0.toml)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("ready", help="assert the live /v0 API is reachable + version-compatible")
    pr.add_argument("--base-url", default=D.DEFAULT_BASE_URL, help="supervisor API base URL")
    pr.add_argument("--city", default=None, help="also fetch per-city readiness for this city")
    pr.add_argument("--timeout", type=float, default=4.0, help="per-request timeout (s)")
    pr.add_argument("--json", action="store_true", help="emit JSON")
    pr.set_defaults(func=cmd_ready)

    pd = sub.add_parser("discover", help="probe the API and (with --write) publish the descriptor")
    pd.add_argument("--base-url", default=D.DEFAULT_BASE_URL, help="supervisor API base URL")
    pd.add_argument(
        "--city",
        action="append",
        metavar="NAME",
        help="record this city in the descriptor (repeatable)",
    )
    pd.add_argument("--write", action="store_true", help="publish to the well-known descriptor path")
    pd.add_argument("--out", default=None, help="write the descriptor to FILE instead")
    pd.add_argument("--timeout", type=float, default=4.0, help="per-request timeout (s)")
    pd.add_argument("--json", action="store_true", help="emit JSON")
    pd.set_defaults(func=cmd_discover)

    pc = sub.add_parser("contract", help="print the /v0 API contract the extension pins")
    pc.add_argument("--json", action="store_true", help="emit JSON")
    pc.set_defaults(func=cmd_contract)

    pa = sub.add_parser("adapter", help="print the extmsg adapter registration spec (runtime)")
    pa.add_argument("--city", default=None, help="fill {cityName} in the endpoint")
    pa.add_argument("--account-id", default="default", help="adapter account id")
    pa.add_argument("--name", default="VS Code Cockpit", help="adapter display name")
    pa.add_argument("--callback-url", default=None, help="adapter outbound callback URL")
    pa.add_argument("--json", action="store_true", help="emit JSON")
    pa.set_defaults(func=cmd_adapter)

    return p


def main(argv: Optional[Sequence[str]] = None, out=None) -> int:
    out = out if out is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args, out))
    except SystemExit as e:  # raised by _load_contract_or_die
        return int(e.code) if e.code is not None else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
