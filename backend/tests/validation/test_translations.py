"""Tests for the deterministic ``ViolationType`` → user-facing translation table.

Axiom 04 says LLMs must not invent translations. The table here is the only
source. We assert completeness so a new ``ViolationType`` cannot be added
without also adding its translation.
"""

from __future__ import annotations

from agentic_calendar.contracts.translations import USER_FACING, user_facing
from agentic_calendar.contracts.violation_types import ViolationType


def test_every_violation_type_has_translation() -> None:
    missing = [v for v in ViolationType if v not in USER_FACING]
    assert missing == [], f"missing translations for: {missing}"


def test_user_facing_returns_string() -> None:
    for v in ViolationType:
        s = user_facing(v)
        assert isinstance(s, str)
        assert s
