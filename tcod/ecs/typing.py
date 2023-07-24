"""Common type-hints for tcod.ecs."""
from __future__ import annotations

import sys
import types
from typing import Any, Tuple, Type, TypeVar, Union

if sys.version_info >= (3, 10):  # pragma: no cover
    EllipsisType = types.EllipsisType
else:  # pragma: no cover
    EllipsisType = Any

T = TypeVar("T")

_ComponentKey = Union[Type[T], Tuple[object, Type[T]]]
"""ComponentKey is plain `type` or tuple `(tag, type)`."""
