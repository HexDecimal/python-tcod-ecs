"""Tests for entity relations."""
from __future__ import annotations

from typing import Final

import tcod.ecs

# ruff: noqa: D103

ChildOf: Final = "ChildOf"


def test_conditional_relations() -> None:
    world = tcod.ecs.World()
    world["A"].relation_tag[ChildOf] = world["B"]
    has_int_query = world.Q.all_of(components=[int])
    assert not set(world.Q.all_of(relations=[(ChildOf, has_int_query)]))
    assert not set(world.Q.all_of(relations=[(has_int_query, ChildOf, None)]))
    world["B"].components[int] = 42
    assert set(world.Q.all_of(relations=[(ChildOf, has_int_query)])) == {world["A"]}
    assert not set(world.Q.all_of(relations=[(has_int_query, ChildOf, None)]))
    del world["B"].components[int]
    assert not set(world.Q.all_of(relations=[(ChildOf, has_int_query)]))
    assert not set(world.Q.all_of(relations=[(has_int_query, ChildOf, None)]))
