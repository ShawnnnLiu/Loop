"""Tests for ``llm_nodes.strategist.FixtureStrategist``."""

from __future__ import annotations

import pytest

from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.llm_nodes import FixtureStrategist
from agentic_calendar.llm_nodes.base import LLMNodeError
from tests._fixture_loader import iter_valid


def _user_profile() -> UserProfile:
    return UserProfile.model_validate(next(iter_valid("user_profile")).payload)


def _syllabus() -> SyllabusUnits:
    return SyllabusUnits.model_validate(next(iter_valid("syllabus_units")).payload)


def test_returns_fixture_keyed_by_target_role() -> None:
    user = _user_profile()
    syllabus = _syllabus()
    node = FixtureStrategist({user.target_role: syllabus})
    out = node.run(run_id="run_001", user_profile=user)
    assert isinstance(out, SyllabusUnits)
    assert out.syllabus_version == syllabus.syllabus_version


def test_unknown_role_raises_llm_node_error() -> None:
    user = _user_profile()
    syllabus = _syllabus()
    node = FixtureStrategist({"Some Other Role": syllabus})
    with pytest.raises(LLMNodeError) as exc_info:
        node.run(run_id="run_001", user_profile=user)
    assert "target_role" in str(exc_info.value)


def test_empty_fixtures_rejected() -> None:
    with pytest.raises(ValueError):
        FixtureStrategist({})


def test_returned_object_is_revalidated() -> None:
    """Even if the fixture is mutated in-flight, the returned object is a fresh model."""
    user = _user_profile()
    syllabus = _syllabus()
    node = FixtureStrategist({user.target_role: syllabus})
    out = node.run(run_id="r", user_profile=user)
    assert out is not syllabus
