"""Trait definitions. These are used to indicate what an entity actually has.

Mostly private at the moment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

import attrs
from typing_extensions import Self, TypeForm, sentinel

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from types import EllipsisType

    from tcod.ecs.entity import Entity
    from tcod.ecs.query import BoundQuery
    from tcod.ecs.typing import ComponentKey, _RelationQuery, _Trait

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
    """The trait for this relation which could be Tag or Relation or a plain key."""
    target: Entity | EllipsisType | BoundQuery
    """The target of this relation.

    Can be a specific entity, a wildcard, or a query.
    """
    inverse: bool = False
    """If True then the target refers to the relations origin instead."""

    @classmethod
    def _from_query(cls, query: _RelationQuery, /) -> Self:
        """Return a Relation from a query-like relation tuple."""
        trait: Any
        if len(query) == 2:  # noqa: PLR2004
            trait, target = query
            return cls(trait, target)
        target, trait, _ = query
        return cls(trait, target, inverse=True)

    def _as_query(self) -> _RelationQuery:
        if self.inverse:
            return (self.target, self.trait, None)
        return (self.trait, self.target)

    def _get_alt(self: Relation[Component[object] | Tag]) -> Relation[Component[object] | Tag] | None:
        """Return a relation with the sub-trait swapped between Tag and Component traits."""
        if isinstance(self.trait, Tag):
            if isinstance(self.trait.tag, tuple) and len(self.trait.tag) != 2:  # noqa: PLR2004
                return None  # Tag not convertible to a Component
            return Relation(Component.from_key(self.trait.tag), self.target, self.inverse)  # type: ignore[arg-type]
        assert isinstance(self.trait, Component)
        return Relation(Tag(self.trait._as_key()), self.target, self.inverse)


def traits_from_query(
    *,
    components: Iterable[ComponentKey[object]] = (),
    tags: Iterable[object] = (),
    relations: Iterable[_RelationQuery] = (),
) -> Iterator[_Trait]:
    """Iterate over the traits derived from a query."""
    for component in components:
        yield Component.from_key(component)
    for tag in tags:
        yield Tag(tag)
    for relation in relations:
        yield Relation._from_query(relation)
