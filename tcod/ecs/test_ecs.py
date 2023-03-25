# ruff: noqa: D100 D103
from __future__ import annotations

import tcod.ecs


def test_world() -> None:
    world = tcod.ecs.World()
    entity = world.new_entity([1, "test"])
    assert entity.components[int] == 1
    assert str in entity.components
    del entity.components[str]
    assert set(tcod.ecs.Query(world).all_of_components(int)) == {entity}

    entity.tags.add("Hello")
    entity.tags.add("World")
    entity.tags.remove("World")
    assert "Hello" in entity.tags
    assert "missing" not in entity.tags
    assert set(tcod.ecs.Query(world).all_of_components(int).all_of_tags("Hello")) == {entity}
