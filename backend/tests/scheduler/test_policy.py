"""Tests for ``scheduler.policy.policy_from_user_profile``."""

from __future__ import annotations

from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.scheduler.policy import policy_from_user_profile
from tests._fixture_loader import iter_valid


def test_policy_mirrors_user_profile_constraints() -> None:
    user = UserProfile.model_validate(next(iter_valid("user_profile")).payload)
    policy = policy_from_user_profile(user)
    assert policy.no_events_before == user.hard_constraints.no_events_before
    assert policy.no_events_after == user.hard_constraints.no_events_after
    assert policy.allow_weekends == user.hard_constraints.allow_weekends
    assert policy.max_daily_study_min == user.hard_constraints.max_daily_study_min
    assert (
        policy.min_break_between_deep_blocks_min
        == user.hard_constraints.min_break_between_deep_blocks_min
    )
    assert policy.max_session_length_min == user.max_session_length_min
    assert policy.preferred_session_length_min == user.preferred_session_length_min
    assert policy.prefer_evening_sessions == user.preferences.prefer_evening_sessions
    assert (
        policy.prefer_weekend_long_blocks == user.preferences.prefer_weekend_long_blocks
    )
    assert (
        policy.avoid_back_to_back_deep_work
        == user.preferences.avoid_back_to_back_deep_work
    )
    assert len(policy.deep_work_windows) == len(user.deep_work_windows)


def test_policy_carries_all_soft_preferences_when_set() -> None:
    """All three soft-preference booleans survive the profile → policy mapping.

    The valid fixture leaves ``prefer_weekend_long_blocks`` at ``False`` (the
    policy default), so the mirror test above cannot distinguish "copied" from
    "defaulted" for it. Flip every preference on and assert each lands.
    """
    payload = dict(next(iter_valid("user_profile")).payload)
    payload["preferences"] = {
        "prefer_evening_sessions": True,
        "prefer_weekend_long_blocks": True,
        "avoid_back_to_back_deep_work": True,
    }
    user = UserProfile.model_validate(payload)
    policy = policy_from_user_profile(user)
    assert policy.prefer_evening_sessions is True
    assert policy.prefer_weekend_long_blocks is True
    assert policy.avoid_back_to_back_deep_work is True
