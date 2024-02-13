"""Tests for entity relations."""
from __future__ import annotations

from typing import Final

import pytest

import tcod.ecs

# ruff: noqa: D103

ChildOf: Final = "ChildOf"


def test_relations() -> None:
    world = tcod.ecs.Registry()
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
    world = tcod.ecs.Registry()
    with pytest.warns(FutureWarning):
        world[None].relation_tags["Foo"] = world[None]


def test_relations_many() -> None:
    world = tcod.ecs.Registry()
    entity_a = world["A"]
    entity_b = world["B"]
    entity_c = world["C"]

    with pytest.raises(KeyError):
        entity_a.relation_tag["foo"]
    with pytest.raises(KeyError):
        entity_a.relation_tags_many["foo"].remove(entity_a)
    assert entity_a not in entity_a.relation_tags_many["foo"]

    entity_a.relation_tags_many["foo"] = (entity_b, entity_c)
    with pytest.raises(ValueError, match=r"Entity relation has multiple targets but an exclusive value was expected\."):
        entity_a.relation_tag["foo"]


def test_relation_components() -> None:
    world = tcod.ecs.Registry()
    entity_a = world["A"]
    entity_b = world["B"]

    with pytest.raises(KeyError):
        entity_b.relation_components[int][entity_a]

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
    world = tcod.ecs.Registry()
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


def test_relation_component_tables() -> None:
    w = tcod.ecs.Registry()
    e1 = w["e1"]
    e2 = w["e2"]
    e3 = w["e3"]

    assert not set(w.Q.all_of(relations=[(int, e2)]))
    e1.relation_components[int][e2] = 1
    assert set(w.Q.all_of(relations=[(int, e2)])) == {e1}
    e3.relation_components[int][e2] = 2
    assert set(w.Q.all_of(relations=[(int, e2)])) == {e1, e3}
    assert set(w.Q.all_of(relations=[(int, ...)])) == {e1, e3}
    assert set(w.Q.all_of(relations=[(..., int, None)])) == {e2}
    assert set(w.Q.all_of(relations=[(e1, int, None)])) == {e2}
    assert set(w.Q.all_of(relations=[(e3, int, None)])) == {e2}

    e3.relation_components[int][e1] = 3
    assert set(w.Q.all_of(relations=[(e3, int, None)])) == {e1, e2}
    assert set(w.Q.all_of(relations=[(..., int, None)])) == {e1, e2}
    assert set(w.Q.all_of(relations=[(int, ...)])) == {e1, e3}

    del e3.relation_components[int][e1]
    assert set(w.Q.all_of(relations=[(e3, int, None)])) == {e2}
    assert set(w.Q.all_of(relations=[(..., int, None)])) == {e2}
    assert set(w.Q.all_of(relations=[(int, ...)])) == {e1, e3}

    del e3.relation_components[int][e2]
    assert set(w.Q.all_of(relations=[(..., int, None)])) == {e2}
    assert set(w.Q.all_of(relations=[(e1, int, None)])) == {e2}
    assert not set(w.Q.all_of(relations=[(e3, int, None)]))


def test_relation_tag_tables() -> None:
    w = tcod.ecs.Registry()
    e1 = w["e1"]
    e2 = w["e2"]
    e3 = w["e3"]

    assert not set(w.Q.all_of(relations=[("tag", e2)]))
    e1.relation_tag["tag"] = e2
    assert set(w.Q.all_of(relations=[("tag", e2)])) == {e1}
    e3.relation_tag["tag"] = e2
    assert set(w.Q.all_of(relations=[("tag", e2)])) == {e1, e3}
    assert set(w.Q.all_of(relations=[("tag", ...)])) == {e1, e3}
    assert set(w.Q.all_of(relations=[(..., "tag", None)])) == {e2}
    assert set(w.Q.all_of(relations=[(e1, "tag", None)])) == {e2}
    assert set(w.Q.all_of(relations=[(e3, "tag", None)])) == {e2}

    e3.relation_tags_many["tag"].add(e1)
    assert set(w.Q.all_of(relations=[(e3, "tag", None)])) == {e1, e2}
    assert set(w.Q.all_of(relations=[(..., "tag", None)])) == {e1, e2}
    assert set(w.Q.all_of(relations=[("tag", ...)])) == {e1, e3}

    e3.relation_tags_many["tag"].discard(e1)
    assert set(w.Q.all_of(relations=[(e3, "tag", None)])) == {e2}
    assert set(w.Q.all_of(relations=[(..., "tag", None)])) == {e2}
    assert set(w.Q.all_of(relations=[("tag", ...)])) == {e1, e3}

    del e3.relation_tag["tag"]
    assert set(w.Q.all_of(relations=[(..., "tag", None)])) == {e2}
    assert set(w.Q.all_of(relations=[(e1, "tag", None)])) == {e2}
    assert not set(w.Q.all_of(relations=[(e3, "tag", None)]))
