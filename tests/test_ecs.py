"""Tests for tcod-ecs."""
from __future__ import annotations

import io
import pickle
import pickletools
import sys
from typing import Callable, Iterator

import pytest

import tcod.ecs

# ruff: noqa: D103


def test_world() -> None:
    world = tcod.ecs.Registry()
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
    world = tcod.ecs.Registry()
    entity = world.new_entity()
    entity.components[("name", str)] = "name"
    entity.components[("foo", str)] = "foo"
    assert entity.components[("name", str)] == "name"
    assert ("name", str) in entity.components
    assert ("name", int) not in entity.components
    assert set(world.Q[tcod.ecs.Entity, ("name", str), ("foo", str)]) == {(entity, "name", "foo")}


def test_naming() -> None:
    world = tcod.ecs.Registry()
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


def sample_world_v1() -> tcod.ecs.Registry:
    """Return a sample world."""
    world = tcod.ecs.Registry()
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


def check_world_v1(world: tcod.ecs.Registry) -> None:
    """Assert a sample world is as expected."""
    entity = world.named["A"]
    assert entity.components[str] == "str"
    assert entity.components[("foo", str)] == "foo"
    assert "tag" in entity.tags
    entity_b = world.named["B"]
    assert entity_b.relation_tag["ChildOf"] == entity
    assert set(world.Q.all_of(relations=[("ChildOf", ...)])) == {entity_b}
    assert set(world.Q.all_of(relations=[("ChildOf", entity)])) == {entity_b}
    assert set(world.Q.all_of(relations=[(..., "ChildOf", None)])) == {entity}
    assert set(world.Q.all_of(relations=[(entity_b, "ChildOf", None)])) == {entity}
    assert entity_b.relation_components[str][entity] == "str"
    assert not world[None].components


def sample_world_v2() -> tcod.ecs.Registry:
    """Return a sample world."""
    world = tcod.ecs.Registry()
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


def check_world_v2(world: tcod.ecs.Registry) -> None:
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
        "latest": b'\x80\x04\x95X\x01\x00\x00\x00\x00\x00\x00\x8c\x11tcod.ecs.registry\x94\x8c\x08Registry\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94}\x94(\x8c\x08builtins\x94\x8c\x03str\x94\x93\x94}\x94\x8c\x0ftcod.ecs.entity\x94\x8c\x06Entity\x94\x93\x94h\x03\x8c\x01A\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\t\x86\x94}\x94h\x10h\x12sh\x07\x8c\x04bool\x94\x93\x94}\x94h\rh\x03N\x86\x94R\x94\x88su\x8c\x0f_tags_by_entity\x94}\x94h\x10\x8f\x94(\x8c\x03tag\x94\x90s\x8c\x18_relation_tags_by_entity\x94}\x94h\rh\x03\x8c\x01B\x94\x86\x94R\x94}\x94\x8c\x07ChildOf\x94\x8f\x94(h\x10\x90ss\x8c\x1e_relation_components_by_entity\x94}\x94h"}\x94h\t}\x94h\x10h\x11sss\x8c\x0e_names_by_name\x94}\x94h\x0eh\x10sub.',  # cspell: disable-line
        "5.0.0": b'\x80\x04\x95R\x01\x00\x00\x00\x00\x00\x00\x8c\x0etcod.ecs.world\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94}\x94(\x8c\x08builtins\x94\x8c\x03str\x94\x93\x94}\x94\x8c\x0ftcod.ecs.entity\x94\x8c\x06Entity\x94\x93\x94h\x03\x8c\x01A\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\t\x86\x94}\x94h\x10h\x12sh\x07\x8c\x04bool\x94\x93\x94}\x94h\rh\x03N\x86\x94R\x94\x88su\x8c\x0f_tags_by_entity\x94}\x94h\x10\x8f\x94(\x8c\x03tag\x94\x90s\x8c\x18_relation_tags_by_entity\x94}\x94h\rh\x03\x8c\x01B\x94\x86\x94R\x94}\x94\x8c\x07ChildOf\x94\x8f\x94(h\x10\x90ss\x8c\x1e_relation_components_by_entity\x94}\x94h"}\x94h\t}\x94h\x10h\x11sss\x8c\x0e_names_by_name\x94}\x94h\x0eh\x10sub.',  # cspell: disable-line
        "3.5.0": b"\x80\x04\x95<\x01\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94}\x94(\x8c\x08builtins\x94\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03\x8c\x01A\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\t\x86\x94}\x94h\x0fh\x11sh\x07\x8c\x04bool\x94\x93\x94}\x94h\x0ch\x03N\x86\x94R\x94\x88su\x8c\x0f_tags_by_entity\x94}\x94h\x0f\x8f\x94(\x8c\x03tag\x94\x90s\x8c\x18_relation_tags_by_entity\x94}\x94h\x0ch\x03\x8c\x01B\x94\x86\x94R\x94}\x94\x8c\x07ChildOf\x94\x8f\x94(h\x0f\x90ss\x8c\x1e_relation_components_by_entity\x94}\x94h!}\x94h\t}\x94h\x0fh\x10sss\x8c\x0e_names_by_name\x94}\x94h\rh\x0fsub.",  # cspell: disable-line
        "3.4.0": b"\x80\x04\x95\xbb\x02\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04dict\x94\x93\x94\x85\x94R\x94(h\t\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03\x8c\x01A\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\x0f\x86\x94}\x94h\x15h\x17sh\t\x8c\x04bool\x94\x93\x94}\x94h\x12h\x03N\x86\x94R\x94\x88su\x8c\x15_components_by_entity\x94h\x08h\t\x8c\x03set\x94\x93\x94\x85\x94R\x94(h\x15\x8f\x94(h\x18h\x0f\x90h\x1e\x8f\x94(h\x1b\x90u\x8c\x0c_tags_by_key\x94h\x08h!\x85\x94R\x94\x8c\x03tag\x94\x8f\x94(h\x15\x90s\x8c\x0f_tags_by_entity\x94h\x08h!\x85\x94R\x94h\x15\x8f\x94(h)\x90s\x8c\x18_relation_tags_by_entity\x94h\x08h\x00\x8c\x13_defaultdict_of_set\x94\x93\x94\x85\x94R\x94h\x12h\x03\x8c\x01B\x94\x86\x94R\x94h\x08h!\x85\x94R\x94\x8c\x07ChildOf\x94\x8f\x94(h\x15\x90ss\x8c\x1e_relation_components_by_entity\x94h\x08h\x00\x8c\x14_defaultdict_of_dict\x94\x93\x94\x85\x94R\x94h6h\x08h\x0b\x85\x94R\x94h\x0f}\x94h\x15h\x16sss\x8c\x11_relations_lookup\x94h\x08h!\x85\x94R\x94(h9h\x15\x86\x94\x8f\x94(h6\x90h9h\t\x8c\x08Ellipsis\x94\x93\x94\x86\x94\x8f\x94(h6\x90h6h9N\x87\x94\x8f\x94(h\x15\x90hIh9N\x87\x94\x8f\x94(h\x15\x90h\x0fh\x15\x86\x94\x8f\x94(h6\x90h\x0fhI\x86\x94\x8f\x94(h6\x90h6h\x0fN\x87\x94\x8f\x94(h\x15\x90hIh\x0fN\x87\x94\x8f\x94(h\x15\x90u\x8c\x0e_names_by_name\x94}\x94h\x13h\x15s\x8c\x10_names_by_entity\x94}\x94h\x15h\x13sub.",  # cspell: disable-line
        "3.0.0": b"\x80\x04\x95\xc6\x02\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94\x8c\x0bcollections\x94\x8c\x0bdefaultdict\x94\x93\x94\x8c\x08builtins\x94\x8c\x04dict\x94\x93\x94\x85\x94R\x94(h\t\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03\x8c\x01A\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\x0f\x86\x94}\x94h\x15h\x17sh\t\x8c\x04bool\x94\x93\x94}\x94h\x12h\x03N\x86\x94R\x94\x88su\x8c\x15_components_by_entity\x94h\x08h\t\x8c\x03set\x94\x93\x94\x85\x94R\x94(h\x15\x8f\x94(h\x18h\x0f\x90h\x1e\x8f\x94(h\x1b\x90u\x8c\x0c_tags_by_key\x94h\x08h!\x85\x94R\x94\x8c\x03tag\x94\x8f\x94(h\x15\x90s\x8c\x0f_tags_by_entity\x94h\x08h!\x85\x94R\x94h\x15\x8f\x94(h)\x90s\x8c\x18_relation_tags_by_entity\x94h\x08\x8c\tfunctools\x94\x8c\x07partial\x94\x93\x94h\x08\x85\x94R\x94(h\x08h!\x85\x94}\x94Nt\x94b\x85\x94R\x94h\x12h\x03\x8c\x01B\x94\x86\x94R\x94h\x08h!\x85\x94R\x94\x8c\x07ChildOf\x94\x8f\x94(h\x15\x90ss\x8c\x1e_relation_components_by_entity\x94h\x08h2h\x08\x85\x94R\x94(h\x08h\x0b\x85\x94}\x94Nt\x94b\x85\x94R\x94h<h\x08h\x0b\x85\x94R\x94h\x0f}\x94h\x15h\x16sss\x8c\x11_relations_lookup\x94h\x08h!\x85\x94R\x94(h?h\x15\x86\x94\x8f\x94(h<\x90h?h\t\x8c\x08Ellipsis\x94\x93\x94\x86\x94\x8f\x94(h<\x90h<h?N\x87\x94\x8f\x94(h\x15\x90hRh?N\x87\x94\x8f\x94(h\x15\x90h\x0fh\x15\x86\x94\x8f\x94(h<\x90h\x0fhR\x86\x94\x8f\x94(h<\x90h<h\x0fN\x87\x94\x8f\x94(h\x15\x90hRh\x0fN\x87\x94\x8f\x94(h\x15\x90u\x8c\x0e_names_by_name\x94}\x94h\x13h\x15s\x8c\x10_names_by_entity\x94}\x94h\x15h\x13sub.",  # cspell: disable-line
    },
    "v1": {
        "latest": b"\x80\x04\x95V\x01\x00\x00\x00\x00\x00\x00\x8c\x11tcod.ecs.registry\x94\x8c\x08Registry\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94}\x94(\x8c\x08builtins\x94\x8c\x03str\x94\x93\x94}\x94\x8c\x0ftcod.ecs.entity\x94\x8c\x06Entity\x94\x93\x94h\x03h\x07\x8c\x06object\x94\x93\x94)\x81\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\t\x86\x94}\x94h\x12h\x14su\x8c\x0f_tags_by_entity\x94}\x94h\x12\x8f\x94(\x8c\x03tag\x94\x90s\x8c\x18_relation_tags_by_entity\x94}\x94h\rh\x03h\x0f)\x81\x94\x86\x94R\x94}\x94\x8c\x07ChildOf\x94\x8f\x94(h\x12\x90ss\x8c\x1e_relation_components_by_entity\x94}\x94h\x1f}\x94h\t}\x94h\x12h\x13sss\x8c\x0e_names_by_name\x94}\x94(\x8c\x01A\x94h\x12\x8c\x01B\x94h\x1fuub.",  # cspell: disable-line
        "5.0.0": b"\x80\x04\x95P\x01\x00\x00\x00\x00\x00\x00\x8c\x0etcod.ecs.world\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94}\x94(\x8c\x08builtins\x94\x8c\x03str\x94\x93\x94}\x94\x8c\x0ftcod.ecs.entity\x94\x8c\x06Entity\x94\x93\x94h\x03h\x07\x8c\x06object\x94\x93\x94)\x81\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\t\x86\x94}\x94h\x12h\x14su\x8c\x0f_tags_by_entity\x94}\x94h\x12\x8f\x94(\x8c\x03tag\x94\x90s\x8c\x18_relation_tags_by_entity\x94}\x94h\rh\x03h\x0f)\x81\x94\x86\x94R\x94}\x94\x8c\x07ChildOf\x94\x8f\x94(h\x12\x90ss\x8c\x1e_relation_components_by_entity\x94}\x94h\x1f}\x94h\t}\x94h\x12h\x13sss\x8c\x0e_names_by_name\x94}\x94(\x8c\x01A\x94h\x12\x8c\x01B\x94h\x1fuub.",  # cspell: disable-line
        "3.5.0": b"\x80\x04\x95:\x01\x00\x00\x00\x00\x00\x00\x8c\x08tcod.ecs\x94\x8c\x05World\x94\x93\x94)\x81\x94}\x94(\x8c\x13_components_by_type\x94}\x94(\x8c\x08builtins\x94\x8c\x03str\x94\x93\x94}\x94h\x00\x8c\x06Entity\x94\x93\x94h\x03h\x07\x8c\x06object\x94\x93\x94)\x81\x94\x86\x94R\x94\x8c\x03str\x94s\x8c\x03foo\x94h\t\x86\x94}\x94h\x11h\x13su\x8c\x0f_tags_by_entity\x94}\x94h\x11\x8f\x94(\x8c\x03tag\x94\x90s\x8c\x18_relation_tags_by_entity\x94}\x94h\x0ch\x03h\x0e)\x81\x94\x86\x94R\x94}\x94\x8c\x07ChildOf\x94\x8f\x94(h\x11\x90ss\x8c\x1e_relation_components_by_entity\x94}\x94h\x1e}\x94h\t}\x94h\x11h\x12sss\x8c\x0e_names_by_name\x94}\x94(\x8c\x01A\x94h\x11\x8c\x01B\x94h\x1euub.",  # cspell: disable-line
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
    sample_world: Callable[[], tcod.ecs.Registry] = globals()[f"sample_world_{sample_version}"]
    check_world: Callable[[tcod.ecs.Registry], None] = globals()[f"check_world_{sample_version}"]
    sample_data = PICKLED_SAMPLES[sample_version]["latest"]

    pickled = pickle.dumps(sample_world(), protocol=4)
    print(pickled)
    assert pickle_disassemble(pickled) == pickle_disassemble(sample_data), "Check if data format has changed"
    unpickled: tcod.ecs.Registry = pickle.loads(pickled)  # noqa: S301
    check_world(unpickled)


@pytest.mark.parametrize(("sample_version", "ecs_version"), iter_samples())
def test_unpickle(sample_version: str, ecs_version: str) -> None:
    """Test that pickled worlds are stable."""
    globals()[f"sample_world_{sample_version}"]
    check_world: Callable[[tcod.ecs.Registry], None] = globals()[f"check_world_{sample_version}"]
    sample_data = PICKLED_SAMPLES[sample_version][ecs_version]

    unpickled: tcod.ecs.Registry = pickle.loads(sample_data)  # noqa: S301
    check_world(unpickled)


def test_global() -> None:
    world = tcod.ecs.Registry()
    with pytest.warns(match=r"world\[None\]"):
        world.global_.components[int] = 1
    with pytest.warns(match=r"world\[None\]"):
        assert set(world.Q[tcod.ecs.Entity, int]) == {(world.global_, 1)}


def test_by_name_type() -> None:
    entity = tcod.ecs.Registry()[None]
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
        tcod.ecs.Registry().Q.all_of(tags="Tags")


def test_component_setdefault() -> None:
    entity = tcod.ecs.Registry()[None]
    assert entity.components.setdefault(int, 1) == 1
    assert entity.components.setdefault(int, 2) == 1


def test_query_exclude_components() -> None:
    world = tcod.ecs.Registry()
    world["A"].components[int] = 0
    world["A"].components[str] = ""
    world["B"].components[int] = 0
    assert set(world.Q.all_of(components=[int]).none_of(components=[str])) == {world["B"]}


def test_query_exclude_tags() -> None:
    world = tcod.ecs.Registry()
    world["A"].tags |= set("AB")
    world["B"].tags |= set("B")
    assert set(world.Q.all_of(tags=["B"]).none_of(tags=["A"])) == {world["B"]}


def test_query_exclude_relations() -> None:
    world = tcod.ecs.Registry()
    world["B"].relation_tag["ChildOf"] = world["A"]
    world["C"].relation_tags_many["ChildOf"] = {world["A"], world["B"]}
    assert set(world.Q.all_of(relations=[("ChildOf", ...)]).none_of(relations=[("ChildOf", world["B"])])) == {
        world["B"]
    }


def test_tag_query() -> None:
    world = tcod.ecs.Registry()
    assert not set(world.Q.all_of(tags=["A"]))
    world["A"].tags.add("A")
    assert set(world.Q.all_of(tags=["A"])) == {world["A"]}
    world["A"].tags.add("A")  # Cover redundant add
    assert set(world.Q.all_of(tags=["A"])) == {world["A"]}
    world["A"].tags.remove("A")
    world["A"].tags.discard("A")  # Cover redundant discard
    assert not set(world.Q.all_of(tags=["A"]))


def test_entity_clear() -> None:
    world = tcod.ecs.Registry()
    entity = world["entity"]
    other = world["other"]
    entity.components[int] = 0
    entity.tags.add(0)
    entity.relation_tag["test"] = other
    entity.relation_components[int][other] = 0
    other.relation_tag["test"] = entity
    other.relation_components[int][entity] = 0

    entity.clear()
    assert int not in entity.components
    assert 0 not in entity.tags
    assert "test" not in entity.relation_tag
    assert int not in entity.relation_components

    # Relations from other to entity are not cleared
    assert other.relation_tag["test"] is entity
    assert entity in other.relation_components[int]


def test_world_iter() -> None:
    with pytest.raises(TypeError, match=r"is not iterable"):
        iter(tcod.ecs.Registry())  # Not iterable for now, maybe later
