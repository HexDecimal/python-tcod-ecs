"""Common type-hints for tcod.ecs."""
from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING, Any, Tuple, Type, TypeVar, Union

from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from tcod.ecs.entity import Entity
else:
    Entity = Any

if sys.version_info >= (3, 10):  # pragma: no cover
    EllipsisType: TypeAlias = types.EllipsisType
else:  # pragma: no cover
    EllipsisType = Any

T = TypeVar("T")

_ComponentKey: TypeAlias = Union[Type[T], Tuple[object, Type[T]]]
"""ComponentKey is plain `type` or tuple `(tag, type)`."""

_RelationTarget: TypeAlias = Union[Entity, EllipsisType]
"""Possible target for relation queries."""

_RelationQuery: TypeAlias = Union[Tuple[object, _RelationTarget], Tuple[_RelationTarget, object, None]]
"""Query format for relations.

One of 4 formats:

* (tag, target)
* (tag, ...)
* (origin, tag, None)
* (..., tag, None)
"""
