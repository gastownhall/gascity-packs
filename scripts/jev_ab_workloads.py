"""Workloads for the gascity vs gascity-jev build A/B (scripts/jev_build_ab.py).

Two kinds, per plan 0003 (Q3):

- planted: small fixtures whose task states edge cases that the visible tests
  do not cover. Hidden checks exercise exactly those stated cases, so a review
  that waves through a subtle defect shows up as a quality loss.
- backlog: real merged changes from this repository's history. The fixture is
  the parent commit's relevant files; the task restates the PR's problem and
  required interface; the hidden check is the merged commit's own test file run
  against the result.

Every workload's visible tests pass except for the missing behavior, and the
seed never contains the answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Workload:
    name: str
    kind: str                      # planted | backlog
    title: str
    description: str
    module: str                    # file the change must touch
    protected_tests: tuple[str, ...]
    test_paths: tuple[str, ...]
    seed: Callable[[Path], None]
    hidden: Callable[[Path, Path, dict], dict]
    stub_marker: str = 'NotImplementedError'
    notes: dict = field(default_factory=dict)

    def test_command(self, python: str = 'python3') -> str:
        return f'{python} -m pytest -q -p no:cacheprovider ' + ' '.join(self.test_paths)

    def task(self) -> str:
        return f'{self.title}\n\n{self.description.strip()}\n'


def run(command, cwd, env, timeout=120):
    proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout + proc.stderr)[-4000:]


def python_cases(module: str, function: str, cases: list[tuple], raises: list[str]):
    """Hidden check: call module.function on each case in a fresh interpreter."""
    code = textwrap.dedent(f'''
        import importlib.util, json
        spec = importlib.util.spec_from_file_location('subject', {module!r})
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        f = getattr(m, {function!r})
        results = []
        for arg, want in {cases!r}:
            try:
                got = f(arg); results.append({{'input': arg, 'expected': want, 'actual': got, 'pass': got == want}})
            except Exception as e:
                results.append({{'input': arg, 'expected': want, 'pass': False, 'error': type(e).__name__}})
        for arg in {raises!r}:
            try:
                got = f(arg); results.append({{'input': arg, 'expected': 'ValueError', 'actual': repr(got), 'pass': False}})
            except ValueError:
                results.append({{'input': arg, 'expected': 'ValueError', 'pass': True}})
            except Exception as e:
                results.append({{'input': arg, 'expected': 'ValueError', 'pass': False, 'error': type(e).__name__}})
        print(json.dumps(results))
        raise SystemExit(0 if all(r['pass'] for r in results) else 1)
    ''')

    def check(candidate: Path, out: Path, env: dict) -> dict:
        code_rc, output = run([sys.executable, '-c', code], candidate, env)
        (out / 'hidden.txt').write_text(output)
        try:
            rows = json.loads(next(l for l in reversed(output.splitlines()) if l.startswith('[')))
        except (ValueError, StopIteration):
            rows = []
        return {'pass': code_rc == 0, 'cases': len(rows), 'failed': [r for r in rows if not r.get('pass')]}
    return check


# --- planted: slugify -----------------------------------------------------------

def seed_slugify(root: Path) -> None:
    sys.path.insert(0, str(ROOT / 'scripts'))
    import gascity_pack_inference_gate as gate
    gate.write_build_basic_fixture(root)


SLUGIFY = Workload(
    name='slugify', kind='planted',
    title='Implement slugify in the fixture repository',
    description='''
The repository contains a deliberately failing Python fixture. Implement
`slugify` in `slugger.py` so the existing tests pass.

Expected behavior:
- Lowercase ASCII alphanumeric words.
- Treat any run of non-alphanumeric characters as a separator.
- Join non-empty groups with single hyphens, with no leading or trailing hyphen.
- Return an empty string when the input contains no alphanumeric characters.

Constraints:
- Do not change tests/test_slugger.py.
- Keep the implementation small and deterministic.
- Run `python3 -m pytest -q` from the repository root and record that proof.
''',
    module='slugger.py', protected_tests=('tests/test_slugger.py',), test_paths=('tests',),
    seed=seed_slugify,
    hidden=python_cases('slugger.py', 'slugify', [
        ('  Hello, World!  ', 'hello-world'), ('a---b___c', 'a-b-c'), ('123 ABC', '123-abc'), ('!@#', ''),
        ('--Leading and trailing--', 'leading-and-trailing'), ('Mixed_Case-42.txt', 'mixed-case-42-txt'),
        ('', '')], []),
)


# --- planted: durations ---------------------------------------------------------

DURATIONS_STUB = '''\
"""Duration parsing for the fixture repository."""


def parse_duration(text: str) -> int:
    """Return the number of seconds described by text, for example "1h30m"."""
    raise NotImplementedError("parse_duration is intentionally missing")
'''

DURATIONS_TESTS = '''\
import pytest

from durations import parse_duration


def test_hours_and_minutes() -> None:
    assert parse_duration("1h30m") == 5400


def test_seconds_only() -> None:
    assert parse_duration("45s") == 45


def test_unknown_unit_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_duration("5x")
'''


def seed_durations(root: Path) -> None:
    (root / 'tests').mkdir(parents=True, exist_ok=True)
    (root / 'durations.py').write_text(DURATIONS_STUB)
    (root / 'tests/test_durations.py').write_text(DURATIONS_TESTS)
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["."]\n')


DURATIONS = Workload(
    name='durations', kind='planted',
    title='Implement parse_duration in the fixture repository',
    description='''
Implement `parse_duration(text)` in `durations.py`. It returns the total number
of seconds as an int.

Expected behavior:
- The input is one or more groups of a non-negative integer followed by a unit:
  `h` (hours), `m` (minutes) or `s` (seconds). Examples: "1h30m" is 5400,
  "45s" is 45, "2h5s" is 7205, "0s" is 0.
- Units appear in h, m, s order and each unit at most once: "30m1h" and
  "1m1m" raise ValueError.
- Leading and trailing whitespace is ignored (" 5m " is 300); whitespace
  inside the value ("1h 30m") raises ValueError.
- An empty string, an unknown unit ("5x"), a unit without a number ("h"), a
  negative number ("-5s") and an uppercase unit ("5S") raise ValueError.

Constraints:
- Do not change tests/test_durations.py.
- Standard library only.
- Run `python3 -m pytest -q` from the repository root and record that proof.
''',
    module='durations.py', protected_tests=('tests/test_durations.py',), test_paths=('tests',),
    seed=seed_durations,
    hidden=python_cases('durations.py', 'parse_duration', [
        ('1h30m', 5400), ('45s', 45), ('2h5s', 7205), ('0s', 0), (' 5m ', 300), ('1h1m1s', 3661),
        ('10m', 600)], ['30m1h', '1m1m', '1h 30m', '', '5x', 'h', '-5s', '5S', '1.5h']),
)


# --- backlog: real merged changes ---------------------------------------------------

def git_tree(commit: str, paths: list[str], dest: Path) -> None:
    archive = subprocess.run(['git', 'archive', commit, *paths], cwd=ROOT, check=True, capture_output=True).stdout
    subprocess.run(['tar', '-x', '-C', str(dest)], input=archive, check=True)


def backlog_seed(commit: str, test_file: str):
    def seed(root: Path) -> None:
        git_tree(f'{commit}^', ['gascity/assets/scripts', 'gascity/schemas', f'gascity/tests/{test_file}'], root)
        (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths = ["gascity/tests"]\n')
    return seed


def backlog_hidden(commit: str, test_file: str):
    """Run the merged commit's own test file against the result's scripts."""
    def check(candidate: Path, out: Path, env: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            shutil.copytree(candidate / 'gascity/assets', work / 'gascity/assets')
            shutil.copytree(candidate / 'gascity/schemas', work / 'gascity/schemas')
            git_tree(commit, [f'gascity/tests/{test_file}'], work)
            code, output = run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                                f'gascity/tests/{test_file}'], work, env, timeout=300)
        (out / 'hidden.txt').write_text(output)
        summary = output.strip().splitlines()[-1] if output.strip() else ''
        return {'pass': code == 0, 'summary': summary, 'merged_tests': f'{commit}:gascity/tests/{test_file}'}
    return check


LEGACY_OPTIONS = Workload(
    name='legacy-work-options', kind='backlog',
    title='Normalize legacy work option metadata in task bead creation',
    description='''
Real backlog item (gascity-packs #68).

`gascity/assets/scripts/create_beads_from_tasks.py` turns a task plan into
bead metadata. Older plans still carry legacy work option keys:
`gc.model`, `gc.reasoning` and `gc.effort`. Gas City now reads the canonical
`opt_model` and `opt_effort` keys, so tasks written with the legacy keys lose
their model and effort settings.

Acceptance criteria:
- Task metadata `gc.model` is emitted as `opt_model`.
- Task metadata `gc.reasoning` or `gc.effort` is emitted as `opt_effort`.
- When a task sets both a legacy key and its canonical key, the explicit
  canonical `opt_model` / `opt_effort` value wins.
- The legacy keys no longer appear in the emitted metadata.
- Add regression coverage in `gascity/tests/test_create_beads_from_tasks.py`
  and keep every existing test passing.

Verify with `python3 -m pytest -q gascity/tests`.
''',
    module='gascity/assets/scripts/create_beads_from_tasks.py',
    protected_tests=(), test_paths=('gascity/tests',),
    seed=backlog_seed('99464ed', 'test_create_beads_from_tasks.py'),
    hidden=backlog_hidden('99464ed', 'test_create_beads_from_tasks.py'),
    notes={'upstream': 'gastownhall/gascity-packs#68', 'commit': '99464ed'},
)

SCHEMA_ROOTS = Workload(
    name='schema-roots', kind='backlog',
    title='Let derived packs register build artifact schemas with the shared validator',
    description='''
Real backlog item (gascity-packs #187).

`gascity/REQUIREMENTS.md` invites derived packs to extend the build artifact
schema set, but `gascity/assets/scripts/validate_build_artifact.py` hardcodes
`SCHEMA_ROOT` to the base pack's own tree and `load_schema()` searches only
that directory. A derived pack's new schema id (for example
`acme.build.bdd.v1`) fails as `unknown build artifact schema`, so derived
packs cannot use the shared artifact gate for the stages they add.

Acceptance criteria:
- Add `schema_roots()` returning the base `SCHEMA_ROOT` first, then any extra
  roots from a new `GC_BUILD_SCHEMA_ROOTS` environment variable
  (`os.pathsep`-separated; blank or missing entries are skipped).
- `load_schema()` searches those roots in order.
- A schema id published in the base root can never be shadowed or relaxed by
  an extra root.
- With `GC_BUILD_SCHEMA_ROOTS` unset, `schema_roots()` returns exactly
  `[SCHEMA_ROOT]` and behavior is unchanged.
- Schemas from extra roots still pass `validate_schema_definition()`.
- The CLI (`--schema`, `--path`) is unchanged.
- Add tests in `gascity/tests/test_validators.py` and keep every existing test
  passing.

Verify with `python3 -m pytest -q gascity/tests`.
''',
    module='gascity/assets/scripts/validate_build_artifact.py',
    protected_tests=(), test_paths=('gascity/tests',),
    seed=backlog_seed('9ab8a75', 'test_validators.py'),
    hidden=backlog_hidden('9ab8a75', 'test_validators.py'),
    notes={'upstream': 'gastownhall/gascity-packs#187', 'commit': '9ab8a75'},
)

WORKLOADS = {w.name: w for w in (SLUGIFY, DURATIONS, LEGACY_OPTIONS, SCHEMA_ROOTS)}
