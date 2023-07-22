"""A type-hinted Entity Component System based on Python dictionaries and sets."""
from __future__ import annotations

import sys
import warnings
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    AbstractSet,
    Any,
    DefaultDict,
    Dict,
    Final,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    MutableSet,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)
from weakref import WeakKeyDictionary, WeakValueDictionary

import attrs
from typing_extensions import Self

import tcod.ecs._converter
from tcod.ecs import _version

if TYPE_CHECKING:
    from _typeshed import SupportsKeysAndGetItem

if sys.version_info >= (3, 10):  # pragma: no cover
    from types import EllipsisType
else:  # pragma: no cover
    EllipsisType = Any

__version__ = _version.__version__

T = TypeVar("T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")
_ComponentKey = Union[Type[T], Tuple[object, Type[T]]]
"""ComponentKey is plain `type` or tuple `(tag, type)`."""


def abstract_component(cls: type[T]) -> type[T]:
    """Register class `cls` as an abstract component and return it.

    .. deprecated:: 3.1
        This decorator is deprecated since abstract components should always be explicit.
    """
    warnings.warn(
        "This decorator is deprecated since abstract components should always be explicit.",
        FutureWarning,
        stacklevel=2,
    )
    cls._TCOD_BASE_COMPONENT = cls  # type: ignore[attr-defined]
    return cls


_entity_table: WeakKeyDictionary[World, WeakValueDictionary[object, Entity]] = WeakKeyDictionary()
"""A weak table of worlds and unique identifiers to entity objects.

This table is used to that non-unique Entity's won't create a new object and thus will always share identities.

_entity_table[world][uid] = entity
"""


class Entity:
    """A unique entity in a world.

    Example::

        >>> import tcod.ecs
        >>> world = tcod.ecs.World()  # Create a new world
        >>> world.new_entity()  # Create a new entity
        <Entity(uid=object at ...)>
        >>> entity = world["entity"]  # Get an entity from a specific identifier
        >>> other_entity = world["other"]
    """  # Changes here should be reflected in conftest.py

    __slots__ = ("world", "uid", "__weakref__")

    world: Final[World]  # type:ignore[misc]  # https://github.com/python/mypy/issues/5774
    """The :any:`World` this entity belongs to."""
    uid: Final[object]  # type:ignore[misc]
    """This entities unique identifier."""

    def __new__(cls, world: World, uid: object = object) -> Entity:
        """Return a unique entity for the given `world` and `uid`.

        If an entity already exists with a matching `world` and `uid` then that entity is returned.

        The `uid` default of `object` will create an instance of :any:`object` as the `uid`.
        An entity created this way will never match or collide with an existing entity.

        Example::

            >>> world = World()
            >>> Entity(world, "foo")
            <Entity(uid='foo')>
            >>> Entity(world, "foo") is Entity(world, "foo")
            True
            >>> Entity(world) is Entity(world)
            False
        """
        if uid is object:
            uid = object()
        try:
            table = _entity_table[world]
        except KeyError:
            table = WeakValueDictionary()
            _entity_table[world] = table
        try:
            return table[uid]
        except KeyError:
            pass
        self = super().__new__(cls)
        self.world = world  # type:ignore[misc]  # https://github.com/python/mypy/issues/5774
        self.uid = uid  # type:ignore[misc]
        _entity_table[world][uid] = self
        return self

    @property
    def components(self) -> EntityComponents:
        """Access an entities components.

        Example::

            >>> entity.components[str] = "foo"  # Assign component
            >>> entity.components[("name", str)] = "my_name" # Assign named component
            >>> entity.components |= {  # Update components in-place
            ...     ("hp", int): 10,
            ...     ("attack", int): 4,
            ...     ("defense", int): 1,
            ... }
            >>> ("name", str) in entity.components
            True
            >>> {str, ("name", str)}.issubset(entity.components.keys())
            True
            >>> list(world.Q.all_of(components=[str]))  # Query components
            [<Entity(uid='entity')>]
            >>> list(world.Q[tcod.ecs.Entity, str, ("name", str)])  # Query zip components
            [(<Entity(uid='entity')>, 'foo', 'my_name')]
        """
        return EntityComponents(self)

    @components.setter
    def components(self, value: EntityComponents) -> None:
        assert value.entity is self

    @property
    def tags(self) -> EntityTags:
        """Access an entities tags.

        Example::

            >>> entity.tags.add("tag") # Add tag
            >>> "tag" in entity.tags  # Check tag
            True
            >>> list(world.Q.all_of(tags=["tag"]))  # Query tags
            [<Entity(uid='entity')>]
            >>> entity.tags.discard("tag")
            >>> entity.tags |= {"IsPortable", "CanBurn", "OnFire"}  # Supports in-place syntax
            >>> {"CanBurn", "OnFire"}.issubset(entity.tags)
            True
            >>> entity.tags -= {"OnFire"}
            >>> {"CanBurn", "OnFire"}.issubset(entity.tags)
            False
        """
        return EntityTags(self)

    @tags.setter
    def tags(self, value: EntityTags) -> None:
        assert value.entity is self

    @property
    def relation_components(self) -> EntityComponentRelations:
        """Access an entities relation components.

        Example::

            >>> entity.relation_components[str][other_entity] = "foo" # Assign component to relation
            >>> entity.relation_components[("distance", int)][other_entity] = 42 # Also works for named components
            >>> other_entity in entity.relation_components[str]
            True
            >>> list(world.Q.all_of(relations=[(str, other_entity)]))
            [<Entity(uid='entity')>]
            >>> list(world.Q.all_of(relations=[(str, ...)]))
            [<Entity(uid='entity')>]
            >>> list(world.Q.all_of(relations=[(entity, str, None)]))
            [<Entity(uid='other')>]
            >>> list(world.Q.all_of(relations=[(..., str, None)]))
            [<Entity(uid='other')>]
        """
        return EntityComponentRelations(self)

    @property
    def relation_tag(self) -> EntityRelationsExclusive:
        """Access an entities exclusive relations.

        Example::

            >>> entity.relation_tag["ChildOf"] = other_entity  # Assign relation
            >>> list(world.Q.all_of(relations=[("ChildOf", other_entity)]))  # Get children of other_entity
            [<Entity(uid='entity')>]
            >>> list(world.Q.all_of(relations=[(entity, "ChildOf", None)]))  # Get parents of entity
            [<Entity(uid='other')>]
            >>> del entity.relation_tag["ChildOf"]
        """
        return EntityRelationsExclusive(self)

    @property
    def relation_tags(self) -> EntityRelationsExclusive:
        """Access an entities exclusive relations.

        .. deprecated:: 3.2
            This attribute was renamed to :any:`relation_tag`.
        """
        warnings.warn("The '.relation_tags' attribute has been renamed to '.relation_tag'", FutureWarning, stacklevel=2)
        return EntityRelationsExclusive(self)

    @property
    def relation_tags_many(self) -> EntityRelations:
        """Access an entities many-to-many relations.

        Example::

            >>> entity.relation_tags_many["KnownBy"].add(other_entity)  # Assign relation
        """
        return EntityRelations(self)

    def _set_name(self, value: object, stacklevel: int = 1) -> None:
        warnings.warn(
            "The name feature has been deprecated and will be removed.",
            FutureWarning,
            stacklevel=stacklevel + 1,
        )
        old_name = self.name
        if old_name is not None:  # Remove self from names
            del self.world._names_by_name[old_name]
            del self.world._names_by_entity[self]

        if value is not None:  # Add self to names
            old_entity = self.world._names_by_name.get(value)
            if old_entity is not None:  # Remove entity with old name, name will be overwritten
                del self.world._names_by_entity[old_entity]
            self.world._names_by_name[value] = self
            self.world._names_by_entity[self] = value

    @property
    def name(self) -> object:
        """The unique name of this entity or None.

        You may assign a new name, but if an entity of the world already has that name then it will lose it.

        .. deprecated:: 3.1
            This feature has been deprecated.
        """
        return self.world._names_by_entity.get(self)

    @name.setter
    def name(self, value: object) -> None:
        self._set_name(value, stacklevel=2)

    def __repr__(self) -> str:
        """Return a representation of this entity.

        Example::

            >>> world.new_entity()
            <Entity(uid=object at ...)>
            >>> world["foo"]
            <Entity(uid='foo')>
        """
        uid_str = f"object at 0x{id(self.uid):X}" if self.uid.__class__ == object else repr(self.uid)
        items = [f"{self.__class__.__name__}(uid={uid_str})"]
        name = self.name
        if name is not None:  # Switch to older style
            items = [self.__class__.__name__, f"name={name!r}"]
        return f"<{' '.join(items)}>"

    def __reduce__(self) -> tuple[type[Entity], tuple[World, object]]:
        """Pickle this Entity.

        Note that any pickled entity will include the world it belongs to and all the entities of that world.
        """
        return self.__class__, (self.world, self.uid)

    def _force_remap(self, new_uid: object) -> None:
        """Remap this Entity to a new uid, both and old and new uid's will use this entity."""
        _entity_table[self.world][new_uid] = self
        self.uid = new_uid  # type: ignore[misc]


class EntityComponents(MutableMapping[Union[Type[Any], Tuple[object, Type[Any]]], Any]):
    """A proxy attribute to access an entities components like a dictionary.

    See :any:`Entity.components`.
    """

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity

    def set(self, value: object, *, _stacklevel: int = 1) -> None:
        """Assign or overwrite a component, automatically deriving the key.

        .. deprecated:: 3.1
            Setting values without an explicit key has been deprecated.
        """
        warnings.warn(
            "Setting values without an explicit key has been deprecated.",
            FutureWarning,
            stacklevel=_stacklevel + 1,
        )
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
        return self.entity.world._components_by_entity[self.entity][key]  # type: ignore[no-any-return]

    def __setitem__(self, key: _ComponentKey[T], value: T) -> None:
        """Assign a component to an entity."""
        assert self.__assert_key(key)
        self.entity.world._components_by_entity[self.entity][key] = value
        self.entity.world._components_by_type[key][self.entity] = value

    def __delitem__(self, key: type[object] | tuple[object, type[object]]) -> None:
        """Delete a component from an entity."""
        assert self.__assert_key(key)

        del self.entity.world._components_by_entity[self.entity][key]
        if not self.entity.world._components_by_entity[self.entity]:
            del self.entity.world._components_by_entity[self.entity]

        del self.entity.world._components_by_type[key][self.entity]
        if not self.entity.world._components_by_type[key]:
            del self.entity.world._components_by_type[key]

    def __contains__(self, key: _ComponentKey[object]) -> bool:  # type: ignore[override]
        """Return True if this entity has the provided component."""
        return key in self.entity.world._components_by_entity.get(self.entity, ())

    def __iter__(self) -> Iterator[_ComponentKey[Any]]:
        """Iterate over the component types belonging to this entity."""
        return iter(self.entity.world._components_by_entity.get(self.entity, ()))

    def __len__(self) -> int:
        """Return the number of components belonging to this entity."""
        return len(self.entity.world._components_by_entity.get(self.entity, ()))

    def update_values(self, values: Iterable[object], *, _stacklevel: int = 1) -> None:
        """Add or overwrite multiple components inplace, deriving the keys from the values.

        .. deprecated:: 3.1
            Setting values without an explicit key has been deprecated.
        """
        for value in values:
            self.set(value, _stacklevel=_stacklevel + 1)

    def by_name_type(self, name_type: type[_T1], component_type: type[_T2]) -> Iterator[tuple[_T1, type[_T2]]]:
        """Iterate over all of an entities component keys with a specific (name_type, component_type) combination.

        .. versionadded:: 3.0

        .. deprecated:: 3.1
            This method has been deprecated. Iterate over items instead.
        """
        warnings.warn("This method has been deprecated. Iterate over items instead.", FutureWarning, stacklevel=2)
        # Naive implementation until I feel like optimizing it
        for key in self:
            if not isinstance(key, tuple):
                continue
            key_name, key_component = key
            if key_component is component_type and isinstance(key_name, name_type):
                yield key_name, key_component

    def __ior__(
        self, value: SupportsKeysAndGetItem[_ComponentKey[Any], Any] | Iterable[tuple[_ComponentKey[Any], Any]]
    ) -> Self:
        """Update components in-place.

        .. versionadded:: 3.4
        """
        self.update(value)
        return self

    def get(self, __key: _ComponentKey[T], __default: T | None = None) -> T | None:
        """Return a component, returns None or a default value when the component is missing."""
        try:
            return self[__key]
        except KeyError:
            return __default

    def setdefault(self, __key: _ComponentKey[T], __default: T) -> T:  # type: ignore[override]
        """Assign a default value if a component is missing, then returns the current value."""
        try:
            return self[__key]
        except KeyError:
            self[__key] = __default
            return __default


class EntityTags(MutableSet[Any]):
    """A proxy attribute to access an entities tags like a set.

    See :any:`Entity.tags`.
    """

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

    def __ior__(self, other: AbstractSet[object]) -> Self:
        """Add tags in-place.

        .. versionadded:: 3.3
        """
        for to_add in other:
            self.add(to_add)
        return self

    def __isub__(self, other: AbstractSet[Any]) -> Self:
        """Remove tags in-place.

        .. versionadded:: 3.3
        """
        for to_discard in other:
            self.discard(to_discard)
        return self


class EntityRelationsMapping(MutableSet[Entity]):
    """A proxy attribute to access entity relation targets like a set.

    See :any:`Entity.relation_tags_many`.
    """

    __slots__ = ("entity", "key")

    def __init__(self, entity: Entity, key: object) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity
        self.key: Final = key
        assert key not in {None, Ellipsis}

    def add(self, target: Entity) -> None:
        """Add a relation target to this tag."""
        world = self.entity.world
        world._relation_tags_by_entity[self.entity][self.key].add(target)

        world._relations_lookup[(self.key, target)].add(self.entity)
        world._relations_lookup[(self.key, ...)].add(self.entity)
        world._relations_lookup[(self.entity, self.key, None)].add(target)
        world._relations_lookup[(..., self.key, None)].add(target)

    def discard(self, target: Entity) -> None:
        """Discard a relation target from this tag."""
        world = self.entity.world

        world._relation_tags_by_entity[self.entity][self.key].discard(target)
        if not world._relation_tags_by_entity[self.entity][self.key]:
            del world._relation_tags_by_entity[self.entity][self.key]
            if not world._relation_tags_by_entity[self.entity]:
                del world._relation_tags_by_entity[self.entity]

        world._relations_lookup[(self.key, target)].discard(self.entity)
        if not world._relations_lookup[(self.key, target)]:
            del world._relations_lookup[(self.key, target)]

        world._relations_lookup[(self.key, ...)].discard(self.entity)
        if not world._relations_lookup[(self.key, ...)]:
            del world._relations_lookup[(self.key, ...)]

        world._relations_lookup[(self.entity, self.key, None)].discard(target)
        if not world._relations_lookup[(self.entity, self.key, None)]:
            del world._relations_lookup[(self.entity, self.key, None)]

        world._relations_lookup[(..., self.key, None)].discard(target)
        if not world._relations_lookup[(..., self.key, None)]:
            del world._relations_lookup[(..., self.key, None)]

    def __contains__(self, target: Entity) -> bool:  # type: ignore[override]
        """Return True if this relation contains the given value."""
        return bool(self.entity.world._relations_lookup.get((self.key, target), ()))

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over this relation tags targets."""
        by_entity = self.entity.world._relation_tags_by_entity.get(self.entity)
        return iter(by_entity.get(self.key, ())) if by_entity is not None else iter(())

    def __len__(self) -> int:
        """Return the number of targets for this relation tag."""
        by_entity = self.entity.world._relation_tags_by_entity.get(self.entity)
        return len(by_entity.get(self.key, ())) if by_entity is not None else 0


class EntityRelations(MutableMapping[object, EntityRelationsMapping]):
    """A proxy attribute to access entity relations like a dict of sets.

    See :any:`Entity.relation_tags_many`.
    """

    __slots__ = ("entity",)

    def __init__(self, entity: Entity) -> None:
        """Initialize this attribute for the given entity."""
        self.entity: Final = entity

    def __getitem__(self, key: object) -> EntityRelationsMapping:
        """Return the relation mapping for a tag."""
        return EntityRelationsMapping(self.entity, key)

    def __setitem__(self, key: object, values: Iterable[Entity]) -> None:
        """Overwrite the targets of a relation tag with the new values."""
        assert not isinstance(values, Entity), "Did you mean `entity.relations[key] = (target,)`?"
        mapping = EntityRelationsMapping(self.entity, key)
        mapping.clear()
        for v in values:
            mapping.add(v)

    def __delitem__(self, key: object) -> None:
        """Clear the relation tags of an entity.

        This does not remove relation tags towards this entity.
        """
        self[key].clear()

    def __iter__(self) -> Iterator[Any]:
        """Iterate over the unique relation tags of this entity."""
        return iter(self.entity.world._relation_tags_by_entity.get(self.entity, {}).keys())

    def __len__(self) -> int:
        """Return the number of unique relation tags this entity has."""
        return len(self.entity.world._relation_tags_by_entity.get(self.entity, {}))


class EntityRelationsExclusive(MutableMapping[object, Entity]):
    """A proxy attribute to access entity relations exclusively.

    See :any:`Entity.relation_tag`.
    """

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
    """An entity-component mapping to access the relation target component objects.

    See :any:`Entity.relation_components`.
    """

    __slots__ = ("entity", "key")

    def __init__(self, entity: Entity, key: _ComponentKey[T]) -> None:
        """Initialize this attribute for the given entity."""
        assert isinstance(entity, Entity), entity
        self.entity: Final = entity
        self.key: _ComponentKey[T] = key

    def __getitem__(self, target: Entity) -> T:
        """Return the component related to a target entity."""
        return self.entity.world._relation_components_by_entity[self.entity][self.key][target]  # type: ignore[no-any-return]

    def __setitem__(self, target: Entity, component: T) -> None:
        """Assign a component to the target entity."""
        world = self.entity.world
        if target in world._relation_components_by_entity[self.entity][self.key] is not None:
            del self[target]
        world._relation_components_by_entity[self.entity][self.key][target] = component

        world._relations_lookup[(self.key, target)] = {self.entity}
        world._relations_lookup[(self.key, ...)].add(self.entity)
        world._relations_lookup[(self.entity, self.key, None)] = {target}
        world._relations_lookup[(..., self.key, None)].add(target)

    def __delitem__(self, target: Entity) -> None:
        """Delete a component assigned to the target entity."""
        world = self.entity.world
        del world._relation_components_by_entity[self.entity][self.key][target]
        if not world._relation_components_by_entity[self.entity][self.key]:
            del world._relation_components_by_entity[self.entity][self.key]
        if not world._relation_components_by_entity[self.entity]:
            del world._relation_components_by_entity[self.entity]

        world._relations_lookup[(self.key, target)].discard(self.entity)
        if not world._relations_lookup[(self.key, target)]:
            del world._relations_lookup[(self.key, target)]

        world._relations_lookup[(self.key, ...)].discard(self.entity)
        if not world._relations_lookup[(self.key, ...)]:
            del world._relations_lookup[(self.key, ...)]

        world._relations_lookup[(self.entity, self.key, None)].discard(target)
        if not world._relations_lookup[(self.entity, self.key, None)]:
            del world._relations_lookup[(self.entity, self.key, None)]

        world._relations_lookup[(..., self.key, None)].discard(target)
        if not world._relations_lookup[(..., self.key, None)]:
            del world._relations_lookup[(..., self.key, None)]

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over the targets with assigned components."""
        by_entity = self.entity.world._relation_components_by_entity.get(self.entity)
        return iter(()) if by_entity is None else iter(by_entity.get(self.key, ()))

    def __len__(self) -> int:
        """Return the count of targets for this component relation."""
        by_entity = self.entity.world._relation_components_by_entity.get(self.entity)
        return 0 if by_entity is None else len(by_entity.get(self.key, ()))


class EntityComponentRelations:
    """Proxy to access the component relations of an entity.

    See :any:`Entity.relation_components`.
    """

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

    def __contains__(self, key: _ComponentKey[object]) -> bool:
        """Return True if this entity contains a relation component for this component key."""
        return bool(EntityComponentRelationMapping(self.entity, key))


def _defaultdict_of_set() -> defaultdict[_T1, set[_T2]]:
    """Return a new defaultdict of sets."""
    return defaultdict(set)


def _defaultdict_of_dict() -> defaultdict[_T1, dict[_T2, _T3]]:
    """Return a new defaultdict of dicts."""
    return defaultdict(dict)


def _components_by_entity_from(
    by_type: defaultdict[_ComponentKey[object], dict[Entity, Any]]
) -> defaultdict[Entity, dict[_ComponentKey[object], Any]]:
    """Return the component lookup table from the components sparse-set."""
    by_entity: defaultdict[Entity, dict[_ComponentKey[object], Any]] = defaultdict(dict)
    for component_key, components in by_type.items():
        for entity, component in components.items():
            by_entity[entity][component_key] = component
    return by_entity


def _tags_by_key_from_tags_by_entity(by_entity: defaultdict[Entity, set[object]]) -> defaultdict[object, set[Entity]]:
    """Return the tag lookup table from the tags sparse-set."""
    tags_by_key = defaultdict(set)
    for entity, tags in by_entity.items():
        for tag in tags:
            tags_by_key[tag].add(entity)
    return tags_by_key


def _relations_lookup_from(
    tags_by_entity: defaultdict[Entity, defaultdict[object, set[Entity]]],
    components_by_entity: defaultdict[Entity, defaultdict[_ComponentKey[object], dict[Entity, Any]]],
) -> defaultdict[tuple[Any, Entity | EllipsisType] | tuple[Entity | EllipsisType, Any, None], set[Entity]]:
    """Return the relation lookup table from the relations sparse-sets."""
    relations_lookup: defaultdict[
        tuple[Any, Entity | EllipsisType] | tuple[Entity | EllipsisType, Any, None], set[Entity]
    ] = defaultdict(set)
    for entity, tags in tags_by_entity.items():
        for tag, targets in tags.items():
            for target in targets:
                relations_lookup[(tag, ...)].add(target)
                relations_lookup[(tag, entity)].add(target)
                relations_lookup[(target, tag, None)].add(entity)
                relations_lookup[(..., tag, None)].add(entity)
    for entity, components in components_by_entity.items():
        for component_key, target_components in components.items():
            for target in target_components:
                relations_lookup[(component_key, ...)].add(target)
                relations_lookup[(component_key, entity)].add(target)
                relations_lookup[(target, component_key, None)].add(entity)
                relations_lookup[(..., component_key, None)].add(entity)

    return relations_lookup


@attrs.define(eq=False)
class World:
    """A container for entities and components."""

    _components_by_entity: defaultdict[Entity, dict[_ComponentKey[object], Any]] = attrs.field(
        init=False, factory=lambda: defaultdict(dict)
    )
    """Random access entity components.

    dict[Entity][ComponentKey] = component_instance
    """
    _components_by_type: defaultdict[_ComponentKey[object], dict[Entity, Any]] = attrs.field(
        init=False, factory=lambda: defaultdict(dict)
    )
    """Query table entity components.

    dict[ComponentKey] = {entities_with_component}
    """

    _tags_by_key: defaultdict[object, set[Entity]] = attrs.field(init=False, factory=lambda: defaultdict(set))
    """Query table entity tags.

    dict[tag] = {all_entities_with_tag}
    """
    _tags_by_entity: defaultdict[Entity, set[Any]] = attrs.field(init=False, factory=lambda: defaultdict(set))
    """Random access entity tags.

    dict[Entity] = {all_tags_for_entity}
    """

    _relation_tags_by_entity: defaultdict[Entity, defaultdict[object, set[Entity]]] = attrs.field(
        init=False, factory=lambda: defaultdict(_defaultdict_of_set)
    )
    """Random access tag multi-relations.

    dict[entity][tag] = {target_entities}
    """
    _relation_components_by_entity: defaultdict[
        Entity, defaultdict[_ComponentKey[object], dict[Entity, Any]]
    ] = attrs.field(init=False, factory=lambda: defaultdict(_defaultdict_of_dict))
    """Random access relations owning components.

    dict[entity][ComponentKey][target_entity] = component
    """
    _relations_lookup: defaultdict[
        tuple[Any, Entity | EllipsisType] | tuple[Entity | EllipsisType, Any, None], set[Entity]
    ] = attrs.field(init=False, factory=lambda: defaultdict(set))
    """Relations query table.  Tags and components are mixed together.

    ```
    Tag:
        dict[(tag, this_entity)] = {target_entities_for_entity}
        dict[(tag, None)] = {target_entities_for_tag}
        dict[(target_entity, tag, None)] = {origin_entities_for_target}
        dict[(None, tag, None)] = {all_origen_entities_for_tag}
    Component:
        dict[(ComponentKey, target_entity)] = {origin_entities}
        dict[(ComponentKey, None)] = {all_origin_entities}
        dict[(origin_entity, ComponentKey, None)] = {target_entities}
        dict[(None, ComponentKey, None)] = {all_target_entities}
    ```
    """

    _names_by_name: dict[object, Entity] = attrs.field(init=False, factory=dict)
    """Name query table.

    dict[name] = named_entity
    """
    _names_by_entity: dict[Entity, object] = attrs.field(init=False, factory=dict)
    """Name lookup table.

    dict[Entity] = entities_name
    """

    @property
    def global_(self) -> Entity:
        """A unique globally accessible entity.

        This can be used to store globally accessible components in the world itself without any extra boilerplate.
        Otherwise this entity is not special and will show up with other entities in queries, etc.

        This entity has a `uid` of `None` and may be accessed that way.
        This syntax my be better for globals in general since it can use any hashable object.

        .. versionadded:: 1.1

        Example::

            >>> world[None].components[("turn", int)] = 0
            >>> world[None].components[("turn", int)]
            0
        """
        warnings.warn(
            "The 'world.global_' attribute has been deprecated. Use 'world[None]' to access this entity.",
            FutureWarning,
            stacklevel=2,
        )
        return Entity(self, None)

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Unpickle this object and handle state migration."""
        global_: Entity | None = state.pop("global_", None)  # Migrate from version <=1.2.0

        # These attributes contain redundant data and will be removed
        REDUNDANT_ATTRIBUTES = frozenset(
            {
                "_components_by_entity",  # <=3.4.0
                "_tags_by_key",  # <=3.4.0
                "_relations_lookup",  # <=3.4.0
                "_names_by_entity",  # <=3.4.0
            }
        )
        for ignored in REDUNDANT_ATTRIBUTES:
            state.pop(ignored, None)

        converter = tcod.ecs._converter._get_converter()
        # Apply defaultdict types to unpickled dictionaries
        self._components_by_type = converter.structure(
            state.pop("_components_by_type"),
            DefaultDict[Any, Dict[Any, Any]],
        )
        self._components_by_entity = _components_by_entity_from(self._components_by_type)

        self._tags_by_entity = converter.structure(
            state.pop("_tags_by_entity"),
            DefaultDict[Any, Set[Any]],
        )
        self._tags_by_key = _tags_by_key_from_tags_by_entity(self._tags_by_entity)

        self._relation_tags_by_entity = converter.structure(
            state.pop("_relation_tags_by_entity"),
            DefaultDict[Any, DefaultDict[Any, Set[Any]]],
        )
        self._relation_components_by_entity = converter.structure(
            state.pop("_relation_components_by_entity"),
            DefaultDict[Any, DefaultDict[Any, Dict[Any, Any]]],
        )
        self._relations_lookup = _relations_lookup_from(
            self._relation_tags_by_entity, self._relation_components_by_entity
        )

        self._names_by_name = state.pop("_names_by_name")
        self._names_by_entity = {entity: name for name, entity in self._names_by_name.items()}

        if global_ is not None and global_.uid is not None:  # Migrate from version <=1.2.0
            global_._force_remap(None)

        if state:
            warnings.warn(f"These attributes were not unpacked {state.keys()}", RuntimeWarning, stacklevel=1)

    def __getstate__(self) -> dict[str, Any]:
        """Pickle this object."""
        converter = tcod.ecs._converter._get_converter()
        # Replace defaultdict types with plain dict when saving
        return {
            "_components_by_type": converter.structure(self._components_by_type, Dict[Any, Dict[Any, Any]]),
            "_tags_by_entity": converter.structure(self._tags_by_entity, Dict[Any, Any]),
            "_relation_tags_by_entity": converter.structure(self._relation_tags_by_entity, Dict[Any, Dict[Any, Any]]),
            "_relation_components_by_entity": converter.structure(
                self._relation_components_by_entity, Dict[Any, Dict[Any, Any]]
            ),
            "_names_by_name": self._names_by_name,
        }

    def __getitem__(self, uid: object) -> Entity:
        """Return an entity associated with a unique id.

        Example::

            >>> world = World()
            >>> foo = world["foo"]  # Referencing a new entity returns a new empty entity
            >>> foo is world["foo"]
            True
            >>> entity = world.new_entity()
            >>> world[entity.uid] is entity  # Anonymous entities can be referred to by their uid
            True
        """
        assert uid is not object, "This is reserved."
        return Entity(self, uid)

    @property
    def named(self) -> Mapping[object, Entity]:
        """A view into this worlds named entities.

        .. deprecated:: 3.1
            This feature has been deprecated.
        """
        return self._names_by_name

    def new_entity(
        self,
        components: Iterable[object] | Mapping[_ComponentKey[object], object] = (),
        *,
        name: object = None,
        tags: Iterable[Any] = (),
    ) -> Entity:
        """Create and return a new entity.

        .. versionchanged:: 3.1
            `components` can now take a mapping.

        Example::

            >>> entity = world.new_entity(
            ...     components={
            ...         ("name", str): "my name",
            ...         ("hp", int): 10,
            ...     },
            ...     tags=["Actor"],
            ... )
            >>> entity.components[("name", str)]
            'my name'
            >>> "Actor" in entity.tags
            True
        """
        entity = Entity(self)
        if isinstance(components, Mapping):
            entity.components.update(components)
        elif components:
            entity.components.update_values(components, _stacklevel=2)
        entity_tags = entity.tags
        for tag in tags:
            entity_tags.add(tag)
        if name is not None:
            entity._set_name(name, stacklevel=2)
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
        self._all_of_relations: set[tuple[Any, Entity | EllipsisType] | tuple[Entity | EllipsisType, Any, None]] = set()
        self._none_of_relations: set[
            tuple[Any, Entity | EllipsisType] | tuple[Entity | EllipsisType, Any, None]
        ] = set()

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
        # Place the smallest sets first to speed up intersections
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

    @staticmethod
    def __check_suspicious_tags(tags: Iterable[object], stacklevel: int = 2) -> None:
        if isinstance(tags, str):
            warnings.warn(
                "The tags parameter was given a str type."
                " This will split the string and check its individual letters as tags."
                "\nAdd square brackets 'tags=[tag]' to check for a single string tag. (Recommended)"
                "\nOtherwise use 'tags=list(tags)' to suppress this warning.",
                RuntimeWarning,
                stacklevel=stacklevel + 1,
            )

    def all_of(
        self,
        components: Iterable[_ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[tuple[object, Entity | EllipsisType] | tuple[Entity | EllipsisType, Any, None]] = (),
    ) -> Self:
        """Filter entities based on having all of the provided elements."""
        self.__check_suspicious_tags(tags)
        self._all_of_components.update(components)
        self._all_of_tags.update(tags)
        self._all_of_relations.update(relations)
        return self

    def none_of(
        self,
        components: Iterable[_ComponentKey[object]] = (),
        *,
        tags: Iterable[object] = (),
        relations: Iterable[tuple[object, Entity | EllipsisType] | tuple[Entity | EllipsisType, Any, None]] = (),
    ) -> Self:
        """Filter entities based on having none of the provided elements."""
        self.__check_suspicious_tags(tags)
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
