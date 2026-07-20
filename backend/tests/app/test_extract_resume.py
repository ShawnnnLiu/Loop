"""Tests for :meth:`CycleService.extract_resume` (résumé intake RI-C).

The extract path is strictly persistence-free: it validates the request into
``ResumeIntakeInput`` (forcing the acting user and the service-resolved
weak-spot vocabulary), mints an ``intake-`` run_id, runs the node, and
normalizes skill surfaces onto the pinned taxonomy. Nothing here may touch a
store — profile persistence remains exclusively ``onboard``. Reuses the
``make_service`` harness so the backing service is the identical
fixture-backed, frozen-clock build the cycle tests drive.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_calendar.app.environment import ResumeIntakeNode
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.resume_extraction import ResumeExtraction
from agentic_calendar.contracts.resume_intake_input import ResumeIntakeInput
from agentic_calendar.llm_nodes import (
    InMemoryLlmCallLogStore,
    LLMGenerationError,
    LLMNodeError,
)
from agentic_calendar.llm_nodes.anthropic_adapter import AnthropicResumeIntake
from agentic_calendar.llm_nodes.resume_intake import FixtureResumeIntake
from agentic_calendar.skill_taxonomy import load_registry, resolve_track
from tests.app.test_cycle import (
    TAXONOMY_ALIASES,
    USER_ID,
    _canonical_profile,
    make_service,
)
from tests.llm_nodes.test_anthropic_adapter import _NOW, FakeTransport, _ok

_RESUME = (
    "Senior Backend Engineer at Acme Corp (2019-2024)\n"
    "Led the billing platform team; Python and Go services on Kubernetes.\n"
    "Certified Flurbo.js expert and conference speaker."
)


def _payload(**overrides: object) -> dict[str, object]:
    return {
        "resume_text": _RESUME,
        "draft_context": {"target_role": "Backend SWE"},
        **overrides,
    }


class RecordingResumeIntake:
    """Delegating node that records every validated intake bundle it receives."""

    def __init__(self, inner: ResumeIntakeNode) -> None:
        self._inner = inner
        self.run_ids: list[str] = []
        self.intakes: list[ResumeIntakeInput] = []

    def run(self, *, run_id: str, intake: ResumeIntakeInput) -> ResumeExtraction:
        self.run_ids.append(run_id)
        self.intakes.append(intake)
        return self._inner.run(run_id=run_id, intake=intake)


class StubResumeIntake:
    """Constant node returning one canned extraction (normalizer tests)."""

    def __init__(self, extraction: ResumeExtraction) -> None:
        self._extraction = extraction

    def run(self, *, run_id: str, intake: ResumeIntakeInput) -> ResumeExtraction:
        del run_id, intake
        return self._extraction


class FailingResumeIntake:
    """Node that always raises, standing in for an exhausted repair loop."""

    def __init__(self, exc: LLMNodeError) -> None:
        self._exc = exc

    def run(self, *, run_id: str, intake: ResumeIntakeInput) -> ResumeExtraction:
        del run_id, intake
        raise self._exc


# --------------------------------------------------------------------------- #
# happy path
# --------------------------------------------------------------------------- #


def test_extract_returns_grounded_proposal_with_canonical_skills() -> None:
    service, _env, _clock = make_service()
    result = service.extract_resume(USER_ID, _payload())

    assert result.status == "ok"
    assert result.user_id == USER_ID
    assert result.taxonomy_version == "skill-taxonomy-v3"
    assert result.proposal is not None
    lowered = _RESUME.lower()
    for surface in result.proposal.skills:
        assert surface.lower() in lowered

    canonical_ids = {skill.skill_id for skill in result.skills_canonical}
    assert {"skill.python", "skill.go", "skill.kubernetes"} <= canonical_ids
    # The fixture node emits only taxonomy-alias hits, so nothing is unmatched.
    assert result.skills_unmatched == []


def test_extract_run_id_carries_intake_prefix() -> None:
    service, _env, _clock = make_service()
    result = service.extract_resume(USER_ID, _payload())
    assert result.run_id.startswith("intake-")


def test_extract_is_deterministic_through_the_service_layer() -> None:
    service, _env, _clock = make_service()
    first = service.extract_resume(USER_ID, _payload())
    second = service.extract_resume(USER_ID, _payload())
    assert first.proposal is not None and second.proposal is not None
    assert first.proposal.model_dump(mode="json") == second.proposal.model_dump(mode="json")
    assert first.skills_canonical == second.skills_canonical
    assert first.taxonomy_version == second.taxonomy_version


def test_extract_weak_spots_stay_inside_the_resolved_track_slice() -> None:
    service, _env, _clock = make_service()
    result = service.extract_resume(USER_ID, _payload())
    assert result.proposal is not None
    track = resolve_track("Backend SWE")
    assert track is not None
    allowed = {e.display_name for e in load_registry().entries_for_track(track)}
    assert result.proposal.inferred_weak_spots
    assert set(result.proposal.inferred_weak_spots) <= allowed


def test_extract_works_before_any_onboarding() -> None:
    """Extraction precedes onboarding in the wizard — no onboarding record needed."""
    service, env, _clock = make_service(onboard=False, seed_claims=False)
    assert env.state.get_onboarding(USER_ID) is None
    result = service.extract_resume(USER_ID, _payload())
    assert result.status == "ok"
    assert env.state.get_onboarding(USER_ID) is None


# --------------------------------------------------------------------------- #
# trust boundary and vocabulary resolution
# --------------------------------------------------------------------------- #


def test_body_user_id_and_allowed_weak_spots_are_overridden() -> None:
    recording = RecordingResumeIntake(
        FixtureResumeIntake(taxonomy_aliases=TAXONOMY_ALIASES)
    )
    service, _env, _clock = make_service(resume_intake=recording)
    result = service.extract_resume(
        USER_ID,
        _payload(user_id="intruder_999", allowed_weak_spots=["Only this"]),
    )
    assert result.user_id == USER_ID
    (intake,) = recording.intakes
    assert intake.user_id == USER_ID
    # The vocabulary comes from the service-resolved track slice, never the body.
    track = resolve_track("Backend SWE")
    assert track is not None
    expected = [e.display_name for e in load_registry().entries_for_track(track)]
    assert intake.allowed_weak_spots == expected


def test_unresolvable_role_falls_back_to_union_vocabulary() -> None:
    recording = RecordingResumeIntake(
        FixtureResumeIntake(taxonomy_aliases=TAXONOMY_ALIASES)
    )
    service, _env, _clock = make_service(resume_intake=recording)
    service.extract_resume(USER_ID, _payload(draft_context={"target_role": "Chef"}))
    (intake,) = recording.intakes
    assert intake.allowed_weak_spots == [
        e.display_name for e in load_registry().entries
    ]


def test_fabricated_skill_lands_in_unmatched_never_canonical() -> None:
    """The Flurbo.js case: a grounded surface with no taxonomy entry is
    returned visibly flagged, never silently promoted (06-skill-taxonomy)."""
    stub = StubResumeIntake(
        ResumeExtraction(skills=["Python", "Flurbo.js"])
    )
    service, _env, _clock = make_service(resume_intake=stub)
    result = service.extract_resume(USER_ID, _payload())

    assert result.skills_unmatched == ["Flurbo.js"]
    assert [s.skill_id for s in result.skills_canonical] == ["skill.python"]


def test_two_surfaces_for_one_entry_keep_the_first() -> None:
    stub = StubResumeIntake(ResumeExtraction(skills=["golang", "Go"]))
    service, _env, _clock = make_service(resume_intake=stub)
    result = service.extract_resume(USER_ID, _payload())
    assert [s.surface for s in result.skills_canonical] == ["golang"]
    assert result.skills_unmatched == []


def test_invalid_payload_raises_validation_error_before_any_node_call() -> None:
    recording = RecordingResumeIntake(StubResumeIntake(ResumeExtraction()))
    service, _env, _clock = make_service(resume_intake=recording)
    with pytest.raises(ValidationError):
        service.extract_resume(USER_ID, {"resume_text": "too short"})
    assert recording.intakes == []


# --------------------------------------------------------------------------- #
# failure mapping (typed reason_code, no state mutation)
# --------------------------------------------------------------------------- #


def test_llm_failure_returns_typed_reason_code_without_run_state() -> None:
    failing = FailingResumeIntake(
        LLMGenerationError("truncated", reason_code=ReasonCode.LLM_TRUNCATED)
    )
    service, env, _clock = make_service(resume_intake=failing)
    before = env.state.get_onboarding(USER_ID)

    result = service.extract_resume(USER_ID, _payload())

    assert result.status == "failed"
    assert result.reason_code is ReasonCode.LLM_TRUNCATED
    assert result.detail == "truncated"
    assert result.proposal is None
    assert result.run_id.startswith("intake-")
    # No run was created or failed; the onboarding record is untouched.
    assert env.state.latest_run_for_user(USER_ID) is None
    assert env.state.get_onboarding(USER_ID) == before


def test_untyped_node_error_maps_to_llm_call_failed() -> None:
    failing = FailingResumeIntake(LLMNodeError("node exploded"))
    service, _env, _clock = make_service(resume_intake=failing)
    result = service.extract_resume(USER_ID, _payload())
    assert result.status == "failed"
    assert result.reason_code is ReasonCode.LLM_CALL_FAILED


# --------------------------------------------------------------------------- #
# observability (RI-E): the service path writes hashed Haiku call-log rows
# --------------------------------------------------------------------------- #


def test_extract_via_service_logs_haiku_rows_with_hashes_only() -> None:
    """A full extract through the service (real adapter, fake transport)
    emits one call-log row carrying the resume_intake node name, the
    service-minted ``intake-`` run_id, the Haiku config's pricing/version —
    and hashes only: the résumé (PII) never appears in the record."""
    grounded = {
        "experience": [
            {
                "title": "Senior Backend Engineer",
                "organization": "Acme Corp",
                "summary": None,
            }
        ],
        "skills": ["Python", "Go", "Kubernetes"],
        "known_strengths": ["backend services"],
        "inferred_weak_spots": ["System design"],
        "target_company_categories": ["infra startups"],
    }
    store = InMemoryLlmCallLogStore()
    node = AnthropicResumeIntake(
        transport=FakeTransport([_ok(grounded)]),
        store=store,
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
        sleeper=lambda _s: None,
    )
    service, _env, _clock = make_service(resume_intake=node)

    result = service.extract_resume(USER_ID, _payload())

    assert result.status == "ok"
    (row,) = store.list_all()
    assert row.node.value == "resume_intake"
    assert row.run_id == result.run_id
    assert row.run_id.startswith("intake-")
    assert row.model_name == "claude-haiku-4-5"
    assert row.prompt_version == "resume-intake-v1-2026-07-06"
    assert row.cost_estimate_usd == (100 * 1.00 + 50 * 5.00) / 1_000_000
    assert row.prompt_hash is not None and row.response_hash is not None
    serialized = row.model_dump_json()
    assert "Senior Backend Engineer" not in serialized
    assert "Acme Corp" not in serialized


# --------------------------------------------------------------------------- #
# persistence-free assertion
# --------------------------------------------------------------------------- #


def test_extract_writes_nothing_to_the_app_document_store(tmp_path: Path) -> None:
    service, env, _clock = make_service(db_path=tmp_path / "app.db")
    assert env.db is not None

    def row_count() -> int:
        with env.db.read() as cursor:
            cursor.execute("SELECT COUNT(*) FROM app_documents")
            return int(cursor.fetchone()[0])

    before = row_count()
    result = service.extract_resume(USER_ID, _payload())
    assert result.status == "ok"
    assert row_count() == before


# --------------------------------------------------------------------------- #
# onboard path (unchanged, verified — RI-C §4)
# --------------------------------------------------------------------------- #


def test_reonboard_round_trips_experience_and_skills() -> None:
    """The new profile fields ride the existing onboard payload with zero
    route/service changes; a re-onboard (profile edit) must not shed them."""
    service, _env, _clock = make_service()
    profile = _canonical_profile().model_dump(mode="json")
    profile["experience"] = [
        {
            "title": "Senior Backend Engineer",
            "organization": "Acme Corp",
            "summary": "Led the billing platform team.",
        }
    ]
    profile["skills"] = ["Python", "Go"]

    service.onboard({"user_profile": profile, "timezone": "UTC"})
    # Re-onboard with an edited copy (what the wizard's edit-later flow sends).
    edited = {**profile, "weekly_hours": 6}
    service.onboard({"user_profile": edited, "timezone": "UTC"})

    me = service.me(USER_ID)
    assert me.profile is not None
    assert [item.organization for item in me.profile.experience] == ["Acme Corp"]
    assert me.profile.skills == ["Python", "Go"]
