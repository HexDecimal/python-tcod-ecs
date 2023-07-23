# About

[![PyPI](https://img.shields.io/pypi/v/tcod-ecs)](https://pypi.org/project/tcod-ecs/)
[![PyPI - License](https://img.shields.io/pypi/l/tcod-ecs)](https://github.com/HexDecimal/python-tcod-ecs/blob/main/LICENSE)
[![Documentation Status](https://readthedocs.org/projects/python-tcod-ecs/badge/?version=latest)](https://python-tcod-ecs.readthedocs.io)
[![codecov](https://codecov.io/gh/HexDecimal/python-tcod-ecs/branch/main/graph/badge.svg?token=4Ak5QpTLZB)](https://codecov.io/gh/HexDecimal/python-tcod-ecs)

`tcod-ecs` is a [Sparse-set](https://skypjack.github.io/2020-08-02-ecs-baf-part-9/) [Entity-component-system](https://en.wikipedia.org/wiki/Entity_component_system) implemented using Python's `dict` and `set` types.
See the [ECS FAQ](https://github.com/SanderMertens/ecs-faq) for more info.

This implementation focuses on type-hinting, organization, and is designed to work well with Python.
The following features are currently implemented:

- Entities can store components which are instances of any Python object. Components are looked up by their type.
- Entities can have one instance of a type, or multiple instances of a type using a hashable tag to differentiate them.
- Entity relationships are supported, either as many-to-many or many-to-one relationships.
- ECS Queries can be made to fetch entities having a combination of components/tags/relations or excluding such.
- The ECS World object can be serialized with Python's pickle module for easy storage.

A lightweight version which implements only the entity-component framework exists called [tcod-ec](https://pypi.org/project/tcod-ec/).
`tcod-ec` was geared towards a dynamic-typed-dict style of syntax and is missing a lot of important features such as queries and named components.

# Installation

Use pip to install this library:
```
pip install tcod-ecs
```

If `tcod` is installed and the version is less than `14.0.0` then `import tcod.ecs` will fail.
Remove or update `tcod` to fix this issue.

# Examples

## World

```py
>>> import tcod.ecs
>>> world = tcod.ecs.World()  # New empty world

```

## Entity

Each Entity is identified by its unique id (`uid`) which can be any hashable object combined with the `world` it belongs.
New unique entities can be created with `World.new_entity` which uses a new `object()` as the `uid`, this guarantees uniqueness which is not always desireable.
An entity always knows about its assigned world, which can be access with the `Entity.world` property from any Entity instance.
Worlds only know about their entities once the entity is assigned a name, component, tag, or relation.

```py
>>> entity = world.new_entity()  # Creates a unique entity using `object()` as the uid
>>> entity
<Entity(uid=object at ...)>
>>> entity.world is world  # Worlds can always be accessed from their entity
True
>>> world[entity.uid] is entity  # Entities with the same world/uid are compared using `is`
True

# Reference an entity with the given uid, can be any hashable object:
>>> entity = world["MyEntity"]
>>> entity
<Entity(uid='MyEntity')>
>>> world["MyEntity"] is entity  # Matching entities ALWAYS share a single identity
True

```

Use `World.new_entity` to create unique entities and use `World[x]` to reference a global entity or relation with an id.
`World[None]` is recommend for use as a global entity when you want to store components in the world itself.

Do not save the `uid`'s of entities to be used later with `World[uid]`, this process is slower than holding onto the Entity instance.

## Serialization

Worlds are normal Python objects and can be pickled as long as all stored components are pickleable.

```py
>>> import pickle
>>> pickled_data: bytes = pickle.dumps(world)
>>> world = pickle.loads(pickled_data)

```

Stability is a priority but changes may still break older saves.
Backwards compatibility is not a priority, pickled worlds should not be unpickled with an older version of the library.
This project follows [Semantic Versioning](https://semver.org/), major version increments will break the API, the save format or both, minor version increments may break backwards compatibility.
Check the [changelog](https://github.com/HexDecimal/python-tcod-ecs/blob/main/CHANGELOG.md) to be aware of format changes and breaks.
There should always be a transition period before a format break, so keeping up with the latest version is a good idea.

## Components

Components are instances of any Python type.
These can be accessed, assigned, or removed from entities via the dict-like `Entity.components` attribute.
The type is used as the key to access the component.
The types used can be custom classes or standard Python types.

```py
>>> import attrs
>>> entity = world.new_entity()
>>> entity.components[int] = 42
>>> entity.components[int]
42
>>> int in entity.components
True
>>> del entity.components[int]
>>> entity.components[int]  # Missing keys raise KeyError
Traceback (most recent call last):
  ...
KeyError: <class 'int'>
>>> entity.components.get(int, "default")  # Test keys with `.get()` like a dictionary
'default'
>>> @attrs.define
... class Vector2:
...     x: int = 0
...     y: int = 0
>>> entity.components[Vector2] = Vector2(1, 2)
>>> entity.components[Vector2]
Vector2(x=1, y=2)
>>> entity.components |= {int: 11, Vector2: Vector2(0, 0)}  # Multiple values can be assigned like a dict
>>> entity.components[int]
11
>>> entity.components[Vector2]
Vector2(x=0, y=0)

# Queries can be made on all entities of a world with matching components
>>> for e in world.Q.all_of(components=[Vector2]):
...     e.components[Vector2].x += 10
>>> entity.components[Vector2]
Vector2(x=10, y=0)

# You can match components and iterate over them at the same time.  This can be combined with the above
>>> for pos, i in world.Q[Vector2, int]:
...     print((pos, i))
(Vector2(x=10, y=0), 11)

# You can include `Entity` to iterate over entities with their components
# This always iterates over the entity itself instead of an Entity component
>>> for e, pos, i in world.Q[tcod.ecs.Entity, Vector2, int]:
...     print((e, pos, i))
(<Entity...>, Vector2(x=10, y=0), 11)

```

## Named Components

Only one component can be assigned unless that component is given a unique name.
You can name components with the key syntax `(name, type)` when assigning components.
Names are not limited to strings, they are a tag equivalent and can be any hashable or frozen object.
The syntax `[type]` and `[(name, type)]` can be used interchangeably in all places accepting a component key.
Queries on components access named components with the same syntax and must use names explicitly.

```py
>>> entity = world.new_entity()
>>> entity.components[Vector2] = Vector2(0, 0)
>>> entity.components[("velocity", Vector2)] = Vector2(1, 1)
>>> entity.components[("velocity", Vector2)]
Vector2(x=1, y=1)
>>> @attrs.define(frozen=True)
... class Slot:
...     index: int
>>> entity.components |= {  # Like a dict Entity.components can use |= to update items in-place
...     ("hp", int): 10,
...     ("max_hp", int): 12,
...     ("atk", int): 1,
...     str: "foo",
...     (Slot(1), str): "empty",
... }
>>> entity.components[("hp", int)]
10
>>> entity.components[str]
'foo'
>>> entity.components[(Slot(1), str)]
'empty'

# Queries can be made on all named components with the same syntax as normal ones
>>> for e in world.Q.all_of(components=[("hp", int), ("max_hp", int)]):
...     e.components[("hp", int)] = e.components[("max_hp", int)]
>>> entity.components[("hp", int)]
12
>>> for e, pos, delta in world.Q[tcod.ecs.Entity, Vector2, ("velocity", Vector2)]:
...     e.components[Vector2] = Vector2(pos.x + delta.x, pos.y + delta.y)
>>> entity.components[Vector2]
Vector2(x=1, y=1)

```

## Tags

Tags are hashable objects stored in the set-like `Entity.tags`.
These are useful as flags or to group entities together.

```py
>>> entity = world.new_entity()
>>> entity.tags.add("player")  # Works well for groups
>>> "player" in entity.tags
True
>>> entity.tags.add(("eats", "fruit"))
>>> entity.tags.add(("eats", "meat"))
>>> set(world.Q.all_of(tags=["player"])) == {entity}
True

```

## Relations

Use `Entity.relation_components[component_key][target] = component` to associate a target entity with a component.
Use `Entity.relation_tag[tag] = target` to associate a tag exclusively with a target entity.
Use `Entity.relation_tags_many[tag].add(target)` to associate a tag with multiple targets.

Relation queries are a little more complex than other queries.
Relation tags and relation components share the same space then queried, so 'normal' tags should not be in the format of a component key.
Relations are unidirectional, but you can query either end of a relation.

```py
>>> @attrs.define
... class OrbitOf:  # OrbitOf component
...     dist: int
>>> LandedOn = "LandedOn"  # LandedOn tag
>>> star = world.new_entity()
>>> planet = world.new_entity()
>>> moon = world.new_entity()
>>> ship = world.new_entity()
>>> player = world.new_entity()
>>> moon_rock = world.new_entity()
>>> planet.relation_components[OrbitOf][star] = OrbitOf(dist=1000)
>>> moon.relation_components[OrbitOf][planet] = OrbitOf(dist=10)
>>> ship.relation_tag[LandedOn] = moon
>>> moon_rock.relation_tag[LandedOn] = moon
>>> player.relation_tag[LandedOn] = moon_rock
>>> set(world.Q.all_of(relations=[(OrbitOf, planet)])) == {moon}
True
>>> set(world.Q.all_of(relations=[(OrbitOf, ...)])) == {planet, moon}  # Get objects in an orbit
True
>>> set(world.Q.all_of(relations=[(..., OrbitOf, None)])) == {star, planet}  # Get objects being orbited
True
>>> set(world.Q.all_of(relations=[(LandedOn, ...)])) == {ship, moon_rock, player}
True
>>> set(world.Q.all_of(relations=[(LandedOn, ...)]).none_of(relations=[(LandedOn, moon)])) == {player}
True

```

You can use the following table to help with constructing relation queries.
`tag` is a component key if you are querying for a component relation.

| Includes                                                              | Syntax |
| --------------------------------------------------------------------- | :----: |
| Entities with a relation tag to the given target                      | `(tag, target_entity)` |
| Entities with a relation tag to any target                            | `(tag, ...)` |
| Entities which are a relation target of a given entity                | `(origin_entity, tag, None)` |
| Entities which are a target of any entity with the given relation tag | `(..., tag, None)` |
