"""stderr redaction (the sensitive-key rule is gc's internal/execenv one)."""

from __future__ import annotations

import pytest

from gc_runtime_herdr_core.rpp.redact import REDACTED, Redactor, is_sensitive_key


@pytest.mark.parametrize(
    "key",
    [
        "GC_INSTANCE_TOKEN",
        "github_token",
        "DB_PASSWORD",
        "AWS_SECRET_ACCESS_KEY",
        "OPENAI_API_KEY",
        "MY-API-KEY",
        "SSH_PRIVATE_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "X_OAUTH_CLIENT",
        "CODEX_AUTH_JSON",
    ],
)
def test_sensitive_keys_follow_gc(key: str) -> None:
    assert is_sensitive_key(key)


@pytest.mark.parametrize("key", ["PATH", "HOME", "GC_CITY", "GC_SESSION_ID", "", "  "])
def test_ordinary_keys_are_not_sensitive(key: str) -> None:
    assert not is_sensitive_key(key)


def test_marker_is_bracketed_upper_case() -> None:
    assert REDACTED == "[REDACTED]"


def test_every_start_env_value_of_eight_characters_or_more_is_redacted() -> None:
    redactor = Redactor()
    redactor.add_start_env({"GC_AGENT": "worker-7", "SHORT": "abc1234", "PROVIDER_URL": "https://x.example/v1"})
    out = redactor.redact("agent worker-7 at https://x.example/v1 used abc1234")
    assert "worker-7" not in out
    assert "https://x.example/v1" not in out
    assert "abc1234" in out  # seven characters, and the key is not sensitive


def test_sensitive_values_from_the_op_environment_are_redacted() -> None:
    redactor = Redactor()
    redactor.add_process_env({"ANTHROPIC_API_KEY": "sk-12", "PATH": "/usr/bin:/bin", "TINY_TOKEN": "abc"})
    out = redactor.redact("key sk-12 path /usr/bin:/bin tiny abc")
    assert "sk-12" not in out
    assert "/usr/bin:/bin" in out
    assert "tiny abc" in out  # under gc's four-character floor


def test_instance_token_never_survives_whatever_its_length() -> None:
    redactor = Redactor()
    redactor.add_start_env({"GC_INSTANCE_TOKEN": "t9"})
    assert "t9" not in redactor.redact("token=t9 and t9")


def test_longer_secrets_are_replaced_first() -> None:
    redactor = Redactor()
    redactor.add_secret("abcdefgh")
    redactor.add_secret("abcdefgh-ijkl")
    assert redactor.redact("x abcdefgh-ijkl y") == f"x {REDACTED} y"


def test_secret_assignments_are_redacted_even_when_unknown() -> None:
    redactor = Redactor()
    out = redactor.redact("hc said: --api-key=zz9q GITHUB_TOKEN: ghp_1 password=hunter2")
    assert "zz9q" not in out
    assert "ghp_1" not in out
    assert "hunter2" not in out
    assert out.startswith("hc said: --api-key=")


def test_redaction_leaves_clean_text_alone() -> None:
    assert Redactor().redact('session "mc-mayor" already exists') == 'session "mc-mayor" already exists'


def test_length_floors_count_utf8_bytes_like_gc() -> None:
    # gc's execenv compares len(value) in bytes: two euro signs are 6 bytes.
    redactor = Redactor()
    redactor.add_process_env({"SHORT_TOKEN": "€€"})
    redactor.add_start_env({"GC_LABEL": "äöüß"})  # 4 characters, 8 bytes
    out = redactor.redact("token €€ label äöüß")
    assert "€€" not in out
    assert "äöüß" not in out


def test_short_ascii_values_stay_below_the_floors() -> None:
    redactor = Redactor()
    redactor.add_process_env({"SHORT_TOKEN": "abc"})
    redactor.add_start_env({"GC_LABEL": "abcdefg"})
    assert redactor.redact("abc abcdefg") == "abc abcdefg"
