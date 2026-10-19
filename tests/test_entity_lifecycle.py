"""Regression tests for unreferenced entity lifetimes."""

from __future__ import annotations

import gc
import pickle
import weakref

import pytest

from tcod.ecs import Registry


@pytest.mark.parametrize(
    "operation",
    [
        "clear",
        "clear_empty",
        "clear_tags",
        "discard_missing_tag",
        "read_missing_component",
        "read_inherited_component",
        "delete_missing_component",
        "delete_missing_relation_component",
        "delete_missing_relation_component_type",
    ],
)
def test_unused_entity_is_released(operation: str) -> None:
    """Reads and cleanup must leave no registry reference to an unused entity."""
    registry = Registry()
    prefab = registry["prefab"]
    prefab_value = 7
    prefab.components[int] = prefab_value
    entity = prefab.instantiate() if operation == "read_inherited_component" else registry.new_entity()
    if operation == "clear":
        entity.components[int] = 3
        entity.tags.add("inventory")
        entity.clear()
    elif operation == "clear_empty":
        entity.clear()
    elif operation == "clear_tags":
        entity.tags.add("inventory")
        entity.tags.clear()
    elif operation == "discard_missing_tag":
        entity.tags.discard("inventory")
    elif operation == "read_missing_component":
        assert entity.components.get(str) is None
    elif operation == "read_inherited_component":
        assert entity.components[int] == prefab_value
        entity.relation_tags_many.clear()
    elif operation == "delete_missing_component":
        with pytest.raises(KeyError, match="str"):
            del entity.components[str]
    elif operation == "delete_missing_relation_component":
        with pytest.raises(KeyError, match="target"):
            del entity.relation_components[str][registry["target"]]
    else:
        assert operation == "delete_missing_relation_component_type"
        entity.relation_components[int][prefab] = 3
        with pytest.raises(KeyError, match="target"):
            del entity.relation_components[str][registry["target"]]
        assert entity.relation_components[int] == {prefab: 3}
        del entity.relation_components[int][prefab]
    reference = weakref.ref(entity)
    del entity
    gc.collect()
    assert reference() is None
    assert registry["prefab"] is prefab
    assert prefab.components[int] == prefab_value


def test_incoming_relation_retains_cleared_entity() -> None:
    """An incoming relation intentionally keeps its target alive until removed."""
    registry = Registry()
    owner, target = registry["owner"], registry.new_entity()
    owner.relation_tag["target"] = target
    reference = weakref.ref(target)
    target.clear()
    del target
    gc.collect()
    assert reference() is not None
    del owner.relation_tag["target"]
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("query_kind", ["component", "tag", "relation", "compound", "subquery"])
@pytest.mark.parametrize("restored", [False, True])
def test_queried_registry_is_released(query_kind: str, *, restored: bool) -> None:
    """Query caches must not keep a discarded registry and its entities alive."""
    registry = Registry()
    registry["player"].components[int] = 3
    registry["player"].tags.add("actor")
    registry["player"].relation_tag["room"] = registry["room"]
    registry["room"].tags.add("active")
    if restored:
        registry = pickle.loads(pickle.dumps(registry))  # noqa: S301
    if query_kind == "component":
        query = registry.Q.all_of(components=[int])
    elif query_kind == "tag":
        query = registry.Q.all_of(tags=["actor"])
    elif query_kind == "relation":
        query = registry.Q.all_of(relations=[("room", registry["room"])])
    elif query_kind == "compound":
        query = registry.Q.all_of(components=[int], tags=["actor"])
    else:
        query = registry.Q.all_of(relations=[("room", registry.Q.all_of(tags=["active"]))])
    assert set(query) == {registry["player"]}
    registry_ref = weakref.ref(registry)
    entity_ref = weakref.ref(registry["player"])
    del query, registry
    gc.collect()
    assert registry_ref() is None
    assert entity_ref() is None


def test_retained_query_keeps_registry_alive() -> None:
    """An application-held query continues to own its registry."""
    registry = Registry()
    registry["player"].tags.add("actor")
    query = registry.Q.all_of(tags=["actor"])
    assert set(query) == {registry["player"]}
    reference = weakref.ref(registry)
    del registry
    gc.collect()
    assert reference() is query.registry
    query.registry["player"].tags.clear()
    assert not query
    del query
    gc.collect()
    assert reference() is None
