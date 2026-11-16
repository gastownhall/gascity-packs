"""The hc config the pack writes for a city's core type-checks against hc
v0.1.19's ``Config`` (``crates/herdr-core/src/config.rs``), the table fake-hc
also enforces: a key of the wrong type makes hc refuse every ``terminal.run``,
and a key hc does not know is silently ignored, so neither may ship."""

from __future__ import annotations

import pytest
from fakehc.hcconfig import HC_CONFIG_KEYS, HcConfigError, parse_hc_config

from gc_runtime_herdr_core.herdrcore.config import HC_CONFIG_TOML


def test_the_packs_hc_config_type_checks_against_hcs_schema() -> None:
    settings = parse_hc_config(HC_CONFIG_TOML)
    assert settings, "the pack writes an hc config with no settings"


def test_the_packs_hc_config_names_only_keys_hc_reads() -> None:
    unknown = sorted(set(parse_hc_config(HC_CONFIG_TOML)) - set(HC_CONFIG_KEYS))
    assert unknown == [], f"hc v0.1.19 ignores these keys: {unknown}"


def test_the_packs_hc_config_turns_notes_off_and_bounds_history() -> None:
    settings = parse_hc_config(HC_CONFIG_TOML)
    assert settings["notes"] is False
    assert settings["history_mb"] == 16


def test_the_schema_table_is_hcs_config_struct() -> None:
    assert HC_CONFIG_KEYS == {
        "shell": "list of strings",
        "detach_key": "string",
        "wait_timeout": "f64",
        "notes": "bool",
        "notes_quiet": "f64",
        "headless": "string",
        "history_mb": "f64",
        "socket": "string",
        "machine_timeout": "f64",
    }


@pytest.mark.parametrize(
    "text",
    ["notes_quiet = true\n", "notes = 0\n", 'history_mb = "16"\n', "history_mb = true\n", 'shell = "sh"\n', "x = \n"],
)
def test_a_wrong_type_fails_the_check(text: str) -> None:
    with pytest.raises(HcConfigError):
        parse_hc_config(text)
