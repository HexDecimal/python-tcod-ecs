# ruff: noqa: D100 D103 ANN401
from __future__ import annotations

from typing import Any, Final

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


def test_component_names() -> None:
    world = tcod.ecs.World()
    entity = world.new_entity()
    entity.components[("name", str)] = "name"
    entity.components[("foo", str)] = "foo"
    assert entity.components[("name", str)] == "name"
    assert ("name", str) in entity.components
    assert ("name", int) not in entity.components
    assert set(world.Q[tcod.ecs.Entity, ("name", str), ("foo", str)]) == {(entity, "name", "foo")}


def test_relations() -> None:
    ChildOf: Final = "ChildOf"
    world = tcod.ecs.World()
    entity_a = world.new_entity(name="A")
    entity_b = world.new_entity(name="B")
    entity_b.relations[ChildOf] = entity_a
    entity_c = world.new_entity(name="C")
    entity_c.relations[ChildOf] = entity_a
    entity_d = world.new_entity(name="D")
    entity_d.relations[ChildOf] = entity_b
    assert set(world.Q.all_of(relations=[(ChildOf, entity_a)])) == {entity_b, entity_c}
    assert set(world.Q.all_of(relations=[(ChildOf, None)])) == {entity_b, entity_c, entity_d}
    assert set(world.Q.all_of(relations=[(ChildOf, entity_d)])) == set()
    assert set(world.Q.all_of(relations=[(ChildOf, None)]).none_of(relations=[(ChildOf, entity_a)])) == {entity_d}
    assert entity_a in entity_b.relations_many[ChildOf]
    assert entity_a == entity_b.relations[ChildOf]
    for e in world.Q.all_of(relations=[(ChildOf, None)]):
        e.relations.clear()
    assert not set(world.Q.all_of(relations=[(ChildOf, None)]))


def test_relations_many() -> None:
    world = tcod.ecs.World()
    entity_a = world.new_entity(name="A")
    entity_b = world.new_entity(name="B")
    entity_c = world.new_entity(name="C")

    with pytest.raises(KeyError):
        entity_a.relations["foo"]
    entity_a.relations_many["foo"] = (entity_b, entity_c)
    with pytest.raises(ValueError, match=r"Entity relation has multiple targets but an exclusive value was expected\."):
        entity_a.relations["foo"]


def test_naming() -> None:
    world = tcod.ecs.World()
    entity_a = world.new_entity(name="A")
    assert entity_a.name == "A"
    assert world.named["A"] is entity_a
    entity_a2 = world.new_entity(name="A")
    assert world.named["A"] is entity_a2
    assert entity_a.name is None
    entity_a2.name = None
    assert entity_a2.name is None
    assert world.named.get("A") is None


def test_component_missing(benchmark: Any) -> None:
    entity = tcod.ecs.World().new_entity()
    benchmark(lambda: entity.components.get(str))


def test_component_assign(benchmark: Any) -> None:
    entity = tcod.ecs.World().new_entity()

    @benchmark  # type: ignore[misc]
    def _() -> None:
        entity.components[str] = "value"


def test_component_found(benchmark: Any) -> None:
    entity = tcod.ecs.World().new_entity()
    entity.components[str] = "value"
    benchmark(lambda: entity.components[str])


def test_tag_missing(benchmark: Any) -> None:
    entity = tcod.ecs.World().new_entity()
    benchmark(lambda: "value" in entity.tags)


def test_tag_assign(benchmark: Any) -> None:
    entity = tcod.ecs.World().new_entity()
    benchmark(lambda: entity.tags.add("value"))


def test_tag_found(benchmark: Any) -> None:
    entity = tcod.ecs.World().new_entity()
    benchmark(lambda: "value" in entity.tags)
