"""Tests for the milestone-template registry (Phase 5c)."""

from __future__ import annotations

import pytest

from agentic_calendar.cache import CacheKey, CacheTarget
from agentic_calendar.contracts.milestone_template import GoalClass, MilestoneTemplate
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.templates import (
    TEMPLATE_SCHEMA_VERSION,
    get_template,
    list_templates,
    select_template_for_profile,
)
from tests._fixture_loader import iter_valid


def _profile_with_goal(goal: str) -> UserProfile:
    payload = dict(next(iter_valid("user_profile")).payload)
    payload["goal"] = goal
    return UserProfile.model_validate(payload)


def test_every_goal_class_has_a_registered_template() -> None:
    """Registry completeness — analogous to the drift mapping-completeness test."""
    for goal_class in GoalClass:
        template = get_template(goal_class)
        assert isinstance(template, MilestoneTemplate)
        assert template.goal_class is goal_class


def test_list_templates_returns_one_per_goal_class() -> None:
    templates = list_templates()
    assert len(templates) == len(GoalClass)
    assert {t.goal_class for t in templates} == set(GoalClass)


def test_templates_share_the_module_schema_version() -> None:
    for template in list_templates():
        assert template.template_schema_version == TEMPLATE_SCHEMA_VERSION


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        ("Get into a top college for undergraduate CS", GoalClass.COLLEGE_ADMISSIONS),
        ("Undergraduate admissions help", GoalClass.COLLEGE_ADMISSIONS),
        ("Graduate school admissions for a PhD", GoalClass.GRADUATE_ADMISSIONS),
        ("Earn a master's in data science", GoalClass.GRADUATE_ADMISSIONS),
        ("Career transition into software engineering", GoalClass.CAREER_TRANSITION),
        ("Prepare for backend interview loops", GoalClass.CAREER_TRANSITION),
    ],
)
def test_select_template_for_profile_matches_goal(
    goal: str, expected: GoalClass
) -> None:
    template = select_template_for_profile(_profile_with_goal(goal))
    assert template is not None
    assert template.goal_class is expected


def test_select_template_for_profile_returns_none_on_no_match() -> None:
    profile = _profile_with_goal("Learn to bake sourdough")
    assert select_template_for_profile(profile) is None


def test_select_template_for_profile_is_case_insensitive_and_deterministic() -> None:
    profile = _profile_with_goal("CAREER TRANSITION, no matter the case")
    first = select_template_for_profile(profile)
    second = select_template_for_profile(profile)
    assert first is not None
    assert first.goal_class is GoalClass.CAREER_TRANSITION
    assert first == second


def test_undergraduate_does_not_route_to_graduate() -> None:
    """``"undergraduate"`` contains ``"graduate"``; college must win."""
    template = select_template_for_profile(
        _profile_with_goal("undergraduate applications")
    )
    assert template is not None
    assert template.goal_class is GoalClass.COLLEGE_ADMISSIONS


def test_template_schema_version_drives_task_template_cache_key() -> None:
    """Axiom-18 convention: a ``task_template`` cache key carries the template's
    ``template_schema_version`` as ``object_schema_version``, so bumping it
    invalidates the entry. No production producer assembles these yet; this pins
    the intended ``templates/`` <-> ``cache/`` linkage the doc references.
    """
    template = get_template(GoalClass.CAREER_TRANSITION)

    def key_for(object_schema_version: str) -> CacheKey:
        return CacheKey(
            target=CacheTarget.TASK_TEMPLATE,
            role_target=template.goal_class.value,
            freshness_window="2026-06",
            object_schema_version=object_schema_version,
        )

    live = key_for(template.template_schema_version)
    assert live.fingerprint() == key_for(template.template_schema_version).fingerprint()
    assert live.fingerprint() != key_for("milestone-template-v2").fingerprint()
    assert template.template_schema_version == TEMPLATE_SCHEMA_VERSION
