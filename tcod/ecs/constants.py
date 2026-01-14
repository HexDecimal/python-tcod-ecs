"""Special constants and sentinel values."""

from __future__ import annotations


class _IgnoreSetState(type):
    def __setstate__(cls, _state: object) -> None:
        """Ignore setstate on outdated sentinel-value pickle data."""


class IsA(metaclass=_IgnoreSetState):
    """The default is-a relationship tag used for entity inheritance."""

    def __new__(cls: type[IsA], *_args: object) -> type[IsA]:  # type: ignore[misc]
        """Return own type instead of instance, for outdated sentinel-value pickle data."""
        return cls


_sentinel_IsA = IsA  # Compatibility with sentinel-value, deprecated since 5.4  # noqa: N816
