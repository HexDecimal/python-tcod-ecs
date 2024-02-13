# ruff: noqa: D100 D103 ANN401
from typing import Any, Dict

import pytest

import tcod.ecs


@pytest.fixture(autouse=True)
def _add_world_entity(doctest_namespace: Dict[str, Any]) -> None:
    """Add world and entity objects to all doctests."""
    world = tcod.ecs.Registry()
    entity = world["entity"]
    other_entity = world["other"]
    doctest_namespace.update(
        {
            "tcod": tcod,
            "world": world,
            "entity": entity,
            "other_entity": other_entity,
        }
    )
