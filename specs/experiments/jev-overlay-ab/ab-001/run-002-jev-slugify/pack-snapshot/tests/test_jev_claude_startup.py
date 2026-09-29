import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('startup',ROOT/'scripts/jev_claude_startup.py')
startup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


def test_trust_only_accepts_exact_experiment_directory():
    text='Accessing workspace:\n/private/tmp/fixture\nQuick safety check:\n❯ No, exit\nYes, I trust this folder'
    assert startup.action(text,Path('/private/tmp/fixture'))=='accept'
    with pytest.raises(ValueError,match='different directory'):
        startup.action(text,Path('/private/tmp/other'))


def test_login_is_a_failure_not_a_prompt_to_accept():
    with pytest.raises(ValueError,match='login'):
        startup.action('Browser did not open? https://claude.com/cai/oauth/authorize',Path('/tmp/fixture'))


def test_normal_subscription_prompt_is_ready():
    assert startup.action('Claude Code\nSonnet 5 · Claude Max\n❯ Try a task',Path('/tmp/fixture'))=='ready'
