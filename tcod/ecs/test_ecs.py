# ruff: noqa: D100 D103
from __future__ import annotations

from typing import Final

import pytest

import tcod.ecs


def test_world() -> None:
    world = tcod.ecs.World()
    entity = world.new_entity([1, "test"])
    assert entity.components[int] == 1
    assert str in entity.components
    del entity.components[str]
    assert set(world.Q.all_of({int})) == {entity}
    assert set(world.Q[tcod.ecs.Entity, int]) == {(entity, 1)}

    entity.tags.add("Hello")
    entity.tags.add("World")
    entity.tags.remove("World")
    assert "Hello" in entity.tags
    assert "missing" not in entity.tags
    assert set(world.Q.all_of({int}, tags={"Hello"})) == {entity}


def test_relations() -> None:
    ChildOf: Final = "ChildOf"
    world = tcod.ecs.World()
    entity_a = world.new_entity()
    entity_b = world.new_entity()
    entity_b.relations[ChildOf] = entity_a
    entity_c = world.new_entity()
    entity_c.relations[ChildOf] = entity_a
    entity_d = world.new_entity()
    entity_d.relations[ChildOf] = entity_b
    assert set(world.Q.all_of(relations=[(ChildOf, entity_a)])) == {entity_b, entity_c}
    assert set(world.Q.all_of(relations=[(ChildOf, None)])) == {entity_b, entity_c, entity_d}
    assert set(world.Q.all_of(relations=[(ChildOf, entity_d)])) == set()
    assert set(world.Q.all_of(relations=[(ChildOf, None)]).none_of(relations=[(ChildOf, entity_a)])) == {entity_d}


def test_relations_many() -> None:
    world = tcod.ecs.World()
    entity_a = world.new_entity()
    entity_b = world.new_entity()
    entity_c = world.new_entity()

    with pytest.raises(KeyError):
        entity_a.relations["foo"]
    entity_a.relations_many["foo"] = (entity_b, entity_c)
    with pytest.raises(ValueError, match=r"Entity relation has multiple targets but an exclusive value was expected\."):
        entity_a.relations["foo"]
