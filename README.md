# About

[![PyPI](https://img.shields.io/pypi/v/tcod-ec)](https://pypi.org/project/tcod-ecs/)
[![PyPI - License](https://img.shields.io/pypi/l/tcod-ecs)](https://github.com/HexDecimal/python-tcod-ecs/blob/main/LICENSE)
[![Documentation Status](https://readthedocs.org/projects/python-tcod-ecs/badge/?version=latest)](https://python-tcod-ecs.readthedocs.io)
[![codecov](https://codecov.io/gh/HexDecimal/python-tcod-ecs/branch/main/graph/badge.svg?token=4Ak5QpTLZB)](https://codecov.io/gh/HexDecimal/python-tcod-ecs)

This is an [Entity-component-system](https://en.wikipedia.org/wiki/Entity_component_system) implemented in Python.
See the [ECS FAQ](https://github.com/SanderMertens/ecs-faq) for more info.

This implementation focuses on type-hinting, organization, and is designed to work well with Python.
The following features are currently implemented:

- Entities can have store components which are instances of any Python object. Components are looked up by their type.
- Entities can have one instance of a type, or multiple instances of a type with a string or other hashable to differentiate them.
- Components can be registered as abstract, allowing a base type to hold subclasses of that component.
- Entity tags are distinct from components, tags are any hashable Python object rather than empty class.
- Entity relationships are supported, either as many-to-many or many-to-one relationships.
- ECS Queries can be made to fetch entities having a combination of components/tags/relations or the absence of such.

A lightweight version which implements only the entity-component framework exists called [tcod-ec](https://pypi.org/project/tcod-ec/).

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
>>> world = tcod.ecs.World()  # New empty world.

```

## Entity

New entities can be created with `World.new_entity`.
An entity always knows about its assigned world.
Worlds only know about their entities once the entity is assigned a name, component, tag, or relation.
An entity is identified by its "Python identity" rather than with a low-level stand-in identifier.

```py

>>> entity = world.new_entity(name="MyEntity")  # Name is optional and can be any hashable, not just str.
>>> entity
<Entity name='MyEntity'>
>>> entity.world is world  # Worlds can always be accessed from their entity.
True
>>> world.named["MyEntity"]  # Named entities can be accessed with `World.named`.
<Entity name='MyEntity'>
>>> world.named.get("Missing") is None  # `World.named` acts like a dictionary, including assignment and `.get()`.
True

```

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
KeyError: <Entity ...>
>>> entity.components.get(int, "default")  # Test keys with `.get()` like a dictionary.
'default'
>>> @attrs.define
... class Vector2:
...     x: int = 0
...     y: int = 0
>>> entity.components[Vector2] = Vector2(1, 2)
>>> entity.components[Vector2]
Vector2(x=1, y=2)
>>> entity.components.set(Vector2(3, 4))  # Shorter syntax derives the type from the value when assigning a component.
>>> entity.components[Vector2]
Vector2(x=3, y=4)
>>> entity.components.update_values([11, Vector2(0, 0)])  # Multiple values can be assigned without keys.
>>> entity.components[int]
11
>>> entity.components[Vector2]
Vector2(x=0, y=0)

# Queries can be made on all entities of a world with matching components.
>>> for e in world.Q.all_of(components=[Vector2]):
...     e.components[Vector2].x += 10
>>> entity.components[Vector2]
Vector2(x=10, y=0)

# You can match components and iterate over them at the same time.  This can be combined with the above.
>>> for pos, i in world.Q[Vector2, int]:
...     print((pos, i))
(Vector2(x=10, y=0), 11)

# You can include `Entity` to iterate over entities with their components.
# This always iterates over the entity itself instead of an Entity component.
>>> for e, pos, i in world.Q[tcod.ecs.Entity, Vector2, int]:
...     print((e, pos, i))
(<Entity ...>, Vector2(x=10, y=0), 11)

```

## Named Components

Only one component can be assigned unless that component is given a unique name.
You can name components with the key syntax `(name, type)` when assigning components.
Names are not limited to strings, and can be any hashable or frozen object.
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
>>> entity.components.update(  # Like a dict Entity.components has the `.update()` method.
...     {
...         ("hp", int): 10,
...         ("max_hp", int): 12,
...         ("atk", int): 1,
...         str: "foo",
...         (Slot(1), str): "empty",
...     }
... )
>>> entity.components[("hp", int)]
10
>>> entity.components[str]
'foo'
>>> entity.components[(Slot(1), str)]
'empty'

# Queries can be made on all named components with the same syntax as normal ones.
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



```py
>>> star = world.new_entity()
>>> planet = world.new_entity()
>>> moon = world.new_entity()
>>> ship = world.new_entity()
>>> player = world.new_entity()
>>> moon_rock = world.new_entity()
>>> OrbitOf = "OrbitOf"
>>> LandedOn = "LandedOn"
>>> planet.relations[OrbitOf] = star
>>> moon.relations[OrbitOf] = planet
>>> ship.relations[LandedOn] = moon
>>> moon_rock.relations[LandedOn] = moon
>>> player.relations[LandedOn] = moon_rock
>>> set(world.Q.all_of(relations=[(OrbitOf, planet)])) == {moon}
True
>>> set(world.Q.all_of(relations=[(OrbitOf, None)])) == {planet, moon}
True
>>> set(world.Q.all_of(relations=[(LandedOn, None)])) == {ship, moon_rock, player}
True
>>> set(world.Q.all_of(relations=[(LandedOn, None)]).none_of(relations=[(LandedOn, moon)])) == {player}
True

```
