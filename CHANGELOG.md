# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Removed
- `tcod.ecs.query.Query` removed due to a refactor.

## [4.4.0] - 2023-08-11
### Added
- Added `WorldQuery.get_entities` for returning query results as a set.

### Fixed
- Removed an optimization which would check the equality of component values, since this would fail when comparing some types such as NumPy arrays.
- Removed unintentional iteration behavior from `World`. https://github.com/HexDecimal/python-tcod-ecs/issues/8

## [4.3.1] - 2023-08-02
### Fixed
- Relation component lookup tables were replacing previous entries instead of adding to them.
- Relation ellipsis lookup tables were discarding entities which still had a relevant relation.

## [4.3.0] - 2023-08-01
### Added
- `tcod.ecs.typing.ComponentKey` is now stable.
- Can now register a callback to be called on component changes.

### Fixed
- Fixed stale caches for relation components.

## [4.2.1] - 2023-07-28
### Fixed
- Unpickled worlds had reversed relations from what were saved.

## [4.2.0] - 2023-07-28
### Added
- `Entity.relation_components` now has `MutableMapping` functionality.
- You can now set the value of `Entity.relation_components[component_key] = {target: component}`.
- Added the `Entity.clear` method which effectively deletes an entity by removing its components/tags/relations.
  This does not delete relations targeting the cleared entity.

## [4.1.0] - 2023-07-28
### Added
- Now supports giving a query to another relation query, allowing conditional and chained relation queries. https://github.com/HexDecimal/python-tcod-ecs/issues/1

## [4.0.0] - 2023-07-26
### Changed
- The type returned by `World.Q` has been renamed from `tcod.ecs.Query` to `tcod.ecs.query.WorldQuery`.
- Serialization format updated.

### Performance
- Added a simple query cache.
  A query is automatically cached until any of the components/tags/relations it depends on have changed.

## [3.5.0] - 2023-07-23
### Changed
- Serialization format updated, older versions will not be able to unpickle this version.
- Reduced the size of the pickled World.

### Fixed
- Missing components in `Entity.components` now returns the missing key in the KeyError exception instead of the entity.
- Backwards relations for querying were not cleared on relation deletions.

## [3.4.0] - 2023-07-12
### Added
- `Entity.components` now supports the `|=` assignment operator.

## [3.3.0] - 2023-07-12
### Added
- `Entity.tags` now supports the `|=` and `-=` assignment operators.

## [3.2.0] - 2023-07-02
### Changed
- Warn if a string is passed directly as a tags parameter, which might cause unexpected behavior.
- `Entity.relation_tags` has been renamed to `Entity.relation_tag`.

### Deprecated
- Deprecated the renamed attribute `Entity.relation_tag`.

## [3.1.0] - 2023-06-10
### Changed
- `World.new_entity` can now take a `Mapping` as the `components` parameter.

### Deprecated
- Implicit keys for components have been deprecated in all places.
- The names feature has been deprecated.
- `Entity.components.by_name_type` has been deprecated.

## [3.0.1] - 2023-06-04
### Deprecated
- `World.global_` has been deprecated since `world[None]` is simpler and less redundant.

## [3.0.0] - 2023-05-29
### Added
- `Entity.components.by_name_type(name_type, component_type)` to iterate over named components with names of a specific type.

### Changed
- Remap `World.global_` to `uid=None`.

## [2.0.0] - 2023-05-26
### Added
- You can now use custom identifiers for entity objects.
  You can access these from World instances with `entity = world[uid]`.

### Removed
- Dropped support for unpickling v1.0 World objects.

## [1.2.0] - 2023-04-26
### Added
- Allow `Entity` instances to be referenced weakly.

### Fixed
- Added missing typing marker.
- Corrected the type-hinting of `Entity.component.get` and `Entity.component.setdefault`.

## [1.1.0] - 2023-04-21
### Added
- World's now have a globally accessible entity accessed with `World.global_`.

### Changed
- You can now quickly lookup the relation tags and relation component keys of an entity.

## [1.0.0] - 2023-04-11
First stable release.
