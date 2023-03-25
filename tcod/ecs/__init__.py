"""A partially implemented Entity Component System."""
from __future__ import annotations

__version__ = "0.0.1"
from typing import (
    AbstractSet,
    Any,
    DefaultDict,
    Final,
    Iterable,
    Iterator,
    MutableMapping,
    MutableSet,
    Type,
    TypeVar,
    overload,
)

from typing_extensions import Self

T = TypeVar("T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")


def abstract_component(cls: type[T]) -> type[T]:
    """Register class `cls` as an abstract component and return it."""
    cls._TCOD_BASE_COMPONENT = cls  # type: ignore[attr-defined]
    return cls


class Entity:
    """A unique entity in a world."""

    __slots__ = ("world", "__weakref__")

    def __init__(self, world: World) -> None:
        """Initialize a new unique entity."""
        self.world: Final = world
        """The :any:`World` this entity belongs to."""

    @property
    def components(self) -> EntityComponents:
        """Access a components components."""
        return EntityComponents(self)

    @property
    def tags(self) -> EntityTags:
        """Access a components tags."""
        return EntityTags(self)


class EntityComponents(MutableMapping[Type[Any], Any]):
    """A proxy attribute to access an entities components."""

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity

    def set(self, value: object) -> None:
        """Assign or overwrite a component, automatically deriving the key."""
        key = getattr(value, "_TCOD_BASE_COMPONENT", value.__class__)
        self[key] = value

    @staticmethod
    def __assert_key(key: type[Any]) -> bool:
        """Verify that abstract classes are accessed correctly."""
        assert (
            getattr(key, "_TCOD_BASE_COMPONENT", key) is key
        ), "Abstract components must be accessed via the base class."
        return True

    def __getitem__(self, key: type[T]) -> T:
        """Return a component belonging to this entity."""
        assert self.__assert_key(key)
        return self.entity.world._components_by_type[key][self.entity]  # type: ignore[no-any-return]

    def __setitem__(self, key: type[T], value: T) -> None:
        """Assign a component to an entity."""
        assert self.__assert_key(key)
        self.entity.world._components_by_type[key][self.entity] = value
        self.entity.world._components_by_entity[self.entity].add(key)

    def __delitem__(self, key: type[object]) -> None:
        """Delete a component from an entity."""
        assert self.__assert_key(key)
        del self.entity.world._components_by_type[key][self.entity]
        self.entity.world._components_by_entity[self.entity].remove(key)
        if not self.entity.world._components_by_type[key]:
            del self.entity.world._components_by_type[key]
        if not self.entity.world._components_by_entity[self.entity]:
            del self.entity.world._components_by_entity[self.entity]

    def __contains__(self, key: type[Any]) -> bool:  # type: ignore[override]
        """Return True if this entity has the provided component."""
        return key in self.entity.world._components_by_entity.get(self.entity, ())

    def __iter__(self) -> Iterator[type[Any]]:
        """Iterate over the component types belonging to this entity."""
        return iter(self.entity.world._components_by_entity.get(self.entity, ()))

    def __len__(self) -> int:
        """Return the number of components belonging to this entity."""
        return len(self.entity.world._components_by_entity.get(self.entity, ()))

    def update_values(self, values: Iterable[object]) -> None:
        """Add or overwrite multiple components inplace, deriving the keys from the values."""
        for value in values:
            self.set(value)


class EntityTags(MutableSet[Any]):
    """A proxy attribute to access an entities tags."""

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity

    def add(self, tag: object) -> None:
        """Add a tag to the entity."""
        self.entity.world._tags_by_entity[self.entity].add(tag)
        self.entity.world._tags_by_key[tag].add(self.entity)

    def discard(self, tag: object) -> None:
        """Discard a tag from an entity."""
        self.entity.world._tags_by_entity[self.entity].discard(tag)
        self.entity.world._tags_by_key[tag].discard(self.entity)
        if not self.entity.world._tags_by_entity[self.entity]:
            del self.entity.world._tags_by_entity[self.entity]
        if not self.entity.world._tags_by_key[tag]:
            del self.entity.world._tags_by_key[tag]

    def __contains__(self, x: object) -> bool:
        """Return True if this entity has the given tag."""
        return x in self.entity.world._tags_by_entity.get(self.entity, ())

    def __iter__(self) -> Iterator[Any]:
        """Iterate over this entities tags."""
        return iter(self.entity.world._tags_by_entity.get(self.entity, ()))

    def __len__(self) -> int:
        """Return the number of tags this entity has."""
        return len(self.entity.world._tags_by_entity.get(self.entity, ()))


class World:
    """A container for entities and components."""

    def __init__(self) -> None:
        """Initialize a new world."""
        # Spare components as `v[ComponentType][Entity] = component`
        self._components_by_type: DefaultDict[type[Any], dict[Entity, Any]] = DefaultDict(dict)
        # Components types belonging to entities.
        self._components_by_entity: DefaultDict[Entity, set[type[Any]]] = DefaultDict(set)

        self._tags_by_key: DefaultDict[Any, set[Entity]] = DefaultDict(set)
        self._tags_by_entity: DefaultDict[Entity, set[Any]] = DefaultDict(set)

    def new_entity(
        self,
        components: Iterable[object] = (),
        *,
        tags: Iterable[Any] = (),
    ) -> Entity:
        """Create and return a new entity."""
        entity = Entity(self)
        entity.components.update_values(components)
        entity_tags = entity.tags
        for tag in tags:
            entity_tags.add(tag)
        return entity


class Query:
    """Collect a set of entities with the provided conditions."""

    def __init__(self, world: World) -> None:
        """Initialize a Query."""
        self.world: Final = world

        self._all_of_components: set[type[object]] = set()
        self._none_of_components: set[type[object]] = set()
        self._all_of_tags: set[object] = set()
        self._none_of_tags: set[object] = set()

    def _get_entities(self, extra_components: AbstractSet[type[object]] = frozenset()) -> set[Entity]:
        collect_components = self._all_of_components | extra_components
        requires: list[AbstractSet[Entity]] = []
        excludes: list[AbstractSet[Entity]] = []
        for component in collect_components:
            requires.append(self.world._components_by_type.get(component, {}).keys())
        for tag in self._all_of_tags:
            requires.append(self.world._tags_by_key.get(tag, set()))

        for component in self._none_of_components:
            excludes.append(self.world._components_by_type.get(component, {}).keys())
        for tag in self._none_of_tags:
            excludes.append(self.world._tags_by_key.get(tag, set()))

        if not requires:
            if excludes:
                msg = "A Query can not function only excluding entities."
            else:
                msg = "This Query did not include any entities."
            raise AssertionError(msg)

        requires.sort(key=lambda x: len(x))  # Place the smallest sets first to speed up intersections.
        entities = set(requires[0])
        for require in requires[1:]:
            entities.intersection_update(require)
        for exclude in excludes:
            entities.difference_update(exclude)
        return entities

    def all_of(
        self,
        components: Iterable[type[object]] = (),
        *,
        tags: Iterable[object] = (),
    ) -> Self:
        """Filter entities based on having all of the provided elements."""
        self._all_of_components.update(components)
        self._all_of_tags.update(tags)
        return self

    def none_of(
        self,
        components: Iterable[type[object]] = (),
        *,
        tags: Iterable[object] = (),
    ) -> Self:
        """Filter entities based on having none of the provided elements."""
        self._none_of_components.update(components)
        self._none_of_tags.update(tags)
        return self

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over the matching entities."""
        return iter(self._get_entities())

    @overload
    def __getitem__(self, key: type[_T1]) -> Iterable[tuple[_T1]]:
        ...

    @overload
    def __getitem__(self, key: tuple[type[_T1]]) -> Iterable[tuple[_T1]]:
        ...

    @overload
    def __getitem__(self, key: tuple[type[_T1], type[_T2]]) -> Iterable[tuple[_T1, _T2]]:
        ...

    @overload
    def __getitem__(self, key: tuple[type[_T1], type[_T2], type[_T3]]) -> Iterable[tuple[_T1, _T2, _T3]]:
        ...

    @overload
    def __getitem__(
        self, key: tuple[type[_T1], type[_T2], type[_T3], type[_T4]]
    ) -> Iterable[tuple[_T1, _T2, _T3, _T4]]:
        ...

    @overload
    def __getitem__(
        self, key: tuple[type[_T1], type[_T2], type[_T3], type[_T4], type[_T5]]
    ) -> Iterable[tuple[_T1, _T2, _T3, _T4, _T5]]:
        ...

    @overload
    def __getitem__(self, key: tuple[type[object], ...] | type[object]) -> Iterable[tuple[Any, ...]]:
        ...

    def __getitem__(self, key: tuple[type[object], ...] | type[object]) -> Iterable[tuple[Any, ...]]:
        """Collect components from a query."""
        assert key is not None
        if not isinstance(key, tuple):
            key = (key,)

        entities = list(self._get_entities(set(key) - {Entity}))
        entity_components = []
        for component_type in key:
            if component_type is Entity:
                entity_components.append(entities)
                continue
            world_components = self.world._components_by_type[component_type]
            entity_components.append([world_components[entity] for entity in entities])
        return zip(*entity_components)
