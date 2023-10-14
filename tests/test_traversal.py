"""Inheritance tests."""

import pytest

from tcod.ecs import IsA, World

# ruff: noqa: D103


def test_component_traversal() -> None:
    world = World()
    assert not world.Q.all_of(components=[str]).get_entities()
    world["derived"].relation_tag[IsA] = world["base"]
    world["instance"].relation_tag[IsA] = world["derived"]
    world["base"].components[str] = "base"
    assert world["base"].components[str] == "base"
    assert world["derived"].components[str] == "base"  # Inherit from direct parent
    assert world["instance"].components[str] == "base"  # Inherit from parents parent
    assert world.Q.all_of(components=[str]).get_entities() == {world["base"], world["derived"], world["instance"]}
    assert world.Q.all_of(components=[str], depth=1).get_entities() == {world["base"], world["derived"]}
    assert world.Q.all_of(components=[str], depth=0).get_entities() == {world["base"]}

    world["derived"].components[str] = "derived"
    assert world["base"].components[str] == "base"
    assert world["derived"].components[str] == "derived"  # Now has its own value
    assert world["instance"].components[str] == "derived"  # Inherited value changed to parent

    world["instance"].components[str] = "instance"
    assert world["base"].components[str] == "base"
    assert world["derived"].components[str] == "derived"
    assert world["instance"].components[str] == "instance"

    del world["derived"].components[str]
    assert world["base"].components[str] == "base"
    assert world["derived"].components[str] == "base"  # Direct value should be deleted
    assert world["instance"].components[str] == "instance"

    del world["base"].components[str]
    with pytest.raises(KeyError, match="str"):
        assert world["base"].components[str]
    with pytest.raises(KeyError, match="str"):
        assert world["derived"].components[str]
    assert str not in world["base"].components
    assert str not in world["derived"].components
    assert world["instance"].components[str] == "instance"
    assert world.Q.all_of(components=[str]).get_entities() == {world["instance"]}

    del world["instance"].components[str]
    assert not world.Q.all_of(components=[str]).get_entities()
    assert str not in world["base"].components
    assert str not in world["derived"].components
    assert str not in world["instance"].components


def test_component_traversal_alternate() -> None:
    world = World()
    world["base"].components[str] = "base"
    world["alt"].components[str] = "alt"
    world["derived"].relation_tag[IsA] = world["base"]
    world["derived"].relation_tag["alt"] = world["alt"]
    assert world["derived"].components[str] == "base"
    assert world["derived"].components(traverse="alt")[str] == "alt"
    with pytest.raises(KeyError, match="str"):
        assert world["derived"].components(traverse=None)[str]

    assert str in world["derived"].components
    assert str in world["derived"].components(traverse="alt")
    assert str not in world["derived"].components(traverse=None)
    assert set(world["derived"].components.keys()) == {str}
    assert set(world["derived"].components(traverse="alt").keys()) == {str}
    assert not set(world["derived"].components(traverse=None).keys())

    assert world.Q.all_of(components=[str]).get_entities() == {world["base"], world["alt"], world["derived"]}
    assert world.Q.all_of(components=[str], traverse="alt").get_entities() == {
        world["base"],
        world["alt"],
        world["derived"],
    }
    assert world.Q.all_of(components=[str], depth=0).get_entities() == {world["base"], world["alt"]}
