"""Tools for querying  World objects."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, AbstractSet, Iterable, Iterator

import attrs
from typing_extensions import Self

from tcod.ecs.typing import _ComponentKey, _RelationQuery

if TYPE_CHECKING:
    from tcod.ecs import Entity, World


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


def _fetch_query(world: World, query: Query) -> set[Entity]:
    """Return the entities for the given query and world."""
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
