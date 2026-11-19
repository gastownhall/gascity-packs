"""rpp.frozen behaves as ``@dataclasses.dataclass(frozen=True)`` does for the
shapes the runtime uses.

Every record class is defined in every op process, and a frozen dataclass
costs about a millisecond per class to define. ``@frozen`` builds the same
record: these tests pin it to dataclasses' behaviour twin by twin.
"""

from __future__ import annotations

import dataclasses
import functools
import sys
from typing import Callable, ClassVar, Dict, List, Mapping, Tuple

import pytest

from gc_runtime_herdr_core.rpp import frozen as fz
from gc_runtime_herdr_core.rpp.frozen import FrozenInstanceError, field, frozen, replace


def _home() -> str:
    return "/home/x"


class Invalid(ValueError):
    pass


# --- twins ------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DPlain:
    a: int
    b: str = "b"
    c: Tuple[str, ...] = ()


@frozen
class FPlain:
    a: int
    b: str = "b"
    c: Tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class DFields:
    name: str
    values: Mapping[str, str] = dataclasses.field(default_factory=dict)
    emit: Callable[[], int] = dataclasses.field(default=lambda: 7)
    home: Callable[[], str] = _home


@frozen
class FFields:
    name: str
    values: Mapping[str, str] = field(default_factory=dict)
    emit: Callable[[], int] = field(default=lambda: 7)
    home: Callable[[], str] = _home


@dataclasses.dataclass(frozen=True)
class DPost:
    id: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise Invalid("blank id")


@frozen
class FPost:
    id: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise Invalid("blank id")


@functools.total_ordering
@dataclasses.dataclass(frozen=True, eq=True)
class DOrdered:
    major: int
    minor: int = 0

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, DOrdered):
            return NotImplemented
        return (self.major, self.minor) < (other.major, other.minor)


@functools.total_ordering
@frozen
class FOrdered:
    major: int
    minor: int = 0

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, FOrdered):
            return NotImplemented
        return (self.major, self.minor) < (other.major, other.minor)


def _without_name(text: str, *names: str) -> str:
    for name in names:
        text = text.replace(name, "X")
    return text


# --- construction -----------------------------------------------------------------------


def test_positional_and_keyword_construction() -> None:
    assert FPlain(1, "x", ("y",)) == FPlain(a=1, b="x", c=("y",))
    made = FPlain(1)
    assert (made.a, made.b, made.c) == (1, "b", ())
    twin = DPlain(1)
    assert (twin.a, twin.b, twin.c) == (made.a, made.b, made.c)


def test_defaults_and_fresh_factory_values() -> None:
    one, two = FFields("a"), FFields("b")
    assert one.values == {} and one.values is not two.values
    assert one.emit() == 7 and one.home() == "/home/x"
    assert FFields.home is _home  # a plain default stays a class attribute, as in dataclasses
    assert DFields.home is _home
    assert not hasattr(FFields, "values") and not hasattr(DFields, "values")
    assert FFields.emit() == DFields.emit() == 7  # field(default=...) becomes the class attribute


def test_post_init_runs_and_its_exception_propagates() -> None:
    assert FPost("x").id == "x"
    with pytest.raises(Invalid, match="blank id"):
        FPost(" ")
    with pytest.raises(Invalid, match="blank id"):
        DPost(" ")


@pytest.mark.parametrize(
    "args, kwargs",
    [
        ((), {}),  # missing
        ((1, "b", (), 4), {}),  # extra
        ((1,), {"bogus": 1}),  # unknown
        ((1,), {"a": 2}),  # twice
    ],
)
def test_argument_errors_match_dataclasses(args: Tuple[object, ...], kwargs: Dict[str, object]) -> None:
    with pytest.raises(TypeError) as ours:
        FPlain(*args, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(TypeError) as theirs:
        DPlain(*args, **kwargs)  # type: ignore[arg-type]
    assert _without_name(str(ours.value), "FPlain") == _without_name(str(theirs.value), "DPlain")


# --- value semantics ----------------------------------------------------------------------


def test_equality() -> None:
    assert FPlain(1) == FPlain(1, "b", ())
    assert FPlain(1) != FPlain(2)
    assert not (FPlain(1) != FPlain(1))
    twin: object = DPlain(1)
    as_tuple: object = (1, "b", ())
    assert FPlain(1).__eq__(twin) is NotImplemented
    assert FPlain(1) != twin
    assert FPlain(1) != as_tuple
    assert FPlain(1).__eq__((1, "b", ())) is NotImplemented
    assert twin != FPlain(1)


def test_hash_is_the_field_tuples() -> None:
    assert hash(FPlain(1, "x", ("y",))) == hash((1, "x", ("y",))) == hash(DPlain(1, "x", ("y",)))
    assert {FPlain(1): "v"}[FPlain(1)] == "v"
    assert len({FPlain(1), FPlain(1), FPlain(2)}) == 2


def test_repr() -> None:
    ours = repr(FPlain(1, "x", ("y",)))
    theirs = repr(DPlain(1, "x", ("y",)))
    assert ours == "FPlain(a=1, b='x', c=('y',))"
    assert _without_name(ours, "FPlain") == _without_name(theirs, "DPlain")


def test_instances_are_frozen() -> None:
    made = FPlain(1)
    with pytest.raises(FrozenInstanceError, match="cannot assign to field 'a'"):
        made.a = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError, match="cannot delete field 'a'"):
        del made.a
    with pytest.raises(AttributeError):
        made.other = 3  # type: ignore[attr-defined]
    assert issubclass(FrozenInstanceError, AttributeError)
    assert made.a == 1 and not hasattr(made, "other")


def test_match_args() -> None:
    assert getattr(FPlain, "__match_args__") == ("a", "b", "c")
    if sys.version_info >= (3, 10):  # dataclasses sets it from 3.10
        assert getattr(DPlain, "__match_args__") == ("a", "b", "c")


def test_total_ordering() -> None:
    assert FOrdered(1) < FOrdered(1, 1) < FOrdered(2)
    assert FOrdered(2) >= FOrdered(1, 9)
    assert sorted([FOrdered(2), FOrdered(1, 1), FOrdered(1)]) == [FOrdered(1), FOrdered(1, 1), FOrdered(2)]
    assert [d.major for d in sorted([DOrdered(2), DOrdered(1)])] == [1, 2]
    assert FOrdered(1) == FOrdered(1, 0)


@pytest.mark.parametrize(
    "use",
    [
        repr,
        hash,
        lambda made: made == object.__new__(type(made)),
        lambda made: (dataclasses.replace if dataclasses.is_dataclass(made) else replace)(made),
    ],
    ids=["repr", "hash", "eq", "replace"],
)
def test_a_half_built_record_raises_as_dataclasses_do(use: Callable[[object], object]) -> None:
    # A record whose __init__ never ran has no field values: reading them
    # raises rather than treating a missing field as None.
    for cls in (FPlain, DPlain):
        with pytest.raises(AttributeError):
            use(object.__new__(cls))


# --- replace ------------------------------------------------------------------------------


def test_replace_builds_a_new_instance() -> None:
    made = FPlain(1, "x")
    changed = replace(made, b="y")
    assert changed == FPlain(1, "y") and made == FPlain(1, "x") and changed is not made
    fresh = replace(FFields("a", values={"k": "v"}), name="b")
    assert fresh.values == {"k": "v"}


def test_replace_runs_post_init_again() -> None:
    with pytest.raises(Invalid):
        replace(FPost("x"), id=" ")


def test_replace_refuses_unknown_names() -> None:
    with pytest.raises(TypeError):
        replace(FPlain(1), bogus=1)  # type: ignore[call-arg]


def test_replace_refuses_a_non_record() -> None:
    with pytest.raises(TypeError):
        fz._replace(object())


# --- refusals at decoration -------------------------------------------------------------------


def test_non_default_after_default() -> None:
    with pytest.raises(TypeError, match="non-default argument 'b' follows default argument"):

        @frozen
        class Bad:
            a: int = 1
            b: int  # type: ignore[misc]

    with pytest.raises(TypeError, match="non-default argument 'b' follows default argument"):

        @dataclasses.dataclass(frozen=True)
        class Twin:
            a: int = 1
            b: int  # type: ignore[misc]


@pytest.mark.parametrize("default", [[], {}, set()])
def test_unhashable_plain_default(default: object) -> None:
    with pytest.raises(ValueError, match="use default_factory"):
        frozen(type("Bad", (), {"__annotations__": {"a": "object"}, "a": default}))
    with pytest.raises(ValueError, match="use default_factory"):
        dataclasses.dataclass(frozen=True)(type("Twin", (), {"__annotations__": {"a": "object"}, "a": default}))


def test_unhashable_field_default() -> None:
    with pytest.raises(ValueError, match="use default_factory"):
        frozen(type("Bad", (), {"__annotations__": {"a": "object"}, "a": field(default=[])}))


def test_a_base_class_is_refused() -> None:
    with pytest.raises(TypeError, match="base class"):

        @frozen
        class Child(FPlain):
            d: int = 0


@pytest.mark.parametrize("annotation", ["ClassVar[int]", "typing.ClassVar[int]", "InitVar[int]", "dataclasses.InitVar[int]", ClassVar[int], dataclasses.InitVar(int)])
def test_classvar_and_initvar_are_refused(annotation: object) -> None:
    with pytest.raises(TypeError, match="ClassVar or InitVar"):
        frozen(type("Bad", (), {"__annotations__": {"a": annotation}}))


@pytest.mark.parametrize("method", ["__init__", "__eq__", "__hash__", "__repr__", "__setattr__", "__delattr__"])
def test_a_class_defining_a_generated_method_is_refused(method: str) -> None:
    def own(self: object, *args: object) -> None:
        return None

    with pytest.raises(TypeError, match=method):
        frozen(type("Bad", (), {"__annotations__": {"a": "int"}, method: own}))


def test_a_class_without_fields() -> None:
    @frozen
    class Empty:
        pass

    assert Empty() == Empty() and repr(Empty()) == "test_a_class_without_fields.<locals>.Empty()"
    assert hash(Empty()) == hash(())


def test_a_mutable_field_value_stays_shared_by_reference() -> None:
    # Frozen means the fields are not reassigned; a list field's contents can
    # still change (lifecycle's refusals append to theirs), as with dataclasses.
    @frozen
    class Bag:
        items: List[str]

    bag = Bag([])
    bag.items.append("x")
    assert bag.items == ["x"]
