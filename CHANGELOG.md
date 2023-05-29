# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
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
