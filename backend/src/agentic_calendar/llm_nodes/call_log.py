"""``llm_call_log`` contract and append-only store (Phase 8).

Canonical spec: ``docs/specs/llm-call-log.schema.md``.

:class:`LlmCallLog` is the write-only observability record axiom 22 requires:
every provider API call made by one of the four allowed nodes appends exactly
one entry. The record stores identifiers, counts, hashes, and outcome metadata
only — never raw prompts or responses (``extra="forbid"`` makes a raw-content
field structurally impossible).

The contract and store live in ``llm_nodes/`` (the owning region) on purpose:
the import-linter independence set prevents any other region from importing
them, which is the structural form of "observability never feeds runtime
routing." Offline consumers (eval harness, trace CLI) live in this region or
in ``tools/``.
"""

from __future__ import annotations

import threading
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.reason_codes import ReasonCode

#: SHA-256 hex digest shape for ``prompt_hash`` / ``response_hash``.
_SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"


class LlmNodeName(StrEnum):
    """The four allowed LLM nodes (axiom 01); no other caller may log here."""

    STRATEGIST = "strategist"
    PLANNER = "planner"
    REFLECTION_SUMMARY = "reflection_summary"
    USER_FACING_EXPLANATION = "user_facing_explanation"


class ValidationOutcome(StrEnum):
    """Whether the call yielded output that passed boundary re-validation."""

    PASS = "pass"
    FAIL = "fail"


class LlmCallLog(BaseModel):
    """One append-only observability record per provider API call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    llm_call_log_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    plan_version: str | None = Field(default=None, min_length=1)
    node: LlmNodeName
    prompt_version: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    attempt: int = Field(ge=0)
    sdk_retry: int = Field(default=0, ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_creation_tokens: int = Field(default=0, ge=0)
    """Provider ``cache_creation_input_tokens`` (excluded from
    ``input_tokens``); priced at 1.25x the input rate in
    ``cost_estimate_usd`` (5-minute-TTL cache; axiom 09)."""
    cache_read_tokens: int = Field(default=0, ge=0)
    """Provider ``cache_read_input_tokens`` (excluded from ``input_tokens``);
    priced at 0.10x the input rate in ``cost_estimate_usd``."""
    cost_estimate_usd: float = Field(ge=0)
    latency_ms: int = Field(ge=0)
    validation_outcome: ValidationOutcome
    reason_code: ReasonCode | None = None
    cache_hit: bool = False
    truncated: bool = False
    refusal: bool = False
    prompt_hash: str | None = Field(default=None, pattern=_SHA256_HEX_PATTERN)
    response_hash: str | None = Field(default=None, pattern=_SHA256_HEX_PATTERN)
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> LlmCallLog:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _reason_code_matches_outcome(self) -> LlmCallLog:
        is_fail = self.validation_outcome is ValidationOutcome.FAIL
        if is_fail and self.reason_code is None:
            raise ValueError("validation_outcome 'fail' requires a non-null reason_code")
        if not is_fail and self.reason_code is not None:
            raise ValueError("validation_outcome 'pass' must have a null reason_code")
        return self

    @model_validator(mode="after")
    def _refusal_implies_fail(self) -> LlmCallLog:
        """A refusal cannot have produced contract-valid output.

        ``truncated`` is deliberately unconstrained: a truncation that still
        parsed and validated stays ``pass`` (the flag preserves the provider's
        stop reason)."""
        if self.refusal and self.validation_outcome is not ValidationOutcome.FAIL:
            raise ValueError("refusal may be true only when validation_outcome is 'fail'")
        return self


class LlmCallLogStoreError(AgenticCalendarError):
    """Base for llm-call-log-store errors."""


class LlmCallLogAlreadyExistsError(LlmCallLogStoreError):
    """Attempted to append an ``llm_call_log_id`` that already exists."""


@runtime_checkable
class LlmCallLogStore(Protocol):
    """Append/read surface for LLM call logs."""

    def append(self, log: LlmCallLog) -> None: ...

    def list_for_run(self, run_id: str) -> list[LlmCallLog]: ...

    def list_all(self) -> list[LlmCallLog]: ...


class InMemoryLlmCallLogStore:
    """Default Phase 8 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, LlmCallLog] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, log: LlmCallLog) -> None:
        """Append ``log``. Rejects a duplicate id (append-only)."""
        with self._lock:
            if log.llm_call_log_id in self._by_id:
                raise LlmCallLogAlreadyExistsError(log.llm_call_log_id)
            self._by_id[log.llm_call_log_id] = log
            self._order.append(log.llm_call_log_id)

    def list_for_run(self, run_id: str) -> list[LlmCallLog]:
        with self._lock:
            return [self._by_id[i] for i in self._order if self._by_id[i].run_id == run_id]

    def list_all(self) -> list[LlmCallLog]:
        with self._lock:
            return [self._by_id[i] for i in self._order]
