#!/usr/bin/env python3
"""Intake router for jev-build: send small, well-specified work to jev-build-compact.

Reads the task bead, asks Jev the frozen intake questions from the intake-router
spike (assets/jev-intake-questions.json) about the request text, and routes to
`jev-build-compact` only when the most likely size is compact at confidence
>= the band (day one 0.8), the risky surface is `none`, and no design step is
needed. Everything else, every uncertain answer, and every Jev failure takes
the full `jev-build` path. Audited compact decisions also take the full path.

The decision is logged to the gate state ledger and passed to the build as
`jev_intake_decision`; the build's review-report step labels it from the
finished diff (at most 3 files and 80 changed lines, no risky path).

Usage:
  jev_route.py <bead-id> [--dry-run] [--var key=value ...] [--target gc.run-operator]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jev_client  # noqa: E402
from jev_client import JevUnavailable  # noqa: E402
from jev_decisions import StateDir, audit_rate, decision  # noqa: E402
from jev_gate import Gc, extract_json  # noqa: E402

QUESTIONS = Path(__file__).resolve().parents[1] / 'jev-intake-questions.json'
SIZE_LEVELS = ('compact', 'standard', 'deep')
MAX_REQUEST = 6000


def request_text(bead: dict) -> str:
    return (f"{bead.get('title', '')}\n\n{bead.get('description', '')}").strip()[:MAX_REQUEST]


def classify(answers: dict) -> dict:
    size = answers['size']
    probabilities = {SIZE_LEVELS[int(k)]: v for k, v in size['probabilities'].items()}
    return {'size': max(probabilities, key=probabilities.get), 'size_probabilities': probabilities,
            'size_confidence': size['confidence'], 'risky_surface': answers['risky_surface']['choice'],
            'needs_design': answers['needs_design']['choice'],
            'well_specified': answers['well_specified']['choice']}


def route(answers: dict | None, band: dict, accepted: int, rng: random.Random,
          audit_override: float | None = None) -> tuple[str, bool, dict]:
    """Return (formula, audited, classification). Pure; tested with recorded answers."""
    if answers is None:
        return 'jev-build', False, {}
    facts = classify(answers)
    compact = (facts['size'] == 'compact' and facts['size_confidence'] >= band['min_confidence']
               and facts['risky_surface'] == 'none' and facts['needs_design'] == 'no'
               and not band.get('tripped'))
    if not compact:
        return 'jev-build', False, facts
    rate = audit_override if audit_override is not None else audit_rate(accepted)
    audited = rng.random() < rate
    return ('jev-build' if audited else 'jev-build-compact'), audited, facts


def state_dir(explicit: str) -> StateDir:
    if explicit:
        return StateDir(Path(explicit))
    city = os.environ.get('GC_CITY') or os.environ.get('GC_CITY_PATH')
    if not city:
        raise SystemExit('set --state-dir or run inside a city (GC_CITY)')
    return StateDir(Path(city) / '.gc/jev-gate')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('bead')
    parser.add_argument('--target', default='gc.run-operator')
    parser.add_argument('--var', action='append', default=[], help='sling variable key=value (repeatable)')
    parser.add_argument('--state-dir', default='')
    parser.add_argument('--model', default=jev_client.DEFAULT_MODEL)
    parser.add_argument('--audit-rate', type=float, default=None)
    parser.add_argument('--dry-run', action='store_true', help='decide and log, but do not sling')
    args = parser.parse_args(argv)
    variables = dict(v.split('=', 1) for v in args.var)
    state = state_dir(args.state_dir or variables.get('jev_state_dir', ''))
    gc = Gc()
    bead = gc.show(args.bead)
    text = request_text(bead)
    questions = json.loads(QUESTIONS.read_text())
    answers, error, usage, model = None, '', {}, args.model
    try:
        reply = jev_client.ask({'request': text}, questions, model=args.model)
        answers, usage, model = reply['answers'], reply['usage'], reply['model']
    except JevUnavailable as exc:
        error = exc.reason
    band = state.bands()['intake.compact']
    formula, audited, facts = route(answers, band, state.accepted_audits().get('intake.compact', 0),
                                    random.Random(), args.audit_rate)
    act = formula == 'jev-build-compact' or audited  # an audited compact decision is still act band
    record = decision('intake.compact', workflow_root='', step_bead=args.bead, subject=args.bead,
                      band='act' if act else ('escalate' if answers is None else 'confirm'),
                      action=formula, audit=audited, question='frozen intake questions v3',
                      answer=facts or None, p=facts.get('size_confidence'),
                      thresholds={'min_confidence': band['min_confidence']},
                      reason=f'jev unavailable: {error}' if error else ('breaker tripped' if band.get('tripped') else ''),
                      model=model, usage=usage)
    state.append([record])
    result = {'bead': args.bead, 'formula': formula, 'audited': audited, 'decision_id': record['decision_id'],
              'facts': facts, 'error': error}
    if not args.dry_run:
        variables.setdefault('jev_state_dir', str(state.path))
        variables['jev_intake_decision'] = record['decision_id']
        cmd = ['sling', args.target, args.bead, '--on', formula, '--json']
        for key, value in variables.items():
            cmd += ['--var', f'{key}={value}']
        out = gc.run(*cmd, timeout=600)
        try:
            data = extract_json(out)
            result['workflow_id'] = data.get('workflow_id') if isinstance(data, dict) else None
        except ValueError:
            result['sling_output'] = out[-500:]
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
