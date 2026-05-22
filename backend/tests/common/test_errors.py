"""Tests for ``agentic_calendar.common.errors``."""

from __future__ import annotations

import pytest

from agentic_calendar.common.errors import (
    AgenticCalendarError,
    ContractError,
    InvariantError,
)


def test_hierarchy() -> None:
    assert issubclass(ContractError, AgenticCalendarError)
    assert issubclass(InvariantError, AgenticCalendarError)
    assert issubclass(AgenticCalendarError, Exception)


def test_can_be_raised_and_caught_by_base() -> None:
    with pytest.raises(AgenticCalendarError):
        raise ContractError("nope")
    with pytest.raises(AgenticCalendarError):
        raise InvariantError("nope")


def test_carries_message() -> None:
    err = ContractError("bad data")
    assert str(err) == "bad data"
