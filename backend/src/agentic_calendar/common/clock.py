"""Injectable clock abstraction.

Determinism requires that ``datetime.now()`` never appears in production code
outside this module. Every region that needs the current time accepts a
``Clock`` and tests inject ``FrozenClock`` to replay scenarios deterministically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Read-only clock interface used by every region that needs time."""

    def now(self) -> datetime:
        """Return the current timezone-aware datetime in UTC."""
        ...


class SystemClock:
    """Production clock backed by ``datetime.now(UTC)``.

    The constructor takes no arguments; use this as the default in production
    wiring and override it in tests.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Test clock that always returns a fixed instant.

    Use ``advance(seconds=...)`` to step forward deterministically inside a
    test. Never used in production; placed in ``common`` so every region's
    test suite imports the same implementation.
    """

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FrozenClock requires a timezone-aware datetime")
        self._instant = instant

    def now(self) -> datetime:
        return self._instant

    def advance(self, *, seconds: int = 0, minutes: int = 0, hours: int = 0) -> None:
        from datetime import timedelta

        self._instant = self._instant + timedelta(
            seconds=seconds, minutes=minutes, hours=hours
        )
