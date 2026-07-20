"""User-facing-explanation node.

This node turns a deterministic outcome into user-readable text, without
introducing any new source of truth. It carries three prompt targets, all
explanation-only and all disposed of by the deterministic core:

- **validation explanation** (Phase 1): words a ``ValidationResult``. The
  translations are a static, reviewable mapping in
  :mod:`agentic_calendar.contracts.translations` (``ViolationType`` -> message).
- **pathway fit note** (NP-F): 2-3 sentences per pathway card explaining how the
  user's *already-confirmed* evidence carries the filled pillars. It decorates a
  ranking the ``narrative/`` kernel already produced; it never ranks.
- **story summary** (NP-F): a "where your package stands" paragraph over the
  selected pathway's deterministic slot states.

Keeping the *deterministic* twin here (the keyless dev server + the test oracle)
ensures the same typed inputs always produce the same explanation (replayable),
tests assert on results rather than prompt wording, and user-facing copy never
becomes an LLM-controlled control plane. The real Anthropic twin lives in
``anthropic_adapter.py`` behind the same surface; both are scanned by the same
deterministic post-checks (prestige denylist + psychological-label denylist +
no-numerals-as-scores) so the story prose can never smuggle a ranking, a score,
or an identity judgment onto the screen.

The story targets are groundedness-safe by construction: their inputs are the
kernel's coverage result (filled/empty slot states + curated pillar titles), a
confirmed-then-structured artifact, never the raw résumé. Fit, gaps, and slot
counts stay 100% deterministic (axiom 00); the prose only explains them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.translations import user_facing
from agentic_calendar.contracts.validation_result import ValidationResult

#: Length ceilings for the story prose. Enforced by the contract (so a runaway
#: model output is a schema rejection routed through the bounded repair loop,
#: not an oversized note on screen) and honored by the deterministic twin.
_NOTE_MAX = 700
_SUMMARY_MAX = 700
_DETAIL_LINE_MAX = 300


class UserExplanation(BaseModel):
    """The structured wrapper for user-visible copy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1)
    detail: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Story-layer prose (NP-F): fit notes + story summary
# --------------------------------------------------------------------------- #
#
# Slot ``state`` is carried as an opaque label ("filled" / "partial" / "empty")
# rather than the ``narrative/`` SlotState enum: this node is prose-only and must
# not depend on the kernel region (import-linter independence set). The
# composition root projects the kernel's coverage into these shapes.


class FitNoteSlot(BaseModel):
    """One pillar's deterministic coverage, as the prose node sees it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1)
    state: str = Field(min_length=1)
    matched_titles: tuple[str, ...] = ()
    """Confirmed evidence titles the kernel matched to this pillar (may be
    empty). Advisory context for the prose; never echoed as a score."""


class FitNoteRequest(BaseModel):
    """The structured spine + coverage for one pathway card's fit note."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathway_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    spine: str = Field(min_length=1)
    audience_note: str = Field(min_length=1)
    slots: tuple[FitNoteSlot, ...]


class PathwayFitNote(BaseModel):
    """One pathway's fit note, keyed by ``pathway_id`` for exact card mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathway_id: str = Field(min_length=1)
    note: str = Field(min_length=1, max_length=_NOTE_MAX)


class PathwayFitNotes(BaseModel):
    """The batched output: one note per requested card (see the id-set check)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    notes: tuple[PathwayFitNote, ...]


class StorySummaryRequest(BaseModel):
    """The selected pathway's spine + slot states for the story summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathway_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    spine: str = Field(min_length=1)
    slots: tuple[FitNoteSlot, ...]


class StorySummary(BaseModel):
    """A short "where your package stands" paragraph plus per-pillar lines."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1, max_length=_SUMMARY_MAX)
    detail: tuple[str, ...] = ()


def _filled(slots: tuple[FitNoteSlot, ...]) -> list[str]:
    return [s.title for s in slots if s.state == "filled"]


def _open(slots: tuple[FitNoteSlot, ...]) -> list[str]:
    return [s.title for s in slots if s.state != "filled"]


def _join(titles: list[str]) -> str:
    """Oxford-style join of curated pillar titles (never user free text, so the
    result is always digit-free of any score shape)."""
    if len(titles) == 1:
        return titles[0]
    if len(titles) == 2:
        return f"{titles[0]} and {titles[1]}"
    return f"{', '.join(titles[:-1])}, and {titles[-1]}"


def _deterministic_fit_note(request: FitNoteRequest) -> str:
    """A clean-by-construction fit note: it references only curated pillar
    titles and the pathway display name (no user free text, no digits, no
    prestige or identity language), so it passes the story-prose scanner the
    Anthropic twin's output is held to."""
    filled = _filled(request.slots)
    open_ = _open(request.slots)
    name = request.display_name
    if not filled and open_:
        return (
            f"Your confirmed evidence doesn't back any pillar of the {name} story "
            f"yet — a clean start. Your plan can build toward {_join(open_)}."
        )
    if filled and not open_:
        return (
            f"Every pillar of the {name} story is already backed by your confirmed "
            f"evidence: {_join(filled)}."
        )
    return (
        f"Your confirmed evidence already carries {_join(filled)} in the {name} "
        f"story. The pillars still open are {_join(open_)}, which your plan can "
        f"prioritize."
    )


def _deterministic_story_summary(
    request: StorySummaryRequest,
) -> tuple[str, tuple[str, ...]]:
    """A clean-by-construction story summary over curated pillar titles."""
    filled = _filled(request.slots)
    open_ = _open(request.slots)
    name = request.display_name
    if not filled:
        summary = (
            f"Your {name} package is just getting started — none of its pillars "
            f"are backed by confirmed evidence yet, and your plan is aimed at the "
            f"first ones."
        )
    elif not open_:
        summary = (
            f"Your {name} package is complete: every pillar is backed by confirmed "
            f"evidence."
        )
    else:
        summary = (
            f"Your {name} package is taking shape — some pillars are already backed "
            f"by your evidence, and your plan is building toward the rest."
        )
    detail = [f"{title} is backed by your confirmed evidence." for title in filled]
    detail += [
        f"{title} is still open — your plan is building toward it." for title in open_
    ]
    return summary, tuple(detail)


class DeterministicUserFacingExplanation:
    """Composes user-facing copy from deterministic outcomes (offline twin)."""

    def run(
        self, *, run_id: str, validation_result: ValidationResult
    ) -> UserExplanation:
        del run_id
        if validation_result.valid:
            return UserExplanation(
                summary="Plan looks good.",
                detail=[],
            )
        details = [user_facing(v.type) for v in validation_result.violations]
        unique_details = list(dict.fromkeys(details))  # de-dupe, preserve order
        summary = "Re-running with fixes."
        return UserExplanation(summary=summary, detail=unique_details)

    def run_fit_notes(
        self, *, run_id: str, requests: tuple[FitNoteRequest, ...]
    ) -> PathwayFitNotes:
        """One fit note per requested card (NP-F), templated from coverage."""
        del run_id
        return PathwayFitNotes(
            notes=tuple(
                PathwayFitNote(
                    pathway_id=r.pathway_id, note=_deterministic_fit_note(r)
                )
                for r in requests
            )
        )

    def run_story_summary(
        self, *, run_id: str, request: StorySummaryRequest
    ) -> StorySummary:
        """The "where your package stands" paragraph (NP-F), from slot states."""
        del run_id
        summary, detail = _deterministic_story_summary(request)
        return StorySummary(summary=summary, detail=detail)
