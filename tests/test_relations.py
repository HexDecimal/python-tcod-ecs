"""Tests for entity relations."""

from __future__ import annotations

from typing import Final

import pytest

import tcod.ecs

# ruff: noqa: D103

ChildOf: Final = "ChildOf"


@pytest.mark.parametrize("operation", ["union", "intersection", "difference", "symmetric_difference"])
def test_inplace_relation_updates(operation: str) -> None:
    world = tcod.ecs.Registry()
    player = world["player"]
    first, second, third = world["first"], world["second"], world["third"]
    expected = {first, second}
    other = {second, third}
    player.relation_tags_many["allies"] = expected
    query = world.Q.all_of(relations=[("allies", second)])
    assert set(query) == {player}

    if operation == "union":
        expected |= other
        player.relation_tags_many["allies"] |= other
    elif operation == "intersection":
        expected &= other
        player.relation_tags_many["allies"] &= other
    elif operation == "difference":
        expected -= other
        player.relation_tags_many["allies"] -= other
    else:
        expected ^= other
        player.relation_tags_many["allies"] ^= other

    assert set(player.relation_tags_many["allies"]) == expected
    assert set(query) == ({player} if second in expected else set())
    assert set(world.Q.all_of(relations=[(player, "allies", None)])) == expected


def test_relation_assignment_from_lazy_self_view() -> None:
    world = tcod.ecs.Registry()
    player = world["player"]
    first, second = world["first"], world["second"]
    player.relation_tags_many["allies"] = (first, second)

    player.relation_tags_many["allies"] = (target for target in player.relation_tags_many["allies"] if target is first)

    assert set(player.relation_tags_many["allies"]) == {first}


def test_relation_assignment_from_another_key() -> None:
    world = tcod.ecs.Registry()
    player = world["player"]
    first, second = world["first"], world["second"]
    player.relation_tags_many["allies"] = (first,)
    player.relation_tags_many["rivals"] = (second,)

    player.relation_tags_many["allies"] = player.relation_tags_many["rivals"]

    assert set(player.relation_tags_many["allies"]) == {second}
    assert set(player.relation_tags_many["rivals"]) == {second}


def test_relation_set_operations() -> None:
    world = tcod.ecs.Registry()
    player = world["player"]
    first, second, third = world["first"], world["second"], world["third"]
    player.relation_tags_many["allies"] = (first, second)
    allies = player.relation_tags_many["allies"]
    other = {second, third}

    assert allies | other == {first, second, third}
    assert allies & other == {second}
    assert allies - other == {first}
    assert allies ^ other == {first, third}
    assert set(allies) == {first, second}


def test_tag_set_operations() -> None:
    world = tcod.ecs.Registry()
    player = world["player"]
    player.tags |= {"visible", "alive"}
    other = {"alive", "friendly"}
    query = world.Q.all_of(tags=["visible"])
    assert set(query) == {player}

    assert player.tags | other == {"visible", "alive", "friendly"}
    assert player.tags & other == {"alive"}
    assert player.tags - other == {"visible"}
    assert player.tags ^ other == {"visible", "friendly"}
    assert set(player.tags) == {"visible", "alive"}
    player.tags &= other
    assert set(player.tags) == {"alive"}
    assert set(query) == set()


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


@pytest.mark.parametrize("source_key", [int, ("fire", int)])
def test_component_relation_copy_between_keys(source_key: type[int] | tuple[str, type[int]]) -> None:
    world = tcod.ecs.Registry()
    mage, target, old_target = world["mage"], world["target"], world["old_target"]
    destination_key = ("poison", int)
    source_value = 5
    mage.relation_components[source_key][target] = source_value
    mage.relation_components[destination_key][old_target] = 9

    mage.relation_components[destination_key] = mage.relation_components[source_key]

    assert dict(mage.relation_components[destination_key]) == {target: source_value}
    assert dict(mage.relation_components[source_key]) == {target: source_value}
    assert set(world.Q.all_of(relations=[(destination_key, target)])) == {mage}
    assert set(world.Q.all_of(relations=[(destination_key, old_target)])) == set()


def test_component_relation_copy_from_another_entity() -> None:
    world = tcod.ecs.Registry()
    first, second, target = world["first"], world["second"], world["target"]
    value = 5
    first.relation_components[int][target] = value

    second.relation_components[int] = first.relation_components[int]

    assert dict(second.relation_components[int]) == {target: value}
    assert dict(first.relation_components[int]) == {target: value}


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


def test_clear_with_relation() -> None:
    world = tcod.ecs.Registry()
    parent = world["parent"]
    child = parent.instantiate()
    entity_other = world[object()]
    for i in range(5):
        parent.components[(i, int)] = i
        parent.tags.add(i)
        parent.relation_components[(i, int)][entity_other] = i
        parent.relation_tag[i] = entity_other

    for i in range(10):
        child.components[(i, int)] = i
        child.tags.add(i)
        child.relation_components[(i, int)][entity_other] = i
        child.relation_tag[i] = entity_other

    components_all = {(i, int) for i in range(10)}
    components_after = {(i, int) for i in range(5)}
    tags_all = set(range(10))
    tags_after = set(range(5))

    assert child.components.keys() == components_all
    assert child.relation_components.keys() == components_all
    assert set(child.tags) == tags_all
    assert set(child.relation_tag.keys()) == tags_all | {tcod.ecs.IsA}

    # Clear direct values, keeping values from parent as long as the IsA relation exists
    child.components.clear()
    assert child.components.keys() == components_after
    child.relation_components.clear()
    assert child.relation_components.keys() == components_after
    child.tags.clear()
    assert set(child.tags) == tags_after

    # Clearing relation_tags means breaking the IsA link to the parent
    child.relation_tag.clear()
    assert not child.relation_tag.keys()
    assert not child.components.keys()
    assert not child.tags
    assert not child.relation_components.keys()
