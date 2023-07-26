"""Tools for querying  World objects."""
from __future__ import annotations

import itertools
import warnings
from collections import defaultdict
from typing import TYPE_CHECKING, AbstractSet, Any, Final, Iterable, Iterator, TypeVar, overload
from weakref import WeakKeyDictionary, WeakSet

import attrs
from typing_extensions import Self

import tcod.ecs.entity
from tcod.ecs.typing import _ComponentKey, _RelationQuery

if TYPE_CHECKING:
    from tcod.ecs.entity import Entity
    from tcod.ecs.world import World

_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")


_query_caches: WeakKeyDictionary[World, _QueryCache] = WeakKeyDictionary()
"""The master table of cached queries."""


@attrs.define
class _QueryCache:
    """Main data structure for the query cache."""

    queries: dict[Query, set[Entity]] = attrs.field(factory=dict)
    """Table of cached queries."""
    by_components: defaultdict[_ComponentKey[object], WeakSet[Query]] = attrs.field(
        factory=lambda: defaultdict(WeakSet)
    )
    """Which queries depend on which components."""
    by_tags: defaultdict[object, WeakSet[Query]] = attrs.field(factory=lambda: defaultdict(WeakSet))
    """Which queries depend on which tags."""
    by_relations: defaultdict[_RelationQuery, WeakSet[Query]] = attrs.field(factory=lambda: defaultdict(WeakSet))
    """Which queries depend on which relations."""


def _touch_component(world: World, component: _ComponentKey[object]) -> None:
    """Drop cached queries if a component change has invalidated them."""
    cache = _query_caches.get(world)
    if cache is None:
        return
    if component not in cache.by_components:
        return
    for touched_query in cache.by_components.pop(component, ()):
        cache.queries.pop(touched_query, None)


def _touch_tag(world: World, tag: object) -> None:
    """Drop cached queries if a tag change has invalidated them."""
    cache = _query_caches.get(world)
    if cache is None:
        return
    if tag not in cache.by_tags:
        return
    for touched_query in cache.by_tags.pop(tag, ()):
        cache.queries.pop(touched_query, None)


def _touch_relations(world: World, relations: Iterable[_RelationQuery]) -> None:
    """Drop cached queries if a relation change has invalidated them."""
    cache = _query_caches.get(world)
    if cache is None:
        return
    for relation in relations:
        if relation not in cache.by_relations:
            continue
        for touched_query in cache.by_relations.pop(relation, ()):
            cache.queries.pop(touched_query, None)


def _check_suspicious_tags(tags: Iterable[object], stacklevel: int = 2) -> None:
    """Warn for the common mistake of passing a string as the tags parameter."""
    if isinstance(tags, str):
        warnings.warn(
            "The tags parameter was given a str type."
            " This will split the string and check its individual letters as tags."
            "\nAdd square brackets 'tags=[tag]' to check for a single string tag. (Recommended)"
            "\nOtherwise use 'tags=list(tags)' to suppress this warning.",
            RuntimeWarning,
            stacklevel=stacklevel + 1,
        )


def _fetch_lookup_tables(
    world: World,
    components: frozenset[_ComponentKey[object]],
    tags: frozenset[object],
    relations: frozenset[_RelationQuery],
) -> Iterator[AbstractSet[Entity]]:
    """Iterate over the relevant sets for this world and query."""
    for component in components:
        yield world._components_by_type.get(component, {}).keys()
    for tag in tags:
        yield world._tags_by_key.get(tag, set())
    for relation in relations:
        yield world._relations_lookup.get(relation, set())


def _add_query_to_cache(world: World, query: Query, entities: set[Entity]) -> None:
    """Adds a query."""
    cache = _query_caches.get(world)
    if cache is None:
        cache = _query_caches[world] = _QueryCache()

    cache.queries[query] = entities
    for component in itertools.chain(query._all_of_components, query._none_of_components):
        cache.by_components[component].add(query)
    for tag in itertools.chain(query._all_of_tags, query._none_of_tags):
        cache.by_tags[tag].add(query)
    for relation in itertools.chain(query._all_of_relations, query._none_of_relations):
        cache.by_relations[relation].add(query)


def _collect_query(world: World, query: Query) -> set[Entity]:
    """Return the entities matching the given query."""
    requires = sorted(  # Place the smallest sets first to speed up intersections
        _fetch_lookup_tables(world, query._all_of_components, query._all_of_tags, query._all_of_relations), key=len
    )
    excludes = list(
        _fetch_lookup_tables(world, query._none_of_components, query._none_of_tags, query._none_of_relations)
    )

    if not requires:
        if excludes:
            msg = "A Query can not function only excluding entities."
        else:
            msg = "This Query did not include any entities."
        raise AssertionError(msg)

    entities = set(requires[0])
    for require in requires[1:]:
        entities.intersection_update(require)
    for exclude in excludes:
        entities.difference_update(exclude)
    return entities


def _get_query(world: World, query: Query) -> set[Entity]:
    """Return the entities for the given query and world."""
    cache = _query_caches.get(world)
    if cache is not None:
        cached_entities = cache.queries.get(query)
        if cached_entities is not None:
            return cached_entities  # Found a cached query
    # Not in cache, build the cache and return the results

    cache = _query_caches.get(world)
    if cache is None:
        cache = _query_caches[world] = _QueryCache()

    cache.queries[query] = entities = _collect_query(world, query)

    for component in itertools.chain(query._all_of_components, query._none_of_components):
        cache.by_components[component].add(query)
    for tag in itertools.chain(query._all_of_tags, query._none_of_tags):
        cache.by_tags[tag].add(query)
    for relation in itertools.chain(query._all_of_relations, query._none_of_relations):
        cache.by_relations[relation].add(query)

    return entities


@attrs.define(frozen=True)
class Query:
    """A set of conditions used to lookup entities in a World."""

    _all_of_components: frozenset[_ComponentKey[object]] = frozenset()
    _none_of_components: frozenset[_ComponentKey[object]] = frozenset()
    _all_of_tags: frozenset[object] = frozenset()
    _none_of_tags: frozenset[object] = frozenset()
    _all_of_relations: frozenset[_RelationQuery] = frozenset()
    _none_of_relations: frozenset[_RelationQuery] = frozenset()

    def __attrs_post_init__(self) -> None:
        """Verify the current state."""
        assert self._all_of_components.isdisjoint(self._none_of_components)
        assert self._all_of_tags.isdisjoint(self._none_of_tags)
        assert self._all_of_relations.isdisjoint(self._none_of_relations)

    def all_of(
        self,
        components: Iterable[_ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[_RelationQuery] = (),
        _stacklevel: int = 1,
    ) -> Self:
        """Filter entities based on having all of the provided elements."""
        _check_suspicious_tags(tags, stacklevel=_stacklevel + 1)
        return self.__class__(
            self._all_of_components.union(components),
            self._none_of_components,
            self._all_of_tags.union(tags),
            self._none_of_tags,
            self._all_of_relations.union(relations),
            self._none_of_relations,
        )

    def none_of(
        self,
        components: Iterable[_ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[_RelationQuery] = (),
        _stacklevel: int = 1,
    ) -> Self:
        """Filter entities based on having none of the provided elements."""
        _check_suspicious_tags(tags, stacklevel=_stacklevel + 1)
        return self.__class__(
            self._all_of_components,
            self._none_of_components.union(components),
            self._all_of_tags,
            self._none_of_tags.union(tags),
            self._all_of_relations,
            self._none_of_relations.union(relations),
        )


class WorldQuery:
    """Collect a set of entities with the provided conditions."""

    def __init__(self, world: World) -> None:
        """Initialize a Query."""
        self.world: Final = world
        self._query = Query()

    def _get_entities(self, extra_components: AbstractSet[_ComponentKey[object]] = frozenset()) -> set[Entity]:
        return _get_query(self.world, self._query.all_of(components=extra_components))

    def all_of(
        self,
        components: Iterable[_ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[_RelationQuery] = (),
    ) -> Self:
        """Filter entities based on having all of the provided elements."""
        self._query = self._query.all_of(components=components, tags=tags, relations=relations, _stacklevel=2)
        return self

    def none_of(
        self,
        components: Iterable[_ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[_RelationQuery] = (),
    ) -> Self:
        """Filter entities based on having none of the provided elements."""
        self._query = self._query.none_of(components=components, tags=tags, relations=relations, _stacklevel=2)
        return self

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over the matching entities."""
        return iter(self._get_entities())

    @overload
    def __getitem__(self, key: tuple[_ComponentKey[_T1]]) -> Iterable[tuple[_T1]]:
        ...

    @overload
    def __getitem__(self, key: tuple[_ComponentKey[_T1], _ComponentKey[_T2]]) -> Iterable[tuple[_T1, _T2]]:
        ...

    @overload
    def __getitem__(
        self, key: tuple[_ComponentKey[_T1], _ComponentKey[_T2], _ComponentKey[_T3]]
    ) -> Iterable[tuple[_T1, _T2, _T3]]:
        ...

    @overload
    def __getitem__(
        self, key: tuple[_ComponentKey[_T1], _ComponentKey[_T2], _ComponentKey[_T3], _ComponentKey[_T4]]
    ) -> Iterable[tuple[_T1, _T2, _T3, _T4]]:
        ...

    @overload
    def __getitem__(
        self,
        key: tuple[_ComponentKey[_T1], _ComponentKey[_T2], _ComponentKey[_T3], _ComponentKey[_T4], _ComponentKey[_T5]],
    ) -> Iterable[tuple[_T1, _T2, _T3, _T4, _T5]]:
        ...

    @overload
    def __getitem__(self, key: tuple[_ComponentKey[object], ...]) -> Iterable[tuple[Any, ...]]:
        ...

    def __getitem__(self, key: tuple[_ComponentKey[object], ...]) -> Iterable[tuple[Any, ...]]:
        """Collect components from a query."""
        assert key is not None
        assert isinstance(key, tuple)

        Entity = tcod.ecs.entity.Entity

        entities = list(self._get_entities(set(key) - {Entity}))
        entity_components = []
        for component_key in key:
            if component_key is Entity:
                entity_components.append(entities)
                continue
            world_components = self.world._components_by_type[component_key]
            entity_components.append([world_components[entity] for entity in entities])
        return zip(*entity_components)
