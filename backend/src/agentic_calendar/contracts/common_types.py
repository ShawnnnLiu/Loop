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
