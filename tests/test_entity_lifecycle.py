"""Regression tests for unreferenced entity lifetimes."""

from __future__ import annotations

import gc
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
    else:
        assert operation == "delete_missing_relation_component"
        with pytest.raises(KeyError, match="target"):
            del entity.relation_components[str][registry["target"]]
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
