"""Common type-hints for tcod.ecs."""

from __future__ import annotations

from types import EllipsisType
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar

from typing_extensions import TypeForm

if TYPE_CHECKING:
    from tcod.ecs.entity import Entity
    from tcod.ecs.query import BoundQuery
else:
    Entity = Any
    BoundQuery = Any


_T = TypeVar("_T")

ComponentKey: TypeAlias = TypeForm[_T] | tuple[object, TypeForm[_T]]
"""ComponentKey is plain `type` or tuple `(tag, type)`."""

_RelationTargetLookup: TypeAlias = Entity | EllipsisType
"""Possible target for stored relations."""

_RelationQueryTarget: TypeAlias = _RelationTargetLookup | BoundQuery
"""Possible target for relation queries."""

_RelationQuery: TypeAlias = tuple[object, _RelationQueryTarget] | tuple[_RelationQueryTarget, object, None]  # noqa: PYI047
"""Query format for relations.

One of 4 formats:

* (tag, target)
* (tag, ...)
* (origin, tag, None)
* (..., tag, None)
"""
