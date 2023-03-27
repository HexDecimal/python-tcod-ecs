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
