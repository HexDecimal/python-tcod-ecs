"""A type-hinted Entity Component System based on Python dictionaries and sets."""

from __future__ import annotations

import importlib.metadata
from collections import defaultdict
from typing import TypeVar

from tcod.ecs.constants import IsA
from tcod.ecs.entity import Entity
from tcod.ecs.registry import Registry
from tcod.ecs.registry import Registry as World

__all__ = (
    "Entity",
    "IsA",
    "Registry",
    "World",
)

try:
    __version__ = importlib.metadata.version("tcod-ecs")
except importlib.metadata.PackageNotFoundError:
    __version__ = ""


_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")


def _defaultdict_of_set() -> defaultdict[_T1, set[_T2]]:  # Migrate from <=3.4
    """Return a new defaultdict of sets."""
    return defaultdict(set)


def _defaultdict_of_dict() -> defaultdict[_T1, dict[_T2, _T3]]:  # Migrate from <=3.4
    """Return a new defaultdict of dicts."""
    return defaultdict(dict)
