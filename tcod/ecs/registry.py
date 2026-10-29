"""Registry management tools."""

from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Final, Literal, NoReturn, TypedDict, TypeVar

import attrs
from typing_extensions import deprecated

import tcod.ecs._converter
import tcod.ecs.query
from tcod.ecs.entity import Entity
from tcod.ecs.query import _QueryCache
from tcod.ecs.traits import Component, Relation, Tag

if TYPE_CHECKING:
    from tcod.ecs.typing import ComponentKey, _RelationTargetLookup

_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")


def _defaultdict_of_set() -> defaultdict[_T1, set[_T2]]:
    """Return a new defaultdict of sets."""
    return defaultdict(set)


def _defaultdict_of_dict() -> defaultdict[_T1, dict[_T2, _T3]]:
    """Return a new defaultdict of dicts."""
    return defaultdict(dict)


def _components_by_entity_from(
    by_type: defaultdict[ComponentKey[_T1], dict[Entity, _T1]],
) -> defaultdict[Entity, dict[ComponentKey[_T1], _T1]]:
    """Return the component lookup table from the components sparse-set."""
    by_entity: defaultdict[Entity, dict[ComponentKey[_T1], _T1]] = defaultdict(dict)
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
    components_by_entity: defaultdict[Entity, defaultdict[ComponentKey[object], dict[Entity, Any]]],
) -> defaultdict[tuple[Any, _RelationTargetLookup] | tuple[_RelationTargetLookup, Any, None], set[Entity]]:
    """Return the relation lookup table from the relations sparse-sets."""
    relations_lookup: defaultdict[
        tuple[Any, _RelationTargetLookup] | tuple[_RelationTargetLookup, Any, None], set[Entity]
    ] = defaultdict(set)
    for origin, tags in tags_by_entity.items():
        for tag, targets in tags.items():
            for target in targets:
                relations_lookup[(tag, ...)].add(origin)
                relations_lookup[(tag, target)].add(origin)
                relations_lookup[(origin, tag, None)].add(target)
                relations_lookup[(..., tag, None)].add(target)
    for origin, components in components_by_entity.items():
        for component_key, target_components in components.items():
            for target in target_components:
                relations_lookup[(component_key, ...)].add(origin)
                relations_lookup[(component_key, target)].add(origin)
                relations_lookup[(origin, component_key, None)].add(target)
                relations_lookup[(..., component_key, None)].add(target)

    return relations_lookup


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


@attrs.define(eq=False)
class Registry:
    """A container for entities and components."""

    _category_entity_key_data: _CategorizedData = attrs.field(init=False, factory=lambda: defaultdict(dict))  # type: ignore[assignment]
    """Random access to entity data by category.

    This is used as the primary source of truth for data associations.
    All other structures derive from or cache the data stored here.
    Only this structure is needed for picking or copying.

    For regular tags/components this is:
    ``dict[category][Entity][key] = data``

    For relations this is:
    ``dict[category][Entity][key][target] = data``

    """

    _trait_entity_data: dict[object, dict[Entity, Any]] = attrs.field(init=False, factory=dict)
    """Query lookup table for all traits.

    dict[trait][Entity] = trait_data
    """

    _components_by_entity: defaultdict[Entity, dict[ComponentKey[object], Any]] = attrs.field(
        init=False, factory=lambda: defaultdict(dict)
    )
    """Random access entity components.

    dict[Entity][ComponentKey] = component_instance
    """
    _components_by_type: defaultdict[ComponentKey[object], dict[Entity, Any]] = attrs.field(
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
    _relation_components_by_entity: defaultdict[Entity, defaultdict[ComponentKey[object], dict[Entity, Any]]] = (
        attrs.field(init=False, factory=lambda: defaultdict(_defaultdict_of_dict))
    )
    """Random access relations owning components.

    dict[entity][ComponentKey][target_entity] = component
    """
    _relations_lookup: defaultdict[
        tuple[Any, _RelationTargetLookup] | tuple[_RelationTargetLookup, Any, None], set[Entity]
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

        converter = tcod.ecs._converter._get_converter()
        # Apply defaultdict types to unpickled dictionaries
        self._components_by_type = converter.structure(
            state.pop("_components_by_type"),
            defaultdict[Any, dict[Any, Any]],
        )
        self._components_by_entity = _components_by_entity_from(self._components_by_type)

        self._tags_by_entity = converter.structure(
            state.pop("_tags_by_entity"),
            defaultdict[Any, set[Any]],
        )
        self._tags_by_key = _tags_by_key_from_tags_by_entity(self._tags_by_entity)

        self._relation_tags_by_entity = converter.structure(
            state.pop("_relation_tags_by_entity"),
            defaultdict[Any, defaultdict[Any, set[Any]]],
        )
        self._relation_components_by_entity = converter.structure(
            state.pop("_relation_components_by_entity"),
            defaultdict[Any, defaultdict[Any, dict[Any, Any]]],
        )
        self._relations_lookup = _relations_lookup_from(
            self._relation_tags_by_entity, self._relation_components_by_entity
        )

        self._names_by_name = state.pop("_names_by_name")
        self._names_by_entity = {entity: name for name, entity in self._names_by_name.items()}

        if global_ is not None and global_.uid is not None:  # Migrate from version <=1.2.0
            global_._force_remap(None)

        self._trait_entity_data = {}
        self._category_entity_key_data = defaultdict(dict)  # type: ignore[assignment]

        categorized: _CategorizedData | None = state.pop("_categorized", None)
        if categorized is not None:
            self._generate_from_categorized_data(categorized)
        else:
            self._migrate_from_old_structures(
                self._components_by_type,
                self._tags_by_entity,
                self._relation_tags_by_entity,  # type: ignore[arg-type]
                self._relation_components_by_entity,  # type: ignore[arg-type]
            )

        if state:
            warnings.warn(f"These attributes were not unpacked {state.keys()}", RuntimeWarning, stacklevel=1)

    def _generate_from_categorized_data(self, categorized: _CategorizedData) -> None:
        """Set internal data and lookup tables from categorized data."""
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
        _tags_by_entity = {entity: set(tags) for entity, tags in self._category_entity_key_data["Tag"].items()}
        assert _tags_by_entity == self._tags_by_entity
        return _tags_by_entity

    def _get_components_by_type(self) -> dict[ComponentKey[object], dict[Entity, object]]:
        _components_by_type: dict[ComponentKey[object], dict[Entity, object]] = {}
        for entity, component_data in self._category_entity_key_data["Component"].items():
            for component_key, value in component_data.items():
                _components_by_type.setdefault(component_key, {})[entity] = value
        assert _components_by_type == self._components_by_type
        return _components_by_type

    def _get_relation_tags_by_entity(self) -> dict[Entity, dict[object, set[Entity]]]:
        _relation_tags_by_entity: dict[Entity, dict[object, set[Entity]]] = {
            entity: {tag: set(targets) for tag, targets in tag_targets.items()}
            for entity, tag_targets in self._category_entity_key_data["RelationTag"].items()
        }
        assert _relation_tags_by_entity == self._relation_tags_by_entity
        return _relation_tags_by_entity

    def _get_relation_components_by_entity(self) -> dict[Entity, dict[ComponentKey[object], dict[Entity, Any]]]:
        assert self._category_entity_key_data["RelationComponent"] == self._relation_components_by_entity
        return self._category_entity_key_data["RelationComponent"]

    def __getstate__(self) -> dict[str, Any]:
        """Pickle this object."""
        return {
            "_categorized": dict(**self._category_entity_key_data),  # Since >5.5
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

    def _set_lookup(self, entity: Entity, trait: object, value: object) -> None:
        """Internal call to set a lookup value.

        Usually called indirectly via `_set_data` or `_set_relation_data`.
        """
        entity_data = self._trait_entity_data.setdefault(trait, {})
        entity_data[entity] = value

    def _discard_lookup(self, entity: Entity, trait: object) -> None:
        """Internal call to delete a lookup value.

        Usually called indirectly via `_discard_data` or `_discard_relation_data`.
        """
        entity_data = self._trait_entity_data.get(trait)
        if entity_data is None:
            return  # Trait is not in registry
        entity_data.pop(entity, None)
        if not entity_data:
            del self._trait_entity_data[trait]

    def _set_data(
        self,
        entity: Entity,
        trait: object,
        category: Literal["Component", "Tag"],
        key: Any,  # noqa: ANN401
        value: object,
    ) -> None:
        """Set an `entity`'s `trait` = `value`. Also sets up the lookup table for `trait` with the same `value`."""
        entity_key_data = self._category_entity_key_data[category]
        key_data = entity_key_data.setdefault(entity, {})
        key_data[key] = value

        self._set_lookup(entity, trait, value)

    def _discard_data(self, entity: Entity, trait: object, category: Literal["Component", "Tag"], key: Any) -> None:  # noqa: ANN401
        """Delete an `entity`'s `trait` and remove it from the lookup table. Does nothing if these don't exist."""
        entity_key_data = self._category_entity_key_data[category]
        key_data = entity_key_data.get(entity)
        if key_data is None:
            return
        key_data.pop(key, None)
        if not key_data:
            del entity_key_data[entity]

        self._discard_lookup(entity, trait)

    def _set_relation_data(  # noqa: PLR0913, PLR0917
        self,
        origin: Entity,
        sub_trait: Component[Any] | Tag,
        category: Literal["RelationComponent", "RelationTag"],
        key: Any,  # noqa: ANN401
        target: Entity,
        value: object,
    ) -> None:
        key_target_data = self._category_entity_key_data[category].setdefault(origin, {})
        target_data = key_target_data.get(key)
        if target_data is None:
            target_data = key_target_data[key] = {}
            for trait in Relation(sub_trait, target)._expand_lookup():
                self._set_lookup(origin, (trait), value=True)

            # Include legacy relation lookups which treat tags and components as equivalent
            for trait in Relation(key, target)._expand_lookup():
                self._set_lookup(origin, (trait), value=True)

        target_data[target] = value

    def _discard_relation_data(
        self,
        origin: Entity,
        sub_trait: Component[Any] | Tag,
        category: Literal["RelationComponent", "RelationTag"],
        key: Any,  # noqa: ANN401
        target: Entity,
    ) -> None:
        key_target_data = self._category_entity_key_data[category].get(origin)
        if key_target_data is None:
            return  # Entity is not in registry
        target_data = key_target_data.get(key)
        if target_data is None:
            return  # Entity relation is not in registry
        target_data.pop(target, None)
        if not target_data:
            del key_target_data[key]
            if not key_target_data:
                del self._category_entity_key_data[category][origin]

        for trait in Relation(sub_trait, target)._expand_lookup():
            self._discard_lookup(origin, trait)

        # Remove legacy relation lookups if neither tag/component traits exist
        if (Relation(sub_trait, target)._get_alt(), target) not in self._trait_entity_data:
            for trait in Relation(key, target)._expand_lookup():
                self._discard_lookup(origin, trait)
