"""ECS callback management."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from tcod.ecs.entity import Entity
    from tcod.ecs.typing import ComponentKey


type _OnComponentChangedFunc[T] = Callable[[Entity, T | None, T | None], None]
_OnComponentChangedFuncT = TypeVar("_OnComponentChangedFuncT", bound=_OnComponentChangedFunc[Any])

_on_component_changed_callbacks: dict[ComponentKey[Any], list[_OnComponentChangedFunc[Any]]] = {}


def register_component_changed(
    *,
    component: ComponentKey[Any],
) -> Callable[[_OnComponentChangedFuncT], _OnComponentChangedFuncT]:
    """Return a decorator to register on-component-changed callback functions.

    Example::

        >>> import tcod.ecs.callbacks
        >>> @tcod.ecs.callbacks.register_component_changed(component=int)
        ... def on_int_changed(entity: Entity, old: int | None, new: int | None) -> None:
        ...    if old is not None and new is not None:
        ...        print(f"int changed from {old} to {new}")
        ...    elif old is not None and new is None:
        ...        print(f"int value {old} was deleted")
        ...    else:
        ...        assert old is None and new is not None
        ...        print(f"int value {new} was added")
        >>> entity.components[int] = 2
        int value 2 was added
        >>> entity.components[int] = 5
        int changed from 2 to 5
        >>> del entity.components[int]
        int value 5 was deleted
        >>> tcod.ecs.callbacks.unregister_component_changed(callback=on_int_changed, component=int)
    """

    def register(callback: _OnComponentChangedFuncT) -> _OnComponentChangedFuncT:
        _on_component_changed_callbacks.setdefault(component, []).append(callback)
        return callback

    return register


def unregister_component_changed[T](callback: _OnComponentChangedFunc[T], *, component: ComponentKey[T]) -> None:
    """Unregister a registered on-component-changed callback function."""
    _on_component_changed_callbacks[component].remove(callback)


def _on_component_changed[T](key: ComponentKey[T], entity: Entity, old: T | None, new: T | None) -> None:
    for callback in _on_component_changed_callbacks.get(key, ()):
        callback(entity, old, new)
