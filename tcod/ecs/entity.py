"""Entity management and interface tools."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, MutableMapping, MutableSet
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Self,
    overload,
)
from weakref import WeakKeyDictionary, WeakValueDictionary

import attrs
from typing_extensions import Sentinel, TypeForm, deprecated

import tcod.ecs.callbacks
from tcod.ecs.constants import IsA
from tcod.ecs.traits import Component, Tag
from tcod.ecs.typing import ComponentKey

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from _typeshed import SupportsKeysAndGetItem

    from tcod.ecs.registry import Registry


_raise: Final = Sentinel("_raise")

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

    __slots__ = ("__weakref__", "registry", "uid")

    registry: Final[Registry]  # type:ignore[misc]  # https://github.com/python/mypy/issues/5774
    """The :any:`Registry` this entity belongs to."""
    uid: Final[object]  # type:ignore[misc]
    """This entities unique identifier."""

    @property
    @deprecated("Use '.registry' instead of '.world'")
    def world(self) -> Registry:
        """Deprecated alias for registry.

        .. deprecated:: 5.1
            Use :any:`registry` instead.
        """
        return self.registry

    def __new__(cls, registry: Registry, uid: object = object) -> Self | Entity:
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

        Immutable components inherited from the parent are always copy-on-write for its child instances.

        Keep in mind that components/tags/relations inherited from the parent are not removable from the child instance.

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
            >>> child.components[str]  # Changes in parent are reflected in children
            'foo'
            >>> child.components[str] += "bar"  # In-place assignment operators will copy-on-write immutable objects
            >>> child.components[str]
            'foobar'
            >>> parent.components[str]
            'foo'
            >>> child.components.pop(str, None)  # Revert the component to the inherited value
            'foobar'
            >>> child.components[str]
            'foo'
            >>> child.components.pop(str, None)  # Safe to call .pop with default when the value isn't set on the child
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
    @deprecated("The '.relation_tags' attribute has been renamed to '.relation_tag'", category=FutureWarning)
    def relation_tags(self) -> EntityRelationsExclusive:
        """Access an entities exclusive relations.

        .. deprecated:: 3.2
            This attribute was renamed to :any:`relation_tag`.
        """
        return EntityRelationsExclusive(self, (IsA,))

    @property
    def relation_tags_many(self) -> EntityRelations:
        """Access an entities many-to-many relations.

        Example::

            >>> entity.relation_tags_many["KnownBy"].add(other_entity)  # Assign relation
        """
        return EntityRelations(self, (IsA,))

    @deprecated("The name feature has been deprecated and will be removed.", category=FutureWarning)
    def _set_name(self, value: object) -> None:
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
    @deprecated("The name feature has been deprecated and will be removed.", category=FutureWarning)
    def name(self, value: object) -> None:
        self._set_name(value)

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
    """Iterate over all entities `start` inherits from, including itself.

    `traverse_parents` are the relation tags to be followed.

    The result is equivalent to a method-resolution-order for this entity.
    """
    if not traverse_parents:
        yield start
        return
    traverse_parents = traverse_parents[::-1]
    visited = {start}
    stack = [start]
    _relation_tags_by_entity = start.registry._any_by_key_by_entity_by_category["RelationTag"]
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
class EntityComponents(MutableMapping[TypeForm[Any] | tuple[object, TypeForm[Any]], object]):
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

    @deprecated("Setting values without an explicit key has been deprecated.", category=FutureWarning)
    def set(self, value: object) -> None:
        """Assign or overwrite a component, automatically deriving the key.

        .. deprecated:: 3.1
            Setting values without an explicit key has been deprecated.
        """
        key = value.__class__
        self[key] = value

    @staticmethod
    def __assert_key(key: ComponentKey[Any]) -> bool:
        """Verify that abstract classes are accessed correctly."""
        if isinstance(key, tuple):
            key = key[1]
        return True

    def __getitem__[T](self, key: ComponentKey[T]) -> T:
        """Return a component belonging to this entity, or an indirect parent."""
        assert self.__assert_key(key)
        _components_by_entity = self.entity.registry._any_by_key_by_entity_by_category["Component"]
        for entity in _traverse_entities(self.entity, self.traverse):
            components = _components_by_entity.get(entity)
            if components is None:
                continue
            try:
                return components[key]  # type: ignore[no-any-return]
            except KeyError:
                pass
        raise KeyError(key)

    def __setitem__[T](self, key: ComponentKey[T], value: T) -> None:
        """Assign a component directly to an entity."""
        assert self.__assert_key(key)

        old_value = self.entity.registry._any_by_key_by_entity_by_category["Component"].get(self.entity, {}).get(key)

        self.entity.registry._set_data(self.entity, Component.from_key(key), "Component", key, value)

        tcod.ecs.callbacks._on_component_changed(key, self.entity, old_value, value)

    def __delitem__(self, key: TypeForm[object] | tuple[object, TypeForm[object]]) -> None:
        """Delete a directly held component from an entity."""
        assert self.__assert_key(key)

        old_value = self.entity.registry._any_by_key_by_entity_by_category["Component"].get(self.entity, {}).get(key)

        if not self.entity.registry._discard_data(self.entity, Component.from_key(key), "Component", key):
            raise KeyError(key)

        tcod.ecs.callbacks._on_component_changed(key, self.entity, old_value, None)

    def keys(self) -> AbstractSet[ComponentKey[object]]:  # type: ignore[override]
        """Return the components held by this entity, including inherited components."""
        _components_by_entity = self.entity.registry._any_by_key_by_entity_by_category["Component"]
        if not self.traverse:
            return _components_by_entity.get(self.entity, {}).keys()
        set_: set[ComponentKey[object]] = set()
        return set_.union(
            *(_components_by_entity.get(entity, ()) for entity in _traverse_entities(self.entity, self.traverse))
        )

    def __contains__(self, key: object) -> bool:
        """Return True if this entity has the provided component key."""
        _components_by_entity = self.entity.registry._any_by_key_by_entity_by_category["Component"]
        return any(
            key in _components_by_entity.get(entity, ()) for entity in _traverse_entities(self.entity, self.traverse)
        )

    def __iter__(self) -> Iterator[ComponentKey[Any]]:
        """Iterate over the component types belonging to this entity."""
        return iter(self.keys())

    def __len__(self) -> int:
        """Return the number of components belonging to this entity."""
        return len(self.keys())

    @deprecated("Setting values without an explicit key has been deprecated.", category=FutureWarning)
    def update_values(self, values: Iterable[object]) -> None:
        """Add or overwrite multiple components inplace, deriving the keys from the values.

        .. deprecated:: 3.1
            Setting values without an explicit key has been deprecated.
        """
        for value in values:
            self.set(value)

    @deprecated("This method has been deprecated. Iterate over items instead.", category=FutureWarning)
    def by_name_type[T, T2](self, name_type: type[T], component_type: TypeForm[T2]) -> Iterator[tuple[T, TypeForm[T2]]]:
        """Iterate over all of an entities component keys with a specific (name_type, component_type) combination.

        .. versionadded:: 3.0

        .. deprecated:: 3.1
            This method has been deprecated. Iterate over items instead.
        """
        for key in self:
            if not isinstance(key, tuple):
                continue
            key_name, key_component = key
            if key_component is component_type and isinstance(key_name, name_type):
                yield key_name, key_component  # type: ignore[unused-ignore]  # Too complex for PyLance, deprecated anyways

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
    def get[T](self, __key: ComponentKey[T], /) -> T | None: ...
    @overload
    def get[T, T1](self, __key: ComponentKey[T], /, default: T1) -> T | T1: ...

    def get[T, T1](self, __key: ComponentKey[T], /, default: T1 | None = None) -> T | T1:
        """Return a component, returns None or a default value when the component is missing."""
        try:
            return self[__key]
        except KeyError:
            return default  # type: ignore[return-value] # https://github.com/python/mypy/issues/3737

    def setdefault[T](self, __key: ComponentKey[T], __default: T, /) -> T:  # type: ignore[override] # Disallows default None
        """Assign a default value if a component is missing, then returns the current value."""
        try:
            return self[__key]
        except KeyError:
            self[__key] = __default
            return __default

    @overload
    def pop[T](self, __key: ComponentKey[T], /) -> T: ...
    @overload
    def pop[T, T1](self, __key: ComponentKey[T], /, default: T1) -> T | T1: ...

    def pop[T, T1](
        self,
        __key: ComponentKey[T],
        /,
        default: T1 = _raise,  # type: ignore[assignment] # https://github.com/python/mypy/issues/3737
    ) -> T | T1:
        """Remove a component directly from this entity.

        Returns the removed value.
        If the value is missing returns `default`.
        If `default` is unset then raises :any:`KeyError` instead.

        Operates directly on the entity without traversal.

        >>> parent = registry[object()]
        >>> parent.components[str] = "foo"
        >>> child = parent.instantiate()
        >>> child.components[str] = "bar"
        >>> child.components.pop(str, None)
        'bar'
        >>> child.components.pop(str, None)
        >>> child.components[str]
        'foo'
        >>> child.components.pop(str)
        Traceback (most recent call last):
            ...
        KeyError: <class 'str'>
        """
        data_by_key = self.entity.registry._any_by_key_by_entity_by_category["Component"].get(self.entity, {})
        if __key not in data_by_key:
            if default is _raise:
                raise KeyError(__key)
            return default
        value: T | T1 = data_by_key[__key]
        del self[__key]
        return value

    def clear(self) -> None:
        """Remove any components stored directly in this entity."""
        if self.traverse:
            self(traverse=()).clear()
            return
        super().clear()


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityTags(MutableSet[Any]):
    """A proxy attribute to access an entities tags like a set.

    See :any:`Entity.tags`.
    """

    entity: Entity
    traverse: tuple[object, ...]

    @classmethod
    def _from_iterable[T](cls, it: Iterable[T]) -> set[T]:
        """Return an independent set for the inherited set operations."""
        return set(it)

    def __call__(self, *, traverse: Iterable[object]) -> Self:
        """Update this view with alternative parameters, such as a specific traversal relation.

        .. versionadded:: 5.0
        """
        return self.__class__(self.entity, tuple(traverse))

    def add(self, tag: object) -> None:
        """Add a tag to the entity."""
        self.entity.registry._set_data(self.entity, Tag(tag), "Tag", tag, True)  # noqa: FBT003

    def discard(self, tag: object) -> None:
        """Discard a tag directly held by an entity."""
        self.entity.registry._discard_data(self.entity, Tag(tag), "Tag", tag)

    def remove(self, tag: object) -> None:
        """Remove a tag directly held by an entity."""
        if not self.entity.registry._discard_data(self.entity, Tag(tag), "Tag", tag):
            raise KeyError(tag)

    def clear(self) -> None:
        """Remove all tags directly in this entity."""
        while tags := self.entity.registry._any_by_key_by_entity_by_category["Tag"].get(self.entity):
            self.discard(next(iter(tags)))

    def __contains__(self, x: object) -> bool:
        """Return True if this entity has the given tag."""
        _tags_by_entity = self.entity.registry._any_by_key_by_entity_by_category["Tag"]
        return any(x in _tags_by_entity.get(entity, ()) for entity in _traverse_entities(self.entity, self.traverse))

    def _as_set(self) -> set[object]:
        """Return all tags inherited by traversal rules into a single set with no duplicates."""
        _tags_by_entity = self.entity.registry._any_by_key_by_entity_by_category["Tag"]
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


@attrs.define(eq=False, frozen=True, weakref_slot=False)
class EntityRelationsMapping(MutableSet[Entity]):
    """A proxy attribute to access entity relation targets like a set.

    See :any:`Entity.relation_tags_many`.
    """

    entity: Entity
    key: object
    traverse: tuple[object, ...]

    @classmethod
    def _from_iterable[T](cls, it: Iterable[T]) -> set[T]:
        """Return an independent set for the inherited set operations."""
        return set(it)

    if __debug__:

        def __attrs_post_init__(self) -> None:
            """Validate attributes."""
            assert self.key not in {None, Ellipsis}

    def add(self, target: Entity) -> None:
        """Add a relation target to this tag."""
        self.entity.registry._set_relation_data(self.entity, Tag(self.key), "RelationTag", self.key, target, value=True)

    def discard(self, target: Entity) -> None:
        """Discard a directly held relation target from this tag."""
        self.entity.registry._discard_relation_data(self.entity, Tag(self.key), "RelationTag", self.key, target)

    def remove(self, target: Entity) -> None:
        """Remove a directly held relation target from this tag.

        This will raise KeyError if only an indirect relation target exists.
        """
        if not self.entity.registry._discard_relation_data(self.entity, Tag(self.key), "RelationTag", self.key, target):
            raise KeyError(target)

    def __contains__(self, target: Entity) -> bool:  # type: ignore[override]
        """Return True if this relation contains the given value."""
        _relation_tags_by_entity = self.entity.registry._any_by_key_by_entity_by_category["RelationTag"]
        for entity in _traverse_entities(self.entity, self.traverse):
            by_entity = _relation_tags_by_entity.get(entity)
            if by_entity is None:
                continue
            if target in by_entity.get(self.key, ()):
                return True
        return False

    def _as_set(self) -> set[Entity]:
        """Return the combined targets of this mapping via traversal with duplicates removed."""
        _relation_tags_by_entity = self.entity.registry._any_by_key_by_entity_by_category["RelationTag"]
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
        by_entity = self.entity.registry._any_by_key_by_entity_by_category["RelationTag"].get(self.entity)
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
        values = tuple(values)  # Values may be a live view of the mapping being replaced.
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
        _relation_tags_by_entity = self.entity.registry._any_by_key_by_entity_by_category["RelationTag"]
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
        for key in list(self.entity.registry._any_by_key_by_entity_by_category["RelationTag"].get(self.entity, ())):
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
        _relation_tags_by_entity = self.entity.registry._any_by_key_by_entity_by_category["RelationTag"]
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
class EntityComponentRelationMapping[T](MutableMapping[Entity, T]):
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

    def __call__(self, *, traverse: Iterable[object]) -> Self:
        """Update this view with alternative parameters, such as a specific traversal relation.

        .. versionadded:: 5.4
        """
        return self.__class__(self.entity, self.key, tuple(traverse))

    def __getitem__(self, target: Entity) -> T:
        """Return the component related to a target entity."""
        _relation_components_by_entity = self.entity.registry._any_by_key_by_entity_by_category["RelationComponent"]
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
        self.entity.registry._set_relation_data(
            self.entity, Component.from_key(self.key), "RelationComponent", self.key, target, component
        )

    def __delitem__(self, target: Entity) -> None:
        """Delete a component assigned to the target entity."""
        if not self.entity.registry._discard_relation_data(
            self.entity, Component.from_key(self.key), "RelationComponent", self.key, target
        ):
            raise KeyError(target)

    def keys(self) -> AbstractSet[Entity]:  # type: ignore[override]
        """Return all entities with an associated component value."""
        _relation_components_by_entity = self.entity.registry._any_by_key_by_entity_by_category["RelationComponent"]
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

    def clear(self) -> None:
        """Remove any components stored directly in this entity relation."""
        if self.traverse:
            return self(traverse=()).clear()
        return super().clear()


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

    def __getitem__[T](self, key: ComponentKey[T]) -> EntityComponentRelationMapping[T]:
        """Access relations for this component key as a `{target: component}` dict-like object."""
        return EntityComponentRelationMapping(self.entity, key, self.traverse)

    def __setitem__[T](self, __key: ComponentKey[T], __values: Mapping[Entity, T], /) -> None:
        """Redefine the component relations for this entity.

        ..versionadded:: 4.2.0
        """
        if (
            isinstance(__values, EntityComponentRelationMapping)
            and __values.entity is self.entity
            and __values.key == __key
        ):
            return
        items = tuple(__values.items())  # The input may inherit values from the mapping being replaced.
        mapping: EntityComponentRelationMapping[T] = self[__key]
        mapping.clear()
        for target, component in items:
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
        for component_key in list(
            self.entity.registry._any_by_key_by_entity_by_category["RelationComponent"].get(self.entity, ())
        ):
            self[component_key].clear()

    def keys(self) -> AbstractSet[ComponentKey[object]]:  # type: ignore[override]
        """Returns the components keys this entity has relations for."""
        _relation_components_by_entity = self.entity.registry._any_by_key_by_entity_by_category["RelationComponent"]
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
