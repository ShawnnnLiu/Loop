"""Tests for ``MotivationProfile``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.motivation_profile import MotivationProfile
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "motivation_profile"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    mp = MotivationProfile.model_validate(payload)
    assert mp.motivation_profile_id == payload["motivation_profile_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        MotivationProfile.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_defaults_applied() -> None:
    minimal = {
        "motivation_profile_id": "mot_d",
        "user_id": "user_d",
        "profile_version": "v1",
        "self_motivation_level": "medium",
        "procrastination_risk": "low",
        "pressure_tolerance": "medium",
        "weekly_checkin_enabled": False,
        "created_at": "2026-04-28T12:00:00-07:00",
        "updated_at": "2026-04-28T12:00:00-07:00",
    }
    mp = MotivationProfile.model_validate(minimal)
    assert mp.missed_task_escalation_threshold == 2
    assert mp.behind_schedule_intervention_threshold_pct == 20
    assert mp.sponsor_enabled is False
    assert mp.sponsor_visibility_level.value == "none"
    assert mp.quiet_hours.start == "22:00"
    assert mp.quiet_hours.end == "08:00"
