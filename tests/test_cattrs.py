"""Tests for cattrs support."""

import json
from pprint import pprint

import attrs
import cattrs
import cattrs.preconf.json
import pytest

import tcod.ecs.cattrs
from tcod.ecs import Entity, World

from . import test_ecs


@attrs.define(frozen=True)
class Base:
    """Test base class."""


@attrs.define(frozen=True)
class Derived(Base):
    """Test derived class."""


def test_cattrs() -> None:
    """Make sure data isn't lost in conversions."""
    world = World()
    world[1].components[int] = 2
    world[None].components[int] = 3
    world[1].tags.add("Hello")
    world[1].components[Base] = Derived()
    world[1].tags.add(Base())
    world[1].tags.add(Derived())

    entity = world.new_entity()
    entity.components[int] = 0
    entity.components[bool] = True
    entity.tags.add(0)
    entity.tags.add(1)
    entity.relation_tags["Baz"] = world[1]
    entity.relation_components[str][world[1]] = "Foo"
    entity.name = "Name"

    converter = cattrs.Converter()
    tcod.ecs.cattrs.configure_ecs(converter)
    data = converter.unstructure(world)
    new_world = converter.structure(data, World)

    assert new_world[1].components[Base] == Derived()
    assert set(new_world.Q.all_of(tags=[0])) == set(new_world.Q.all_of(components=[bool]))

    converter = cattrs.Converter()
    tcod.ecs.cattrs.configure_ecs(converter)
    converter.unstructure(new_world)


def test_cattrs_object() -> None:
    """Make sure objects are not duplicated."""
    world = World()
    entity = world.new_entity()
    entity.components[int] = 0
    entity.tags.add(0)
    entity.relation_tags["RelatedTo"] = entity

    converter = cattrs.Converter()
    tcod.ecs.cattrs.configure_ecs(converter)
    data = converter.unstructure(world)
    pprint(data)
    world = converter.structure(data, World)
    (test_entity,) = world.Q.all_of(tags=[0])
    assert test_entity.relation_tags["RelatedTo"] == test_entity
    assert {test_entity} == set(world.Q.all_of(components=[int]))
    assert {test_entity} == set(world.Q.all_of(relations=[("RelatedTo", ...)]))


@pytest.mark.parametrize("samples_version", ["v1", "v2"])
def test_samples(samples_version: str) -> None:
    """Check with test samples used for pickle."""
    world: World = getattr(test_ecs, f"sample_world_{samples_version}")()

    converter = cattrs.Converter()
    tcod.ecs.cattrs.configure_ecs(converter)

    world = converter.structure(converter.unstructure(world), World)
    getattr(test_ecs, f"check_world_{samples_version}")(world)


@pytest.mark.parametrize("samples_version", ["v1", "v2"])
def test_samples_json(samples_version: str) -> None:
    """Check with test samples used for pickle."""
    world: World = getattr(test_ecs, f"sample_world_{samples_version}")()

    converter = cattrs.preconf.json.make_converter()
    tcod.ecs.cattrs.configure_ecs(converter)

    unstructured = converter.unstructure(world)
    pprint(unstructured)
    world = converter.structure(json.loads(json.dumps(unstructured)), World)
    getattr(test_ecs, f"check_world_{samples_version}")(world)


def test_multiple() -> None:
    """Test multiple references and external references to worlds."""

    @attrs.define()
    class Test:
        world: World
        world_: World
        entity: Entity

    world = World()

    converter = cattrs.Converter()
    tcod.ecs.cattrs.configure_ecs(converter)
    test = converter.structure(converter.unstructure(Test(world, world, world[None])), Test)
    assert world is not test.world
    assert isinstance(test.world, World)
    assert test.world is test.world_
    assert isinstance(test.entity, Entity)
    assert test.entity.world is test.world
