"""Registry management tools."""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Final, Literal, NoReturn, TypedDict

import attrs
from typing_extensions import deprecated

import tcod.ecs.query
from tcod.ecs.entity import Entity
from tcod.ecs.query import _QueryCache
from tcod.ecs.traits import Component, Relation, Tag

if TYPE_CHECKING:
    from tcod.ecs.typing import ComponentKey, _Trait


class _CategorizedData(TypedDict):
    """Known subtypes of categorized data."""

    Component: dict[Entity, dict[ComponentKey[object], Any]]
    """Storage for component data.

    ``this[entity][type] = value``

    Technically anything can be stored. The assumption is that `type` always has the correct TypeForm of `value`.
    """
    Tag: dict[Entity, dict[object, object]]
    """Storage for tag data. The value is True to indicate that a tag exists normally.

    ``this[entity][type] = True``
    """
    RelationComponent: dict[Entity, dict[ComponentKey[object], dict[Entity, Any]]]
    """Storage for component relations. Same as Component but stores values for each `target` entity.

    ``this[origin][type][target] = value``
    """
    RelationTag: dict[Entity, dict[object, dict[Entity, object]]]
    """Storage for tag relations. Same as Tag but stores values for each `target`.

    ``this[origin][type][target] = True``
    """


def _new_CategorizedData() -> _CategorizedData:  # noqa: N802
    """Return a new categorized data dict with empty values."""
    # Parameter order doesn't matter but tests are sensitive to it
    return _CategorizedData(Component={}, Tag={}, RelationTag={}, RelationComponent={})


@attrs.define(eq=False)
class Registry:
    """A container for entities and components."""

    _any_by_key_by_entity_by_category: _CategorizedData = attrs.field(init=False, factory=_new_CategorizedData)
    """Random access to entity data by category.

    This is used as the primary source of truth for data associations.
    All other structures derive from or cache the data stored here.
    Only this structure is needed for picking or copying.

    For regular tags/components this is:
    ``dict[category][Entity][key] = data``

    For relations this is:
    ``dict[category][Entity][key][target] = data``

    """

    _any_by_entity_by_trait: dict[object, dict[Entity, Any]] = attrs.field(init=False, factory=dict)
    """Query lookup table for all traits.

    For any trait key, the inner dict keys include all entities including that trait.

    The data assigned may be used for optimization or bookkeeping, otherwise the data will be literal True.

    The data assigned is respective of the trait.
    Components duplicate the source data as trait data.
    Wildcard relations use trait data to track the other ends of a relation.

    ``dict[trait][Entity] = trait_data``

    Reference for relation data:

    ```
    dict[Relation(key, target)] = dict[origin_entities, True]
    dict[Relation(key, ...)] = dict[origin_entities, set[target_entities]]
    dict[Relation(key, origin, inverse=True)] = dict[target_entities, True]
    dict[Relation(key, ..., inverse=True)] = dict[target_entities, set[origin_entities]]
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

    _query_cache: _QueryCache = attrs.field(init=False, factory=_QueryCache, repr=False)
    """Transient query cache, owned here so cached entities do not keep registries alive globally."""

    @property
    @deprecated(
        "The 'registry.global_' attribute has been deprecated. Use 'registry[None]' to access this entity.",
        category=FutureWarning,
    )
    def global_(self) -> Entity:
        """A unique globally accessible entity.

        This can be used to store globally accessible components in the registry itself without any extra boilerplate.
        Otherwise this entity is not special and will show up with other entities in queries, etc.

        This entity has a `uid` of `None` and may be accessed that way.
        This syntax my be better for globals in general since it can use any hashable object.

        .. versionadded:: 1.1

        Example::

            >>> registry[None].components[("turn", int)] = 0
            >>> registry[None].components[("turn", int)]
            0
        """
        return Entity(self, None)

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Unpickle this object and handle state migration."""
        self._query_cache = _QueryCache()
        global_: Entity | None = state.pop("global_", None)  # Migrate from version <=1.2.0

        # These attributes contain redundant data and will be removed
        redundant_attributes: Final = frozenset(
            {
                "_components_by_entity",  # <=3.4.0
                "_tags_by_key",  # <=3.4.0
                "_relations_lookup",  # <=3.4.0
                "_names_by_entity",  # <=3.4.0
            }
        )
        for ignored in redundant_attributes:
            state.pop(ignored, None)

        _components_by_type: dict[ComponentKey[object], dict[Entity, Any]] = state.pop("_components_by_type", {})
        _tags_by_entity: dict[Entity, set[Any]] = state.pop("_tags_by_entity", {})
        _relation_tags_by_entity: dict[Entity, dict[object, set[Entity]]] = state.pop("_relation_tags_by_entity", {})
        _relation_components_by_entity: dict[Entity, dict[ComponentKey[object], dict[Entity, Any]]] = state.pop(
            "_relation_components_by_entity", {}
        )

        self._names_by_name = state.pop("_names_by_name")
        self._names_by_entity = {entity: name for name, entity in self._names_by_name.items()}

        if global_ is not None and global_.uid is not None:  # Migrate from version <=1.2.0
            global_._force_remap(None)

        self._any_by_entity_by_trait = {}
        self._any_by_key_by_entity_by_category = _new_CategorizedData()

        categorized: _CategorizedData | None = state.pop("_categorized", None)
        if categorized is not None:
            self._generate_from_categorized_data(categorized)
        else:
            self._migrate_from_old_structures(
                _components_by_type,
                _tags_by_entity,
                _relation_tags_by_entity,
                _relation_components_by_entity,
            )

        if state:
            warnings.warn(f"These attributes were not unpacked {state.keys()}", RuntimeWarning, stacklevel=1)

    def _generate_from_categorized_data(self, categorized: _CategorizedData) -> None:
        """Set internal data and lookup tables from categorized data. The input `categorized` is untouched."""
        key: Any
        for standard_category in ("Component", "Tag"):
            if standard_category not in categorized:
                continue
            trait_cls = Tag if standard_category == "Tag" else Component.from_key
            for entity, key_data in categorized[standard_category].items():
                for key, value in key_data.items():
                    self._set_data(entity, trait_cls(key), standard_category, key, value)
        for relation_category in ("RelationComponent", "RelationTag"):
            if relation_category not in categorized:
                continue
            trait_cls = Tag if relation_category == "RelationTag" else Component.from_key
            for entity, key_target_data in categorized[relation_category].items():
                for key, target_data in key_target_data.items():
                    for target, value in target_data.items():
                        self._set_relation_data(entity, trait_cls(key), relation_category, key, target, value)

    def _migrate_from_old_structures(  # noqa: C901
        self,
        components_by_type: dict[ComponentKey[Any], dict[Entity, object]],
        tags_by_entity: dict[Entity, set[Any]],
        relation_tags_by_entity: dict[Entity, dict[object, set[Entity]]],
        relation_components_by_entity: dict[Entity, dict[ComponentKey[object], dict[Entity, Any]]],
    ) -> None:
        """Migrate old data structures to the current format."""
        for component_key, entity_data in components_by_type.items():
            for entity, value in entity_data.items():
                self._set_data(entity, Component.from_key(component_key), "Component", component_key, value)
        for entity, tags in tags_by_entity.items():
            for tag in tags:
                self._set_data(entity, Tag(tag), "Tag", tag, True)  # noqa: FBT003
        for entity, tag_relations in relation_tags_by_entity.items():
            for tag, targets in tag_relations.items():
                for target in targets:
                    self._set_relation_data(entity, Tag(tag), "RelationTag", tag, target, True)  # noqa: FBT003
        for entity, component_relations in relation_components_by_entity.items():
            for component_key, target_data in component_relations.items():
                for target, data in target_data.items():
                    self._set_relation_data(
                        entity, Component.from_key(component_key), "RelationComponent", component_key, target, data
                    )

    def _get_tags_by_entity(self) -> dict[Entity, set[object]]:
        """Return the legacy data structure from categorized data."""
        return {entity: set(tags) for entity, tags in self._any_by_key_by_entity_by_category["Tag"].items()}

    def _get_components_by_type(self) -> dict[ComponentKey[object], dict[Entity, object]]:
        """Return the legacy data structure from categorized data."""
        _components_by_type: dict[ComponentKey[object], dict[Entity, object]] = {}
        for entity, component_data in self._any_by_key_by_entity_by_category["Component"].items():
            for component_key, value in component_data.items():
                _components_by_type.setdefault(component_key, {})[entity] = value
        return _components_by_type

    def _get_relation_tags_by_entity(self) -> dict[Entity, dict[object, set[Entity]]]:
        """Return the legacy data structure from categorized data."""
        _relation_tags_by_entity: dict[Entity, dict[object, set[Entity]]] = {
            entity: {tag: set(targets) for tag, targets in tag_targets.items()}
            for entity, tag_targets in self._any_by_key_by_entity_by_category["RelationTag"].items()
        }
        return _relation_tags_by_entity

    def _get_relation_components_by_entity(self) -> dict[Entity, dict[ComponentKey[object], dict[Entity, Any]]]:
        """Return categorized relation component data which is equivalent to the legacy data structure."""
        return self._any_by_key_by_entity_by_category["RelationComponent"]

    def __getstate__(self) -> dict[str, Any]:
        """Pickle this object."""
        return {
            "_categorized": self._any_by_key_by_entity_by_category,  # Since >5.5
            # Remaining items for backwards compatibility
            "_components_by_type": self._get_components_by_type(),
            "_tags_by_entity": self._get_tags_by_entity(),
            "_relation_tags_by_entity": self._get_relation_tags_by_entity(),
            "_relation_components_by_entity": self._get_relation_components_by_entity(),
            "_names_by_name": self._names_by_name,
        }

    def __getitem__(self, uid: object) -> Entity:
        """Return an entity associated with a unique id.

        Example::

            >>> registry = Registry()
            >>> foo = registry["foo"]  # Referencing a new entity returns a new empty entity
            >>> foo is registry["foo"]
            True
            >>> entity = registry.new_entity()
            >>> registry[entity.uid] is entity  # Anonymous entities can be referred to by their uid
            True
        """
        assert uid is not object, "This is reserved."
        return Entity(self, uid)

    def __iter__(self) -> NoReturn:
        """Raises TypeError, :any:`Registry` is not iterable."""
        msg = "'Registry' object is not iterable."
        raise TypeError(msg)

    @property
    def named(self) -> Mapping[object, Entity]:
        """A view into this registries named entities.

        .. deprecated:: 3.1
            This feature has been deprecated.
        """
        return self._names_by_name

    def new_entity(
        self,
        components: Iterable[object] | Mapping[ComponentKey[object], object] = (),
        *,
        name: object = None,
        tags: Iterable[Any] = (),
    ) -> Entity:
        """Create and return a new entity.

        .. versionchanged:: 3.1
            `components` can now take a mapping.

        Example::

            >>> entity = registry.new_entity(
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
            entity.components.update_values(components)
        entity_tags = entity.tags
        for tag in tags:
            entity_tags.add(tag)
        if name is not None:
            entity._set_name(name)
        return entity

    @property
    def Q(self) -> tcod.ecs.query.BoundQuery:  # noqa: N802
        """Start a new Query for this registry.

        Alias for ``tcod.ecs.Query(registry)``.
        """
        return tcod.ecs.query.BoundQuery(self)

    def _set_lookup(self, entity: Entity, trait: _Trait, value: object) -> None:
        """Internal call to set a lookup value.

        Usually called indirectly via `_set_data` or `_set_relation_data`.
        """
        any_by_entity = self._any_by_entity_by_trait.setdefault(trait, {})
        any_by_entity[entity] = value
        self._query_cache._touch_trait(trait)  # Maybe entity added to trait

    def _discard_lookup(self, entity: Entity, trait: _Trait) -> None:
        """Internal call to delete a lookup value.

        Usually called indirectly via `_discard_data` or `_discard_relation_data`.
        """
        any_by_entity = self._any_by_entity_by_trait.get(trait)
        if any_by_entity is None:
            return  # Trait is not in registry
        any_by_entity.pop(entity, None)
        if not any_by_entity:
            del self._any_by_entity_by_trait[trait]
        self._query_cache._touch_trait(trait)  # Maybe entity removed from trait

    def _add_lookup_relation(self, entity: Entity, trait: _Trait, target: Entity) -> None:
        """Add `entity` to the lookup for `trait`. The lookup will be kept alive by `target`.

        The data for this lookup is the set of `target` entities.

        Usually called indirectly.
        """
        ends_by_entity: dict[Entity, set[Entity]] = self._any_by_entity_by_trait.setdefault(trait, {})
        ends_by_entity.setdefault(entity, set()).add(target)
        self._query_cache._touch_trait(trait)  # Maybe entity added to trait

    def _discard_lookup_relation(self, entity: Entity, trait: _Trait, target: Entity) -> None:
        """Discard `target` from a lookup set. Discard lookup when the set is empty.

        Usually called indirectly.
        """
        ends_by_entity: dict[Entity, set[Entity]] | None = self._any_by_entity_by_trait.get(trait)
        if ends_by_entity is None:
            return  # Trait is not in registry
        if entity not in ends_by_entity:
            return  # entity not in trait

        ends_by_entity[entity].discard(target)
        if not ends_by_entity[entity]:
            del ends_by_entity[entity]
            if not ends_by_entity:
                del self._any_by_entity_by_trait[trait]

        self._query_cache._touch_trait(trait)  # Maybe entity removed from trait

    def _set_data(
        self,
        entity: Entity,
        trait: _Trait,
        category: Literal["Component", "Tag"],
        key: Any,  # noqa: ANN401
        value: object,
    ) -> None:
        """Set an `entity`'s `trait` = `value`. Also sets up the lookup table for `trait` with the same `value`."""
        data_by_key_by_entity = self._any_by_key_by_entity_by_category[category]
        data_by_key = data_by_key_by_entity.setdefault(entity, {})
        data_by_key[key] = value

        self._set_lookup(entity, trait, value)

    def _discard_data(self, entity: Entity, trait: _Trait, category: Literal["Component", "Tag"], key: Any) -> bool:  # noqa: ANN401
        """Delete an `entity`'s `trait` and remove it from the lookup table. Does nothing if these don't exist.

        Return False if the entity/key did not exist.
        """
        data_by_key_by_entity = self._any_by_key_by_entity_by_category[category]
        data_by_key = data_by_key_by_entity.get(entity)
        if data_by_key is None:
            return False  # Entity not in category
        if key not in data_by_key:
            return False  # Key not in entity
        del data_by_key[key]
        if not data_by_key:
            del data_by_key_by_entity[entity]

        self._discard_lookup(entity, trait)
        return True

    def _set_relation_data(  # noqa: PLR0913, PLR0917
        self,
        origin: Entity,
        sub_trait: Component[Any] | Tag,
        category: Literal["RelationComponent", "RelationTag"],
        key: Any,  # noqa: ANN401
        target: Entity,
        value: object,
    ) -> None:
        data_by_target_by_key = self._any_by_key_by_entity_by_category[category].setdefault(origin, {})
        data_by_target = data_by_target_by_key.get(key)
        if data_by_target is None:
            data_by_target = data_by_target_by_key[key] = {}
        data_by_target[target] = value

        self._set_lookup(origin, Relation(sub_trait, target), value=True)
        self._add_lookup_relation(origin, Relation(sub_trait, ...), target)
        self._set_lookup(target, Relation(sub_trait, origin, inverse=True), value=True)
        self._add_lookup_relation(target, Relation(sub_trait, ..., inverse=True), origin)

        # Add legacy lookups
        self._set_lookup(origin, Relation(key, target), value=True)
        self._add_lookup_relation(origin, Relation(key, ...), target)
        self._set_lookup(target, Relation(key, origin, inverse=True), value=True)
        self._add_lookup_relation(target, Relation(key, ..., inverse=True), origin)

    def _discard_relation_data(
        self,
        origin: Entity,
        sub_trait: Component[Any] | Tag,
        category: Literal["RelationComponent", "RelationTag"],
        key: Any,  # noqa: ANN401
        target: Entity,
    ) -> bool:
        data_by_target_by_key = self._any_by_key_by_entity_by_category[category].get(origin)
        if data_by_target_by_key is None:
            return False  # Entity is not in registry
        data_by_target = data_by_target_by_key.get(key)
        if data_by_target is None:
            return False  # Entity relation is not in registry
        data_by_target.pop(target, None)
        if not data_by_target:
            del data_by_target_by_key[key]
            if not data_by_target_by_key:
                del self._any_by_key_by_entity_by_category[category][origin]

        self._discard_lookup(origin, Relation(sub_trait, target))
        self._discard_lookup_relation(origin, Relation(sub_trait, ...), target)
        self._discard_lookup(target, Relation(sub_trait, origin, inverse=True))
        self._discard_lookup_relation(target, Relation(sub_trait, ..., inverse=True), origin)

        # Remove legacy relation lookups if neither tag/component traits exist
        if Relation(sub_trait, target)._get_alt() not in self._any_by_entity_by_trait:
            self._discard_lookup(origin, Relation(key, target))
            self._discard_lookup_relation(origin, Relation(key, ...), target)
            self._discard_lookup(target, Relation(key, origin, inverse=True))
            self._discard_lookup_relation(target, Relation(key, ..., inverse=True), origin)

        return True
