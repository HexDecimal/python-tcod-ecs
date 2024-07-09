"""Common type-hints for tcod.ecs."""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING, Any, Tuple, Type, TypeVar, Union

from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from tcod.ecs.entity import Entity
    from tcod.ecs.query import BoundQuery
else:
    Entity = Any
    BoundQuery = Any

if sys.version_info >= (3, 10):  # pragma: no cover
    EllipsisType: TypeAlias = types.EllipsisType
else:  # pragma: no cover
    EllipsisType = Any

_T = TypeVar("_T")

ComponentKey: TypeAlias = Union[Type[_T], Tuple[object, Type[_T]]]
"""ComponentKey is plain `type` or tuple `(tag, type)`."""

_RelationTargetLookup: TypeAlias = Union[Entity, EllipsisType]
"""Possible target for stored relations."""

_RelationQueryTarget: TypeAlias = Union[_RelationTargetLookup, BoundQuery]
"""Possible target for relation queries."""

_RelationQuery: TypeAlias = Union[Tuple[object, _RelationQueryTarget], Tuple[_RelationQueryTarget, object, None]]  # noqa: PYI047
"""Query format for relations.

One of 4 formats:

* (tag, target)
* (tag, ...)
* (origin, tag, None)
* (..., tag, None)
"""
