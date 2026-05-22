"""Tests for ``scheduler.inputs``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentic_calendar.scheduler.inputs import FreeBusyInterval


def test_free_busy_requires_aware() -> None:
    with pytest.raises(ValidationError):
        FreeBusyInterval(start=datetime(2026, 5, 4, 8), end=datetime(2026, 5, 4, 9))


def test_free_busy_end_after_start() -> None:
    with pytest.raises(ValidationError):
        FreeBusyInterval(
            start=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
            end=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
        )
