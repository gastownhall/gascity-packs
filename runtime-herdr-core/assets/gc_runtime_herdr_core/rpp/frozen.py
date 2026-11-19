"""Frozen value records, built without :mod:`dataclasses`.

``@frozen`` makes a class a frozen record, as ``@dataclass(frozen=True)``
does: an ``__init__`` taking its annotated fields in order (with defaults,
``field(default=...)`` and ``field(default_factory=...)``) that runs
``__post_init__`` when the class has one; ``__eq__`` and ``__hash__`` over
the field tuple (``NotImplemented`` against any other class); a ``repr`` of
``Name(a=..., b=...)``; ``__match_args__``; and assignment or deletion of an
attribute raises :class:`FrozenInstanceError`. :func:`replace` builds a new
record through ``__init__``, so its validation runs again.

Why not dataclasses: gc runs every op as a fresh process, which defines
every record class again. A frozen dataclass costs about a millisecond per
class to define on CPython 3.9-3.14 (an ``exec`` per generated method, and
``inspect.signature`` for a class without a docstring), and importing
:mod:`dataclasses` pulls in :mod:`inspect` and :mod:`ast`. ``@frozen`` runs
one ``exec`` per class, for ``__init__``; the other methods are shared.

It covers only what the runtime uses, and refuses the rest when the class
is defined: a base class other than ``object``, ``ClassVar`` or ``InitVar``
annotations, and a class that defines ``__init__``, ``__eq__``,
``__hash__``, ``__repr__``, ``__setattr__`` or ``__delattr__`` itself. A
non-default field after a default one is a ``TypeError`` and an unhashable
plain default a ``ValueError``, as in dataclasses.

Type checkers see :func:`frozen` as a ``dataclass_transform`` and
:func:`field` and :func:`replace` as dataclasses', so a record's fields,
constructor and ``replace`` calls are checked as a frozen dataclass's are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Final, List, Mapping, Optional, Tuple, TypeVar, cast

_C = TypeVar("_C", bound=type)
_T = TypeVar("_T")

FIELDS_ATTR: Final = "_frozen_fields"
"""The class attribute holding a record's field names, in order."""

_GENERATED: Final = ("__init__", "__eq__", "__hash__", "__repr__", "__setattr__", "__delattr__")
_SPECIAL_ANNOTATIONS: Final = ("ClassVar", "typing.ClassVar", "InitVar", "dataclasses.InitVar")
_RESERVED_PREFIX: Final = "_frozen_"


class FrozenInstanceError(AttributeError):
    """A field of a frozen record was assigned or deleted."""


class _Missing:
    """No default given."""


_MISSING: Final = _Missing()


class _Field:
    """What :func:`field` returns: a field's default or default factory."""

    __slots__ = ("default", "default_factory")

    def __init__(self, default: object, default_factory: object) -> None:
        self.default = default
        self.default_factory = default_factory


def _field(*, default: object = _MISSING, default_factory: object = _MISSING) -> object:
    if default is not _MISSING and default_factory is not _MISSING:
        raise ValueError("cannot specify both default and default_factory")
    return _Field(default, default_factory)


def _fields(obj: object) -> Tuple[str, ...]:
    found: object = getattr(type(obj), FIELDS_ATTR, None)
    if not isinstance(found, tuple):
        raise TypeError(f"{type(obj).__name__} is not a frozen record")
    return cast(Tuple[str, ...], found)


def _get(obj: object, name: str) -> object:
    """Field ``name`` of record ``obj``; a field never set raises
    :class:`AttributeError`, as in dataclasses."""
    value: object = getattr(obj, name)
    return value


def _attr_or_none(obj: object, name: str) -> object:
    value: object = getattr(obj, name, None)
    return value


def _values(obj: object) -> Tuple[object, ...]:
    return tuple(_get(obj, name) for name in _fields(obj))


def _replace(obj: _T, /, **changes: object) -> _T:
    values: Dict[str, object] = {name: _get(obj, name) for name in _fields(obj)}
    values.update(changes)
    made: _T = type(obj)(**values)
    return made


if TYPE_CHECKING:
    from dataclasses import field as field, replace as replace

    from typing_extensions import dataclass_transform  # a typeshed stub, never imported at run time
else:

    def dataclass_transform(**_: object):
        return lambda decorated: decorated

    field = _field
    replace = _replace


def _eq(self: object, other: object) -> bool:
    if other.__class__ is self.__class__:
        return _values(self) == _values(other)
    unrelated: bool = NotImplemented
    return unrelated


def _hash(self: object) -> int:
    return hash(_values(self))


def _repr(self: object) -> str:
    shown = ", ".join(f"{name}={_get(self, name)!r}" for name in _fields(self))
    return f"{self.__class__.__qualname__}({shown})"


def _setattr(self: object, name: str, value: object) -> None:
    raise FrozenInstanceError(f"cannot assign to field {name!r}")


def _delattr(self: object, name: str) -> None:
    raise FrozenInstanceError(f"cannot delete field {name!r}")


def _is_special(annotation: object) -> bool:
    """Whether ``annotation`` is a ``ClassVar`` or ``InitVar``, written as a
    string (postponed annotations) or as the object."""
    if isinstance(annotation, str):
        head = annotation.split("[", 1)[0].strip()
        return head in _SPECIAL_ANNOTATIONS
    origin = _attr_or_none(annotation, "__origin__")
    return any(_attr_or_none(x, "_name") == "ClassVar" for x in (annotation, origin)) or type(annotation).__name__ == "InitVar"


def _check_class(cls: type, own: Mapping[str, object]) -> Mapping[str, object]:
    if cls.__bases__ != (object,):
        raise TypeError(f"@frozen {cls.__name__}: a base class other than object is not supported")
    for name in _GENERATED:
        if name in own:
            raise TypeError(f"@frozen {cls.__name__}: defines {name} itself, which @frozen generates")
    annotations: Mapping[str, object] = getattr(cls, "__annotations__", {})  # the class's own: its base is object
    for name, annotation in annotations.items():
        if _is_special(annotation):
            raise TypeError(f"@frozen {cls.__name__}: field {name!r} is a ClassVar or InitVar, which @frozen does not support")
        if name == "self" or name.startswith(_RESERVED_PREFIX):
            raise TypeError(f"@frozen {cls.__name__}: field name {name!r} is reserved")
    return annotations


def _unhashable(value: object, name: str) -> None:
    if type(value).__hash__ is None:
        raise ValueError(f"mutable default {type(value)} for field {name} is not allowed: use default_factory")


def _init(cls: type, names: List[str], defaults: Mapping[str, object], factories: Mapping[str, object]) -> object:
    """The record's ``__init__``, from one ``exec``."""
    params: List[str] = []
    body: List[str] = []
    setter: object = object.__setattr__
    namespace: Dict[str, object] = {"_frozen_set": setter, "_frozen_factory": _MISSING}
    for name in names:
        if name in factories:
            params.append(f"{name}=_frozen_factory")
            namespace[f"_frozen_make_{name}"] = factories[name]
            body.append(f"_frozen_set(self, {name!r}, _frozen_make_{name}() if {name} is _frozen_factory else {name})")
        else:
            if name in defaults:
                params.append(f"{name}=_frozen_default_{name}")
                namespace[f"_frozen_default_{name}"] = defaults[name]
            else:
                params.append(name)
            body.append(f"_frozen_set(self, {name!r}, {name})")
    own: Mapping[str, object] = vars(cls)
    if "__post_init__" in own:
        body.append("self.__post_init__()")
    source = f"def __init__({', '.join(['self', *params])}):\n" + "".join(f"    {line}\n" for line in body or ["pass"])
    created: Dict[str, object] = {}
    exec(source, namespace, created)  # noqa: S102 - the source is built only from field names
    init = created["__init__"]
    setattr(init, "__qualname__", f"{cls.__qualname__}.__init__")
    setattr(init, "__module__", cls.__module__)
    return init


# dataclasses.field, which type checkers see here, is typed with Any.
@dataclass_transform(frozen_default=True, field_specifiers=(field,))  # type: ignore[misc]
def frozen(cls: _C) -> _C:
    """Make ``cls`` a frozen record (see the module docstring)."""
    view: Mapping[str, object] = vars(cls)
    own = dict(view)  # a copy: fields with a factory leave the class below
    annotations = _check_class(cls, own)
    names = list(annotations)
    defaults: Dict[str, object] = {}
    factories: Dict[str, object] = {}
    seen_default: Optional[str] = None
    for name in names:
        value = own.get(name, _MISSING)
        if isinstance(value, _Field):
            if value.default_factory is not _MISSING:
                factories[name] = value.default_factory
                delattr(cls, name)
            elif value.default is not _MISSING:
                _unhashable(value.default, name)
                defaults[name] = value.default
                setattr(cls, name, value.default)
            else:
                delattr(cls, name)
        elif value is not _MISSING:
            _unhashable(value, name)
            defaults[name] = value
        if name in defaults or name in factories:
            seen_default = name
        elif seen_default is not None:
            raise TypeError(f"non-default argument {name!r} follows default argument {seen_default!r}")
    fields: Tuple[str, ...] = tuple(names)
    setattr(cls, FIELDS_ATTR, fields)
    setattr(cls, "__match_args__", fields)
    setattr(cls, "__init__", _init(cls, names, defaults, factories))
    setattr(cls, "__eq__", _eq)
    setattr(cls, "__hash__", _hash)
    setattr(cls, "__repr__", _repr)
    setattr(cls, "__setattr__", _setattr)
    setattr(cls, "__delattr__", _delattr)
    return cls


__all__ = ["FrozenInstanceError", "field", "frozen", "replace"]
