"""Service-level tests for the story-layer LLM prose surfaces (NP-F).

The HTTP + node tests cover the onboarded path and the prose post-checks; this
pins the two service-only behaviours: the draft (persistence-free, no-onboarding)
posture the wizard uses, and that the prose call never mutates the deterministic
coverage it decorates.
"""

from __future__ import annotations

from agentic_calendar.contracts.common_types import EvidenceKind
from agentic_calendar.llm_nodes.anthropic_adapter import _scan_story_prose
from tests.app.test_cycle import USER_ID, make_service
from tests.narrative._helpers import item, make_profile


def test_fit_notes_over_a_draft_profile_need_no_onboarding() -> None:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    profile = make_profile(
        [item("Payments service", EvidenceKind.WORK, ["backend-systems"])]
    )
    result = service.pathway_fit_notes(
        USER_ID, {"user_profile": profile.model_dump(mode="json"), "track": "swe"}
    )

    assert result.status == "ok"
    assert result.registry_version == "pathway-registry-v1"
    assert result.notes  # at least one note for the top cards
    assert len(result.notes) <= 4
    for note in result.notes.values():
        _scan_story_prose(note)  # clean under the deterministic post-checks


def test_fit_notes_do_not_mutate_the_deterministic_ranking() -> None:
    service, _env, _clock = make_service(onboard=True, seed_claims=False)
    before = service.pathways_view(USER_ID, track="swe")
    service.pathway_fit_notes(USER_ID, {"track": "swe"})
    after = service.pathways_view(USER_ID, track="swe")

    assert after == before  # display-only prose changes nothing about the cards
