"""Base protocol shared by every node in :mod:`agentic_calendar.llm_nodes`.

This is intentionally small. The project doesn't want a rich "agent framework"
to become a hidden control plane; instead, the deterministic core owns routing,
validation, retries, and side-effect safety.

The boundary guarantees:

- Node code returns a **structured Pydantic model** (never free-form prose).
- Call sites always supply a deterministic ``run_id`` for correlation.
- Implementations may accept any constructor inputs; all runtime inputs are
  passed into ``run(...)``.

Re-validation policy:

Real SDK adapters (Phase 5+) should treat the model schema as the contract and
re-validate before returning, so malformed SDK responses (or prompt regressions)
never leak past the boundary into deterministic consumers.
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from agentic_calendar.common.errors import AgenticCalendarError

OutputT = TypeVar("OutputT", bound=BaseModel, covariant=True)


class LLMNodeError(AgenticCalendarError):
    """Raised when an LLM node fails to produce a valid structured output.

    Phase 1's fixture fakes only raise this on misuse (unknown fixture key);
    real adapters will raise it after exhausting their internal retries.
    """


@runtime_checkable
class LLMNode(Protocol, Generic[OutputT]):
    """Minimal contract for every LLM-backed node.

    Concrete adapters take whatever inputs they need in their constructor;
    ``run`` is invoked with a ``run_id`` and node-specific keyword args.
    """

    def run(self, *, run_id: str, **inputs: object) -> OutputT: ...
