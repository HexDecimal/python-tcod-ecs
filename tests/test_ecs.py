# ruff: noqa: D100 D103 ANN401 S301
from __future__ import annotations

import io
import pickle
import pickletools
import sys
from typing import Any, Callable, Final, Iterator

import pytest

import tcod.ecs


def test_world() -> None:
    world = tcod.ecs.World()
    with pytest.warns():
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
    entity_a = world["A"]
    entity_b = world["B"]
    entity_b.relation_tag[ChildOf] = entity_a
    entity_c = world["C"]
    entity_c.relation_tag[ChildOf] = entity_a
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


def test_naming() -> None:
    world = tcod.ecs.World()
    with pytest.warns():
        entity_a = world.new_entity(name="A")
    assert entity_a.name == "A"
    assert world.named["A"] is entity_a
    with pytest.warns():
        entity_a2 = world.new_entity(name="A")
    assert world.named["A"] is entity_a2
    assert entity_a.name is None
    with pytest.warns():
        entity_a2.name = None
    assert entity_a2.name is None
    assert world.named.get("A") is None
    with pytest.warns():
        assert repr(world.new_entity(name="foo")) == "<Entity name='foo'>"


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
    with pytest.warns():
        entity = world.new_entity(name="A")
    entity.components[str] = "str"
    entity.components[("foo", str)] = "foo"
    entity.tags.add("tag")
    with pytest.warns():
        entity_b = world.new_entity(name="B")
    entity_b.relation_tag["ChildOf"] = entity
    entity_b.relation_components[str][entity] = "str"
    return world


def check_world_v1(world: tcod.ecs.World) -> None:
    """Assert a sample world is as expected."""
    entity = world.named["A"]
    assert entity.components[str] == "str"
    assert entity.components[("foo", str)] == "foo"
    assert "tag" in entity.tags
    entity_b = world.named["B"]
    assert entity_b.relation_tag["ChildOf"] == entity
    assert entity_b.relation_components[str][entity] == "str"
    assert not world[None].components


def sample_world_v2() -> tcod.ecs.World:
    """Return a sample world."""
    world = tcod.ecs.World()
    with pytest.warns():
        world["A"].name = "A"
    assert world.named["A"] is world["A"]
    world["A"].components[str] = "str"
    world["A"].components[("foo", str)] = "foo"
    world["A"].tags.add("tag")
    world["B"].relation_tag["ChildOf"] = world["A"]
    world["B"].relation_components[str][world["A"]] = "str"
    world[None].components[bool] = True
    return world


def check_world_v2(world: tcod.ecs.World) -> None:
    """Assert a sample world is as expected."""
    original = sample_world_v2()
    assert not world["X"].components
    assert world.named["A"] is world["A"]
    assert world["A"].components == original["A"].components
    assert world["A"].tags == original["A"].tags
    assert world["B"].relation_tag["ChildOf"] == world["A"]
    assert world["B"].relation_components[str][world["A"]] == "str"
    assert world[None].components[bool] is True


PICKLED_SAMPLES = {
    "v2": {
        "latest": b"\x80\x04\x95:\x01\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x15_components_by_entity\x94}\x94(h\x00\x8c\x06Entity\x94\x93\x94h\x03\x8c\x01A\x94\x86\x94R\x94}\x94(\x8c\x08builtins\x94\x8c\x03str\x94\x93\x94\x8c\x03str\x94\x8c\x03foo\x94h\x0f\x86\x94h\x11uh\x08h\x03N\x86\x94R\x94}\x94h\r\x8c\x04bool\x94\x93\x94\x88su\x8c\x0f_tags_by_entity\x94}\x94h\x0b\x8f\x94(\x8c\x03tag\x94\x90s\x8c\x18_relation_tags_by_entity\x94}\x94h\x08h\x03\x8c\x01B\x94\x86\x94R\x94}\x94\x8c\x07ChildOf\x94\x8f\x94(h\x0b\x90ss\x8c\x1e_relation_components_by_entity\x94}\x94h }\x94h\x0f}\x94h\x0bh\x10sss\x8c\x0e_names_by_name\x94}\x94h\th\x0bsub.",  # cspell: disable-line
        "3.4.0": b"\x80\x04\x95\xbb\x02\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04dict\x94\x93\x94\x85\x94R\x94(h\t\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03\x8c\x01A\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\x0f\x86\x94}\x94h\x15h\x17sh\t\x8c\x04bool\x94\x93\x94}\x94h\x12h\x03N\x86\x94R\x94\x88su\x8c\x15_components_by_entity\x94h\x08h\t\x8c\x03set\x94\x93\x94\x85\x94R\x94(h\x15\x8f\x94(h\x18h\x0f\x90h\x1e\x8f\x94(h\x1b\x90u\x8c\x0c_tags_by_key\x94h\x08h!\x85\x94R\x94\x8c\x03tag\x94\x8f\x94(h\x15\x90s\x8c\x0f_tags_by_entity\x94h\x08h!\x85\x94R\x94h\x15\x8f\x94(h)\x90s\x8c\x18_relation_tags_by_entity\x94h\x08h\x00\x8c\x13_defaultdict_of_set\x94\x93\x94\x85\x94R\x94h\x12h\x03\x8c\x01B\x94\x86\x94R\x94h\x08h!\x85\x94R\x94\x8c\x07ChildOf\x94\x8f\x94(h\x15\x90ss\x8c\x1e_relation_components_by_entity\x94h\x08h\x00\x8c\x14_defaultdict_of_dict\x94\x93\x94\x85\x94R\x94h6h\x08h\x0b\x85\x94R\x94h\x0f}\x94h\x15h\x16sss\x8c\x11_relations_lookup\x94h\x08h!\x85\x94R\x94(h9h\x15\x86\x94\x8f\x94(h6\x90h9h\t\x8c\x08Ellipsis\x94\x93\x94\x86\x94\x8f\x94(h6\x90h6h9N\x87\x94\x8f\x94(h\x15\x90hIh9N\x87\x94\x8f\x94(h\x15\x90h\x0fh\x15\x86\x94\x8f\x94(h6\x90h\x0fhI\x86\x94\x8f\x94(h6\x90h6h\x0fN\x87\x94\x8f\x94(h\x15\x90hIh\x0fN\x87\x94\x8f\x94(h\x15\x90u\x8c\x0e_names_by_name\x94}\x94h\x13h\x15s\x8c\x10_names_by_entity\x94}\x94h\x15h\x13sub.",  # cspell: disable-line
        "3.0.0": b"\x80\x04\x95\xc6\x02\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04dict\x94\x93\x94\x85\x94R\x94(h\t\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03\x8c\x01A\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\x0f\x86\x94}\x94h\x15h\x17sh\t\x8c\x04bool\x94\x93\x94}\x94h\x12h\x03N\x86\x94R\x94\x88su\x8c\x15_components_by_entity\x94h\x08h\t\x8c\x03set\x94\x93\x94\x85\x94R\x94(h\x15\x8f\x94(h\x18h\x0f\x90h\x1e\x8f\x94(h\x1b\x90u\x8c\x0c_tags_by_key\x94h\x08h!\x85\x94R\x94\x8c\x03tag\x94\x8f\x94(h\x15\x90s\x8c\x0f_tags_by_entity\x94h\x08h!\x85\x94R\x94h\x15\x8f\x94(h)\x90s\x8c\x18_relation_tags_by_entity\x94h\x08\x8c\tfunctools\x94\x8c\x07partial\x94\x93\x94h\x08\x85\x94R\x94(h\x08h!\x85\x94}\x94Nt\x94b\x85\x94R\x94h\x12h\x03\x8c\x01B\x94\x86\x94R\x94h\x08h!\x85\x94R\x94\x8c\x07ChildOf\x94\x8f\x94(h\x15\x90ss\x8c\x1e_relation_components_by_entity\x94h\x08h2h\x08\x85\x94R\x94(h\x08h\x0b\x85\x94}\x94Nt\x94b\x85\x94R\x94h<h\x08h\x0b\x85\x94R\x94h\x0f}\x94h\x15h\x16sss\x8c\x11_relations_lookup\x94h\x08h!\x85\x94R\x94(h?h\x15\x86\x94\x8f\x94(h<\x90h?h\t\x8c\x08Ellipsis\x94\x93\x94\x86\x94\x8f\x94(h<\x90h<h?N\x87\x94\x8f\x94(h\x15\x90hRh?N\x87\x94\x8f\x94(h\x15\x90h\x0fh\x15\x86\x94\x8f\x94(h<\x90h\x0fhR\x86\x94\x8f\x94(h<\x90h<h\x0fN\x87\x94\x8f\x94(h\x15\x90hRh\x0fN\x87\x94\x8f\x94(h\x15\x90u\x8c\x0e_names_by_name\x94}\x94h\x13h\x15s\x8c\x10_names_by_entity\x94}\x94h\x15h\x13sub.",  # cspell: disable-line
    },
    "v1": {
        "latest": b"\x80\x04\x957\x01\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x15_components_by_entity\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03\x8c\x08builtins\x94\x8c\x06object\x94\x93\x94)\x81\x94\x86\x94R\x94}\x94(h\t\x8c\x03str\x94\x93\x94\x8c\x03str\x94\x8c\x03foo\x94h\x11\x86\x94h\x13us\x8c\x0f_tags_by_entity\x94}\x94h\x0e\x8f\x94(\x8c\x03tag\x94\x90s\x8c\x18_relation_tags_by_entity\x94}\x94h\x08h\x03h\x0b)\x81\x94\x86\x94R\x94}\x94\x8c\x07ChildOf\x94\x8f\x94(h\x0e\x90ss\x8c\x1e_relation_components_by_entity\x94}\x94h\x1d}\x94h\x11}\x94h\x0eh\x12sss\x8c\x0e_names_by_name\x94}\x94(\x8c\x01A\x94h\x0e\x8c\x01B\x94h\x1duub.",  # cspell: disable-line
        "3.4.0": b"\x80\x04\x95\xb5\x02\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04dict\x94\x93\x94\x85\x94R\x94(h\t\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03h\t\x8c\x06object\x94\x93\x94)\x81\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\x0f\x86\x94}\x94h\x17h\x19su\x8c\x15_components_by_entity\x94h\x08h\t\x8c\x03set\x94\x93\x94\x85\x94R\x94h\x17\x8f\x94(h\x1ah\x0f\x90s\x8c\x0c_tags_by_key\x94h\x08h\x1e\x85\x94R\x94\x8c\x03tag\x94\x8f\x94(h\x17\x90s\x8c\x0f_tags_by_entity\x94h\x08h\x1e\x85\x94R\x94h\x17\x8f\x94(h%\x90s\x8c\x18_relation_tags_by_entity\x94h\x08h\x00\x8c\x13_defaultdict_of_set\x94\x93\x94\x85\x94R\x94h\x12h\x03h\x14)\x81\x94\x86\x94R\x94h\x08h\x1e\x85\x94R\x94\x8c\x07ChildOf\x94\x8f\x94(h\x17\x90ss\x8c\x1e_relation_components_by_entity\x94h\x08h\x00\x8c\x14_defaultdict_of_dict\x94\x93\x94\x85\x94R\x94h2h\x08h\x0b\x85\x94R\x94h\x0f}\x94h\x17h\x18sss\x8c\x11_relations_lookup\x94h\x08h\x1e\x85\x94R\x94(h5h\x17\x86\x94\x8f\x94(h2\x90h5h\t\x8c\x08Ellipsis\x94\x93\x94\x86\x94\x8f\x94(h2\x90h2h5N\x87\x94\x8f\x94(h\x17\x90hEh5N\x87\x94\x8f\x94(h\x17\x90h\x0fh\x17\x86\x94\x8f\x94(h2\x90h\x0fhE\x86\x94\x8f\x94(h2\x90h2h\x0fN\x87\x94\x8f\x94(h\x17\x90hEh\x0fN\x87\x94\x8f\x94(h\x17\x90u\x8c\x0e_names_by_name\x94}\x94(\x8c\x01A\x94h\x17\x8c\x01B\x94h2u\x8c\x10_names_by_entity\x94}\x94(h\x17hVh2hWuub.",  # cspell: disable-line
        "3.0.0": b"\x80\x04\x95\xc0\x02\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04dict\x94\x93\x94\x85\x94R\x94(h\t\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03h\t\x8c\x06object\x94\x93\x94)\x81\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\x0f\x86\x94}\x94h\x17h\x19su\x8c\x15_components_by_entity\x94h\x08h\t\x8c\x03set\x94\x93\x94\x85\x94R\x94h\x17\x8f\x94(h\x1ah\x0f\x90s\x8c\x0c_tags_by_key\x94h\x08h\x1e\x85\x94R\x94\x8c\x03tag\x94\x8f\x94(h\x17\x90s\x8c\x0f_tags_by_entity\x94h\x08h\x1e\x85\x94R\x94h\x17\x8f\x94(h%\x90s\x8c\x18_relation_tags_by_entity\x94h\x08\x8c\tfunctools\x94\x8c\x07partial\x94\x93\x94h\x08\x85\x94R\x94(h\x08h\x1e\x85\x94}\x94Nt\x94b\x85\x94R\x94h\x12h\x03h\x14)\x81\x94\x86\x94R\x94h\x08h\x1e\x85\x94R\x94\x8c\x07ChildOf\x94\x8f\x94(h\x17\x90ss\x8c\x1e_relation_components_by_entity\x94h\x08h.h\x08\x85\x94R\x94(h\x08h\x0b\x85\x94}\x94Nt\x94b\x85\x94R\x94h8h\x08h\x0b\x85\x94R\x94h\x0f}\x94h\x17h\x18sss\x8c\x11_relations_lookup\x94h\x08h\x1e\x85\x94R\x94(h;h\x17\x86\x94\x8f\x94(h8\x90h;h\t\x8c\x08Ellipsis\x94\x93\x94\x86\x94\x8f\x94(h8\x90h8h;N\x87\x94\x8f\x94(h\x17\x90hNh;N\x87\x94\x8f\x94(h\x17\x90h\x0fh\x17\x86\x94\x8f\x94(h8\x90h\x0fhN\x86\x94\x8f\x94(h8\x90h8h\x0fN\x87\x94\x8f\x94(h\x17\x90hNh\x0fN\x87\x94\x8f\x94(h\x17\x90u\x8c\x0e_names_by_name\x94}\x94(\x8c\x01A\x94h\x17\x8c\x01B\x94h8u\x8c\x10_names_by_entity\x94}\x94(h\x17h_h8h`uub.",  # cspell: disable-line
        "1.2.0": b'\x80\x04\x95\xbd\x02\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04dict\x94\x93\x94\x85\x94R\x94(h\t\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03\x85\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\x0f\x86\x94}\x94h\x14h\x16su\x8c\x15_components_by_entity\x94h\x08h\t\x8c\x03set\x94\x93\x94\x85\x94R\x94h\x14\x8f\x94(h\x17h\x0f\x90s\x8c\x0c_tags_by_key\x94h\x08h\x1b\x85\x94R\x94\x8c\x03tag\x94\x8f\x94(h\x14\x90s\x8c\x0f_tags_by_entity\x94h\x08h\x1b\x85\x94R\x94h\x14\x8f\x94(h"\x90s\x8c\x18_relation_tags_by_entity\x94h\x08\x8c\tfunctools\x94\x8c\x07partial\x94\x93\x94h\x08\x85\x94R\x94(h\x08h\x1b\x85\x94}\x94Nt\x94b\x85\x94R\x94h\x12h\x03\x85\x94R\x94h\x08h\x1b\x85\x94R\x94\x8c\x07ChildOf\x94\x8f\x94(h\x14\x90ss\x8c\x1e_relation_components_by_entity\x94h\x08h+h\x08\x85\x94R\x94(h\x08h\x0b\x85\x94}\x94Nt\x94b\x85\x94R\x94h4h\x08h\x0b\x85\x94R\x94h\x0f}\x94h\x14h\x15sss\x8c\x11_relations_lookup\x94h\x08h\x1b\x85\x94R\x94(h7h\x14\x86\x94\x8f\x94(h4\x90h7h\t\x8c\x08Ellipsis\x94\x93\x94\x86\x94\x8f\x94(h4\x90h4h7N\x87\x94\x8f\x94(h\x14\x90hJh7N\x87\x94\x8f\x94(h\x14\x90h\x0fh\x14\x86\x94\x8f\x94(h4\x90h\x0fhJ\x86\x94\x8f\x94(h4\x90h4h\x0fN\x87\x94\x8f\x94(h\x14\x90hJh\x0fN\x87\x94\x8f\x94(h\x14\x90u\x8c\x0e_names_by_name\x94}\x94(\x8c\x01A\x94h\x14\x8c\x01B\x94h4u\x8c\x10_names_by_entity\x94}\x94(h\x14h[h4h\\u\x8c\x07global_\x94h\x12h\x03\x85\x94R\x94ub.',  # cspell: disable-line
    },
}
"""Pickled World samples are stored here for testing."""


def iter_samples() -> Iterator[tuple[str, str]]:
    """Iterate over the stored pickled samples."""
    for sample_version, pickles in PICKLED_SAMPLES.items():
        for ecs_version in pickles:
            yield sample_version, ecs_version


def pickle_disassemble(pickle: bytes) -> str:
    """Return a readable disassembly of a pickle stream."""
    with io.StringIO() as out:
        pickletools.dis(pickle, out)
        return out.getvalue()


@pytest.mark.xfail(
    condition=not (sys.platform == "win32" and sys.version_info[:2] == (3, 11)),
    reason="Pickle objects are sometimes not reproducible",
)
@pytest.mark.parametrize("sample_version", PICKLED_SAMPLES.keys())
def test_pickle(sample_version: str) -> None:
    """Test that pickled worlds are stable."""
    sample_world: Callable[[], tcod.ecs.World] = globals()[f"sample_world_{sample_version}"]
    check_world: Callable[[tcod.ecs.World], None] = globals()[f"check_world_{sample_version}"]
    sample_data = PICKLED_SAMPLES[sample_version]["latest"]

    pickled = pickle.dumps(sample_world(), protocol=4)
    print(pickled)
    assert pickle_disassemble(pickled) == pickle_disassemble(sample_data), "Check if data format has changed"
    unpickled: tcod.ecs.World = pickle.loads(pickled)
    check_world(unpickled)


@pytest.mark.parametrize(("sample_version", "ecs_version"), iter_samples())
def test_unpickle(sample_version: str, ecs_version: str) -> None:
    """Test that pickled worlds are stable."""
    globals()[f"sample_world_{sample_version}"]
    check_world: Callable[[tcod.ecs.World], None] = globals()[f"check_world_{sample_version}"]
    sample_data = PICKLED_SAMPLES[sample_version][ecs_version]

    unpickled: tcod.ecs.World = pickle.loads(sample_data)
    check_world(unpickled)


def test_global() -> None:
    world = tcod.ecs.World()
    with pytest.warns(match=r"world\[None\]"):
        world.global_.components[int] = 1
    with pytest.warns(match=r"world\[None\]"):
        assert set(world.Q[tcod.ecs.Entity, int]) == {(world.global_, 1)}


def test_by_name_type() -> None:
    entity = tcod.ecs.World()[None]
    with pytest.warns():
        assert list(entity.components.by_name_type(int, int)) == []
    entity.components[int] = 0
    entity.components[1, int] = 1
    entity.components[2, int] = 2
    entity.components["", int] = 3
    with pytest.warns():
        assert set(entity.components.by_name_type(int, int)) == {(1, int), (2, int)}


def test_suspicious_tags() -> None:
    with pytest.warns(match=r"The tags parameter was given a str type"):
        tcod.ecs.World().Q.all_of(tags="Tags")


def test_component_setdefault() -> None:
    entity = tcod.ecs.World()[None]
    assert entity.components.setdefault(int, 1) == 1
    assert entity.components.setdefault(int, 2) == 1
