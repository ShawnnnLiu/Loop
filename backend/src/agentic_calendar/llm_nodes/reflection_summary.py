"""Reflection-summary node — deterministic Phase 4 implementation.

The reflection node *explains* drift to the user in friendly language. Per
axiom 07 it must never *classify* drift: it consumes already-classified
:class:`DriftEvent` objects (produced deterministically by ``drift/``) and turns
them into short, behavior-only copy. Like ``DeterministicUserFacingExplanation``,
this Phase-4 version is a deterministic fake — the same typed inputs always
produce the same summary, so tests assert on results, not prompt wording.
Phase 8 swaps a real mid-tier LLM adapter in behind this same surface.

Two boundary guarantees enforced here:

* **No control-plane leakage.** The summary is derived from typed drift events;
  it introduces no new source of truth.
* **No psychological labels** (axiom 07). Output is scanned for trust-breaking
  identity language and rejected if any appears — a guard that matters most once
  a real model writes the prose.

This node imports only ``contracts`` (the :class:`DriftEvent` shape), never the
``drift`` or ``telemetry`` regions, so the LLM boundary stays independent of them.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.drift_event import DriftEvent, DriftType

from .base import LLMNodeError

#: Identity/trait words the system must never emit about a user (axiom 07
#: "Psychological Labeling Restrictions"). Behavior is describable; identity is
#: not. Matched on word boundaries so ordinary words are unaffected.
_PSYCH_DENYLIST: frozenset[str] = frozenset(
    {
        "lazy",
        "unmotivated",
        "irresponsible",
        "avoidant",
        "anxious",
        "undisciplined",
        "careless",
        "procrastinator",
        "procrastinating",
        "apathetic",
        "negligent",
        "incompetent",
    }
)


def _ensure_no_psychological_labels(text: str) -> None:
    lowered = text.lower()
    for term in _PSYCH_DENYLIST:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            raise LLMNodeError(
                f"reflection summary contains forbidden psychological label "
                f"{term!r} (axiom 07: describe behavior, not identity)"
            )


def _format_categories(event: DriftEvent) -> str:
    return ", ".join(
        c.value.replace("_", " ") for c in event.evidence.affected_categories
    )


def _explain(event: DriftEvent) -> str:
    """Behavior-only, action-oriented one-liner for a single drift event."""
    dt = event.drift_type
    cats = _format_categories(event)
    if dt is DriftType.DURATION_UNDERESTIMATE:
        return (
            f"{cats.capitalize()} tasks are taking longer than planned; "
            "their time estimates will be increased."
        )
    if dt is DriftType.DURATION_OVERESTIMATE:
        return (
            f"{cats.capitalize()} tasks are finishing faster than planned; "
            "their time estimates will be reduced."
        )
    if dt is DriftType.CAPACITY_MISMATCH:
        return (
            "Completed study time has been below the weekly plan; "
            "the weekly load can be reduced or the timeline extended."
        )
    if dt is DriftType.TOPIC_AVOIDANCE:
        return (
            f"{cats.capitalize()} tasks have been moved or missed more than "
            "others; they can be split into smaller steps."
        )
    if dt is DriftType.EXTERNAL_CONFLICT:
        return (
            "Several tasks ran into calendar conflicts; they can be "
            "rescheduled without changing the plan."
        )
    if dt is DriftType.LOW_ENGAGEMENT:
        return (
            "Completion has been low across several areas; it may help to "
            "adjust the goal or scope."
        )
    if dt is DriftType.DEPENDENCY_BLOCKED:
        return (
            "Some tasks are waiting on an earlier task that hasn't been "
            "finished; that earlier task can be rescheduled first."
        )
    if dt is DriftType.CALENDAR_FRAGMENTATION:
        return (
            "There is enough total free time, but no single block is long "
            "enough for deep-work tasks; those tasks can be split or larger "
            "blocks opened."
        )
    # Unreachable while DriftType is exhaustively handled above; kept typed.
    raise LLMNodeError(f"no reflection phrasing for drift_type {dt.value!r}")


class ReflectionSummary(BaseModel):
    """A short, structured, user-facing summary of recent plan drift."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1)
    detail: list[str] = Field(default_factory=list)


class DeterministicReflectionSummary:
    """Compose a behavior-only summary from classified drift events.

    Deterministic stand-in for the Phase 8 LLM-backed node; takes the same
    typed inputs and returns the same :class:`ReflectionSummary` contract.
    """

    def run(
        self,
        *,
        run_id: str,
        drift_events: Sequence[DriftEvent],
        completion_rate: float | None = None,
    ) -> ReflectionSummary:
        del run_id  # correlation only; deterministic output

        detail: list[str] = []
        if completion_rate is not None:
            detail.append(
                f"You've completed {round(completion_rate * 100)}% of recent "
                "scheduled tasks."
            )
        detail.extend(_explain(e) for e in drift_events)

        if not drift_events:
            summary = "Your plan is on track."
        else:
            n = len(drift_events)
            plural = "s" if n != 1 else ""
            summary = (
                f"{n} adjustment{plural} suggested based on your recent activity."
            )

        _ensure_no_psychological_labels(summary)
        for line in detail:
            _ensure_no_psychological_labels(line)

        return ReflectionSummary(summary=summary, detail=detail)
