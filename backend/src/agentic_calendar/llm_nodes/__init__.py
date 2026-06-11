"""LLM adapter boundary (see ``docs/axioms/01-system-boundaries.md``).

This package exists to make a key axiom enforceable in code:

**LLMs propose. Deterministic infrastructure disposes.**

Concretely:

- All LLM SDK calls (Phase 5+) must live behind this boundary.
- Deterministic modules (Supervisor, Validation, Scheduler, Planning, etc.)
  must never import an LLM SDK or depend on prompt wording as control-plane
  state.

Only the four named *node roles* are allowed to be LLM-backed:

- ``StrategistNode``: propose ``SyllabusUnits`` from ``UserProfile``.
- ``PlannerNode``: propose ``TaskPlan`` from ``SyllabusUnits``.
- ``ReflectionSummaryNode``: summarise telemetry (Phase 4+).
- ``UserFacingExplanationNode``: explain deterministic outcomes (Phase 1 keeps
  this deterministic on purpose).

Phase 1 ships deterministic fakes so the rest of the system can be built and
tested end-to-end without any external model dependency:

- ``FixtureStrategist`` chooses a canned ``SyllabusUnits`` by ``target_role``.
- ``FixturePlanner`` chooses a canned ``TaskPlan`` by ``syllabus_version``.
- ``DeterministicUserFacingExplanation`` maps typed violations to reviewable
  strings (no model call).
- ``DeterministicReflectionSummary`` renders behavior-only copy from classified
  drift events (Phase 4); it explains drift but never classifies it, and the
  Phase 8 LLM adapter slots in behind the same surface.

Enforcement:

The repository's ``import-linter`` configuration includes an
``llm-sdk-isolation`` contract: any import of common LLM SDKs must occur only
under ``agentic_calendar.llm_nodes`` (and operator tools).
"""

from .base import LLMNode, LLMNodeError
from .call_log import (
    InMemoryLlmCallLogStore,
    LlmCallLog,
    LlmCallLogAlreadyExistsError,
    LlmCallLogStore,
    LlmCallLogStoreError,
    LlmNodeName,
    ValidationOutcome,
)
from .planner import FixturePlanner
from .reflection_summary import DeterministicReflectionSummary, ReflectionSummary
from .strategist import FixtureStrategist
from .user_facing_explanation import (
    DeterministicUserFacingExplanation,
    UserExplanation,
)

__all__ = [
    "DeterministicReflectionSummary",
    "DeterministicUserFacingExplanation",
    "FixturePlanner",
    "FixtureStrategist",
    "InMemoryLlmCallLogStore",
    "LLMNode",
    "LLMNodeError",
    "LlmCallLog",
    "LlmCallLogAlreadyExistsError",
    "LlmCallLogStore",
    "LlmCallLogStoreError",
    "LlmNodeName",
    "ReflectionSummary",
    "UserExplanation",
    "ValidationOutcome",
]
