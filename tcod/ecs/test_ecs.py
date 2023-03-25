# ruff: noqa: D100 D103
from __future__ import annotations

from typing import Final

import tcod.ecs


def test_world() -> None:
    world = tcod.ecs.World()
    entity = world.new_entity([1, "test"])
    assert entity.components[int] == 1
    assert str in entity.components
    del entity.components[str]
    assert set(tcod.ecs.Query(world).all_of({int})) == {entity}
    assert set(tcod.ecs.Query(world)[tcod.ecs.Entity, int]) == {(entity, 1)}

    entity.tags.add("Hello")
    entity.tags.add("World")
    entity.tags.remove("World")
    assert "Hello" in entity.tags
    assert "missing" not in entity.tags
    assert set(tcod.ecs.Query(world).all_of({int}, tags={"Hello"})) == {entity}


def test_relations() -> None:
    ChildOf: Final = "ChildOf"
    world = tcod.ecs.World()
    entity_a = world.new_entity()
    entity_b = world.new_entity()
    entity_b.relations[ChildOf].add(entity_a)
    entity_c = world.new_entity()
    entity_c.relations[ChildOf].add(entity_a)
    entity_d = world.new_entity()
    entity_d.relations[ChildOf].add(entity_b)
    assert set(tcod.ecs.Query(world).all_of(relations=[(ChildOf, entity_a)])) == {entity_b, entity_c}
    assert set(tcod.ecs.Query(world).all_of(relations=[(ChildOf, None)])) == {entity_b, entity_c, entity_d}
    assert set(tcod.ecs.Query(world).all_of(relations=[(ChildOf, entity_d)])) == set()
    assert set(tcod.ecs.Query(world).all_of(relations=[(ChildOf, None)]).none_of(relations=[(ChildOf, entity_a)])) == {
        entity_d
    }
