"""Tie ``prompt_version`` to the prompt bytes (axiom 22 measurement hygiene).

``prompt_version`` is a hand-maintained constant with no structural link to the
prompt text it labels. An edit without a version bump would silently mislabel
every call-log row and eval comparison. Two pin layers enforce the lockstep:

1. **System-prompt pins** — a SHA-256 of each ``_*_SYSTEM`` constant next to
   its version string.
2. **Full-rendered-prompt pins** — a SHA-256 over EVERY outbound content block
   (system + assembled user prompt + repair suffix) produced by running each
   node against a fake transport with fixed canonical inputs that exercise
   every optional prompt section (constraints/goal/exclusions/hints/anchor/
   repair blocks, résumé block, continuity block, …). This covers the
   user-prompt *assembly* bytes the system-prompt hash cannot see.

An intentional change to EITHER layer's bytes requires bumping the node's
``prompt_version`` (new date suffix) AND replacing the pinned hash **in the
same commit**.

To regenerate after an intentional prompt change: run this test; the failing
assertion message prints the new hash. (For the system-prompt layer the
one-liner still works too:

    uv run python -c "import hashlib; \
from agentic_calendar.llm_nodes import anthropic_adapter as aa; \
print(hashlib.sha256(aa._PLANNER_SYSTEM.encode()).hexdigest())"
)
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

import pytest

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import Task
from agentic_calendar.contracts.validation_result import (
    ArtifactType,
    NextAction,
    ValidationResult,
    Violation,
)
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.llm_nodes import anthropic_adapter as adapter
from agentic_calendar.llm_nodes.anthropic_adapter import (
    AnthropicPlanner,
    AnthropicReflectionSummary,
    AnthropicResumeIntake,
    AnthropicStrategist,
    AnthropicUserFacingExplanation,
)
from agentic_calendar.llm_nodes.call_log import InMemoryLlmCallLogStore
from agentic_calendar.llm_nodes.user_facing_explanation import (
    FitNoteRequest,
    FitNoteSlot,
    StorySummaryRequest,
)
from tests._fixture_loader import iter_valid
from tests.llm_nodes.test_anthropic_adapter import (
    _INVALID_PLAN,
    _NOW,
    _SYLLABUS,
    _TWO_MODULE_SYLLABUS,
    _VALID_PLAN,
    FakeTransport,
    _ok,
    _profile,
    _profile_with_plan_direction,
)
from tests.llm_nodes.test_anthropic_resume_intake import (
    _ALLOWED_THEMES,
    _UNGROUNDED_EXTRACTION,
    _VALID_EXTRACTION,
    _intake,
)

#: (prompt constant name, config, pinned prompt_version, pinned SHA-256).
_PINNED: list[tuple[str, object, str, str]] = [
    (
        "_STRATEGIST_SYSTEM",
        adapter.STRATEGIST_CONFIG,
        # v5 (PD-B): plan-direction translate rule + hedge extension changed
        # the system-prompt bytes. v6 (NP-D): system-prompt rule 7 (link up to
        # max_slot_modules modules to unfilled_slots via evidence_slot_id) +
        # the seven-rule self-check line changed the bytes again.
        "strategist-v6-2026-07-20",
        "b3fbf12f2a90065f998a086171bc44bfb288c924d21c45d01bbe9bd73581e174",
    ),
    (
        "_PLANNER_SYSTEM",
        adapter.PLANNER_CONFIG,
        # Bumped v5->v6 (KT-A) for the SyllabusModule knowledge_node_ids field
        # (v5 was NP-A's evidence_slot_id). System-prompt template text is
        # unchanged in both cases, so the system-prompt hash is the same.
        "planner-v6-2026-07-20",
        "71cb5b40315ec2f2ef0411c03928a27518f1a6df05903f4c5c4a46e9a0626513",
    ),
    (
        "_REFLECTION_SYSTEM",
        adapter.REFLECTION_CONFIG,
        "reflection-v3-2026-07-05",
        "7683ed20e07104b9eb6fb0e60c1320f5ef3c4a4248a6d6d1fcfe3f1b37e3e684",
    ),
    (
        "_EXPLANATION_SYSTEM",
        adapter.EXPLANATION_CONFIG,
        "explanation-v3-2026-07-05",
        "cbd9e9a559f6e67ed77fa2ad28e58a7633340c00226b9f8ce0bbd8be7dde3a59",
    ),
    (
        "_RESUME_INTAKE_SYSTEM",
        adapter.RESUME_INTAKE_CONFIG,
        # v2 (NP-C): rule 7 (evidence `kind` + closed-vocabulary `theme_tags`)
        # and the exemplar's two new fields changed the system-prompt bytes.
        "resume-intake-v2-2026-07-20",
        "b525603a35121c1c98dff419c3b34f90b0967abb30614804a4c963f849690fc5",
    ),
    (
        # NP-F: the pathway fit-note target, inside the explanation node.
        "_FIT_NOTE_SYSTEM",
        adapter.FIT_NOTE_CONFIG,
        "story-fit-note-v1-2026-07-20",
        "aa92078400896a86b5e30b68f684ba68205dfb0d7ce7ff5916ae15e9857d7207",
    ),
    (
        # NP-F: the story-summary target, inside the explanation node.
        "_STORY_SUMMARY_SYSTEM",
        adapter.STORY_SUMMARY_CONFIG,
        "story-summary-v1-2026-07-20",
        "f2098d6fb5225f9a4492cc831ac6f9014b4b39bb7a84ea219f56dd70427fd21c",
    ),
]


@pytest.mark.parametrize(
    ("constant_name", "config", "pinned_version", "pinned_sha256"),
    _PINNED,
    ids=[name.strip("_").lower() for name, _, _, _ in _PINNED],
)
def test_prompt_version_matches_prompt_bytes(
    constant_name: str,
    config: adapter.AdapterConfig,
    pinned_version: str,
    pinned_sha256: str,
) -> None:
    prompt_text = getattr(adapter, constant_name)
    actual_sha256 = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    assert config.prompt_version == pinned_version, (
        f"{constant_name}: prompt_version changed without updating the pinned "
        f"pair in this test — keep version and hash in lockstep"
    )
    assert actual_sha256 == pinned_sha256, (
        f"{constant_name}: prompt bytes changed. Bump the node's prompt_version "
        f"(new date suffix) and update the pinned hash here in the same commit; "
        f"new hash: {actual_sha256}"
    )


# --------------------------------------------------------------------------- #
# Full-rendered-prompt pins: golden hashes over EVERY outbound content block
# each node emits for fixed canonical inputs. The system-prompt pins above
# cannot see the user-prompt assembly bytes (goal block, behavioral hints,
# prior-plan anchor, replan mode, continuity block, repair-violation
# formatting, …) — these pins do. Inputs are frozen: fixture files, literal
# dicts, and FrozenClock; nothing reads now().
# --------------------------------------------------------------------------- #


def _node_kwargs() -> dict[str, object]:
    return {
        "store": InMemoryLlmCallLogStore(),
        "clock": FrozenClock(_NOW),
        "id_generator": DeterministicIdGenerator(),
    }


def _render_outbound(transport: FakeTransport) -> str:
    """Deterministic concatenation of every outbound content block.

    One frame per transport call: the system prompt, the assembled base user
    prompt, and the repair suffix (empty on the first call) — the exact byte
    surfaces the model sees across the base call and the repair round.
    """
    frames = [
        f"=== call {i} ===\n"
        f"[system]\n{req['system']}\n"
        f"[user]\n{req['user_prompt']}\n"
        f"[repair]\n{req['repair_suffix'] or ''}"
        for i, req in enumerate(transport.requests)
    ]
    return "\n".join(frames)


def _failed_validation_result() -> ValidationResult:
    """Fixed failed ValidationResult: drives the planner's inbound repair
    block and the explanation node's input."""
    return ValidationResult(
        run_id="run_pin",
        artifact_type=ArtifactType.TASK_PLAN,
        valid=False,
        repairable=True,
        reason_code=ReasonCode.USER_FIT_VIOLATED,
        violations=[
            Violation(
                type=ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION,
                task_id="dp_001",
                details={"duration_min": 150, "max_session_length_min": 120},
            )
        ],
        repair_attempt=1,
        next_action=NextAction.PLANNER_REPAIR_RETRY,
    )


def _strategist_full() -> tuple[adapter.AdapterConfig, FakeTransport]:
    """Optional sections: résumé context block + plan-direction context block;
    engine repair suffix (the first response violates max_modules, so round 2
    carries the rejection)."""
    transport = FakeTransport([_ok(_TWO_MODULE_SYLLABUS), _ok(_SYLLABUS)])
    node = AnthropicStrategist(transport=transport, **_node_kwargs())  # type: ignore[arg-type]
    claim_fixture = next(
        f for f in iter_valid("source_claim") if f.name == "company_blog_high"
    )
    node.run(
        run_id="run_pin",
        user_profile=_profile_with_plan_direction(
            "PINNED PLAN DIRECTION: Blind 75 first, then system design.",
            resume_text="PINNED RESUME: 4 yrs Go, distributed systems.",
        ),
        source_claims=[SourceClaim.model_validate(claim_fixture.payload)],
        strategy_constraints=StrategyConstraints(max_modules=1),
        plan_version="v_pin",
    )
    # Guard: the pin must actually cover what it claims (builder-rot check).
    prompt = transport.requests[0]["user_prompt"]
    assert "Candidate résumé" in prompt
    assert "User-provided plan direction" in prompt
    assert "claim_blog_1" in prompt
    assert transport.requests[1]["repair_suffix"] is not None
    return adapter.STRATEGIST_CONFIG, transport


def _planner_full() -> tuple[adapter.AdapterConfig, FakeTransport]:
    """Optional sections: profile constraints + goal block, excluded tasks,
    behavioral hints, prior-plan anchor + replan mode, inbound repair
    ValidationResult; engine repair suffix (first response has a duplicate
    task_id, so round 2 carries the typed schema rejection)."""
    transport = FakeTransport([_ok(_INVALID_PLAN), _ok(_VALID_PLAN)])
    node = AnthropicPlanner(transport=transport, **_node_kwargs())  # type: ignore[arg-type]
    node.run(
        run_id="run_pin",
        syllabus=SyllabusUnits.model_validate(_SYLLABUS),
        plan_version="v_pin",
        user_profile=_profile(),
        repair=_failed_validation_result(),
        excluded_tasks=["task_done_00"],
        behavioral_hints=["2026-06-28: Practice tasks ran past their estimates."],
        prior_plan_tasks=[Task.model_validate(_VALID_PLAN["tasks"][0])],
        replan_mode=RecoveryAction.SCOPE_REDUCTION,
    )
    # Guard: the pin must actually cover what it claims (builder-rot check).
    prompt = transport.requests[0]["user_prompt"]
    for marker in (
        "Planning constraints",
        "User goal context",
        "Do NOT regenerate these tasks",
        "Prior approved plan",
        "Recovery mode: scope_reduction.",
        "Recent reflections",
        "failed deterministic validation",
    ):
        assert marker in prompt, f"planner pin no longer renders {marker!r}"
    assert transport.requests[1]["repair_suffix"] is not None
    return adapter.PLANNER_CONFIG, transport


def _reflection_full() -> tuple[adapter.AdapterConfig, FakeTransport]:
    """Optional sections: completion-rate line + prior-reflections continuity
    block; engine repair suffix (the first response trips the psych-label
    scan, so round 2 carries the rubric rejection)."""
    transport = FakeTransport(
        [
            _ok({"summary": "You have been lazy this week.", "detail": []}),
            _ok(
                {
                    "summary": "Practice tasks are taking longer than planned.",
                    "detail": [],
                }
            ),
        ]
    )
    node = AnthropicReflectionSummary(transport=transport, **_node_kwargs())  # type: ignore[arg-type]
    drift_fixture = next(
        f for f in iter_valid("drift_event") if f.name == "duration_underestimate"
    )
    node.run(
        run_id="run_pin",
        drift_events=[DriftEvent.model_validate(drift_fixture.payload)],
        completion_rate=0.5,
        plan_version="v_pin",
        prior_reflections=["2026-06-28: Practice tasks ran past their estimates."],
    )
    # Guard: the pin must actually cover what it claims (builder-rot check).
    prompt = transport.requests[0]["user_prompt"]
    assert "Recent completion rate: 0.5" in prompt
    assert "Earlier reflections" in prompt
    assert transport.requests[1]["repair_suffix"] is not None
    return adapter.REFLECTION_CONFIG, transport


def _explanation_full() -> tuple[adapter.AdapterConfig, FakeTransport]:
    """The explanation prompt has no optional sections (one fixed template
    over the canonical ValidationResult JSON); the pin still covers the
    template bytes and the engine repair suffix (psych-label rejection)."""
    transport = FakeTransport(
        [
            _ok({"summary": "You were lazy, so the plan failed.", "detail": []}),
            _ok(
                {
                    "summary": "This plan needed more time than your weekly limit.",
                    "detail": ["Lower the weekly load or trim the syllabus."],
                }
            ),
        ]
    )
    node = AnthropicUserFacingExplanation(transport=transport, **_node_kwargs())  # type: ignore[arg-type]
    node.run(
        run_id="run_pin",
        validation_result=_failed_validation_result(),
        plan_version="v_pin",
    )
    # Guard: the pin must actually cover what it claims (builder-rot check).
    assert transport.requests[0]["user_prompt"].startswith("Validation result:")
    assert transport.requests[1]["repair_suffix"] is not None
    return adapter.EXPLANATION_CONFIG, transport


def _resume_intake_full() -> tuple[adapter.AdapterConfig, FakeTransport]:
    """Optional sections: allowed weak-spot vocabulary block + allowed-themes
    block (NP-C) + labeled résumé block; engine repair suffix (the first
    response carries an ungrounded skill, so round 2 carries the typed
    groundedness rejection)."""
    transport = FakeTransport([_ok(_UNGROUNDED_EXTRACTION), _ok(_VALID_EXTRACTION)])
    node = AnthropicResumeIntake(transport=transport, **_node_kwargs())  # type: ignore[arg-type]
    node.run(run_id="intake-pin", intake=_intake(allowed_themes=_ALLOWED_THEMES))
    # Guard: the pin must actually cover what it claims (builder-rot check).
    prompt = transport.requests[0]["user_prompt"]
    assert "Allowed weak-spot vocabulary (choose only from this list):" in prompt
    assert "Allowed evidence themes for theme_tags" in prompt
    assert "Candidate résumé" in prompt
    assert '"resume_text"' not in prompt
    assert transport.requests[1]["repair_suffix"] is not None
    return adapter.RESUME_INTAKE_CONFIG, transport


def _fit_notes_full() -> tuple[adapter.AdapterConfig, FakeTransport]:
    """Two pathway cards (NP-F); the first response trips the numeric-score
    post-check, so round 2 carries the rejection. Covers the batched
    ``Pathway cards:`` assembly and the story-prose repair formatting."""
    transport = FakeTransport(
        [
            _ok(
                {
                    "notes": [
                        {
                            "pathway_id": "pw-a",
                            "note": "You cover 3 of 4 pillars here — the best match.",
                        },
                        {"pathway_id": "pw-b", "note": "A weaker option overall."},
                    ]
                }
            ),
            _ok(
                {
                    "notes": [
                        {
                            "pathway_id": "pw-a",
                            "note": (
                                "Your shipped work already anchors the depth pillar; "
                                "the public artifact pillar is still open, so your "
                                "plan can build toward it."
                            ),
                        },
                        {
                            "pathway_id": "pw-b",
                            "note": (
                                "None of these pillars are backed yet — a clean start "
                                "your plan can build from."
                            ),
                        },
                    ]
                }
            ),
        ]
    )
    node = AnthropicUserFacingExplanation(transport=transport, **_node_kwargs())  # type: ignore[arg-type]
    node.run_fit_notes(
        run_id="story-pin",
        requests=(
            FitNoteRequest(
                pathway_id="pw-a",
                display_name="Backend Engineer",
                spine="Depth-first services and production ops.",
                audience_note="Backend and infrastructure teams.",
                slots=(
                    FitNoteSlot(
                        title="Depth services",
                        state="filled",
                        matched_titles=("Payments API",),
                    ),
                    FitNoteSlot(title="Public artifact", state="empty"),
                ),
            ),
            FitNoteRequest(
                pathway_id="pw-b",
                display_name="Full-Stack Engineer",
                spine="Frontend surface through backend depth.",
                audience_note="Product teams.",
                slots=(FitNoteSlot(title="Frontend surface", state="empty"),),
            ),
        ),
    )
    # Guard: the pin must actually cover what it claims (builder-rot check).
    prompt = transport.requests[0]["user_prompt"]
    assert prompt.startswith("Pathway cards:")
    assert '"pw-a"' in prompt and '"pw-b"' in prompt
    assert transport.requests[1]["repair_suffix"] is not None
    return adapter.FIT_NOTE_CONFIG, transport


def _story_summary_full() -> tuple[adapter.AdapterConfig, FakeTransport]:
    """The story summary (NP-F); the first response trips both the score and
    psych-label post-checks, so round 2 carries the rejection."""
    transport = FakeTransport(
        [
            _ok(
                {
                    "summary": "You're 60% there but undisciplined about the rest.",
                    "detail": [],
                }
            ),
            _ok(
                {
                    "summary": (
                        "Your package is taking shape — depth is backed, and your "
                        "plan is building toward the public artifact."
                    ),
                    "detail": [
                        "Depth is backed by your confirmed evidence.",
                        "The public artifact is still open — your plan is building "
                        "toward it.",
                    ],
                }
            ),
        ]
    )
    node = AnthropicUserFacingExplanation(transport=transport, **_node_kwargs())  # type: ignore[arg-type]
    node.run_story_summary(
        run_id="story-pin",
        request=StorySummaryRequest(
            pathway_id="pw-a",
            display_name="Backend Engineer",
            spine="Depth-first services and production ops.",
            slots=(
                FitNoteSlot(
                    title="Depth services",
                    state="filled",
                    matched_titles=("Payments API",),
                ),
                FitNoteSlot(title="Public artifact", state="empty"),
            ),
        ),
    )
    # Guard: the pin must actually cover what it claims (builder-rot check).
    assert transport.requests[0]["user_prompt"].startswith("Selected pathway:")
    assert transport.requests[1]["repair_suffix"] is not None
    return adapter.STORY_SUMMARY_CONFIG, transport


#: (node id, builder, pinned prompt_version, pinned full-prompt SHA-256).
_FULL_PROMPT_PINS: list[
    tuple[str, Callable[[], tuple[adapter.AdapterConfig, FakeTransport]], str, str]
] = [
    (
        "strategist",
        _strategist_full,
        # 2026-07-20 (NP-A): StrategyConstraints story-layer default fields now
        # serialize into the input bundle — rendered bytes changed, rehashed.
        # v6 (NP-D): system-prompt rule 7 changed the system frame, rehashed.
        "strategist-v6-2026-07-20",
        "498d544a77d4effb8a3e7604fb5ed0a4d37ab0431d845b7a46f89ffe2575e3c6",
    ),
    (
        "planner",
        _planner_full,
        # v6 (KT-A): SyllabusModule knowledge_node_ids serializes into the
        # validated-syllabus block (default []) — rendered bytes changed,
        # rehashed. (v5 was NP-A's evidence_slot_id.)
        "planner-v6-2026-07-20",
        "bf92ef3556fa4d11350a3cb02fc15d4f8ac9ff67f7fdbb59002ffeb938e8a8f8",
    ),
    (
        "reflection_summary",
        _reflection_full,
        "reflection-v3-2026-07-05",
        "940a3709030ca73b956640d60d8607bdce033e62ce8ee06464848418f292089c",
    ),
    (
        "user_facing_explanation",
        _explanation_full,
        "explanation-v3-2026-07-05",
        "cf9f95ac76221c187a9c42bdc5648f90f9a7771d9b41f3774e89582f79db2fe2",
    ),
    (
        "resume_intake",
        _resume_intake_full,
        # v2 (NP-C): system-prompt rule 7, plus the rendered bundle now carries
        # allowed_themes and a labeled allowed-evidence-themes block — bytes
        # changed, rehashed.
        "resume-intake-v2-2026-07-20",
        "19134eacda83dd8b88677c8885e09ba11fc58520c97fcbfa0c68311ac757d1ed",
    ),
    (
        "story_fit_notes",
        _fit_notes_full,
        "story-fit-note-v1-2026-07-20",
        "daccaea50be6603d65a3ea998e0eb2e016089a4ad30816e74b004336c49abe0d",
    ),
    (
        "story_summary",
        _story_summary_full,
        "story-summary-v1-2026-07-20",
        "afe747bea81e2a17b9b2ed55712fb0987e1335f6c9adf434133210ec7b2ef96a",
    ),
]


@pytest.mark.parametrize(
    ("node_id", "build", "pinned_version", "pinned_sha256"),
    _FULL_PROMPT_PINS,
    ids=[pin[0] for pin in _FULL_PROMPT_PINS],
)
def test_prompt_version_matches_full_rendered_prompt_bytes(
    node_id: str,
    build: Callable[[], tuple[adapter.AdapterConfig, FakeTransport]],
    pinned_version: str,
    pinned_sha256: str,
) -> None:
    config, transport = build()
    rendered = _render_outbound(transport)
    actual_sha256 = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    assert config.prompt_version == pinned_version, (
        f"{node_id}: prompt_version changed without updating the pinned "
        f"full-prompt pair in this test — keep version and hash in lockstep"
    )
    assert actual_sha256 == pinned_sha256, (
        f"{node_id}: full rendered prompt bytes changed (system prompt, "
        f"user-prompt assembly, or repair formatting). Bump the node's "
        f"prompt_version (new date suffix) and update the pinned hash here in "
        f"the same commit; new hash: {actual_sha256}"
    )
