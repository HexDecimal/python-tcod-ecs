"""A type-hinted Entity Component System based on Python dictionaries and sets."""
from __future__ import annotations

__version__ = "0.2.0"
from functools import partial
from typing import (
    AbstractSet,
    Any,
    DefaultDict,
    Final,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    MutableSet,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from typing_extensions import Self

T = TypeVar("T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")
_ComponentKey = Union[Type[T], Tuple[object, Type[T]]]


def abstract_component(cls: type[T]) -> type[T]:
    """Register class `cls` as an abstract component and return it."""
    cls._TCOD_BASE_COMPONENT = cls  # type: ignore[attr-defined]
    return cls


class Entity:
    """A unique entity in a world."""

    __slots__ = ("world",)

    def __init__(self, world: World) -> None:
        """Initialize a new unique entity."""
        self.world: Final = world
        """The :any:`World` this entity belongs to."""

    @property
    def components(self) -> EntityComponents:
        """Access an entities components."""
        return EntityComponents(self)

    @property
    def tags(self) -> EntityTags:
        """Access an entities tags."""
        return EntityTags(self)

    @property
    def relation_components(self) -> EntityComponentRelations:
        """Access an entities relation components."""
        return EntityComponentRelations(self)

    @property
    def relation_tags(self) -> EntityRelationsExclusive:
        """Access an entities exclusive relations."""
        return EntityRelationsExclusive(self)

    @property
    def relation_tags_many(self) -> EntityRelations:
        """Access an entities many-to-many relations."""
        return EntityRelations(self)

    @property
    def name(self) -> object:
        """The unique name of this entity or None.

        You may assign a new name, but if an entity of the world already has that name then it will lose it.
        """
        return self.world._names_by_entity.get(self)

    @name.setter
    def name(self, value: object) -> None:
        old_name = self.name
        if old_name is not None:  # Remove self from names.
            del self.world._names_by_name[old_name]
            del self.world._names_by_entity[self]

        if value is not None:  # Add self to names.
            old_entity = self.world._names_by_name.get(value)
            if old_entity is not None:  # Remove entity with old name, name will be overwritten.
                del self.world._names_by_entity[old_entity]
            self.world._names_by_name[value] = self
            self.world._names_by_entity[self] = value

    def __repr__(self) -> str:
        """Return a representation of this entity."""
        items = [self.__class__.__name__]
        name = self.name
        items.append(f"0x{id(self):X}" if name is None else f"name={name!r}")
        return f"<{' '.join(items)}>"


class EntityComponents(MutableMapping[Union[Type[Any], Tuple[object, Type[Any]]], Any]):
    """A proxy attribute to access an entities components like a dictionary."""

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity

    def set(self, value: object) -> None:
        """Assign or overwrite a component, automatically deriving the key."""
        key = getattr(value, "_TCOD_BASE_COMPONENT", value.__class__)
        self[key] = value

    @staticmethod
    def __assert_key(key: _ComponentKey[Any]) -> bool:
        """Verify that abstract classes are accessed correctly."""
        if isinstance(key, tuple):
            key = key[1]
        assert (
            getattr(key, "_TCOD_BASE_COMPONENT", key) is key
        ), "Abstract components must be accessed via the base class."
        return True

    def __getitem__(self, key: _ComponentKey[T]) -> T:
        """Return a component belonging to this entity."""
        assert self.__assert_key(key)
        return self.entity.world._components_by_type[key][self.entity]  # type: ignore[no-any-return]

    def __setitem__(self, key: _ComponentKey[T], value: T) -> None:
        """Assign a component to an entity."""
        assert self.__assert_key(key)
        self.entity.world._components_by_type[key][self.entity] = value
        self.entity.world._components_by_entity[self.entity].add(key)

    def __delitem__(self, key: type[object] | tuple[object, type[object]]) -> None:
        """Delete a component from an entity."""
        assert self.__assert_key(key)

        del self.entity.world._components_by_type[key][self.entity]
        if not self.entity.world._components_by_type[key]:
            del self.entity.world._components_by_type[key]

        self.entity.world._components_by_entity[self.entity].remove(key)
        if not self.entity.world._components_by_entity[self.entity]:
            del self.entity.world._components_by_entity[self.entity]

    def __contains__(self, key: _ComponentKey[object]) -> bool:  # type: ignore[override]
        """Return True if this entity has the provided component."""
        return key in self.entity.world._components_by_entity.get(self.entity, ())

    def __iter__(self) -> Iterator[_ComponentKey[Any]]:
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
    """A proxy attribute to access an entities tags like a set."""

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
        if not self.entity.world._tags_by_entity[self.entity]:
            del self.entity.world._tags_by_entity[self.entity]

        self.entity.world._tags_by_key[tag].discard(self.entity)
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


class EntityRelationsMapping(MutableSet[Entity]):
    """A proxy attribute to access entity relation targets like a set."""

    __slots__ = ("entity", "key")

    def __init__(self, entity: Entity, key: object) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity
        self.key: Final = key
        assert key not in {None, Ellipsis}

    def add(self, target: Entity) -> None:
        """Add a relation target to this key."""
        world = self.entity.world
        world._relations_by_key[self.key][self.entity].add(target)

        world._relations_lookup[(self.key, target)].add(self.entity)
        world._relations_lookup[(self.key, None)].add(self.entity)
        world._relations_lookup[(self.entity, self.key, None)].add(target)
        world._relations_lookup[(None, self.key, None)].add(target)

    def discard(self, target: Entity) -> None:
        """Discard a relation target from this key."""
        world = self.entity.world

        world._relations_by_key[self.key][self.entity].discard(target)
        if not world._relations_by_key[self.key][self.entity]:
            del world._relations_by_key[self.key][self.entity]
            if not world._relations_by_key[self.key]:
                del world._relations_by_key[self.key]

        world._relations_lookup[(self.key, target)].discard(self.entity)
        if not world._relations_lookup[(self.key, target)]:
            del world._relations_lookup[(self.key, target)]

        world._relations_lookup[(self.key, None)].discard(self.entity)
        if not world._relations_lookup[(self.key, None)]:
            del world._relations_lookup[(self.key, None)]

        world._relations_lookup[(self.entity, self.key, None)].discard(target)
        if not world._relations_lookup[(self.entity, self.key, None)]:
            del world._relations_lookup[(self.entity, self.key, None)]

        world._relations_lookup[(None, self.key, None)].discard(target)
        if not world._relations_lookup[(None, self.key, None)]:
            del world._relations_lookup[(None, self.key, None)]

    def __contains__(self, target: Entity) -> bool:  # type: ignore[override]
        """Return True if this relation contains the given value."""
        return bool(self.entity.world._relations_lookup.get((self.key, target), ()))

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over this relations targets."""
        relations = self.entity.world._relations_by_key.get(self.key)
        return iter(relations.get(self.entity, ())) if relations is not None else iter(())

    def __len__(self) -> int:
        """Return the number of targets in this relation."""
        relations = self.entity.world._relations_by_key.get(self.key)
        return len(relations.get(self.entity, ())) if relations is not None else 0


class EntityRelations(MutableMapping[object, EntityRelationsMapping]):
    """A proxy attribute to access entity relations like a dict of sets."""

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity

    def __getitem__(self, key: object) -> EntityRelationsMapping:
        """Return the relation mapping for a key."""
        return EntityRelationsMapping(self.entity, key)

    def __setitem__(self, key: object, values: Iterable[Entity]) -> None:
        """Overwrite the targets of a relation key with the new values."""
        assert not isinstance(values, Entity), "Did you mean `entity.relations[key] = (target,)`?"
        mapping = EntityRelationsMapping(self.entity, key)
        mapping.clear()
        for v in values:
            mapping.add(v)

    def __delitem__(self, key: object) -> None:
        """Clear the relation targets of a relation key."""
        self[key].clear()

    def __iter__(self) -> Iterator[Any]:
        """Iterate over the keys of this entities relations."""
        # Slow!
        for key, value in self.entity.world._relations_by_key.items():
            if self.entity in value:
                yield key

    def __len__(self) -> int:
        """Return the number of relations this entity has."""
        return len(list(self.__iter__()))  # Slow!


class EntityRelationsExclusive(MutableMapping[object, Entity]):
    """A proxy attribute to access entity relations exclusively."""

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity

    def __getitem__(self, key: object) -> Entity:
        """Return the relation target for a key.

        If the relation has no target then raises KeyError.
        If the relation is not exclusive then raises ValueError.
        """
        values = tuple(EntityRelationsMapping(self.entity, key))
        if not values:
            raise KeyError(key)
        try:
            (target,) = values
        except ValueError:
            msg = "Entity relation has multiple targets but an exclusive value was expected."
            raise ValueError(msg) from None
        return target

    def __setitem__(self, key: object, target: Entity) -> None:
        """Set a relation exclusively to a new target."""
        mapping = EntityRelationsMapping(self.entity, key)
        mapping.clear()
        mapping.add(target)

    def __delitem__(self, key: object) -> None:
        """Clear the relation targets of a relation key."""
        EntityRelationsMapping(self.entity, key).clear()

    def __iter__(self) -> Iterator[Any]:
        """Iterate over the keys of this entities relations."""
        return EntityRelations(self.entity).__iter__()

    def __len__(self) -> int:
        """Return the number of relations this entity has."""
        return EntityRelations(self.entity).__len__()


class EntityComponentRelationMapping(Generic[T], MutableMapping[Entity, T]):
    """An entity-component mapping to access the relation target component objects.."""

    __slots__ = ("entity", "key")

    def __init__(self, entity: Entity, key: _ComponentKey[T]) -> None:
        """Initialize this attribute for the given entity."""
        assert isinstance(entity, Entity), entity
        self.entity: Final = entity
        self.key: _ComponentKey[T] = key

    def __getitem__(self, target: Entity) -> T:
        """Return the component related to a target entity."""
        return self.entity.world._relation_components[self.key][self.entity][target]  # type: ignore[no-any-return]

    def __setitem__(self, target: Entity, component: T) -> None:
        """Assign a component to the target entity."""
        world = self.entity.world
        if target in world._relation_components[self.key][self.entity] is not None:
            del self[target]
        world._relation_components[self.key][self.entity][target] = component

        world._relations_lookup[(self.key, target)] = {self.entity}
        world._relations_lookup[(self.key, None)].add(self.entity)
        world._relations_lookup[(self.entity, self.key, None)] = {target}
        world._relations_lookup[(None, self.key, None)].add(target)

    def __delitem__(self, target: Entity) -> None:
        """Delete a component assigned to the target entity."""
        world = self.entity.world
        del world._relation_components[self.key][self.entity][target]
        if not world._relation_components[self.key][self.entity]:
            del world._relation_components[self.key][self.entity]
        if not world._relation_components[self.key]:
            del world._relation_components[self.key]

        world._relations_lookup[(self.key, target)].discard(self.entity)
        if not world._relations_lookup[(self.key, target)]:
            del world._relations_lookup[(self.key, target)]

        world._relations_lookup[(self.key, None)].discard(self.entity)
        if not world._relations_lookup[(self.key, None)]:
            del world._relations_lookup[(self.key, None)]

        world._relations_lookup[(self.entity, self.key, None)].discard(self.entity)
        if not world._relations_lookup[(self.entity, self.key, None)]:
            del world._relations_lookup[(self.entity, self.key, None)]

        world._relations_lookup[(None, self.key, None)].discard(self.entity)
        if not world._relations_lookup[(None, self.key, None)]:
            del world._relations_lookup[(None, self.key, None)]

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over the targets with assigned components."""
        relations_by_type = self.entity.world._relation_components.get(self.key)
        return iter(()) if relations_by_type is None else iter(relations_by_type.get(self.entity, ()))

    def __len__(self) -> int:
        """Return the count of targets for this component relation."""
        relations_by_type = self.entity.world._relation_components.get(self.key)
        return 0 if relations_by_type is None else len(relations_by_type.get(self.entity, ()))


class EntityComponentRelations:
    """Proxy to access the component relations of an entity."""

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        assert isinstance(entity, Entity), entity
        self.entity: Final = entity

    def __getitem__(self, key: _ComponentKey[T]) -> EntityComponentRelationMapping[T]:
        """Access relations for this component key as a `{target: component}` dict-like object."""
        return EntityComponentRelationMapping(self.entity, key)

    def __delitem__(self, key: _ComponentKey[object]) -> None:
        """Remove all relations associated with this component key."""
        EntityComponentRelationMapping(self.entity, key).clear()


class World:
    """A container for entities and components."""

    def __init__(self) -> None:
        """Initialize a new world."""
        # Spare-set components.
        # ComponentKey is `type` or `(tag, type)`, see annotation.
        # dict[ComponentKey][Entity] = component_instance
        self._components_by_type: DefaultDict[_ComponentKey[object], dict[Entity, Any]] = DefaultDict(dict)
        # dict[Entity] = {component_keys_owned_by_entity}
        self._components_by_entity: DefaultDict[Entity, set[_ComponentKey[object]]] = DefaultDict(set)

        # Sparse-set tags.
        # dict[tag] = {all_entities_with_tag}
        self._tags_by_key: DefaultDict[object, set[Entity]] = DefaultDict(set)
        # dict[Entity] = {all_tags_for_entity}
        self._tags_by_entity: DefaultDict[Entity, set[Any]] = DefaultDict(set)

        # Sparse-set relations.
        # dict[tag][this_entity] = {target_entities_for_entity}
        self._relations_by_key: DefaultDict[object, DefaultDict[Entity, set[Entity]]] = DefaultDict(
            partial(DefaultDict, set)  # type: ignore[arg-type]
        )
        # Tag:
        # dict[(tag, this_entity)] = {target_entities_for_entity}
        # dict[(tag, None)] = {target_entities_for_tag}
        # dict[(target_entity, tag, None)] = {origin_entities_for_target}
        # dict[(None, tag, None)] = {all_origen_entities_for_tag}
        # Component:
        # dict[(ComponentKey, target_entity)] = {origin_entities}
        # dict[(ComponentKey, None)] = {all_origin_entities}
        # dict[(origin_entity, ComponentKey, None)] = {target_entities}
        # dict[(None, ComponentKey, None)] = {all_target_entities}
        self._relations_lookup: DefaultDict[
            tuple[Any, Entity | None] | tuple[Entity | None, Any, Entity | None], set[Entity]
        ] = DefaultDict(set)

        # Sparse-set relations owning components.
        # dict[ComponentKey][own_entity][target_entity] = component
        self._relation_components: DefaultDict[
            _ComponentKey[object], DefaultDict[Entity, dict[Entity, Any]]
        ] = DefaultDict(
            partial(DefaultDict, dict)  # type: ignore[arg-type]
        )

        # Named objects dictionary.
        # dict[name] = named_entity
        self._names_by_name: dict[object, Entity] = {}
        # dict[Entity] = entities_name
        self._names_by_entity: dict[Entity, object] = {}

    @property
    def named(self) -> Mapping[object, Entity]:
        """A view into this worlds named entities."""
        return self._names_by_name

    def new_entity(
        self,
        components: Iterable[object] = (),
        *,
        name: object = None,
        tags: Iterable[Any] = (),
    ) -> Entity:
        """Create and return a new entity."""
        entity = Entity(self)
        entity.components.update_values(components)
        entity_tags = entity.tags
        for tag in tags:
            entity_tags.add(tag)
        entity.name = name
        return entity

    @property
    def Q(self) -> Query:
        """Start a new Query for this world.

        Alias for ``tcod.ecs.Query(world)``.
        """
        return Query(self)


class Query:
    """Collect a set of entities with the provided conditions."""

    def __init__(self, world: World) -> None:
        """Initialize a Query."""
        self.world: Final = world

        self._all_of_components: set[_ComponentKey[object]] = set()
        self._none_of_components: set[_ComponentKey[object]] = set()
        self._all_of_tags: set[object] = set()
        self._none_of_tags: set[object] = set()
        self._all_of_relations: set[tuple[Any, Entity | None] | tuple[Entity | None, Any, Entity | None]] = set()
        self._none_of_relations: set[tuple[Any, Entity | None] | tuple[Entity | None, Any, Entity | None]] = set()

    def __iter_requires(self, extra_components: AbstractSet[_ComponentKey[object]]) -> Iterator[AbstractSet[Entity]]:
        collect_components = self._all_of_components | extra_components
        for component in collect_components:
            yield self.world._components_by_type.get(component, {}).keys()
        for tag in self._all_of_tags:
            yield self.world._tags_by_key.get(tag, set())
        for relation in self._all_of_relations:
            yield self.world._relations_lookup.get(relation, set())

    def __iter_excludes(self) -> Iterator[AbstractSet[Entity]]:
        for component in self._none_of_components:
            yield self.world._components_by_type.get(component, {}).keys()
        for tag in self._none_of_tags:
            yield self.world._tags_by_key.get(tag, set())
        for relation in self._none_of_relations:
            yield self.world._relations_lookup.get(relation, set())

    def _get_entities(self, extra_components: AbstractSet[_ComponentKey[object]] = frozenset()) -> set[Entity]:
        # Place the smallest sets first to speed up intersections.
        requires = sorted(self.__iter_requires(extra_components), key=len)
        excludes = list(self.__iter_excludes())

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

    def all_of(
        self,
        components: Iterable[_ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[tuple[object, Entity | None] | tuple[Entity | None, Any, Entity | None]] = (),
    ) -> Self:
        """Filter entities based on having all of the provided elements."""
        self._all_of_components.update(components)
        self._all_of_tags.update(tags)
        self._all_of_relations.update(relations)
        return self

    def none_of(
        self,
        components: Iterable[_ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[tuple[object, Entity | None] | tuple[Entity | None, Any, Entity | None]] = (),
    ) -> Self:
        """Filter entities based on having none of the provided elements."""
        self._none_of_components.update(components)
        self._none_of_tags.update(tags)
        self._none_of_relations.update(relations)
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

        entities = list(self._get_entities(set(key) - {Entity}))
        entity_components = []
        for component_key in key:
            if component_key is Entity:
                entity_components.append(entities)
                continue
            world_components = self.world._components_by_type[component_key]
            entity_components.append([world_components[entity] for entity in entities])
        return zip(*entity_components)
