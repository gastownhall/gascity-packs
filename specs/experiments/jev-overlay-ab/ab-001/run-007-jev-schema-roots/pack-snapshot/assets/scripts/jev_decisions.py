#!/usr/bin/env python3
"""Bands, audit sampling, circuit breaker and decision log for the Jev gates.

A gate state directory holds:

- `bands.json`  — per decision type thresholds plus the circuit-breaker flag.
  Missing entries fall back to the day-one bands below.
- `ledger.jsonl` — every decision and every later outcome, across builds. The
  adaptive audit rate reads its counts from here.

Each build also writes the same records to `<artifact_root>/jev/decisions.jsonl`.

Subcommands:
  status     print bands, breaker state and audit counts for a state dir
  aggregate  merge decision logs from many runs into one summary
  refit      recompute bands from labeled outcomes and reset tripped breakers
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sys
import uuid

# Day-one bands (plan 0003 and the gate spikes). Conservative on purpose;
# `refit` widens or narrows them from audited outcomes.
DAY_ONE_BANDS = {
    # Noul "is there any input that violates this criterion?": the acceptance
    # lane skips a criterion at P(violation) <= act_max_p.
    'review.criterion': {'act_max_p': 0.15},
    # Receipts (tests pass, pre-existing tests unchanged by hash) skip the
    # test-evidence lane. No Jev threshold.
    'review.test_evidence': {'act_enabled': True},
    # Smell screen: a fully clean screen (every rule x hunk <= clean_max_p)
    # drops the smell checks from the simplicity lane.
    'smell.clean': {'clean_max_p': 0.2},
    # A smell at P >= confirmed_min_p goes straight to the implementer.
    'smell.confirmed': {'confirmed_min_p': 0.9},
    # Simplicity design review: day one always runs (plan 0003). A refit or an
    # operator may set skip_when_screen_clean once audits support it.
    'simplicity.design': {'skip_when_screen_clean': False},
    # Intake route: compact only at size confidence >= min_confidence with no
    # risky surface and no design need.
    'intake.compact': {'min_confidence': 0.8},
}

# Adaptive audit schedule per decision type (plan 0003, Q7).
AUDIT_SCHEDULE = ((60, 0.30), (300, 0.10))
AUDIT_FLOOR = 0.05

REFIT_MARGIN = 0.05
REFIT_MIN_LABELS = 60
REFIT_STEP = 0.05
REFIT_CAPS = {'review.criterion': 0.30, 'smell.clean': 0.35}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def new_id() -> str:
    return 'jd-' + uuid.uuid4().hex[:12]


def audit_rate(accepted_audits: int) -> float:
    for limit, rate in AUDIT_SCHEDULE:
        if accepted_audits < limit:
            return rate
    return AUDIT_FLOOR


class StateDir:
    """Cross-run gate state. All writes hold an exclusive file lock."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.bands_path = self.path / 'bands.json'
        self.ledger_path = self.path / 'ledger.jsonl'

    @contextmanager
    def lock(self):
        with (self.path / '.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def raw_bands(self) -> dict:
        if not self.bands_path.is_file():
            return {'version': 1, 'types': {}}
        data = json.loads(self.bands_path.read_text())
        if not isinstance(data, dict) or not isinstance(data.get('types'), dict):
            raise ValueError(f'{self.bands_path} is not a bands file')
        return data

    def bands(self) -> dict:
        """Effective bands: day-one defaults overlaid with the stored file."""
        stored = self.raw_bands()['types']
        merged = {}
        for kind, defaults in DAY_ONE_BANDS.items():
            merged[kind] = {**defaults, 'tripped': False, **stored.get(kind, {})}
        return merged

    def write_bands(self, types: dict, note: str) -> None:
        data = {'version': 1, 'updated_at': now(), 'note': note, 'types': types}
        tmp = self.bands_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
        tmp.replace(self.bands_path)

    def records(self) -> list[dict]:
        return read_jsonl(self.ledger_path)

    def append(self, records: list[dict]) -> None:
        with self.lock():
            append_jsonl(self.ledger_path, records)

    def accepted_audits(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.records():
            if row.get('record') == 'outcome' and row.get('audited') and not row.get('miss'):
                counts[row['type']] = counts.get(row['type'], 0) + 1
        return counts

    def trip(self, kind: str, decision_id: str, reason: str) -> None:
        """Circuit breaker: fold this type's act band into confirm until refit."""
        with self.lock():
            data = self.raw_bands()
            entry = data['types'].setdefault(kind, {})
            entry.update(tripped=True, tripped_at=now(), tripped_by=decision_id, tripped_reason=reason)
            self.write_bands(data['types'], f'breaker tripped for {kind}')


def read_jsonl(path: Path) -> list[dict]:
    if not Path(path).is_file():
        return []
    rows = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, records: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('a') as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + '\n')


class DecisionLog:
    """Writes one build's records to its JSONL file and to the shared ledger."""

    def __init__(self, build_log: Path, state: StateDir):
        self.build_log = Path(build_log)
        self.state = state

    def write(self, records: list[dict]) -> None:
        if not records:
            return
        append_jsonl(self.build_log, records)
        self.state.append(records)

    def outcome(self, decision: dict, *, label: str, jev_correct: bool | None,
                source: str, note: str = '', always_labeled: bool = False) -> dict:
        """Record a labeled outcome; trip the breaker on an audited act-band miss.

        always_labeled marks decision types whose every act decision gets a
        label (the intake route, labeled from the finished diff), so a
        contradiction counts as a miss without an audit.
        """
        checked = decision.get('audit') or always_labeled
        miss = bool(decision.get('band') == 'act' and checked and jev_correct is False)
        record = {'record': 'outcome', 'decision_id': decision['decision_id'], 'type': decision['type'],
                  'at': now(), 'workflow_root': decision.get('workflow_root'), 'label': label,
                  'jev_correct': jev_correct, 'audited': bool(decision.get('audit')),
                  'band': decision.get('band'), 'miss': miss, 'source': source, 'note': note}
        self.write([record])
        if miss:
            self.state.trip(decision['type'], decision['decision_id'],
                            f'audited act-band decision contradicted by {source}')
        return record


def decision(kind: str, *, workflow_root: str, step_bead: str, subject: str, band: str,
             action: str, audit: bool = False, question: str = '', answer=None, p=None,
             thresholds: dict | None = None, receipts: dict | None = None, reason: str = '',
             model: str = '', usage: dict | None = None) -> dict:
    return {'record': 'decision', 'decision_id': new_id(), 'type': kind, 'at': now(),
            'workflow_root': workflow_root, 'step_bead': step_bead, 'subject': subject,
            'band': band, 'action': action, 'audit': audit, 'question': question,
            'answer': answer, 'p': p, 'thresholds': thresholds or {}, 'receipts': receipts or {},
            'reason': reason, 'model': model, 'usage': usage or {}}


def join(records: list[dict]) -> list[dict]:
    """Decisions with their latest outcome attached, deduplicated by id."""
    decisions, outcomes = {}, {}
    for row in records:
        if row.get('record') == 'decision':
            decisions[row['decision_id']] = row
        elif row.get('record') == 'outcome':
            outcomes[row['decision_id']] = row
    return [{**d, 'outcome': outcomes.get(i)} for i, d in decisions.items()]


def summarize(records: list[dict]) -> dict:
    rows = join(records)
    summary: dict[str, dict] = {}
    for row in rows:
        s = summary.setdefault(row['type'], {'decisions': 0, 'bands': {}, 'actions': {},
                                              'audited': 0, 'labeled': 0, 'misses': 0})
        s['decisions'] += 1
        s['bands'][row['band']] = s['bands'].get(row['band'], 0) + 1
        s['actions'][row['action']] = s['actions'].get(row['action'], 0) + 1
        s['audited'] += bool(row.get('audit'))
        if row['outcome']:
            s['labeled'] += 1
            s['misses'] += bool(row['outcome'].get('miss'))
    return summary


def refit(records: list[dict], bands: dict) -> tuple[dict, list[str]]:
    """Recompute bands from labeled outcomes and clear tripped breakers.

    Threshold types move to just below the nearest contradicting label (minus a
    margin) and widen by one step only after REFIT_MIN_LABELS labels with no
    contradiction inside the widened band. Receipt-only types re-enable only
    while the audited miss rate stays at or under 5%.
    """
    rows = [r for r in join(records) if r['outcome']]
    new = {k: dict(v) for k, v in bands.items()}
    notes = []

    def labeled(kind):
        return [r for r in rows if r['type'] == kind and isinstance(r.get('p'), (int, float))]

    def threshold_low(kind, key, bad_labels):
        entry = new[kind]
        current = entry[key]
        items = labeled(kind)
        bad = [r['p'] for r in items if r['outcome']['label'] in bad_labels]
        cap = REFIT_CAPS[kind]
        if bad and min(bad) - REFIT_MARGIN < current:
            target = round(max(0.0, min(bad) - REFIT_MARGIN), 3)
            notes.append(f'{kind}: narrowed {key} {current} -> {target} (contradiction at p={min(bad)})')
        elif len(items) >= REFIT_MIN_LABELS:
            limit = min(bad) - REFIT_MARGIN if bad else cap
            target = round(min(current + REFIT_STEP, limit, cap), 3)
            notes.append(f'{kind}: {key} {current} -> {target} over {len(items)} labels')
        else:
            target = current
            notes.append(f'{kind}: kept {key} {current} ({len(items)} labels < {REFIT_MIN_LABELS})')
        entry[key] = max(target, 0.0)

    threshold_low('review.criterion', 'act_max_p', {'violated'})
    threshold_low('smell.clean', 'clean_max_p', {'present'})

    confirmed = labeled('smell.confirmed')
    false_alarms = [r['p'] for r in confirmed if r['outcome']['label'] == 'absent']
    if false_alarms:
        entry = new['smell.confirmed']
        target = round(min(1.0, max(entry['confirmed_min_p'], max(false_alarms) + REFIT_MARGIN)), 3)
        notes.append(f"smell.confirmed: confirmed_min_p {entry['confirmed_min_p']} -> {target}")
        entry['confirmed_min_p'] = target

    intake = [r for r in rows if r['type'] == 'intake.compact' and r['outcome'].get('miss')]
    if intake:
        entry = new['intake.compact']
        worst = max(float((r.get('answer') or {}).get('size_confidence', 0)) for r in intake)
        entry['min_confidence'] = round(min(1.0, max(entry['min_confidence'], worst + REFIT_MARGIN)), 3)
        notes.append(f"intake.compact: min_confidence -> {entry['min_confidence']}")

    evidence = [r for r in rows if r['type'] == 'review.test_evidence' and r['outcome'].get('audited')]
    misses = sum(bool(r['outcome'].get('miss')) for r in evidence)
    receipts_ok = not evidence or misses / len(evidence) <= 0.05
    new['review.test_evidence']['act_enabled'] = receipts_ok
    notes.append(f'review.test_evidence: {misses} misses in {len(evidence)} audits; act '
                 + ('enabled' if receipts_ok else 'disabled'))

    for kind, entry in new.items():
        if entry.get('tripped'):
            notes.append(f'{kind}: breaker reset by refit')
        for key in ('tripped', 'tripped_at', 'tripped_by', 'tripped_reason'):
            entry.pop(key, None)
        entry['tripped'] = False
    return new, notes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    status = sub.add_parser('status')
    status.add_argument('--state-dir', type=Path, required=True)
    aggregate = sub.add_parser('aggregate')
    aggregate.add_argument('logs', type=Path, nargs='+', help='decisions.jsonl or ledger.jsonl files')
    aggregate.add_argument('--out', type=Path)
    fit = sub.add_parser('refit')
    fit.add_argument('--state-dir', type=Path, required=True)
    fit.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)

    if args.command == 'status':
        state = StateDir(args.state_dir)
        counts = state.accepted_audits()
        report = {'state_dir': str(state.path), 'bands': state.bands(),
                  'accepted_audits': counts,
                  'audit_rates': {k: audit_rate(counts.get(k, 0)) for k in DAY_ONE_BANDS},
                  'summary': summarize(state.records())}
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.command == 'aggregate':
        records = [row for path in args.logs for row in read_jsonl(path)]
        rows = join(records)
        report = {'sources': [str(p) for p in args.logs], 'decisions': len(rows),
                  'summary': summarize(records), 'rows': rows}
        text = json.dumps(report, indent=2, sort_keys=True) + '\n'
        if args.out:
            args.out.write_text(text)
            print(json.dumps({'decisions': len(rows), 'out': str(args.out)}))
        else:
            sys.stdout.write(text)
        return 0
    state = StateDir(args.state_dir)
    with state.lock():
        new, notes = refit(state.records(), state.bands())
        if not args.dry_run:
            state.write_bands(new, 'refit: ' + '; '.join(notes))
    print(json.dumps({'bands': new, 'notes': notes, 'written': not args.dry_run}, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
