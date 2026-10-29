"""Trait definitions. These are used to indicate what an entity actually has.

Mostly private at the moment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

import attrs
from typing_extensions import Self, TypeForm, sentinel

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import EllipsisType

    from tcod.ecs.entity import Entity
    from tcod.ecs.query import BoundQuery
    from tcod.ecs.typing import ComponentKey, _RelationQuery

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
    target: Entity | EllipsisType | BoundQuery
    inverse: bool = False

    @classmethod
    def _from_query(cls, query: _RelationQuery, /) -> Self:
        trait: Any
        if len(query) == 2:  # noqa: PLR2004
            trait, target = query
            return cls(trait, target)
        target, trait, _ = query
        return cls(trait, target, inverse=True)

    def _expand_lookup(self: Relation[T]) -> Iterator[Relation[T]]:
        """Iterate over the variants of a common `Relation(trait, target)` trait."""
        assert self.target is not ...
        assert self.inverse is False
        yield self
        yield self.__class__(self.trait, ...)
        yield self.__class__(self.trait, self.target, inverse=True)
        yield self.__class__(self.trait, ..., inverse=True)

    def _get_alt(self: Relation[Component[object] | Tag]) -> Relation[Component[object] | Tag]:
        """Return a relation with the sub-trait swapped between Tag and Component traits."""
        if isinstance(self.trait, Tag):
            return Relation(Component(type=self.trait.tag), self.target, self.inverse)  # type: ignore[arg-type]
        assert isinstance(self.trait, Component)
        return Relation(Tag(self.trait._as_key()), self.target, self.inverse)
