"""Trait definitions. These are used to indicate what an entity actually has.

Mostly private at the moment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

import attrs
from typing_extensions import Self, TypeForm, sentinel

if TYPE_CHECKING:
    from tcod.ecs.typing import ComponentKey

T = TypeVar("T")

_undefined = sentinel("_undefined")


@attrs.define(frozen=True, weakref_slot=False, kw_only=True)
class Component(Generic[T]):
    """A component or named component trait."""

    type: TypeForm[T]
    name: object = _undefined

    @classmethod
    def from_key(cls, key: ComponentKey[T], /) -> Self:
        """Return the trait for the given component key."""
        if isinstance(key, tuple):
            name, type_ = key
            return cls(name=name, type=type_)
        return cls(type=key)

    def _as_key(self) -> ComponentKey[T]:
        """Return this trait as a `ComponentKey`."""
        if self.name is _undefined:
            return self.type
        return self.name, self.type


@attrs.define(frozen=True, weakref_slot=False)
class Tag:
    """A tag trait."""

    tag: object


@attrs.define(frozen=True, weakref_slot=False)
class Relation(Generic[T]):
    """A relation trait for the sub-trait itself rather than any specific target."""

    trait: T

    def _get_alt(self: Relation[Component[object] | Tag]) -> Relation[Component[object] | Tag]:
        """Return a relation with the sub-trait swapped between Tag and Component traits."""
        if isinstance(self.trait, Tag):
            return Relation(Component(type=self.trait.tag))  # type: ignore[arg-type]
        assert isinstance(self.trait, Component)
        return Relation(Tag(self.trait._as_key()))
