"""Shared pytest fixtures.

Phase 1 only needs deterministic clock + ID injection. As more regions land,
fixture loaders for ``tests/fixtures/{valid,invalid}/...`` will be added here.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator


@pytest.fixture
def frozen_clock() -> FrozenClock:
    """A clock pinned at 2026-05-04T12:00:00Z (matches several spec examples)."""
    return FrozenClock(datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC))


@pytest.fixture
def id_gen() -> DeterministicIdGenerator:
    """Counter-based ID generator. Each prefix starts at 1."""
    return DeterministicIdGenerator(digits=3)
