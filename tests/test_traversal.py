"""Inheritance tests."""

from __future__ import annotations

from typing import Final

import pytest

from tcod.ecs import IsA, Registry

# ruff: noqa: D103


def test_component_traversal() -> None:
    world = Registry()
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
    world = Registry()
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
    world = Registry()
    ViaA: Final = object()  # noqa: N806
    ViaC: Final = object()  # noqa: N806
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
    world = Registry()
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


def test_tag_traversal() -> None:
    world = Registry()
    world["B"].relation_tag[IsA] = world["A"]
    world["C"].relation_tag[IsA] = world["B"]

    assert not set(world["C"].tags)
    assert not world.Q.all_of(tags=["A"]).get_entities()
    world["A"].tags.add("A")
    assert world.Q.all_of(tags=["A"]).get_entities() == {world["A"], world["B"], world["C"]}
    assert set(world["C"].tags) == {"A"}
    assert not world.Q.all_of(tags=["B"]).get_entities()
    world["B"].tags.add("B")
    assert world.Q.all_of(tags=["B"]).get_entities() == {world["B"], world["C"]}
    assert set(world["C"].tags) == {"A", "B"}
    world["C"].tags.add("C")
    assert set(world["A"].tags) == {"A"}
    assert set(world["B"].tags) == {"A", "B"}
    assert set(world["C"].tags) == {"A", "B", "C"}
    assert "A" in world["C"].tags
    assert "C" not in world["A"].tags

    world["C"].tags.discard("A")
    assert set(world["C"].tags) == {"A", "B", "C"}

    with pytest.raises(KeyError):
        world["C"].tags.remove("A")

    world["C"].tags.add("A")
    assert set(world["C"].tags) == {"A", "B", "C"}
    world["C"].tags.remove("A")
    assert set(world["C"].tags) == {"A", "B", "C"}

    assert set(world["C"].tags(traverse=())) == {"C"}

    world["A"].tags.remove("A")
    assert not world.Q.all_of(tags=["A"]).get_entities()


def test_relation_traversal() -> None:
    world = Registry()
    world["B"].relation_tag[IsA] = world["A"]
    world["C"].relation_tag[IsA] = world["B"]
    assert set(world["C"].relation_tags_many[IsA]) == {world["A"], world["B"]}
    assert world["C"].relation_tag[IsA] == world["B"]
    assert set(world["C"].relation_tag) == {IsA}
    assert world.Q.all_of(relations=[(IsA, world["A"])]).get_entities() == {world["B"], world["C"]}

    world["A"].relation_tag["test"] = world["foo"]
    world["B"].relation_tag["test"] = world["bar"]

    assert set(world["C"].relation_tags_many["test"]) == {world["foo"], world["bar"]}
    assert len(world["C"].relation_tags_many["test"]) == 2  # noqa: PLR2004
    assert world["C"].relation_tag["test"] == world["bar"]
    assert world.Q.all_of(relations=[("test", ...)]).get_entities() == {world["A"], world["B"], world["C"]}
    assert not set(world["C"].relation_tags_many(traverse=())["test"])
    with pytest.raises(KeyError):
        world["C"].relation_tag(traverse=())["test"]

    del world["B"].relation_tag["test"]
    assert set(world["C"].relation_tags_many["test"]) == {world["foo"]}
    assert world["C"].relation_tag["test"] == world["foo"]
    with pytest.raises(KeyError):
        world["C"].relation_tags_many["test"].remove(world["foo"])
    world["A"].relation_tags_many["test"].remove(world["foo"])

    world["A"].relation_components[str][world["foo"]] = "foo"
    assert world.Q.all_of(relations=[(str, ...)]).get_entities() == {world["A"], world["B"], world["C"]}
    assert not set(world["C"].relation_components(traverse=()))

    world["B"].relation_components[str][world["bar"]] = "bar"
    world["C"].relation_components[str][world["bar"]] = "replaced"
    assert dict(world["B"].relation_components[str].items()) == {world["foo"]: "foo", world["bar"]: "bar"}
    assert dict(world["C"].relation_components[str].items()) == {world["foo"]: "foo", world["bar"]: "replaced"}
    assert len(world["C"].relation_components[str]) == 2  # noqa: PLR2004
    world["C"].relation_components[int][world["foo"]] = 0
    assert set(world["C"].relation_components) == {str, int}


def test_inherited_clear() -> None:
    world = Registry()
    world["A"].components[int] = 1
    world["A"].tags.add("foo")
    world["A"].relation_components[str][world["B"]] = "bar"
    with pytest.warns():
        world["A"].relation_tags["baz"] = world["B"]
    child = world["A"].instantiate()
    child.clear()  # Could hang if broken
    x = child.components
    x[int] = "asd"
