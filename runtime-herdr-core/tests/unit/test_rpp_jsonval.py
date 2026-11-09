"""Typed JSON edges: decoding errors never carry the document, and encoding
produces only JSON that gc's decoder accepts."""

from __future__ import annotations

import math

import pytest

from gc_runtime_herdr_core.rpp.jsonval import JsonObject, JsonShapeError, dumps, loads


def test_dumps_is_compact_ascii() -> None:
    assert dumps({"a": [1, "é"], "b": None}) == '{"a":[1,"\\u00e9"],"b":null}'


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_dumps_refuses_what_json_cannot_carry(value: float) -> None:
    # Go's encoding/json (gc's side of every wire) rejects NaN and Infinity.
    with pytest.raises(ValueError):
        dumps({"progress": value})


def test_loads_reports_size_not_content() -> None:
    with pytest.raises(JsonShapeError) as caught:
        loads(b'{"token": "sk-secret-value"')
    assert "sk-secret" not in str(caught.value)


def test_field_paths_name_nested_fields() -> None:
    doc = JsonObject.of(loads(b'{"outer": {"inner": 5}}'))
    with pytest.raises(JsonShapeError, match=r"outer\.inner"):
        doc.req_obj("outer").req_str("inner")
