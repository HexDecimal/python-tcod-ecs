"""Tools for querying Registry objects."""

from __future__ import annotations

import itertools
import warnings
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Protocol, TypeVar, overload
from weakref import WeakKeyDictionary, WeakSet

import attrs
from typing_extensions import Self

import tcod.ecs.entity
from tcod.ecs.constants import IsA

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from tcod.ecs.entity import Entity
    from tcod.ecs.registry import Registry
    from tcod.ecs.typing import ComponentKey, _RelationQuery

_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")


_query_caches: WeakKeyDictionary[Registry, _QueryCache] = WeakKeyDictionary()
"""The master table of cached queries."""


@attrs.define
class _QueryCache:
    """Main data structure for the query cache."""

    queries: dict[_Query, AbstractSet[Entity]] = attrs.field(factory=dict)
    """Table of cached queries."""
    by_components: defaultdict[ComponentKey[object], WeakSet[_Query]] = attrs.field(
        factory=lambda: defaultdict(WeakSet)
    )
    """Which queries depend on which components."""
    by_tags: defaultdict[object, WeakSet[_Query]] = attrs.field(factory=lambda: defaultdict(WeakSet))
    """Which queries depend on which tags."""
    by_relations: defaultdict[_RelationQuery, WeakSet[_Query]] = attrs.field(factory=lambda: defaultdict(WeakSet))
    """Which queries depend on which relations."""

    dependencies: dict[_Query, set[tuple[Registry, _Query]]] = attrs.field(factory=lambda: defaultdict(set))
    """Tracks which queries depend on the queries of the current registry.

    `dependencies[dependency] = {dependant}`
    """


def _drop_cached_query(cache: _QueryCache, query: _Query) -> None:
    """Drop a cached query and all of its dependant queries."""
    cache.queries.pop(query, None)
    for sub_registry, sub_query in cache.dependencies.pop(query, ()):
        _drop_cached_query(_query_caches[sub_registry], sub_query)


def _touch_component(registry: Registry, component: ComponentKey[object]) -> None:
    """Drop cached queries if a component change has invalidated them."""
    cache = _get_query_cache(registry)
    if component not in cache.by_components:
        return
    for touched_query in cache.by_components.pop(component, ()):
        _drop_cached_query(cache, touched_query)


def _touch_tag(registry: Registry, tag: object) -> None:
    """Drop cached queries if a tag change has invalidated them."""
    cache = _get_query_cache(registry)
    if tag not in cache.by_tags:
        return
    for touched_query in cache.by_tags.pop(tag, ()):
        _drop_cached_query(cache, touched_query)


def _touch_relations(registry: Registry, relations: Iterable[_RelationQuery]) -> None:
    """Drop cached queries if a relation change has invalidated them."""
    cache = _get_query_cache(registry)
    for relation in relations:
        if relation not in cache.by_relations:
            continue
        for touched_query in cache.by_relations.pop(relation, ()):
            _drop_cached_query(cache, touched_query)


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


def _fetch_relation_table(registry: Registry, relation: _RelationQuery) -> AbstractSet[Entity]:
    """Get the entity table for this relation.

    For simple cases where target/origin is `Entity | ...` this returns the set directly from the lookup table.

    For advanced cases `BoundQuery` this returns the subset of entities following the query condition.
    """
    if len(relation) == 2:  # noqa: PLR2004
        tag, target = relation
        if not isinstance(target, BoundQuery):
            return registry._relations_lookup.get((tag, target), frozenset())

        registry = target.registry
        return set().union(*(registry._relations_lookup.get((tag, entity), ()) for entity in target))
    origin, tag, target_none = relation
    if not isinstance(origin, BoundQuery):
        return registry._relations_lookup.get((origin, tag, target_none), frozenset())

    registry = origin.registry
    return set().union(*(registry._relations_lookup.get((entity, tag, None), ()) for entity in origin))


def _get_query_cache(registry: Registry) -> _QueryCache:
    """Return the global cache for the given registry, creating it if it does not exist."""
    cache = _query_caches.get(registry)
    if cache is None:
        cache = _query_caches[registry] = _QueryCache()
    return cache


def _get_query(registry: Registry, query: _Query) -> AbstractSet[Entity]:
    """Return the entities for the given query and registry."""
    cache = _get_query_cache(registry)
    if cache is not None:
        cached_entities = cache.queries.get(query)
        if cached_entities is not None:
            return cached_entities  # Found a cached query
    # Not in cache, build the cache and return the results

    cache.queries[query] = entities = query._compile(registry, cache)
    query._add_to_cache(registry, cache)
    return entities


def _normalize_query_relation(relation: _RelationQuery) -> _RelationQuery:
    """Normalize a relation query.

    This adds the inverse lookup to the sub-query so that this only matches entities which have a relation.
    """
    if len(relation) == 2:  # noqa: PLR2004
        tag, targets = relation
        if isinstance(targets, BoundQuery):  # (tag, targets)
            return tag, targets.all_of(relations=[(..., tag, None)])
        return relation
    origin, tag, _ = relation
    if isinstance(origin, BoundQuery):  # (origins, tag, None)
        return origin.all_of(relations=[(tag, ...)]), tag, None
    return relation


class _Query(Protocol):
    """Abstract query class."""

    def _add_to_cache(self, registry: Registry, cache: _QueryCache) -> None:
        """Add this query to the local cache."""
        ...

    def _compile(self, registry: Registry, cache: _QueryCache) -> AbstractSet[Entity]:
        """Compile the entities of this query, returning a set which must not be modified."""
        ...


@attrs.define(frozen=True)
class _QueryComponent:
    """Query all entities with the given component."""

    _component: ComponentKey[object]

    def _add_to_cache(self, registry: Registry, cache: _QueryCache) -> None:  # noqa: ARG002
        cache.by_components[self._component].add(self)

    def _compile(self, registry: Registry, cache: _QueryCache) -> AbstractSet[Entity]:  # noqa: ARG002
        return registry._components_by_type.get(self._component, {}).keys()


@attrs.define(frozen=True)
class _QueryTag:
    """Query all entities with the given tag."""

    _tag: object

    def _add_to_cache(self, registry: Registry, cache: _QueryCache) -> None:  # noqa: ARG002
        cache.by_tags[self._tag].add(self)

    def _compile(self, registry: Registry, cache: _QueryCache) -> AbstractSet[Entity]:  # noqa: ARG002
        return registry._tags_by_key.get(self._tag, set())


@attrs.define(frozen=True)
class _QueryRelation:
    """Query all entities with the given relation."""

    _relation: _RelationQuery = attrs.field(converter=_normalize_query_relation)

    def _add_to_cache(self, registry: Registry, cache: _QueryCache) -> None:
        """Add this query to the cache and mark it dependant on a registry query if the relation uses one."""

        def _get_registry_query() -> BoundQuery | None:
            """Return the bound query of a relation if it exists."""
            if isinstance(self._relation[0], BoundQuery):
                return self._relation[0]
            if isinstance(self._relation[-1], BoundQuery):
                return self._relation[-1]
            return None

        cache.by_relations[self._relation].add(self)
        w_query = _get_registry_query()
        if w_query is not None:
            _get_query_cache(w_query.registry).dependencies[w_query._query].add((registry, self))

    def _compile(self, registry: Registry, cache: _QueryCache) -> AbstractSet[Entity]:  # noqa: ARG002
        return _fetch_relation_table(registry, self._relation)


@attrs.define(frozen=True)
class _QueryLogicalAnd:
    """Combines queries so that entities match all of a set of queries except those excluded by another set.

    This is the typical ECS 'entity must include all of these components' query.
    """

    _all_of: frozenset[_Query] = frozenset()
    _none_of: frozenset[_Query] = frozenset()

    def __attrs_post_init__(self) -> None:
        """Verify the current state."""
        assert self._all_of.isdisjoint(self._none_of)

    def _add_to_cache(self, registry: Registry, cache: _QueryCache) -> None:
        for dependency in itertools.chain(self._all_of, self._none_of):
            cache.dependencies[dependency].add((registry, self))

    def _compile(self, registry: Registry, cache: _QueryCache) -> AbstractSet[Entity]:  # noqa: ARG002
        if len(self._all_of) == 1 and not self._none_of:  # Only one sub-query, simply return the results of it
            return _get_query(registry, next(iter(self._all_of)))  # Avoids an extra copy of a set
        requires = sorted(  # Place the smallest sets first to speed up intersections
            (_get_query(registry, q) for q in self._all_of), key=len
        )
        entities = set(requires[0])
        for required_set in requires[1:]:
            entities.intersection_update(required_set)
        for excluded_query in self._none_of:
            entities.difference_update(_get_query(registry, excluded_query))
        return entities

    def __and__(self, other: _Query) -> Self:
        if isinstance(other, _QueryLogicalAnd):
            return self.__class__(all_of=self._all_of | other._all_of, none_of=self._none_of | other._none_of)
        return self.__class__(all_of=self._all_of | {other}, none_of=self._none_of)


@attrs.define(frozen=True)
class _QueryLogicalOr:
    """Combines queries so that entities matching *any* of a set of queries are all included."""

    _any_of: frozenset[_Query] = frozenset()

    def _add_to_cache(self, registry: Registry, cache: _QueryCache) -> None:
        for dependency in self._any_of:
            cache.dependencies[dependency].add((registry, self))

    def _compile(self, registry: Registry, cache: _QueryCache) -> AbstractSet[Entity]:  # noqa: ARG002
        if len(self._any_of) == 1:  # If there is only one sub-query then simply return the results of it
            return _get_query(registry, next(iter(self._any_of)))  # Avoids an extra copy of a set
        entities: set[Entity] = set()
        entities.update(*(_get_query(registry, q) for q in self._any_of))
        return entities


@attrs.define(frozen=True)
class _QueryTraversalPropagation:
    """Propagate a query via a traversal key."""

    _sub_query: _Query
    """Query to propagate."""
    _traverse_keys: tuple[object, ...]
    """The key used for traversal relations."""
    _max_depth: int | None
    """Max depth to propagate to. None for infinite."""

    def _get_traverse_query(self) -> _QueryLogicalOr:
        """Return the relation query for the provided traverse key."""
        return _QueryLogicalOr(
            any_of=frozenset(_QueryRelation((..., traverse_key, None)) for traverse_key in self._traverse_keys)
        )

    def _add_to_cache(self, registry: Registry, cache: _QueryCache) -> None:
        cache.dependencies[self._sub_query].add((registry, self))
        cache.dependencies[self._get_traverse_query()].add((registry, self))

    def _compile(self, registry: Registry, cache: _QueryCache) -> AbstractSet[Entity]:  # noqa: ARG002
        cumulative_set = set(_get_query(registry, self._sub_query))  # All entities touched by this traversal
        relations_set = _get_query(
            registry, self._get_traverse_query()
        )  # The subset of entities which can propagate from
        unchecked_set = cumulative_set & relations_set  # Most recently touched entities which can propagate farther
        depth = 0
        while unchecked_set and (self._max_depth is None or depth < self._max_depth):
            depth += 1
            new_set: set[Entity] = set()
            empty_set: frozenset[Entity] = frozenset()
            for traverse_key in self._traverse_keys:
                for unchecked in unchecked_set:
                    new_set |= registry._relations_lookup.get((traverse_key, unchecked), empty_set)
            new_set -= cumulative_set
            cumulative_set |= new_set
            unchecked_set = new_set
        return cumulative_set


@attrs.define(frozen=True)
class BoundQuery:
    """Collect a set of entities with the provided conditions.

    This query is bound to a specific registry.
    """

    registry: Registry
    _query: _Query = attrs.field(factory=_QueryLogicalAnd)

    @property
    def world(self) -> Registry:
        """Deprecated alias for registry.

        .. deprecated:: Unreleased
            Use :any:`registry` instead.
        """
        if __debug__:
            warnings.warn("Use '.registry' instead of '.world'", DeprecationWarning, stacklevel=2)
        return self.registry

    def get_entities(self) -> AbstractSet[Entity]:
        """Return entities matching the current query as a read-only set.

        This is useful for post-processing the results of a query using set operations.

        .. versionadded:: 4.4
        """
        return _get_query(self.registry, self._query)

    def __bool__(self) -> bool:
        """Return True if any entity matches this query."""
        return bool(self.get_entities())

    @staticmethod
    def __as_queries(
        components: Iterable[ComponentKey[object]] = (),
        tags: Iterable[object] = (),
        relations: Iterable[_RelationQuery] = (),
        traverse: Iterable[object] = (IsA,),
        depth: int | None = None,
    ) -> Iterator[_Query]:
        """Convert parameters into queries."""
        traverse = tuple(traverse)
        yield from (_QueryTraversalPropagation(_QueryComponent(component), traverse, depth) for component in components)
        yield from (_QueryTraversalPropagation(_QueryTag(tag), traverse, depth) for tag in tags)
        yield from (_QueryTraversalPropagation(_QueryRelation(relations), traverse, depth) for relations in relations)

    def all_of(
        self,
        components: Iterable[ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[_RelationQuery] = (),
        traverse: Iterable[object] = (IsA,),
        depth: int | None = None,
    ) -> Self:
        """Filter entities based on having all of the provided elements."""
        _check_suspicious_tags(tags, stacklevel=2)
        return self.__class__(
            self.registry,
            _QueryLogicalAnd(all_of=frozenset(self.__as_queries(components, tags, relations, traverse, depth)))
            & self._query,
        )

    def none_of(
        self,
        components: Iterable[ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[_RelationQuery] = (),
        traverse: Iterable[object] = (IsA,),
        depth: int | None = None,
    ) -> Self:
        """Filter entities based on having none of the provided elements."""
        _check_suspicious_tags(tags, stacklevel=2)
        return self.__class__(
            self.registry,
            _QueryLogicalAnd(none_of=frozenset(self.__as_queries(components, tags, relations, traverse, depth)))
            & self._query,
        )

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over the matching entities."""
        return iter(self.get_entities())

    @overload
    def __getitem__(self, key: tuple[ComponentKey[_T1]]) -> Iterable[tuple[_T1]]: ...

    @overload
    def __getitem__(self, key: tuple[ComponentKey[_T1], ComponentKey[_T2]]) -> Iterable[tuple[_T1, _T2]]: ...

    @overload
    def __getitem__(
        self, key: tuple[ComponentKey[_T1], ComponentKey[_T2], ComponentKey[_T3]]
    ) -> Iterable[tuple[_T1, _T2, _T3]]: ...

    @overload
    def __getitem__(
        self, key: tuple[ComponentKey[_T1], ComponentKey[_T2], ComponentKey[_T3], ComponentKey[_T4]]
    ) -> Iterable[tuple[_T1, _T2, _T3, _T4]]: ...

    @overload
    def __getitem__(
        self,
        key: tuple[ComponentKey[_T1], ComponentKey[_T2], ComponentKey[_T3], ComponentKey[_T4], ComponentKey[_T5]],
    ) -> Iterable[tuple[_T1, _T2, _T3, _T4, _T5]]: ...

    @overload
    def __getitem__(self, key: tuple[ComponentKey[object], ...]) -> Iterable[tuple[Any, ...]]: ...

    def __getitem__(self, key: tuple[ComponentKey[object], ...]) -> Iterable[tuple[Any, ...]]:
        """Collect components from a query."""
        assert key is not None
        assert isinstance(key, tuple)

        Entity = tcod.ecs.entity.Entity  # noqa: N806

        entities = list(self.all_of(components=set(key) - {Entity}).get_entities())
        entity_components = []
        for component_key in key:
            if component_key is Entity:
                entity_components.append(entities)
                continue
            registry_components = self.registry._components_by_type[component_key]
            entity_components.append([registry_components[entity] for entity in entities])
        return zip(*entity_components)


WorldQuery = BoundQuery
