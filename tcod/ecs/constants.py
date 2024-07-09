"""Special constants and sentinel values."""

from __future__ import annotations

from typing import Final

from sentinel_value import sentinel

IsA: Final = sentinel("IsA")
"""The default is-a relationship tag used for entity inheritance."""
