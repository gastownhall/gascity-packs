"""Typed access to decoded JSON at the wire edges.

Documents are parsed once, at the edge, into typed records by explicit
readers: a reader ignores fields it does not ask for and is strict about the
ones it does. Errors name the field's path and the expected type, never the
value, because the values on these wires (session environments, labels,
screen text) can be secrets.
"""

from __future__ import annotations

import json
from typing import Dict, List, Mapping, Optional, Tuple, Union, cast


class JsonShapeError(ValueError):
    """A JSON document is not the shape its reader requires."""


def loads(data: Union[str, bytes]) -> object:
    """Decode one JSON document."""
    try:
        value: object = json.loads(data)
    except ValueError:  # JSONDecodeError and UnicodeDecodeError both
        raise JsonShapeError(f"not a JSON document ({len(data)} bytes)") from None
    return value


def dumps(value: object) -> str:
    """Encode compactly, ASCII only, so any str (even an undecodable one) encodes.

    NaN and the infinities raise ValueError: they are not JSON, and gc's Go
    decoder rejects them.
    """
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def _kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, int):
        return "an integer"
    if isinstance(value, float):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, list):
        return "an array"
    return "an object"


class JsonObject:
    """A decoded JSON object, read field by field."""

    def __init__(self, fields: Mapping[str, object], where: str = "") -> None:
        self._fields = fields
        self._where = where

    @classmethod
    def of(cls, value: object, where: str = "") -> JsonObject:
        """Wrap ``value``, which must be a JSON object."""
        if not isinstance(value, dict):
            raise JsonShapeError(f"{where or 'document'}: expected an object, got {_kind(value)}")
        return cls(cast(Dict[str, object], value), where)

    def path(self, key: str) -> str:
        """The dotted path of ``key`` inside the document, for messages."""
        return f"{self._where}.{key}" if self._where else key

    def has(self, key: str) -> bool:
        """Whether ``key`` is present (null included)."""
        return key in self._fields

    def raw(self, key: str) -> object:
        """The undecoded value of ``key`` (None when missing)."""
        return self._fields.get(key)

    def _wrong(self, key: str, expected: str) -> JsonShapeError:
        if key not in self._fields:
            return JsonShapeError(f"{self.path(key)}: is required ({expected})")
        return JsonShapeError(f"{self.path(key)}: expected {expected}, got {_kind(self._fields[key])}")

    # strings

    def req_str(self, key: str) -> str:
        value = self._fields.get(key)
        if not isinstance(value, str):
            raise self._wrong(key, "a string")
        return value

    def opt_str(self, key: str) -> Optional[str]:
        value = self._fields.get(key)
        if value is None or isinstance(value, str):
            return value
        raise self._wrong(key, "a string or null")

    def str_or(self, key: str, default: str) -> str:
        value = self.opt_str(key)
        return default if value is None else value

    # integers (a JSON boolean is never an integer here)

    def req_int(self, key: str) -> int:
        value = self._fields.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise self._wrong(key, "an integer")
        return value

    def opt_int(self, key: str) -> Optional[int]:
        value = self._fields.get(key)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise self._wrong(key, "an integer or null")
        return value

    def int_or(self, key: str, default: int) -> int:
        value = self.opt_int(key)
        return default if value is None else value

    # booleans

    def req_bool(self, key: str) -> bool:
        value = self._fields.get(key)
        if not isinstance(value, bool):
            raise self._wrong(key, "a boolean")
        return value

    def opt_bool(self, key: str) -> Optional[bool]:
        value = self._fields.get(key)
        if value is None or isinstance(value, bool):
            return value
        raise self._wrong(key, "a boolean or null")

    def bool_or(self, key: str, default: bool) -> bool:
        value = self.opt_bool(key)
        return default if value is None else value

    # collections

    def _array(self, key: str, *, required: bool) -> List[object]:
        value = self._fields.get(key)
        if value is None and not required:
            return []
        if not isinstance(value, list):
            raise self._wrong(key, "an array")
        return cast(List[object], value)

    def _object(self, key: str) -> Dict[str, object]:
        value = self._fields.get(key)
        if not isinstance(value, dict):
            raise self._wrong(key, "an object")
        return cast(Dict[str, object], value)

    def _opt_object(self, key: str) -> Optional[Dict[str, object]]:
        return None if self._fields.get(key) is None else self._object(key)

    def str_tuple(self, key: str, *, required: bool = False) -> Tuple[str, ...]:
        """An array of strings (missing or null reads empty unless required)."""
        out: List[str] = []
        for index, item in enumerate(self._array(key, required=required)):
            if not isinstance(item, str):
                raise JsonShapeError(f"{self.path(key)}[{index}]: expected a string, got {_kind(item)}")
            out.append(item)
        return tuple(out)

    def str_map(self, key: str, *, required: bool = False) -> Dict[str, str]:
        """An object of strings (missing or null reads empty unless required)."""
        fields = self._object(key) if required else self._opt_object(key)
        out: Dict[str, str] = {}
        for name, item in (fields or {}).items():
            if not isinstance(item, str):
                raise JsonShapeError(f"{self.path(key)}.{name}: expected a string, got {_kind(item)}")
            out[name] = item
        return out

    def req_obj(self, key: str) -> JsonObject:
        return JsonObject(self._object(key), self.path(key))

    def opt_obj(self, key: str) -> Optional[JsonObject]:
        fields = self._opt_object(key)
        return None if fields is None else JsonObject(fields, self.path(key))

    def obj_tuple(self, key: str, *, required: bool = False) -> Tuple[JsonObject, ...]:
        """An array of objects (missing or null reads empty unless required)."""
        return tuple(
            JsonObject.of(item, f"{self.path(key)}[{index}]")
            for index, item in enumerate(self._array(key, required=required))
        )

    def obj_map(self, key: str) -> Dict[str, JsonObject]:
        """An object of objects (missing or null reads empty)."""
        fields = self._opt_object(key)
        return {name: JsonObject.of(item, f"{self.path(key)}.{name}") for name, item in (fields or {}).items()}
