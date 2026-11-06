"""Common type-hints for tcod.ecs."""

from __future__ import annotations

from types import EllipsisType
from typing import TYPE_CHECKING, Any

from typing_extensions import TypeForm

if TYPE_CHECKING:
    from tcod.ecs.entity import Entity
    from tcod.ecs.query import BoundQuery
    from tcod.ecs.traits import Component, Relation, Tag


type ComponentKey[T] = TypeForm[T] | tuple[object, TypeForm[T]]
"""ComponentKey is plain `type` or tuple `(tag, type)`."""

type _RelationTargetLookup = Entity | EllipsisType
"""Possible target for stored relations."""

type _RelationQueryTarget = _RelationTargetLookup | BoundQuery
"""Possible target for relation queries."""

type _RelationQuery = tuple[object, _RelationQueryTarget] | tuple[_RelationQueryTarget, object, None]  # noqa: PYI047
"""Query format for relations.

One of 4 formats:

* (tag, target)
* (tag, ...)
* (origin, tag, None)
* (..., tag, None)
"""

type _Trait = Component[Any] | Tag | Relation[Any]  # noqa: PYI047
"""Available trait objects."""
