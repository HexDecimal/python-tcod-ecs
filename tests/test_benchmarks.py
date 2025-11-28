"""Benchmarking tests."""

from __future__ import annotations

from typing import Any

import tcod.ecs

# ruff: noqa: D103 ANN401


def test_component_missing(benchmark: Any) -> None:
    entity = tcod.ecs.Registry().new_entity()
    benchmark(lambda: entity.components.get(str))


def test_component_assign(benchmark: Any) -> None:
    entity = tcod.ecs.Registry().new_entity()

    @benchmark  # type: ignore[untyped-decorator]
    def _() -> None:
        entity.components[str] = "value"


def test_component_found(benchmark: Any) -> None:
    entity = tcod.ecs.Registry().new_entity()
    entity.components[str] = "value"
    benchmark(lambda: entity.components[str])


def test_tag_missing(benchmark: Any) -> None:
    entity = tcod.ecs.Registry().new_entity()
    benchmark(lambda: "value" in entity.tags)


def test_tag_assign(benchmark: Any) -> None:
    entity = tcod.ecs.Registry().new_entity()
    benchmark(lambda: entity.tags.add("value"))


def test_tag_found(benchmark: Any) -> None:
    entity = tcod.ecs.Registry().new_entity()
    benchmark(lambda: "value" in entity.tags)
