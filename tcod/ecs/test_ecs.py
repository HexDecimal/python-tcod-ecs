# ruff: noqa: D100 D103 ANN401 S301
from __future__ import annotations

import pickle
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
    entity_b.relation_tags[ChildOf] = entity_a
    entity_c = world.new_entity(name="C")
    entity_c.relation_tags[ChildOf] = entity_a
    entity_d = world.new_entity(name="D")
    entity_d.relation_tags[ChildOf] = entity_b
    assert set(world.Q.all_of(relations=[(ChildOf, entity_a)])) == {entity_b, entity_c}
    assert set(world.Q.all_of(relations=[(ChildOf, ...)])) == {entity_b, entity_c, entity_d}
    assert set(world.Q.all_of(relations=[(ChildOf, entity_d)])) == set()
    assert set(world.Q.all_of(relations=[(ChildOf, ...)]).none_of(relations=[(ChildOf, entity_a)])) == {entity_d}
    assert entity_a in entity_b.relation_tags_many[ChildOf]
    assert entity_a == entity_b.relation_tags[ChildOf]
    for e in world.Q.all_of(relations=[(ChildOf, ...)]):
        e.relation_tags.clear()
    assert not set(world.Q.all_of(relations=[(ChildOf, ...)]))


def test_relations_many() -> None:
    world = tcod.ecs.World()
    entity_a = world.new_entity(name="A")
    entity_b = world.new_entity(name="B")
    entity_c = world.new_entity(name="C")

    with pytest.raises(KeyError):
        entity_a.relation_tags["foo"]
    entity_a.relation_tags_many["foo"] = (entity_b, entity_c)
    with pytest.raises(ValueError, match=r"Entity relation has multiple targets but an exclusive value was expected\."):
        entity_a.relation_tags["foo"]


def test_relation_components() -> None:
    world = tcod.ecs.World()
    entity_a = world.new_entity(name="A")
    entity_b = world.new_entity(name="B")

    entity_b.relation_components[int][entity_a] = 1
    assert entity_b.relation_components[int][entity_a] == 1
    del entity_b.relation_components[int][entity_a]

    entity_b.relation_components[("named", int)][entity_a] = 0
    assert entity_b.relation_components[("named", int)][entity_a] == 0


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


def sample_world_v1() -> tcod.ecs.World:
    """Return a sample world."""
    world = tcod.ecs.World()
    entity = world.new_entity(name="A")
    entity.components[str] = "str"
    entity.components[("foo", str)] = "foo"
    entity.tags.add("tag")
    entity_b = world.new_entity(name="B")
    entity_b.relation_tags["ChildOf"] = entity
    entity_b.relation_components[str][entity] = "str"
    return world


def check_world_v1(world: tcod.ecs.World) -> None:
    """Assert a sample world is as expected."""
    entity = world.named["A"]
    assert entity.components[str] == "str"
    assert entity.components[("foo", str)] == "foo"
    assert "tag" in entity.tags
    entity_b = world.named["B"]
    assert entity_b.relation_tags["ChildOf"] == entity
    assert entity_b.relation_components[str][entity] == "str"


def test_pickle() -> None:
    unpickled: tcod.ecs.World = pickle.loads(pickle.dumps(sample_world_v1(), protocol=4))
    check_world_v1(unpickled)


def test_unpickle_v1_0() -> None:
    WORLD_v1_0 = b"\x80\x04\x95\xc7\x02\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04dict\x94\x93\x94\x85\x94R\x94(h\t\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94)\x81\x94N}\x94\x8c\x05world\x94h\x03s\x86\x94b\x8c\x03str\x94s\x8c\x03foo\x94h\x0f\x86\x94}\x94h\x13h\x18su\x8c\x15_components_by_entity\x94h\x08h\t\x8c\x03set\x94\x93\x94\x85\x94R\x94h\x13\x8f\x94(h\x19h\x0f\x90s\x8c\x0c_tags_by_key\x94h\x08h\x1d\x85\x94R\x94\x8c\x03tag\x94\x8f\x94(h\x13\x90s\x8c\x0f_tags_by_entity\x94h\x08h\x1d\x85\x94R\x94h\x13\x8f\x94(h$\x90s\x8c\x11_relations_by_key\x94h\x08\x8c\tfunctools\x94\x8c\x07partial\x94\x93\x94\x8c\x06typing\x94\x8c\x0bDefaultDict\x94\x93\x94\x85\x94R\x94(h0h\x1d\x85\x94}\x94Nt\x94b\x85\x94R\x94\x8c\x07ChildOf\x94h\x08h\x1d\x85\x94R\x94h\x12)\x81\x94N}\x94h\x15h\x03s\x86\x94b\x8f\x94(h\x13\x90ss\x8c\x14_relation_components\x94h\x08h-h0\x85\x94R\x94(h0h\x0b\x85\x94}\x94Nt\x94b\x85\x94R\x94h\x0fh\x08h\x0b\x85\x94R\x94h;}\x94h\x13h\x17sss\x8c\x11_relations_lookup\x94h\x08h\x1d\x85\x94R\x94(h8h\x13\x86\x94\x8f\x94(h;\x90h8h\t\x8c\x08Ellipsis\x94\x93\x94\x86\x94\x8f\x94(h;\x90h;h8N\x87\x94\x8f\x94(h\x13\x90hPh8N\x87\x94\x8f\x94(h\x13\x90h\x0fh\x13\x86\x94\x8f\x94(h;\x90h\x0fhP\x86\x94\x8f\x94(h;\x90h;h\x0fN\x87\x94\x8f\x94(h\x13\x90hPh\x0fN\x87\x94\x8f\x94(h\x13\x90u\x8c\x0e_names_by_name\x94}\x94(\x8c\x01A\x94h\x13\x8c\x01B\x94h;u\x8c\x10_names_by_entity\x94}\x94(h\x13hah;hbuub."  # cspell: disable-line
    unpickled: tcod.ecs.World = pickle.loads(WORLD_v1_0)
    check_world_v1(unpickled)
    unpickled.new_entity()
    assert not unpickled.global_.components


def test_global() -> None:
    world = tcod.ecs.World()
    world.global_.components[int] = 1
    assert set(world.Q[tcod.ecs.Entity, int]) == {(world.global_, 1)}
