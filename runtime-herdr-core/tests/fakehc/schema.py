"""The fake-hc schema guard.

Every result fake-hc returns, and every request a client sends it, is
validated against hc's OpenRPC document vendored at the pinned tag
(``hc.openrpc.json``; provenance in ``hc.openrpc.provenance.json``). A fake
that drifts from the real API, or a client that sends what hc does not
declare, fails the test that exercised it.

One deviation is excused, because the real core has it: hc v0.1.19 omits
``terminal.list``'s ``machines`` when it is empty although the schema
requires it (hc #190).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping

import referencing
import referencing.jsonschema
from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "hc.openrpc.json"
PROVENANCE_PATH = HERE / "hc.openrpc.provenance.json"

_BASE_URI = "urn:herdr-core:hc.openrpc"


class SchemaGuard:
    """Validates hc method params and results against an OpenRPC document."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self._document = document
        resource = referencing.Resource.from_contents(
            dict(document), default_specification=referencing.jsonschema.DRAFT7
        )
        self._registry: referencing.Registry[Any] = referencing.Registry().with_resource(_BASE_URI, resource)
        self._index: Dict[str, int] = {method["name"]: i for i, method in enumerate(document["methods"])}
        self._results: Dict[str, Draft7Validator] = {}
        self._params: Dict[str, Draft7Validator] = {}

    @classmethod
    @functools.lru_cache(maxsize=1)
    def vendored(cls) -> SchemaGuard:
        """The guard for the vendored schema (loaded once per process)."""
        return cls(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

    @property
    def methods(self) -> FrozenSet[str]:
        return frozenset(self._index)

    def error_kinds(self) -> FrozenSet[str]:
        """Every ``data.kind`` a method of the schema declares."""
        kinds = set()
        for method in self._document["methods"]:
            for error in method.get("errors", []):
                data = error.get("data")
                if isinstance(data, dict) and isinstance(data.get("kind"), str):
                    kinds.add(data["kind"])
        return frozenset(kinds)

    def _validator(self, schema: Dict[str, Any]) -> Draft7Validator:
        return Draft7Validator(schema, registry=self._registry)

    def _result_validator(self, method: str) -> Draft7Validator:
        if method not in self._results:
            pointer = f"{_BASE_URI}#/methods/{self._index[method]}/result/schema"
            self._results[method] = self._validator({"$ref": pointer})
        return self._results[method]

    def _params_validator(self, method: str) -> Draft7Validator:
        if method not in self._params:
            index = self._index[method]
            params = self._document["methods"][index].get("params", [])
            self._params[method] = self._validator(
                {
                    "type": "object",
                    "properties": {
                        param["name"]: {"$ref": f"{_BASE_URI}#/methods/{index}/params/{j}/schema"}
                        for j, param in enumerate(params)
                    },
                    "required": [param["name"] for param in params if param.get("required")],
                    "additionalProperties": False,
                }
            )
        return self._params[method]

    def check_result(self, method: str, result: object) -> List[str]:
        """Violations of ``method``'s result schema (empty when the result conforms)."""
        if method not in self._index:
            return [f"{method}: not an hc method"]
        if method == "terminal.list" and isinstance(result, dict) and "machines" not in result:
            result = dict(result, machines=[])  # hc #190: omitted when empty
        return [
            f"{method} result: {error.message} at /{'/'.join(str(p) for p in error.absolute_path)}"
            for error in self._result_validator(method).iter_errors(result)
        ]

    def check_params(self, method: str, params: object) -> List[str]:
        """Violations of ``method``'s params (by name; unknown params are violations)."""
        if method not in self._index:
            return [f"{method}: not an hc method"]
        return [
            f"{method} params: {error.message} at /{'/'.join(str(p) for p in error.absolute_path)}"
            for error in self._params_validator(method).iter_errors(params)
        ]
