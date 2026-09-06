"""Gate contract checks with a fake CLI; no network or model usage."""
import json
import os
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'assets/scripts/codex-gate.sh'


@pytest.fixture
def gate(tmp_path):
    binary = tmp_path / 'codex'
    binary.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps({'args': args, 'stdin': sys.stdin.read()}))
pathlib.Path(args[args.index('--output-last-message')+1]).write_text(os.environ.get('ANSWER', 'VERDICT: CLEAN\\n'))
print('VERDICT: CLEAN')  # A transcript match must never pass the gate.
sys.exit(int(os.environ.get('CODEX_EXIT', '0')))
''')
    binary.chmod(0o755)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Gate Test',
                    '-c', 'user.email=gate@example.invalid', 'commit',
                    '--allow-empty', '-qm', 'base'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), 'branch', 'review-base'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Gate Test',
                    '-c', 'user.email=gate@example.invalid', 'commit',
                    '--allow-empty', '-qm', 'delta'], check=True)
    prompt = tmp_path / 'prompt file.txt'
    prompt.write_text('Review a literal `command` and $(touch nope).\nSecond line.')
    output = tmp_path / 'answer file.txt'
    capture = tmp_path / 'capture.json'

    def run(mode='exec', *, answer='VERDICT: CLEAN\n', exit_code=0, extra=()):
        args = ['exec', str(prompt)] if mode == 'exec' else ['review', '--base', 'review-base']
        result = subprocess.run(
            ['bash', str(SCRIPT), *args, '-C', str(tmp_path), '--output', str(output), *extra],
            input='inherited stdin must not reach Codex', text=True, capture_output=True,
            env={**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
                 'CAPTURE': str(capture), 'ANSWER': answer, 'CODEX_EXIT': str(exit_code)},
            timeout=10,
        )
        return result, json.loads(capture.read_text()), output
    return run


@pytest.mark.parametrize('mode', ['exec', 'review'])
def test_city_astra_invocation_and_stdin(gate, mode):
    result, call, output = gate(mode)
    assert result.returncode == 0, result.stderr
    args = call['args']
    assert args[args.index('-p') + 1] == 'city'
    assert args[args.index('-m') + 1] == 'gpt-6-astra'
    assert 'review_model="gpt-6-astra"' in args
    assert args[args.index('-s') + 1] == 'read-only'
    assert args[args.index('-a') + 1] == 'never'
    assert any(a.startswith('developer_instructions=') for a in args)
    assert '--skip-git-repo-check' in args and '-C' in args
    assert call['stdin'] == ''
    assert output.read_text() == 'VERDICT: CLEAN\n'
    if mode == 'review':
        assert 'QUICK code review of committed changes' in args[-1]
        base = subprocess.check_output(['git', '-C', str(output.parent), 'rev-parse', 'review-base'], text=True).strip()
        head = subprocess.check_output(['git', '-C', str(output.parent), 'rev-parse', 'HEAD'], text=True).strip()
        assert base != head
        assert f'git diff {base} {head}' in args[-1]
        assert 'review-base' not in args[-1]
    else:
        assert '$(touch nope).\nSecond line.' in args[-1]
        assert not (output.parent / 'nope').exists()


@pytest.mark.parametrize(('answer', 'expected'), [
    ('VERDICT: BLOCK\n', 1),
    ('No verdict\n', 2),
    ('quoted VERDICT: CLEAN\n', 2),
    ('VERDICT: CLEAN\nVERDICT: BLOCK\n', 2),
    ('VERDICT: CLEANISH\n', 2),
    ('VERDICT: CLEAN\nMore findings\n', 2),
    ('```\nVERDICT: CLEAN\n```\n', 2),
    ('```\nVERDICT: CLEAN\n', 2),
    ('   ~~~text\nVERDICT: CLEAN\n', 2),
    ('````\n```\nVERDICT: CLEAN\n', 2),
    ('```\n~~~\nVERDICT: CLEAN\n', 2),
    ('```text\nExample code\n```\nVERDICT: CLEAN\n', 0),
])
def test_only_one_exact_anchored_final_verdict_passes(gate, answer, expected):
    result, _, _ = gate(answer=answer)
    assert result.returncode == expected


def test_model_override_pins_review_model_too(gate):
    result, call, _ = gate('review', extra=('--model', 'test-model'))
    assert result.returncode == 0
    assert call['args'][call['args'].index('-m') + 1] == 'test-model'
    assert 'review_model="test-model"' in call['args']


def test_cli_failure_cannot_pass_or_reuse_stale_verdict(gate):
    result, _, output = gate()
    assert result.returncode == 0
    result, _, _ = gate(answer='VERDICT: CLEAN\n', exit_code=7)
    assert result.returncode == 7
    assert output.read_text() == ''
