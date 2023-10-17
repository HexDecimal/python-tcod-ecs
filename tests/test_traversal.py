"""Inheritance tests."""
from typing import Final

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
    assert world["derived"].components(traverse=["alt"])[str] == "alt"
    with pytest.raises(KeyError, match="str"):
        assert world["derived"].components(traverse=())[str]

    assert str in world["derived"].components
    assert str in world["derived"].components(traverse=["alt"])
    assert str not in world["derived"].components(traverse=())
    assert set(world["derived"].components.keys()) == {str}
    assert set(world["derived"].components(traverse=["alt"]).keys()) == {str}
    assert not set(world["derived"].components(traverse=()).keys())

    assert world.Q.all_of(components=[str]).get_entities() == {world["base"], world["alt"], world["derived"]}
    assert world.Q.all_of(components=[str], traverse=["alt"]).get_entities() == {
        world["base"],
        world["alt"],
        world["derived"],
    }
    assert world.Q.all_of(components=[str], depth=0).get_entities() == {world["base"], world["alt"]}


def test_multiple_inheritance() -> None:
    world = World()
    ViaA: Final = object()
    ViaC: Final = object()
    world["A"].components[str] = "A"
    world["B"].components[str] = "B"
    world["B"].components[int] = 0
    world["C"].components[str] = "C"
    world["C"].relation_tag[IsA] = world["B"]
    world["D"].relation_tag[ViaA] = world["A"]
    world["D"].relation_tag[ViaC] = world["C"]
    world["E"].relation_tag[IsA] = world["D"]
    assert str not in world["D"].components
    assert int not in world["D"].components
    assert world["E"].components(traverse=[ViaA, IsA])[str] == "A"
    assert world["E"].components(traverse=[ViaA, ViaC, IsA])[str] == "A"
    assert world["E"].components(traverse=[ViaC, ViaA, IsA])[str] == "C"
    assert world["E"].components(traverse=[IsA, ViaA, ViaC])[int] == 0
    assert world["E"].components(traverse=[IsA, ViaA, ViaC]).keys() == {str, int}
    assert world["E"].components(traverse=[IsA, ViaA]).keys() == {str}
    assert world.Q.all_of(components=[int]).get_entities() == {world["B"], world["C"]}
    assert world.Q.all_of(components=[int], traverse=[IsA, ViaC]).get_entities() == {
        world["B"],
        world["C"],
        world["D"],
        world["E"],
    }


def test_cyclic_inheritance() -> None:
    world = World()
    world["A"].relation_tag[IsA] = world["D"]
    world["B"].relation_tag[IsA] = world["A"]
    world["C"].relation_tag[IsA] = world["B"]
    world["D"].relation_tag[IsA] = world["C"]

    world["A"].components[str] = "A"
    world["C"].components[str] = "C"

    assert int not in world["A"].components
    assert world["A"].components[str] == "A"
    assert world["B"].components[str] == "A"
    assert world["C"].components[str] == "C"
    assert world["D"].components[str] == "C"
