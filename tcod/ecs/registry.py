"""Registry management tools."""

from __future__ import annotations

import warnings
from collections import defaultdict
from typing import TYPE_CHECKING, Any, DefaultDict, Dict, Final, Iterable, Mapping, NoReturn, Set, TypeVar

import attrs

import tcod.ecs._converter
import tcod.ecs.query
from tcod.ecs.entity import Entity

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
    by_type: defaultdict[ComponentKey[object], dict[Entity, Any]],
) -> defaultdict[Entity, dict[ComponentKey[object], Any]]:
    """Return the component lookup table from the components sparse-set."""
    by_entity: defaultdict[Entity, dict[ComponentKey[object], Any]] = defaultdict(dict)
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
                relations_lookup[(component_key, origin)].add(origin)
                relations_lookup[(origin, component_key, None)].add(target)
                relations_lookup[(..., component_key, None)].add(target)

    return relations_lookup


@attrs.define(eq=False)
class Registry:
    """A container for entities and components."""

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

    @property
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
        warnings.warn(
            "The 'registry.global_' attribute has been deprecated. Use 'registry[None]' to access this entity.",
            FutureWarning,
            stacklevel=2,
        )
        return Entity(self, None)

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Unpickle this object and handle state migration."""
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
            entity.components.update_values(components, _stacklevel=2)
        entity_tags = entity.tags
        for tag in tags:
            entity_tags.add(tag)
        if name is not None:
            entity._set_name(name, stacklevel=2)
        return entity

    @property
    def Q(self) -> tcod.ecs.query.BoundQuery:  # noqa: N802
        """Start a new Query for this registry.

        Alias for ``tcod.ecs.Query(registry)``.
        """
        return tcod.ecs.query.BoundQuery(self)
