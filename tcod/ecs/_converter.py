from __future__ import annotations

import functools
from collections import defaultdict
from typing import Any, Callable, get_args, get_origin

import cattrs


def _is_defaultdict_type(type_hint: object) -> bool:
    """Return True if `type_hint` is a defaultdict type-hint."""
    return get_origin(type_hint) is defaultdict


def _setup_defaultdict_factory(type_hint: type[defaultdict[Any, Any] | object]) -> Callable[[], Any]:
    """Return the factory value for a defaultdict given its value type-hint."""
    assert type_hint is not Any  # type: ignore[comparison-overlap]
    if get_origin(type_hint) is not defaultdict:
        return get_origin(type_hint) or type_hint
    return functools.partial(defaultdict, _setup_defaultdict_factory(get_args(type_hint)[1]))


def _get_converter() -> cattrs.Converter:
    """Return a cattrs converter configured for tcod.ecs.

    This converter is only for structuring.
    """
    converter = cattrs.Converter()

    def _structure_defaultdict(obj: dict[Any, Any], type_hint: type[Any]) -> defaultdict[Any, Any]:
        """Structure a dict into a nested defaultdict."""
        key_type, value_type = get_args(type_hint)
        return defaultdict(
            _setup_defaultdict_factory(value_type),
            (
                (converter.structure(key, key_type), converter.structure(value, value_type))
                for key, value in obj.items()
            ),
        )

    converter.register_structure_hook_func(_is_defaultdict_type, _structure_defaultdict)

    return converter
