"""Story-layer prose targets (NP-F): the fit-note and story-summary surfaces.

Fixture-driven contract checks only (03-llm-surfaces §Eval additions): the
deterministic twin's output shapes, the three deterministic post-checks
(prestige denylist + psychological-label denylist + no-numerals-as-scores), and
the Anthropic adapter's repair behaviour under a fake transport. Prompt wording
is never a test oracle.
"""

from __future__ import annotations

import pytest

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.llm_nodes import anthropic_adapter as adapter
from agentic_calendar.llm_nodes.anthropic_adapter import (
    AnthropicUserFacingExplanation,
    LLMGenerationError,
    _scan_story_prose,
)
from agentic_calendar.llm_nodes.base import LLMNodeError
from agentic_calendar.llm_nodes.call_log import InMemoryLlmCallLogStore
from agentic_calendar.llm_nodes.user_facing_explanation import (
    DeterministicUserFacingExplanation,
    FitNoteRequest,
    FitNoteSlot,
    StorySummaryRequest,
)
from tests.llm_nodes.test_anthropic_adapter import _NOW, FakeTransport, _ok


def _slots(*pairs: tuple[str, str]) -> tuple[FitNoteSlot, ...]:
    return tuple(FitNoteSlot(title=t, state=s) for t, s in pairs)


def _fit_request(pathway_id: str, *pairs: tuple[str, str]) -> FitNoteRequest:
    return FitNoteRequest(
        pathway_id=pathway_id,
        display_name="Backend Engineer",
        spine="Depth-first services.",
        audience_note="Backend teams.",
        slots=_slots(*pairs),
    )


# --------------------------------------------------------------------------- #
# Deterministic post-checks
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text",
    [
        "You cover 3 of 5 pillars.",
        "You're 60% of the way there.",
        "A 4/6 fit for this story.",
        "You are 3 out of 6 pillars in.",
    ],
)
def test_numeric_scores_are_rejected(text: str) -> None:
    with pytest.raises(LLMNodeError):
        _scan_story_prose(text)


@pytest.mark.parametrize(
    "text",
    [
        "Your shipped v2 dashboard anchors the depth pillar.",  # version tag, not a score
        "Your 2026 internship carries the breadth pillar.",  # year, not a score
        "Two pillars are already backed by your evidence.",  # spelled-out count
    ],
)
def test_non_score_numerals_pass(text: str) -> None:
    _scan_story_prose(text)  # must not raise


def test_prestige_terms_are_rejected() -> None:
    with pytest.raises(LLMNodeError):
        _scan_story_prose("This is a mediocre, second-rate story for you.")


def test_psychological_labels_are_rejected() -> None:
    with pytest.raises(LLMNodeError):
        _scan_story_prose("You've been lazy about the open pillars.")


# --------------------------------------------------------------------------- #
# Deterministic twin: shapes + self-consistency with the scanner
# --------------------------------------------------------------------------- #


def test_twin_fit_notes_cover_every_request_and_pass_the_scanner() -> None:
    twin = DeterministicUserFacingExplanation()
    requests = (
        _fit_request("all", ("Depth", "filled"), ("Breadth", "filled")),
        _fit_request("none", ("Depth", "empty"), ("Breadth", "empty")),
        _fit_request("mixed", ("Depth", "filled"), ("Breadth", "empty")),
        _fit_request("partial", ("Depth", "partial"), ("Breadth", "filled")),
    )
    out = twin.run_fit_notes(run_id="story-t", requests=requests)

    assert [n.pathway_id for n in out.notes] == ["all", "none", "mixed", "partial"]
    for note in out.notes:
        assert note.note.strip()
        _scan_story_prose(note.note)  # clean-by-construction guarantee


def test_twin_story_summary_shapes_and_passes_the_scanner() -> None:
    twin = DeterministicUserFacingExplanation()
    request = StorySummaryRequest(
        pathway_id="mixed",
        display_name="Backend Engineer",
        spine="Depth-first services.",
        slots=_slots(("Depth", "filled"), ("Public artifact", "empty")),
    )
    out = twin.run_story_summary(run_id="story-t", request=request)

    assert out.summary.strip()
    _scan_story_prose(out.summary)
    # one line per pillar (filled then open)
    assert len(out.detail) == 2
    for line in out.detail:
        _scan_story_prose(line)


# --------------------------------------------------------------------------- #
# Anthropic adapter: repair loop + call-log emission (fake transport)
# --------------------------------------------------------------------------- #


def _node(transport: FakeTransport) -> AnthropicUserFacingExplanation:
    return AnthropicUserFacingExplanation(
        transport=transport,  # type: ignore[arg-type]
        store=InMemoryLlmCallLogStore(),
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
    )


def _requests() -> tuple[FitNoteRequest, ...]:
    return (
        _fit_request("pw-a", ("Depth", "filled"), ("Artifact", "empty")),
        _fit_request("pw-b", ("Depth", "empty")),
    )


def test_adapter_fit_notes_repairs_a_wrong_id_set_then_returns() -> None:
    # First response drops pw-b (id-set mismatch → rejected); second is complete.
    transport = FakeTransport(
        [
            _ok({"notes": [{"pathway_id": "pw-a", "note": "Depth is backed."}]}),
            _ok(
                {
                    "notes": [
                        {"pathway_id": "pw-a", "note": "Depth is backed by your evidence."},
                        {"pathway_id": "pw-b", "note": "A clean start to build from."},
                    ]
                }
            ),
        ]
    )
    store = InMemoryLlmCallLogStore()
    node = AnthropicUserFacingExplanation(
        transport=transport,  # type: ignore[arg-type]
        store=store,
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
    )
    out = node.run_fit_notes(run_id="story-r", requests=_requests())

    assert {n.pathway_id for n in out.notes} == {"pw-a", "pw-b"}
    rows = store.list_for_run("story-r")
    # One fail (id-set) + one pass row, both under the explanation node.
    assert [r.validation_outcome.value for r in rows] == ["fail", "pass"]
    assert rows[0].node.value == "user_facing_explanation"
    assert rows[0].prompt_version == "story-fit-note-v1-2026-07-20"


def test_adapter_fit_notes_exhausts_repairs_on_a_persistent_score() -> None:
    scored = _ok({"notes": [
        {"pathway_id": "pw-a", "note": "You cover 1 of 2 pillars."},
        {"pathway_id": "pw-b", "note": "A clean start."},
    ]})
    transport = FakeTransport([scored, scored, scored])
    node = _node(transport)

    with pytest.raises(LLMGenerationError) as exc:
        node.run_fit_notes(run_id="story-x", requests=_requests())
    assert exc.value.reason_code is ReasonCode.REPAIR_LIMIT_EXCEEDED


def test_adapter_story_summary_scans_detail_lines() -> None:
    # First response's detail line carries a score → rejected; second is clean.
    transport = FakeTransport(
        [
            _ok({"summary": "Taking shape.", "detail": ["You're 2 of 3 done."]}),
            _ok(
                {
                    "summary": "Your package is taking shape.",
                    "detail": ["Depth is backed by your evidence."],
                }
            ),
        ]
    )
    node = _node(transport)
    out = node.run_story_summary(
        run_id="story-s",
        request=StorySummaryRequest(
            pathway_id="pw-a",
            display_name="Backend Engineer",
            spine="Depth-first services.",
            slots=_slots(("Depth", "filled")),
        ),
    )
    assert out.summary == "Your package is taking shape."
    assert out.detail == ("Depth is backed by your evidence.",)


def test_fit_note_config_runs_on_haiku() -> None:
    # 03-llm-surfaces + axiom 09 story-layer table: the story targets are Haiku.
    assert adapter.FIT_NOTE_CONFIG.model_name == "claude-haiku-4-5"
    assert adapter.STORY_SUMMARY_CONFIG.model_name == "claude-haiku-4-5"
