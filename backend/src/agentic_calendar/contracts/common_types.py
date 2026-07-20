"""Shared primitive types used across multiple contract modules.

These exist so the day-of-week enum, ``HH:MM`` time string, and other small
shared shapes have a single canonical definition. Contract modules import
from here rather than redeclaring.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator

HHMM_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _validate_hhmm(value: str) -> str:
    """Ensure a string is a valid ``HH:MM`` 24-hour clock value."""
    if not HHMM_PATTERN.fullmatch(value):
        raise ValueError(f"expected HH:MM 24-hour format, got {value!r}")
    return value


HHMM = Annotated[str, AfterValidator(_validate_hhmm)]
"""24-hour clock string in the form ``"HH:MM"`` (e.g. ``"22:30"``)."""


class Day(StrEnum):
    """Day-of-week token used everywhere a single weekday is referenced."""

    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceKind(StrEnum):
    """Closed classification of one confirmed evidence item.

    Shared by ``ExperienceItem.kind`` (user-profile spec) and
    ``EvidenceSlot.required_kinds`` (pathway-template spec). Closed for humans
    too: kinds are join keys for the deterministic ``narrative/`` kernel, so
    the UI offers the same fixed dropdown the LLM proposal is bound to.
    """

    WORK = "work"
    PROJECT = "project"
    VOLUNTEERING = "volunteering"
    LEADERSHIP = "leadership"
    RESEARCH = "research"
    AWARD = "award"
    COURSEWORK = "coursework"


class KnowledgeNodeKind(StrEnum):
    """What a knowledge-map node represents (pathway-template spec, KT-A).

    ``skill`` nodes are taxonomy-anchored and live in exactly one group;
    ``capstone`` nodes are branch-level (one per evidence slot) and belong to
    no group. There are no other kinds and no edges between nodes.
    """

    SKILL = "skill"
    CAPSTONE = "capstone"


class MasteryTier(StrEnum):
    """The four-state deterministic mastery ladder (knowledge-map, KT-A).

    Computed by the ``narrative/`` map-state kernel (KT-B) from stored records;
    an LLM never assigns, names, or explains a tier. ``target_tier`` on a
    ``MasterySetPoint`` (knowledge-map-overlay spec) is a member of this enum.
    """

    DISCOVERED = "discovered"
    """On the map, no work yet."""
    TRAINING = "training"
    """Work underway (a linked task, or basis below the honed bar)."""
    HONED = "honed"
    """The study happened, or the user self-assessed ownership."""
    PROVEN = "proven"
    """Honed and backed by a confirmed evidence anchor (pathway nodes only)."""


class MasteryGrantSource(StrEnum):
    """What onboarding flow produced a ``MasteryGrant`` (knowledge-map-overlay
    spec, KT-A). The only two flows allowed to write mastery grants."""

    ONBOARDING = "onboarding"
    EVIDENCE = "evidence"


class TaskCategory(StrEnum):
    """Allowed values for ``task.category`` (see task-plan spec)."""

    CONCEPT_REVIEW = "concept_review"
    PRACTICE = "practice"
    MOCK_INTERVIEW = "mock_interview"
    PROJECT = "project"
    REFLECTION = "reflection"
    REVIEW = "review"


class FocusLevel(StrEnum):
    """Allowed values for ``task.required_focus_level``."""

    LIGHT = "light"
    MEDIUM = "medium"
    DEEP = "deep"


class AccountabilityStatus(StrEnum):
    """Deterministic accountability/progress status (axiom 21 ``current_status``).

    Shared by the sponsor report (Phase 3) and, later, the Accountability State
    projection and Policy Engine (Phase 7). Computed deterministically from
    thresholds; never inferred by the LLM.
    """

    ON_TRACK = "on_track"
    SLIGHTLY_BEHIND = "slightly_behind"
    BEHIND = "behind"
    FAR_BEHIND = "far_behind"
    DISENGAGED = "disengaged"
