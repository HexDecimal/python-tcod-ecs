"""A type-hinted Entity Component System based on Python dictionaries and sets."""

from __future__ import annotations

import importlib.metadata
from collections import defaultdict
from typing import TYPE_CHECKING

from tcod.ecs.constants import IsA
from tcod.ecs.entity import Entity
from tcod.ecs.registry import Registry

if TYPE_CHECKING:
    from typing_extensions import deprecated

    @deprecated("Renamed to Registry.")
    class World(Registry):  # noqa: D101
        pass

else:
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


def _defaultdict_of_set[T1, T2]() -> defaultdict[T1, set[T2]]:  # Migrate from <=3.4
    """Return a new defaultdict of sets."""
    return defaultdict(set)


def _defaultdict_of_dict[T1, T2, T3]() -> defaultdict[T1, dict[T2, T3]]:  # Migrate from <=3.4
    """Return a new defaultdict of dicts."""
    return defaultdict(dict)
