"""ECS callback management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, TypeVar, Union

from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from tcod.ecs.entity import Entity
    from tcod.ecs.typing import ComponentKey

_T = TypeVar("_T")

_OnComponentChangedFunc: TypeAlias = Callable[["Entity", Union[_T, None], Union[_T, None]], None]
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


def unregister_component_changed(callback: _OnComponentChangedFunc[_T], *, component: ComponentKey[_T]) -> None:
    """Unregister a registered on-component-changed callback function."""
    _on_component_changed_callbacks[component].remove(callback)


def _on_component_changed(key: ComponentKey[_T], entity: Entity, old: _T | None, new: _T | None) -> None:
    for callback in _on_component_changed_callbacks.get(key, ()):
        callback(entity, old, new)
