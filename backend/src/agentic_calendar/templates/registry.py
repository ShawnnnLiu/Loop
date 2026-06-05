"""Milestone-template registry (deterministic seed layer, Phase 5c).

The single source of truth mapping each :class:`GoalClass` to its canned
:class:`MilestoneTemplate`. Templates are skeleton seeds — one per goal class,
3-5 milestones each — that a later stage expands into ``SyllabusModule``s.

Selection from a :class:`UserProfile` is a deterministic, case-folded keyword
scan over the free-text ``goal`` field (the profile carries no goal-class
field). It mirrors the honest fall-through of
``source_claims.classification.classify_source``: an unrecognised goal yields
``None`` rather than a guess. Classes are scanned college-before-graduate on
purpose — ``"undergraduate"`` contains the substring ``"graduate"``, so college
must win first or undergrad goals would mis-route. This is a documented
heuristic skeleton, not personalisation (that is Phase 6).

This is a leaf kernel: it depends only on ``contracts/`` and ``common/``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from agentic_calendar.contracts.common_types import Priority
from agentic_calendar.contracts.milestone_template import (
    GoalClass,
    Milestone,
    MilestoneTemplate,
)
from agentic_calendar.contracts.user_profile import UserProfile

#: Bumped when the *shape* of a template changes. Drives ``task_template`` cache
#: invalidation via ``CacheKey.object_schema_version`` (axiom 18).
TEMPLATE_SCHEMA_VERSION = "milestone-template-v1"


_COLLEGE_ADMISSIONS_TEMPLATE = MilestoneTemplate(
    template_id="college-admissions-skeleton",
    goal_class=GoalClass.COLLEGE_ADMISSIONS,
    template_schema_version=TEMPLATE_SCHEMA_VERSION,
    milestones=[
        Milestone(
            milestone_id="standardized-testing",
            title="Standardized testing",
            offset_days_before_deadline=180,
            target_outcomes=["Target test score reached"],
            priority=Priority.HIGH,
            default_estimated_total_min=3000,
        ),
        Milestone(
            milestone_id="personal-essays",
            title="Personal statement and supplemental essays",
            offset_days_before_deadline=90,
            target_outcomes=[
                "Personal statement drafted",
                "Supplemental essays drafted",
            ],
            priority=Priority.HIGH,
            default_estimated_total_min=2400,
        ),
        Milestone(
            milestone_id="recommendations",
            title="Letters of recommendation",
            offset_days_before_deadline=60,
            target_outcomes=["Recommenders confirmed", "Requests sent"],
            priority=Priority.MEDIUM,
            default_estimated_total_min=300,
        ),
        Milestone(
            milestone_id="financial-aid",
            title="Financial aid and scholarships",
            offset_days_before_deadline=30,
            target_outcomes=["Aid forms submitted", "Scholarship applications sent"],
            priority=Priority.MEDIUM,
            default_estimated_total_min=480,
        ),
        Milestone(
            milestone_id="application-submission",
            title="Application assembly and submission",
            offset_days_before_deadline=14,
            target_outcomes=["Applications submitted"],
            priority=Priority.HIGH,
            default_estimated_total_min=600,
        ),
    ],
)


_GRADUATE_ADMISSIONS_TEMPLATE = MilestoneTemplate(
    template_id="graduate-admissions-skeleton",
    goal_class=GoalClass.GRADUATE_ADMISSIONS,
    template_schema_version=TEMPLATE_SCHEMA_VERSION,
    milestones=[
        Milestone(
            milestone_id="entrance-exam-or-portfolio",
            title="Entrance exam or portfolio",
            offset_days_before_deadline=150,
            target_outcomes=["Target exam score reached or portfolio assembled"],
            priority=Priority.HIGH,
            default_estimated_total_min=2400,
        ),
        Milestone(
            milestone_id="statement-of-purpose",
            title="Statement of purpose",
            offset_days_before_deadline=90,
            target_outcomes=["Statement of purpose drafted and revised"],
            priority=Priority.HIGH,
            default_estimated_total_min=1800,
        ),
        Milestone(
            milestone_id="recommendations",
            title="Letters of recommendation",
            offset_days_before_deadline=60,
            target_outcomes=["Recommenders confirmed", "Requests sent"],
            priority=Priority.MEDIUM,
            default_estimated_total_min=300,
        ),
        Milestone(
            milestone_id="application-submission",
            title="Application assembly and submission",
            offset_days_before_deadline=14,
            target_outcomes=["Applications submitted"],
            priority=Priority.HIGH,
            default_estimated_total_min=600,
        ),
    ],
)


_CAREER_TRANSITION_TEMPLATE = MilestoneTemplate(
    template_id="career-transition-skeleton",
    goal_class=GoalClass.CAREER_TRANSITION,
    template_schema_version=TEMPLATE_SCHEMA_VERSION,
    milestones=[
        Milestone(
            milestone_id="skill-gap-assessment",
            title="Skill-gap assessment",
            offset_days_before_deadline=120,
            target_outcomes=["Target-role skill gaps identified"],
            priority=Priority.HIGH,
            default_estimated_total_min=600,
        ),
        Milestone(
            milestone_id="portfolio-projects",
            title="Portfolio projects",
            offset_days_before_deadline=75,
            target_outcomes=["Portfolio project completed"],
            priority=Priority.HIGH,
            default_estimated_total_min=3600,
        ),
        Milestone(
            milestone_id="resume-and-networking",
            title="Resume refresh and networking",
            offset_days_before_deadline=45,
            target_outcomes=["Resume updated", "Outreach started"],
            priority=Priority.MEDIUM,
            default_estimated_total_min=900,
        ),
        Milestone(
            milestone_id="interview-preparation",
            title="Interview preparation",
            offset_days_before_deadline=14,
            target_outcomes=["Mock interviews completed"],
            priority=Priority.HIGH,
            default_estimated_total_min=1800,
        ),
    ],
)


#: Single source of truth: every :class:`GoalClass` maps to exactly one template.
#: The completeness test (``tests/templates/test_registry.py``) enforces totality.
_TEMPLATES: Mapping[GoalClass, MilestoneTemplate] = MappingProxyType(
    {
        GoalClass.COLLEGE_ADMISSIONS: _COLLEGE_ADMISSIONS_TEMPLATE,
        GoalClass.GRADUATE_ADMISSIONS: _GRADUATE_ADMISSIONS_TEMPLATE,
        GoalClass.CAREER_TRANSITION: _CAREER_TRANSITION_TEMPLATE,
    }
)


#: Deterministic keyword table for :func:`select_template_for_profile`, scanned
#: in order. Matched as case-folded substrings of ``UserProfile.goal``; the first
#: class with any keyword present wins. College precedes graduate so that
#: ``"undergraduate"`` (⊃ ``"graduate"``) routes to college, not graduate.
_GOAL_KEYWORDS: tuple[tuple[GoalClass, tuple[str, ...]], ...] = (
    (GoalClass.COLLEGE_ADMISSIONS, ("college", "undergrad", "bachelor")),
    (
        GoalClass.GRADUATE_ADMISSIONS,
        ("graduate", "grad school", "phd", "ph.d", "master's", "masters", "mba", "doctoral"),
    ),
    (GoalClass.CAREER_TRANSITION, ("career", "interview", "job", "software engineer", "bootcamp")),
)


def get_template(goal_class: GoalClass) -> MilestoneTemplate:
    """Return the canned template for ``goal_class``.

    Total: every :class:`GoalClass` is registered (enforced by the registry
    completeness test), so this never raises for a valid enum member.
    """
    return _TEMPLATES[goal_class]


def list_templates() -> tuple[MilestoneTemplate, ...]:
    """Return all registered templates in ``GoalClass`` declaration order."""
    return tuple(_TEMPLATES.values())


def select_template_for_profile(profile: UserProfile) -> MilestoneTemplate | None:
    """Return the milestone template matching ``profile.goal``, or ``None``.

    Deterministic: a case-folded substring scan of ``profile.goal`` against
    :data:`_GOAL_KEYWORDS`. No fuzzy/ML matching and no guessing — an
    unrecognised goal returns ``None`` so the caller decides what to do,
    mirroring ``classify_source``'s ``UNCLASSIFIED`` fall-through.
    """
    goal = profile.goal.casefold()
    for goal_class, keywords in _GOAL_KEYWORDS:
        if any(keyword in goal for keyword in keywords):
            return _TEMPLATES[goal_class]
    return None
