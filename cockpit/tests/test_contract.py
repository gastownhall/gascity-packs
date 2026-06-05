"""cockpit — contract loader tests.

Own the /v0 contract: the shipped contract/v0.toml loads, pins the API version,
declares the load-bearing required endpoints, and yields a well-formed extmsg
adapter registration spec. Malformed contracts fail loudly.

Pure stdlib + pytest. The pack root is importable so ``cockpit.contract`` resolves.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest  # noqa: E402

from cockpit import contract as K  # noqa: E402


def test_shipped_contract_loads_and_pins_version():
    c = K.load_contract()
    assert c["schema"] == K.CONTRACT_SCHEMA
    assert K.required_api_version(c) == "0.1.0"


def test_required_paths_include_critical_endpoints():
    req = K.required_paths(K.load_contract())
    assert "/health" in req
    assert "/v0/cities" in req
    assert any("extmsg/adapters" in p for p in req)
    assert any("session/{id}/submit" in p for p in req)
    assert any("pending" in p for p in req)


def test_adapter_spec_shape_and_casing():
    spec = K.adapter_registration_spec(K.load_contract(), callback_url="http://x/cb")
    assert spec["provider"] == "cockpit"
    assert spec["account_id"] == "default"
    assert spec["callback_url"] == "http://x/cb"
    # Casing must mirror the live ExtMsgAdapterRegisterInputBody / AdapterCapabilities.
    assert set(spec["capabilities"]) == {
        "SupportsChildConversations",
        "SupportsAttachments",
        "MaxMessageLength",
    }


def test_adapter_spec_omits_callback_when_absent():
    spec = K.adapter_registration_spec(K.load_contract())
    assert "callback_url" not in spec


def test_register_path_is_city_scoped():
    assert "{cityName}" in K.register_path(K.load_contract())


def test_schema_mismatch_raises(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('schema = "nope"\n[api]\nrequired_version = "0.1.0"\n')
    with pytest.raises(K.ContractError):
        K.load_contract(str(p))


def test_missing_required_version_raises(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('schema = "cockpit.v0"\n[api]\ntitle = "x"\n')
    with pytest.raises(K.ContractError):
        K.load_contract(str(p))


def test_missing_file_raises(tmp_path):
    with pytest.raises(K.ContractError):
        K.load_contract(str(tmp_path / "nope.toml"))
