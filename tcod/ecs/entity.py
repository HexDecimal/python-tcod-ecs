"""Entity management and interface tools."""

from __future__ import annotations

import warnings
from typing import (
    TYPE_CHECKING,
    Any,
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
from weakref import WeakKeyDictionary, WeakValueDictionary

import attrs
from typing_extensions import Self

import tcod.ecs.callbacks
import tcod.ecs.query
from tcod.ecs.constants import IsA
from tcod.ecs.typing import ComponentKey

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from _typeshed import SupportsKeysAndGetItem

    from tcod.ecs.registry import Registry


T = TypeVar("T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")

_entity_table: WeakKeyDictionary[Registry, WeakValueDictionary[object, Entity]] = WeakKeyDictionary()
"""A weak table of registries and unique identifiers to entity objects.

This table is used to that non-unique Entity's won't create a new object and thus will always share identities.

_entity_table[registry][uid] = entity
"""


class Entity:
    """A unique entity in a registry.

    Example::

        >>> import tcod.ecs
        >>> registry = tcod.ecs.Registry()  # Create a new registry
        >>> registry.new_entity()  # Create a new entity
        <Entity(uid=object at ...)>
        >>> entity = registry["entity"]  # Get an entity from a specific identifier
        >>> other_entity = registry["other"]
    """  # Changes here should be reflected in conftest.py

    __slots__ = ("registry", "uid", "__weakref__")

    registry: Final[Registry]  # type:ignore[misc]  # https://github.com/python/mypy/issues/5774
    """The :any:`Registry` this entity belongs to."""
    uid: Final[object]  # type:ignore[misc]
    """This entities unique identifier."""

    @property
    def world(self) -> Registry:
        """Deprecated alias for registry.

        .. deprecated:: Unreleased
            Use :any:`registry` instead.
        """
        if __debug__:
            warnings.warn("Use '.registry' instead of '.world'", DeprecationWarning, stacklevel=2)
        return self.registry

    def __new__(cls, registry: Registry, uid: object = object) -> Entity:  # noqa: PYI034
        """Return a unique entity for the given `registry` and `uid`.

        If an entity already exists with a matching `registry` and `uid` then that entity is returned.

        The `uid` default of `object` will create an instance of :any:`object` as the `uid`.
        An entity created this way will never match or collide with an existing entity.

        Example::

            >>> registry = tcod.ecs.Registry()
            >>> Entity(registry, "foo")
            <Entity(uid='foo')>
            >>> Entity(registry, "foo") is Entity(registry, "foo")
            True
            >>> Entity(registry) is Entity(registry)
            False
        """
        if uid is object:
            uid = object()
        try:
            table = _entity_table[registry]
        except KeyError:
            table = WeakValueDictionary()
            _entity_table[registry] = table
        try:
            return table[uid]
        except KeyError:
            pass
        self = super().__new__(cls)
        self.registry = registry  # type:ignore[misc]  # https://github.com/python/mypy/issues/5774
        self.uid = uid  # type:ignore[misc]
        _entity_table[registry][uid] = self
        return self

    def clear(self) -> None:
        """Deletes all of this entities components, tags, and relations.

        Relations targeting this component are still kept.

        .. versionadded:: 4.2.0
        """
        self.components.clear()
        self.tags.clear()
        self.relation_tags_many.clear()
        self.relation_components.clear()

    def instantiate(self) -> Self:
        """Return a new entity which inherits the components, tags, and relations of this entity.

        This creates a new unique entity and assigns an :any:`IsA` relationship with `self` to the new entity.
        The :any:`IsA` relation is the only data this new entity directly holds.

        Example::

            # 'child = entity.instantiate()' is equivalent to the following:
            >>> from tcod.ecs import IsA
            >>> child = registry[object()]  # New unique entity
            >>> child.relation_tag[IsA] = entity  # Configure IsA relation

        Example::

            >>> parent = registry.new_entity()
            >>> parent.components[str] = "baz"
            >>> child = parent.instantiate()
            >>> child.components[str]  # Inherits components from parent
            'baz'
            >>> parent.components[str] = "foo"
            >>> child.components[str]  # Changes in parent and reflected in children
            'foo'
            >>> child.components[str] += "bar"  # In-place assignment operators will copy-on-write immutable objects
            >>> child.components[str]
            'foobar'
            >>> parent.components[str]
            'foo'
            >>> del child.components[str]
            >>> child.components[str]
            'foo'

            # Note: Mutable objects have the same gotchas as in other Python examples:
            >>> from typing import List, Tuple
            >>> parent.components[List[str]] = ["foo"]
            >>> child.components[List[str]] += ["bar"]  # Will modify list in-place then assign that same list to child
            >>> parent.components[List[str]]  # Parent references the same list as the child now
            ['foo', 'bar']
            >>> child.components[List[str]]
            ['foo', 'bar']
            >>> parent.components[List[str]] is child.components[List[str]]
            True
            >>> parent.components[Tuple[str, ...]] = ("foo",)  # Prefer immutable types to avoid the above issue
            >>> child.components[Tuple[str, ...]] += ("bar",)
            >>> child.components[Tuple[str, ...]]
            ('foo', 'bar')
            >>> parent.components[Tuple[str, ...]]
            ('foo',)

        .. versionadded:: 5.0
        """
        new_entity = self.__class__(self.registry, object())
        new_entity.relation_tag[IsA] = self
        return new_entity

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
            >>> list(registry.Q.all_of(components=[str]))  # Query components
            [<Entity(uid='entity')>]
            >>> list(registry.Q[tcod.ecs.Entity, str, ("name", str)])  # Query zip components
            [(<Entity(uid='entity')>, 'foo', 'my_name')]
        """
        return EntityComponents(self, (IsA,))

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
            >>> list(registry.Q.all_of(tags=["tag"]))  # Query tags
            [<Entity(uid='entity')>]
            >>> entity.tags.discard("tag")
            >>> entity.tags |= {"IsPortable", "CanBurn", "OnFire"}  # Supports in-place syntax
            >>> {"CanBurn", "OnFire"}.issubset(entity.tags)
            True
            >>> entity.tags -= {"OnFire"}
            >>> {"CanBurn", "OnFire"}.issubset(entity.tags)
            False
        """
        return EntityTags(self, (IsA,))

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
            >>> list(registry.Q.all_of(relations=[(str, other_entity)]))
            [<Entity(uid='entity')>]
            >>> list(registry.Q.all_of(relations=[(str, ...)]))
            [<Entity(uid='entity')>]
            >>> list(registry.Q.all_of(relations=[(entity, str, None)]))
            [<Entity(uid='other')>]
            >>> list(registry.Q.all_of(relations=[(..., str, None)]))
            [<Entity(uid='other')>]
        """
        return EntityComponentRelations(self, (IsA,))

    @property
    def relation_tag(self) -> EntityRelationsExclusive:
        """Access an entities exclusive relations.

        Example::

            >>> entity.relation_tag["ChildOf"] = other_entity  # Assign relation
            >>> list(registry.Q.all_of(relations=[("ChildOf", other_entity)]))  # Get children of other_entity
            [<Entity(uid='entity')>]
            >>> list(registry.Q.all_of(relations=[(entity, "ChildOf", None)]))  # Get parents of entity
            [<Entity(uid='other')>]
            >>> del entity.relation_tag["ChildOf"]
        """
        return EntityRelationsExclusive(self, (IsA,))

    @property
    def relation_tags(self) -> EntityRelationsExclusive:
        """Access an entities exclusive relations.

        .. deprecated:: 3.2
            This attribute was renamed to :any:`relation_tag`.
        """
        warnings.warn("The '.relation_tags' attribute has been renamed to '.relation_tag'", FutureWarning, stacklevel=2)
        return EntityRelationsExclusive(self, (IsA,))

    @property
    def relation_tags_many(self) -> EntityRelations:
        """Access an entities many-to-many relations.

        Example::

            >>> entity.relation_tags_many["KnownBy"].add(other_entity)  # Assign relation
        """
        return EntityRelations(self, (IsA,))

    def _set_name(self, value: object, stacklevel: int = 1) -> None:
        warnings.warn(
            "The name feature has been deprecated and will be removed.",
            FutureWarning,
            stacklevel=stacklevel + 1,
        )
        old_name = self.name
        if old_name is not None:  # Remove self from names
            del self.registry._names_by_name[old_name]
            del self.registry._names_by_entity[self]

        if value is not None:  # Add self to names
            old_entity = self.registry._names_by_name.get(value)
            if old_entity is not None:  # Remove entity with old name, name will be overwritten
                del self.registry._names_by_entity[old_entity]
            self.registry._names_by_name[value] = self
            self.registry._names_by_entity[self] = value

    @property
    def name(self) -> object:
        """The unique name of this entity or None.

        You may assign a new name, but if an entity of the registry already has that name then it will lose it.

        .. deprecated:: 3.1
            This feature has been deprecated.
        """
        return self.registry._names_by_entity.get(self)

    @name.setter
    def name(self, value: object) -> None:
        self._set_name(value, stacklevel=2)

    def __repr__(self) -> str:
        """Return a representation of this entity.

        Example::

            >>> registry.new_entity()
            <Entity(uid=object at ...)>
            >>> registry["foo"]
            <Entity(uid='foo')>
        """
        uid_str = f"object at 0x{id(self.uid):X}" if self.uid.__class__ is object else repr(self.uid)
        items = [f"{self.__class__.__name__}(uid={uid_str})"]
        name = self.name
        if name is not None:  # Switch to older style
            items = [self.__class__.__name__, f"name={name!r}"]
        return f"<{' '.join(items)}>"

    def __reduce__(self) -> tuple[type[Entity], tuple[Registry, object]]:
        """Pickle this Entity.

        Note that any pickled entity will include the registry it belongs to and all the entities of that registry.
        """
        return self.__class__, (self.registry, self.uid)

    def _force_remap(self, new_uid: object) -> None:
        """Remap this Entity to a new uid, both and old and new uid's will use this entity."""
        _entity_table[self.registry][new_uid] = self
        self.uid = new_uid  # type: ignore[misc]


def _traverse_entities(start: Entity, traverse_parents: tuple[object, ...]) -> Iterator[Entity]:
    """Iterate over all entities this one inherits from, including itself."""
    if not traverse_parents:
        yield start
        return
    traverse_parents = traverse_parents[::-1]
    visited = {start}
    stack = [start]
    _relation_tags_by_entity = start.registry._relation_tags_by_entity
    while stack:
        entity = stack.pop()
        yield entity
        entity_relations = _relation_tags_by_entity.get(entity)
        if entity_relations is None:
            continue
        for traverse_key in traverse_parents:
            relations = entity_relations.get(traverse_key)
            if relations is None:
                continue
            assert len(relations) == 1
            next_entity = next(iter(relations))
            if next_entity in visited:
                continue
            visited.add(next_entity)
            stack.append(next_entity)


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityComponents(MutableMapping[Union[Type[Any], Tuple[object, Type[Any]]], Any]):
    """A proxy attribute to access an entities components like a dictionary.

    See :any:`Entity.components`.
    """

    entity: Entity
    traverse: tuple[object, ...]

    def __call__(self, *, traverse: Iterable[object]) -> Self:
        """Update this view with alternative parameters, such as a specific traversal relation.

        .. versionadded:: 5.0
        """
        return self.__class__(self.entity, tuple(traverse))

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
        key = value.__class__
        self[key] = value

    @staticmethod
    def __assert_key(key: ComponentKey[Any]) -> bool:
        """Verify that abstract classes are accessed correctly."""
        if isinstance(key, tuple):
            key = key[1]
        return True

    def __getitem__(self, key: ComponentKey[T]) -> T:
        """Return a component belonging to this entity, or an indirect parent."""
        assert self.__assert_key(key)
        _components_by_entity = self.entity.registry._components_by_entity
        for entity in _traverse_entities(self.entity, self.traverse):
            try:
                return _components_by_entity[entity][key]  # type: ignore[no-any-return]
            except KeyError:  # noqa: PERF203
                pass
        raise KeyError(key)

    def __setitem__(self, key: ComponentKey[T], value: T) -> None:
        """Assign a component directly to an entity."""
        assert self.__assert_key(key)

        old_value = self.entity.registry._components_by_entity[self.entity].get(key)

        if old_value is None:
            tcod.ecs.query._touch_component(self.entity.registry, key)  # Component added

        self.entity.registry._components_by_entity[self.entity][key] = value
        self.entity.registry._components_by_type[key][self.entity] = value

        tcod.ecs.callbacks._on_component_changed(key, self.entity, old_value, value)

    def __delitem__(self, key: type[object] | tuple[object, type[object]]) -> None:
        """Delete a directly held component from an entity."""
        assert self.__assert_key(key)

        old_value = self.entity.registry._components_by_entity[self.entity].get(key)

        del self.entity.registry._components_by_entity[self.entity][key]
        if not self.entity.registry._components_by_entity[self.entity]:
            del self.entity.registry._components_by_entity[self.entity]

        del self.entity.registry._components_by_type[key][self.entity]
        if not self.entity.registry._components_by_type[key]:
            del self.entity.registry._components_by_type[key]

        tcod.ecs.query._touch_component(self.entity.registry, key)  # Component removed
        tcod.ecs.callbacks._on_component_changed(key, self.entity, old_value, None)

    def keys(self) -> AbstractSet[ComponentKey[object]]:  # type: ignore[override]
        """Return the components held by this entity, including inherited components."""
        _components_by_entity = self.entity.registry._components_by_entity
        if not self.traverse:
            return _components_by_entity.get(self.entity, {}).keys()
        set_: set[ComponentKey[object]] = set()
        return set_.union(
            *(_components_by_entity.get(entity, ()) for entity in _traverse_entities(self.entity, self.traverse))
        )

    def __contains__(self, key: ComponentKey[object]) -> bool:  # type: ignore[override]
        """Return True if this entity has the provided component."""
        _components_by_entity = self.entity.registry._components_by_entity
        return any(
            key in _components_by_entity.get(entity, ()) for entity in _traverse_entities(self.entity, self.traverse)
        )

    def __iter__(self) -> Iterator[ComponentKey[Any]]:
        """Iterate over the component types belonging to this entity."""
        return iter(self.keys())

    def __len__(self) -> int:
        """Return the number of components belonging to this entity."""
        return len(self.keys())

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

    @overload
    def __ior__(self, value: SupportsKeysAndGetItem[ComponentKey[Any], Any]) -> Self: ...

    @overload
    def __ior__(self, value: Iterable[tuple[ComponentKey[Any], Any]]) -> Self: ...

    def __ior__(
        self, value: SupportsKeysAndGetItem[ComponentKey[Any], Any] | Iterable[tuple[ComponentKey[Any], Any]]
    ) -> Self:
        """Update components in-place.

        .. versionadded:: 3.4
        """
        self.update(value)
        return self

    @overload
    def get(self, __key: ComponentKey[T]) -> T | None: ...
    @overload
    def get(self, __key: ComponentKey[T], __default: _T1) -> T | _T1: ...

    def get(self, __key: ComponentKey[T], __default: _T1 | None = None) -> T | _T1:
        """Return a component, returns None or a default value when the component is missing."""
        try:
            return self[__key]
        except KeyError:
            return __default  # type: ignore[return-value] # https://github.com/python/mypy/issues/3737

    def setdefault(self, __key: ComponentKey[T], __default: T) -> T:  # type: ignore[override]
        """Assign a default value if a component is missing, then returns the current value."""
        try:
            return self[__key]
        except KeyError:
            self[__key] = __default
            return __default


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityTags(MutableSet[Any]):
    """A proxy attribute to access an entities tags like a set.

    See :any:`Entity.tags`.
    """

    entity: Entity
    traverse: tuple[object, ...]

    def __call__(self, *, traverse: Iterable[object]) -> Self:
        """Update this view with alternative parameters, such as a specific traversal relation.

        .. versionadded:: 5.0
        """
        return self.__class__(self.entity, tuple(traverse))

    def add(self, tag: object) -> None:
        """Add a tag to the entity."""
        if tag in self.entity.registry._tags_by_entity[self.entity]:
            return  # Already has tag
        tcod.ecs.query._touch_tag(self.entity.registry, tag)  # Tag added

        self.entity.registry._tags_by_entity[self.entity].add(tag)
        self.entity.registry._tags_by_key[tag].add(self.entity)

    def discard(self, tag: object) -> None:
        """Discard a tag directly held by an entity."""
        if tag not in self.entity.registry._tags_by_entity[self.entity]:
            return  # Already doesn't have tag
        tcod.ecs.query._touch_tag(self.entity.registry, tag)  # Tag removed

        self.entity.registry._tags_by_entity[self.entity].discard(tag)
        if not self.entity.registry._tags_by_entity[self.entity]:
            del self.entity.registry._tags_by_entity[self.entity]

        self.entity.registry._tags_by_key[tag].discard(self.entity)
        if not self.entity.registry._tags_by_key[tag]:
            del self.entity.registry._tags_by_key[tag]

    def remove(self, tag: object) -> None:
        """Remove a tag directly held by an entity."""
        tags = self.entity.registry._tags_by_entity.get(self.entity)
        if tags is None or tag not in tags:
            raise KeyError(tag)
        self.discard(tag)

    def __contains__(self, x: object) -> bool:
        """Return True if this entity has the given tag."""
        _tags_by_entity = self.entity.registry._tags_by_entity
        return any(x in _tags_by_entity.get(entity, ()) for entity in _traverse_entities(self.entity, self.traverse))

    def _as_set(self) -> set[object]:
        """Return all tags inherited by traversal rules into a single set with no duplicates."""
        _tags_by_entity = self.entity.registry._tags_by_entity
        return set().union(
            *(_tags_by_entity.get(entity, ()) for entity in _traverse_entities(self.entity, self.traverse))
        )

    def __iter__(self) -> Iterator[Any]:
        """Iterate over this entities tags."""
        return iter(self._as_set())

    def __len__(self) -> int:
        """Return the number of tags this entity has."""
        return len(self._as_set())

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


def _relations_lookup_add(registry: Registry, origin: Entity, tag: object, target: Entity) -> None:
    """Add a relation tag/component to the lookup table and handle side effects."""
    registry._relations_lookup[(tag, target)].add(origin)
    registry._relations_lookup[(tag, ...)].add(origin)
    registry._relations_lookup[(origin, tag, None)].add(target)
    registry._relations_lookup[(..., tag, None)].add(target)
    tcod.ecs.query._touch_relations(registry, ((tag, target), (tag, ...), (origin, tag, None), (..., tag, None)))


def _relations_lookup_discard(registry: Registry, origin: Entity, tag: object, target: Entity) -> None:
    """Discard a relation tag/component from the lookup table and handle side effects."""
    registry._relations_lookup[(tag, target)].discard(origin)
    if not registry._relations_lookup[(tag, target)]:
        del registry._relations_lookup[(tag, target)]

        registry._relations_lookup[(..., tag, None)].discard(target)
        if not registry._relations_lookup[(..., tag, None)]:
            del registry._relations_lookup[(..., tag, None)]

    registry._relations_lookup[(origin, tag, None)].discard(target)
    if not registry._relations_lookup[(origin, tag, None)]:
        del registry._relations_lookup[(origin, tag, None)]

        registry._relations_lookup[(tag, ...)].discard(origin)
        if not registry._relations_lookup[(tag, ...)]:
            del registry._relations_lookup[(tag, ...)]

    tcod.ecs.query._touch_relations(registry, ((tag, target), (tag, ...), (origin, tag, None), (..., tag, None)))


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityRelationsMapping(MutableSet[Entity]):
    """A proxy attribute to access entity relation targets like a set.

    See :any:`Entity.relation_tags_many`.
    """

    entity: Entity
    key: object
    traverse: tuple[object, ...]

    if __debug__:

        def __attrs_post_init__(self) -> None:
            """Validate attributes."""
            assert self.key not in {None, Ellipsis}

    def add(self, target: Entity) -> None:
        """Add a relation target to this tag."""
        registry = self.entity.registry
        registry._relation_tags_by_entity[self.entity][self.key].add(target)

        _relations_lookup_add(registry, self.entity, self.key, target)

    def discard(self, target: Entity) -> None:
        """Discard a directly held relation target from this tag."""
        registry = self.entity.registry

        registry._relation_tags_by_entity[self.entity][self.key].discard(target)
        if not registry._relation_tags_by_entity[self.entity][self.key]:
            del registry._relation_tags_by_entity[self.entity][self.key]
            if not registry._relation_tags_by_entity[self.entity]:
                del registry._relation_tags_by_entity[self.entity]

        _relations_lookup_discard(registry, self.entity, self.key, target)

    def remove(self, target: Entity) -> None:
        """Remove a directly held relation target from this tag.

        This will raise KeyError of only an indirect relation target exists.
        """
        relations = self.entity.registry._relation_tags_by_entity.get(self.entity)
        if relations is None:
            raise KeyError(target)
        targets = relations.get(self.key)
        if targets is None or target not in targets:
            raise KeyError(target)
        self.discard(target)

    def __contains__(self, target: Entity) -> bool:  # type: ignore[override]
        """Return True if this relation contains the given value."""
        _relation_tags_by_entity = self.entity.registry._relation_tags_by_entity
        for entity in _traverse_entities(self.entity, self.traverse):
            by_entity = _relation_tags_by_entity.get(entity)
            if by_entity is None:
                continue
            if target in by_entity.get(self.key, ()):
                return True
        return False

    def _as_set(self) -> set[Entity]:
        """Return the combined targets of this mapping via traversal with duplicates removed."""
        _relation_tags_by_entity = self.entity.registry._relation_tags_by_entity
        results: set[Entity] = set()
        for entity in _traverse_entities(self.entity, self.traverse):
            by_entity = _relation_tags_by_entity.get(entity)
            if by_entity is None:
                continue
            results.update(by_entity.get(self.key, ()))
        return results

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over this relation tags targets."""
        yield from self._as_set()

    def __len__(self) -> int:
        """Return the number of targets for this relation tag."""
        return len(self._as_set())

    def clear(self) -> None:
        """Discard all targets for this tag relation."""
        by_entity = self.entity.registry._relation_tags_by_entity.get(self.entity)
        if by_entity is None:
            return
        for key in list(by_entity.get(self.key, ())):
            self.discard(key)


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityRelations(MutableMapping[object, EntityRelationsMapping]):
    """A proxy attribute to access entity relations like a dict of sets.

    See :any:`Entity.relation_tags_many`.
    """

    entity: Entity
    traverse: tuple[object, ...]

    def __call__(self, *, traverse: Iterable[object]) -> Self:
        """Update this view with alternative parameters, such as a specific traversal relation.

        .. versionadded:: 5.0
        """
        return self.__class__(self.entity, tuple(traverse))

    def __getitem__(self, key: object) -> EntityRelationsMapping:
        """Return the relation mapping for a tag."""
        return EntityRelationsMapping(self.entity, key, self.traverse)

    def __setitem__(self, key: object, values: Iterable[Entity]) -> None:
        """Overwrite the targets of a relation tag with the new values."""
        assert not isinstance(values, Entity), "Did you mean `entity.relations[key] = (target,)`?"
        mapping = EntityRelationsMapping(self.entity, key, self.traverse)
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
        _relation_tags_by_entity = self.entity.registry._relation_tags_by_entity
        empty_dict: dict[object, set[Entity]] = {}
        yield from set().union(
            *(
                _relation_tags_by_entity.get(entity, empty_dict).keys()
                for entity in _traverse_entities(self.entity, self.traverse)
            )
        )

    def __len__(self) -> int:
        """Return the number of unique relation tags this entity has."""
        return len(list(self.__iter__()))

    def clear(self) -> None:
        """Discard all tag relations from an entity."""
        for key in list(self.entity.registry._relation_tags_by_entity.get(self.entity, ())):
            del self[key]


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityRelationsExclusive(MutableMapping[object, Entity]):
    """A proxy attribute to access entity relations exclusively.

    See :any:`Entity.relation_tag`.
    """

    entity: Entity
    traverse: tuple[object, ...]

    def __call__(self, *, traverse: Iterable[object]) -> Self:
        """Update this view with alternative parameters, such as a specific traversal relation.

        .. versionadded:: 5.0
        """
        return self.__class__(self.entity, tuple(traverse))

    def __getitem__(self, key: object) -> Entity:
        """Return the relation target for a key.

        If the relation has no target then raises KeyError.
        If the relation is not exclusive then raises ValueError.
        """
        _relation_tags_by_entity = self.entity.registry._relation_tags_by_entity
        for entity in _traverse_entities(self.entity, self.traverse):
            by_entity = _relation_tags_by_entity.get(entity)
            if by_entity is None:
                continue
            values = by_entity.get(key)
            if not values:
                continue
            try:
                (target,) = values
            except ValueError:
                msg = "Entity relation has multiple targets but an exclusive value was expected."
                raise ValueError(msg) from None
            return target

        raise KeyError(key)

    def __setitem__(self, key: object, target: Entity) -> None:
        """Set a relation exclusively to a new target."""
        mapping = EntityRelationsMapping(self.entity, key, self.traverse)
        mapping.clear()
        mapping.add(target)

    def __delitem__(self, key: object) -> None:
        """Clear the relation targets of a relation key."""
        EntityRelationsMapping(self.entity, key, self.traverse).clear()

    def __iter__(self) -> Iterator[Any]:
        """Iterate over the keys of this entities relations."""
        return EntityRelations(self.entity, self.traverse).__iter__()

    def __len__(self) -> int:
        """Return the number of relations this entity has."""
        return EntityRelations(self.entity, self.traverse).__len__()

    def clear(self) -> None:
        """Discard all tag relations from an entity."""
        EntityRelations(self.entity, self.traverse).clear()


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityComponentRelationMapping(Generic[T], MutableMapping[Entity, T]):
    """An entity-component mapping to access the relation target component objects.

    See :any:`Entity.relation_components`.
    """

    entity: Entity
    key: ComponentKey[T]
    traverse: tuple[object, ...]

    if __debug__:

        def __attrs_post_init__(self) -> None:
            """Validate attributes."""
            assert isinstance(self.entity, Entity), self.entity

    def __getitem__(self, target: Entity) -> T:
        """Return the component related to a target entity."""
        _relation_components_by_entity = self.entity.registry._relation_components_by_entity
        for entity in _traverse_entities(self.entity, self.traverse):
            by_entity = _relation_components_by_entity.get(entity)
            if by_entity is None:
                continue
            by_key = by_entity.get(self.key)
            if by_key is None or target not in by_key:
                continue

            return by_key[target]  # type: ignore[no-any-return]

        raise KeyError(target)

    def __setitem__(self, target: Entity, component: T) -> None:
        """Assign a component to the target entity."""
        registry = self.entity.registry

        old_value = registry._relation_components_by_entity[self.entity][self.key].get(target)
        if old_value is None:  # Relation added
            tcod.ecs.query._touch_relations(
                registry, ((self.key, target), (self.key, ...), (self.entity, self.key, None), (..., self.key, None))
            )

        registry._relation_components_by_entity[self.entity][self.key][target] = component

        _relations_lookup_add(registry, self.entity, self.key, target)

    def __delitem__(self, target: Entity) -> None:
        """Delete a component assigned to the target entity."""
        registry = self.entity.registry
        del registry._relation_components_by_entity[self.entity][self.key][target]
        if not registry._relation_components_by_entity[self.entity][self.key]:
            del registry._relation_components_by_entity[self.entity][self.key]
        if not registry._relation_components_by_entity[self.entity]:
            del registry._relation_components_by_entity[self.entity]

        _relations_lookup_discard(registry, self.entity, self.key, target)

    def keys(self) -> AbstractSet[Entity]:  # type: ignore[override]
        """Return all entities with an associated component value."""
        _relation_components_by_entity = self.entity.registry._relation_components_by_entity
        result: set[Entity] = set()
        for entity in _traverse_entities(self.entity, self.traverse):
            by_entity = _relation_components_by_entity.get(entity)
            if by_entity is None:
                continue
            result.update(by_entity.get(self.key, ()))
        return result

    def __iter__(self) -> Iterator[Entity]:
        """Iterate over the targets with assigned components."""
        yield from self.keys()

    def __len__(self) -> int:
        """Return the count of targets for this component relation."""
        return len(self.keys())


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityComponentRelations(MutableMapping[ComponentKey[Any], EntityComponentRelationMapping[Any]]):
    """Proxy to access the component relations of an entity.

    See :any:`Entity.relation_components`.

    ..versionchanged:: 4.2.0
        Is now a :any:`collections.abc.MutableMapping` subtype.
    """

    entity: Entity
    traverse: tuple[object, ...]

    if __debug__:

        def __attrs_post_init__(self) -> None:
            """Validate attributes."""
            assert isinstance(self.entity, Entity), self.entity

    def __call__(self, *, traverse: Iterable[object]) -> Self:
        """Update this view with alternative parameters, such as a specific traversal relation.

        .. versionadded:: 5.0
        """
        return self.__class__(self.entity, tuple(traverse))

    def __getitem__(self, key: ComponentKey[T]) -> EntityComponentRelationMapping[T]:
        """Access relations for this component key as a `{target: component}` dict-like object."""
        return EntityComponentRelationMapping(self.entity, key, self.traverse)

    def __setitem__(self, __key: ComponentKey[T], __values: Mapping[Entity, object]) -> None:
        """Redefine the component relations for this entity.

        ..versionadded:: 4.2.0
        """
        if isinstance(__values, EntityComponentRelationMapping) and __values.entity is self.entity:
            return
        mapping: EntityComponentRelationMapping[object] = self[__key]
        mapping.clear()
        for target, component in __values.items():
            mapping[target] = component

    def __delitem__(self, key: ComponentKey[object]) -> None:
        """Remove all relations associated with this component key."""
        EntityComponentRelationMapping(self.entity, key, self.traverse).clear()

    def __contains__(self, key: object) -> bool:
        """Return True if this entity contains a relation component for this component key."""
        return key in self.keys()

    def clear(self) -> None:
        """Clears the relation components this entity directly has with other entities.

        Does not clear relations targeting this entity.
        """
        for component_key in list(self.entity.registry._relation_components_by_entity.get(self.entity, ())):
            self[component_key].clear()

    def keys(self) -> AbstractSet[ComponentKey[object]]:  # type: ignore[override]
        """Returns the components keys this entity has relations for."""
        _relation_components_by_entity = self.entity.registry._relation_components_by_entity
        return set().union(
            *(
                _relation_components_by_entity.get(entity, ())
                for entity in _traverse_entities(self.entity, self.traverse)
            )
        )

    def __iter__(self) -> Iterator[ComponentKey[object]]:
        """Iterates over the component keys this entity has relations for."""
        return iter(self.keys())

    def __len__(self) -> int:
        """Returns the number of unique component keys this entity has relations for."""
        return len(self.keys())
