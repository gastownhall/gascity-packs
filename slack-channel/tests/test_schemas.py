"""Validate slack-channel registry records against the shipped JSON Schemas.

The schemas in ../schema are the documented contract for the three on-disk
registries the adapter owns. This test asserts that records matching the
adapter's serialized shape pass, and that the documented constraints
(required keys, enums, mutual exclusions) actually reject bad records — so
"schema documented" and "schema validated" stay in lockstep.

Run: python3 -m pytest slack-channel/tests/
"""

from __future__ import annotations

import json
import pathlib

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema"


def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


# --- channel_mappings ------------------------------------------------------

CHANNEL_V = "channel_mappings.schema.json"


def test_channel_mappings_valid():
    doc = {
        "T123:C1": {
            "workspace_id": "T123",
            "channel_id": "C1",
            "kind": "room",
            "session_ids": ["s1", "s2"],
            "created_at": "2026-05-30T12:00:00Z",
            "updated_at": "2026-05-30T12:00:00Z",
        }
    }
    _validator(CHANNEL_V).validate(doc)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.pop("kind"),
        lambda r: r.update(kind="thread"),
        lambda r: r.update(session_ids=[]),
        lambda r: r.update(extra="nope"),
    ],
)
def test_channel_mappings_rejects(mutate):
    rec = {
        "workspace_id": "T123",
        "channel_id": "C1",
        "kind": "room",
        "session_ids": ["s1"],
        "created_at": "2026-05-30T12:00:00Z",
        "updated_at": "2026-05-30T12:00:00Z",
    }
    mutate(rec)
    with pytest.raises(ValidationError):
        _validator(CHANNEL_V).validate({"T123:C1": rec})


# --- identities ------------------------------------------------------------

IDENTITY_V = "identities.schema.json"


def test_identities_username_only_valid():
    doc = {
        "s1": {
            "session_id": "s1",
            "username": "Gas City PL",
            "created_at": "2026-05-30T12:00:00Z",
            "updated_at": "2026-05-30T12:00:00Z",
        }
    }
    _validator(IDENTITY_V).validate(doc)


def test_identities_rejects_both_icons():
    doc = {
        "s1": {
            "session_id": "s1",
            "icon_url": "https://x/a.png",
            "icon_emoji": "robot_face",
            "created_at": "2026-05-30T12:00:00Z",
            "updated_at": "2026-05-30T12:00:00Z",
        }
    }
    with pytest.raises(ValidationError):
        _validator(IDENTITY_V).validate(doc)


def test_identities_rejects_all_empty():
    doc = {
        "s1": {
            "session_id": "s1",
            "created_at": "2026-05-30T12:00:00Z",
            "updated_at": "2026-05-30T12:00:00Z",
        }
    }
    with pytest.raises(ValidationError):
        _validator(IDENTITY_V).validate(doc)


# --- handle_aliases --------------------------------------------------------

ALIAS_V = "handle_aliases.schema.json"


def test_handle_aliases_valid():
    doc = {
        "mayor": {
            "handle": "mayor",
            "session_id": "sess-m",
            "created_at": "2026-05-30T12:00:00Z",
            "updated_at": "2026-05-30T12:00:00Z",
        }
    }
    _validator(ALIAS_V).validate(doc)


@pytest.mark.parametrize("bad_handle", ["Mayor", "with space", "@mayor", ""])
def test_handle_aliases_rejects_bad_handle(bad_handle):
    doc = {
        bad_handle: {
            "handle": bad_handle,
            "session_id": "sess-m",
            "created_at": "2026-05-30T12:00:00Z",
            "updated_at": "2026-05-30T12:00:00Z",
        }
    }
    with pytest.raises(ValidationError):
        _validator(ALIAS_V).validate(doc)
