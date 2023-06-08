"""Support for saving and loading :any:`World`'s with :any:`cattrs`."""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Generic, Iterable, List, Mapping, NewType, Tuple, TypeVar

import attrs
import cattrs

from tcod.ecs import Entity, World, _ComponentKey

# ruff: noqa: ANN401 # It is difficult to type-hint cattrs supporting functions.

_T = TypeVar("_T")
_K = TypeVar("_K")
_GenericObject = NewType("_GenericObject", object)
_EntityUID = NewType("_EntityUID", object)


class _TrackingDict(Generic[_K], Dict[_K, int]):
    def __init__(self) -> None:
        self.next_id = 0

    def track(self, key: _K) -> int:
        new_id = self.next_id
        self.next_id += 1
        self[key] = new_id
        return new_id


def _pack_components_by_entity(world: World) -> dict[Entity, dict[_ComponentKey[Any], Any]]:
    return {entity: dict(entity.components) for entity in world._components_by_entity}


@attrs.define()
class _ECSConverter:
    converter: cattrs.Converter
    world_from_id: dict[int, World] = attrs.field(factory=dict)
    world_known: _TrackingDict[int] = attrs.field(factory=_TrackingDict)
    obj_from_id: dict[int, object] = attrs.field(factory=dict)
    obj_known: _TrackingDict[int] = attrs.field(factory=_TrackingDict)

    def unstructure_generic(self, obj: Any) -> Any:
        """Unstructure an object used as an ID, tracking seen objects."""
        if obj.__class__ is tuple:
            return self.converter.unstructure(obj, Tuple[_GenericObject, ...])
        if id(obj) in self.obj_known:
            return {"id": self.obj_known[id(obj)]}
        if isinstance(obj, type):
            return {"type": f"{obj.__module__}.{obj.__name__}"}
        if obj is None or obj.__class__ in {bool, int, float, str, bytes}:
            return obj
        if obj.__class__ is object:
            return {"id": self.obj_known.track(id(obj))}
        return {
            "type": f"{obj.__class__.__module__}.{obj.__class__.__name__}",
            "data": self.converter.unstructure(obj, obj.__class__),
            "id": self.obj_known.track(id(obj)),
        }

    def structure_generic(
        self, obj: dict[str, Any] | list[Any] | bool | int | float | str | bytes | None, cls: type[Any]
    ) -> Any:
        """Structure an object used as an ID, can return the same object if it is duplicate."""
        if isinstance(obj, list):
            return tuple(self.converter.structure(value, _GenericObject) for value in obj)
        if not isinstance(obj, dict):
            return obj
        if obj.get("id", None) in self.obj_from_id:
            return self.obj_from_id[obj["id"]]
        if "type" not in obj:
            self.obj_from_id[obj["id"]] = out = object()
            return out
        type_module, type_name = obj["type"].rsplit(".", 1)
        out_type: type[Any] = getattr(importlib.import_module(type_module), type_name)
        if "data" not in obj:
            return out_type
        self.obj_from_id[obj["id"]] = out = self.converter.structure(obj["data"], out_type)
        return out

    def unstructure_entity(self, entity: Entity) -> dict[str, Any]:
        """Unstructure a (world, uid) pair."""
        return {
            "world": self.converter.unstructure(entity.world, World),
            "uid": self.converter.unstructure(entity.uid, _GenericObject),
        }

    def structure_entity(self, obj: dict[str, Any], cls: type[Entity]) -> Entity:
        """Structure a (world, uid) pair."""
        return cls(
            self.converter.structure(obj["world"], World),
            self.converter.structure(obj["uid"], _GenericObject),
        )

    def unstructure_entity_uid(self, entity: Entity) -> Any:
        """Unstructure a (world, uid) pair."""
        return self.converter.unstructure(entity.uid, _GenericObject)

    def __pack_entity_dict(self, mapping: Mapping[Entity, _T], converter: Callable[[_T], Any]) -> list[dict[str, Any]]:
        """Pack a dict[Entity, T] dict so that the entity becomes a value in a new dictionary."""
        return [
            {"uid": self.converter.unstructure(entity, _EntityUID), "contents": converter(contents)}
            for entity, contents in mapping.items()
        ]

    def __pack_mapping(self, mapping: dict[_ComponentKey[Any], Any]) -> list[dict[str, Any]]:
        """Pack a mapping so that the key doesn't need to be hashed by moving the key into the dict."""
        return [
            {
                "key": self.converter.unstructure(key, _GenericObject),
                "value": self.converter.unstructure(value, _GenericObject),
            }
            for key, value in mapping.items()
        ]

    def __pack_tags(self, tags: Iterable[object]) -> Any:
        return self.converter.unstructure(tags, List[_GenericObject])

    def __pack_relation_tags(self, relations: Mapping[object, Iterable[Entity]]) -> list[dict[str, Any]]:
        return [
            {
                "tag": self.converter.unstructure(tag, _GenericObject),
                "targets": self.converter.unstructure(targets, List[_EntityUID]),
            }
            for tag, targets in relations.items()
        ]

    def __pack_relation_components(
        self, relations: dict[_ComponentKey[Any], dict[Entity, object]]
    ) -> list[dict[str, Any]]:
        return [
            {
                "key": self.converter.unstructure(component_key, _GenericObject),
                "components": [
                    {
                        "uid": self.converter.unstructure(entity, _EntityUID),
                        "value": self.converter.unstructure(value, _GenericObject),
                    }
                    for entity, value in relations_values.items()
                ],
            }
            for component_key, relations_values in relations.items()
        ]

    def __pack_names(self, names: dict[Entity, Any]) -> list[dict[str, Any]]:
        return [
            {
                "uid": self.converter.unstructure(entity.uid, _GenericObject),
                "name": self.converter.unstructure(name, _GenericObject),
            }
            for entity, name in names.items()
        ]

    def unstructure_world(self, world: World) -> dict[str, Any]:
        """Unstructure a World instance."""
        if id(world) in self.world_known:
            return {"id": self.world_known[id(world)]}

        out = {
            "id": self.world_known.track(id(world)),
            "components": self.__pack_entity_dict(_pack_components_by_entity(world), self.__pack_mapping),
            "tags": self.__pack_entity_dict(world._tags_by_entity, self.__pack_tags),
            "relation_tags": self.__pack_entity_dict(world._relation_tags_by_entity, self.__pack_relation_tags),
            "relation_components": self.__pack_entity_dict(
                world._relation_components_by_entity, self.__pack_relation_components
            ),
            "names": self.__pack_names(world._names_by_entity),
        }
        for key in out.keys() - {"id"}:
            if not out[key]:
                del out[key]
        return out

    def __unpack_components(self, obj: Any) -> dict[object, dict[Any, Any]]:
        return {
            self.converter.structure(components["uid"], _GenericObject): {
                self.converter.structure(contents["key"], _GenericObject): self.converter.structure(
                    contents["value"], _GenericObject
                )
                for contents in components["contents"]
            }
            for components in obj
        }

    def __unpack_tags(self, obj: Any) -> dict[object, list[Any]]:
        return {
            self.converter.structure(components["uid"], _GenericObject): [
                self.converter.structure(contents, _GenericObject) for contents in components["contents"]
            ]
            for components in obj
        }

    def __unpack_relation_tags(self, obj: Any) -> dict[object, dict[Any, list[Any]]]:
        return {
            self.converter.structure(relations["uid"], _GenericObject): {
                self.converter.structure(contents["tag"], _GenericObject): [
                    self.converter.structure(target, _GenericObject) for target in contents["targets"]
                ]
                for contents in relations["contents"]
            }
            for relations in obj
        }

    def __unpack_relation_components(self, obj: Any) -> dict[object, dict[Any, dict[Any, Any]]]:
        return {
            self.converter.structure(relations["uid"], _GenericObject): {
                self.converter.structure(contents["key"], _GenericObject): {
                    self.converter.structure(components["uid"], _GenericObject): self.converter.structure(
                        components["value"], _GenericObject
                    )
                    for components in contents["components"]
                }
                for contents in relations["contents"]
            }
            for relations in obj
        }

    def __unpack_names(self, obj: Any) -> dict[object, object]:
        return {
            self.converter.structure(names["uid"], _GenericObject): self.converter.structure(
                names["name"], _GenericObject
            )
            for names in obj
        }

    def structure_world(self, obj: Mapping[str, Any], cls: type[World]) -> World:
        """Structure an object used as an ID, can return the same object if it is duplicate."""
        if obj["id"] in self.world_from_id:
            return self.world_from_id[obj["id"]]
        self.world_from_id[obj["id"]] = world = cls()
        world._unpack(
            components=self.__unpack_components(obj.get("components", {})),
            tags=self.__unpack_tags(obj.get("tags", {})),
            relation_tags=self.__unpack_relation_tags(obj.get("relation_tags", {})),
            relation_components=self.__unpack_relation_components(obj.get("relation_components", {})),
            names=self.__unpack_names(obj.get("names", {})),
        )
        return world


def configure_ecs(converter: cattrs.Converter) -> None:
    """Configure a :any:`cattrs.Converter` to support :any:`World` and anonymous components/tags.

    Because this configuration adds support for cyclic references it is sensitive to being used multiple times.
    Do not reuse a converter configured by this function, always start a fresh converter when loading or saving.

    Example::

        >>> import json
        >>> import tcod.ecs
        >>> import tcod.ecs.cattrs
        >>> world = tcod.ecs.World()
        >>> converter = cattrs.Converter()
        >>> tcod.ecs.cattrs.configure_ecs(converter)
        >>> data = json.dumps(converter.unstructure(world))
        >>> loaded_world = converter.structure(json.loads(data), World)

    .. versionadded:: Unreleased
    """
    ecs_converter = _ECSConverter(converter)  # Bind to converter

    converter.register_unstructure_hook(World, ecs_converter.unstructure_world)
    converter.register_structure_hook(World, ecs_converter.structure_world)

    converter.register_unstructure_hook(_EntityUID, ecs_converter.unstructure_entity_uid)

    converter.register_unstructure_hook(Entity, ecs_converter.unstructure_entity)
    converter.register_structure_hook(Entity, ecs_converter.structure_entity)

    converter.register_unstructure_hook(_GenericObject, ecs_converter.unstructure_generic)
    converter.register_structure_hook(_GenericObject, ecs_converter.structure_generic)
