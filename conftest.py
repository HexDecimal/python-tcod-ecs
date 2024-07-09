# ruff: noqa: D100 D103 ANN401
from __future__ import annotations

from typing import Any

import pytest

import tcod.ecs


@pytest.fixture(autouse=True)
def _add_registry_entity(doctest_namespace: dict[str, Any]) -> None:
    """Add registry and entity objects to all doctests."""
    registry = tcod.ecs.Registry()
    entity = registry["entity"]
    other_entity = registry["other"]
    doctest_namespace.update(
        {
            "tcod": tcod,
            "registry": registry,
            "entity": entity,
            "other_entity": other_entity,
        }
    )
