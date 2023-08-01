"""Tests for entity relations."""
from __future__ import annotations

from typing import Final

import pytest

import tcod.ecs

# ruff: noqa: D103

ChildOf: Final = "ChildOf"


def test_relations() -> None:
    world = tcod.ecs.World()
    entity_a = world["A"]
    entity_b = world["B"]
    entity_b.relation_tag[ChildOf] = entity_a
    entity_c = world["C"]
    assert len(entity_c.relation_tag) == 0
    entity_c.relation_tag[ChildOf] = entity_a
    assert len(entity_c.relation_tag) == 1
    entity_d = world["D"]
    entity_d.relation_tag[ChildOf] = entity_b
    assert set(world.Q.all_of(relations=[(ChildOf, entity_a)])) == {entity_b, entity_c}
    assert set(world.Q.all_of(relations=[(ChildOf, ...)])) == {entity_b, entity_c, entity_d}
    assert set(world.Q.all_of(relations=[(ChildOf, entity_d)])) == set()
    assert set(world.Q.all_of(relations=[(ChildOf, ...)]).none_of(relations=[(ChildOf, entity_a)])) == {entity_d}
    assert entity_a in entity_b.relation_tags_many[ChildOf]
    assert entity_a == entity_b.relation_tag[ChildOf]
    for e in world.Q.all_of(relations=[(ChildOf, ...)]):
        e.relation_tag.clear()
    assert not set(world.Q.all_of(relations=[(ChildOf, ...)]))

    del entity_c.relation_tags_many[ChildOf]


def test_relations_old() -> None:
    world = tcod.ecs.World()
    with pytest.warns(FutureWarning):
        world[None].relation_tags["Foo"] = world[None]


def test_relations_many() -> None:
    world = tcod.ecs.World()
    entity_a = world["A"]
    entity_b = world["B"]
    entity_c = world["C"]

    with pytest.raises(KeyError):
        entity_a.relation_tag["foo"]
    entity_a.relation_tags_many["foo"] = (entity_b, entity_c)
    with pytest.raises(ValueError, match=r"Entity relation has multiple targets but an exclusive value was expected\."):
        entity_a.relation_tag["foo"]


def test_relation_components() -> None:
    world = tcod.ecs.World()
    entity_a = world["A"]
    entity_b = world["B"]

    entity_b.relation_components[int][entity_a] = 1
    assert entity_b.relation_components[int][entity_a] == 1
    del entity_b.relation_components[int][entity_a]

    entity_b.relation_components[("named", int)][entity_a] = 0
    assert entity_b.relation_components[("named", int)][entity_a] == 0

    assert ("named", int) in entity_b.relation_components
    assert len(entity_b.relation_components) == 1
    del entity_b.relation_components[("named", int)]
    assert ("named", int) not in entity_b.relation_components

    entity_a.relation_components[int] = {world[1]: 1, world[2]: 2}
    entity_a.relation_components[int] = entity_a.relation_components[int]
    entity_a.relation_components[int][world[1]] = 1

    assert set(world.Q.all_of(relations=[(int, world[1])])) == {entity_a}

    entity_a.relation_components.clear()

    assert not set(world.Q.all_of(relations=[(int, world[1])]))


def test_conditional_relations() -> None:
    world = tcod.ecs.World()
    world["A"].relation_tag[ChildOf] = world["B"]
    world["C"].components[int] = 42
    has_int_query = world.Q.all_of(components=[int])
    assert not set(world.Q.all_of(relations=[(ChildOf, has_int_query)]))
    assert not set(world.Q.all_of(relations=[(has_int_query, ChildOf, None)]))
    world["B"].components[int] = 42
    assert set(world.Q.all_of(relations=[(ChildOf, has_int_query)])) == {world["A"]}
    assert not set(world.Q.all_of(relations=[(has_int_query, ChildOf, None)]))
    del world["B"].components[int]
    assert not set(world.Q.all_of(relations=[(ChildOf, has_int_query)]))
    assert not set(world.Q.all_of(relations=[(has_int_query, ChildOf, None)]))
