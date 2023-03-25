"""A partially implemented Entity Component System."""
from __future__ import annotations

__version__ = "0.0.1"
from typing import AbstractSet, Any, DefaultDict, Final, Iterable, Iterator, MutableMapping, MutableSet, Type, TypeVar

from typing_extensions import Self

T = TypeVar("T")


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
    def groups(self) -> EntityGroups:
        """Access a components groups."""
        return EntityGroups(self)


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


class EntityGroups(MutableSet[Any]):
    """A proxy attribute to access an entities groups."""

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity

    def add(self, group: object) -> None:
        """Add a group to the entity."""
        self.entity.world._groups_by_entity[self.entity].add(group)
        self.entity.world._groups_by_key[group].add(self.entity)

    def discard(self, group: object) -> None:
        """Discard a group from an entity."""
        self.entity.world._groups_by_entity[self.entity].discard(group)
        self.entity.world._groups_by_key[group].discard(self.entity)
        if not self.entity.world._groups_by_entity[self.entity]:
            del self.entity.world._groups_by_entity[self.entity]
        if not self.entity.world._groups_by_key[group]:
            del self.entity.world._groups_by_key[group]

    def __contains__(self, x: object) -> bool:
        """Return True if this entity belongs to a group."""
        return x in self.entity.world._groups_by_entity.get(self.entity, ())

    def __iter__(self) -> Iterator[Any]:
        """Iterate over this entities groups."""
        return iter(self.entity.world._groups_by_entity.get(self.entity, ()))

    def __len__(self) -> int:
        """Return the number of groups this entity belongs to."""
        return len(self.entity.world._groups_by_entity.get(self.entity, ()))


class World:
    """A container for entities and components."""

    def __init__(self) -> None:
        """Initialize a new world."""
        # Spare components as `v[ComponentType][Entity] = component`
        self._components_by_type: DefaultDict[type[Any], dict[Entity, Any]] = DefaultDict(dict)
        # Components types belonging to entities.
        self._components_by_entity: DefaultDict[Entity, set[type[Any]]] = DefaultDict(set)

        self._groups_by_key: DefaultDict[Any, set[Entity]] = DefaultDict(set)
        self._groups_by_entity: DefaultDict[Entity, set[Any]] = DefaultDict(set)

    def new_entity(
        self,
        components: Iterable[object] = (),
        *,
        groups: Iterable[Any] = (),
    ) -> Entity:
        """Create and return a new entity."""
        entity = Entity(self)
        entity.components.update_values(components)
        entity_groups = entity.groups
        for group in groups:
            entity_groups.add(group)
        return entity


class Query:
    """Collect a set of entities with the provided conditions."""

    def __init__(self, world: World) -> None:
        """Initialize a Query."""
        self.world: Final = world
        self.entities: set[Entity] | None = None

    def __apply_intersection(self, entities: AbstractSet[Entity]) -> Self:
        """Apply an interaction of a set."""
        if self.entities is None:
            self.entities = set(entities)
        else:
            self.entities &= entities
        return self

    def __apply_exclusion(self, entities: AbstractSet[Entity]) -> Self:
        """Exclude entities based on a set."""
        if self.entities is None:
            msg = "Query can not begin by excluding entities."
            raise AssertionError(msg)
        self.entities -= entities
        return self

    def all_of_components(self, *components: type[object]) -> Self:
        """Collect entities which have all of the given components."""
        for component in components:
            self.__apply_intersection(self.world._components_by_type.get(component, {}).keys())
        return self

    def none_of_components(self, *components: type[object]) -> Self:
        """Collect entities which have none of the given components."""
        for component in components:
            self.__apply_exclusion(self.world._components_by_type.get(component, {}).keys())
        return self

    def all_of_groups(self, *groups: type[object]) -> Self:
        """Collect entities which have all of the given groups."""
        for group in groups:
            self.__apply_intersection(self.world._groups_by_key.get(group, set()))
        return self

    def none_of_groups(self, *groups: type[object]) -> Self:
        """Collect entities which have none of the given groups."""
        for group in groups:
            self.__apply_exclusion(self.world._groups_by_key.get(group, set()))
        return self

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over the matching entities."""
        return iter(self.entities if self.entities is not None else iter(()))
